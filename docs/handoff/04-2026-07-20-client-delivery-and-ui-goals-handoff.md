Code Sense (yacm) — Handoff, 2026-07-20

Picking up work on Code Sense, an offline SAST desktop app (Tauri/Rust shell + Django/Python
backend, frozen with PyInstaller, running fully offline). Read `CLAUDE.md` at repo root for full
architecture context; this file covers only what changed since the previous handoff
(`docs/handoff/03-2026-07-19-stability-fixes-handoff.md`) and needs to be understood before
touching anything. **This session's focus is pivoting to UI-related work — see "Next goals"
at the bottom.**

## tl;dr status

Both stability fixes from the 07-19 handoff are now **committed** (still unpushed) on branch
`week6`. A client delivery went out today (ISec zip rebuilt with a baked-in 30-day license) and
is currently mid-troubleshooting on the client's PC — two real bugs were found live during that
process, one fixed/recovered, one still open. Branch is **30 commits ahead of `origin/week6`**,
nothing pushed, per standing policy.

## What's committed this session (on `week6`, unpushed)

1. **`3bb87ad`** — background-thread DB connection leak fix (the 07-17 session's work, reviewed
   and committed as-is): `close_old_connections()` added to the `finally` block of all 4
   background scan-thread workers (`server/scanner/views.py`, `server/local/api_app/views/scan_views.py`),
   plus a real-file `TEST` DB name in `settings.py` so the new regression test
   (`server/local/api_app/tests/test_background_thread_db_cleanup.py`, 2 tests) can open a second
   independent sqlite3 connection. Verified green (173 server tests pass, 5 skip).
2. **`787a7ff`** — Windows Job Object fix (the 07-19 session's actual root-cause fix for the
   "account doesn't exist" / stuck-backend bug): `client/src-tauri/src/main.rs` gained a
   `win_job` module wrapping `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`; every sidecar
   (`codesense-server`, `llama-server`) is assigned to it right after spawn, so Windows
   force-kills both the instant `codesense.exe` exits, by ANY means. Re-verified live on the
   freshly rebuilt binary this session (force-killed the GUI, both sidecars died, zero orphans).
3. **`83c5211`** — new this session: baked a **fixed 30-day license period** into the client
   build. `main.rs::spawn_backend()` now sets `LICENSE_DURATION_DAYS=30` in the sidecar's env,
   overriding the backend's own 90-day default (`settings.py::LICENSE_DURATION_DAYS`). Verified
   live: `/api/license/` correctly computed `expires_at = first_seen + 30d` against an existing
   `first_seen` stamp. **Known caveat, told to the user**: this value is NOT part of the
   HMAC-signed license record (only `first_seen`/`last_seen` are — see
   `server/licenses/services/offline_license.py`), so it only stops casual tampering, not a
   determined user. Fine for the current ISec-review delivery context; would need hardening
   (folding duration into the signature) before shipping to an untrusted party.

## ISec delivery — three zips now exist, only one is current

- `C:\Users\AstraCybertech\codesense\codesense-isec-build.zip` — **07-15, oldest, superseded**
  (predates all three fixes above).
- `C:\Users\AstraCybertech\codesense\codesense-isec-build-2026-07-20.zip` — has the DB-leak +
  Job Object fixes, **predates the 30-day license change** — superseded.
- `C:\Users\AstraCybertech\codesense\codesense-isec-build-2026-07-20b.zip` — **current, 7.16 GB,
  commit `83c5211`, has everything.** This is the one the user transferred to the client PC
  today. Rebuild pipeline each time: refreeze backend (`pyinstaller codesense.spec --noconfirm
  --clean`) only if `server/` changed → copy into
  `client/src-tauri/binaries/codesense-server-x86_64-pc-windows-msvc.exe` → **always**
  `npx --yes @tauri-apps/cli@2 build --no-bundle` from `client/` (never raw `cargo build`, it
  skips the `devUrl`→`frontendDist` swap) → zip `target/release/` root exe/dlls +
  `resources/{model,grype-db,tools,semgrep-rules}/`, NoCompression, byte-exact verified against
  disk. **Deliberately excluded from every zip:** `target/release/license_data/` (dev-machine
  anti-tamper runtime state — never ship this). None of the stale zips have been deleted; flagged
  to the user each time, not removed unilaterally.

