Code Sense (yacm) — Handoff, 2026-07-29 → 2026-07-30

Picking up work on Code Sense, an offline SAST desktop app (Tauri/Rust shell +
Django/Python backend, frozen with PyInstaller, running fully offline). Read
`CLAUDE.md` at repo root for architecture context — **note it is now stale on
one point: it still refers to branch `week6` throughout; the repo has since
been consolidated onto a single branch, `main`** (see below). This file covers
everything since the previous handoff
(`docs/handoff/05-2026-07-27-dashboard-sbom-pia-handoff.md`) and should be
read before touching git or planning further work.

## tl;dr status

- **Repo location changed**: `C:\Users\AstraCybertech\codesense\` was renamed
  to `C:\Users\AstraCybertech\codesense-v1\` partway through this session (an
  external action, not something done by Claude). The project is now at
  `C:\Users\AstraCybertech\codesense-v1\yacm`. No data was lost — same git
  history, same working-tree state — but any old absolute-path references
  (docs, scripts, cached build artifacts) may still say `codesense\yacm`.
- **Repo consolidated to one branch.** `main` is now the only branch, both
  locally and on `origin` (`github.com/grv-astra/codesense`), set as GitHub's
  default branch. `week6`, `lsast-handoff-2026-05-31` ("production", was live
  on Railway per the user), `trial-mode`, `week2-instruct-model`,
  `week4-verifier-accuracy`, and `week5-enrichment-tiers` were all deleted
  (both origin and local) after their commits were reconciled onto `main` —
  `trial-mode`'s 2 unique commits (scan-cap enforcement + its UI) were merged
  in first, nothing else had unique undelivered work. **This was done with
  the user's explicit, branch-by-branch confirmation, not unilaterally.**
- **Current `main` tip: `9cc8e92`**, pushed, `origin/main` in sync (0 ahead /
  0 behind). Full commit list below.
- **Two real, unrelated bugs found and fixed this session** (both via live
  testing, not just code review): the SBOM cosign-signing-key gap and the
  grype-db reassembly-layout bug (SBOM vulnerability scanning was silently
  broken in **every** prior packaged build — see item 2 below). A third,
  smaller bug (AST-analysis failures leaving a scan stuck at `"queued"`
  forever) was found while verifying a feature request and fixed on request.
- **Trial mode is now a real, tested feature spanning both scan types**, and
  is wired into the packaged desktop build for the first time (previously
  dev-from-source/Railway only).
- **Delivery zips built this session are NOT currently on disk** — see
  "Missing delivery zips" below. Rebuild before handing anything over again.
- Scheduled cloud routine `codesense-semgrep-rules-canary` is live (Mon/Wed/Fri
  9:00 UTC), checking `origin/main`.
- Working tree still carries the same handful of **deliberately-deferred,
  pre-existing uncommitted files** that multiple prior sessions have left
  alone — see "Still uncommitted, don't touch" below.

## What changed this session, in order

### 1. Pre-handover test + rebuild pass (ISec review delivery)
Full local test suite pass (server 227→229, client 21, `tsc` clean) plus a
full rebuild pipeline (refreeze backend, rebuild Tauri app, repackage). Found
and fixed two real bugs via live testing on the actual packaged exe:

- **SBOM signing had no fresh-install path.** `init_sbom_signing` (the only
  thing that ever generated the cosign keypair) is a manual-only Django
  command, never invoked anywhere in the packaged app. Fixed with
  `tools.ensure_cosign_keys()` — lazily generates the keypair + signing config
  on first SBOM sign. Also had to bake a fixed `COSIGN_PASSWORD` into the
  packaged app (`main.rs`) since it was previously unset, which would have
  blocked on an interactive password prompt with no stdin to answer it.
- **SBOM vulnerability scanning was silently broken in every prior packaged
  build.** Grype expects its DB cache at
  `<GRYPE_DB_CACHE_DIR>/<schemaVersion>/vulnerability.db`; the first-run
  asset-reassembly path was reassembling the sharded grype-db asset flat into
  `GRYPE_DB_CACHE_DIR` directly (no subdirectory). Grype failed to load the
  DB — silently, error swallowed — so every packaged-app SBOM scan reported
  **zero vulnerabilities regardless of actual risk**. License findings were
  unaffected (those come from `syft`, not `grype`). Fixed by reassembling
  into `GRYPE_DB_CACHE_DIR/<GRYPE_DB_SCHEMA_VERSION>/` (`main.rs`, new
  `GRYPE_DB_SCHEMA_VERSION = "5"` const). The user independently caught this
  live (a real DVWA SBOM scan showing 0 vulnerabilities) before the fix was
  found to be the actual root cause — worth remembering that user-driven
  live testing is what surfaced this, not code review.

Both fixes verified live: rebuilt the packaged exe, ran real SBOM scans
against a completely fresh data dir, confirmed signing self-heals and a
known-vulnerable test package now correctly reports its vulnerabilities.

**Also discovered, not a bug**: this dev machine has very thin margin under
the scanner's 300-second subprocess timeout — a single full-ruleset semgrep
scan occasionally exceeds 300s even in complete isolation (no other load).
Root cause not pinned down (possibly Windows Defender re-scanning), but
confirmed via repeated testing that it's environmental, not a code
regression — a rerun of the exact same test typically passes clean. If a
future session sees a spurious `test_characterization`/eval-gate failure with
a `timed out after 300 seconds` log line, this is almost certainly it —
rerun before assuming a real regression.

### 2. UI fixes (requested directly)
- **"Findings0" tab-badge bug**: `{count && <Badge/>}` renders the literal
  number `0` when count is exactly 0 (JS `&&` short-circuits to the falsy
  operand itself, and React renders numbers as text) — tabs showed
  "Findings0" instead of "Findings" on zero-finding scans. Fixed with `!!count`
  in both `scan/$scanId/route.tsx` and `scan/sbom.$sbomscanId/route.tsx`.
- **License Overview added to the SBOM scan's Updates tab** (previously
  vulnerability-only): total license-finding count, a short preview list
  (package/license/decision), and a link to the existing full Licenses tab.

### 3. Verified the scan-orphan-row fix (from an earlier session) still holds
Re-confirmed via unit tests, a live repro (real corrupt zip through the
running backend), and a UI check that a failed scan shows `"Failed"` /
`"Scan Failed"`, never stuck at `"queued"`.

### 4. Branch consolidation ("clean github and make only one branch")
See tl;dr above for the end state. Mechanics worth knowing for next time:
- Renaming a local branch (`git branch -m week6 main`) does **not** touch or
  delete the branch's old name on `origin` — `origin/week6` was left behind
  as an orphan after pushing the renamed branch as `main`, and had to be
  separately deleted. Easy to miss.
- GitHub refuses to delete a branch that's currently the repo's default —
  the default had to be flipped to `main` (via the GitHub web UI, done by
  the user; no `gh` CLI or API token was available in this environment) before
  the old default (`lsast-handoff-2026-05-31`) could be deleted.
- Merging `trial-mode` into `week6` (before the rename) produced one real
  content conflict (`client/src/components/charts/cards.tsx` — trial-mode's
  SBOM-hiding filter vs. this session's new "SBOM Findings" dashboard card,
  both unaware of each other) and one Django migration-graph conflict
  (`trial-mode`'s own `0002_trialusage.py` vs. this session's `0002` for
  confidence/rule_id, both independently depending on `0001_initial`) —
  resolved with `manage.py makemigrations --merge` →
  `0005_merge_20260729_1528.py` (no-op merge migration). **Caught and fixed a
  self-made mistake**: the merge migration file was generated but not staged
  before the merge commit landed — required a follow-up commit
  (`4bcf447`) to actually include it. Worth double-checking `git show --stat`
  on any commit involving a generated migration merge.

### 5. Trial mode now covers SBOM scans too (was: hidden instead of capped)
Previously, trial mode hid SBOM entirely (entry points, project tab) while
code scans were properly capped. Now both share one `TrialUsage` counter:
- `SbomCreateView` + `GrypeCreateView` (create-from-existing-SBOM) both check
  `trial.can_start()`; `trial.record_completion()` fires on SBOM success too.
- `trial.in_progress()` now counts in-progress/queued rows from **both**
  `Scan` and `SbomScan`, so a concurrent code+SBOM submission can't jointly
  overshoot the cap.
- All client-side SBOM-hiding removed (dashboard cards, project scan-type
  selector, scan-start entry points, scan-type pickers in
  uploadzip/githubrepo) — SBOM is always offered now, gated by the same
  disabled-button + "X/Y scans used" banner code scans already had.
- Verified live: `TRIAL_MODE=true`, `TRIAL_SCAN_LIMIT=1` — an SBOM scan
  completed and consumed the shared slot; a second scan of either type got a
  real 403; UI button correctly disabled with SBOM still listed as an option.
- **Found in passing, not fixed** (pre-existing, unrelated to trial mode):
  `githubrepo.tsx`'s "SBOM Scan" type option is non-functional — it never
  branches to an SBOM-specific mutation, always hits the code-scan endpoint
  regardless of selection. Flagged to the user, left alone since it wasn't
  what was asked.

### 6. Verified + then fixed: failed scans never consume a trial slot
User explicitly asked to "ensure" this. Traced every scan-creation path
(`ScanCreateView`, `GitHubRepoScanView`, `SbomCreateView`, `GrypeCreateView`)
and proved with 8 new tests (not just code reading) that
`trial.record_completion()` is structurally unreachable on any failure —
caught exceptions, and `scan_folder`'s early-return-on-AST-failure path both
correctly avoid it.

**While tracing this, found a real adjacent bug** (unrelated to trial slots):
if AST analysis itself raises inside `scan_folder`, the function returns `[]`
normally instead of raising — so the calling view's own exception handler
(the one that marks rows `"failed"`, fixed for other failure points back in
`7198fd1`) never fires for this specific failure point. The row stayed stuck
at `"queued"` forever, silently, with no `end_time`. **User asked to fix it**:
TDD (extended the existing AST-failure test to assert `status="failed"` +
`end_time`, confirmed RED against the old code), then a one-line fix in
`scanner.py`'s except block. 259/259 tests after.

### 7. Client delivery: trial mode wired into the packaged desktop build
`TRIAL_MODE`/`TRIAL_SCAN_LIMIT` had never been connected to the desktop build
at all (dev-from-source and Railway only). Added `TRIAL_MODE="true"` +
`TRIAL_SCAN_LIMIT="2"` constants to `main.rs`, wired into `spawn_backend`,
same per-delivery baked-constant pattern as the existing
`LICENSE_DURATION_DAYS="30"` (which was already correct, no change needed).

**Two environment issues hit during the rebuild, both traced to the
`codesense`→`codesense-v1` folder rename**:
- `server/.venv/Scripts/pyinstaller.exe` (the launcher script) started
  failing silently (exit 1, zero output, not even `--version` worked) —
  root cause not fully pinned down (likely Windows Defender flagging the exe
  after the rename triggered a fresh scan), but `python -m PyInstaller`
  works identically and was used as the workaround for the rest of this
  session. **Use `python -m PyInstaller <spec> --noconfirm --clean` instead
  of the `.exe` launcher going forward** unless the launcher is confirmed
  fixed.
- `npx tauri build` failed with `failed to read plugin permissions: ...
  path specified` — a Cargo build-cache directory
  (`client/src-tauri/target/release/build/tauri-<hash>/`) had the **old**
  absolute path (`...\codesense\yacm\...`) baked into its cached output from
  before the rename. Fixed by deleting that one specific stale directory (not
  a full `cargo clean`) and retrying. If this recurs on a different hash
  directory, same fix applies — find and delete the specific stale
  `target/release/build/{tauri,codesense}-<hash>` dir the error names.

Verified live on the rebuilt exe: `GET /api/trial/` → `limit=2 used=0`; a
code scan + an SBOM scan together consumed both slots (proving the shared
counter); a third scan attempt (either type) got a real 403; the 30-day
license computed `expires_at` correctly; Job Object kill-on-close still
holds (force-killed the GUI, backend + llama-server died with it).

### Missing delivery zips
Two zips were built and verified this session but are **not currently found
anywhere on disk** (searched the full `C:\Users\AstraCybertech` tree):
- `codesense-isec-build-2026-07-28c.zip` (~7.16 GB, no trial cap, ISec-review
  README) — built after the cosign + grype-db fixes.
- `codesense-client-trial-2026-07-29.zip` (~7.16 GB, `TRIAL_MODE=true`
  `TRIAL_SCAN_LIMIT=2`, 30-day license, client-facing `README.txt`) — the
  most recent build, includes everything through commit `9cc8e92`.

Most likely explanation: the user already sent one or both and deleted the
large local copies to free disk space — but this was not confirmed in this
session, so **don't assume either still exists**. If a delivery is needed,
rebuild from current `main` following the pipeline in item 7 above (refreeze
backend if any `server/` file changed since `9cc8e92`, copy into
`client/src-tauri/binaries/`, `tauri build --no-bundle`, live-verify, zip
`client/src-tauri/target/release/` excluding Cargo build caches / `.pdb` /
`.d` / `license_data/`).

## Scheduled cloud routine

`codesense-semgrep-rules-canary` (id `trig_015fQRL2SNW3yRzhxSjSXGHW`), cron
`0 9 * * 1,3,5` (Mon/Wed/Fri 9:00 UTC / 2:30 PM IST). Each run: fresh clone of
`main`, re-stages the upstream `github.com/semgrep/semgrep-rules` snapshot
into a scratch dir (never touches the repo), runs the curated detector eval
gate against it with `pip`-installed Semgrep standing in for the Windows-only
bundled OpenGrep binary, reports pass/fail + metrics. Read-only — no commits,
no PRs. View/manage at `https://claude.ai/code/routines/trig_015fQRL2SNW3yRzhxSjSXGHW`.

