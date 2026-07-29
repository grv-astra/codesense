# Code Sense (yacm) — Handoff, 2026-07-19

Picking up work on **Code Sense**, an offline SAST desktop app (Tauri/Rust shell + Django/Python
backend, frozen with PyInstaller, running fully offline). Read `CLAUDE.md` at repo root for full
architecture context; this file covers only what changed since the 12-week roadmap closed out
(2026-07-01) and needs to be understood before touching anything.

## tl;dr status

The **12-week roadmap is complete** (accuracy/quality targets all met — see `metrics/RESULTS.md`).
Since then, two critical **stability bugs** surfaced in real usage and were root-caused and fixed
this session (2026-07-19), on branch `week6`, **all uncommitted, awaiting explicit push/commit OK**.
The app is currently verified working end-to-end on this dev machine (real scan, real AI
verification, real findings persisted and retrievable).

## Primary goal right now

**Get the two fix batches below reviewed and committed**, then decide whether to rebuild and
redeliver the ISec zip (it currently predates both fixes). Nothing has been pushed to
`origin/week6` — do not push without explicit OK, per standing project policy.

## What's uncommitted (`git status` on `week6`)

**Batch 1 — background-thread DB connection leak (2026-07-17 session, real cleanup, NOT the root
cause of the user-facing bug — see below):**
- `server/scanner/views.py`, `server/local/api_app/views/scan_views.py` — added
  `close_old_connections()` to the `finally` block of all 4 background `threading.Thread` scan
  workers, which never fired Django's request-lifecycle signals and so never released their DB
  connections.
- `server/codesense/settings.py` — added `DATABASES["default"]["TEST"]["NAME"]` pointing at a real
  file instead of Django's default `:memory:` (needed so a regression test can open a second
  independent sqlite3 connection to the same DB).
- `server/local/api_app/tests/test_background_thread_db_cleanup.py` (new) — 2 regression tests,
  both green. Full suite: 204 pass / 7 skip.

**Batch 2 — orphaned zombie backend process, the ACTUAL root cause of "User doesn't exist" (2026-07-19
session):**
- `client/src-tauri/Cargo.toml` + `Cargo.lock` — added `windows-sys = "0.61.2"` (Windows-only,
  `Win32_System_JobObjects`/`Win32_System_Threading`/`Win32_Foundation` features).
