# CLAUDE.md — Code Sense LSAST handoff context

You are picking up work on **Code Sense** (`yacm`), an **offline** SAST desktop app. Read
`docs/handoff/00-SESSION-NARRATIVE.md` (what was done) and `docs/handoff/02-NEXT-STEPS.md` (what's next)
before acting (full developer onboarding: `docs/handoff/onboarding.md`). This file is the quick orientation.

## Current roadmap position
- The 12-week plan lives in `docs/superpowers/plans/2026-05-31-codesense-12week-roadmap-README.md`
  (index) with the design spec in `docs/superpowers/specs/2026-05-31-codesense-12week-roadmap-design.md`
  and per-phase plans (`...-phase1/2/3.md`) alongside the README. Execution model: one session per week,
  context reset between; each week ends with its acceptance test green + docs updated + next-week brief.
- **Position: pre-Week-1.** Environment is reconstituted (repo cloned from bundle, `server/.venv` built,
  scanner suite 91/91 on Windows). Week 1 = "Baselines + characterization lock" (1.1 characterization test,
  1.2 scorecard + baseline) writing into `metrics/` and `scripts/eval/tests/` — not started yet.
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
  (`cd server && .venv/bin/python manage.py test scanner` → 91 passing). Use the project venv
  (`server/.venv`), not system python (Django/DRF needed).
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
