import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from scanner.rag.semgrep_detector import (
    run_semgrep, parse_semgrep_json, derive_cwe, _extract_taint_trace, _read_code_lines)
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
    def test_forces_utf8_env_and_omits_metrics_flag(self, mock_run, _bin, _rules):
        # The bundled engine is OpenGrep: it rejects --metrics (rc=2) and reads
        # rule YAMLs with the process locale, so we drop the flag and force UTF-8.
        mock_run.return_value = mock.Mock(returncode=0, stdout='{"results":[]}', stderr="")
        run_semgrep("/code")
        cmd = mock_run.call_args.args[0]
        self.assertNotIn("--metrics", cmd)
        env = mock_run.call_args.kwargs["env"]
        self.assertEqual(env["LC_ALL"], "C.UTF-8")
        self.assertEqual(env["LANG"], "C.UTF-8")
        self.assertEqual(env["PYTHONUTF8"], "1")
        self.assertEqual(env["SEMGREP_SEND_METRICS"], "off")

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

    @mock.patch("scanner.rag.semgrep_detector.get_privacy_rules_dir", return_value="/privacy-rules")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_rules_dir", return_value="/rules")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_bin", return_value="/bin/semgrep")
    @mock.patch("scanner.rag.semgrep_detector.subprocess.run")
    def test_layers_privacy_rules_config_alongside_bundled_rules(self, mock_run, _bin, _rules, _privacy):
        mock_run.return_value = mock.Mock(returncode=0, stdout='{"results":[]}', stderr="")
        run_semgrep("/code")
        cmd = mock_run.call_args.args[0]
        self.assertIn("/rules", cmd)
        self.assertIn("/privacy-rules", cmd)
        # both dirs get their own --config flag
        self.assertEqual(cmd.count("--config"), 2)

    @mock.patch("scanner.rag.semgrep_detector.get_privacy_rules_dir", return_value="/privacy-rules")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_rules_dir", return_value="")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_bin", return_value="/bin/semgrep")
    @mock.patch("scanner.rag.semgrep_detector.subprocess.run")
    def test_layers_privacy_rules_config_alongside_registry_packs(self, mock_run, _bin, _rules, _privacy):
        mock_run.return_value = mock.Mock(returncode=0, stdout='{"results":[]}', stderr="")
        run_semgrep("/code")
        cmd = mock_run.call_args.args[0]
        self.assertIn("p/security-audit", cmd)
        self.assertIn("/privacy-rules", cmd)

    @mock.patch("scanner.rag.semgrep_detector.get_privacy_rules_dir", return_value="")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_rules_dir", return_value="/rules")
    @mock.patch("scanner.rag.semgrep_detector.get_semgrep_bin", return_value="/bin/semgrep")
    @mock.patch("scanner.rag.semgrep_detector.subprocess.run")
    def test_omits_privacy_config_when_not_bundled(self, mock_run, _bin, _rules, _privacy):
        mock_run.return_value = mock.Mock(returncode=0, stdout='{"results":[]}', stderr="")
        run_semgrep("/code")
        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd.count("--config"), 1)


class DeriveCweTests(SimpleTestCase):
    """Layered CWE derivation: explicit -> rule-name keyword -> OWASP -> category."""

    def test_explicit_cwe_string_and_int(self):
        self.assertEqual(derive_cwe({"cwe": "CWE-89: SQLi"}, "x"), "CWE-89")
        self.assertEqual(derive_cwe({"cwe": [89]}, "x"), "CWE-89")
        self.assertEqual(derive_cwe({"cwe": ["89: SQL Injection"]}, "x"), "CWE-89")

    def test_rule_id_keyword_when_no_metadata(self):
        self.assertEqual(derive_cwe({}, "js.security.path-traversal.path-join"), "CWE-22")
        self.assertEqual(derive_cwe({}, "x.jsonwebtoken.security.hardcoded-jwt-secret"), "CWE-798")
        self.assertEqual(derive_cwe({}, "x.express.security.express-check-csurf"), "CWE-352")

    def test_owasp_fallback(self):
        self.assertEqual(derive_cwe({"owasp": "A03:2021 - Injection"}, "rule"), "CWE-74")
        self.assertEqual(
            derive_cwe({"owasp": ["A07:2017 - Cross-Site Scripting (XSS)"]}, "r"), "CWE-79")
        self.assertEqual(derive_cwe({"owasp": "A10:2021 - Server-Side Request Forgery (SSRF)"}, "r"),
                         "CWE-918")

    def test_non_security_category_maps_to_coding_standards(self):
        self.assertEqual(derive_cwe({"category": "correctness"}, "useless-assignment"), "CWE-710")
        self.assertEqual(
            derive_cwe({"category": "best-practice"}, "dockerfile-source-not-pinned"), "CWE-710")

    def test_security_category_without_signal_stays_unknown(self):
        # We must NOT fabricate a CWE for an unclassifiable security rule.
        self.assertEqual(derive_cwe({"category": "security"}, "some-obscure-rule"), "")

    def test_rule_id_keyword_does_not_misfire(self):
        # 'source' contains the substring 'rce' — a naive map would mislabel this
        # best-practice rule as CWE-78 (OS command injection). It must not.
        self.assertNotEqual(
            derive_cwe({"category": "best-practice"}, "dockerfile-source-not-pinned"), "CWE-78")
        self.assertEqual(
            derive_cwe({"category": "best-practice"}, "dockerfile-source-not-pinned"), "CWE-710")

    def test_precedence_explicit_beats_keyword(self):
        # An explicit (even unusual) CWE wins over a keyword guess from the id.
        self.assertEqual(derive_cwe({"cwe": "CWE-1234"}, "x.sqli.tainted-sql"), "CWE-1234")

    def test_command_exec_cwe94_corrected_to_cwe78(self):
        # Upstream php rules (tainted-exec, exec-use) tag their shell_exec/system/
        # exec/passthru/proc_open sinks as CWE-94 (code injection), but an OS
        # command-execution sink is CWE-78. Correct that mislabel.
        cwe94 = "CWE-94: Improper Control of Generation of Code ('Code Injection')"
        self.assertEqual(derive_cwe({"cwe": cwe94}, "php.lang.security.tainted-exec"), "CWE-78")
        self.assertEqual(derive_cwe({"cwe": cwe94}, "php.lang.security.exec-use"), "CWE-78")
        self.assertEqual(
            derive_cwe({"cwe": cwe94}, "php.wordpress.wp-command-execution-audit"), "CWE-78")

    def test_genuine_code_injection_stays_cwe94(self):
        # eval/assert/create_function code-injection rules are REALLY CWE-94 — the
        # correction must not touch them (no OS-command-exec signal in the id).
        cwe94 = "CWE-94: Improper Control of Generation of Code ('Code Injection')"
        self.assertEqual(derive_cwe({"cwe": cwe94}, "php.lang.security.eval-use"), "CWE-94")
        self.assertEqual(derive_cwe({}, "js.lang.security.code-injection"), "CWE-94")


