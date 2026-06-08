# Code Sense Roadmap — Phase 2 Plan (Weeks 6–8): Performance + Foundational Product

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development or
> superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** cut scan latency by parallelizing the per-finding LLM calls, persist + expose the verifier's
verdict metadata, and add a CI regression gate so detection quality can't silently drop.

**Architecture:** batching uses a bounded `ThreadPoolExecutor` (LLM calls are IO-bound; threads release the
GIL during `requests`). Verdict metadata becomes real Finding fields via an additive migration (back-compat
default). The CI gate reuses the existing `scripts/eval/run_eval.py --gate`.

**Tech Stack:** Python/Django, `concurrent.futures`, the `scripts/eval/` harness, GitHub Actions.
Tests: `cd server && .venv/bin/python manage.py test scanner`. **Spec/Phase1:** see the spec + phase1 docs.

---

## Week 6 — Batch / parallelize the verifier + reporter calls

**Session goal:** the LSAST pipeline runs the per-finding LLM work concurrently (bounded), producing an
identical finding set, materially faster. **Acceptance test:** a unit test proves the parallel path yields
the same visible/filtered findings as sequential (mocked LLMs) and calls each LLM once per finding; live DVB
scan wall-time ↓ ≥ 40% vs the W1 baseline. **Milestone: latency target hit.**

### Task 6.1: Extract per-finding processing into a pure function

**Files:** Modify `server/scanner/rag/lsast_scanner.py`; Test `server/scanner/tests/test_lsast_scanner.py`

- [ ] **Step 1: Write the failing test** (a `_process_one` that does normalize→verify→fuse→enrich for one finding)
```python
# add to test_lsast_scanner.py
from scanner.rag.lsast_scanner import _process_one
from scanner.rag.lsast_types import SemgrepFinding, VerifierVerdict

class ProcessOneTests(SimpleTestCase):
    @mock.patch("scanner.rag.lsast_scanner.generate_report", return_value=None)
    @mock.patch("scanner.rag.lsast_scanner.verify", return_value=VerifierVerdict("TP","x",0.9))
    def test_process_one_returns_outcome(self, _v, _g):
        sf = SemgrepFinding(rule_id="r.sqli", cwe="CWE-89", severity="high", message="m",
                            file_path="a.py", start_line=1, end_line=2, code_excerpt="x",
                            taint_trace=[], sanitizers_observed=[])
        outcome = _process_one(sf, "s1", "u1")
        self.assertEqual(outcome.action, "show")
        self.assertEqual(outcome.finding["cwe"], "CWE-89")
```
- [ ] **Step 2: Run** → FAIL (`cannot import name '_process_one'`).
- [ ] **Step 3: Refactor `lsast_scan_folder`** — pull the loop body into `_process_one(sf, scan_id, triggered_by) -> FusionOutcome | None` (returns `None` on the per-finding exception), and have the loop call it. (Behavior identical; this just makes the unit parallelizable.)
```python
def _process_one(sf, scan_id, triggered_by):
    try:
        finding_dict, dataflow = normalize(sf, scan_id=scan_id, triggered_by=triggered_by)
        verdict = verify(cwe=sf.cwe, language=language_for_path(sf.file_path).name,
                         dataflow=dataflow, code_excerpt=sf.code_excerpt)
        outcome = fuse(finding_dict, verdict)
    except Exception as exc:
        logger.warning("LSAST: skipping finding %s — %s", getattr(sf, "rule_id", "?"), exc)
        return None
    if outcome.action != "suppress":
        report = generate_report(
            rule_name=outcome.finding.get("title", ""), cwe=outcome.finding.get("cwe", ""),
            language=language_for_path(sf.file_path).name, file_path=sf.file_path,
            line=sf.start_line, dataflow=dataflow, code_excerpt=sf.code_excerpt,
            detector_note=sf.message)
        apply_report(outcome.finding, report)
    return outcome
```
- [ ] **Step 4: Run** `manage.py test scanner.tests.test_lsast_scanner` → PASS (existing + new).
- [ ] **Step 5: Commit** `git commit -am "refactor(lsast): extract _process_one for parallelization"`

### Task 6.2: Parallelize with a bounded pool (config-gated)

