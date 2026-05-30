from unittest import mock

from django.test import SimpleTestCase

from scanner.rag.lsast_scanner import lsast_scan_folder
from scanner.rag.lsast_types import SemgrepFinding, VerifierVerdict


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