## Still uncommitted, don't touch without asking (pre-existing, carried across
many prior sessions unchanged)
`client/src-tauri/tauri.conf.json` (the P0 AI-fix resources map + a
dev-only `downloadBootstrapper` webviewInstallMode — the latter must go back
to `fixedRuntime` before any *real* offline installer build, per earlier
handoffs), `client/src-tauri/.gitignore`, `client/src/hooks/use-asset-setup.ts`
+ `.test.ts`, `docs/RELEASE-NOTES.md`, `server/run_dev.ps1`. Also harmless/
untracked and not part of any feature: `app_stderr.log`, `app_stdout.log`,
`client/.env.development`, `server/local/api_app/views/.gitignore` (a
redundant duplicate of the root `.gitignore`, likely accidental, never
addressed).

## How-to reference (asked about this session, may come up again)

- **Reset the trial counter** on a packaged build (no `manage.py` access in
  the frozen exe): direct SQLite edit —
  `python -c "import sqlite3, os; c = sqlite3.connect(os.path.join(os.environ['LOCALAPPDATA'], 'com.codesense.desktop', 'app.sqlite3')); c.execute('UPDATE trial_usage SET scans_used = 0'); c.commit()"`
  (app must be fully closed first — tray → Quit).
- **Reset the license**: stored redundantly in
  `%LOCALAPPDATA%\com.codesense.desktop\license.json` **and**
  `HKCU\Software\CodeSense\license` (registry) — `first_seen` is taken as the
  earliest valid timestamp across both, so both must be deleted or it just
  gets re-populated from whichever one survives.
