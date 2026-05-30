import unittest
from eval.matching import cwe_number, same_cwe_family, finding_hits_case, Case


class MatchingTests(unittest.TestCase):
    def test_cwe_number(self):
        self.assertEqual(cwe_number("CWE-89"), 89)
        self.assertEqual(cwe_number("CWE-89: SQLi"), 89)
        self.assertIsNone(cwe_number("CWE-Unknown"))
        self.assertIsNone(cwe_number(""))

    def test_same_cwe_family_exact(self):
        self.assertTrue(same_cwe_family("CWE-89", "CWE-89"))

    def test_same_cwe_family_alias(self):
        self.assertTrue(same_cwe_family("CWE-943", "CWE-89"))

    def test_different_family(self):
        self.assertFalse(same_cwe_family("CWE-79", "CWE-89"))

    def test_finding_hits_case_same_file_and_family(self):
        case = Case(case_id="t1", source_path="app/views.py", is_real=True, cwe="CWE-89")
        finding = {"file_path": "app/views.py [12,18]", "cwe": "CWE-89"}
        self.assertTrue(finding_hits_case(finding, case))

    def test_finding_does_not_hit_wrong_file(self):
        case = Case(case_id="t1", source_path="app/views.py", is_real=True, cwe="CWE-89")
        finding = {"file_path": "other/x.py [1,2]", "cwe": "CWE-89"}
        self.assertFalse(finding_hits_case(finding, case))

    def test_finding_does_not_hit_wrong_family(self):
        case = Case(case_id="t1", source_path="app/views.py", is_real=True, cwe="CWE-89")
        finding = {"file_path": "app/views.py [1,2]", "cwe": "CWE-79"}
        self.assertFalse(finding_hits_case(finding, case))


if __name__ == "__main__":
    unittest.main()
