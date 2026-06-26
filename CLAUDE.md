# CLAUDE.md — Code Sense LSAST handoff context

You are picking up work on **Code Sense** (`yacm`), an **offline** SAST desktop app. Read
`docs/handoff/00-SESSION-NARRATIVE.md` (what was done) and `docs/handoff/02-NEXT-STEPS.md` (what's next)
before acting (full developer onboarding: `docs/handoff/onboarding.md`). This file is the quick orientation.

## Current roadmap position
- The 12-week plan lives in `docs/superpowers/plans/2026-05-31-codesense-12week-roadmap-README.md`
  (index) with the design spec in `docs/superpowers/specs/2026-05-31-codesense-12week-roadmap-design.md`
  and per-phase plans (`...-phase1/2/3.md`) alongside the README. Execution model: one session per week,
  context reset between; each week ends with its acceptance test green + docs updated + next-week brief.
- **Position: PHASE 2 BACKEND DONE (W6–W8, 2026-06-25), on branch `week6` (off production tip
  `72b2de5`, committed locally, NOT pushed).** Batch A complete: W6 parallelized the per-finding
  LLM work (bounded `ThreadPoolExecutor`, `LSAST_MAX_WORKERS`, identical findings — wall-time
  ≥40% **pending a live model host**, CPU-serialized 7B caps real speedup); W7 persists + exposes
  `rule_id`/`confidence`/`verifier_reason` (migration `0002`); W8 added the detector-recall CI gate
  (`.github/workflows/lsast-eval-gate.yml`) + grew curated to **5 languages** (added go/php/ruby,
  10 cases, F1/recall 1.000, FP 0.000). See `metrics/scorecard.md` W6/W7/W8.
- **Position: PHASE 3 STARTED — W9 DONE (2026-06-26), on branch `week6`** (same branch as Batch A,
  committed locally, NOT pushed). W9 expanded language coverage: registry routing **lock** for
  go/ruby/csharp/kotlin (all already in the top-40 table — `test_languages.py`, 10 unit tests) +
  curated eval grown **5→7 languages** (added C# SQLi + Kotlin cmd-injection pairs; detector
  F1/recall **1.000**, FP **0.000**, TP=7/FP=0/FN=0/TN=7; new langs csharp/kotlin recall **1.000**).
  Suite **scanner+local.api_app 165 pass / 2 skip + 6 curated eval tests**; characterization
  snapshot green. See `metrics/scorecard.md` W9. **Next: W10 (finding-details UX — frontend).**
- **Phase 1 (W1–W5, COMPLETE 2026-06-23)** — milestone "LLM quality fixed". Branch
  `week5-enrichment-tiers`, **merged into production `72b2de5`** this cycle. Phase 1 summary:
  - **W2 — license-safe instruct model** ✅ (branch `week2-instruct-model`, pushed, no PR): `model_mode()`
    flag (`LLM_MODEL_MODE=instruct`); the bundled GGUF is now **Qwen2.5-Coder-7B-Instruct Q4_K_M
    (Apache-2.0)** — non-commercial-license blocker RESOLVED. FIM path byte-for-byte unchanged when the
    flag is off.
  - **W3 — instruct/JSON path** ✅ (shipped in the W2 branch): `VLLMClient.invoke()` instruct branch +
    `response_format:{type:json_object}` wired from verifier & enricher; A/B-validated in W4.
  - **W4 — verifier discriminates** ✅ (branch `week4-verifier-accuracy`, pushed, no PR): FP-default
    verifier prompt (TP/FP semantics), CWE-94→78 OS-command fix, finding de-dup, class-specific CVSS.
    Proven on DVWA shapes (safe→FP, unsafe→TP). Curated Tier-2 = 1.000 but trivial (detector flags 0 safe
    cases, so FP-suppression unexercised — see scorecard W4 caveat).
  - **W5 — enrichment quality + device-tier config** ✅ (branch `week5-enrichment-tiers`):
    enrichment **parse-rate 1.00 (10/10)** on a fixed 10-finding set via the live 7B (W1 baseline 0.34);
    `server/scanner/rag/model_tiers.py` maps `MODEL_TIER` low/mid/high → 1.5B/7B/14B GGUF (tested-but-
    unwired; only 7B staged locally). Caveat: 3 eval/CWE-95 findings get a title mislabeled "OS Command
    Injection" (number correct, body correct) — candidate prompt fix, not applied (measurement week).
  - **Open / carried to later weeks:** fusion high-sev-FP policy (keep `needs_review[verifier:FP]` vs
    suppress) → **W8**; grow curated with real detector-FP cases + `run_eval.py --tier verifier` → **W8**;
    the W5 enrichment title-mislabel one-line prompt fix; PR strategy for the stacked W2→W4→W5 branches
    (nothing merges to frozen prod). **Production `lsast-handoff-2026-05-31` is LIVE on Railway — do NOT
    push to it without explicit OK; it runs the legacy FIM path (`LLM_MODEL_MODE` unset).**

- **Historical — W1 (2026-06-10):** Environment reconstituted (repo from bundle,
  `server/.venv` built). W1 delivered both tasks:
  - **1.1 — characterization lock** pins the detector→normalize→derive_cwe output on a fixed fixture
    (`server/scanner/tests/fixtures/characterization/{app.py,Dockerfile}`) via
    `server/scanner/tests/test_characterization.py`. Locks the **exact** 4-finding snapshot
    (`dockerfile-source-not-pinned`→CWE-710, `missing-user`→CWE-250, `tainted-sql-string`→CWE-915,
    `sqlalchemy-execute-raw-query`→CWE-89). Gated on `SEMGREP_BIN`+`SEMGREP_RULES_DIR` (skips without the
    engine). Scanner suite now **94/94 green** on Windows (was 91).
  - **1.2 — scorecard** renderer `scripts/eval/scorecard.py` (+ `scripts/eval/tests/test_scorecard.py`,
    3 green) and the W1 baseline in `metrics/scorecard.md`: detector **F1 1.000 / FP 0.000** (curated,
    N=4, measured this session — `scripts/eval/results/20260610T063827Z.md`); verifier FP-suppression
    **0.000** and enrichment parse-rate **0.34** (carried from the W0 audit in `scripts/eval/BASELINE.md`,
    not re-measurable locally since the LLM fails open); signed-build **False**; app size **5.7 GB**.
  - **⚠️ Windows/git gotcha (new):** OpenGrep's directory walker enumerates **0 files** for any subdir
    *inside a git working tree* (single-file targets are unaffected). The characterization test therefore
    copies its fixture to a temp dir before scanning; the curated eval works because its cases are
    single-file `source_path`s. `run_eval.py`'s final `print(md)` also crashes on the ✅ emoji under the
    cp1252 console — set `PYTHONUTF8=1` or read the written `results/*.md` (the numbers are saved before
    the print).
  - **Pre-existing failing test (out of scope, flagged):** `scripts/eval/tests/test_owasp.py` has a POSIX
    path assertion (`/benchmark/src` vs Windows `\benchmark\src`) — 1 failure in the eval suite, unrelated
    to W1.
- **Note:** `astra.gguf` is NOT present locally, so the LLM stages **fail open** (findings preserved as
  low-confidence TP, enrichment skipped) until a model is staged at
  `client/src-tauri/resources/model/astra.gguf` **or** `VLLM_BASE_URL` points at a running `llama-server`;
  roadmap **W2** produces the license-clean replacement.

## Architecture (what you're working in)
- **LSAST** is the only scan pipeline:
  `detector (Semgrep/OpenGrep) → finding_normalizer → llm_verifier (TP/FP) → fusion → [report_enricher] → persist`.
  Code lives in `server/scanner/rag/`.
- Django backend is **frozen with PyInstaller** as `codesense-server` and run by a **Tauri** shell
  (`client/src-tauri/src/main.rs`). A bundled **`llama-server`** serves a quantized GGUF on
  `127.0.0.1:8001`; the client talks to it via `VLLMClient` in `server/scanner/rag/llm.py`
  (env `VLLM_BASE_URL`, `VLLM_MODEL=astra-code-reviewer`).
- The SAST engine binary is **OpenGrep** (an OSS Semgrep fork), bundled as `resources/tools/semgrep`;
  rules are staged into `resources/semgrep-rules` by `scripts/offline_sbom/stage_semgrep_rules.py`.
- Everything ships **offline** — no network at runtime.

## Ground truth & gotchas (learned this session)
- **The app runs the *frozen* backend**, not your source. To see backend changes live you must re-freeze
  (`cd server && .venv/bin/pyinstaller codesense.spec --noconfirm --clean`) and either rebuild the app or
  swap `dist/codesense-server` into `Code Sense.app/Contents/MacOS/` + `codesign --force --deep --sign -`
  (the app is adhoc-signed). The narrative documents this loop.
- **OpenGrep ≠ Semgrep** in three ways the code now handles: it rejects `--metrics`; it needs a UTF-8
  locale (`PYTHONUTF8`/`LC_ALL=C.UTF-8`) or it crashes on rule files; and its `dataflow_trace` JSON is an
  OCaml tagged-tuple `["CliLoc",[loc,code]]`, not a list of dicts. See `semgrep_detector.py`.
- **The LLM was weak; FIXED in Phase 1 (W2–W5).** The original `astra.gguf` was a **Qwen2.5-Coder-3B
  fill-in-the-middle (FIM)** model under a **NON-COMMERCIAL license** — it couldn't emit `FP` (rubber-
  stamped `TP`) and the enricher parsed only ~34%. Replaced by **Qwen2.5-Coder-7B-Instruct Q4_K_M
  (Apache-2.0)** behind `LLM_MODEL_MODE=instruct`; with the W4 verifier-prompt fix it discriminates
  TP/FP, and W5 enrichment parses 10/10. The local server lives in `astra-model-host/` (sibling of
  `yacm/`, not inside it): `astra-model-host\model\astra-Q4_K_M.gguf` is the 7B; serve with
  `.\bin\llama-server.exe --model .\model\astra-Q4_K_M.gguf --host 127.0.0.1 --port 8001 --ctx-size 8192
  --api-key <key> --alias astra-code-reviewer --jinja`. **Default (no `LLM_MODEL_MODE`) is still the FIM
  path** — frozen prod runs it.
