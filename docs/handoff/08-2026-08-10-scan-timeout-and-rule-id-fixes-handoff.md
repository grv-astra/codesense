Code Sense (yacm) — Handoff, 2026-08-10

Picking up work on Code Sense, an offline SAST desktop app (Tauri/Rust shell +
Django/Python backend, frozen with PyInstaller) whose **primary target is
actually the web app** (Django + React, run as a normal web stack — see
`docs/handoff/07-2026-08-03-sbom-license-grant-fix-isec-builds-handoff.md` and
this repo's own `client/src/hooks/use-asset-setup.ts` gate, fixed 2026-08-05
to allow standalone browser loads). Read `CLAUDE.md` (**stale** — still
describes the old `week6` branch/W1–W12 roadmap; repo has been on a single
`main` branch since late July), then handoff `06`, then `07`, then this file.

## tl;dr status

- **Two real bugs fixed and tested this session** (both still uncommitted,
  see below): (1) a Semgrep/OpenGrep detection **timeout used to silently
  report a clean "0 findings" scan** instead of failing — now raises and
  marks the scan `interrupted` with a real error. (2) the finding-detail
  page's **Verifier Verdict box showed the raw, namespace-mangled Semgrep
  rule id** (e.g. a full rule-pack path) instead of a clean rule name — fixed
  at both the point it's persisted (new scans) and the point it's displayed
  (so already-persisted garbled rows also render clean, no DB migration
  needed).
- **A status audit was run against every open item in the `07` handoff.**
  Several turned out to already be fixed by an *unwritten* session on
  2026-08-04 → 2026-08-06 (visible only in `git log`, no handoff doc exists
  for it — worth writing one retroactively, or at least reading the commits
  directly): the `main.rs` trial/license config trap, the `grant` build fix
  (now committed), and the web-app-standalone-load gate. **Two items from
  `07` are still genuinely open**: the `githubrepo.tsx` non-functional SBOM
  scan-type option, and the two ISec review zips' delete-the-older-one
  decision. Full detail in "Status audit" below.
