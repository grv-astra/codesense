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
   **FIXED (2026-05-31, commit `1880aae`):** added
   `scripts/offline_sbom/stage_semgrep_rules.py`, which clones the repo and prunes
   every YAML lacking a top-level `rules:` key (78 in the current clone; note the
   offenders include nested `*.test.yaml`, so pointing at language subdirs alone is
   *not* enough), leaving a valid `--config` target. `build_macos.sh` now calls it;
   `build_windows.ps1` previously bundled no rules **and no semgrep binary** — both
   were added (OpenGrep staged as `semgrep.exe`). Verified: `semgrep --config <staged>`
   over the curated fixtures returns **rc=0** (was 7), flags both unsafe cases, and
   clears both safe ones. Guarded by `scripts/offline_sbom/tests/test_stage_semgrep_rules.py`.
2. **Default registry packs find nothing offline.** `run_semgrep`'s fallback packs
   (`p/security-audit`, `p/owasp-top-ten`, `p/secrets`) returned 0 findings (likely need
   `semgrep login`/registry fetch). The bundled-rules path (SEMGREP_RULES_DIR) is the
   one that must work for the offline product.
3. **Curated FP measurement needs one-case-per-file.** Fixed during this run — the
   initial fixtures put real+safe in one file, and file+CWE matching cross-counted them
   as FPs. Now one case per file (like OWASP).
4. **`run_eval.py`/README must use the venv python**, not system `python3` (Django+DRF).

## Recommended next steps (follow-on, not in this plan)
- ~~Fix the build script's rule bundling (issue 1) — highest priority; without it the
  shipped scanner detects nothing.~~ **DONE** — see issue 1 above (staging helper + tests;
  Windows semgrep binary also added).
- Grow the curated set across more of the top-40 languages.
- Run the OWASP Benchmark detector tier for a real headline F1/recall.
- ~~Run the sampled verifier tier against llama-server to measure FP suppression.~~
  **DONE — see "Verifier (Tier 2) audit" below.**

## Verifier (Tier 2) audit — 2026-05-31 (manual, live llama-server)

Ran the verifier live (`scanner.rag.llm_verifier.verify`) over all 32 Semgrep
findings from the Damn-Vulnerable-Bank backend, plus a controlled safe/unsafe
A/B. **Result: the verifier currently provides ZERO FP-suppression value.**

| Probe | Verdict | Correct? |
|---|---|---|
| 32 DVB findings (real vulns + lint-y) | **TP × 32** (conf 0.8–0.9, 0 fail-open) | n/a — keeps everything |
| A/B: SQLi via string concat (unsafe) | TP | ✓ |
| A/B: SQLi parameterized `%s,[q]` (safe) | **TP** — reason literally said *"parameterized queries, which prevents SQL injection"* | ✗ |

**Root cause — model capability, not a code bug.** The bundled model (`astra.gguf`,
alias `astra-code-reviewer`) is a **fill-in-the-middle code-completion model**, not
an instruction-tuned classifier (see the header comments in `scanner/rag/llm.py`).
Empirically it has a near-total **`TP`-label bias**: it emits `"verdict":"TP"` for
everything — *even code whose own `reason` it describes as safe*. It is **not**
failing open (it reaches the server and returns parseable JSON with conf 0.8–0.9);
it simply never says `FP`. Since `fusion.fuse` only suppresses on `FP`+low/medium
severity, nothing is ever suppressed → every finding stays `open`. That is the
entire explanation for "kept all 50 open" — rubber-stamping, not adjudication.

**Prompt fixes don't help (tested).** A safe-default reframing and a one-shot
FP/TP example both *degraded* output: the FIM model echoed the (longer) prompt
back verbatim → unparseable → fail-open `TP`. The current terse JSON prompt is the
only one that reliably parses, and it still returns all-`TP`. So this cannot be
fixed by prompting.

**Why no quick code patch was applied.** The model's prose `reason` is sometimes
correct, so a "parse the reason and flip TP→FP" override was considered and
**rejected**: it is fragile (the model also hallucinates — in prompt B it called
the parameterized query "without proper sanitization"), and in a security tool a
wrong *suppression* (missed vulnerability) is worse than a kept false positive.
The current fail-safe (show everything) is the correct default while the model is
non-discriminative.

**Recommended fix (follow-on initiative, needs a product decision).** Replace the
verifier model with a small **instruction-tuned** model that can follow the JSON
verdict contract and actually emit `FP` (e.g. Qwen2.5-Coder-Instruct-3B/7B,
Llama-3.2-3B-Instruct), re-bundle the GGUF, and re-measure with this same Tier-2
probe. Optionally pair with guided/GBNF decoding to lock the `verdict` field to
`{TP,FP}`. Secondary: `fusion` sets `confidence`/`verifier_reason` but
`FindingModel.insert_many` drops them (not model fields) — persist them (small
migration) so verdict metadata survives once the model is trustworthy.