- **Finding fields:** `title` = Semgrep rule name (e.g. `sequelize-raw-query`); `description`/`security_risk`
  = Semgrep message (or LLM-authored if enrichment succeeded); `mitigation` = LLM remediation or empty.
  `cwe`/`severity`/`file_path` are **deterministic** — never let the LLM author them.
- `FindingModel.insert_many` **drops keys not in the model** (e.g. `affected`, `lines`, `confidence`,
  `verifier_reason`) — don't rely on those persisting without a migration.

## Conventions
- **TDD** — there are unit tests for every change under `server/scanner/tests/`; keep them green
  (`cd server && .venv/bin/python manage.py test scanner` → **94 passing** as of W1; Windows:
  `server\.venv\Scripts\python.exe manage.py test scanner`, and set `SEMGREP_BIN`+`SEMGREP_RULES_DIR`
  — e.g. via `server\run_dev.ps1`'s env — for the characterization tests to run rather than skip). Use the
  project venv (`server/.venv`), not system python (Django/DRF needed).
- The eval harness lives in `scripts/eval/` (dev-host only, never bundled). `scripts/eval/BASELINE.md`
  records the detector baseline + the verifier audit.
- Don't commit build artifacts, `.gguf` models, or the `semgrep-rules` tree.

## How to apply this handoff
The handoff is **already applied** — this checkout was cloned from `codesense-repo.bundle` and includes the
handoff commit (`003af6f`) on branch `lsast-handoff-2026-05-31` (the roadmap was authored against `main`;
the branch is 1 commit / clean fast-forward ahead of `origin/main`). The original `codesense-changes.patch`
and `code/<path>` overlay from the handoff package are therefore no longer needed. Read
`docs/handoff/02-NEXT-STEPS.md` and pick up at item #2 (the model swap) — the highest-leverage remaining
work — while #1 (model license) is the urgent compliance item. The 12-week roadmap (see **Current roadmap
position** above) sequences this work starting at Week 1.

