import os
from unittest import mock

from django.test import SimpleTestCase

from scanner.rag.lsast_scanner import lsast_scan_folder
from scanner.rag.lsast_types import FindingReport, SemgrepFinding, VerifierVerdict
from scanner.rag.resume import fingerprint


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


class ProcessOneTests(SimpleTestCase):
    """W6.1 — the per-finding unit pulled out of the loop so a pool can run it.

    It must behave exactly like one iteration of the old serial loop: real
    normalize → verify → fuse → (enrich), returning the FusionOutcome, or None
    on a per-finding error, and honouring the fail-open `llm_ok=False` path.
    """

    @mock.patch("scanner.rag.lsast_scanner.generate_report", return_value=None)
    @mock.patch("scanner.rag.lsast_scanner.verify",
                return_value=VerifierVerdict("TP", "unsanitized concat", 0.9))
    def test_returns_show_outcome_for_tp(self, _v, _g):
        from scanner.rag.lsast_scanner import _process_one
        outcome = _process_one(_sqli_finding(), "s1", "u1")
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.action, "show")
        self.assertEqual(outcome.finding["cwe"], "CWE-89")

    @mock.patch("scanner.rag.lsast_scanner.generate_report", return_value=None)
    @mock.patch("scanner.rag.lsast_scanner.verify", side_effect=RuntimeError("boom"))
    def test_returns_none_on_processing_error(self, _v, _g):
        from scanner.rag.lsast_scanner import _process_one
        self.assertIsNone(_process_one(_sqli_finding(), "s1", "u1"))

    @mock.patch("scanner.rag.lsast_scanner.generate_report", return_value=None)
    @mock.patch("scanner.rag.lsast_scanner.verify")
    def test_llm_unavailable_skips_verify_and_enrich(self, mock_verify, mock_gen):
        from scanner.rag.lsast_scanner import _process_one
        outcome = _process_one(_sqli_finding(), "s1", "u1", llm_ok=False)
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.action, "show")     # fail-open TP preserved
        mock_verify.assert_not_called()
        mock_gen.assert_not_called()
        self.assertEqual(outcome.finding["fingerprint"], fingerprint(_sqli_finding()))

    @mock.patch("scanner.rag.lsast_scanner.generate_report", return_value=None)
    @mock.patch("scanner.rag.lsast_scanner.verify",
                return_value=VerifierVerdict("TP", "unsanitized concat", 0.9))
    def test_outcome_carries_a_fingerprint(self, _v, _g):
        from scanner.rag.lsast_scanner import _process_one
        sf = _sqli_finding()
        outcome = _process_one(sf, "s1", "u1")
        self.assertEqual(outcome.finding["fingerprint"], fingerprint(sf))


# --- W6.2: bounded-concurrency identity --------------------------------------
# Six findings chosen to hit ALL four fuse branches, so the parallel/serial
# comparison covers show / needs_review / suppress, not just the happy path.
#   (rule_suffix, severity, code_excerpt, verdict) -> outcome
_PARALLEL_CASES = [
    ("a", "high",     "e1", "TP"),   # -> show         (visible)
    ("b", "high",     "e2", "FP"),   # -> needs_review (visible, never dropped)
    ("c", "medium",   "e3", "TP"),   # -> show         (visible)
    ("d", "medium",   "e4", "FP"),   # -> suppress     (filtered)
    ("e", "critical", "e5", "FP"),   # -> needs_review (visible, never dropped)
    ("f", "low",      "e6", "TP"),   # -> show         (visible)
]
_VERDICT_BY_EXCERPT = {exc: vd for (_s, _sev, exc, vd) in _PARALLEL_CASES}


def _parallel_findings() -> list:
    out = []
    for i, (suf, sev, exc, _v) in enumerate(_PARALLEL_CASES, start=1):
        out.append(SemgrepFinding(
            rule_id=f"python.audit.rule.{suf}", cwe="CWE-89", severity=sev,
            message=f"issue {i}", file_path="app/views.py",
            start_line=i, end_line=i, code_excerpt=exc,
            taint_trace=[(i, f"src{i}"), (i, exc)], sanitizers_observed=[]))
    return out


