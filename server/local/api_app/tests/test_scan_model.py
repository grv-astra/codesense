from django.test import TestCase
from local.api_app.models.scan_models import ScanModel
from local.api_app.models.orm import Finding
from datetime import datetime, timezone


class ScanModelTests(TestCase):
    def test_create_defaults_and_string_ids(self):
        s = ScanModel.create({"project_id": "proj1", "scan_name": "S1", "triggered_by": "u1"})
        self.assertEqual(s["project_id"], "proj1")
        self.assertEqual(s["status"], "queued")
        self.assertEqual(s["source"], "zip")
        self.assertEqual(s["metrics"], {"total_functions": 0, "total_loc": 0, "languages": []})

    def test_update_status_and_progress(self):
        s = ScanModel.create({"project_id": "p", "scan_name": "S"})
        ScanModel.update_status(s["id"], "in_progress")
        self.assertEqual(ScanModel.find_by_id(s["id"])["status"], "in_progress")
        updated = ScanModel.update_progress(s["id"], files_scanned=3, findings=7)
        self.assertEqual(updated["files_scanned"], 3)
        self.assertEqual(updated["findings"], 7)

    def test_find_by_project_pagination(self):
        ScanModel.create({"project_id": "shared", "scan_name": "A"})
        ScanModel.create({"project_id": "shared", "scan_name": "B"})
        result = ScanModel.find_by_project("shared", page=1, limit=1)
        self.assertEqual(result["pagination"]["total"], 2)
        self.assertEqual(len(result["scans"]), 1)

    def test_delete_scan_removes_scan_and_findings(self):
        s = ScanModel.create({"project_id": "p", "scan_name": "S"})
        Finding.objects.create(scan_id=s["id"], created_at=datetime.now(timezone.utc))
        self.assertTrue(ScanModel.delete_scan(s["id"]))
        self.assertIsNone(ScanModel.find_by_id(s["id"]))
        self.assertEqual(Finding.objects.filter(scan_id=s["id"]).count(), 0)

    def test_find_by_id_includes_per_scan_severity_counts(self):
        s = ScanModel.create({"project_id": "p", "scan_name": "S"})
        other = ScanModel.create({"project_id": "p", "scan_name": "Other"})
        now = datetime.now(timezone.utc)
        Finding.objects.create(scan_id=s["id"], created_at=now, severity="critical")
        Finding.objects.create(scan_id=s["id"], created_at=now, severity="critical")
        Finding.objects.create(scan_id=s["id"], created_at=now, severity="low")
        # A finding on a different scan must not bleed into this scan's counts.
        Finding.objects.create(scan_id=other["id"], created_at=now, severity="high")
        result = ScanModel.find_by_id(s["id"])
        self.assertEqual(
            result["severity_counts"],
            {"critical": 2, "high": 0, "medium": 0, "low": 1},
        )

    def test_find_by_id_severity_counts_all_zero_with_no_findings(self):
        s = ScanModel.create({"project_id": "p", "scan_name": "S"})
        result = ScanModel.find_by_id(s["id"])
        self.assertEqual(
            result["severity_counts"],
            {"critical": 0, "high": 0, "medium": 0, "low": 0},
        )
