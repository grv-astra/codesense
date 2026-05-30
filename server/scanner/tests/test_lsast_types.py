from django.test import SimpleTestCase
from scanner.rag.lsast_types import SemgrepFinding, DataflowContext, VerifierVerdict


class LsastTypesTests(SimpleTestCase):
    def test_semgrep_finding_minimal(self):
        f = SemgrepFinding(
            rule_id="python.lang.security.audit.sql-injection",
            cwe="CWE-89",
            severity="high",
            message="Possible SQL injection",
            file_path="app/views.py",
            start_line=12,
            end_line=18,
            code_excerpt="cursor.execute(q)",
            taint_trace=[],
            sanitizers_observed=[],
        )
        self.assertEqual(f.cwe, "CWE-89")
        self.assertEqual(f.severity, "high")

    def test_dataflow_context_renders_for_prompt(self):
        ctx = DataflowContext(
            source_line=12, source_code="request.GET['q']",
            sink_line=18, sink_code="cursor.execute(q)",
            steps=[(14, "query = '...' + q + '...'")],
            sanitizers_observed=[],
        )
        rendered = ctx.render_for_prompt()
        self.assertIn("Source", rendered)
        self.assertIn("line 12", rendered)
        self.assertIn("Sink", rendered)
        self.assertIn("line 18", rendered)
        self.assertIn("none", rendered.lower())   # no sanitizers

    def test_verifier_verdict_parses_valid_json(self):
        v = VerifierVerdict.from_json('{"verdict":"FP","reason":"parameterized query","confidence":0.9}')
        self.assertEqual(v.verdict, "FP")
        self.assertAlmostEqual(v.confidence, 0.9)

    def test_verifier_verdict_invalid_json_returns_none(self):
        self.assertIsNone(VerifierVerdict.from_json("not json"))
        self.assertIsNone(VerifierVerdict.from_json('{"verdict":"MAYBE"}'))   # invalid verdict