- **There's a substantial, uncommitted, unwritten-up feature branch of work**
  sitting in the working tree that predates this session (not touched by
  it): a real-time findings-progress bar wired to LLM verification progress,
  an activation-check timing fix, download-complete toasts on code/SBOM
  export, an SBOM page relabel ("Findings" → "Vulnerabilities"), and a real
  toast-theme bug fix (`sonner.tsx` was reading an unmounted `next-themes`
  provider instead of the app's actual theme context). None of this was
  touched or verified this session — flagged so it isn't mistaken for stray
  cruft and discarded. See "Uncommitted state" below for the full file list.
- **`main` is 5 commits ahead of `origin/main`, unpushed** (unchanged from
  whatever state the last session left it in — this session added no
  commits).

## This session's fixes, in detail

### 1. Silent scan-timeout bug (must-fix, security-tool correctness)

**Symptom** (reported by the user from an earlier session testing NodeGoat
vs DVWA): a large codebase's scan completed instantly with 0 findings — no
error, looked identical to "your code is clean."

**Root cause**: `server/scanner/rag/semgrep_detector.py`'s `run_semgrep()`
caught `subprocess.TimeoutExpired`/`FileNotFoundError` around the Semgrep
subprocess call, logged a warning, and returned `[]`. The 300s hardcoded
timeout (`_TIMEOUT_SECONDS`) is easily exceeded by a real-sized codebase
against the full bundled multi-thousand-rule pack; the caller
(`scanner.py::scan_folder`) then marked the scan `status="completed"` with
`findings: 0`, indistinguishable from a genuinely clean result.

**Fix**:
- `semgrep_detector.py` — new `SemgrepDetectionError(RuntimeError)`. The
  timeout/missing-binary except-block now raises it (with a clear message)
  instead of swallowing and returning `[]`. A normal "ran fine, found
  nothing" result is unaffected — that path still returns `[]` without
  raising.
- `scanner.py::scan_folder` — the STEP-2 (LSAST detection) call is now
  wrapped in `try/except SemgrepDetectionError`, mirroring the existing
  STEP-1 (AST analysis) failure pattern: marks `status="interrupted"` with
  `error=str(e)`, `end_time` set, returns `[]`, and — same as the AST-failure
  path — does **not** consume a trial slot. A generic (non-timeout) LSAST
  failure still propagates uncaught to the caller, unchanged.
- Tests added: `test_semgrep_detector.py` (timeout raises, missing-binary
  raises), `test_scanner.py` (`test_detector_timeout_marks_interrupted_not_completed`
  — asserts `interrupted` not `completed`, error message present, no trial
  slot consumed). Full `scanner` suite: **192 pass / 5 skip** (was 191 before
  this fix's own new tests; skips are the pre-existing `SEMGREP_BIN`-gated
  characterization tests).
- **Not done, still an open decision** (raised to the user, no answer yet):
  whether to also *raise* the 300s timeout itself (e.g. to 10–15 min) given
  this host is CPU-constrained and a bank client's real codebases will be
  bigger than NodeGoat/DVWA. The fix above only stops the timeout from
  *lying* — it doesn't make scans finish faster or extend the window.

### 2. Rule-ID garbling in the finding-detail UI (cosmetic, client-facing)

**Symptom**: the "Verifier Verdict" box on a finding's detail page showed
the raw Semgrep `check_id` — namespace-prefixed by its rule-pack path (and,
when rules load from a local dir, by the *full install path on disk*, e.g.
`Applications.CodeSense.app.Contents.Resources.semgrep-rules.dockerfile.
security.missing-user.missing-user`) — right next to the finding's `Title`,
which already shows the clean rule name (`missing-user`). Same information,
shown twice, once garbled.

**Root cause**: `finding_normalizer.py::normalize()` set the persisted
`rule_id` field to the raw `f.rule_id` verbatim (line ~273), unlike `title`
a few lines above, which already ran the check_id through `_rule_name()`
(last dotted segment). `UpdatedFinding.tsx` then rendered that raw
`rule_id` in a `break-all <code>` block.

**Fix (both layers, as the user asked)**:
- **Write-time** (`finding_normalizer.py`): `rule_id` is now
  `_rule_name(f.rule_id) or f.rule_id` — same cleanup as `title`, with a
  fallback to the raw value only if cleanup produces nothing (empty
  check_id). Only affects the *persisted-dict* `rule_id` field used for
  display/API — does **not** touch `SemgrepFinding.rule_id` (the raw
  dataclass field), which `resume.py::fingerprint()` still uses verbatim for
  resume/dedup identity, so this is display-only and doesn't affect
  checkpoint/resume correctness.
- **Display-time** (`UpdatedFinding.tsx`): a `ruleName()` helper (same
  last-dotted-segment logic) is applied wherever `rule_id` is rendered — so
  findings **already** in the database from before this fix (with the old
  garbled value) also render clean immediately, no DB migration needed.
- Tests: `test_finding_normalizer.py` — updated
  `test_normalize_sets_rule_id_and_verdict_defaults` to expect the cleaned
  value, added `test_normalize_rule_id_falls_back_to_raw_when_unparseable`.
  `UpdatedFinding.test.tsx` — added a test asserting the last-segment is
  shown and the full namespaced path is not. **Backend: 25/25 normalizer
  tests, 192/192 (5 skip) full scanner suite. Frontend: 7/7 component
  tests.**

## Status audit — every open item from the `07` handoff, re-checked today

Done by reading `git log`/`git diff`/current file contents directly rather
than trusting the (7-day-stale) `07` doc's claims. Findings:

| Item (from `07` handoff) | Status now | Evidence |
|---|---|---|
| `main.rs` uncommitted ISec trial/license config trap (`TRIAL_MODE="false"`, `LICENSE_DURATION_DAYS="180"`) | **Resolved** | Current file has the safe committed defaults (`"true"`/`"30"`); no working-tree diff on `main.rs` at all. |
| `grant` (SBOM license scanner) build fix, only isolated-step-verified | **Committed** | `2acde52` (2026-08-06) `fix(build): build grant from source instead of a nonexistent Windows release asset`. Still **not** proven via an actual full from-scratch `build_windows.ps1` run (no `-SkipTools`) — that specific gap is unchanged. |
| Web app hangs at "Setting up Code Sense… 0%" outside Tauri (from my own memory, not literally in `07`'s list, but same family) | **Resolved** | `ef5ac01` (2026-08-05) `fix(client): let the web app load standalone without the Tauri desktop shell` — gates `useAssetSetup` on `isTauri()`. |
| `client/src-tauri/tauri.conf.json`, `.gitignore`, `use-asset-setup.ts`/`.test.ts`, `docs/RELEASE-NOTES.md` uncommitted | **Resolved (committed)** | No working-tree diff on any of these now; landed across the 2026-08-04→06 commits. |
| `githubrepo.tsx` non-functional SBOM scan-type option | **Still open** | Code now has an explicit comment admitting it (`githubrepo.tsx:87-88`): *"the 'SBOM' option here never branches to an SBOM mutation"* — always creates a code scan regardless of the picked type. Confirmed current as of `638c1b3` (2026-08-06), the latest commit touching that file. |
| Rule-ID garbling display bug | **Fixed this session** | See above. |
| Two ISec review zips, decide whether to delete the older `-30.zip` | **Still open** | Both `codesense-isec-build-2026-07-30.zip` and `...-30b.zip` still on disk, untouched. |
| Pile of long-carried "don't touch without asking" uncommitted files | **Partially resolved, partially regrown** | Several from `07`'s list got committed (see above row). But `app_stdout.log`/`app_stderr.log`, `client/.env.development`, `server/local/api_app/views/.gitignore`, modified `run_dev.ps1` are still sitting uncommitted, **plus new ones accumulated since**: `CLIENT_MACHINE_PREREQUISITES.md`, `HANDOVER_DEPLOY.md`, `use-activation.test.tsx`, `.claude/worktrees/`, and — notably — **handoff docs `06` and `07` themselves were never committed** (still untracked). |

## Uncommitted state — full picture, right now

`git status --short` on `main`:

```
 M client/src/components/atomic/sonner.tsx                              <- pre-existing, not this session
 M client/src/components/update/Scanupdate.tsx                          <- pre-existing, not this session
 M client/src/components/update/UpdatedFinding.test.tsx                 <- THIS SESSION (rule-id fix test)
 M client/src/components/update/UpdatedFinding.tsx                      <- THIS SESSION (rule-id fix)
 M client/src/hooks/use-activation.tsx                                  <- pre-existing, not this session
 M client/src/routes/__root.tsx                                         <- pre-existing, not this session
 M client/src/routes/_authenticated/project/$projectId/codescan.tsx     <- pre-existing, not this session
 M client/src/routes/_authenticated/project/$projectId/sbomscan.tsx     <- pre-existing, not this session
 M client/src/routes/_authenticated/scan/sbom.$sbomscanId/findings.tsx  <- pre-existing, not this session
 M client/src/routes/_authenticated/scan/sbom.$sbomscanId/route.tsx     <- pre-existing, not this session
 M client/src/types/scan.ts                                             <- pre-existing, not this session
 M server/run_dev.ps1                                                   <- pre-existing, not this session
 M server/scanner/rag/finding_normalizer.py                             <- THIS SESSION (rule-id fix)
 M server/scanner/rag/lsast_scanner.py                                  <- pre-existing, not this session
 M server/scanner/rag/scanner.py                                        <- THIS SESSION (timeout fix)
 M server/scanner/rag/semgrep_detector.py                                <- THIS SESSION (timeout fix)
 M server/scanner/tests/test_finding_normalizer.py                      <- THIS SESSION
 M server/scanner/tests/test_lsast_scanner.py                           <- pre-existing, not this session
 M server/scanner/tests/test_scanner.py                                 <- MIXED: pre-existing resume-count tests + THIS SESSION's timeout test
 M server/scanner/tests/test_semgrep_detector.py                        <- THIS SESSION
?? .claude/worktrees/                                                   <- carried, contains the merged worktree-scan-interrupt-resume checkout
?? CLIENT_MACHINE_PREREQUISITES.md                                      <- carried, not investigated
?? HANDOVER_DEPLOY.md                                                   <- carried, not investigated
?? app_stderr.log / app_stdout.log                                      <- carried, log files, likely safe to delete but ask first
?? client/.env.development                                              <- carried, not investigated
?? client/src/hooks/use-activation.test.tsx                             <- carried, pairs with use-activation.tsx above
?? docs/handoff/06-...-handoff.md                                        <- carried, never committed
?? docs/handoff/07-...-handoff.md                                        <- carried, never committed
?? server/local/api_app/views/.gitignore                                <- carried, not investigated
```

**The "pre-existing, not this session" group is one coherent, unfinished
feature effort** (inspected via `git diff` to write this table, not just
assumed): a real-time findings-progress bar keyed off
`metrics.findings_progress` (phases re-tuned to 0–15–20–95–100, since
detection is one atomic pass but LLM verification is the long
per-finding-progress-reporting part — see `Scanupdate.tsx` +
`FindingsProgress` type in `scan.ts`); `useActivation(ready: boolean)` now
takes a `ready` param so it only starts polling once `useAssetSetup` is
actually `'ready'` (`__root.tsx` updated to pass
`assetSetup.status === 'ready'`), fixing a race where activation checks
fired before the backend was listening; download-complete toasts on the
code-scan and SBOM-scan Excel exports (`codescan.tsx`, `sbomscan.tsx` —
needed because the packaged desktop app has no browser download bar to
confirm a save succeeded); an SBOM findings page relabel ("Findings" →
"Vulnerabilities" in both the tab and empty-state text,
`sbom.$sbomscanId/{route,findings}.tsx`); and a real bug fix in
`sonner.tsx` — it was reading `next-themes`' `useTheme()`, but
`next-themes`' `ThemeProvider` is never mounted anywhere in this app (it
uses its own `contexts/use-theme.tsx`), so toasts silently used a
disconnected, always-`"system"` theme value, producing mismatched
light/dark toast styling. Now reads the app's real `isDarkMode`.
`run_dev.ps1`'s only change is the dev port, `8585` → `8586` (reason not
recorded, possibly to avoid a port clash while another instance ran).
**None of this was written up in any handoff doc** — there's a gap between
`07` (2026-08-03) and whatever session did this (git blame/log on these
files, or ask the user, would date it — likely 2026-08-04 through 08-09
given the commit timestamps bracketing it on either side).