## Phase 2 (W6–W8) — DONE on branch `week6` (committed locally, NOT pushed)

- **W6 — parallelize verifier+reporter** ✅ `_process_one()` (normalize→verify→fuse→enrich, no DB I/O)
  runs across findings in a bounded `ThreadPoolExecutor` capped by `LSAST_MAX_WORKERS` (default 4; 1 =
  serial). `ex.map` preserves order; persist/progress stay on the main thread → finding set identical to
  serial (unit-proven over all 4 fuse branches + a `Barrier(3)` overlap test). **Wall-time ≥40% is PENDING
  a live model host** — the local 7B is CPU-only and serializes inference (~40s/call), so real speedup is
  capped at the single CPU slot; measure on the infra box, don't claim 40% locally (scorecard W6).
- **W7 — persist + expose verdict metadata** ✅ `rule_id`/`confidence`/`verifier_reason` were dropped by
  `FindingModel._FIELDS`; now persisted via migration `0002` (3 nullable/blank cols, back-compat) +
  returned by `FindingModel.serialize` (the findings API). `normalize()` sets `rule_id`; `fuse()` writes
  the verdict pair. DB round-trip tested.
- **W8 — eval CI gate + grow curated** ✅ `.github/workflows/lsast-eval-gate.yml` runs
  `run_eval.py --dataset curated --tier detector --gate` (exits non-zero below §9 thresholds). Curated
  grown 2→**5 languages** (added go cmd-inj, php/ruby SQLi; 10 cases, F1/recall 1.000, FP 0.000). Gate
  regression proven locally (empty rules dir → recall 0 → exit 1). **CI not yet run on a GitHub runner**
  (real Semgrep + upstream rules vs local OpenGrep + bundled rules — fidelity caveat in the workflow).

