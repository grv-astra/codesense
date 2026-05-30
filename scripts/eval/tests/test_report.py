import unittest
from eval.report import render_markdown


class ReportTests(unittest.TestCase):
    def test_markdown_contains_metrics_and_verdict(self):
        md = render_markdown(
            title="Baseline",
            detector={"precision": 0.5, "recall": 0.6, "f1": 0.55, "fp_rate": 0.2,
                      "tp": 6, "fp": 6, "fn": 4, "tn": 24},
            verifier={"precision": 0.9, "recall": 0.8, "f1": 0.85, "fp_rate": 0.1,
                      "tp": 8, "fp": 1, "fn": 2, "tn": 9},
            per_language={"python": {"recall": 0.7}, "java": {"recall": 0.4}},
            passed=False, failures=["f1 0.55 < 0.7"],
        )
        self.assertIn("Baseline", md)
        self.assertIn("Detector", md)
        self.assertIn("Verifier", md)
        self.assertIn("python", md)
        self.assertIn("FAIL", md)
        self.assertIn("f1 0.55 < 0.7", md)

    def test_pass_verdict_shown(self):
        md = render_markdown(title="t", detector={}, verifier={}, per_language={},
                             passed=True, failures=[])
        self.assertIn("PASS", md)


if __name__ == "__main__":
    unittest.main()
