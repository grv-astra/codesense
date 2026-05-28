from datetime import datetime, timezone
from django.test import TestCase
from local.api_app.views.dashboard_views import DashboardView
from local.api_app.models.orm import Project, Scan, Finding


class DashboardAggregationTests(TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc)
        self.p = Project.objects.create(name="P", created_at=now)
        self.s = Scan.objects.create(project_id=self.p.id, scan_name="S", status="completed",
                                     source="zip", findings=2, created_at=now,
                                     metrics={"total_loc": 10, "total_functions": 2,
                                              "languages": ["Python", "Go"]})
        Finding.objects.create(scan_id=self.s.id, severity="critical", cwe="CWE-89: SQLi",
                               created_at=now)
        Finding.objects.create(scan_id=self.s.id, severity="high", cwe="CWE-79: XSS",
                               created_at=now)
        self.view = DashboardView()

    def test_system_status(self):
        out = self.view._get_system_status()
        self.assertEqual(out["total_scans"], 1)
        self.assertEqual(out["counts"].get("completed"), 1)

    def test_severity_counts(self):
        self.assertEqual(self.view._get_severity_counts(),
                         {"critical": 1, "high": 1, "medium": 0, "low": 0})

    def test_language_distribution(self):
        langs = {row["language"]: row for row in self.view._get_language_distribution()}
        self.assertIn("Python", langs)
        self.assertEqual(langs["Python"]["scans"], 1)
        self.assertEqual(langs["Python"]["vulnerabilities"], 2)

    def test_top_cwe(self):
        ids = [row["id"] for row in self.view._get_top_cwe()]
        self.assertIn("CWE-89", ids)

    def test_scans_by_project(self):
        rows = self.view._get_scans_by_project()
        self.assertEqual(rows[0]["project"], "P")
        self.assertEqual(rows[0]["scans"], 1)
        self.assertEqual(rows[0]["critical"], 1)

    def test_scan_distribution(self):
        rows = self.view._get_scan_distribution()
        self.assertEqual(rows[0]["name"], "ZIP Upload")
        self.assertEqual(rows[0]["value"], 1)

    def test_findings_trend_has_seven_days(self):
        self.assertEqual(len(self.view._get_findings_trend()), 7)
