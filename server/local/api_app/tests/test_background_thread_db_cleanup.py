"""Regression coverage for the "stuck backend process shows a stale/empty DB
view" bug (packaged desktop app, DATA_DIR/app.sqlite3): scan_views.py and
scanner/views.py spawn plain `threading.Thread` workers that touch the Django
ORM but never go through request_started/request_finished, so their DB
connections were never explicitly closed. These tests lock in the fix
(`close_old_connections()` in each thread's `finally` block) and the
underlying invariant it protects: a fresh ORM query on one connection must
see a write committed by a completely independent connection, even while
another thread is mid-transaction on a `bulk_create`.

Uses TransactionTestCase (real commits, no wrapping/rollback) against a real
sqlite file (see DATABASES["default"]["TEST"] in settings.py) so a plain
sqlite3.connect() from the test can act as a genuinely separate connection --
this is what makes cross-connection visibility even observable.
"""
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone

from django.db import close_old_connections, connections, transaction
from django.test import TransactionTestCase

from local.auth_app.models.orm import User


class BackgroundThreadClosesConnectionTests(TransactionTestCase):
    def test_background_thread_leaves_no_open_connection_behind(self):
        """Mirrors the fixed run_scan()/run_github_scan() pattern: a plain
        thread does ORM work, then calls close_old_connections() in `finally`.
        After the thread exits, its connection must be closed, not leaked."""
        observed = {}

        def worker():
            try:
                User.objects.filter(email="nobody@nowhere.invalid").exists()
                wrapper = connections["default"]
                observed["had_connection_while_running"] = wrapper.connection is not None
            finally:
                close_old_connections()
                observed["connection_after_cleanup"] = connections["default"].connection

        t = threading.Thread(target=worker)
        t.start()
        t.join(timeout=5)

        self.assertTrue(observed.get("had_connection_while_running"))
        self.assertIsNone(
            observed.get("connection_after_cleanup"),
            "background thread must not leave its DB connection open when it exits",
        )

    def test_external_write_visible_during_and_after_background_bulk_create(self):
        """Direct regression test for the reported symptom: while a background
        thread holds an ORM bulk_create() open inside transaction.atomic()
        (the exact pattern FindingModel.insert_many uses for scan persistence),
        a row committed by a totally separate sqlite3 connection must still be
        visible to a fresh ORM read -- both mid-transaction and after the
        background thread finishes and cleans up its connection."""
        db_path = connections["default"].settings_dict["NAME"]

        hold_open = threading.Event()
        release = threading.Event()
        errors = []

        def background_worker():
            try:
                with transaction.atomic():
                    now = datetime.now(timezone.utc)
                    User.objects.bulk_create([
                        User(email=f"bg-{uuid.uuid4().hex[:8]}@test.local", password="x",
                             name="bg", role="user", deleted=True,
                             created_at=now, updated_at=now)
                    ])
                    hold_open.set()
                    release.wait(timeout=5)
            except Exception as e:  # pragma: no cover - surfaced via errors list
                errors.append(e)
            finally:
                close_old_connections()

        t = threading.Thread(target=background_worker)
        t.start()
        self.assertTrue(hold_open.wait(timeout=5), "background thread never reached its atomic() hold point")

        # Simulate a completely independent writer (e.g. an external script,
        # or another process) committing directly to the same sqlite file
        # while the background thread's transaction is still open.
        probe_email = f"probe-{uuid.uuid4().hex[:8]}@test.local"
        raw = sqlite3.connect(db_path, timeout=5)
        try:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
            raw.execute(
                "INSERT INTO users (id, email, password, name, company, role, deleted, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
                (uuid.uuid4().hex, probe_email, "hash", "probe", None, "user", now, now),
            )
            raw.commit()
        finally:
            raw.close()

        # A fresh ORM read (its own connection) must see the externally
        # committed row right away -- this is the exact check that failed
        # in production ("User doesn't exist" for a row that was on disk).
        self.assertTrue(
            User.objects.filter(email=probe_email).exists(),
            "externally committed row not visible while a background thread's "
            "atomic() transaction is open on another connection",
        )

        release.set()
        t.join(timeout=5)
        self.assertEqual(errors, [])

        # Still visible after the background thread finished and closed its
        # own connection.
        self.assertTrue(User.objects.filter(email=probe_email).exists())