- `client/src-tauri/src/main.rs` — new `win_job` module wrapping a Windows Job Object with
  `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, created once at startup, and every sidecar
  (`codesense-server`, `llama-server`) is assigned to it right after spawn. Windows now guarantees
  both sidecars die the instant `codesense.exe` exits, by ANY means — clean quit, crash, Task
  Manager kill, debugger stop — not just the two paths `shutdown()` already handled.
- Full detail, live-verification steps, and the forensic trail: memory file
  `yacm-stuck-backend-stale-db-fix.md` (if you have access to project memory) — otherwise the
  summary below is self-contained.

**Pre-existing, unrelated, already uncommitted before this session — do NOT touch without asking:**
`client/src-tauri/tauri.conf.json`, `client/src/hooks/use-asset-setup.{ts,test.ts}`,
`docs/RELEASE-NOTES.md`, `server/run_dev.ps1`. Untracked, also pre-existing/harmless:
`app_stderr.log`, `app_stdout.log`, `client/.env.development`, `client/src-tauri/resources/`,
`server/local/api_app/views/.gitignore` (a stale June-4 duplicate of the root `.gitignore`).

## The bug, in one paragraph

`codesense.exe` (GUI) spawns `codesense-server.exe` (Django/waitress backend) as a child process.
The code that kills that child (`shutdown()` in `main.rs`) only ran on a *clean* exit path (tray
Quit / Tauri's `ExitRequested`). Any ungraceful exit — crash, force-kill, a dev restart — left the
backend running forever as an orphan, still bound to port 8585. The `tauri-plugin-single-instance`
guard only prevents a second **GUI**, not a second **backend**, so the next launch's frontend ended
up talking to whichever stale backend was already listening, producing "User doesn't exist" for
accounts that were genuinely on disk. Caught a live specimen mid-bug (orphan PID with a dead
parent, confirmed via `psutil`), killed it, confirmed a fresh launch worked instantly, then fixed
the underlying process-lifecycle gap with a Windows Job Object and proved via direct testing
(force-kill the GUI → backend now dies too, before the fix it wouldn't have).

## Important environment gotcha discovered this session — read before debugging file state again

**Any Bash/PowerShell tool call made *by Claude* on this dev machine, when it touches a path under
`%LOCALAPPDATA%`, is silently redirected by Windows to a private sandboxed mirror** (Windows
Package File System Virtualization for the "Claude" desktop app container) — NOT the real file the
actual app processes read/write. Confirmed via `Get-Item <path> -Force | Select Target` showing a
populated `Target` under `AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\...`. This
caused real confusion this session (direct file reads of `app.sqlite3` gave stale/wrong answers
about what the live app actually had). **Rule going forward: never trust a direct file read under
`%LOCALAPPDATA%` from Claude's own shell tools as ground truth — always verify through the app's
own HTTP API (`curl 127.0.0.1:8585/...`) instead**, since that's a real network call to the real
unsandboxed backend process.

## Data note (low priority, user already informed and unconcerned)

During this session's testing, the original `admin@codesense.dev` account (and an old test
project/2 scans/60 findings from 2026-07-14/15) went missing from the real database — exact
mechanism not identified (plausibly one of several ungraceful kill/relaunch cycles during testing,
or pre-existing dev-machine churn from earlier sessions — this machine has a documented history of
its admin account getting wiped during first-run-simulation testing). Restored login access by
renaming a test account back to `admin@codesense.dev` / `Admin@123` via the app's own user-update
API (kept its admin role). User confirmed the missing data was just test scans, not important, and
declined a recovery investigation. **The app was then re-verified fully working end-to-end**: real
login → real project → real zip upload → real scan through the full LSAST pipeline (detector → LLM
verifier → enrichment, live 7B model) → 2 correct findings persisted and retrievable via the API.

## Next goals, roughly in order

1. **Decide on committing** Batch 1 + Batch 2 above (or ask for a commit now if you're continuing
   this thread directly). Suggest two separate commits matching the two batches, since they're
   independent fixes for independent (if related-sounding) issues.
2. **Rebuild the ISec delivery zip.** The one at
   `C:\Users\AstraCybertech\codesense\codesense-isec-build.zip` predates both fixes — needs
   `client/src-tauri` rebuilt via the Tauri CLI (`npx --yes @tauri-apps/cli@2 build --no-bundle`
   from `client/` — **not** raw `cargo build`, which skips the `devUrl`→`frontendDist` swap and
   breaks the webview) plus the `server/` backend refrozen with PyInstaller if Batch 1 lands
   (`codesense-server.exe` currently still dated 2026-07-01, predates the `close_old_connections()`
   fix).
3. **Still-open from the 12-week roadmap, unchanged:** the ≥40% scan wall-time speedup (needs a
   multi-slot inference host — this box serializes on one CPU slot), a **signed** installer (needs
   Windows code-signing cert + clean test VM — still not procured), and the NSIS 32-bit ~2GB mmap
   limit for the full model (root-caused, fix scoped, not started — see
   `yacm-asset-reassembly-and-isec-delivery` memory / git history around 2026-07-15 for the
   options: ship low-tier 1.5B model, split-GGUF further, switch to WiX/MSI, or first-run fetch).
4. Push strategy for the stacked uncommitted work on `week6` — still awaiting explicit OK, several
   sessions running now (W9→W12 roadmap commits + this session's two fix batches).

## Quick verification recipe (if you need to re-confirm the app works)

```powershell
# from client/src-tauri/target/release/
Start-Process .\codesense.exe
# wait ~15-20s for the backend to bind 127.0.0.1:8585, then:
curl -X POST http://127.0.0.1:8585/api/auth/login/ -H "Content-Type: application/json" `
  -d '{"email":"admin@codesense.dev","password":"Admin@123"}'
```
Should return `200` with a token. To test the crash-safety fix specifically: note the
`codesense.exe` PID, `Stop-Process -Force` it, and confirm `codesense-server.exe` /
`llama-server.exe` are also gone within a second or two (`tasklist`) — before the fix they'd
survive.
