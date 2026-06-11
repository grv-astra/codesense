from unittest import mock

from django.test import SimpleTestCase

from scanner.rag.lsast_scanner import lsast_scan_folder
from scanner.rag.lsast_types import FindingReport, SemgrepFinding, VerifierVerdict


def _sqli_finding() -> SemgrepFinding:
    return SemgrepFinding(
        rule_id="python.lang.security.audit.sql-injection.tainted-sql-string",
        cwe="CWE-89", severity="high",
        message="Possible SQL injection",
        file_path="app/views.py", start_line=12, end_line=18,
        code_excerpt="cursor.execute(query)",
        taint_trace=[(12, "request.GET['q']"), (18, "cursor.execute(query)")],
        sanitizers_observed=[],
    )


def _safe_orm_finding() -> SemgrepFinding:
    return SemgrepFinding(
        rule_id="python.lang.security.audit.sql-injection.tainted-sql-string",
        cwe="CWE-89", severity="medium",
        message="Possible SQL injection",
        file_path="app/views.py", start_line=30, end_line=32,
        code_excerpt="User.objects.filter(name=request.GET['q'])",
        taint_trace=[(30, "request.GET['q']"), (32, "User.objects.filter(name=q)")],
        sanitizers_observed=[],
    )


class LsastScanFolderTests(SimpleTestCase):
    def setUp(self):
        # Keep the report-enrichment LLM pass out of these pipeline tests by
        # default (hermetic); a dedicated test below exercises the wiring.
        p = mock.patch("scanner.rag.lsast_scanner.generate_report", return_value=None)
        p.start(); self.addCleanup(p.stop)
        # The orchestrator now probes LLM availability and publishes progress
        # incrementally; keep both out of these hermetic (DB-less) unit tests.
        h = mock.patch("scanner.rag.lsast_scanner.llm_health", return_value=(True, "ok"))
        h.start(); self.addCleanup(h.stop)
        up = mock.patch("scanner.rag.lsast_scanner.update_progress")
        up.start(); self.addCleanup(up.stop)

    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.verify")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep")
    def test_pipeline_keeps_tp_and_suppresses_medium_fp(self, mock_run, mock_verify, mock_save):
        mock_run.return_value = [_sqli_finding(), _safe_orm_finding()]
        mock_verify.side_effect = [
            VerifierVerdict("TP", "unsanitized concat", 0.9),
            VerifierVerdict("FP", "Django ORM parameterizes", 0.95),
        ]
        visible, filtered = lsast_scan_folder(
            folder_path="/tmp/code", scan_id="s1", triggered_by="user-1")
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["severity"], "high")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["status"], "filtered")
        mock_save.assert_called_once()
        saved_arg = mock_save.call_args.args[0]
        self.assertEqual(len(saved_arg), 1)
        self.assertEqual(saved_arg[0]["cwe"], "CWE-89")

    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.verify")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep")
    def test_high_severity_fp_promoted_to_needs_review(self, mock_run, mock_verify, mock_save):
        mock_run.return_value = [_sqli_finding()]            # severity "high"
        mock_verify.return_value = VerifierVerdict("FP", "looks safe", 0.7)
        visible, filtered = lsast_scan_folder(
            folder_path="/tmp/code", scan_id="s1", triggered_by="user-1")
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["status"], "needs_review")
        self.assertEqual(filtered, [])
        mock_save.assert_called_once()

    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep", return_value=[])
    def test_no_findings_short_circuits(self, _run, mock_save):
        visible, filtered = lsast_scan_folder("/tmp/code", "s1", "user-1")
        self.assertEqual(visible, [])
        self.assertEqual(filtered, [])
        mock_save.assert_not_called()

    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.verify")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep")
    def test_language_inferred_from_path_passed_to_verifier(self, mock_run, mock_verify, mock_save):
        mock_run.return_value = [_sqli_finding()]            # path app/views.py → python
        mock_verify.return_value = VerifierVerdict("TP", "x", 0.8)
        lsast_scan_folder("/tmp/code", "s1", "user-1")
        self.assertEqual(mock_verify.call_args.kwargs["language"], "python")

    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.verify")
    @mock.patch("scanner.rag.lsast_scanner.normalize")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep")
    def test_one_bad_finding_does_not_abort_the_batch(self, mock_run, mock_normalize, mock_verify, mock_save):
        from scanner.rag.lsast_types import DataflowContext
        mock_run.return_value = [_sqli_finding(), _safe_orm_finding()]
        # First finding blows up in normalize; second normalizes fine.
        good_dict = {"severity": "high", "title": "ok", "status": "open", "cwe": "CWE-89"}
        good_ctx = DataflowContext(source_line=1, source_code="x", sink_line=2, sink_code="y")
        mock_normalize.side_effect = [RuntimeError("boom"), (good_dict, good_ctx)]
        mock_verify.return_value = VerifierVerdict("TP", "real", 0.9)
        visible, filtered = lsast_scan_folder("/tmp/code", "s1", "user-1")
        self.assertEqual(len(visible), 1)         # the good one survived
        self.assertEqual(len(filtered), 0)
        mock_save.assert_called_once()

    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.verify", return_value=VerifierVerdict("TP", "x", 0.9))
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep")
    @mock.patch("scanner.rag.lsast_scanner.generate_report",
                return_value=FindingReport("SQLi in transfer", "user input concatenated",
                                           "attacker reads the DB", "use parameterized queries"))
    def test_visible_finding_enriched_with_llm_report(self, _gen, mock_run, _verify, _save):
        mock_run.return_value = [_sqli_finding()]
        visible, _ = lsast_scan_folder("/tmp/code", "s1", "u1")
        f = visible[0]
        self.assertEqual(f["title"], "SQLi in transfer")              # LLM name
        self.assertEqual(f["description"], "user input concatenated")  # LLM description
        self.assertEqual(f["security_risk"], "attacker reads the DB")  # LLM impact
        self.assertEqual(f["mitigation"], "use parameterized queries") # LLM remediation
        self.assertEqual(f["cwe"], "CWE-89")                           # deterministic, untouched
        self.assertEqual(f["severity"], "high")                        # deterministic, untouched


    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.verify")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep")
    def test_llm_unavailable_keeps_findings_and_skips_verify(self, mock_run, mock_verify, mock_save):
        """When the LLM can't do inference (e.g. bad API key), the scan still
        returns the deterministic findings and does NOT call the AI verifier."""
        mock_run.return_value = [_sqli_finding()]
        with mock.patch("scanner.rag.lsast_scanner.llm_health",
                        return_value=(False, "auth: invalid key")):
            visible, filtered = lsast_scan_folder("/tmp/code", "s1", "u1")
        self.assertEqual(len(visible), 1)        # deterministic finding preserved
        self.assertEqual(filtered, [])
        mock_verify.assert_not_called()          # AI verify skipped when LLM is down
        mock_save.assert_called_once()           # still persisted (incrementally)


class LanguageRoutingTests(SimpleTestCase):
    def setUp(self):
        p = mock.patch("scanner.rag.lsast_scanner.generate_report", return_value=None)
        p.start(); self.addCleanup(p.stop)
        h = mock.patch("scanner.rag.lsast_scanner.llm_health", return_value=(True, "ok"))
        h.start(); self.addCleanup(h.stop)
        up = mock.patch("scanner.rag.lsast_scanner.update_progress")
        up.start(); self.addCleanup(up.stop)

    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.verify")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep")
    def test_verifier_gets_registry_language(self, mock_run, mock_verify, mock_save):
        from scanner.rag.lsast_types import SemgrepFinding, VerifierVerdict
        f = SemgrepFinding(rule_id="r", cwe="CWE-89", severity="high", message="m",
                           file_path="src/Main.kt", start_line=1, end_line=2,
                           code_excerpt="x", taint_trace=[], sanitizers_observed=[])
        mock_run.return_value = [f]
        mock_verify.return_value = VerifierVerdict("TP", "x", 0.9)
        lsast_scan_folder("/tmp/code", "s1", "u1")
        self.assertEqual(mock_verify.call_args.kwargs["language"], "kotlin")