- **Remove trial mode entirely**: it's a compile-time baked Rust constant
  (`TRIAL_MODE` in `main.rs`), not a runtime toggle — requires editing the
  constant to `"false"` and rebuilding (`tauri build --no-bundle`, no backend
  refreeze needed for a Rust-only change).
- **Generate an SBOM file** to test the "upload existing SBOM" path:
  `dist\tools\windows\syft.exe scan dir:<path> -o json > sbom.json` (the
  pipeline auto-detects `syft-json` format natively, no conversion needed).
- **Test repo recommendations**: DVWA (`Downloads\DVWA-master.zip`, already
  on this machine) is good for code-scan findings but its own Composer
  dependencies are clean — an SBOM scan on it legitimately returns 0
  vulnerabilities, confirmed this session, not a bug. `NodeGoat-master.zip`
  (also already in `Downloads`) was recommended for testing *both* code and
  SBOM findings together but not yet verified end-to-end.

## Next steps / open items

1. Confirm whether either delivery zip was actually sent, and clean up /
   rebuild as needed.
2. `CLAUDE.md`'s "Current roadmap position" section still refers to branch
   `week6` throughout — now stale, should be updated to reflect the `main`
   consolidation whenever someone's doing doc cleanup (not blocking).
3. The four carried-over "don't touch without asking" files (tauri.conf.json
   etc.) remain undecided — someone should eventually decide whether to
   commit or discard them.
4. `githubrepo.tsx`'s non-functional SBOM scan-type option (found this
   session, not fixed, low priority).
5. Whichever real-world repo gets used for combined code+SBOM demo testing
   (NodeGoat suggested, not yet verified) — worth confirming it gives
   meaningful results on both axes before using it for a client demo.

## How to apply this handoff

Read `CLAUDE.md` (mind the stale `week6` references), then this file. The
repo now lives at `C:\Users\AstraCybertech\codesense-v1\yacm`, single branch
`main`, tip `9cc8e92`, fully pushed. No uncommitted feature work is pending —
everything from this session is committed and pushed. Start by confirming
the delivery-zip question above before assuming any packaged build is ready
to hand over.
