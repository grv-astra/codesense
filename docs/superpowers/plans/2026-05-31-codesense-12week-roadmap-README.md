# Code Sense 12-Week Roadmap — Index (weeks → tasks → milestones)

**Spec:** [`../specs/2026-05-31-codesense-12week-roadmap-design.md`](../specs/2026-05-31-codesense-12week-roadmap-design.md)
**Plans:** [Phase 1](2026-05-31-codesense-12week-roadmap-phase1.md) · [Phase 2](2026-05-31-codesense-12week-roadmap-phase2.md) · [Phase 3](2026-05-31-codesense-12week-roadmap-phase3.md)

**Execution model:** one Claude Code session per week, context reset between. Every week ends by: acceptance
test passes → `CLAUDE.md`/docs updated → next-week brief written. Strategy A (foundation/model-first).
**Scorecard:** `metrics/scorecard.md` (baseline W1, re-measured W12 in `metrics/RESULTS.md`).

| Wk | Phase | Goal | Key tasks | Acceptance test | Milestone |
|---|---|---|---|---|---|
| 1 | 1 | Baselines + characterization lock | 1.1 characterization test, 1.2 scorecard + baseline | scorecard.md filled; characterization green | Baseline established |
| 2 | 1 | License-safe model behind a flag | 2.1 `LLM_MODEL_MODE`, 2.2 convert GGUF, 2.3 round-trip | instruct model loads/serves behind flag; legacy unchanged | **Compliance blocker resolved** |
| 3 | 1 | De-FIM client + grammar JSON | 3.1 instruct branch, 3.2 verifier/enricher response_format | A/B: safe→FP, unsafe→TP; JSON ≈100% | — |
| 4 | 1 | Verifier correctness + fusion | 4.1 FP-default prompt, 4.2 Tier-2 measure | Tier-2 meets §9 (or documented gap) | **Verifier discriminates** |
| 5 | 1 | Enrichment quality + device tiers | 5.1 tier→gguf map, 5.2 parse-rate | enrichment >80% parse; ≥2 tiers switch | **LLM quality fixed** |
| 6 | 2 | Batch/parallelize LLM calls | 6.1 `_process_one`, 6.2 ThreadPool | identical findings, ↓≥40% wall-time | **Latency target hit** |
| 7 | 2 | Persist + expose verdict metadata | 7.1 fields+normalize, 7.2 migration, 7.3 API | API returns rule_id/confidence/reason; round-trip test | — |
| 8 | 2 | Eval CI gate + grow curated | 8.1 CI workflow, 8.2 +3 languages | CI fails on injected regression | **No silent regressions** |
| 9 | 3 | Language-coverage expansion *(feature)* | 9.1 registry entries, 9.2 per-language eval | ≥4 langs route + pass per-language eval | Broader coverage, measured |
| 10 | 3 | Finding-details UX overhaul *(feature)* | 10.1 TS type, 10.2 render fields | details view renders verdict/remediation/CWE; render test | Richer triage UX |
| 11 | 3 | Clean signed/notarized build | 11.1 macOS DMG, 11.2 Windows EXE | install+run+scan on a fresh VM | **Shippable installer** |
| 12 | 3 | Harden + measure results | 12.1 re-measure, 12.2 RESULTS.md, 12.3 fixes | RESULTS.md before/after; tests + gate green | **Outcomes measured** |

## Phase milestones
- **Phase 1 (W1–5):** license-clean instruct model live; verifier emits FP; enrichment >80%; detector locked.
- **Phase 2 (W6–8):** ≥40% faster scans; verdict metadata persisted + exposed; CI regression gate.
- **Phase 3 (W9–12):** +4 languages; richer finding-details UX; signed installers; measured before/after.

## Non-negotiables (every week)
- Backward-compatible: characterization tests + flags before changing legacy code.
- Measurable: each improvement maps to a scorecard metric, measured before & after.
- Independently shippable: one session, acceptance-tested, next-week brief written.

## Deferred (explicitly out of scope for these 12 weeks)
Beating commercial SAST; multi-engine (CodeQL); full top-40 deep coverage; auto-tuning; a results dashboard;
cloud/multi-user. (Spec §2 / §7.)
