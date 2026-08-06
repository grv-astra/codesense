import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from licenses.services import trial
from local.api_app.models.orm import Scan, SbomScan, TrialUsage


def _mk_scan(status):
    return Scan.objects.create(
        project_id="p", scan_name="s", status=status, source="zip",
        created_at=datetime.now(timezone.utc),
    )


def _mk_sbom_scan(status):
    return SbomScan.objects.create(
        project_id="p", scan_name="s", status=status,
        created_at=datetime.now(timezone.utc),
    )


class TrialGateTests(TestCase):
    def setUp(self):
        os.environ.pop("TRIAL_MODE", None)
        os.environ.pop("TRIAL_SCAN_LIMIT", None)

    def test_disabled_by_default_is_unlimited(self):
        self.assertFalse(trial.enabled())
        self.assertTrue(trial.can_start(trial.CODE))
        self.assertTrue(trial.can_start(trial.SBOM))
        self.assertEqual(trial.status()["trial_mode"], False)

    def test_record_completion_is_noop_when_disabled(self):
        trial.record_completion(trial.CODE)
        self.assertEqual(TrialUsage.objects.count(), 0)  # nothing created/incremented

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_gate_blocks_after_limit(self):
        self.assertTrue(trial.can_start(trial.CODE))          # 0/2
        trial.record_completion(trial.CODE)
        trial.record_completion(trial.CODE)
        self.assertEqual(trial.used(trial.CODE), 2)
        self.assertFalse(trial.can_start(trial.CODE))         # 2/2 -> blocked
        self.assertEqual(
            trial.status(),
            {
                "trial_mode": True,
                "code": {"limit": 2, "used": 2, "remaining": 0},
                "sbom": {"limit": 2, "used": 0, "remaining": 2},
            },
        )

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_code_and_sbom_limits_are_independent(self):
        """Exhausting the code-scan allowance must not touch the SBOM
        allowance, and vice versa -- each type gets its own N scans."""
        trial.record_completion(trial.CODE)
        trial.record_completion(trial.CODE)
        self.assertFalse(trial.can_start(trial.CODE))   # code: 2/2 -> blocked
        self.assertTrue(trial.can_start(trial.SBOM))     # sbom: 0/2 -> still open

        trial.record_completion(trial.SBOM)
        trial.record_completion(trial.SBOM)
        self.assertFalse(trial.can_start(trial.SBOM))    # sbom: 2/2 -> blocked too now

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_in_progress_scans_count_against_that_types_limit_only(self):
        trial.record_completion(trial.CODE)          # code used=1
        _mk_scan("in_progress")                       # +1 code in-progress -> 2
        self.assertFalse(trial.can_start(trial.CODE))  # blocked even though used (1) < limit (2)
        self.assertTrue(trial.can_start(trial.SBOM))    # unaffected

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_in_progress_sbom_scans_do_not_count_against_code_limit(self):
        _mk_sbom_scan("in_progress")
        _mk_sbom_scan("in_progress")
        self.assertEqual(trial.in_progress(trial.SBOM), 2)
        self.assertEqual(trial.in_progress(trial.CODE), 0)
        self.assertFalse(trial.can_start(trial.SBOM))
        self.assertTrue(trial.can_start(trial.CODE))

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_completed_and_failed_scans_do_not_count_as_in_progress(self):
        _mk_scan("completed")
        _mk_scan("failed")
        self.assertEqual(trial.in_progress(trial.CODE), 0)
        self.assertTrue(trial.can_start(trial.CODE))

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_completed_and_failed_sbom_scans_do_not_count_as_in_progress(self):
        _mk_sbom_scan("completed")
        _mk_sbom_scan("failed")
        self.assertEqual(trial.in_progress(trial.SBOM), 0)
        self.assertTrue(trial.can_start(trial.SBOM))

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_interrupted_scans_count_against_limit(self):
        trial.record_completion(trial.CODE)          # used=1
        _mk_scan("interrupted")                        # +1 pending-resume -> used+ip = 2
        self.assertFalse(trial.can_start(trial.CODE))  # blocked even though used (1) < limit (2)

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_cancelled_scans_do_not_count_against_limit(self):
        _mk_scan("cancelled")
        self.assertEqual(trial.in_progress(trial.CODE), 0)
        self.assertTrue(trial.can_start(trial.CODE))

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_unknown_scan_type_raises(self):
        with self.assertRaises(ValueError):
            trial.can_start("not-a-real-type")


class ModelDeletionOnExhaustionTests(TestCase):
    """The bundled AI model is only used by the code-scan verifier -- SBOM
    scanning never touches it -- so it should be deleted the moment the CODE
    trial allowance (not SBOM's) is exhausted, to reclaim disk space."""

    def setUp(self):
        os.environ.pop("TRIAL_MODE", None)
        os.environ.pop("TRIAL_SCAN_LIMIT", None)
        self.data_dir = tempfile.mkdtemp()
        self._ov = override_settings(DATA_DIR=self.data_dir)
        self._ov.enable()
        self.model_dir = Path(self.data_dir) / "model"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.model_dir / "astra.gguf"
        self.model_path.write_bytes(b"fake gguf bytes")

    def tearDown(self):
        self._ov.disable()

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_model_deleted_once_code_trial_is_exhausted(self):
        marker = self.model_dir / "TRIAL_EXHAUSTED"
        trial.record_completion(trial.CODE)
        self.assertTrue(self.model_path.exists())  # 1/2 -- not exhausted yet
        self.assertFalse(marker.exists())
        trial.record_completion(trial.CODE)
        self.assertFalse(self.model_path.exists())  # 2/2 -- exhausted, deleted
        # The marker is what stops main.rs's asset-setup from silently
        # rebuilding the model right back from its bundled shards on the next
        # launch -- without it, deleting just the file achieves nothing.
        self.assertTrue(marker.exists())

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_model_survives_sbom_exhaustion_alone(self):
        trial.record_completion(trial.SBOM)
        trial.record_completion(trial.SBOM)
        self.assertFalse(trial.can_start(trial.SBOM))  # sbom exhausted
        self.assertTrue(self.model_path.exists())       # but code never was -- model stays
        self.assertFalse((self.model_dir / "TRIAL_EXHAUSTED").exists())

    def test_no_deletion_when_trial_mode_is_off(self):
        trial.record_completion(trial.CODE)  # no-op entirely
        self.assertTrue(self.model_path.exists())
        self.assertFalse((self.model_dir / "TRIAL_EXHAUSTED").exists())

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_missing_model_file_does_not_raise(self):
        self.model_path.unlink()
        trial.record_completion(trial.CODE)
        trial.record_completion(trial.CODE)  # exhausts -- must not blow up on a missing file
