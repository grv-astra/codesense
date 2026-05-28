import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from licenses.services import offline_license as lic


def _ago(days):
    return datetime.now(timezone.utc) - timedelta(days=days)


class OfflineLicenseTests(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._ov = override_settings(DATA_DIR=self.dir, LICENSE_DURATION_DAYS=90)
        self._ov.enable()

    def tearDown(self):
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
        lic._file_write(lic._make_record(_ago(100), _ago(100)))
        self.assertTrue(lic.is_write_blocked())
        lic._file_write(lic._make_record(_ago(1), _ago(1)))
        self.assertFalse(lic.is_write_blocked())
