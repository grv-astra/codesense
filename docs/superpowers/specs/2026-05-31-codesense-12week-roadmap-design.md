# Code Sense — 12-Week Improvement Roadmap (Spec)

- **Date:** 2026-05-31
- **Status:** Approved design (pre-plan)
- **Repo:** `yacm` (Code Sense), branch `main`
- **Builds on:** the LSAST pipeline + this session's work (rule-name titles, OpenGrep bundling/compat,
  layered CWE derivation, verifier audit, LLM report-enrichment) and
  `2026-05-31-instruction-tuned-verifier-model-swap-scope.md`.

## 1. Problem & goals

LSAST works end-to-end (91 scanner tests green; detector + normalizer + CWE derivation are solid), but
three things block it from being a shippable, trustworthy product:

1. **The verifier can't discriminate** — the bundled model (`astra.gguf` = Qwen2.5-Coder-3B, a
   fill-in-the-middle base model) rubber-stamps every finding `TP`, so fusion suppresses nothing.
2. **Report enrichment is unreliable** — same model garbles JSON; only ~34% of findings get a full report.
3. **Compliance blocker** — Qwen2.5-Coder-3B is under the **non-commercial `qwen-research`** license.

Plus: scans are slow (~2 sequential LLM calls/finding), there is no live accuracy baseline or regression
gate, verdict metadata isn't surfaced, and distribution builds were verified by in-place swap rather than a
clean signed installer.

**Goal:** over 12 one-per-week sessions, take LSAST to **license-clean, accurate, fast, and packaged**,
proven by a balanced before/after scorecard — without breaking existing behavior.

## 2. Scope

**In scope (phased, model swap as centerpiece):**
- Phase 1 (W1–5): baselines + characterization lock; license-safe instruction-tuned model; de-FIM client +
  grammar-constrained JSON; working verifier (real FP-suppression); reliable enrichment + device-tier model
  config.
- Phase 2 (W6–8): batch/parallelize LLM calls; persist + expose verdict metadata; eval CI regression gate.
- Phase 3 (W9–12): language-coverage expansion (feature); finding-details UX overhaul (feature); clean
  signed/notarized DMG + EXE; harden + measure results.

**Out of scope (deferred / YAGNI):** beating commercial SAST on accuracy; multi-engine (CodeQL/linters);
deep coverage for the full top-40 (only a chosen batch); auto-tuning; a results dashboard; cloud/multi-user;
mobile. The push to `origin` is the user's (auth-blocked) action, not roadmap work.

## 3. Success metrics — the balanced scorecard

Baselined in **W1**, re-measured in **W12** (every improvement names a metric, measured before & after):

| Axis | Metrics |
|---|---|
| **Accuracy** | detector precision/recall/F1 + FP-rate (eval Tier-1, curated + OWASP if present); verifier FP-suppression rate + Tier-2 F1 vs §9 (**F1 ≥ 0.70, FP ≤ 25%, recall ≥ 0.60**); enrichment parse-rate % + accuracy spot-check |
| **Performance** | DVB scan wall-time (p50), per-finding LLM latency, model load RAM/time |
| **Packaging** | clean signed-build success (DMG/EXE), install-and-scan on a fresh VM (pass/fail), app size |

Where a baseline is currently unknown, W1 either measures it or records `N/A — established W#`.

## 4. Architecture impact

- **Model:** swap `astra.gguf` → an Apache-2.0 **Qwen2.5-Coder-Instruct** GGUF (7B mid-tier default; 1.5B
  low, 14B high). Same ChatML family → one code path. Served by the existing `llama-server`.
- **LLM client (`server/scanner/rag/llm.py`):** add a model "mode" (FIM vs instruct); for instruct, disable
  the FIM `_STOP_TOKENS` + `_clean_output` "Vulnerability:" hunting, allow a system prompt, and add
  grammar-constrained JSON (`response_format`/GBNF). Backward-compatible (FIM path stays for the old model).
- **Pipeline (`lsast_scanner.py`):** introduce bounded-concurrency batching of the verifier + reporter calls.
- **Data model:** migration to persist `confidence` / `verifier_reason` / rule id on the Finding model;
  serializer + API expose them; UI consumes them.
- **Detector (`semgrep_detector.py`) / normalizer:** unchanged in behavior — **locked by characterization
  tests** so the model/UX work can't regress detection. Language work adds rules + routing only.
- **Build (`scripts/build_*.{sh,ps1}`, `convert_model_to_gguf.sh`):** stage the new model per device tier;
  produce a clean signed installer.

## 5. Sequencing (chosen: Strategy A — foundation/model-first)

Default "stabilize → foundation → features → harden" order, because the model swap both **unblocks** the
verifier + enrichment and **removes the license blocker**, so every later week builds on a model that works.
(Rejected: B "quick-wins-first" ships visible wins sooner but builds product on broken LLM output; C
"parallel tracks" fits one-session/week-with-reset poorly.)

## 6. The 12-week roadmap

Each week = a clear goal + a concrete **acceptance test**; each session ends by: acceptance test passes,
`CLAUDE.md`/docs updated, and a **next-week brief** written (so the next reset-context session can start cold).