## Live client-PC troubleshooting — one bug found+recovered, one open, one suspected

All three surfaced today, in sequence, on the actual client PC (not this dev machine) as the
client tried to get the delivered zip running. **None of these are fixed in code yet** — all
handled as live recovery advice so far.

### 1. Stuck on login page, no admin ever created — real frontend bug, NOT YET FIXED IN CODE

`client/src/routes/_auth/login.tsx` only redirects to `/setup` from a `useEffect` gated on
`useSetupStatus()`'s query result. That hook (`client/src/hooks/use-setup.tsx`) is configured
with **`retry: false`** and no error UI. If that one `GET /api/auth/setup/` check fails or is
slow even once — most likely a race against the backend still finishing startup right after
first-run asset reassembly completes — it never retries, `setup_needed` stays `undefined`
forever, and the user is stuck on a normal-looking login page with **zero indication anything's
wrong and no admin ever created server-side.**

- **Workaround given (worked):** fully quit (tray → Quit) and relaunch. Re-fires the query fresh;
  second load correctly landed on the "Create administrator" screen.
- **Real fix, not yet applied:** add retry/polling to `useSetupStatus()`, or at minimum surface an
  error state instead of silently stalling. **This is UI work — a good first item for the
  UI-focused session below.**

### 2. "License validation failed — read-only mode" right after first successful login

Triggered immediately after the client got through setup and logged in — far too early to be a
real 30-day expiry. This is the `tampered` state in `offline_license.py`: the license record is
signed and stored redundantly in **two** places (`%LOCALAPPDATA%\com.codesense.desktop\license.json`
+ Windows registry `HKCU\Software\CodeSense\license`) specifically so deleting one doesn't reset
the clock — `tampered` fires if either stored copy exists but fails its HMAC check, or looks
like it's from the future (clock rollback). Client reported `license.json` **doesn't exist**,
which actually pinpoints the registry copy as the sole bad source (only present source ⇒ must be
the invalid one).

- **Root cause not fully pinned** — plausible mechanism is some inconsistency introduced across
  the relaunch cycle from bug #1 above, not confirmed further.
