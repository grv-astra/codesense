from django.test import SimpleTestCase

from scanner.rag.fusion import FusionOutcome, fuse
from scanner.rag.lsast_types import VerifierVerdict


def _finding(severity: str) -> dict:
    return {"severity": severity, "title": "x", "status": "open"}


class FuseTests(SimpleTestCase):
    def test_tp_verdict_shows_with_verdict_confidence(self):
        outcome = fuse(_finding("high"), VerifierVerdict("TP", "real", 0.7))
        self.assertEqual(outcome.action, "show")
        self.assertAlmostEqual(outcome.finding["confidence"], 0.7)

    def test_fp_on_low_severity_suppresses(self):
        outcome = fuse(_finding("low"), VerifierVerdict("FP", "safe", 0.9))
        self.assertEqual(outcome.action, "suppress")
        self.assertEqual(outcome.finding["status"], "filtered")

    def test_fp_on_medium_severity_suppresses(self):
        outcome = fuse(_finding("medium"), VerifierVerdict("FP", "safe", 0.9))
        self.assertEqual(outcome.action, "suppress")

    def test_fp_on_high_severity_kept_for_review(self):
        outcome = fuse(_finding("high"), VerifierVerdict("FP", "looks safe but…", 0.8))
        self.assertEqual(outcome.action, "needs_review")
        self.assertEqual(outcome.finding["status"], "needs_review")
        self.assertIn("[verifier:FP]", outcome.finding["title"])

    def test_fp_on_critical_severity_kept_for_review(self):
        outcome = fuse(_finding("critical"), VerifierVerdict("FP", "looks safe", 0.6))
        self.assertEqual(outcome.action, "needs_review")

    def test_failopen_low_confidence_tp_stays_low(self):
        # fail-open verdict is a low-confidence TP; its confidence must NOT be inflated
        outcome = fuse(_finding("medium"),
                       VerifierVerdict("TP", "verifier unparseable; preserved for review", 0.3))
        self.assertEqual(outcome.action, "show")
        self.assertAlmostEqual(outcome.finding["confidence"], 0.3)

    def test_verifier_reason_attached(self):
        outcome = fuse(_finding("low"), VerifierVerdict("FP", "ORM parameterizes", 0.9))
        self.assertEqual(outcome.finding["verifier_reason"], "ORM parameterizes")

    def test_unknown_severity_defaults_to_medium_band(self):
        # an unrecognized severity is treated as medium → FP suppresses (not needs_review)
        outcome = fuse(_finding("weird"), VerifierVerdict("FP", "safe", 0.9))
        self.assertEqual(outcome.action, "suppress")
