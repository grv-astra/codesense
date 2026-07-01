# CLAUDE.md — Code Sense LSAST handoff context

You are picking up work on **Code Sense** (`yacm`), an **offline** SAST desktop app. Read
`docs/handoff/00-SESSION-NARRATIVE.md` (what was done) and `docs/handoff/02-NEXT-STEPS.md` (what's next)
before acting (full developer onboarding: `docs/handoff/onboarding.md`). This file is the quick orientation.

## Current roadmap position

> **🏁 ROADMAP COMPLETE — W1–W12 done (W12: 2026-07-01).** All 12 weeks landed on branch `week6`
> (W6–W8 pushed to `origin/week6@2bd8e7c`; W9–W12 are **local-only, NOT pushed** — awaiting OK).
> The closing measurement pass (`metrics/RESULTS.md`) shows **every accuracy axis meets its target**:
> detector F1/recall 1.000 / FP 0.000; verifier Tier-2 F1 1.000 + FP-suppression **0.857** (was
> 0.000); enrichment parse-rate **1.00** (was 0.34); per-finding LLM latency 29.7 s p50. Two
> **infrastructure/procurement gaps** remain (not code/model regressions): the ≥40% scan speed-up
> (needs a multi-slot host — this box serializes on one CPU slot) and a **signed** installer (needs
> certs + clean VMs). See `metrics/RESULTS.md`, `docs/RELEASE-NOTES.md`, and the "Week 12" sections
> below. Suite **169 pass / 2 skip**; eval gate green.

- The 12-week plan lives in `docs/superpowers/plans/2026-05-31-codesense-12week-roadmap-README.md`
  (index) with the design spec in `docs/superpowers/specs/2026-05-31-codesense-12week-roadmap-design.md`
  and per-phase plans (`...-phase1/2/3.md`) alongside the README. Execution model: one session per week,
  context reset between; each week ends with its acceptance test green + docs updated + next-week brief.
- **Position: PHASE 2 BACKEND DONE (W6–W8, 2026-06-25), on branch `week6` (off production tip
  `72b2de5`). W6–W8 ARE pushed — `origin/week6` holds them at `2bd8e7c` (W8). Only the later
  W9/W10 commits are local-only (awaiting push OK).** Batch A complete: W6 parallelized the per-finding
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
  snapshot green. See `metrics/scorecard.md` W9.
- **Position: PHASE 3 — W10 DONE (2026-06-30), on branch `week6`** (local-only, NOT pushed).
  W10 was the finding-details UX overhaul — **frontend only** (React/TS, `client/`), consuming
  the W7 verdict fields. 10.1 extended `FindingDetails` with `rule_id?`/`confidence?: number |
  null`/`verifier_reason?` (commit `e2359fb`); 10.2 rendered a **Verifier Verdict** block
  (confidence %, reason, rule_id — guarded by `confidence != null`), a deterministic **CWE
  Reference** link (`cwe.mitre.org/.../<n>.html`), and guarded the Mitigation block so empty
  fail-open findings degrade gracefully (commit `6deda4c`). Stood up the **client test harness**
  (none existed): vitest + RTL + jsdom, `npm test`. Render test 2/2 pass; `tsc --noEmit` clean.
  ⚠️ Live-scan visual confirmation PENDING (needs the model host). See `metrics/scorecard.md`
  W10. **Next: W11 (signed/notarized installer — BLOCKED on code-signing certs + a build host).**
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

## Phase 3 — W10 DONE on branch `week6` (committed locally, NOT pushed)

- **W10 — finding-details UX overhaul** ✅ **Frontend only** (React/TS, `client/`); consumes the
  W7 verdict fields, no backend/model/Semgrep work.
  - **10.1 — extend the finding type** (`client/src/types/finding.ts`, commit `e2359fb`): added
    optional `rule_id?: string`, `confidence?: number | null`, `verifier_reason?: string`.
    `confidence` is `number | null` (not `number`) to preserve fail-open/pre-W7 nulls — the
    serializer leaves them null, never coalesced. `tsc --noEmit` clean.
  - **10.2 — render them** (`client/src/components/update/UpdatedFinding.tsx`, commit `6deda4c`):
    a **Verifier Verdict** block (confidence as a rounded `%` + `verifier_reason` + `rule_id`,
    guarded by `confidence != null` so fail-open null/undefined renders nothing); a deterministic
    **CWE Reference** link (`https://cwe.mitre.org/data/definitions/<n>.html`, `<n>` regex-extracted
    from `finding.cwe`); and the existing **Mitigation** (remediation) block now guarded by truthy
    `finding.mitigation` so empty fail-open findings degrade gracefully. (Impact/Description/dataflow
    `flow_diagram`/severity already existed in this component.)
  - **Test harness stood up from scratch** — `client/` had no runner. Added `vitest` +
    `@testing-library/react`/`jest-dom`/`dom` + `jsdom` devDeps, a jsdom `test` block in
    `vite.config.ts` (`src/test/setup.ts`), and a `"test": "vitest run"` script.
    `UpdatedFinding.test.tsx` (TDD, RED→GREEN) asserts remediation + confidence `%` + verifier
    reason + the CWE **link** when present, and no crash when the verdict fields are empty. **2/2
    pass**; `tsc --noEmit` clean. See `metrics/scorecard.md` W10.
  - ⚠️ **Live-scan visual confirmation PENDING** (plan step 10.2.5) — needs the 7B host + a real
    scan to eyeball the new blocks; not run this session (model host down, frontend-only week).

## Phase 3 — W11 DONE on branch `week6` (committed locally, NOT pushed) — 2026-06-30

**W11 — signed/notarized distribution build.** Packaging/build week (no backend/frontend feature
code). **Scope this session was deliberately scripts + docs + an *unsigned on-host build attempt*:**
the user confirmed **no Apple cert, no Windows code-signing cert, and no clean test VM** — only this
Windows 11 box as a build host. So the signing/notarization is **wired behind cred-presence checks**
but **no signed artifact and no clean-VM install→scan acceptance was produced** (both remain owed,
blocked on procurement).

- **W11.1 launcher wiring** (`client/src-tauri/src/main.rs`): `spawn_backend` now sets
  **`LLM_MODEL_MODE=instruct`** alongside `VLLM_MODEL` — the shipped app was defaulting to the legacy
  **FIM** path; it now runs the instruct verifier/enricher JSON path. `spawn_llama` prepends a staged
  **`resources/llama-runtime`** dir to the child `PATH` (`#[cfg(target_os = "windows")]`) so the thin
  ~9 KB `llama-server.exe` launcher resolves its sibling DLLs.
- **W11.2 Windows build** (`scripts/build_windows.ps1`): (1) stages **every `*.dll`** beside the
  provided `-LlamaServer` into `resources\llama-runtime` (it previously staged only the launcher → the
  bundled model server could not start); (2) **`-ModelTier low|mid|high`** (default mid = Apache 7B),
  validated + logged + size-stamped (mirrors `model_tiers.py`); (3) an **Authenticode signing step**
  (`signtool sign … /tr … ; verify /pa`) gated on `-SigningCert`, password from
  `$env:WINDOWS_CERT_PASSWORD`, no-op + warning when absent (mirrors the macOS `APPLE_SIGNING_IDENTITY`
  gate); (4) **re-saved UTF-8 *with BOM*** — the file was UTF-8-no-BOM and **Windows PowerShell 5.1**
  (the only PS on the host; `#requires 5.1`) mis-decodes its em-dashes as ANSI and **fails to parse the
  script** — a latent blocker to any real Windows build, now fixed. `scripts/build_macos.sh` gained the
  matching `MODEL_TIER` wiring.
- **On-host build attempt (this Windows box, no clean VM):** verified the pipeline through every stage
  **except the final NSIS wrap**:
  - **Backend freeze ✓** — `pyinstaller codesense.spec` → `server/dist/codesense-server.exe` (**28.7 MB**).
  - **Frontend build ✓** + **Tauri Rust app compile + link ✓** — `tauri build` produced
    `target/release/codesense.exe` (**11.87 MB**); the build log confirmed the `resources/llama-runtime`
    DLLs registered as bundle resources. My `main.rs` edits compile clean on **rustc 1.96**.
  - **LIVE RUN ✓ + 2 Windows bugs found & fixed** (commit `2fbfd1e`). Ran the built app from a mirrored
    install layout: it launches, spawns the backend on 127.0.0.1:8585, Django routes resolve
    (`/admin/`→302) and WhiteNoise serves static (`/static/admin/css/base.css`→200). Running it
    surfaced two Windows-only bugs never hit on the macOS-only prior builds: **(1)** `main.rs` set
    `SEMGREP_BIN` with **no `.exe`** (the backend uses that override verbatim; only the
    `SCANNER_TOOLS_DIR` fallback appends the ext) → the packaged scanner couldn't find OpenGrep →
    scans found nothing. Fixed with a `cfg!(target_os="windows")` `semgrep.exe`. **(2)** `codesense.spec`
    didn't collect **`whitenoise`** (settings references it only by dotted string) → the frozen backend
    **crashed at startup** on `collectstatic` (`ModuleNotFoundError: whitenoise`). Fixed with
    `collect_submodules("whitenoise")`. Both re-verified live after re-freeze/rebuild.
  - ⚠️ **Toolchain gotcha (fixed):** the host's **rustc 1.85.1** was too old for current Tauri deps
    (`darling`/`icu_*`/`image`/`serde_with`/`time` need 1.86–1.88); `rustup update stable` → **1.96.0**
    unblocked it. *(The global toolchain on this machine was updated as a build-host setup step.)*
  - ⚠️ **WebView2:** `tauri.conf.json` pins a **fixed-version WebView2 runtime** (absent here), which
    Tauri's codegen validates even with `--no-bundle`. The compile was unblocked by **temporarily**
    switching to `downloadBootstrapper`; the config was **reverted to `fixedRuntime`** before commit
    (the committed app stays fully-offline). A full installer needs that runtime staged (`-WebView2`)
    or that config switch.
  - **NSIS installer — BLOCKED on a 32-bit makensis limit (new finding).** The full `tauri build`
    reached makensis (NSIS 3.11, auto-fetched) and aborted: `File: failed creating mmap of
    …\astra.gguf` (`installer.nsi:672`). Tauri's NSIS bundler mmaps every resource and 32-bit makensis
    **cannot mmap a ~2 GB+ file** — the **4.68 GB** 7B GGUF exceeds it. Mitigations (decide W12, see
    `metrics/scorecard.md` "W11 NSIS large-file limit"): ship the **low-tier 1.5B (~1 GB, fits)** in the
    EXE — the `-ModelTier` wiring this week exists for exactly this; or split the GGUF into <2 GB shards;
    or switch the Windows target to WiX/MSI; or first-run fetch. macOS `.dmg` has no such limit. App
    size in `metrics/scorecard.md` W11 is a **computed staged-payload proxy (~4.8 GB)**, not installed.
- **Still owed (carried to W12):** a **signed** DMG/EXE + clean-VM install→scan (blocked on Apple cert,
  Windows cert, per-OS VMs); W6 ≥40% wall-time, W8 CI on a real runner, W10 live-scan visual (all need a
  live 7B host). See `metrics/scorecard.md` W11.

## Phase 3 — W12 DONE on branch `week6` (committed locally, NOT pushed) — 2026-07-01

**W12 — Harden + measure results.** The roadmap's closing pass: re-measure every scorecard axis with
the final build/model against a **live** instruct 7B host, write the before/after results doc, and
fix the top quality item (TDD). **Measurement + hardening, no feature code.** Full detail:
[`metrics/RESULTS.md`](metrics/RESULTS.md), `metrics/scorecard.md` (Week 12), `docs/RELEASE-NOTES.md`.

- **12.1 — full scorecard re-measured live.** Host = the sibling `astra-model-host/` 7B
  (Apache Qwen2.5-Coder-7B-Instruct Q4_K_M) on `127.0.0.1:8001` (CPU-only, single-slot, ~30 s/call).
  - **Detector** (`run_eval.py --dataset curated --tier detector --gate`, real OpenGrep): **PASS** —
    F1/recall **1.000**, FP **0.000**, TP=7/FP=0/FN=0/TN=7 across all 7 curated langs.
  - **Verifier Tier-2** (live, 8 detector findings from the 7 real fixtures): **F1 1.000**, all
    TP-retained. **FP-suppression = 0.857 (6/7)** via a direct probe on the safe fixtures (they're
    detector TNs so never reach the verifier through the pipeline — the standing curated caveat); the
    one miss errs toward a spurious flag. Was **0.000** (FIM rubber-stamp) at W1.
  - **Enrichment** (live, 8 real findings): parse-rate **1.00**, 0 CWE contradictions. Was 0.34 at W1.
  - **Per-finding LLM latency = 29.7 s p50** (16 live calls). **App size ≈ 4.85 GB** (core-payload proxy).
  - Rendered via `scripts/eval/scorecard.py render_scorecard` (see `metrics/scorecard.md` W12).
- **12.2 — `metrics/RESULTS.md` written** — W1→W12 before/after per axis + §9 pass/fail + narrative
  (what improved, what's open per spec §7, next-quarter rec). Every **accuracy** axis meets target.
- **12.3 — hardening (TDD).** The re-measure surfaced **no regressions**. The one actionable quality
  item — the 7B occasionally prefixing an enriched title with a canonical CWE label ("CWE-78: OS
  Command Injection"), the deferred-since-W5 finding — is fixed by a **deterministic title sanitizer**
  (`report_enricher._strip_cwe_prefix`, applied in `apply_report`; the `cwe` field stays the source of
  truth, surfaced separately as the W10 CWE link). RED→GREEN, 4 new tests. Suite **169 pass / 2 skip**.

**Two gaps remain (infrastructure/procurement, NOT code/model regressions):**
- **≥40% scan wall-time (W6)** — needs a **multi-slot** inference host; this box serializes on one CPU
  slot so parallelization can't demonstrate the speed-up. Code path in place + env-tunable.
- **Signed installer + clean-VM install→scan** — blocked on (a) Apple Developer ID + notarization
  creds, (b) a Windows code-signing cert, (c) per-OS clean VMs. Signing is **wired** on both OSes.
- **Windows 7B packaging** still blocked by the 32-bit NSIS ~2 GB mmap limit — decide low-tier 1.5B EXE
  (`-ModelTier low`, fits) / split-GGUF / WiX-MSI / first-run fetch. macOS `.dmg` unaffected.

**Still-open / carry-overs (unchanged this session, flagged not silently done):**
- **Push strategy** for the stacked W9→W12 commits on `week6` (still **local-only**, awaiting OK).
  **Do NOT push to frozen production `lsast-handoff-2026-05-31` without explicit OK.**
- OWASP Benchmark headline still deferred (curated N=14 is a coverage probe); grow curated with genuine
  detector-FP cases so verifier FP-suppression is exercised through the full pipeline.
- W8 CI never run on a real GitHub runner; deferred fusion high-sev-FP policy decision.
- Prod Phase-1 deploy pending (push OK + `LLM_MODEL_MODE=instruct` on cloud + reachable instruct host
  served `--jinja`); `main` vs prod reconcile (no Phase 1 on `main`).
- Pre-existing, out of scope: `scripts/eval/tests/test_owasp.py` POSIX-path failure.
