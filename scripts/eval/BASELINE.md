# LSAST Eval — Phase 2 baseline (2026-05-31)

First baseline from the eval harness. Run on a dev host (Apple Silicon), branch
`phase2-eval-languages`, Semgrep 1.164.0, rules = the `python/` + `javascript/`
subdirs of `github.com/semgrep/semgrep-rules` (510 rule files).

## Result — curated set, Tier 1 (detector), deterministic

| Stage | Precision | Recall | F1 | FP-rate | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|---|
| Detector (Tier 1) | 1.000 | 1.000 | 1.000 | 0.000 | 2 | 0 | 0 | 2 |

Per-language detector recall: python 1.000, javascript 1.000. **Verdict: PASS** vs
§9 thresholds (F1 ≥ 0.70, recall ≥ 0.60, FP ≤ 0.25).

The detector flags both real vulns (Python SQLi via tainted concat; JS command
injection via `exec`) and correctly clears both safe variants (parameterized query;
`execFile` arg-array). Tier 2 (verifier) shows zeros — it's a manual, llama-server
pass and was not run here (by design).

## How to reproduce
```bash
cd scripts/eval
PYTHONPATH=../../server \
SEMGREP_BIN=../../server/.venv/bin/semgrep \
SEMGREP_RULES_DIR=/path/to/semgrep-rules-python-and-javascript \
../../server/.venv/bin/python run_eval.py --dataset curated --tier detector
```
(Use the **venv** python — `_scanner()` needs Django+DRF, which aren't in system python3.)

## Honest caveats (this is a smoke-level baseline, not a headline number)
1. **N = 4 curated cases.** Perfect P/R here is reassuring but not statistically
   meaningful. The curated set must grow (more cases, more of the top-40 languages)
   before these numbers mean much.
2. **OWASP Benchmark not run** — needs a `BenchmarkJava` checkout (Java, ~2,740 cases).
   The adapter + matching are built and unit-tested; the headline F1/recall against
   OWASP is deferred to a run with the dataset present.
3. **Verifier (Tier 2) not measured** — needs llama-server; the sampled+cached pass is
   built and unit-tested but run manually.

## Issues the baseline surfaced (real, actionable)
1. **Production rule-bundling is broken.** `build_macos.sh` clones the *entire*
   `semgrep-rules` repo and points `SEMGREP_RULES_DIR` at it. Semgrep then aborts with
   **rc=7** ("invalid configuration file found") because the repo root contains non-rule
   YAML (e.g. `.pre-commit-config.yaml` lacks a top-level `rules` key). **Fix:** bundle
   only the language rule subdirs (or strip non-rule YAMLs) — pointing at a clean
   `{python,javascript,...}` dir works. *(Until fixed, a packaged scan finds nothing.)*
2. **Default registry packs find nothing offline.** `run_semgrep`'s fallback packs
   (`p/security-audit`, `p/owasp-top-ten`, `p/secrets`) returned 0 findings (likely need
   `semgrep login`/registry fetch). The bundled-rules path (SEMGREP_RULES_DIR) is the
   one that must work for the offline product.
3. **Curated FP measurement needs one-case-per-file.** Fixed during this run — the
   initial fixtures put real+safe in one file, and file+CWE matching cross-counted them
   as FPs. Now one case per file (like OWASP).
4. **`run_eval.py`/README must use the venv python**, not system `python3` (Django+DRF).

## Recommended next steps (follow-on, not in this plan)
- Fix the build script's rule bundling (issue 1) — highest priority; without it the
  shipped scanner detects nothing.
- Grow the curated set across more of the top-40 languages.
- Run the OWASP Benchmark detector tier for a real headline F1/recall.
- Run the sampled verifier tier against llama-server to measure FP suppression.
