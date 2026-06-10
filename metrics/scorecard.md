# Code Sense — Balanced Scorecard

The single before/after instrument for the 12-week roadmap (spec §3). Baselined in
**W1**, re-measured in **W12** (`metrics/RESULTS.md`). Every roadmap improvement maps
to a row here and is measured before & after. Rows marked `N/A — established W#` need a
component that does not exist yet this week (the instruct model, a signed build, etc.);
they are filled in the week named.

Table rows are produced by `scripts/eval/scorecard.py` (`render_scorecard`), unit-tested
in `scripts/eval/tests/test_scorecard.py`.

## Baseline (W1) — 2026-06-10

| Metric | Value |
|---|---|
| Detector F1 | 1.000 |
| Detector FP-rate | 0.000 |
| Verifier FP-suppression | 0.000 |
| Verifier Tier-2 F1 | N/A |
| Enrichment parse-rate | 0.34 |
| Scan wall-time (p50, s) | 540 |
| Per-finding LLM latency (s) | N/A |
| Signed build OK | False |
| App size (GB) | 5.7 |

## Provenance & caveats (how each number was obtained)

**Accuracy**

- **Detector F1 = 1.000 / FP-rate = 0.000** — measured *this session on Windows* via
  `run_eval.py --dataset curated --tier detector` (real OpenGrep + the staged
  `dist/semgrep-rules`). Result: P=R=F1=1.000, FP-rate=0.000, TP=2/FP=0/FN=0/TN=2;
  per-language recall python 1.000, javascript 1.000. Run artifact:
  `scripts/eval/results/20260610T063827Z.md`. ⚠️ **N = 4 curated cases** — a smoke-level
  baseline, not a statistically meaningful headline (grow the curated set before reading
  much into it; the OWASP Benchmark headline is deferred — needs a `BenchmarkJava`
  checkout). This matches the prior macOS baseline in `scripts/eval/BASELINE.md`, i.e. the
  detector behaves identically across OSes.
- **Verifier FP-suppression = 0.000** — from the W0 verifier audit (`scripts/eval/BASELINE.md`,
  "Verifier (Tier 2) audit"): the bundled FIM model (`astra.gguf` = Qwen2.5-Coder-3B,
  fill-in-the-middle) rubber-stamps **`TP × 32`** over the Damn-Vulnerable-Bank backend and
  on the safe/unsafe A/B — it never emits `FP`, so `fusion` suppresses nothing. This is the
  central problem the model swap (W2–W4) fixes. Not re-measured this session: **the LLM
  stages fail open locally** (no `astra.gguf` staged / `VLLM_BASE_URL` unset), so the
  verifier returns no verdict here at all.
- **Verifier Tier-2 F1 = N/A — established W4.** Needs an instruction-tuned model that can
  actually discriminate; measured against §9 (F1 ≥ 0.70, FP ≤ 25%, recall ≥ 0.60) once the
  W2 model swap + W3 de-FIM JSON path land.
- **Enrichment parse-rate = 0.34** — from this session-lineage's enrichment audit (spec §1.2 /
  CLAUDE.md): the same FIM model garbles JSON, so only ~34% of findings receive a full
  report (the rest fail open to the deterministic Semgrep-derived text). Target > 80%,
  **established W5** with the instruct model. Not re-measured this session (LLM fails open).

**Performance**

- **Scan wall-time (p50) ≈ 540 s** — the documented Damn-Vulnerable-Bank full-backend scan
  (~9 min) reference figure carried into W1 as the latency baseline for the W6 ≥40% target.
  ⚠️ Provenance is the prior LLM-enabled run; a local Windows run *with the LLM failing open*
  is faster (no per-finding model calls), so this is a reference baseline, not a clean W1
  Windows re-measure. W6 re-measures p50 on a fixed corpus before/after parallelization.
- **Per-finding LLM latency = N/A — established W6** (needs a live `llama-server`; LLM fails
  open locally this week).

**Packaging**

- **Signed build OK = False** — distribution was previously verified by in-place binary swap,
  not a clean signed installer. **Established W11** (signed/notarized DMG + EXE).
- **App size (GB) = 5.7** — recorded app-bundle size of the prior build (dominated by the
  bundled GGUF + llama-server + OpenGrep). Re-recorded W11/W12 after the model swap (the
  Apache 7B Q4_K_M is ~4.7 GB).

## Status vs §9 thresholds (this week)

- Detector: **PASS** (F1 1.000 ≥ 0.70, recall 1.000 ≥ 0.60, FP 0.000 ≤ 0.25) — on N=4.
- Verifier Tier-2: **not yet measurable** (model-bound; W4).
- The W1 deliverable is the *baseline + the characterization lock*, not hitting the verifier
  bar — that is W4's milestone.
