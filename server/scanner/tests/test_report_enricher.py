from unittest import mock

from django.test import SimpleTestCase

from scanner.rag.lsast_types import DataflowContext, FindingReport
from scanner.rag import report_enricher
from scanner.rag.report_enricher import (
    build_report_prompt, generate_report, apply_report)


def _df() -> DataflowContext:
    return DataflowContext(source_line=1, source_code="req.body.q", sink_line=3,
                           sink_code="db.query('... '+q)", steps=[], sanitizers_observed=[])


class FindingReportFromJsonTests(SimpleTestCase):
    def test_full_object(self):
        r = FindingReport.from_json(
            '{"name":"SQLi in login","description":"raw concat","impact":"data theft","remediation":"use params"}')
        self.assertEqual(r.name, "SQLi in login")
        self.assertEqual(r.description, "raw concat")
        self.assertEqual(r.impact, "data theft")
        self.assertEqual(r.remediation, "use params")

    def test_alternate_keys(self):
        r = FindingReport.from_json('{"title":"X","mitigation":"patch it","risk":"RCE"}')
        self.assertEqual(r.name, "X")
        self.assertEqual(r.remediation, "patch it")
        self.assertEqual(r.impact, "RCE")
        self.assertEqual(r.description, "")

    def test_blank_fields_become_empty(self):
        r = FindingReport.from_json('{"name":"   ","description":""}')
        self.assertEqual((r.name, r.description, r.impact, r.remediation), ("", "", "", ""))

    def test_malformed_or_non_object_is_none(self):
        self.assertIsNone(FindingReport.from_json("not json"))
        self.assertIsNone(FindingReport.from_json("[1,2,3]"))


class BuildReportPromptTests(SimpleTestCase):
    def test_prompt_has_facts_and_json_contract(self):
        p = build_report_prompt(rule_name="node-mysql-sqli", cwe="CWE-89", language="javascript",
                                file_path="a.js", line=12, dataflow=_df(), code_excerpt="db.query(x)")
        self.assertIn("CWE-89", p)
        self.assertIn("node-mysql-sqli", p)
        self.assertIn("a.js:12", p)
        self.assertIn('"remediation"', p)
        self.assertIn("ONLY this JSON", p)


class GenerateReportTests(SimpleTestCase):
    @mock.patch.object(report_enricher, "get_ready_llm")
    def test_returns_report_and_requests_more_tokens(self, mock_llm):
        client = mock.Mock()
        client.invoke.return_value = {"result":
            '{"name":"SQL injection","description":"d","impact":"i","remediation":"r"}'}
        mock_llm.return_value = client
        r = generate_report(rule_name="sqli", cwe="CWE-89", language="python",
                            file_path="x.py", line=3, dataflow=_df(), code_excerpt="q")
        self.assertEqual(r.name, "SQL injection")
        # the reporting pass asks for more output than the default verdict cap
        self.assertIn("max_tokens", client.invoke.call_args.args[0])

    @mock.patch.object(report_enricher, "get_ready_llm", side_effect=RuntimeError("server down"))
    def test_fail_open_on_call_error(self, _llm):
        self.assertIsNone(generate_report(rule_name="r", cwe="", language="python",
                                          file_path="x.py", line=1, dataflow=_df(), code_excerpt="q"))

    @mock.patch.object(report_enricher, "get_ready_llm")
    def test_none_on_unparseable_output(self, mock_llm):
        client = mock.Mock(); client.invoke.return_value = {"result": "sorry, no json here"}
        mock_llm.return_value = client
        self.assertIsNone(generate_report(rule_name="r", cwe="", language="python",
                                          file_path="x.py", line=1, dataflow=_df(), code_excerpt="q"))

    @mock.patch.dict("os.environ", {"LSAST_ENRICH_FINDINGS": "0"})
    @mock.patch.object(report_enricher, "get_ready_llm")
    def test_disabled_via_env_skips_llm(self, mock_llm):
        self.assertIsNone(generate_report(rule_name="r", cwe="", language="python",
                                          file_path="x.py", line=1, dataflow=_df(), code_excerpt="q"))
        mock_llm.assert_not_called()


class ApplyReportTests(SimpleTestCase):
    def _base(self):
        return {"title": "node-mysql-sqli", "description": "rule msg",
                "security_risk": "rule msg", "mitigation": "", "cwe": "CWE-89", "severity": "high"}

    def test_overlays_present_fields_only(self):
        f = self._base()
        apply_report(f, FindingReport(name="SQL Injection in transfer",
                                      description="user input concatenated into query",
                                      impact="", remediation="use parameterized queries"))
        self.assertEqual(f["title"], "SQL Injection in transfer")
        self.assertEqual(f["description"], "user input concatenated into query")
        self.assertEqual(f["mitigation"], "use parameterized queries")
        self.assertEqual(f["security_risk"], "rule msg")   # blank impact -> kept deterministic value
        self.assertEqual(f["cwe"], "CWE-89")               # never touched
        self.assertEqual(f["severity"], "high")            # never touched

    def test_none_report_leaves_finding_unchanged(self):
        f = self._base()
        self.assertEqual(apply_report(f, None), self._base())
