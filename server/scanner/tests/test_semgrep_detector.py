import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from scanner.rag.semgrep_detector import run_semgrep, parse_semgrep_json
from scanner.rag.lsast_types import SemgrepFinding


FIXTURE = Path(__file__).parent / "fixtures" / "semgrep" / "sample_sqli.json"


class ParseSemgrepJsonTests(SimpleTestCase):
    def test_parses_one_finding(self):
        raw = FIXTURE.read_text()
        findings = parse_semgrep_json(raw)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertIsInstance(f, SemgrepFinding)
        self.assertEqual(f.rule_id, "python.lang.security.audit.sql-injection.tainted-sql-string")
        self.assertEqual(f.cwe, "CWE-89")
        self.assertEqual(f.severity, "high")          # ERROR -> high
        self.assertEqual(f.file_path, "app/views.py")
        self.assertEqual(f.start_line, 12)
        self.assertEqual(f.end_line, 18)
        self.assertIn("cursor.execute", f.code_excerpt)
        self.assertEqual(len(f.taint_trace), 3)        # source + 1 intermediate + sink
        self.assertEqual(f.taint_trace[0][0], 12)
        self.assertEqual(f.taint_trace[-1][0], 18)

    def test_empty_results_returns_empty_list(self):
        self.assertEqual(parse_semgrep_json('{"version":"1","results":[],"errors":[]}'), [])

    def test_malformed_json_returns_empty_list(self):
        self.assertEqual(parse_semgrep_json("not json"), [])
        self.assertEqual(parse_semgrep_json(""), [])


class RunSemgrepTests(SimpleTestCase):
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_rules_dir", return_value="/rules")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_bin", return_value="/bin/semgrep")
    @mock.patch("scanner.rag.semgrep_detector.subprocess.run")
    def test_invokes_semgrep_with_rules_and_returns_findings(self, mock_run, _bin, _rules):
        mock_run.return_value = mock.Mock(returncode=0, stdout=FIXTURE.read_text(), stderr="")
        findings = run_semgrep("/some/code/path")
        self.assertEqual(len(findings), 1)
        cmd = mock_run.call_args.args[0]
        self.assertIn("/bin/semgrep", cmd)
        self.assertIn("--config", cmd)
        self.assertIn("/rules", cmd)
        self.assertIn("--json", cmd)
        self.assertIn("/some/code/path", cmd)

    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_rules_dir", return_value="")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_bin", return_value="/bin/semgrep")
    @mock.patch("scanner.rag.semgrep_detector.subprocess.run")
    def test_falls_back_to_registry_packs_when_no_bundled_rules(self, mock_run, _bin, _rules):
        mock_run.return_value = mock.Mock(returncode=0, stdout='{"results":[]}', stderr="")
        run_semgrep("/code")
        cmd = mock_run.call_args.args[0]
        self.assertIn("p/security-audit", cmd)
        self.assertIn("p/owasp-top-ten", cmd)

    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_rules_dir", return_value="/rules")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_bin", return_value="/bin/semgrep")
    @mock.patch("scanner.rag.semgrep_detector.subprocess.run")
    def test_returns_empty_on_semgrep_failure(self, mock_run, _bin, _rules):
        mock_run.return_value = mock.Mock(returncode=2, stdout="", stderr="rule load error")
        self.assertEqual(run_semgrep("/code"), [])

    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_rules_dir", return_value="/rules")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_bin", return_value="/bin/semgrep")
    @mock.patch("scanner.rag.semgrep_detector.subprocess.run")
    def test_rc1_returns_findings(self, mock_run, _bin, _rules):
        """rc=1 is Semgrep's normal 'matches found' exit code; findings must be returned."""
        mock_run.return_value = mock.Mock(returncode=1, stdout=FIXTURE.read_text(), stderr="")
        findings = run_semgrep("/some/code/path")
        self.assertEqual(len(findings), 1)