**Files:** Modify `server/scanner/rag/lsast_scanner.py`; Test `server/scanner/tests/test_lsast_scanner.py`
- [ ] **Step 1: Failing test** — same findings as sequential, order preserved, each LLM called once
```python
class ParallelScanTests(SimpleTestCase):
    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.generate_report", return_value=None)
    @mock.patch("scanner.rag.lsast_scanner.verify")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep")
    def test_parallel_matches_sequential(self, run, vfy, _g, _save):
        fs = [SemgrepFinding(rule_id=f"r{i}", cwe="CWE-89", severity="high", message="m",
              file_path="a.py", start_line=i, end_line=i, code_excerpt="x",
              taint_trace=[], sanitizers_observed=[]) for i in range(5)]
        run.return_value = fs
        vfy.return_value = VerifierVerdict("TP", "x", 0.9)
        with mock.patch.dict(os.environ, {"LSAST_MAX_WORKERS": "4"}):
            visible, filtered = lsast_scan_folder("/x", "s1", "u1")
        self.assertEqual(len(visible), 5)
        self.assertEqual(vfy.call_count, 5)
```
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** the parallel loop in `lsast_scan_folder`:
```python
import os
from concurrent.futures import ThreadPoolExecutor

def _max_workers() -> int:
    try: return max(1, int(os.getenv("LSAST_MAX_WORKERS", "4")))
    except ValueError: return 4

# inside lsast_scan_folder, replace the sequential loop:
    workers = _max_workers()
    if workers > 1 and len(sem_findings) > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            outcomes = list(ex.map(lambda sf: _process_one(sf, scan_id, triggered_by), sem_findings))
    else:
        outcomes = [_process_one(sf, scan_id, triggered_by) for sf in sem_findings]
    for outcome in outcomes:
        if outcome is None: continue
        (filtered if outcome.action == "suppress" else visible).append(outcome.finding)
```
- [ ] **Step 4: Run** `manage.py test scanner` → Expected: all green. **Step 5: Commit** `git commit -am "feat(lsast): bounded-concurrency LLM calls (LSAST_MAX_WORKERS, default 4)"`

### Task 6.3: Measure + handoff
- [ ] Live DVB scan (instruct model), record wall-time in `metrics/scorecard.md` "W6" and compute the % drop vs W1. Update `CLAUDE.md`; commit; write the W7 brief.

> **W7 brief:** add `confidence`, `verifier_reason`, `rule_id` to `_FIELDS` in
> `server/local/api_app/models/finding_models.py`; set `rule_id` in `normalize`; expose the fields in the
> finding serializer/API. Acceptance: API returns them; round-trip test.

---

## Week 7 — Persist + expose verdict metadata

**Session goal:** the verifier's `confidence`/`verifier_reason` and the Semgrep `rule_id` survive persistence
and are returned by the API (today `insert_many` drops them). **Acceptance test:** a test asserts the new keys
are retained by the `_FIELDS` filter and `normalize` sets `rule_id`; the finding API response includes them.

### Task 7.1: Add the fields to the model field list + normalizer

**Files:** Modify `server/local/api_app/models/finding_models.py` (the `_FIELDS` list, line 4-8) and
`server/scanner/rag/finding_normalizer.py`; Test `server/scanner/tests/test_finding_normalizer.py`
- [ ] **Step 1: Failing test** (normalize sets rule_id; the field filter keeps the new keys)
```python
# add to test_finding_normalizer.py
from local.api_app.models.finding_models import _FIELDS

def test_normalize_sets_rule_id_and_new_fields_are_persisted():
    from scanner.rag.finding_normalizer import normalize
    f = _sample_finding()
    fd, _ = normalize(f, "s", "u")
    assert fd["rule_id"] == f.rule_id
    for k in ("rule_id", "confidence", "verifier_reason"):
        assert k in _FIELDS, f"{k} must be a persisted field"
```
- [ ] **Step 2: Run** → FAIL. **Step 3a:** in `finding_models.py` add `"rule_id", "confidence", "verifier_reason"` to `_FIELDS`. **Step 3b:** in `normalize`, add `"rule_id": f.rule_id,` and defaults `"confidence": None, "verifier_reason": "",` to the finding dict (fuse overwrites confidence/verifier_reason for visible findings).
- [ ] **Step 4: Run** `manage.py test scanner.tests.test_finding_normalizer` → PASS. **Step 5: Commit** `git commit -am "feat(findings): persist rule_id + verifier confidence/reason"`