Suite: **scanner+api_app 164 pass / 2 skip** + 5 curated eval tests; characterization snapshot green.

## Phase 3 — W9 DONE on branch `week6` (committed locally, NOT pushed)

- **W9 — language-coverage expansion** ✅ Detector/registry/eval work, **no model needed**.
  - **W9.1 — registry routing lock.** The top-40 table in `server/scanner/rag/languages.py` already
    contained go/ruby/csharp/kotlin, so this is a **lock**, not new entries: `test_languages.py`
    (10 unit tests) asserts the four W9 langs route (incl. `.kts`, case-insensitive) + carry a real
    Semgrep analyzer at `strong` tier, extensions are unique, coverage ∈ {strong,partial,none}, and
    `none`-tier ⇔ no analyzer.
  - **W9.2 — per-language detector eval.** Curated grown **5→7 languages** (added **C#** SQLi via the
    taint-mode `csharp-sqli` rule, CWE-89; **Kotlin** cmd-injection via the pattern-based
    `command-injection-formatted-runtime-call`, CWE-78). Each is one real + one safe fixture; safe
    variants yield **0 findings** (true TNs). Full gate `run_eval.py --dataset curated --tier detector
    --gate` → **PASS** (F1/recall 1.000, FP 0.000, TP=7/FP=0/FN=0/TN=7); per-language recall **1.000**
    for all 7 langs incl. the new csharp/kotlin. Manifest CWE = **raw** rule output (matcher gotcha:
    eval skips `normalize`/`derive_cwe`). See `metrics/scorecard.md` W9.

Suite: **scanner+local.api_app 165 pass / 2 skip** + 6 curated eval tests; characterization green.

## Next-week brief — Week 10: Finding-details UX overhaul (consumes the W7 API fields)

**Goal:** the finding-details view surfaces the verifier confidence + reason, the LLM remediation, the
dataflow, a CWE reference link, and severity — degrading gracefully for fail-open findings with empty
fields. **Acceptance:** the details component renders all fields for a real scan finding and renders
nothing broken when a field is empty; a component render test passes. Plan:
`docs/superpowers/plans/...-phase3.md` (Week 10, ~line 68). **This is frontend work (React/TS), not backend.**

**Tasks (TDD):**
1. **10.1 — extend the finding type** in `client/src/types/finding.ts`: add optional
   `rule_id?: string`, `confidence?: number | null`, `verifier_reason?: string` (the W7 API now returns
   these via `FindingModel.serialize`). Typecheck: `cd client && npx tsc --noEmit` → no new errors.
2. **10.2 — render them** in `client/src/components/update/UpdatedFinding.tsx`: add a **Remediation**
   block (`finding.mitigation`, only if non-empty), an **Impact** block (`finding.security_risk`), a
   **Verifier** block (confidence as a % + `verifier_reason`, only if `confidence != null`), and a **CWE
   link** (`https://cwe.mitre.org/data/definitions/<n>.html` from `finding.cwe`). Guard each with a truthy
   check so empty fields render nothing. Write/extend a vitest+RTL render test (see plan ~line 88 for the
   exact test shape) — assert remediation + CWE link + confidence show when present, and the component
   renders without crashing when `confidence`/`verifier_reason`/`mitigation` are undefined.

**Environment notes (carry forward):**
- W10 is **frontend** (`client/`, React/TS + Tauri). Backend/model untouched — no llama-server,
  no Semgrep. Use the `client/` test setup (vitest/RTL; add a minimal vitest test if none exists).
- The W7 fields are live in the API (`rule_id`/`confidence`/`verifier_reason`, migration `0002`,
  `FindingModel.serialize`) — W10 just consumes them. `cwe`/`severity`/`file_path` stay deterministic.
- Branch: continue on `week6` (or cut `week10` off it). **Do NOT push to frozen production
  `lsast-handoff-2026-05-31` without explicit OK.**
- ⚠️ Backend reminder if you re-run the eval: **OpenGrep ~85s/scan, rule-load bound** — a full 14-case
  curated detector run is ~20 min; per-file probing validates new fixtures fast. Combined backend suite
  is `manage.py test scanner local.api_app` (the app label is **`local.api_app`**, not `api_app`).
- Still open (pre-existing): `scripts/eval/tests/test_owasp.py` POSIX-path failure (out of scope).
- **W6 carry:** the ≥40% wall-time number is still owed — run it on the infra box once the 7B host is up.
