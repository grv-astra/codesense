import unittest
from pathlib import Path
from eval.datasets.curated import load_curated
from eval.matching import Case

DATA = Path(__file__).resolve().parents[1] / "data" / "curated"


class CuratedTests(unittest.TestCase):
    def test_loads_cases_as_Case_objects(self):
        cases = load_curated(DATA)
        self.assertGreaterEqual(len(cases), 4)
        self.assertTrue(all(isinstance(c, Case) for c in cases))

    def test_real_and_fake_labels_map_to_is_real(self):
        by_id = {c.case_id: c for c in load_curated(DATA)}
        self.assertTrue(by_id["py_sqli_unsafe"].is_real)
        self.assertFalse(by_id["py_sqli_safe"].is_real)

    def test_source_path_points_at_real_file(self):
        for c in load_curated(DATA):
            self.assertTrue(Path(c.source_path).exists(), c.source_path)


if __name__ == "__main__":
    unittest.main()
