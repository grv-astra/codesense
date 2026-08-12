from django.test import TestCase
from local.api_app.models.finding_models import FindingModel


class FindingModelTests(TestCase):
    def _finding(self, scan_id="scan1", **over):
        base = {"scan_id": scan_id, "created_by": "u1", "cwe": "CWE-89",
                "title": "SQLi", "severity": "high"}
        base.update(over)
        return base

    def test_insert_many_ignores_unknown_keys_and_serializes(self):
        out = FindingModel.insert_many([
            self._finding(lines=[1, 2], affected="foo()")  # unknown keys must be dropped
        ])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["cwe"], "CWE-89")
        self.assertEqual(out[0]["status"], "open")
        self.assertFalse(out[0]["approved"])
        self.assertNotIn("lines", out[0])

    def test_find_by_scan_pagination_and_excludes_deleted(self):
        FindingModel.insert_many([self._finding(), self._finding()])
        result = FindingModel.find_by_scan("scan1", page=1, limit=1)
        self.assertEqual(result["pagination"]["total"], 2)
        self.assertEqual(len(result["findings"]), 1)

    def test_soft_delete_and_toggle_approved(self):
        out = FindingModel.insert_many([self._finding()])
        fid = out[0]["id"]
        self.assertEqual(FindingModel.toggle_approved(fid), {"id": fid, "approved": True})
        self.assertEqual(FindingModel.soft_delete(fid), 1)
        self.assertNotIn(fid, [f["id"] for f in FindingModel.find_all_by_scan("scan1")])

    def test_persists_rule_id_confidence_and_verifier_reason(self):
        # W7: these three were previously dropped by the _FIELDS filter; they
        # must now round-trip through insert (write) and serialize (read).
        out = FindingModel.insert_many([self._finding(
            rule_id="py.audit.sqli.tainted-sql-string",
            confidence=0.92,
            verifier_reason="unsanitized concat reaches execute")])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["rule_id"], "py.audit.sqli.tainted-sql-string")
        self.assertEqual(out[0]["confidence"], 0.92)
        self.assertEqual(out[0]["verifier_reason"], "unsanitized concat reaches execute")
        # re-read from the DB to confirm the columns persisted, not just echoed
        again = FindingModel.find_by_id(out[0]["id"])
        self.assertEqual(again["rule_id"], "py.audit.sqli.tainted-sql-string")
        self.assertEqual(again["confidence"], 0.92)
        self.assertEqual(again["verifier_reason"], "unsanitized concat reaches execute")

    def test_persists_flow_diagram(self):
        # Flow-diagram widget data: a list of formatted "Source/Step/Sink" strings
        # built from the detector's dataflow trace. Must round-trip like rule_id etc.
        steps = ["Source (line 12): request.GET['q']",
                 "Sink (line 18): cursor.execute(query)"]
        out = FindingModel.insert_many([self._finding(flow_diagram=steps)])
        self.assertEqual(out[0]["flow_diagram"], steps)
        again = FindingModel.find_by_id(out[0]["id"])
        self.assertEqual(again["flow_diagram"], steps)

    def test_flow_diagram_defaults_to_empty_list(self):
        out = FindingModel.insert_many([self._finding()])
        self.assertEqual(out[0]["flow_diagram"], [])

    def test_persists_code_snip_start_line(self):
        out = FindingModel.insert_many([self._finding(code_snip_start_line=10)])
        self.assertEqual(out[0]["code_snip_start_line"], 10)
        again = FindingModel.find_by_id(out[0]["id"])
        self.assertEqual(again["code_snip_start_line"], 10)

    def test_code_snip_start_line_defaults_to_none(self):
        out = FindingModel.insert_many([self._finding()])
        self.assertIsNone(out[0]["code_snip_start_line"])

    def test_find_by_project_via_scan_ids(self):
        from local.api_app.models.scan_models import ScanModel
        s = ScanModel.create({"project_id": "projX", "scan_name": "S"})
        FindingModel.insert_many([self._finding(scan_id=s["id"])])
        rows = FindingModel.find_by_project("projX")
        self.assertEqual(len(rows), 1)

    def test_insert_many_persists_fingerprint(self):
        from datetime import datetime, timezone
        saved = FindingModel.insert_many([{
            "scan_id": "s1", "title": "t", "cwe": "CWE-89", "severity": "high",
            "status": "open", "created_at": datetime.now(timezone.utc),
            "fingerprint": "abc123",
        }])
        self.assertEqual(saved[0]["fingerprint"], "abc123")

    def test_insert_many_persists_first_seen_scan_id(self):
        from local.api_app.models.finding_models import FindingModel
        from datetime import datetime, timezone

        result = FindingModel.insert_many([{
            "scan_id": "scan1", "created_by": "u", "cwe": "CWE-89",
            "file_path": "a.py [1,2]", "created_at": datetime.now(timezone.utc),
            "first_seen_scan_id": "scan1",
        }])
        self.assertEqual(result[0]["first_seen_scan_id"], "scan1")

    def test_copy_forward_copies_matching_unchanged_findings_with_new_scan_id(self):
        from local.api_app.models.finding_models import FindingModel
        from local.api_app.models.orm import Finding
        from datetime import datetime, timezone

        Finding.objects.create(
            scan_id="baseline-scan", file_path="src/app.py [1,2]", cwe="CWE-89",
            created_at=datetime.now(timezone.utc), first_seen_scan_id="baseline-scan",
        )
        Finding.objects.create(
            scan_id="baseline-scan", file_path="src/other.py [5,6]", cwe="CWE-79",
            created_at=datetime.now(timezone.utc), first_seen_scan_id="baseline-scan",
        )

        count = FindingModel.copy_forward("baseline-scan", "new-scan", {"src/app.py"})

        self.assertEqual(count, 1)
        copied = Finding.objects.filter(scan_id="new-scan")
        self.assertEqual(copied.count(), 1)
        self.assertEqual(copied.first().file_path, "src/app.py [1,2]")
        self.assertEqual(copied.first().cwe, "CWE-89")
        self.assertNotEqual(copied.first().id, Finding.objects.get(scan_id="baseline-scan", cwe="CWE-89").id)

    def test_copy_forward_preserves_original_first_seen_scan_id(self):
        from local.api_app.models.finding_models import FindingModel
        from local.api_app.models.orm import Finding
        from datetime import datetime, timezone

        Finding.objects.create(
            scan_id="scan-2", file_path="src/app.py [1,2]", cwe="CWE-89",
            created_at=datetime.now(timezone.utc), first_seen_scan_id="scan-1",
        )

        FindingModel.copy_forward("scan-2", "scan-3", {"src/app.py"})

        copied = Finding.objects.get(scan_id="scan-3")
        self.assertEqual(copied.first_seen_scan_id, "scan-1")

    def test_copy_forward_falls_back_to_baseline_id_when_first_seen_missing(self):
        from local.api_app.models.finding_models import FindingModel
        from local.api_app.models.orm import Finding
        from datetime import datetime, timezone

        Finding.objects.create(
            scan_id="scan-old", file_path="src/app.py [1,2]", cwe="CWE-89",
            created_at=datetime.now(timezone.utc), first_seen_scan_id="",
        )

        FindingModel.copy_forward("scan-old", "scan-new", {"src/app.py"})

        copied = Finding.objects.get(scan_id="scan-new")
        self.assertEqual(copied.first_seen_scan_id, "scan-old")

    def test_copy_forward_skips_deleted_findings(self):
        from local.api_app.models.finding_models import FindingModel
        from local.api_app.models.orm import Finding
        from datetime import datetime, timezone

        Finding.objects.create(
            scan_id="scan-x", file_path="src/app.py [1,2]", cwe="CWE-89",
            created_at=datetime.now(timezone.utc), deleted=True,
        )

        count = FindingModel.copy_forward("scan-x", "scan-y", {"src/app.py"})
        self.assertEqual(count, 0)

    def test_copy_forward_returns_zero_for_empty_unchanged_set(self):
        from local.api_app.models.finding_models import FindingModel
        self.assertEqual(FindingModel.copy_forward("any-scan", "other-scan", set()), 0)
