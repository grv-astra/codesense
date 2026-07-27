from datetime import datetime, timedelta, timezone
from django.test import TestCase
from local.api_app.views.dashboard_views import DashboardView
from local.api_app.models.orm import Project, Scan, Finding, SbomScan


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
        rows = {r["name"]: r["value"] for r in self.view._get_scan_distribution()}
        # distribution is now Code (SAST) vs SBOM (SCA), not zip vs github
        self.assertEqual(rows["Code Scans"], 1)
        self.assertEqual(rows["SBOM Scans"], 0)

    def test_findings_trend_has_seven_days(self):
        self.assertEqual(len(self.view._get_findings_trend()), 7)

    def test_findings_trend_respects_days_param(self):
        self.assertEqual(len(self.view._get_findings_trend(days=30)), 30)
        self.assertEqual(len(self.view._get_findings_trend(days=90)), 90)

    def test_findings_trend_includes_setup_finding_on_last_day(self):
        # setUp's two findings were created "now", which is the last bucket
        # regardless of the requested window size.
        trend90 = self.view._get_findings_trend(days=90)
        self.assertEqual(trend90[-1]["total"], 2)

    def test_parse_trend_days_defaults_and_clamps(self):
        from unittest.mock import Mock
        self.assertEqual(self.view._parse_trend_days(Mock(query_params={})), 7)
        self.assertEqual(self.view._parse_trend_days(Mock(query_params={"trend_days": "30"})), 30)
        self.assertEqual(self.view._parse_trend_days(Mock(query_params={"trend_days": "90"})), 90)
        # unsupported/garbage values fall back to the 7-day default
        self.assertEqual(self.view._parse_trend_days(Mock(query_params={"trend_days": "14"})), 7)
        self.assertEqual(self.view._parse_trend_days(Mock(query_params={"trend_days": "nope"})), 7)

    def test_recent_scans_merges_code_and_sbom_ordered_newest_first(self):
        older = datetime.now(timezone.utc) - timedelta(hours=2)
        newer = datetime.now(timezone.utc) - timedelta(minutes=1)
        SbomScan.objects.create(project_id=self.p.id, scan_name="SBOM1", status="completed",
                                 vulnerabilities=4, created_at=older)
        Scan.objects.create(project_id=self.p.id, scan_name="CODE2", status="queued",
                             source="zip", findings=0, created_at=newer)
        rows = self.view._get_recent_scans(limit=10)

        # newest first: the "CODE2" scan (1 min ago) before setUp's "S" (now is oldest of
        # these three once CODE2/self.s share "now"-ish timestamps) -- assert ordering by
        # comparing positions instead of exact timestamps.
        names = [r["scan_name"] for r in rows]
        self.assertIn("CODE2", names)
        self.assertIn("SBOM1", names)
        self.assertIn("S", names)
        self.assertLess(names.index("CODE2"), names.index("SBOM1"))

    def test_recent_scans_shape_and_type(self):
        rows = self.view._get_recent_scans(limit=10)
        row = next(r for r in rows if r["scan_name"] == "S")
        self.assertEqual(row["type"], "code")
        self.assertEqual(row["project"], "P")
        self.assertEqual(row["status"], "completed")
        self.assertEqual(row["findings"], 2)

    def test_recent_scans_respects_limit(self):
        for i in range(5):
            Scan.objects.create(project_id=self.p.id, scan_name=f"C{i}", status="completed",
                                 source="zip", findings=0, created_at=datetime.now(timezone.utc))
        rows = self.view._get_recent_scans(limit=3)
        self.assertEqual(len(rows), 3)

    def test_top_counts_trend_shape(self):
        trend = self.view._get_top_counts_trend()
        for key, period in (
            ("users", "than last week"),
            ("projects", "than last month"),
            ("scans", "than yesterday"),
            ("sbom_scans", "than last week"),
        ):
            self.assertIn(key, trend)
            self.assertEqual(trend[key]["period"], period)
            self.assertIsInstance(trend[key]["pct"], float)

    def test_top_counts_trend_no_prior_period_is_100_pct(self):
        # setUp's project/scan were created "now", so nothing existed a week/month/day ago.
        trend = self.view._get_top_counts_trend()
        self.assertEqual(trend["projects"]["pct"], 100.0)
        self.assertEqual(trend["scans"]["pct"], 100.0)

    def test_top_counts_trend_percentage_math(self):
        old = datetime.now(timezone.utc) - timedelta(days=2)
        Scan.objects.create(project_id=self.p.id, scan_name="OLD", status="completed",
                             source="zip", findings=0, created_at=old)
        # current = 2 (setUp's "now" scan + this 2-day-old one), previous (<=1 day ago) = 1
        trend = self.view._get_top_counts_trend()
        self.assertEqual(trend["scans"]["pct"], 100.0)

    def test_top_counts_trend_zero_when_nothing_exists(self):
        Project.objects.all().delete()
        Scan.objects.all().delete()
        trend = self.view._get_top_counts_trend()
        self.assertEqual(trend["projects"]["pct"], 0.0)
        self.assertEqual(trend["scans"]["pct"], 0.0)