class ExtractTaintTraceTests(SimpleTestCase):
    """Taint trace must parse BOTH engine shapes and never raise (an unparsed
    node must not sink the scan — the real OpenGrep crash this guards)."""

    def test_semgrep_list_of_dicts_shape(self):
        extra = {"dataflow_trace": {
            "taint_source": [{"start": {"line": 5}, "code": "req.q"}],
            "intermediate_vars": [],
            "taint_sink": [{"start": {"line": 9}, "content": "exec(x)"}],
        }}
        self.assertEqual(_extract_taint_trace(extra), [(5, "req.q"), (9, "exec(x)")])

    def test_opengrep_cliloc_tagged_tuple_shape(self):
        # OpenGrep: ["CliLoc", [{start:{line}}, "code"]] — item[0] is a STRING tag,
        # not a dict. The old parser did item.get(...) on "CliLoc" -> AttributeError.
        extra = {"dataflow_trace": {
            "taint_source": ["CliLoc",
                             [{"start": {"line": 30}, "end": {"line": 33}}, "jwt.sign(x, 'secret')"]],
            "intermediate_vars": [],
            "taint_sink": ["CliLoc", [{"start": {"line": 30}}, "jwt.sign(x, 'secret')"]],
        }}
        out = _extract_taint_trace(extra)
        self.assertIn((30, "jwt.sign(x, 'secret')"), out)

    def test_garbage_shapes_never_raise(self):
        self.assertEqual(_extract_taint_trace({"dataflow_trace": "nope"}), [])
        self.assertEqual(_extract_taint_trace({}), [])
        self.assertEqual(
            _extract_taint_trace({"dataflow_trace": {"taint_source": ["weird", 123, None]}}), [])


class CodeSnippetRecoveryTests(SimpleTestCase):
    """Semgrep redacts the `lines` field as 'requires login' for registry rules
    when unauthenticated (the cloud uses registry packs). run_semgrep recovers
    the real snippet from disk so the stored snippet + LLM context aren't blank."""

    def test_read_code_lines_reads_range(self):
        import os, tempfile
        p = os.path.join(tempfile.mkdtemp(), "x.py")
        Path(p).write_text("a=1\nb=2\nc=3\n")
        self.assertEqual(_read_code_lines(p, 2, 2), "b=2")
        self.assertEqual(_read_code_lines(p, 1, 3), "a=1\nb=2\nc=3")

    def test_read_code_lines_handles_bad_input(self):
        self.assertEqual(_read_code_lines("/no/such/file", 1, 1), "")
        self.assertEqual(_read_code_lines("", 0, 0), "")

    @mock.patch("scanner.rag.semgrep_detector.subprocess.run")
    def test_run_semgrep_recovers_redacted_snippet(self, mock_run):
        import os, tempfile
        p = os.path.join(tempfile.mkdtemp(), "installation.py")
        Path(p).write_text("\n".join(f"row{i}" for i in range(1, 10)))
        doc = {"results": [{
            "check_id": "python.lang.security.audit.dangerous-subprocess-use",
            "path": p,
            "start": {"line": 3}, "end": {"line": 3},
            "extra": {"lines": "requires login", "message": "m",
                      "severity": "WARNING", "metadata": {"cwe": ["CWE-78"]}},
        }]}
        mock_run.return_value = mock.Mock(returncode=0, stdout=json.dumps(doc), stderr="")
        findings = run_semgrep(p)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].code_excerpt, "row3")   # recovered from disk
