Code Sense (yacm) — Handoff, 2026-07-27

Picking up work on Code Sense, an offline SAST desktop app (Tauri/Rust shell +
Django/Python backend, frozen with PyInstaller, running fully offline). Read
`CLAUDE.md` at repo root for full architecture context; this file covers only
what changed since the previous handoff
(`docs/handoff/04-2026-07-20-client-delivery-and-ui-goals-handoff.md`) and
needs to be understood before touching anything.

## tl;dr status

This session pivoted to UI/feature work per the 04 handoff's stated priority,
plus two things that came up live: SBOM API testing (which surfaced two real
bugs) and a new custom Semgrep rule pack for Privacy Impact Assessment (PIA)
coverage. **Nothing from this session is committed** — it's all working-tree
changes on branch `week6` (still 30 commits ahead of `origin/week6`, unchanged
from before). The two open items from the 04 handoff (license-tampered
recovery confirmation, SBOM error text from the client) were **not**
revisited this session — still open, see "Carried-over open items" below.

## What changed this session (all uncommitted on `week6`)

### 1. Dashboard — 5 enhancements, all live-verified in browser
- **Real trend %s** — `DashboardView._get_top_counts_trend()`
  (`server/local/api_app/views/dashboard_views.py`) computes real
  week/month/day-over-period deltas from `created_at` timestamps, replacing
  hardcoded `+5%`/`+3%`/`-2%`/`+1%` in `cards.tsx`.
- **License status card** — new `license-status-card.tsx` (+ test), reuses
  the existing `useLicenseStatus()` hook that previously only fed the
  warning banner; now shows "Active — N days remaining" too.
- **Findings / SBOM Findings cards** — `top_counts` already returned these,
  `DashboardCards` just never rendered them; added.
