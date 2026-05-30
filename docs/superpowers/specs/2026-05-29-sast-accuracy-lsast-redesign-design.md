# Code Sense — SAST Accuracy Redesign (LSAST architecture)

- **Date:** 2026-05-29
- **Status:** Approved design (pre-implementation)
- **Author:** Brainstormed with Claude (deep-research-backed)
- **Repo:** `yacm` (Code Sense)

## 1. Problem statement

The current Code Sense SAST scanner ([server/scanner/rag/](../../../server/scanner/rag/)) produces ~100 % false positives on real codebases. Root causes identified by reading the pipeline:

1. The prompt **pre-hints the vulnerability** (`"Risk indicators detected: SQL Injection, User Input"`) → the small model confirms the hint instead of analyzing.
2. **Zero dataflow / taint tracking** — the LLM sees a ±15-line window around a sink with no visibility into whether data is tainted or already sanitized.
3. **Zero interprocedural context** — caller/callee relationships are invisible.
4. **No verification pass** — single-shot LLM → finding.
5. **Risk regexes match nearly any code** (`os.path.join`, `open(`, `requests.get`).
6. **No sanitizer awareness** — parameterized queries, ORM, escaping are not recognized.
7. **Small 3 B model** (Qwen2.5-Coder-3B fine-tune, q8_0) is more pattern-completer than reasoner in thin context.
8. **Output format biases toward emitting a finding** rather than declining.

## 2. What the research established

Deep research (16 verified findings, sources incl. peer-reviewed papers, vendor patents, vendor docs) found:

- **Checkmarx / Fortify / Veracode share one architecture pattern:** language-agnostic IR built once → declarative rule DSL separated from the engine → interprocedural taint analysis → **explicit sanitizer modeling as a first-class category** (Fortify's `Validate`, Checkmarx's "flow barrier" nodes, Veracode's multi-color taint tags).
- **LSAST is the strongest empirically-grounded recipe for an offline LLM scanner** (Esposito et al. 2024, arXiv:2409.15735): run a conservative deterministic scanner first, inject its findings into the LLM prompt as an oracle, instruct the LLM to verify them. Lifted Llama-3-70B from **F1 0.39 → 0.77**. Follow-on hybrid systems (ZeroFalse, SAST-Genius) reach **F1 0.91–0.95**.
- **Critical caveat for our 3 B model:** Xiong & Zhang (2026, arXiv:2601.22952) showed agentic frameworks improve strong models (+16.7 pp on Sonnet 4) but **regress weaker models** (−1.9 pp on DeepSeek Chat). A Qwen2.5-Coder-3B-class model must be used as a **constrained single-turn classifier**, not an autonomous detector.
- **Naive RAG hurts** (F1 76.5 % → 49.2 % when retrieval relevance is loose).
- The production-deployed commercial pattern in 2025 (Veracode Fix) is the same shape: **rule-based SAST detects → LLM acts downstream**.

## 3. Locked decisions

| Topic | Decision |
|-------|----------|
| Architecture | **LSAST**: deterministic rule-based detector first, LLM as downstream verifier |
| Detector | Semgrep (or OpenGrep — the OSS fork) with taint mode + curated rule packs, bundled offline |
| LLM role | **Constrained single-turn TP/FP classifier**. Never invents findings. Forced JSON output, temperature 0, no agent loop |
| Recall ceiling | Semgrep + bundled rule packs. Adding an LLM "find-extras" pass is **out of scope** for Phase 1 (option C rejected — too risky on a 3 B model) |
| Sanitizer model | Use Semgrep's built-in sanitizer rules (single-color taint). Multi-color taint (Veracode-style) is a Phase 4+ initiative |
| Offline | Fully offline. Semgrep CLI + rule packs bundled in the .app (~50 MB total) |
| Rule pack scope | Phase 1: `p/security-audit`, `p/owasp-top-ten`, `p/secrets` + per-language for **Python, JavaScript/TypeScript, Java, Go** |
| Model fine-tuning | Out of scope for now (uncurated LLMs replicate insecurities; separate large initiative) |

## 4. Architecture

```
Per scan target (folder):
 1. AST analyze (existing)          → metrics
 2. File pre-filter (existing)      → skip lock/license/etc.
 3. Semgrep detector (NEW)          ── taint mode + curated rule packs
        ↓ findings: rule_id, source loc, sink loc, taint trace,
                    sanitizers observed, code excerpt, CWE, severity
 4. Normalizer (NEW)                → unified Finding dict + DataflowContext
        ↓
 5. LLM verifier (NEW)              single-turn constrained classifier
        Input  : dataflow trace + code excerpt + sanitizers + CWE
        Output : forced JSON {verdict, reason, confidence}
        ↓
 6. Confidence fusion (NEW)         combine Semgrep severity + LLM verdict
        ↓
 7. Persist                         TP findings as today;
                                    LLM-suppressed shown in a separate
                                    "filtered" view (auditable)
```

The legacy LLM-primary path stays available behind a feature flag (`SCAN_ENGINE=legacy`) during transition. Default flips to `lsast` after the eval harness (Phase 2) confirms the new pipeline meets acceptance criteria.

## 5. Components

| File (new unless noted) | Responsibility |
|---|---|
| `scanner/rag/lsast_types.py` | Dataclasses: `SemgrepFinding`, `DataflowContext`, `VerifierVerdict` |
| `scanner/rag/semgrep_detector.py` | Invoke `semgrep --config <bundled> --json <path>`; parse → list[SemgrepFinding] |
| `scanner/rag/finding_normalizer.py` | `SemgrepFinding` → existing `Finding` dict + extract `DataflowContext` |
| `scanner/rag/llm_verifier.py` | Constrained verifier (forced JSON, strict parse, fail-open) — replaces today's `analysis.py` + `prompts.py` for the new path |
| `scanner/rag/fusion.py` | Combine Semgrep severity + LLM verdict per fusion rules |
| `scanner/rag/lsast_scanner.py` | Orchestrator: detector → normalizer → verifier → fusion → persist |
| `scanner/rag/scanner.py` *(modify)* | Feature flag: route to `lsast_scanner` or legacy path |
| `server/codesense.spec` *(modify)* | Bundle Semgrep CLI + rule packs into the frozen backend |
| `scripts/build_macos.sh` / `build_windows.ps1` *(modify)* | Stage Semgrep + rules into the Tauri bundle |

## 6. The prompt change (the single biggest lever)

**Before** (pre-hints the vulnerability):
```
Analyze the following py code for security vulnerabilities.
Risk indicators detected: SQL Injection, User Input.
If vulnerable, respond in this format: Vulnerability: ...
```

**After** (judges a concrete claim, with the dataflow):
```
A static dataflow analyzer flagged a potential CWE-89 (SQL Injection).

Dataflow trace:
  Source : request.GET["q"]                line 12
  → step : query = "SELECT … WHERE x='" + q + "'"   line 14
  → Sink : cursor.execute(query)           line 18
Sanitizers observed in trace: none

Code (lines 8–22):
```python
…code…
```

QUESTION: Is this finding a TRUE positive or a FALSE positive? Consider
whether any sanitizer / parameterization / ORM / framework escaping
makes the sink safe.

Respond with ONLY this JSON, no prose:
{"verdict":"TP"|"FP", "reason":"<≤200 chars>", "confidence": 0.0-1.0}
```

The model judges instead of searches, sees an **explicit dataflow** (the missing context that drove FPs), is told which sanitizers to consider, and is bounded by **forced JSON** parsed strictly.

## 7. Confidence fusion rules

**`confidence` = the verifier's confidence in its own verdict** (NOT a function of Semgrep severity — severity is a separate axis, "how bad if real", carried in the `severity` field; the verifier is the "how likely real" judge). This keeps a fail-open low-confidence TP visibly uncertain instead of being inflated by severity.

| LLM verdict | Semgrep severity | Outcome |
|---|---|---|
| `TP` | any | Show as TP. `confidence = verdict.confidence` |
| `FP` | `low` or `medium` | **Suppress** (write to filtered view, hidden by default) |
| `FP` | `high` or `critical` | Keep as **"needs review"** (never silently drop a high-severity finding on a 3 B model's say-so) |
| parse failure / timeout | any | Show as **low-confidence TP** (fail open) |

## 8. Bundle & deployment

- Semgrep CLI shipped as a sidecar at `Contents/MacOS/semgrep-<triple>` (~30 MB) — same pattern as syft/grype/cosign.
- Bundled rule packs at `Contents/Resources/semgrep-rules/` (~20 MB), refreshed at each repackage.
- Env wiring from the Tauri shell: `SEMGREP_BIN`, `SEMGREP_RULES_DIR`.
- All offline at runtime.

## 9. Acceptance criteria (the bar — measured by Phase 2 eval harness)

- **F1 ≥ 0.70** on the OWASP Benchmark Java subset (commercial tools land 0.45–0.85; LSAST paper hit 0.77 on Llama-3-70B).
- **FP rate ≤ 25 %** on a curated real-world sample (vs. ~100 % today).
- **Recall ≥ 0.60** — no precision wins via silently dropping real bugs.
- CI gate on every prompt / rule / fusion change.

## 10. Phased rollout

- **Phase 1 (this plan):** Core LSAST pipeline behind a feature flag (`SCAN_ENGINE`). Working end-to-end with bundled Semgrep + rule packs + verifier + fusion + unit/smoke tests. Default `legacy` until eval gates pass.
- **Phase 2:** Eval harness (OWASP Benchmark + Juliet + curated real-world set). Tune verifier prompt + rule packs against held-out data. Flip default to `lsast`.
- **Phase 3:** FP feedback loop in UI (mark FP → suppression file → next scan skips).
- **Phase 4+ (later):** Custom rule authoring; multi-color taint; LSAST find-extras pass (if 3 B verifier accuracy improves enough).

## 11. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Semgrep rule gaps on niche frameworks | Use curated registry packs; add custom rules per real-world miss |
| 3 B verifier wrongly suppresses a real critical | Fusion never silently drops high-severity Semgrep findings; only demotes low/medium; auditable filtered view |
| Forced-JSON parse failures | Fail-open (show as low-confidence TP); track parse-failure rate as a health metric |
| Recall regression from Semgrep miss | Eval harness gates on recall; run `legacy` engine side-by-side via the flag during transition |
| Bundle size growth | ~50 MB on a 5.7 GB bundle — negligible |

## 12. Out of scope (named for clarity)
- Fine-tuning Astra on curated vuln data.
- "Find-extras" LSAST variant.
- IDE plugin / pre-commit hook integration.
- Multi-color taint.
- Migrating SBOM/SCA pipeline (it's separate and not the FP problem).