### Task 7.2: Database migration (additive, back-compat)
**Files:** Create a migration under `server/local/api_app/migrations/` (follow the newest existing migration's pattern)
- [ ] **Step 1:** Generate: `cd server && .venv/bin/python manage.py makemigrations api_app` (adds the three nullable columns). Inspect the generated file — confirm `null=True`/`blank=True` defaults (back-compat for existing rows).
- [ ] **Step 2:** Apply: `.venv/bin/python manage.py migrate` → Expected: `Applying api_app.NNNN... OK`.
- [ ] **Step 3:** Round-trip test in `server/scanner/tests/test_finding_persistence.py` (a `TransactionTestCase` that saves a finding dict with the new keys and reads them back). Run → PASS.
- [ ] **Step 4: Commit** `git add -A && git commit -m "feat(db): migration for rule_id/confidence/verifier_reason"`

### Task 7.3: Expose in the API + handoff
**Files:** Modify the finding serializer (grep: `grep -rl "security_risk" server/local/api_app/views server/local/api_app/serializers* 2>/dev/null`)
- [ ] **Step 1:** Add `rule_id`, `confidence`, `verifier_reason` to the finding serializer's field list (follow the existing field pattern).
- [ ] **Step 2:** Verify via the API: `curl .../api/findings/scan/<sid>/` returns the new keys (a test or a manual check). 
- [ ] **Step 3:** Update `CLAUDE.md`; commit; write the W8 brief.

> **W8 brief:** wire `run_eval.py --dataset curated --tier detector --gate` into CI (`.github/workflows/`),
> failing on a recall regression; grow the curated manifest. Acceptance: CI fails on an injected regression.

---

## Week 8 — Eval CI regression gate + grow curated set

**Session goal:** detector recall regressions fail CI; the curated set covers more languages.
**Acceptance test:** the CI job exits non-zero when a regression is injected; the curated manifest gains N
cases across ≥ 3 languages and the detector tier still passes. **Milestone: no silent regressions.**

### Task 8.1: CI workflow running the detector gate
**Files:** Create `.github/workflows/lsast-eval-gate.yml`
- [ ] **Step 1:** Write the workflow — checkout, set up Python + `server/.venv` deps, stage rules via
  `scripts/offline_sbom/stage_semgrep_rules.py`, then:
```yaml
      - name: Detector regression gate
        run: |
          cd scripts/eval
          PYTHONPATH=../../server SEMGREP_BIN=../../server/.venv/bin/semgrep \
            SEMGREP_RULES_DIR="$RULES_DIR" \
            ../../server/.venv/bin/python run_eval.py --dataset curated --tier detector --gate
```
- [ ] **Step 2:** Locally simulate the gate pass: run the command above → Expected: exit 0 + metrics above §9 floor.
- [ ] **Step 3:** Inject a regression check: temporarily point at a broken rules dir → Expected: `--gate` exits 1. Revert.
- [ ] **Step 4: Commit** `git add .github/workflows/lsast-eval-gate.yml && git commit -m "ci(eval): detector recall regression gate"`

### Task 8.2: Grow the curated set (≥3 new languages)
**Files:** Add fixtures under `scripts/eval/data/curated/` + entries in `scripts/eval/data/curated/manifest.yml` (follow the existing manifest entry shape: `file, lines, cwe, label`)
- [ ] **Step 1:** Add one real + one safe fixture each for e.g. Go, Ruby, PHP (one case per file — see BASELINE.md issue 3). 
- [ ] **Step 2:** Run `run_eval.py --dataset curated --tier detector` → Expected: new cases matched; recall stable/up. **Step 3: Commit** `git commit -am "test(eval): grow curated set across Go/Ruby/PHP"`
- [ ] **Step 4:** Update `CLAUDE.md` (Phase 2 done); commit; write the W9 brief (language coverage expansion).

## Phase 2 acceptance summary
- [ ] Parallel scan: identical findings, ≥40% faster (scorecard W6).
- [ ] `rule_id`/`confidence`/`verifier_reason` persisted (migration) + in the API.
- [ ] CI gate fails on injected regression; curated set +3 languages.
- [ ] `manage.py test scanner` green.
