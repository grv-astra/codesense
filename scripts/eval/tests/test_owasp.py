import unittest
from pathlib import Path
from eval.datasets.owasp_benchmark import parse_expectedresults
from eval.matching import Case

FIXT = Path(__file__).resolve().parent / "fixtures" / "owasp_expectedresults.csv"


class OwaspTests(unittest.TestCase):
    def test_parses_rows_to_cases(self):
        cases = parse_expectedresults(FIXT, src_root="/benchmark/src")
        self.assertEqual(len(cases), 3)
        self.assertTrue(all(isinstance(c, Case) for c in cases))

    def test_real_flag_and_cwe(self):
        by_id = {c.case_id: c for c in parse_expectedresults(FIXT, src_root="/benchmark/src")}
        self.assertTrue(by_id["BenchmarkTest00001"].is_real)
        self.assertEqual(by_id["BenchmarkTest00001"].cwe, "CWE-89")
        self.assertFalse(by_id["BenchmarkTest00002"].is_real)

    def test_source_path_built_from_root(self):
        c = parse_expectedresults(FIXT, src_root="/benchmark/src")[0]
        self.assertTrue(c.source_path.endswith("BenchmarkTest00001.java"))


if __name__ == "__main__":
    unittest.main()
