import json
import unittest
from collections import defaultdict
from pathlib import Path
from eval.datasets.curated import load_curated
from eval.matching import Case

DATA = Path(__file__).resolve().parents[1] / "data" / "curated"


def _manifest():
    return json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))


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

    def test_covers_at_least_three_languages(self):
        # W8.2 — the curated set must span >=3 languages (grown from python+js).
        langs = {c["language"] for c in _manifest()["cases"]}
        self.assertGreaterEqual(len(langs), 3, f"want >=3 languages, got {langs}")
        self.assertTrue({"go", "php", "ruby"} <= langs, f"new langs missing: {langs}")

    def test_every_language_has_a_real_and_safe_pair(self):
        labels = defaultdict(set)
        for c in _manifest()["cases"]:
            labels[c["language"]].add(c["label"])
        for lang, ls in labels.items():
            self.assertEqual(ls, {"real", "fake"}, f"{lang} lacks a real/safe pair: {ls}")


if __name__ == "__main__":
    unittest.main()
