from pathlib import Path
from django.test import SimpleTestCase


class EvalNotBundledTests(SimpleTestCase):
    def test_codesense_spec_does_not_reference_eval(self):
        spec = (Path(__file__).resolve().parents[2] / "codesense.spec").read_text(encoding="utf-8")
        self.assertNotIn("scripts/eval", spec)
        self.assertNotIn("scripts.eval", spec)
