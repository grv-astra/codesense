# Handover: Code Sense — ready to deploy, scan-interrupt-resume feature landed

## What this project is
Code Sense (`yacm`) — **the primary target is a web app: Django backend + React frontend.**
Do NOT touch the Tauri desktop `.exe`/packaging unless explicitly asked by name. Repo:
`https://github.com/grv-astra/codesense`, working dir `C:\Users\AstraCybertech\codesense-v1\yacm`.

## Current state (verified clean before this handover)
- `main` is at `46ca0f2`, fully in sync with `origin/main` — nothing to push.
- Backend suite: 310 tests, 7 skipped, green. Frontend: 21 tests green, `tsc --noEmit` clean.
- No servers currently running (backend/frontend both stopped cleanly at end of last session).

## What landed this session (in order)
1. **Scan interrupt/resume feature** (PR #1, merged): cancel a running scan, resume an
   interrupted/cancelled one without re-running LLM verification on findings already
   persisted. Fingerprint-based checkpointing, `Scan.cancel_requested`/`source_path`,
   `ScanCancelView`/`ScanResumeView`, trial-cap accounting, startup reconciliation of
   crash-orphaned scans, Cancel/Resume UI.
2. **Standalone web-app fix**: the app was hard-blocking behind Tauri-only IPC
   (`useAssetSetup`) and couldn't load in a plain browser at all. Fixed via Tauri's own
   `isTauri()` runtime check — desktop behavior unchanged, web app now loads standalone.
3. **CRITICAL bug found + fixed (commit `46ca0f2`) — READ THIS BEFORE DEPLOYING:**
   The scan-resume feature's source retention wrote extracted zip contents to
   `server/media/scans/...` — which sits **inside this repo's git working tree**.
   OpenGrep's directory walker silently enumerates **0 files** for any path inside a git
   working tree (documented in this repo's own `CLAUDE.md` as the "Windows/git gotcha").
   Result: every zip-uploaded code scan run from a git checkout found 0 findings, with
   **no error surfaced anywhere** — it just silently completed with 0 results.

   Fixed by adding `_resolve_media_root()` in `server/local/api_app/views/scan_views.py`:
   respects `CODESENSE_DATA_DIR` env var when set (external app-data dir, matches
   `settings.DATA_DIR`'s own convention), otherwise falls back to the OS temp directory —
   never `BASE_DIR`. Verified end-to-end with a real zip through the real upload path:
   37 raw findings → 33 deduped → 7 persisted (was 0 before the fix).

   **⚠️ Pre-deploy check for whoever picks this up: confirm the deployment target's
   runtime data/media directory is NOT itself inside a git working tree** (e.g. if the
   deploy process does a plain `git clone`/checkout onto the server and runs from inside
   it, without `CODESENSE_DATA_DIR` pointing somewhere external, scans will silently find
   0 findings again — same bug, different environment). Set `CODESENSE_DATA_DIR` to a
   real external path in the deploy environment, or confirm the deploy mechanism doesn't
   leave a `.git` directory in the runtime working tree at all.

## Known local-only state (do not treat as "needs committing" without checking with the user)
- `server/run_dev.ps1` — locally modified (backend port 8585→8586), intentional and
  currently in use, consistent with an untracked `client/.env.development`
  (`VITE_BACKEND_URL=http://127.0.0.1:8586`) so dev-from-source can coexist with the
  packaged desktop app's default port. Leave as-is unless told otherwise.
- Untracked, harmless: `.claude/worktrees/` (a git worktree used during this session,
  branch `worktree-scan-interrupt-resume`, already merged — safe to ignore or remove),
  `app_stderr.log`/`app_stdout.log`, `docs/handoff/06-...md`/`07-...md`,
  `server/local/api_app/views/.gitignore`.

## What's NOT yet established — figure this out before deploying
This session never touched or confirmed an actual deployment pipeline/target for this
repo/branch. `CLAUDE.md` references a Railway deployment, but that's for a **different,
older branch** (`lsast-handoff-2026-05-31`, the legacy FIM-model path) — **not** this
`main` branch's work. Ask the user what the actual deploy target/process is before
assuming anything (Railway, another host, manual server restart, etc.), and confirm the
`CODESENSE_DATA_DIR` point above against whatever that target actually is.

## Verification tools available if needed
- Backend: `cd server && .venv/Scripts/python.exe manage.py test`
- Frontend: `cd client && npm test` / `npx tsc --noEmit`
- Real-tool env vars for a from-source dev run: `server/run_dev.ps1` (sets
  `SCANNER_TOOLS_DIR`/`SEMGREP_BIN`/`SEMGREP_RULES_DIR`/`GRYPE_DB_CACHE_DIR`/
  `COSIGN_KEY_DIR` from `dist/` at the repo root).
