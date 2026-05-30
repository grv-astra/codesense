import unittest
from eval.metrics import Counts, compute, meets_thresholds


class MetricsTests(unittest.TestCase):
    def test_precision_recall_f1(self):
        m = compute(Counts(tp=8, fp=2, fn=4, tn=6))
        self.assertAlmostEqual(m["precision"], 0.8)
        self.assertAlmostEqual(m["recall"], 8 / 12)
        self.assertAlmostEqual(m["f1"], 2 * 0.8 * (8 / 12) / (0.8 + 8 / 12))
        self.assertAlmostEqual(m["fp_rate"], 2 / 8)

    def test_zero_division_safe(self):
        m = compute(Counts(tp=0, fp=0, fn=0, tn=0))
        self.assertEqual(m["precision"], 0.0)
        self.assertEqual(m["recall"], 0.0)
        self.assertEqual(m["f1"], 0.0)
        self.assertEqual(m["fp_rate"], 0.0)

    def test_meets_thresholds(self):
        good = {"f1": 0.71, "recall": 0.61, "fp_rate": 0.24}
        bad = {"f1": 0.69, "recall": 0.61, "fp_rate": 0.24}
        self.assertTrue(meets_thresholds(good)[0])
        ok, failures = meets_thresholds(bad)
        self.assertFalse(ok)
        self.assertIn("f1", " ".join(failures))

    def test_recall_below_threshold_fails(self):
        ok, failures = meets_thresholds({"f1": 0.8, "recall": 0.59, "fp_rate": 0.2})
        self.assertFalse(ok)
        self.assertIn("recall", " ".join(failures))

    def test_fp_rate_above_threshold_fails(self):
        ok, failures = meets_thresholds({"f1": 0.8, "recall": 0.7, "fp_rate": 0.26})
        self.assertFalse(ok)
        self.assertIn("fp_rate", " ".join(failures))

    def test_boundary_values_pass(self):
        # exactly at thresholds: f1=0.70, recall=0.60, fp_rate=0.25 all pass
        ok, failures = meets_thresholds({"f1": 0.70, "recall": 0.60, "fp_rate": 0.25})
        self.assertTrue(ok, failures)


if __name__ == "__main__":
    unittest.main()
