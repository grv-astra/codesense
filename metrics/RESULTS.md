# Code Sense — 12-Week Results (W1 → W12)

**Final measurement pass — 2026-07-01 (Week 12).** This is the roadmap's before/after
instrument (design spec §3, §7): every improvement shipped W1–W11 mapped back to the
balanced scorecard and re-measured against the W1 baseline with the **final build/model**
(the instruct path — Apache-2.0 Qwen2.5-Coder-7B-Instruct Q4_K_M — served live). The
per-week detail lives in [`metrics/scorecard.md`](scorecard.md); this file is the
consolidated headline + pass/fail vs the §9 acceptance thresholds + the narrative.

Thresholds (design spec §3, enforced by `scripts/eval/metrics.py`):
**detector/verifier F1 ≥ 0.70, recall ≥ 0.60, FP-rate ≤ 0.25; enrichment parse-rate > 0.80;
scan wall-time ↓ ≥ 40%.**

## Before / after — every scorecard axis

| Metric | W1 baseline (2026-06-10) | **W12 (2026-07-01, live)** | Target | Verdict |
|---|---|---|---|---|
| Detector F1 | 1.000 (N=4) | **1.000** (N=14, 7 langs) | ≥ 0.70 | ✅ PASS |
| Detector recall | 1.000 | **1.000** (TP=7/FN=0) | ≥ 0.60 | ✅ PASS |
| Detector FP-rate | 0.000 | **0.000** (FP=0/TN=7) | ≤ 0.25 | ✅ PASS |
| Verifier Tier-2 F1 | N/A (FIM couldn't classify) | **1.000** (8 findings, all TP-retained) | ≥ 0.70 | ✅ PASS |
| Verifier FP-suppression | **0.000** (FIM rubber-stamped TP ×32) | **0.857** (6/7 safe→FP) | improve | ✅ PASS |
| Enrichment parse-rate | 0.34 (FIM garbled JSON) | **1.00** (8/8; 0 CWE contradictions) | > 0.80 | ✅ PASS |
| Per-finding LLM latency | N/A | **29.7 s p50** (16 calls; 21.4–43.5 s) | record | ✅ recorded |
| Scan wall-time (p50) ↓ ≥ 40% | 540 s (reference) | **not validated** — single-slot CPU host | ↓ ≥ 40% | ⚠️ GAP |
| Signed build OK | False | **False** — certs + clean VM unavailable | True | ⚠️ GAP |
| App size (GB) | 5.7 | **~4.85** (core AI-payload proxy) | record | ✅ recorded |

### W12 scorecard (rendered by `scripts/eval/scorecard.py` `render_scorecard`)

| Metric | Value |
|---|---|
| Detector F1 | 1.000 |
| Detector FP-rate | 0.000 |
| Verifier FP-suppression | 0.857 |
| Verifier Tier-2 F1 | 1.000 |
| Enrichment parse-rate | 1.00 |
| Scan wall-time (p50, s) | N/A |
| Per-finding LLM latency (s) | 29.7 |
| Signed build OK | False |
| App size (GB) | 4.8 |

**Headline:** every **accuracy** axis meets or exceeds its §9 threshold on the final
build. The two open items — packaging signature and the ≥40% wall-time speed-up — are
**infrastructure/procurement gaps, not model or code regressions** (detail below).

## Provenance & caveats (how each W12 number was obtained)

All model-bound rows were measured against the **live** instruct host this session:
Apache-2.0 **Qwen2.5-Coder-7B-Instruct Q4_K_M** served by `llama-server` on
`127.0.0.1:8001` (`LLM_MODEL_MODE=instruct`), the sibling `astra-model-host/`. The host
is **CPU-only and single-slot** (serialized inference ~30 s/call at p50) — this is the
crux of the one performance gap.

**Accuracy**

- **Detector F1/recall/FP = 1.000/1.000/0.000** — `run_eval.py --dataset curated --tier
  detector --gate` over the **real OpenGrep + staged `dist/semgrep-rules`** (Windows).
  Verdict **PASS**, exit 0. Confusion TP=7/FP=0/FN=0/TN=7 across the **7 curated
  languages** (python, javascript, go, php, ruby, C#, kotlin), per-language recall 1.000
  for all seven. ⚠️ **N = 14 curated cases** — a smoke/coverage-level probe, not a
  statistically-meaningful headline; the OWASP Benchmark headline (Java, ~2,740 cases)
  remains deferred (needs a `BenchmarkJava` checkout — carried since W1).
- **Verifier Tier-2 F1 = 1.000** — the live verifier judged all **8** detector findings
  from the 7 real fixtures (the python SQLi case yields 2: CWE-89 + CWE-915) as **TP**
  at confidence 1.0, each with a concrete source→sink reason. tp=8/fp=0/fn=0/tn=0. This
  is a clean **TP-retention** pass: the verifier does not regress real findings.
- **Verifier FP-suppression = 0.857 (6/7)** — the row that was **0.000** at W1 (the
  central problem the model swap fixed). Because the curated **safe** fixtures are
  detector TNs (0 findings), none reach the verifier through the pipeline, so
  FP-suppression was measured with a **direct probe** (mirrors the W4 A/B method): each
  of the 7 safe fixtures' code was fed to the live verifier with a synthetic flagged
  dataflow at the fixture's line, expecting `FP`. **6/7 correctly returned FP** (parameterized
  queries / arg-array exec correctly recognized as safe). The **one miss** — `kt_cmdi_safe`
  → TP — errs **toward a spurious flag, not a missed vuln** (the safe direction for a
  security tool). Net vs W1: from *never* emitting FP (rubber-stamp) to **86% correct
  suppression** on genuine safe code.
- **Enrichment parse-rate = 1.00 (8/8)** — the live enricher authored a usable
  `FindingReport` for every one of the 8 real findings; **0 CWE-number contradictions** in
  the authored prose (CWE/severity/location stay deterministic, never LLM-authored). Up
  from **0.34** at W1. ⚠️ Title-phrase check here is a looser automated one (non-empty +
  no contradicting CWE token) than W5's manual audit; two titles still embed a canonical
  CWE phrase ("CWE-78: OS Command Injection") — cosmetic, the CWE field and body prose are
  correct. The deferred one-line "don't embed a CWE id/name in the title" prompt tweak
  (W5) still applies.

**Performance**

- **Per-finding LLM latency = 29.7 s p50** (mean 30.2 s, min 21.4 s, max 43.5 s over 16
  live calls: 8 verifier + 8 enrichment). This is the honest per-call cost of the 7B on
  this **CPU-only** box.
- **Scan wall-time ↓ ≥ 40% — NOT validated (documented gap).** W6 shipped bounded
  concurrency (`LSAST_MAX_WORKERS`) with **proven parallel≡serial finding identity**, but
  the only reachable host serializes inference on a single CPU slot, so overlapping
  in-flight LLM calls cannot beat that one slot — the ≥40% number needs a **multi-slot
  host** (GPU or a multi-core inference server), which was not available. The code path is
  in place and env-tunable; the measurement is owed on infra hardware. (The per-file
  detector rule-reload here — ~85 s/file — is a single-file-invocation artifact of the
  eval harness, **not** representative of a real folder scan, so it is not used as a
  wall-time figure.)

**Packaging**

- **Signed build OK = False** — the signing/notarization is **wired** (macOS via
  Tauri/Apple env; Windows `signtool` behind `-SigningCert`, W11) but cannot be produced
  without (a) an Apple Developer ID + notarization creds, (b) a Windows code-signing cert,
  and (c) per-OS clean test VMs — none available. Hard procurement blocker, not a code gap.
- **App size ≈ 4.85 GB** — measured core AI payload on disk: model GGUF 4.36 GiB +
  llama-server & runtime DLLs 78.7 MB + frozen backend 28.7 MB + OpenGrep 44.9 MB + rules
  6.7 MB ≈ **4.52 GiB ≈ 4.85 GB** (decimal, to match prior rows). Down from W1's 5.7 GB.
  ⚠️ Still a **staged-payload proxy**: no NSIS installer was producible on Windows — the
  32-bit `makensis` cannot mmap the 4.68 GB (decimal) GGUF (W11 finding). The full
  installed footprint adds the Grype CVE-DB snapshot + the offline WebView2 runtime,
  landing near the W1 5.7 GB.

## What improved over the 12 weeks

1. **The LLM went from a liability to the product's core value.** W1's bundled model was a
   non-commercially-licensed FIM code-completion model that **rubber-stamped every finding
   TP** (FP-suppression 0.000) and garbled enrichment JSON (parse-rate 0.34). It is now the
   **Apache-2.0 instruct 7B** (W2), driving a verifier that **suppresses 86% of false
   positives on safe code** (W4) and enrichment that **parses 100%** of findings (W5).
2. **The detector held its ground while coverage tripled.** The W1 characterization lock
   guaranteed the model swap never touched detection; curated coverage grew **2 → 7
   languages** (W8/W9) with F1/recall staying 1.000 and FP 0.000 throughout.
3. **Verdict metadata now flows end-to-end.** `rule_id`/`confidence`/`verifier_reason`
   persist (migration 0002, W7) and surface in a richer finding-details view with a CWE
   reference link and graceful empty-field degradation (W10, render-tested).
4. **The pipeline is parallel-ready and CI-gated.** W6 made per-finding LLM work
   concurrent (identity-proven); W8 added a detector-recall regression gate that exits
   non-zero below the §9 thresholds.
5. **Packaging is wired for a real signed offline build.** Instruct mode ships by default,
   the bundled `llama-server` resolves its DLLs on Windows, model tiers are threadable, and
   signing is gated behind cred-presence on both OSes (W11).

## What is still open (deferred per spec §7 / carried gaps)

- **≥40% scan speed-up — needs a multi-slot inference host.** The single most-owed number;
  code is ready, measurement is hardware-bound.
- **Signed installer + clean-VM install→scan acceptance** — blocked on Apple/Windows
  code-signing creds + per-OS VMs (procurement).
- **Windows packaging of the 7B** — the 32-bit NSIS `makensis` cannot mmap the 4.68 GB
  GGUF. Decide: ship low-tier 1.5B in the EXE (`-ModelTier low`, fits), split-GGUF shards,
  switch to WiX/MSI, or first-run fetch (breaks offline). macOS `.dmg` is unaffected.
- **Statistically-meaningful accuracy headline** — the OWASP Benchmark detector run (Java,
  ~2,740 cases) is still deferred; curated N=14 is a coverage probe. Grow curated with
  **genuine detector-FP cases** so verifier FP-suppression is exercised through the full
  pipeline (not just the direct probe).
- **CI on a real GitHub runner** — the eval gate is proven locally; it has not run on
  Actions (real Semgrep + upstream rules vs local OpenGrep + bundled rules — fidelity
  caveat in the workflow).
- **Deferred prompt tweaks** — fusion high-sev-FP policy (`needs_review` vs suppress now
  that the verifier discriminates reliably); the W5 enrichment title-phrase one-liner.
- **Pre-existing, out of scope:** `scripts/eval/tests/test_owasp.py` POSIX-path assertion
  fails on Windows (unrelated to the roadmap).

## Recommended next quarter

1. **Stand up a multi-slot inference host** (GPU or multi-core server) and close the two
   remaining gaps in one pass: validate the ≥40% wall-time speed-up (W6) and run the app's
   live scan end-to-end. This is the highest-leverage owed item.
2. **Procure code-signing creds + spin per-OS clean VMs**, then produce and verify a signed
   DMG + a Windows installer — resolving the NSIS 7B blocker first (low-tier EXE is the
   pragmatic default; WiX/MSI or split-GGUF for the 7B).
3. **Grow the eval set for a real headline**: land the OWASP Benchmark detector run and add
   genuine detector-FP curated cases so FP-suppression is measured through the pipeline.
4. **Deploy Phase 1 to production** (currently frozen on the legacy FIM path): push the
   stacked W9–W12 work, set `LLM_MODEL_MODE=instruct` on the cloud, and point it at a
   reachable instruct host served with `--jinja`.

## Acceptance (W12)

- `metrics/RESULTS.md` shows the before/after scorecard with targets met **or documented
  gaps** — ✅ (this file).
- `manage.py test scanner local.api_app` green — ✅ **169 pass / 2 skip** this session (was
  165/2; +4 for the W12.3 enrichment-title hardening fix, RED→GREEN).
- Eval gate green — ✅ (`run_eval.py --dataset curated --tier detector --gate` → **PASS**,
  exit 0, this session).
