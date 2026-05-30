# Code Sense — Phase 2: LSAST Eval Harness + Top-40 Language Coverage

- **Date:** 2026-05-31
- **Status:** Approved design (pre-implementation)
- **Repo:** `yacm` (Code Sense), branch `main`
- **Builds on:** `2026-05-29-sast-accuracy-lsast-redesign-design.md` (the LSAST pipeline, now the sole engine)

## 1. Problem & goals

Two related Phase-2 goals:

**A. Eval harness** — measure the LSAST scanner (Semgrep detector + Astra verifier + fusion) against the acceptance criteria so the already-live `lsast` default is *validated*, not assumed, and so rule/prompt tuning has a feedback loop:
- **F1 ≥ 0.70**, **FP rate ≤ 25%**, **recall ≥ 0.60** (per the LSAST spec §9).

**B. Top-40 language coverage** — make the pipeline handle the top 40 programming languages end-to-end: correct extension→language routing, bundled Semgrep rules for every language Semgrep supports, and graceful, clearly-reported no-op for languages it doesn't. The eval harness measures per-language coverage so the claim is empirical.

### Honest scope of "40-language support"
SAST *detection* depends on Semgrep/OpenGrep's parser + security rules. Reality:
- **Strong rule coverage (~12–15):** Python, JavaScript, TypeScript, Java, Go, Ruby, PHP, C, C++, C#, Kotlin, Scala, Rust, Swift.
- **Partial coverage (parser + some rules):** Bash/Shell, Terraform, Dockerfile, YAML/JSON configs, Lua, OCaml, Elixir, Clojure, Julia, R, Solidity (via plugins), Generic-mode patterns.
- **Routing-only (no Semgrep parser/rules):** the long tail (e.g., COBOL, Fortran, Assembly, VBA, Perl in some versions, Haskell, Erlang). For these the pipeline routes the file, finds nothing via Semgrep, and **reports "no analyzer coverage"** rather than silently implying "clean."

So "support for 40 languages" = **the registry + routing + bundled rules + graceful degradation for all 40**, with detection quality bounded by and *measured* per-language. True deep SAST for the routing-only tail would require additional engines (CodeQL, language linters) — out of scope, flagged as a future initiative.

## 2. Part B — Top-40 language registry & routing

**New:** `server/scanner/rag/languages.py` — a single source of truth:
```python
@dataclass(frozen=True)
class Language:
    name: str            # canonical, e.g. "python"
    extensions: tuple    # (".py", ".pyi", ...)
    semgrep_lang: str|None   # Semgrep lang id, or None if unsupported
    coverage: str        # "strong" | "partial" | "none"

LANGUAGES: list[Language]  # the top ~40 (TIOBE/GitHub blend), see appendix
```
- **`language_for_path(path) -> Language`** replaces the inline `_language_from_path` dict in `lsast_scanner.py`. Returns the registry entry (or an `UNKNOWN` sentinel with coverage="none").
- `lsast_scan_folder` uses `language_for_path(...).name` for the verifier's `language` arg (unchanged behavior, broader coverage).
- The detector already hands the whole folder to Semgrep, which auto-detects languages from the bundled rules — so adding languages is about (a) routing/labeling and (b) ensuring rules are bundled (Part of build: the `semgrep-rules` clone already carries all Semgrep-supported languages).
- **Coverage reporting:** a finding/scan can note when files were in `coverage="none"` languages (so a scan over COBOL doesn't read as "clean — no vulns" when it's really "not analyzed"). Minimal Phase-2 surfacing: a `log.info` + an optional `scan.metrics["unanalyzed_languages"]` list; full UI surfacing is follow-on.

**The top-40 list** is enumerated explicitly in the spec appendix and in `languages.py` (name, extensions, semgrep id, coverage tier), so it's reviewable and testable.

## 3. Part A — Eval harness architecture (two-tier)

Dev-host-only, under `scripts/eval/` — **never bundled / shipped / added to `codesense.spec`**.

```
datasets ─▶ Tier 1 (deterministic, full):  Semgrep over every case → match to
           │   ground truth → detector precision/recall/F1   [fast, CI-gateable]
           └▶ Tier 2 (sampled, cached):     balanced sample of findings → Astra
               verifier → TP/FP accuracy   [slow, manual; needs llama-server]
                          │
                          ▼
              combine → end-to-end F1 estimate + FP rate → report + PASS/FAIL gate
```

