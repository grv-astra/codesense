import json
import plistlib
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock, skipUnless

from django.test import SimpleTestCase, override_settings

from licenses.services import offline_license as lic


def _ago(days):
    return datetime.now(timezone.utc) - timedelta(days=days)


class OfflineLicenseTests(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        # Redirect the macOS plist second store into the temp dir so tests stay
        # hermetic (this build host is darwin → the plist backend is live).
        self._plist = str(Path(self.dir) / "second_store.plist")
        self._ov = override_settings(
            DATA_DIR=self.dir,
            LICENSE_DURATION_DAYS=90,
            LICENSE_PLIST_PATH=self._plist,
        )
        self._ov.enable()
        # Isolate the Windows registry backend with an in-memory store. Without
        # this, on Windows the tests read/write the REAL HKCU\Software\CodeSense
        # stamp — they pollute each other (one test's expired stamp leaks into the
        # next) AND can corrupt the live app's license stamp. No-op on macOS/Linux.
        self._reg = {}
        self._reg_read = mock.patch.object(
            lic, "_registry_read", side_effect=lambda: self._reg.get("rec"))
        self._reg_write = mock.patch.object(
            lic, "_registry_write", side_effect=lambda rec: self._reg.__setitem__("rec", rec))
        self._reg_read.start()
        self._reg_write.start()

    def tearDown(self):
        self._reg_read.stop()
        self._reg_write.stop()
        self._ov.disable()

    def _file(self):
        return Path(self.dir) / "license.json"

    def test_first_run_creates_active_stamp(self):
        state = lic.get_state()
        self.assertEqual(state["state"], lic.ACTIVE)
        self.assertTrue(self._file().exists())
        self.assertGreaterEqual(state["days_remaining"], 89)

    def test_expired_when_first_seen_past_duration(self):
        lic._file_write(lic._make_record(_ago(100), _ago(100)))
        self.assertEqual(lic.get_state()["state"], lic.EXPIRED)

    def test_expiring_within_window(self):
        lic._file_write(lic._make_record(_ago(85), _ago(85)))
        state = lic.get_state()
        self.assertEqual(state["state"], lic.EXPIRING)
        self.assertLessEqual(state["days_remaining"], 7)

    def test_tamper_when_signature_invalid(self):
        rec = lic._make_record(_ago(1), _ago(1))
        rec["sig"] = "deadbeef"
        lic._file_write(rec)
        self.assertEqual(lic.get_state()["state"], lic.TAMPERED)

    def test_tamper_when_first_seen_edited(self):
        rec = lic._make_record(_ago(1), _ago(1))
        rec["first_seen"] = _ago(0).isoformat()  # edited without re-signing
        lic._file_write(rec)
        self.assertEqual(lic.get_state()["state"], lic.TAMPERED)

    def test_clock_rollback_detected(self):
        # last_seen high-water-mark is in the FUTURE -> system clock went backwards
        future = datetime.now(timezone.utc) + timedelta(days=10)
        lic._file_write(lic._make_record(_ago(1), future))
        self.assertEqual(lic.get_state()["state"], lic.TAMPERED)

    def test_corrupt_file_is_tamper(self):
        self._file().write_text("{not json", encoding="utf-8")
        self.assertEqual(lic.get_state()["state"], lic.TAMPERED)

    def test_high_water_mark_advances(self):
        lic.get_state()  # stamp now
        rec = json.loads(self._file().read_text())
        self.assertTrue(lic._is_valid(rec))
        # a subsequent read keeps it valid and active
        self.assertEqual(lic.get_state()["state"], lic.ACTIVE)

    def test_is_write_blocked(self):
        # Write through ALL stores: with a redundant second store, rewriting only
        # one copy intentionally can't move the clock (see the macOS plist tests).
        lic._write_all(lic._make_record(_ago(100), _ago(100)))
        self.assertTrue(lic.is_write_blocked())
        lic._write_all(lic._make_record(_ago(1), _ago(1)))
        self.assertFalse(lic.is_write_blocked())

    @skipUnless(sys.platform == "darwin", "macOS-only license second store")
    def test_macos_plist_is_redundant_second_store(self):
        # First run stamps both the DATA_DIR file and the macOS plist second store.
        self.assertEqual(lic.get_state()["state"], lic.ACTIVE)
        self.assertTrue(Path(self._plist).exists())
        # Deleting the DATA_DIR copy must NOT reset the 90-day clock.
        self._file().unlink()
        state = lic.get_state()
        self.assertEqual(state["state"], lic.ACTIVE)
        self.assertGreaterEqual(state["days_remaining"], 89)
        self.assertTrue(self._file().exists())  # self-healed from the plist

    @skipUnless(sys.platform == "darwin", "macOS-only license second store")
    def test_macos_forged_plist_is_tamper(self):
        lic.get_state()  # stamp both stores
        with Path(self._plist).open("rb") as fh:
            rec = plistlib.load(fh)
        rec["sig"] = "deadbeef"  # invalidate without re-signing
        with Path(self._plist).open("wb") as fh:
            plistlib.dump(rec, fh)
        self.assertEqual(lic.get_state()["state"], lic.TAMPERED)
