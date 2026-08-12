import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from django.test import TestCase

from local.api_app.models.orm import Finding, Scan
from local.api_app.models.project_models import ProjectModel
from scanner.rag.scanner import scan_folder

_HAVE_ENGINE = bool(os.getenv("SEMGREP_BIN")) and bool(os.getenv("SEMGREP_RULES_DIR"))


@unittest.skipUnless(_HAVE_ENGINE, "set SEMGREP_BIN + SEMGREP_RULES_DIR to run this test")
class IncrementalScanIntegrationTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="codesense_incr_integration_")
        self.project_id = ProjectModel.create({"name": "incr-test", "created_by": "u"})["id"]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, rel_path, content):
        full = os.path.join(self.tmp, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)

    def _create_scan_row(self, scan_id, scan_name):
        # scan_folder()'s progress updates go through update_progress(), which
        # does Scan.objects.filter(id=scan_id).update(...) -- an UPDATE, not a
        # create. In production the calling view creates the Scan row up front
        # via ScanModel.create() (see local/api_app/views/scan_views.py) and
        # only then invokes scan_folder() with that row's id. Mirror that here
        # so the id we pass to scan_folder actually has a row to update.
        Scan.objects.create(
            id=scan_id, project_id=self.project_id, scan_name=scan_name,
            status="queued", created_at=datetime.now(timezone.utc), deleted=False,
        )

    def test_second_scan_carries_forward_unchanged_and_detects_changed(self):
        vulnerable_sql = (
            "from sqlalchemy import text\n"
            "def run(conn, user_input):\n"
            "    return conn.execute(text('SELECT * FROM t WHERE id=' + user_input))\n"
        )
        self._write("stable.py", vulnerable_sql)
        self._write("to_be_removed.py", vulnerable_sql)
        self._write("to_be_changed.py", "print('safe, no findings here')\n")

        self._create_scan_row("scan-1", "first")
        scan_folder(
            folder_path=self.tmp, scan_id="scan-1", triggered_by="u",
            scan_name="first", project_id=self.project_id,
        )
        first_scan = Scan.objects.get(id="scan-1")
        self.assertEqual(first_scan.status, "completed")
        first_findings = list(Finding.objects.filter(scan_id="scan-1", deleted=False))
        self.assertTrue(any(f.file_path.startswith("stable.py") for f in first_findings))
        self.assertTrue(any(f.file_path.startswith("to_be_removed.py") for f in first_findings))

        os.remove(os.path.join(self.tmp, "to_be_removed.py"))
        with open(os.path.join(self.tmp, "to_be_changed.py"), "w") as f:
            f.write(vulnerable_sql)
        self._write("added.py", vulnerable_sql)

        self._create_scan_row("scan-2", "second")
        scan_folder(
            folder_path=self.tmp, scan_id="scan-2", triggered_by="u",
            scan_name="second", project_id=self.project_id,
        )
        second_scan = Scan.objects.get(id="scan-2")
        self.assertEqual(second_scan.status, "completed")
        second_findings = list(Finding.objects.filter(scan_id="scan-2", deleted=False))

        stable_finding = next(f for f in second_findings if f.file_path.startswith("stable.py"))
        self.assertEqual(stable_finding.first_seen_scan_id, "scan-1")

        changed_finding = next(f for f in second_findings if f.file_path.startswith("to_be_changed.py"))
        self.assertEqual(changed_finding.first_seen_scan_id, "scan-2")

        self.assertTrue(any(f.file_path.startswith("added.py") for f in second_findings))
        self.assertFalse(any(f.file_path.startswith("to_be_removed.py") for f in second_findings))

    def test_multi_hop_provenance_survives_three_consecutive_scans(self):
        vulnerable_sql = (
            "from sqlalchemy import text\n"
            "def run(conn, user_input):\n"
            "    return conn.execute(text('SELECT * FROM t WHERE id=' + user_input))\n"
        )
        self._write("stable.py", vulnerable_sql)

        self._create_scan_row("scan-hop-1", "first")
        scan_folder(
            folder_path=self.tmp, scan_id="scan-hop-1", triggered_by="u",
            scan_name="first", project_id=self.project_id,
        )
        first_findings = list(Finding.objects.filter(scan_id="scan-hop-1", deleted=False))
        self.assertTrue(any(f.file_path.startswith("stable.py") for f in first_findings))

        self._create_scan_row("scan-hop-2", "second")
        scan_folder(
            folder_path=self.tmp, scan_id="scan-hop-2", triggered_by="u",
            scan_name="second", project_id=self.project_id,
        )
        second_finding = next(
            f for f in Finding.objects.filter(scan_id="scan-hop-2", deleted=False)
            if f.file_path.startswith("stable.py")
        )
        self.assertEqual(second_finding.first_seen_scan_id, "scan-hop-1")

        self._create_scan_row("scan-hop-3", "third")
        scan_folder(
            folder_path=self.tmp, scan_id="scan-hop-3", triggered_by="u",
            scan_name="third", project_id=self.project_id,
        )
        third_finding = next(
            f for f in Finding.objects.filter(scan_id="scan-hop-3", deleted=False)
            if f.file_path.startswith("stable.py")
        )
        self.assertEqual(third_finding.first_seen_scan_id, "scan-hop-1")

    def test_ruleset_version_change_forces_full_rescan(self):
        from unittest.mock import patch

        vulnerable_sql = (
            "from sqlalchemy import text\n"
            "def run(conn, user_input):\n"
            "    return conn.execute(text('SELECT * FROM t WHERE id=' + user_input))\n"
        )
        self._write("stable.py", vulnerable_sql)

        self._create_scan_row("scan-a", "first")
        scan_folder(
            folder_path=self.tmp, scan_id="scan-a", triggered_by="u",
            scan_name="first", project_id=self.project_id,
        )

        self._create_scan_row("scan-b", "second")
        with patch("scanner.rag.scanner.compute_ruleset_version", return_value="a-different-ruleset-hash"), \
             patch("scanner.rag.scanner.lsast_scan_folder") as mock_lsast:
            mock_lsast.return_value = ([], [])
            scan_folder(
                folder_path=self.tmp, scan_id="scan-b", triggered_by="u",
                scan_name="second", project_id=self.project_id,
            )
            _args, kwargs = mock_lsast.call_args
            self.assertIsNone(kwargs.get("only_files"))
