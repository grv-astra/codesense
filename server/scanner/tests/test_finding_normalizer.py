import uuid

from django.test import SimpleTestCase

from scanner.rag.finding_normalizer import normalize, build_dataflow_context
from scanner.rag.lsast_types import SemgrepFinding


def _sample_finding() -> SemgrepFinding:
    return SemgrepFinding(
        rule_id="python.lang.security.audit.sql-injection.tainted-sql-string",
        cwe="CWE-89",
        severity="high",
        message="Possible SQL injection",
        file_path="app/views.py",
        start_line=12,
        end_line=18,
        code_excerpt="q = request.GET['q']\nquery = '...' + q\ncursor.execute(query)",
        taint_trace=[
            (12, "request.GET['q']"),
            (14, "query = '...' + q + '...'"),
            (18, "cursor.execute(query)"),
        ],
        sanitizers_observed=[],
    )


class BuildDataflowContextTests(SimpleTestCase):
    def test_picks_first_step_as_source_last_as_sink(self):
        ctx = build_dataflow_context(_sample_finding())
        self.assertEqual(ctx.source_line, 12)
        self.assertEqual(ctx.source_code, "request.GET['q']")
        self.assertEqual(ctx.sink_line, 18)
        self.assertIn("cursor.execute", ctx.sink_code)
        self.assertEqual(len(ctx.steps), 1)
        self.assertEqual(ctx.steps[0][0], 14)

    def test_no_trace_falls_back_to_finding_lines(self):
        f = _sample_finding()
        f.taint_trace = []
        ctx = build_dataflow_context(f)
        self.assertEqual(ctx.source_line, 12)
        self.assertEqual(ctx.sink_line, 18)
        self.assertEqual(ctx.steps, [])

    def test_empty_excerpt_and_no_trace_does_not_crash(self):
        f = _sample_finding()
        f.taint_trace = []
        f.code_excerpt = ""
        ctx = build_dataflow_context(f)          # must not raise IndexError
        self.assertEqual(ctx.source_code, "")
        self.assertEqual(ctx.sink_code, "")

    def test_sanitizers_observed_round_trip(self):
        f = _sample_finding()
        f.sanitizers_observed = ["html.escape"]
        ctx = build_dataflow_context(f)
        self.assertEqual(ctx.sanitizers_observed, ["html.escape"])


class NormalizeTests(SimpleTestCase):
    def test_produces_finding_dict_matching_existing_shape(self):
        scan_id = uuid.uuid4().hex
        finding_dict, ctx = normalize(_sample_finding(),
                                     scan_id=scan_id, triggered_by="user-123")
        self.assertEqual(finding_dict["scan_id"], scan_id)
        self.assertEqual(finding_dict["cwe"], "CWE-89")
        self.assertEqual(finding_dict["severity"], "high")
        self.assertEqual(finding_dict["status"], "open")
        self.assertFalse(finding_dict["deleted"])
        self.assertFalse(finding_dict["approved"])
        self.assertIn("app/views.py", finding_dict["file_path"])
        self.assertIn("[12,18]", finding_dict["file_path"])
        self.assertEqual(finding_dict["created_by"], "user-123")
        self.assertEqual(finding_dict["lines"], [12, 18])
        # title is the Semgrep rule NAME (last segment of the check_id), not the prose message
        self.assertEqual(finding_dict["title"], "tainted-sql-string")
        # the prose message is preserved as the description
        self.assertEqual(finding_dict["description"], "Possible SQL injection")
        # security_risk is a distinct deterministic impact statement (NOT the message)
        self.assertNotEqual(finding_dict["security_risk"], finding_dict["description"])
        self.assertIn("CWE-89", finding_dict["security_risk"])
        self.assertIn("high-severity", finding_dict["security_risk"])
        self.assertTrue(finding_dict["code"].startswith("f-"))
        self.assertEqual(finding_dict["reference"],
                         "https://cwe.mitre.org/data/definitions/89.html")
        self.assertEqual(ctx.sink_line, 18)

    def test_unknown_cwe_yields_NA_reference(self):
        f = _sample_finding()
        f.cwe = ""
        finding_dict, _ = normalize(f, scan_id="s", triggered_by="u")
        self.assertEqual(finding_dict["cwe"], "CWE-Unknown")
        self.assertEqual(finding_dict["reference"], "NA")

    def test_title_uses_rule_name_last_segment(self):
        # Semgrep namespaces a rule by its path and often duplicates the final
        # segment; the displayed NAME is that last segment of the check_id.
        f = _sample_finding()
        f.rule_id = ("javascript.lang.security.audit.sqli."
                     "node-mysql-sqli.node-mysql-sqli")
        f.message = "Avoiding SQL string concatenation: untrusted input ..."
        finding_dict, _ = normalize(f, scan_id="s", triggered_by="u")
        self.assertEqual(finding_dict["title"], "node-mysql-sqli")
        self.assertIn("Avoiding SQL", finding_dict["description"])

    def test_title_falls_back_to_message_then_default(self):
        f = _sample_finding()
        f.rule_id = ""
        f.message = "Some issue"
        self.assertEqual(normalize(f, "s", "u")[0]["title"], "Some issue")
        f.message = ""
        self.assertEqual(normalize(f, "s", "u")[0]["title"], "Vulnerability")