- **Recovery given (not yet confirmed by the client as of session end):**
  `reg delete "HKCU\Software\CodeSense" /v license /f` (or delete the whole
  `HKCU\Software\CodeSense` key if that errors), then relaunch — re-stamps a fresh `first_seen`,
  full 30 days restored, admin account and DB untouched (this does NOT require nuking
  `%LOCALAPPDATA%\com.codesense.desktop\`, which would also wipe the fresh admin account).
- **Follow up next session:** confirm with the user whether this actually resolved it on the
  client PC.

### 3. SBOM scan failing — suspected root cause, NOT YET CONFIRMED OR FIXED

User reported SBOM scans failing on the client PC; exact error text not yet obtained (asked for
it, session ended before it came back — **get this first thing next session**). Two known
historical SBOM issues were ruled out by reading current code: the cosign `--signing-config`
flag bug (fixed already, confirmed present in `server/scanner/services/sbom_pipeline.py`) and
missing tool staging (confirmed `cosign.exe`/`grype.exe`/`semgrep.exe`/`syft.exe` are all present
in the shipped zip's `resources/tools/`).

**New gap found while investigating, likely the real cause:** SBOM signing needs a cosign
keypair (`cosign.key`/`cosign.pub`) at `COSIGN_KEY_DIR` (`%LOCALAPPDATA%\com.codesense.desktop\keys\`
for the packaged app). That keypair is only ever generated by
`scanner/management/commands/init_sbom_signing.py` — a **manual** Django management command,
never invoked automatically by `main.rs`, Django startup, or the SBOM pipeline itself
(`_sign_sbom()` in `sbom_pipeline.py` just resolves the path and calls cosign directly — no
existence check, no lazy-generate). This dev machine's SBOM testing has "worked" this whole time
only because someone ran `init_sbom_signing` manually against it back on 2026-06-04 (see
`docs/handoff` history / `yacm-offline-scanner-tools` memory) — a genuinely fresh client PC has
never had that command run and never will, since the packaged exe has no exposed way to run
Django management commands at all.

- **Not yet fixed.** Real fix: make key generation happen automatically (lazy-generate-if-missing
  inside `_sign_sbom`/`cosign_paths`, or on first SBOM request) instead of requiring a manual
  command that isn't even reachable in the packaged app.
- **Next session, in order:** (a) get the exact client error message to confirm this theory,
  (b) if confirmed, implement the auto-generate fix, (c) rebuild+rezip (backend change → needs a
  PyInstaller refreeze this time, unlike the Rust-only license change).

## Repo / build state

- Branch `week6`, **30 commits ahead of `origin/week6`**, nothing pushed — **do not push without
  explicit OK**, standing policy.
- Pre-existing, unrelated, already-uncommitted before this session — do NOT touch without asking:
  `client/src-tauri/tauri.conf.json`, `client/src/hooks/use-asset-setup.{ts,test.ts}`,
  `docs/RELEASE-NOTES.md`, `server/run_dev.ps1`.
- Untracked, harmless, pre-existing: `app_stderr.log`, `app_stdout.log`, `client/.env.development`,
  `client/src-tauri/resources/` (local dev staging, ~7.1GB, gitignored by convention),
  `server/local/api_app/views/.gitignore` (stale duplicate of root `.gitignore`).
- **Environment gotcha, still true:** any Bash/PowerShell read of a path under `%LOCALAPPDATA%`
  from Claude's own shell tools on *this* dev machine is silently redirected to a sandboxed
  mirror, not the real file. Never trust a direct file read there as ground truth — use the app's
  own HTTP API instead. (Does not apply to the client's separate PC, which Claude has no access
  to at all — all client-PC diagnosis this session was code-reading + reasoning, not direct
  inspection.)

## Next goals — UI-focused (per user, this is the stated priority for the next session)

The user wants to pick up **UI-related work** next. Concrete candidates surfaced by this
session's real bugs, roughly in priority order:

1. **Fix the login/setup race (bug #1 above)** — add retry/polling to `useSetupStatus()`
   (`client/src/hooks/use-setup.tsx`) and/or surface a visible error/loading state on the login
   page instead of silently stalling forever. Directly caused today's first client-PC blocker;
   good first item.
2. **Confirm + close out the SBOM investigation (bug #3)** — get the client's exact error,
   confirm the missing-keypair theory, implement the fix. Backend-leaning but blocks a whole
   feature area (SBOM) for every fresh install, worth prioritizing even in a "UI session."
3. **W10 live-scan visual confirmation** — carried open item from the 12-week roadmap
   (`CLAUDE.md`'s W10 section): the finding-details UX overhaul (Verifier Verdict block, CWE
   link, guarded Mitigation block) was unit-tested but never visually confirmed against a real
   live scan. Now that a real client is running real scans, this is finally checkable.
4. **User's own UI goals** — not yet enumerated in this handoff; ask the user directly what
   specific UI work they have in mind before assuming scope beyond the three items above.

## How to apply this handoff

Read `CLAUDE.md` for architecture, then `docs/handoff/03-2026-07-19-stability-fixes-handoff.md`
for the prior state, then this file for what changed since. Start next session by asking the
user (a) whether the license-tampered recovery worked on the client PC, (b) the exact SBOM error
text, and (c) what specific UI goals they have beyond the candidates listed above.
