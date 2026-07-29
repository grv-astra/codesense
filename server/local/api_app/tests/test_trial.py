import os
from datetime import datetime, timezone
from unittest import mock

from django.test import TestCase

from licenses.services import trial
from local.api_app.models.orm import Scan, TrialUsage


def _mk_scan(status):
    return Scan.objects.create(
        project_id="p", scan_name="s", status=status, source="zip",
        created_at=datetime.now(timezone.utc),
    )


class TrialGateTests(TestCase):
    def setUp(self):
        os.environ.pop("TRIAL_MODE", None)
        os.environ.pop("TRIAL_SCAN_LIMIT", None)

    def test_disabled_by_default_is_unlimited(self):
        self.assertFalse(trial.enabled())
        self.assertTrue(trial.can_start())
        self.assertEqual(trial.status()["trial_mode"], False)

    def test_record_completion_is_noop_when_disabled(self):
        trial.record_completion()
        self.assertEqual(TrialUsage.objects.count(), 0)  # nothing created/incremented

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_gate_blocks_after_limit(self):
        self.assertTrue(trial.can_start())          # 0/2
        trial.record_completion()
        trial.record_completion()
        self.assertEqual(trial.used(), 2)
        self.assertFalse(trial.can_start())         # 2/2 -> blocked
        self.assertEqual(trial.status(), {"trial_mode": True, "limit": 2, "used": 2, "remaining": 0})

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_in_progress_scans_count_against_limit(self):
        trial.record_completion()                   # used=1
        _mk_scan("in_progress")                     # +1 in-progress -> used+ip = 2
        self.assertFalse(trial.can_start())         # blocked even though used (1) < limit (2)

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_completed_and_failed_scans_do_not_count_as_in_progress(self):
        _mk_scan("completed")
        _mk_scan("failed")
        self.assertEqual(trial.in_progress(), 0)
        self.assertTrue(trial.can_start())
