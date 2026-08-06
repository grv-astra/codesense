import tempfile
from pathlib import Path
from unittest import mock

import bcrypt
from django.test import SimpleTestCase, override_settings

from licenses.services import activation as act

_PASSWORD = "correct-horse-battery-staple"
_HASH = bcrypt.hashpw(_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


class ActivationTests(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._ov = override_settings(DATA_DIR=self.dir, ACTIVATION_PASSWORD_HASH=_HASH)
        self._ov.enable()
        # Isolate the Windows registry backend with an in-memory store, same
        # approach as test_offline_license.py -- otherwise tests would read/
        # write the REAL HKCU\Software\CodeSense\activation key.
        self._reg = {}
        self._reg_read = mock.patch.object(
            act, "_registry_read", side_effect=lambda: self._reg.get("rec"))
        self._reg_write = mock.patch.object(
            act, "_registry_write", side_effect=lambda rec: self._reg.__setitem__("rec", rec))
        self._reg_read.start()
        self._reg_write.start()
        # Isolate the machine fingerprint too -- tests need to simulate
        # "a different machine" without depending on the real host's identity.
        self._fp = "machine-a"
        self._fp_patch = mock.patch.object(act, "machine_fingerprint", side_effect=lambda: self._fp)
        self._fp_patch.start()

    def tearDown(self):
        self._reg_read.stop()
        self._reg_write.stop()
        self._fp_patch.stop()
        self._ov.disable()

    def _file(self):
        return Path(self.dir) / "activation.json"

    def test_unconfigured_build_is_always_activated(self):
        with override_settings(ACTIVATION_PASSWORD_HASH=None):
            self.assertFalse(act.is_configured())
            self.assertTrue(act.is_activated())

    def test_configured_build_not_activated_by_default(self):
        self.assertTrue(act.is_configured())
        self.assertFalse(act.is_activated())

    def test_wrong_password_does_not_activate(self):
        self.assertFalse(act.activate("nope"))
        self.assertFalse(act.is_activated())

    def test_correct_password_activates_and_persists(self):
        self.assertTrue(act.activate(_PASSWORD))
        self.assertTrue(act.is_activated())
        self.assertTrue(self._file().exists())

    def test_activation_does_not_carry_to_a_different_machine(self):
        self.assertTrue(act.activate(_PASSWORD))
        self.assertTrue(act.is_activated())
        # Simulate the activated app folder being copied to a different
        # machine -- the file+registry records are still there, but this
        # machine's own fingerprint no longer matches what's stored.
        self._fp = "machine-b"
        self.assertFalse(act.is_activated())

    def test_tampered_record_is_rejected(self):
        # A valid record in EITHER store is enough (redundancy, same as the
        # license system) -- so both must be forged to actually defeat this.
        act.activate(_PASSWORD)
        rec = act._file_read()
        rec["sig"] = "deadbeef"
        act._file_write(rec)
        act._registry_write(dict(rec))
        self.assertFalse(act.is_activated())

    def test_tampering_only_one_store_does_not_deactivate(self):
        act.activate(_PASSWORD)
        rec = act._file_read()
        rec["sig"] = "deadbeef"
        act._file_write(rec)  # file corrupted, registry copy still valid
        self.assertTrue(act.is_activated())

    def test_file_alone_is_sufficient_when_registry_is_empty(self):
        act.activate(_PASSWORD)
        self._reg.clear()  # only the file copy survives
        self.assertTrue(act.is_activated())

    def test_registry_alone_is_sufficient_when_file_is_missing(self):
        act.activate(_PASSWORD)
        self._file().unlink()
        self.assertTrue(act.is_activated())
