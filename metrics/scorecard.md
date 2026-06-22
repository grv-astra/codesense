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

## Status vs §9 thresholds (W1)

- Detector: **PASS** (F1 1.000 ≥ 0.70, recall 1.000 ≥ 0.60, FP 0.000 ≤ 0.25) — on N=4.
- Verifier Tier-2: **not yet measurable** (model-bound; W4).
- The W1 deliverable is the *baseline + the characterization lock*, not hitting the verifier
  bar — that is W4's milestone.

## Week 4 (Verifier accuracy) — 2026-06-22

First measurement with a working verifier: the W2 Apache-2.0 instruct model
(Qwen2.5-Coder-7B-Instruct Q4_K_M) served locally + the W4.1 verifier-prompt fix
(explicit TP/FP semantics, default-FP). Branch `week4-verifier-accuracy`.

| Metric | W1 baseline | W4 | Target (§9) |
|---|---|---|---|
| Verifier FP-suppression | 0.000 (FIM rubber-stamped TP) | **working** — emits FP on safe code (see A/B) | — |
| Verifier Tier-2 F1 (curated) | N/A | **1.000** (P=R=1.0, FP-rate=0.0) ⚠️ see caveat | ≥ 0.70 |
| Verifier Tier-2 FP-rate (curated) | N/A | **0.000** ⚠️ see caveat | ≤ 0.25 |

### Provenance & caveats

- **Tier-2 on curated (`--dataset curated`)** — built verifier samples by running the
  real detector on each curated case to get its dataflow + code, then ran the **live**
  verifier (instruct mode, `127.0.0.1:8001`). Result: **tp=2 fp=0 fn=0 tn=0 →
  P=R=F1=1.000, FP-rate=0.000**. Both real cases (`py_sqli_unsafe`, `js_cmdi_unsafe`)
  correctly kept as TP at conf 1.00.
  ⚠️ **Curated does not exercise FP-suppression.** The detector flags **0 of the 2 safe
  cases** (`py_sqli_safe`, `js_cmdi_safe` are detector TNs — already its FP-rate=0.000), so
  **no false positive ever reaches the verifier** on this set. The 1.000/0.000 here is a
  clean pass but a *trivial* one for the verifier. Measuring real verifier FP-suppression
  needs cases where the detector over-flags safe code — see the A/B below; grow the curated
  set with detector-FP cases (parameterized/prepared queries the rules still flag) in a
  later week.
- **FP-suppression evidence (A/B, DVWA-shaped)** — the verifier was run on 4 hand-built
  safe/unsafe pairs that mimic the DVWA regression (last week the FIM model flagged the
  secure `impossible.*` files identically to vulnerable ones):
  - PDO prepared statement (`impossible.php` shape) → **FP** ✓ (the exact W3 regression)
  - constant / not-attacker-controlled → **FP** ✓
  - string-concat SQLi (`low` shape) → **TP** ✓
  - Python DBAPI `execute(sql, params)` `%s`/`?` parameterization → **TP ✗** (the 7B
    conflates safe bound-parameter placeholders with `%`-string-formatting). **3/4.**
  The one miss errs toward **TP** (a spurious flag, not a missed vuln) — the safe direction
  for a security tool. Net vs W1: the verifier went from *never* emitting FP (0.000) to
  correctly suppressing the real DVWA false-positive shapes.
- **Fusion behaviour (confirmed, with an important nuance)** — `fuse()` suppresses an FP
  verdict **only at low/medium severity** (`status="filtered"`). A **high/critical** FP
  verdict is **not dropped** — it becomes `needs_review`, titled `[verifier:FP] …`, "never
  drop a high-severity finding on a 3B model's say-so." So DVWA's `impossible.*` SQLi (HIGH)
  now re-classifies from a confident *show* to `needs_review` tagged `[verifier:FP]` with the
  FP reason — a real improvement, but **not full suppression** of high-severity FPs.
  **Open question for the user:** now that the 7B verifier discriminates reliably, should a
  high-confidence high-severity FP be down-ranked/suppressed rather than kept as
  `needs_review`? That is a fusion-policy change, deliberately out of scope this week.

### Status vs §9 thresholds (W4)

- Verifier Tier-2 (curated): **PASS** (F1 1.000 ≥ 0.70, recall 1.000 ≥ 0.60, FP 0.000 ≤
  0.25) — but on N=2 reaching the verifier, and **not exercising FP-suppression** (caveat
  above). Treat as "verifier no longer regresses real findings", not as a headline
  FP-suppression number.
- The substantive W4.1 win is qualitative + A/B-proven: the verifier now emits `FP` on safe
  code (PDO-prepared, constants) where the FIM model could not. A statistically meaningful
  FP-suppression headline needs a curated set with genuine detector false positives.