## Next steps / open items

1. **Commit this session's two fixes** (timeout + rule-id) — clean, tested,
   self-contained; safe to commit independently of the carried WIP above.
   Ask the user first per this repo's "always confirm before committing"
   norm.
2. Decide whether to also raise `_TIMEOUT_SECONDS` (currently 300s) — open
   question posed to the user this session, no answer yet.
3. **The carried, uncommitted feature-branch work (progress bar, activation
   timing, export toasts, SBOM relabel, sonner theme fix) needs a decision**:
   commit it, keep iterating on it, or get a proper handoff write-up for it
   since none exists. Don't silently discard — it looks like real, coherent
   work, not stray cruft.
4. `githubrepo.tsx` non-functional SBOM scan-type option — still open, not
   touched this session. Root cause already known (see table above and the
   original conversation): `handleSubmit` always calls the code-scan
   mutation regardless of `formData.scan_type`.
5. Decide on the two ISec review zips (delete the older 2-scan/30-day one
   now that the unrestricted 180-day one supersedes it for review purposes?)
   — still unresolved, unchanged since `07`.
6. `build_windows.ps1`'s grant fix still wants a real full end-to-end run
   before trusting it blindly for the next client build.
7. Consider committing `docs/handoff/06-...md` and `07-...md` (and this
   file) — three handoff docs in a row have now been written but never
   actually committed to the repo.
8. Same long-carried "don't touch without asking" files as ever — still
   nobody's decided what to do with `app_std{out,err}.log`,
   `client/.env.development`, `server/local/api_app/views/.gitignore`,
   `CLIENT_MACHINE_PREREQUISITES.md`, `HANDOVER_DEPLOY.md`.

## How to apply this handoff

Read `CLAUDE.md` (stale), then handoff `06`, then `07`, then this file.
Repo is at `C:\Users\AstraCybertech\codesense-v1\yacm`, branch `main`, 5
commits ahead of `origin/main` (unpushed, unchanged this session) — **check
`git status` before touching anything**, there is substantial uncommitted
state in the working tree, split between this session's two tested fixes
(safe, self-contained) and an older unwritten-up feature effort (functional
but undocumented — read the "Uncommitted state" section above before
assuming any of it is safe to discard).
