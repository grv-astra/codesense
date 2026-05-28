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

    def test_find_by_project_via_scan_ids(self):
        from local.api_app.models.scan_models import ScanModel
        s = ScanModel.create({"project_id": "projX", "scan_name": "S"})
        FindingModel.insert_many([self._finding(scan_id=s["id"])])
        rows = FindingModel.find_by_project("projX")
        self.assertEqual(len(rows), 1)