- **Findings-trend range picker** — `_get_findings_trend(days)` now accepts
  7/30/90 via `?trend_days=`; frontend adds a 7D/30D/90D toggle
  (`keepPreviousData` so switching range doesn't blank the page).
- **Recent Activity feed** — new `_get_recent_scans()` merges code + SBOM
  scans newest-first; new `recent-activity.tsx` component, clickable through
  to each scan's detail page.
- Backend: 17 new dashboard tests, all green. Frontend: `tsc` clean, new
  client tests green.

### 2. SBOM API testing → found + fixed 2 real bugs
Was asked to test all SBOM-related APIs end-to-end (create/get/delete scan,
findings, license findings, CSV/xlsx export, Grype-from-existing-SBOM). Found:
- **Dead 404 check** (`finding_views.py`): `SbomFindingListCreateView`,
  `SbomLicenseFindingList`, and `FindingListCreateView` all checked `if not
  findings: return 404` — which fires for a *real* scan with zero findings
  just as much as a scan that doesn't exist. Fixed by checking
  `ScanModel.find_by_id()`/`SbomModel.find_by_id()` first. 7 new tests.
- **Disk leak on delete** (`sbom_models.py`): `SbomModel.delete_scan()`
  deleted DB rows but never removed `output/<scan_id>/` (SBOM/grype/grant
  reports + the cosign signature bundle written by
  `scanner/services/sbom_pipeline.py`) — every deleted SBOM scan leaked its
  artifacts on disk forever. Fixed with `shutil.rmtree`, idempotent. 2 new
  tests. Also manually cleaned up 3 orphaned `output/` dirs left from testing
  before the fix existed.

### 3. Missing back button on finding-detail pages
User-reported: no way back from a finding's detail page in the packaged exe
(no browser chrome). `/finding/$findingId` (the real, reachable one — hit via
the eye icon on any code-scan findings table) now has a
`router.history.back()` button, matching the pattern already used on
scan-detail pages. Live-verified: click in, click back, lands on the correct
findings list.
⚠️ Also patched `/finding/sbom/$sbomfindingId` for consistency, but **that
route is dead code** — nothing in the app links to it (SBOM findings use an
in-page modal dialog instead, in `scan/sbom.$sbomscanId/findings.tsx`). Not
visually verified since it's unreachable through normal navigation.

### 4. Pagination state persisted in the URL
User-reported: every table pagination was React-local `useState`, so refresh
or navigate-away-and-back silently reset to page 1. New shared hook
`client/src/hooks/use-table-query-state.ts` reads/writes `?page=`/`?q=` via
TanStack Router's `useSearch({ strict: false })` + `useNavigate({ to: '.',
replace: true })`. `GenericTable` gained an `initialQuery` prop so the visible
search box also restores (it previously owned fully uncontrolled internal
state). Wired into all 7 real API-backed tables: `project/list`,
`users/list`, `project/$projectId/codescan`, `project/$projectId/sbomscan`,
`scan/$scanId/findings`, `scan/sbom.$sbomscanId/findings`,
`scan/sbom.$sbomscanId/licenses`. Skipped `scan/sbom.$sbomscanId/
dependencies.tsx` — it's static demo data, not a real API call.
Live-verified on a real 22-row/3-page table: paged to 2, refreshed, landed on
page 2 (not page 1).

### 5. Scan concurrency — investigated, no code change
User asked how the scan queue works / whether multiple scans run at once.
Answer: **no real queue exists.** `local/api_app/views/scan_views.py` has a
single module-level `scan_thread`/`scan_thread_lock` pair shared by *all
three* scan-creation views (code, SBOM-from-zip, SBOM-from-existing-file) —
only one scan runs app-wide at a time; a second request gets an immediate 409,
it does not wait its turn. `scanner/views.py` has a *different*
`ScanCreateView` supporting real concurrency (`MAX_CONCURRENT_SCANS=10`,
independent threads) but `scanner/urls.py` is never `include()`d in
`codesense/urls.py` — it's dead/unreachable code. Per-finding LLM
verification *within* one scan is parallelized (`LSAST_MAX_WORKERS`,
`lsast_scanner.py`) — that's orthogonal, not inter-scan concurrency. This
investigation directly informed bug #6 below.

### 6. Scan-creation orphaned-row bug (found via the concurrency investigation)
Real bug, reproduced from something the user hit live: uploading a corrupt
zip (or hitting the single-scan lock from #5) left the just-created
Scan/SbomScan row **stuck at `status="queued"` forever** — the error-response
paths in `ScanCreateView`/`SbomCreateView`/`GrypeCreateView`
(`local/api_app/views/scan_views.py`) never updated the row's status before
returning. Found the user's actual stuck scan ("badzip", 2+ hours queued) via
the new Recent Activity feed (#1) and fixed the live DB row too. Fixed all 3
views' `BadZipFile`/generic-exception/thread-lock-conflict branches to mark
`"failed"` + clean up the temp dir before returning. 5 new tests
(`test_scan_views.py`), each reproducing the exact bug via a real
`APIRequestFactory` request bypassing only the auth decorator.
**Compounding UX fix**: `uploadzip.tsx`/`uploadsbom.tsx` previously only
`console.error`'d on failure — now show a `sonner` toast with the actual
server error (matches the existing pattern in `login.tsx`).

### 7. PIA (Privacy Impact Assessment) case coverage — new feature
User asked whether the scanner detects privacy/PII-related findings for their
own compliance review. Answer was **no** (confirmed by grep: zero CWE-359
rules anywhere in the bundled ruleset; the only PII-adjacent rules were
generic insecure-transport ones that mention "PII" in passing). Built:
- **New rule pack** `server/scanner/rules/privacy/` — deliberately *not*
  inside the upstream-cloned `SEMGREP_RULES_DIR` tree (which
  `stage_semgrep_rules.py` wholesale `rmtree`s + replaces on every re-stage —
  custom rules living there would get silently wiped).
  - `generic/hardcoded-pii-literals.yaml` — SSN/credit-card-shaped literals,
    any language (`languages: [regex]`), CWE-359.
  - `<lang>/pii-logging-exposure.yaml` for all 8 languages the eval suite
    already covers (python, javascript, java, php, go, ruby, csharp,
    kotlin) — flags PII-named values (ssn, email, credit_card, dob, passport,
    phone_number, bank_account, etc.) passed directly to logging/print
    calls, CWE-532.
- **Detector wiring**: `run_semgrep()` (`scanner/rag/semgrep_detector.py`)
  now adds a second `--config <privacy_rules_dir>` on top of whichever main
  rules source is in play (bundled dir or cloud registry packs). New
  `get_privacy_rules_dir()` in `scanner/services/tools.py`, resolved via
  `__file__` (same pattern as `cosign_paths()`) so it works unchanged in
  dev-from-source and frozen builds. 3 new detector-wiring tests.
- **Packaging**: `server/codesense.spec` gained a `datas` entry so the frozen
  backend actually ships the new rule files (verified the collector finds
  all 9 files).
- **Eval coverage**: 16 new curated safe/unsafe fixture pairs (one per
  language) added to `scripts/eval/data/curated/manifest.json`, following the
  exact existing pattern.
- **Verified via the real eval gate, not just unit tests**:
  `run_eval.py --dataset curated --tier detector --gate` →
  **Precision 1.000 / Recall 1.000 / F1 1.000 / FP-rate 0.000**, TP=15 FP=0
  FN=0 TN=15 (14 pre-existing cases + 16 new ones, all correct, zero
  interference with existing rules). Per-language recall 1.000 across all 8.
- **Known, documented limitation** (not hidden): the logging rule matches on
  identifier *name* substrings, so it can false-positive on a non-PII
  identifier that happens to contain a PII-ish word (e.g.
  `emailTemplateEngine`). Same class of imprecision the rest of the detector
  already has — the downstream LLM verifier stage exists exactly to triage
  this, not a new failure mode.
- **Explicitly scoped out this pass** (told to the user, not silently
  dropped): cleartext PII storage (CWE-312) and PII-over-plaintext-transport
  (CWE-319) — both need real dataflow analysis to keep false-positive rates
  reasonable; pattern-only rules for these would be materially lower quality
  than what shipped. Worth a dedicated follow-up if wanted.

## Repo / build state

- Branch `week6`, still **30 commits ahead of `origin/week6`** — unchanged,
  nothing pushed this session either. **Do not push without explicit OK.**
- **Nothing from this session committed** — 63 changed/untracked paths per
  `git status --short`. Natural commit grouping, if/when asked to commit:
  dashboard (item 1), SBOM API fixes (item 2), back-button (item 3),
  pagination (item 4), scan-orphan fix (item 6), PIA rule pack (item 7) — 6
  logically separate commits, matching how each was built/tested
  independently.
- Pre-existing, unrelated, already-uncommitted before this session — still do
  NOT touch without asking: `client/src-tauri/tauri.conf.json`,
  `client/src/hooks/use-asset-setup.{ts,test.ts}`, `docs/RELEASE-NOTES.md`,
  `server/run_dev.ps1`.
- Untracked, harmless, pre-existing: `app_stderr.log`, `app_stdout.log`,
  `client/.env.development`, `client/src-tauri/resources/`,
  `server/local/api_app/views/.gitignore`, both prior handoff docs.
- **ISec delivery zips are now stale** relative to this session's work — none
  of items 1–7 are in any built/shipped artifact. If another client delivery
  is needed, the full rebuild pipeline (refreeze backend if `server/`
  changed → copy into `client/src-tauri/binaries/` → `tauri build
  --no-bundle` → rezip) needs to run again from current `week6` tip.
- **Dev-DB admin password changed this session**: the dev-from-source
  `admin@codesense.dev` account's password is now `DevPass@123` (was
  unknown/stale from a prior session). Reset via direct DB write +
  `account_integrity.register_user()` re-registration (the account-integrity
  anti-tamper fingerprint must be re-registered after any direct password
  edit, or login 401s with "protected CodeSense account details were
  modified locally" — same mechanism as the license-tampered bug from the
  03 handoff, just triggered by me this time, not the client).
- Environment gotcha, still true: any Bash/PowerShell read of a path under
  `%LOCALAPPDATA%` from Claude's own shell tools on this dev machine is
  silently redirected to a sandboxed mirror, not the real file — irrelevant
  to the client's separate PC.
- Dev servers: `.claude/launch.json` has `codesense-backend` (waitress,
  :8586, **no hot-reload** — restart after any backend edit),
  `codesense-frontend` (vite, :5173, HMR works), `codesense-llm` (not needed
  for anything in this session). Not guaranteed still running — start fresh
  if picking this up in a new session.

## Carried-over open items (from the 04 handoff, NOT touched this session)

1. Whether `reg delete "HKCU\Software\CodeSense" /v license /f` actually
   resolved the client's "License validation failed — read-only mode" bug —
   still unconfirmed.
2. The client's exact SBOM-scan error text — still not obtained. The
   suspected root cause (cosign keypair never auto-generated on a fresh
   install, since `init_sbom_signing` is a manual-only Django command) is
   still just a theory, not fixed.

## Next goals

1. **Ask the user** (a) whether they want the 6 logical groups above
   committed now, and if so whether as 6 separate commits or fewer, and
   (b) whether the two carried-over client-PC items (above) are still live
   or resolved by other means since the 04 handoff.
2. If picking PIA work back up: implement CWE-312 (cleartext storage) and/or
   CWE-319 (PII over plaintext transport) — scoped out this session for
   quality reasons, not forgotten.
3. W10 live-scan visual confirmation (carried all the way from the 12-week
   roadmap, `CLAUDE.md`'s W10 section) — still open, still easy to check now
   that a real scan pipeline + dashboard are both being exercised live in
   every session.
4. Systematic pass for the "no back button" UI pattern (item 3) across other
   pages, since the user flagged it as a general exe/no-browser-chrome
   concern, not a one-page fix — only the finding-detail page was checked
   this session.

## How to apply this handoff

Read `CLAUDE.md` for architecture, then `docs/handoff/04-2026-07-20-client-
delivery-and-ui-goals-handoff.md` for the state going into this session, then
this file for what changed since. Start next session by asking the user the
two questions in "Next goals" item 1 before touching git, since 63 files of
uncommitted work across 6 unrelated features need explicit direction on
how to group/commit — don't guess.
