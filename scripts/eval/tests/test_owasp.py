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

    def test_skips_blank_short_and_non_boolean_rows(self):
        import io, tempfile, os
        content = (
            "# header comment,category,real,cwe\n"
            "testname,category,real vulnerability,cwe\n"   # bare header (non-boolean col2) -> skip
            "\n"                                             # blank -> skip
            "ShortRow,sqli\n"                                # short -> skip
            "BenchmarkTest09999,sqli,true,89\n"              # valid
        )
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write(content); path = fh.name
        try:
            cases = parse_expectedresults(path, src_root="/s")
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0].case_id, "BenchmarkTest09999")
        finally:
            os.unlink(path)

    def test_source_path_includes_src_root(self):
        c = parse_expectedresults(FIXT, src_root="/benchmark/src")[0]
        self.assertIn("/benchmark/src", c.source_path)


if __name__ == "__main__":
    unittest.main()