### Phase 1 — Stabilize + model swap (W1–5)
| Wk | Goal | Acceptance test | Milestone |
|---|---|---|---|
| 1 | Baselines + **characterization lock** | `metrics/scorecard.md` committed with real numbers (or `N/A — established W#`) for every row; characterization suite pins current detector/normalizer/CWE output on a fixed fixture corpus and is green | Baseline established |
| 2 | **License-safe model** (Qwen2.5-Coder-7B-Instruct, Apache) → GGUF, bundled **behind a flag** | flag on → `llama-server` serves it, `healthcheck()` passes, chat round-trip integration test; flag off → behavior unchanged | Compliance blocker resolved |
| 3 | **De-FIM client + grammar-JSON** (instruct mode) | verifier A/B probe: safe-parameterized → `FP`, unsafe-concat → `TP`; JSON parse ≈100% on the probe set; existing tests green | — |
| 4 | **Verifier correctness + fusion suppression** | eval Tier-2 on curated meets §9 (or a documented gap + plan); characterization tests still green (detector unaffected) | Verifier discriminates |
| 5 | **Enrichment quality + device-tier model config** | enrichment parse-rate > 80% + accurate on a 10-finding set; ≥2 tiers (e.g. 1.5B/7B) switch cleanly via config; tests green | LLM quality fixed |

### Phase 2 — Performance + foundational product (W6–8)
| Wk | Goal | Acceptance test | Milestone |
|---|---|---|---|
| 6 | **Batch/parallelize** verifier + reporter calls | DVB scan wall-time ↓ ≥ 40% vs W1 baseline; identical finding set (characterization); llama-server not oversaturated | Latency target hit |
| 7 | **Persist + expose verdict metadata** (confidence/reason/rule id) | migration applied; API returns the new fields; round-trip persistence test; existing rows back-compatible | — |
| 8 | **Eval CI regression gate** + grow curated set | CI job fails on an injected detector-recall regression; curated set + N cases across ≥ 3 languages | No silent regressions |

### Phase 3 — Features + packaging + harden (W9–12)
| Wk | Goal | Acceptance test | Milestone |
|---|---|---|---|
| 9 | **Language-coverage expansion** *(feature)* | ≥ 4 new top-40 languages, each with a passing per-language detector eval + a coverage-registry entry; routing-only langs report "no analyzer coverage" | Broader coverage, measured |
| 10 | **Finding-details UX overhaul** *(feature; consumes W7)* | details view renders confidence, verifier reason, remediation, dataflow, CWE link, severity for a real scan; graceful on empty fields; render test | Richer triage UX |
| 11 | **Clean signed/notarized build** (DMG + EXE) | a clean build artifact installs + runs + completes a scan on a fresh machine/VM, with the real OpenGrep + Apache model + rules bundled; app size recorded | Shippable installer |
| 12 | **Harden + measure results** | full scorecard re-run; before/after vs W1 documented; top regressions fixed; `RESULTS.md` + release notes committed | 12-week outcomes measured |

## 7. Calibrated depth — what "done at Week 12" means / does NOT mean

**DOES mean:** a license-clean, instruction-tuned model; a verifier that actually suppresses false
positives; reliable (>80% parse) enrichment; ~40%+ faster scans; verdict metadata surfaced in a richer
finding-details view; +4 languages with per-language eval; a clean signed installer (macOS + Windows); a
measured before/after scorecard; a CI regression gate.

**Does NOT mean:** state-of-the-art detection accuracy or parity with commercial SAST; a second analysis
engine (CodeQL); deep coverage of the entire top-40 (only the chosen batch); automated rule/prompt tuning; a
results dashboard; cloud or multi-user. Each week is **one Claude Code session** — depth is bounded to
"shippable + acceptance-tested," not exhaustive.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Model swap regresses the **detector** | Characterization tests (W1) lock detector/normalizer/CWE output; the model only touches the verifier + enricher |
| Instruct model too **slow on CPU** | Device tiers (1.5B/7B/14B) + bounded-concurrency batching (W6) + Q4_K_M; mid-tier default 7B |
| llama.cpp **grammar/JSON** flakiness across builds | Pin the llama.cpp version; prefer `response_format: json_object`; keep the fail-open parser |
| Migration **breaks existing findings** | Additive columns + back-compat default; round-trip test on old rows |
| Signed build needs **Apple/Windows creds** | Keep an unsigned local-build fallback path (already in `build_macos.sh`) |
| **One-session/week context loss** | Each week is self-contained, ships behind a flag where risky, and ends by updating `CLAUDE.md` + writing the next-week brief |
| Model swap **legal** sign-off pending | W2 lands the Apache model behind a flag; default flip only after sign-off |

## 9. Non-negotiables honored
- **Backward compatibility:** characterization/regression tests added **before** changing legacy code;
  risky changes (new model, JSON mode, metadata schema) gated by flags + back-compat defaults.
- **Measurability:** every improvement maps to a scorecard metric, measured before & after.
- **Independently shippable weeks:** one session each, acceptance-tested, with a written next-week brief and
  updated `CLAUDE.md`.

## 10. Deliverables
- This spec (committed).
- Three phase plans: `docs/superpowers/plans/2026-05-31-codesense-12week-roadmap-phase{1,2,3}.md` — per-week
  TDD tasks with exact file paths, runnable code, commands + expected output, and commits.
- A README index mapping weeks → tasks → milestones.