def _verify_by_excerpt(**kw):
    """Deterministic and order-independent: keyed on the excerpt, not call order,
    so a pool that completes findings out of order still gets the same verdicts."""
    return VerifierVerdict(_VERDICT_BY_EXCERPT[kw["code_excerpt"]], "reason", 0.8)


# Fields that are deterministic given the input. `code` (random uuid) and
# `created_at` (timestamp) are intentionally excluded — they differ run-to-run
# even in the serial path, so "identical" means identical modulo those.
_STABLE_FIELDS = ("cwe", "severity", "status", "title", "file_path",
                  "cvss_score", "cvss_vector", "confidence", "verifier_reason",
                  "lines", "affected")


def _project(findings: list) -> list:
    return sorted(
        ({k: f.get(k) for k in _STABLE_FIELDS} for f in findings),
        key=lambda d: (str(d["file_path"]), str(d["title"])),
    )


class ParallelIdentityTests(SimpleTestCase):
    """W6.2 — the bounded-concurrency path yields the SAME finding set as serial."""

    def setUp(self):
        for tgt, kw in (
            ("scanner.rag.lsast_scanner.generate_report", {"return_value": None}),
            ("scanner.rag.lsast_scanner.llm_health", {"return_value": (True, "ok")}),
            ("scanner.rag.lsast_scanner.update_progress", {}),
            ("scanner.rag.lsast_scanner.save_findings_to_db", {}),
        ):
            p = mock.patch(tgt, **kw); p.start(); self.addCleanup(p.stop)

    def _run(self, workers: int):
        with mock.patch("scanner.rag.lsast_scanner.run_semgrep",
                        return_value=_parallel_findings()), \
             mock.patch("scanner.rag.lsast_scanner.verify",
                        side_effect=_verify_by_excerpt) as mv, \
             mock.patch.dict(os.environ, {"LSAST_MAX_WORKERS": str(workers)}):
            visible, filtered = lsast_scan_folder("/x", "s1", "u1")
        return visible, filtered, mv.call_count

    def test_parallel_matches_serial(self):
        sv, sf, s_calls = self._run(1)     # serial
        pv, pf, p_calls = self._run(8)     # parallel pool

        # exactly one verifier call per finding, both paths
        self.assertEqual(s_calls, 6)
        self.assertEqual(p_calls, 6)

        # identical visible + filtered partitions (order-independent)
        self.assertEqual(_project(sv), _project(pv))
        self.assertEqual(_project(sf), _project(pf))

        # sanity: all four fuse branches exercised (5 visible, 1 filtered)
        self.assertEqual(len(pv), 5)
        self.assertEqual(len(pf), 1)
        self.assertEqual(
            sum(1 for f in pv if f.get("status") == "needs_review"), 2)

    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    def test_each_visible_finding_persisted_once_under_concurrency(self, mock_save):
        # Progress/persistence must stay correct under the pool: one save call
        # per visible finding (incremental persist), none for suppressed ones.
        with mock.patch("scanner.rag.lsast_scanner.run_semgrep",
                        return_value=_parallel_findings()), \
             mock.patch("scanner.rag.lsast_scanner.verify",
                        side_effect=_verify_by_excerpt), \
             mock.patch.dict(os.environ, {"LSAST_MAX_WORKERS": "8"}):
            visible, _ = lsast_scan_folder("/x", "s1", "u1")
        self.assertEqual(mock_save.call_count, len(visible))   # one per visible

    def test_verify_calls_actually_overlap(self):
        """Proves real bounded concurrency: a Barrier(3) only releases if three
        verify() calls are in flight at once. A serial loop never reaches three
        parties, so this would time out (BrokenBarrierError) — it fails on the
        old sequential code and passes once the pool is wired."""
        import threading
        barrier = threading.Barrier(3, timeout=5)

        def _verify_waits(**kw):
            barrier.wait()   # blocks until 3 workers arrive; raises on timeout
            return _verify_by_excerpt(**kw)

        with mock.patch("scanner.rag.lsast_scanner.run_semgrep",
                        return_value=_parallel_findings()), \
             mock.patch("scanner.rag.lsast_scanner.verify", side_effect=_verify_waits), \
             mock.patch.dict(os.environ, {"LSAST_MAX_WORKERS": "3"}):
            visible, filtered = lsast_scan_folder("/x", "s1", "u1")
        self.assertEqual(len(visible) + len(filtered), 6)
