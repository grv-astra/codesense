# CLAUDE.md — Code Sense LSAST handoff context

You are picking up work on **Code Sense** (`yacm`), an **offline** SAST desktop app. Read
`docs/handoff/00-SESSION-NARRATIVE.md` (what was done) and `docs/handoff/02-NEXT-STEPS.md` (what's next)
before acting (full developer onboarding: `docs/handoff/onboarding.md`). This file is the quick orientation.

## Current roadmap position
- The 12-week plan lives in `docs/superpowers/plans/2026-05-31-codesense-12week-roadmap-README.md`
  (index) with the design spec in `docs/superpowers/specs/2026-05-31-codesense-12week-roadmap-design.md`
  and per-phase plans (`...-phase1/2/3.md`) alongside the README. Execution model: one session per week,
  context reset between; each week ends with its acceptance test green + docs updated + next-week brief.
- **Position: Week 1 DONE (2026-06-10), pre-Week-2.** Environment reconstituted (repo from bundle,
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
- **The bundled LLM is weak.** `astra.gguf` is a **Qwen2.5-Coder-3B fill-in-the-middle (FIM)** model, not
  instruction-tuned: the verifier can't emit `FP` (rubber-stamps `TP`) and the report enricher only parses
  ~34% of the time (rest fail-open). Both are model-bound — the fix is the **instruction-tuned model swap**
  in `docs/instruction-tuned-model-swap-scope.md`. **⚠️ That same 3B is under a NON-COMMERCIAL license —
  see §9.1; treat moving off it as urgent.**
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

## Next-week brief — Week 2: License-safe model behind a flag

**Goal:** an Apache-licensed instruction-tuned model converts to GGUF, is selectable behind a flag, loads,
and serves — with legacy (FIM) behavior unchanged when the flag is off. **Milestone: compliance blocker
resolved.** Plan: `docs/superpowers/plans/2026-05-31-codesense-12week-roadmap-phase1.md` (Week 2). Acceptance:
with `LLM_MODEL_MODE=instruct` + the instruct GGUF, a chat round-trip integration test passes; with the
default (`fim`), `test_semgrep_detector`/verifier tests are unchanged.

**Tasks (TDD, exact files in the plan):**
1. **2.1 — add the flag (no behavior change):** add `model_mode()` to `server/scanner/rag/llm.py`
   (`"instruct"` iff `LLM_MODEL_MODE=instruct`, else `"fim"`); test `server/scanner/tests/test_llm_mode.py`.
   This is the only code change that lands in the repo this week — it must be a true no-op for the FIM path.
2. **2.2 — convert + verify the GGUF (build-host task):** `Qwen/Qwen2.5-Coder-7B-Instruct` (Apache-2.0) →
   GGUF Q4_K_M via `scripts/offline_ai/convert_model_to_gguf.sh`; confirm `llama-server` serves it and
   `/v1/models` returns the id. Document in `scripts/offline_ai/README-model-swap.md` (per-tier variants:
   1.5B Q5_K_M / 7B Q4_K_M / 14B Q4_K_M; build stages the chosen GGUF as `resources/model/astra.gguf`).
3. **2.3 — gated round-trip test:** `server/scanner/tests/test_llm_integration.py`, skipped unless
   `LLM_LIVE_TEST=1` with a running server.

**Windows / this-environment notes for W2:**
- The model is **not staged locally** and there is no GPU build host here, so 2.2 (HF download + GGUF
  convert, networked) and the live 2.3 round-trip will be **deferred/documented** — land 2.1 (the flag, fully
  testable offline) + 2.2's docs/script, and write the gated 2.3 test (skips without `LLM_LIVE_TEST=1`).
  Carry the live-serve verification + the `instruct` baseline into W3/W4 when a server is available.
- Use `server\.venv\Scripts\python.exe manage.py test scanner` (Windows venv). For any eval/script that
  prints to the console, set `PYTHONUTF8=1` (cp1252 chokes on the harness's ✅/❌/em-dash output).
- Keep the **characterization snapshot green** — W2 must not touch the detector; if `test_characterization`
  changes, something regressed.
- The pre-existing `scripts/eval/tests/test_owasp.py` POSIX-path failure is still open (out of W2 scope).
