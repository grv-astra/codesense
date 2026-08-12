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

    def test_scan_stores_file_manifest_and_ruleset_version(self):
        from local.api_app.models.orm import Scan
        from datetime import datetime, timezone

        scan = Scan.objects.create(
            project_id="proj1",
            scan_name="S",
            status="completed",
            created_at=datetime.now(timezone.utc),
            file_manifest={"src/app.py": "a" * 64},
            ruleset_version="rules-hash-1",
        )
        reloaded = Scan.objects.get(id=scan.id)
        self.assertEqual(reloaded.file_manifest, {"src/app.py": "a" * 64})
        self.assertEqual(reloaded.ruleset_version, "rules-hash-1")

    def test_scan_file_manifest_defaults_to_empty_dict(self):
        from local.api_app.models.orm import Scan
        from datetime import datetime, timezone

        scan = Scan.objects.create(
            project_id="proj1", scan_name="S", status="queued",
            created_at=datetime.now(timezone.utc),
        )
        self.assertEqual(scan.file_manifest, {})
        self.assertEqual(scan.ruleset_version, "")

    def test_find_baseline_scan_returns_most_recent_completed_matching_ruleset(self):
        from local.api_app.models.orm import Scan
        from scanner.rag.incremental import find_baseline_scan
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        Scan.objects.create(
            project_id="proj-baseline", scan_name="old", status="completed",
            created_at=now - timedelta(hours=2), file_manifest={"a.py": "h1"},
            ruleset_version="v1",
        )
        newest = Scan.objects.create(
            project_id="proj-baseline", scan_name="newer", status="completed",
            created_at=now - timedelta(hours=1), file_manifest={"a.py": "h2"},
            ruleset_version="v1",
        )

        baseline = find_baseline_scan("proj-baseline", "v1")
        self.assertEqual(baseline.id, newest.id)

    def test_find_baseline_scan_ignores_non_completed_scans(self):
        from local.api_app.models.orm import Scan
        from scanner.rag.incremental import find_baseline_scan
        from datetime import datetime, timezone

        Scan.objects.create(
            project_id="proj-inprogress", scan_name="s", status="in_progress",
            created_at=datetime.now(timezone.utc), file_manifest={"a.py": "h1"},
            ruleset_version="v1",
        )
        self.assertIsNone(find_baseline_scan("proj-inprogress", "v1"))

    def test_find_baseline_scan_ignores_mismatched_ruleset_version(self):
        from local.api_app.models.orm import Scan
        from scanner.rag.incremental import find_baseline_scan
        from datetime import datetime, timezone

        Scan.objects.create(
            project_id="proj-rules", scan_name="s", status="completed",
            created_at=datetime.now(timezone.utc), file_manifest={"a.py": "h1"},
            ruleset_version="v1-old",
        )
        self.assertIsNone(find_baseline_scan("proj-rules", "v2-new"))

    def test_find_baseline_scan_ignores_empty_manifest(self):
        from local.api_app.models.orm import Scan
        from scanner.rag.incremental import find_baseline_scan
        from datetime import datetime, timezone

        Scan.objects.create(
            project_id="proj-empty", scan_name="s", status="completed",
            created_at=datetime.now(timezone.utc), file_manifest={}, ruleset_version="v1",
        )
        self.assertIsNone(find_baseline_scan("proj-empty", "v1"))

    def test_find_baseline_scan_returns_none_for_unknown_project(self):
        from scanner.rag.incremental import find_baseline_scan
        self.assertIsNone(find_baseline_scan("no-such-project", "v1"))
