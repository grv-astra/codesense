import uuid

from django.test import SimpleTestCase

from scanner.rag.finding_normalizer import (
    normalize, build_dataflow_context, dedupe_findings, derive_cvss,
    _cvss_base_score, _parse_vector)
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

    def test_produces_flow_diagram_strings_source_step_sink(self):
        finding_dict, _ = normalize(_sample_finding(), scan_id="s", triggered_by="u")
        steps = finding_dict["flow_diagram"]
        self.assertEqual(len(steps), 3)
        self.assertIn("Source", steps[0])
        self.assertIn("line 12", steps[0])
        self.assertIn("request.GET['q']", steps[0])
        self.assertIn("Step", steps[1])
        self.assertIn("line 14", steps[1])
        self.assertIn("Sink", steps[2])
        self.assertIn("line 18", steps[2])
        self.assertIn("cursor.execute", steps[2])

    def test_flow_diagram_empty_when_no_trace_and_no_excerpt(self):
        f = _sample_finding()
        f.taint_trace = []
        f.code_excerpt = ""
        finding_dict, _ = normalize(f, scan_id="s", triggered_by="u")
        self.assertEqual(finding_dict["flow_diagram"], [])

    def test_code_snip_uses_context_when_available(self):
        f = _sample_finding()
        f.context_code = "before\nq = request.GET['q']\nquery = '...' + q\ncursor.execute(query)\nafter"
        f.context_start_line = 10
        finding_dict, _ = normalize(f, scan_id="s", triggered_by="u")
        self.assertEqual(finding_dict["code_snip"], f.context_code)
        self.assertEqual(finding_dict["code_snip_start_line"], 10)

    def test_code_snip_falls_back_to_exact_match_excerpt(self):
        f = _sample_finding()   # context_code/_start_line default "" / 0
        finding_dict, _ = normalize(f, scan_id="s", triggered_by="u")
        self.assertEqual(finding_dict["code_snip"], f.code_excerpt)
        self.assertEqual(finding_dict["code_snip_start_line"], f.start_line)

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


class NormalizeVerdictFieldsTests(SimpleTestCase):
    """W7 — the verifier's metadata + the Semgrep rule_id must survive into the
    finding dict (and the persistence field filter) so the API can expose them."""

    def test_normalize_sets_rule_id_and_verdict_defaults(self):
        f = _sample_finding()
        fd, _ = normalize(f, "s", "u")
        # Cleaned the same way as title -- last dotted segment of the raw
        # check_id, not the full namespace-prefixed path.
        self.assertEqual(fd["rule_id"], "tainted-sql-string")
        # defaults before fuse runs; fuse overwrites these for findings it judges
        self.assertIsNone(fd["confidence"])
        self.assertEqual(fd["verifier_reason"], "")

    def test_normalize_rule_id_falls_back_to_raw_when_unparseable(self):
        f = _sample_finding()
        f.rule_id = ""
        fd, _ = normalize(f, "s", "u")
        self.assertEqual(fd["rule_id"], "")

    def test_new_fields_survive_the_persistence_filter(self):
        from local.api_app.models.finding_models import _FIELDS
        for k in ("rule_id", "confidence", "verifier_reason"):
            self.assertIn(k, _FIELDS, f"{k} must be a persisted field")


class DeriveCvssTests(SimpleTestCase):
    """CVSS is derived from the CWE's characteristic vector, not a flat
    per-severity constant (which made 79/86 DVWA findings identically 8.8)."""

    def test_class_specific_not_flat_by_severity(self):
        # SQLi and XSS are both "high" but must NOT share a CVSS score.
        sqli_score, sqli_vec = derive_cvss("CWE-89", "high")
        xss_score, xss_vec = derive_cvss("CWE-79", "high")
        self.assertNotEqual(sqli_score, xss_score)
        self.assertEqual(sqli_score, "9.8")     # network RCE-class impact
        self.assertEqual(xss_score, "6.1")      # scope-changed, requires UI
        self.assertTrue(sqli_vec.startswith("CVSS:3.1/"))

    def test_command_injection_distinct_from_weak_crypto(self):
        cmd, _ = derive_cvss("CWE-78", "high")
        crypto, _ = derive_cvss("CWE-327", "high")
        self.assertEqual(cmd, "9.8")
        self.assertEqual(crypto, "5.9")

    def test_unknown_cwe_falls_back_to_severity(self):
        self.assertEqual(derive_cvss("CWE-Unknown", "low")[0], "3.1")
        self.assertEqual(derive_cvss("", "critical")[0], "9.8")

    def test_published_score_matches_its_own_vector(self):
        # Guard against hand-typed score/vector mismatches: the published score is
        # the CVSS 3.1 base score of the published vector.
        for cwe in ("CWE-89", "CWE-79", "CWE-22", "CWE-78", "CWE-352",
                    "CWE-918", "CWE-327", "CWE-330"):
            score, vec = derive_cvss(cwe, "high")
            recomputed = f"{_cvss_base_score(_parse_vector(vec)):.1f}"
            self.assertEqual(score, recomputed, f"{cwe}: {vec}")

    def test_normalize_uses_class_specific_cvss(self):
        f = _sample_finding()           # CWE-89, high
        d, _ = normalize(f, "s", "u")
        self.assertEqual(d["cvss_score"], "9.8")
        f.cwe = "CWE-79"
        d, _ = normalize(f, "s", "u")
        self.assertEqual(d["cvss_score"], "6.1")


class DedupeFindingsTests(SimpleTestCase):
    def _f(self, rule_id, line=12, cwe="CWE-89", trace=None, excerpt="x"):
        return SemgrepFinding(
            rule_id=rule_id, cwe=cwe, severity="high", message="m",
            file_path="app/views.py", start_line=line, end_line=line + 1,
            code_excerpt=excerpt, taint_trace=trace or [], sanitizers_observed=[])

    def test_same_location_same_cwe_two_rules_collapses_to_one(self):
        findings = [self._f("rule-a"), self._f("rule-b")]
        out = dedupe_findings(findings)
        self.assertEqual(len(out), 1)

    def test_keeps_the_more_informative_finding(self):
        sparse = self._f("rule-a", trace=[], excerpt="x")
        rich = self._f("rule-b", trace=[(12, "src"), (13, "sink")], excerpt="much longer excerpt")
        out = dedupe_findings([sparse, rich])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].rule_id, "rule-b")

    def test_distinct_cwe_at_same_line_is_preserved(self):
        out = dedupe_findings([self._f("rule-a", cwe="CWE-89"),
                               self._f("rule-b", cwe="CWE-79")])
        self.assertEqual(len(out), 2)

    def test_distinct_locations_preserved(self):
        out = dedupe_findings([self._f("r", line=12), self._f("r", line=40)])
        self.assertEqual(len(out), 2)

    def test_order_stable(self):
        out = dedupe_findings([self._f("r", line=5), self._f("r", line=1),
                               self._f("r", line=5)])
        self.assertEqual([f.start_line for f in out], [5, 1])