### Components (`scripts/eval/`)
| File | Responsibility |
|---|---|
| `datasets/owasp_benchmark.py` | Fetch/locate OWASP Benchmark; parse `expectedresults-*.csv` → `(case_id, source_path, is_real, cwe)`. |
| `datasets/curated.py` | Load `scripts/eval/data/curated/manifest.yml` — labeled multi-language snippets (`file, lines, cwe, label`). Doubles as the FP-rate set **and** the multi-language coverage probe (Part B). |
| `matching.py` | Map a finding (`file_path "<path> [s,e]"`, `cwe`, `lines`) to a case. OWASP = per-test-case granularity; curated = file + overlapping line-range + CWE family. Holds the OWASP-category↔CWE↔Semgrep-CWE table. |
| `runner.py` | Tier 1 (`run_semgrep` over sources → match → detector metrics) and Tier 2 (balanced stratified sample → `verify` → verdicts cached in `scripts/eval/.cache/` keyed by `(cwe, sha1(code))`). |
| `metrics.py` | TP/FP/FN/TN, precision, recall, F1, FP-rate; per-CWE **and per-language** breakdown; vs thresholds. |
| `report.py` | Markdown + JSON → `scripts/eval/results/<UTC-date>.md`; PASS/FAIL summary; per-language coverage table (ties Part A↔B). |
| `run_eval.py` | CLI: `--tier {detector,verifier,all}`, `--dataset {owasp,curated,all}`, `--sample-size N`, `--gate`. |

It imports the **real** scanner modules (`scanner.rag.semgrep_detector.run_semgrep`, `scanner.rag.llm_verifier.verify`, `scanner.rag.finding_normalizer`, `scanner.rag.languages`) so it tests the live pipeline.

### Ground truth & scoring
OWASP ships machine-checkable truth (`expectedresults.csv`: real/fake + category). Score per case: real-flagged=TP, fake-flagged=FP, real-missed=FN, fake-clean=TN → detector P/R/F1. Curated set is line-labeled by us for precise FP measurement and per-language coverage.

### Verifier cost (the feasibility lever)
Tier 1 is deterministic and runs over everything (no LLM). Tier 2 runs the verifier only on a **balanced, CWE-stratified sample** (default ~200 real-region + ~200 safe-region findings), with verdicts **cached** by `(cwe, sha1(code))` so prompt-unchanged re-runs are instant. End-to-end F1 is *estimated* by composing detector recall with sampled verifier precision.

## 4. CI vs manual
- **CI:** Tier 1 detector metrics on the **curated set only** (small, deterministic, no network, no LLM) → fails the build if curated detector recall drops below a floor. Cheap regression guard; also guards the language registry (curated set spans many of the 40 languages).
- **Manual/scheduled:** full OWASP Tier 1 + sampled Tier 2 (needs network once + llama-server) → the headline report. Documented in `scripts/eval/README.md`.

## 5. Testing
Unit-test the deterministic, bug-prone parts with tiny fixtures (no LLM, no network):
- `languages.py` — extension→language resolution, coverage tiers, the 40-entry table is well-formed (unique extensions, valid semgrep ids).
- `matching.py` — a finding correctly matched/missed against a known case; CWE-family mapping.
- `metrics.py` — P/R/F1/FP math on hand-computed cases.
- dataset adapters — a tiny fixture CSV + manifest.

## 6. Deliverables & flow
1. **Part B:** `languages.py` + registry + wire `lsast_scanner` to it + tests. (Broadens routing immediately; small, ships with the scanner.)
2. **Part A:** the `scripts/eval/` harness + tests.
3. **Run once:** produce a **baseline report** — real F1/FP/recall on OWASP + curated, plus the per-language coverage table.
4. The baseline drives follow-on tuning (rule curation, prompt) — **that tuning is out of scope here**; this plan builds the harness + registry and produces the baseline.

## 7. Risks & honesty
| Risk | Handling |
|---|---|
| "40 languages" over-claims SAST quality | Registry tags coverage tier; eval reports per-language empirically; routing-only langs reported as "no analyzer coverage", never "clean". |
| OWASP Java rule coverage in our bundle is weak → low F1 | That's a *real finding* the baseline surfaces → drives rule curation (follow-on). The harness's job is to measure it, not hide it. |
| Verifier too slow over full benchmark | Two-tier + sampling + caching (§3). |
| Eval code accidentally bundled into the offline app | Lives in `scripts/eval/`, excluded from `codesense.spec`; a test asserts the spec doesn't reference it. |

## 8. Out of scope
Auto-tuning; a results dashboard; Juliet/SARD; additional analysis engines (CodeQL etc.) for the routing-only language tail; the actual rule/prompt tuning iterations (driven by the baseline, separately).

## Appendix — Top-40 languages (initial registry)
Python, JavaScript, TypeScript, Java, C, C++, C#, Go, Rust, Ruby, PHP, Swift, Kotlin, Scala, Dart, R, Perl, Lua, Elixir, Erlang, Haskell, Clojure, Objective-C, Groovy, Julia, Shell/Bash, PowerShell, SQL, HTML, Solidity, Terraform/HCL, Dockerfile, YAML, JSON, OCaml, F#, Visual Basic/.NET, COBOL, Fortran, Assembly. (Each entry in `languages.py` carries its extensions, Semgrep lang id or None, and coverage tier strong/partial/none.)
