# Code Sense — Release Notes

## v1.0 — "LLM quality fixed + measured" (2026-07-01)

The close of the 12-week roadmap (design spec `docs/superpowers/specs/2026-05-31-…-design.md`).
Code Sense is an **offline** SAST desktop app: OpenGrep detection → an LLM verifier that suppresses
false positives → LLM-authored finding reports, all shipping with no network at runtime. This
release turns the bundled LLM from a liability into the product's core value and proves it with a
measured before/after scorecard. Full numbers: [`metrics/RESULTS.md`](../metrics/RESULTS.md).

### Highlights

- **License-clean, instruction-tuned model.** The bundled GGUF is now **Apache-2.0
  Qwen2.5-Coder-7B-Instruct Q4_K_M**, replacing a non-commercially-licensed fill-in-the-middle
  code model. The instruct JSON path ships by default in the app. *(W2/W3)*
- **The verifier actually suppresses false positives.** From **0.000** (the old model rubber-stamped
  every finding "true positive") to **0.857** — 6 of 7 genuinely-safe code samples correctly judged
  false-positive, with the one miss erring toward a spurious flag (never a missed vulnerability).
  *(W4, re-measured W12)*
- **Reliable enrichment.** Human-facing finding reports now parse **100%** of the time (up from 34%),
  with zero CWE contradictions in the authored prose. CWE / severity / location stay deterministic —
  never model-authored. *(W5, re-measured W12)*
- **Broader language coverage.** Curated per-language evaluation grew from 2 to **7 languages**
  (python, javascript, go, php, ruby, C#, kotlin) with detector F1/recall **1.000** and FP **0.000**
  held throughout. *(W8/W9)*
- **Richer triage UX.** The finding-details view surfaces the verifier verdict (confidence, reason,
  rule id), a deterministic CWE reference link, and degrades gracefully when fields are empty.
  *(W10)*
- **Parallel-ready, CI-gated pipeline.** Per-finding LLM work runs under bounded concurrency
  (`LSAST_MAX_WORKERS`) with proven parallel≡serial finding identity; a detector-recall regression
  gate fails CI below threshold. *(W6/W8)*
- **Verdict metadata persisted end-to-end.** `rule_id` / `confidence` / `verifier_reason` survive
  the DB (additive migration `0002`, back-compatible) and are returned by the findings API. *(W7)*
- **Packaging wired for a signed offline build.** Instruct mode + a loadable bundled `llama-server`
  (Windows DLLs staged) + threadable model tiers + signing gated behind cred-presence on macOS and
  Windows. *(W11)*

### Scorecard vs targets (final, W12)

| Metric | Baseline | Final | Target | Status |
|---|---|---|---|---|
| Detector F1 / recall / FP | 1.000 / 1.000 / 0.000 | 1.000 / 1.000 / 0.000 | ≥.70 / ≥.60 / ≤.25 | ✅ |
| Verifier Tier-2 F1 | N/A | 1.000 | ≥ 0.70 | ✅ |
| Verifier FP-suppression | 0.000 | 0.857 | improve | ✅ |
| Enrichment parse-rate | 0.34 | 1.00 | > 0.80 | ✅ |
| Scan wall-time ↓ ≥ 40% | 540 s | not validated | ↓ ≥ 40% | ⚠️ |
| Signed build | False | False | True | ⚠️ |

All accuracy targets met. The two ⚠️ items are **infrastructure/procurement gaps, not regressions.**

### Known limitations / not in this release

- **≥40% scan speed-up is not yet validated.** The parallelization code shipped (W6), but the only
  available inference host is CPU-only and single-slot (~30 s/finding), which cannot demonstrate the
  speed-up — it needs a multi-slot (GPU/multi-core) host.
- **No signed installer yet.** Signing is wired on both OSes but needs Apple/Windows code-signing
  credentials + clean per-OS VMs to produce and verify a real install→scan.
- **Windows packaging of the 7B model is blocked** by a 32-bit NSIS `makensis` ~2 GB per-file mmap
  limit (the model is ~4.68 GB). Options: ship the low-tier 1.5B in the EXE (`-ModelTier low`),
  split-GGUF shards, WiX/MSI, or first-run fetch. macOS `.dmg` is unaffected.
- **Accuracy numbers are coverage-level (N=14 curated), not a statistical headline.** The OWASP
  Benchmark detector run (Java, ~2,740 cases) remains deferred.
- Deferred prompt/policy tweaks: the fusion high-severity-FP policy (`needs_review` vs suppress) is
  an open product decision now that the verifier discriminates reliably.

### Deployment note

Production is currently frozen on the legacy FIM path. To ship this release to the cloud: deploy the
stacked W6–W12 work, set `LLM_MODEL_MODE=instruct`, and point `VLLM_BASE_URL`/`VLLM_MODEL`/
`VLLM_API_KEY` at a reachable instruct host served with `--jinja`.
