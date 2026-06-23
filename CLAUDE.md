# CLAUDE.md — Code Sense LSAST handoff context

You are picking up work on **Code Sense** (`yacm`), an **offline** SAST desktop app. Read
`docs/handoff/00-SESSION-NARRATIVE.md` (what was done) and `docs/handoff/02-NEXT-STEPS.md` (what's next)
before acting (full developer onboarding: `docs/handoff/onboarding.md`). This file is the quick orientation.

## Current roadmap position
- The 12-week plan lives in `docs/superpowers/plans/2026-05-31-codesense-12week-roadmap-README.md`
  (index) with the design spec in `docs/superpowers/specs/2026-05-31-codesense-12week-roadmap-design.md`
  and per-phase plans (`...-phase1/2/3.md`) alongside the README. Execution model: one session per week,
  context reset between; each week ends with its acceptance test green + docs updated + next-week brief.
- **Position: PHASE 1 COMPLETE (W1–W5, 2026-06-23). Pre-Phase-2 (W6).** Milestone "LLM quality fixed"
  reached. Branch `week5-enrichment-tiers` (off `week4-verifier-accuracy`, committed locally, NOT pushed).
  Scanner suite **132 pass / 2 skip**; characterization snapshot green throughout. Phase 1 summary:
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

## Next-week brief — Week 6: Parallelize verifier + reporter calls (Phase 2 start)

**Goal:** cut scan wall-time by parallelizing the per-finding LLM calls (verify + enrich) in
`server/scanner/rag/lsast_scanner.py` with **bounded** concurrency, producing **identical findings** to the
serial path. **Acceptance:** DVB (or a fixed corpus) wall-time ↓ ≥40% vs the W1 reference; finding set
byte-identical to serial. Plan: `docs/superpowers/plans/2026-05-31-codesense-12week-roadmap-phase2.md` (Week 6).

**Tasks (TDD):**
1. **6.1 — bounded-concurrency executor** over the per-finding loop (lines ~56–112 of `lsast_scanner.py`):
   `verify()` + `generate_report()` run concurrently across findings with a small worker cap (the local
   `llama-server` serializes anyway — cap to its slot count, env-tunable). Persist/progress stay correct
   under concurrency (currently incremental `save_findings_to_db` + `update_progress` inside the loop).
2. **6.2 — order/identity test:** results must equal the serial pipeline regardless of completion order
   (sort before compare); a test asserts the same visible/filtered partition and field values.
3. **6.3 — measure** wall-time before/after on a fixed corpus; record "W6 — scan wall-time" + per-finding
   LLM latency in `metrics/scorecard.md` (the W1 540s p50 + `N/A` latency rows).

**Environment notes (carry forward):**
- Local model server is in **`astra-model-host/`** (sibling of `yacm/`): start it first (see the LLM note
  above); it's CPU-only and serializes requests, so "concurrency" mostly overlaps detector/normalize work
  with in-flight LLM calls — measure honestly, don't claim 40% if the bottleneck is the single CPU slot.
- Tests: `server\.venv\Scripts\python.exe manage.py test scanner` with `PYTHONUTF8=1` +
  `SEMGREP_BIN`/`SEMGREP_RULES_DIR` = `yacm\dist\tools\windows\semgrep.exe` / `yacm\dist\semgrep-rules`.
  Suite is **132 pass / 2 skip**; keep the **characterization snapshot green** (W6 must not touch the detector).
- `.env` `load_dotenv` is `override=False` — a stray shell `VLLM_BASE_URL` wins; use a clean shell.
- Branch: cut W6 off `week5-enrichment-tiers` (it has the full Phase-1 stack). **Do NOT push to frozen
  production `lsast-handoff-2026-05-31` without explicit OK.**
- Still open (pre-existing): `scripts/eval/tests/test_owasp.py` POSIX-path failure (out of scope).
