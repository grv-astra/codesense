import unittest

from eval.scorecard import render_scorecard


class ScorecardRenderTests(unittest.TestCase):
    def test_render_scorecard_has_all_axes(self):
        md = render_scorecard({
            "detector_f1": 1.0, "verifier_fp_suppression": 0.0,
            "enrichment_parse_rate": 0.34, "scan_wall_s_p50": 540.0,
            "build_signed_ok": False, "app_size_gb": 5.7,
        })
        for label in ("Detector F1", "Verifier FP-suppression", "Enrichment parse-rate",
                      "Scan wall-time", "Signed build", "App size"):
            self.assertIn(label, md)
        self.assertIn("0.34", md)

    def test_missing_keys_render_as_na(self):
        md = render_scorecard({"detector_f1": 1.0})
        self.assertIn("N/A", md)
        self.assertIn("1.000", md)

    def test_bool_renders_plainly(self):
        self.assertIn("False", render_scorecard({"build_signed_ok": False}))
        self.assertIn("True", render_scorecard({"build_signed_ok": True}))
