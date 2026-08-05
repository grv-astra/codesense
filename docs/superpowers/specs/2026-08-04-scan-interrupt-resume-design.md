# Code Sense — Scan Interrupt Handling & Resume (+ Live Findings/Progress)

- **Date:** 2026-08-04
- **Status:** Approved design (pre-implementation)
- **Author:** Brainstormed with Claude
- **Repo:** `yacm`, `server/` (Django backend, LSAST pipeline)

## 1. Problem statement

A client asked for interrupt handling / task resumption on scans — they don't want a failure to
force a full re-scan. Tracing the current code confirmed the concern is real and worse than just
"failures aren't resumable":

- **Everything is deleted on every exit path.** `ScanCreateView`/`GitHubRepoScanView`'s
  `run_scan()`/`run_github_scan()` (`server/local/api_app/views/scan_views.py`) always
  `shutil.rmtree(temp_dir)` in a `finally` block — on success **and** on failure. There is
  currently no way to retry without re-uploading the zip or re-supplying GitHub credentials from
  scratch, independent of how much LLM work had already completed.
- **LLM work is thrown away in one shot.** `lsast_scan_folder()`
  (`server/scanner/rag/lsast_scanner.py`) computes `outcomes = list(ex.map(...))` — every finding
  must finish its verify+enrich LLM call (the ~30s/finding bottleneck, single CPU slot per
  `CLAUDE.md`) before **any** of them are persisted. If something throws before the whole batch
  drains, everything computed so far — even if 95 of 100 findings were already fully verified — is
  lost.
- **A killed process leaves permanent orphans.** If the app crashes, is force-quit, OOM-killed, or
  loses power mid-scan, no exception handler runs at all. The `Scan`/`SbomScan` row stays at
  `"queued"`/`"in_progress"` forever; the temp dir leaks; and if `TRIAL_MODE=true`, that row
  permanently occupies a trial slot (`trial.in_progress()` counts `("queued", "in_progress")` with
  no timeout). Nothing in the codebase detects or reconciles this — confirmed via a repo-wide
  search for `stale|reconcile|orphan|heartbeat|resume|checkpoint`, zero hits.
- **Findings and progress are both invisible until the very end**, for the same underlying
  reason as the LLM-loss issue above: nothing is persisted, and `files_scanned`/`total_files`
  (which drive the progress %) are never updated during the detection+verification phase — only
  at the final `update_progress()` call in `scan_folder()`.

## 2. Goals / non-goals

### Goals
- Code scans only (zip + GitHub, the LSAST pipeline). Survive three interrupt scenarios: process
  crash, explicit user cancel, and transient failure (LLM host unreachable, network drop, a single
  bad file). On retry, never re-run the expensive per-finding LLM work for findings already
  verified.
- Resume is **manual only** — an explicit user action, for both a crash-interrupted scan and a
  user-cancelled one. No silent auto-continuation on app relaunch.
- Findings appear via the existing findings API as soon as they're verified, not only once the
  whole scan completes. Progress % climbs continuously through the detection+verification phase.

### Non-goals
- SBOM/Grype pipeline resume — different shape (a sequential step-chain, not a per-finding loop),
  and re-running syft/grype/grant from scratch is already fast. Explicitly out of scope per this
  session's scoping decision.
- Automatic/silent resume on app startup — considered and rejected in favor of manual resume (see
  §3).
- True completion-order (`concurrent.futures.as_completed`) streaming — submission-order streaming
  via `ex.map()` is enough to fix the "stuck at 0% until the end" problem without touching the
  existing order-preservation guarantee the W6 tests rely on.
- Caching/reusing raw Semgrep detector output across a resume (rejected "Approach B" — see §3).
  AST metrics and detection are cheap and deterministic; only the per-finding LLM step needs a
  checkpoint.
- Persisting a GitHub token for later re-cloning — avoided entirely (see §3): the retained
  extracted folder serves both zip- and GitHub-sourced scans identically on resume.

## 3. Locked decisions (from brainstorming)

| Topic | Decision |
|-------|----------|
| Scope | Code scans only (zip + GitHub / LSAST pipeline); SBOM/Grype excluded |
| Interrupt scenarios covered | All three: crash, explicit cancel, transient failure — general resilience |
| Resume trigger | Manual only, for both `interrupted` and `cancelled` — no auto-resume on app startup |
| Checkpoint granularity | Per-finding fingerprint (file_path + line + rule_id). AST + detector steps are always re-run — fast, deterministic, not worth checkpointing |
| Rejected: full pipeline checkpoint | Caching raw Semgrep output adds cache-invalidation/corruption complexity for a step that's already cheap relative to the LLM step |
| Rejected: file-level checkpoint | `run_semgrep()` is one subprocess call over the whole folder today, not per-file; building per-file invocation would be a bigger change than the rest of this feature for a coarser result |
| Source retention | Extracted folder moves from `tempfile.mkdtemp()` to a durable `media/scans/<scan_id>/source/`, kept until the scan reaches a real terminal, non-resumable state |
| GitHub re-fetch | Never needed — the retained extracted folder means resume never re-clones or re-holds a token |
| Live findings | Persist each finding as its `ex.map()` slot completes, instead of after `list(ex.map(...))` fully drains |
| Live progress | Reuse the existing `scanned`/`total` progress fields, repurposed to finding-verification counts during the detection+verification phase |

## 4. Architecture

```
Current (all-or-nothing):
  POST /create ──▶ Scan row (queued) ──▶ extract to tempfile.mkdtemp()
    ──▶ background thread: AST ──▶ detect ──▶ [ list(ex.map(verify+enrich)) ]  <- blocks until ALL done
        ──▶ persist all findings ──▶ status=completed
    ──▶ finally: shutil.rmtree(temp_dir)   <- ALWAYS, even on failure/crash-adjacent exceptions
  Process killed at any point ──▶ row stuck at queued/in_progress forever, temp dir leaked,
                                   nothing else runs (no exception handler fires)

New:
  POST /create ──▶ Scan row (queued) ──▶ extract to media/scans/<scan_id>/source/ (durable)
    ──▶ background thread: AST ──▶ detect+dedupe ──▶ fingerprint each raw finding
        ──▶ for result in ex.map(verify+enrich):     <- persist AS EACH becomes ready
              save Finding (with fingerprint) ──▶ update_progress(scanned+=1, total=N)
    ──▶ status=completed ──▶ ONLY NOW: cleanup source_path

  Backend restart (crash recovery) ──▶ run_server.py startup reconciliation:
    any Scan row still queued/in_progress ──▶ relabel "interrupted" (source_path retained,
    no processing started automatically)

  User clicks Cancel ──▶ cancel_requested=True (DB, durable) + in-memory Event set
    ──▶ loop notices between findings ──▶ status="cancelled" (source_path retained)

  User clicks Resume (on "interrupted" or "cancelled") ──▶ ScanResumeView:
    re-run AST + detect+dedupe over retained source_path ──▶ fingerprint fresh findings
    ──▶ diff against fingerprints already persisted for this scan_id ──▶ only unmatched
        findings enter the verify+enrich loop ──▶ persist incrementally as above
    ──▶ status=completed ──▶ cleanup source_path
```

## 5. Components

### 5.1 Data model changes (`server/local/api_app/models/orm.py`, new migration)
- `Scan.status`: vocabulary grows to include `"interrupted"` and `"cancelled"`, alongside the
  existing `queued`/`in_progress`/`completed`/`failed` (free-text `CharField`, no enum migration
  needed at the DB level — just documented allowed values).
- `Scan.source_path` (new `CharField`, blank/null once cleaned up): durable path to the retained
  extraction directory, replacing the throwaway `temp_dir` variable.
- `Scan.cancel_requested` (new `BooleanField`, default `False`): written synchronously when the
  user requests cancellation, so a crash in the gap between "user clicked cancel" and "the loop
  noticed" is still correctly classified on the next reconciliation pass.
- `Finding.fingerprint` (new `CharField`, indexed): `sha256(file_path + start_line + rule_id)`,
  computed once per raw detector finding, before the expensive verify+enrich call — used to diff
  "already done" findings on resume.

### 5.2 `server/scanner/rag/resume.py` (new module)
- `fingerprint(sf) -> str`: stable hash from a raw Semgrep finding's `file_path`/`start_line`/
  `rule_id`. Pure function, unit-testable in isolation.
- `already_done_fingerprints(scan_id) -> set[str]`: query of persisted `Finding.fingerprint`
  values for a scan.
- `find_orphaned_scans() -> QuerySet[Scan]`: scans still `queued`/`in_progress` — by construction,
  crash leftovers from a prior process, since a fresh process hasn't started anything yet.

### 5.3 `server/local/api_app/views/scan_views.py` changes
- `ScanCreateView`/`GitHubRepoScanView`: extraction target becomes `media/scans/<scan_id>/source/`
  instead of `tempfile.mkdtemp()`. Two distinct cleanup points, not one:
  - **Pre-extraction failures** (`zipfile.BadZipFile`, an I/O error while saving/extracting) keep
    their existing immediate cleanup and end in `status="failed"` — there is no usable
    `source_path` yet, so nothing is resumable, no behavior change here.
  - **The background thread's `finally: shutil.rmtree(...)`** (today runs unconditionally once
    extraction has already succeeded) is removed. Once a real `source_path` exists, *any* outcome
    other than a clean `completed` — an uncaught exception from the LSAST pipeline, a crash, an
    explicit cancel — leaves `source_path` intact and ends the row in `"interrupted"` (see below),
    never `"failed"`. `"failed"` is reserved for the pre-extraction case above, where resuming
    would mean nothing more than starting over anyway.
- New `ScanResumeView` (`POST /api/scan/<scan_id>/resume/`, `@require_permission("create_scan")` —
  it starts new scan work, same gate as the create views): validates `source_path` still exists
  and the row is `interrupted` or `cancelled`, then starts a background thread through the *same*
  `scan_thread`/`scan_thread_lock` gate a fresh scan uses — no new locking logic.
- New `ScanCancelView` (`POST /api/scan/<scan_id>/cancel/`, `@require_permission("delete_scan")` —
  it stops/discards in-progress work, same permission tier as deleting a scan): sets
  `cancel_requested=True` in the DB and, if this scan is the one currently running, sets an
  in-memory `threading.Event` from a small registry alongside the existing `scan_thread`/
  `scan_thread_lock` globals (same module — same category of process-lifetime synchronization
  state).
- Reconciliation call wired into `server/run_server.py`'s `main()`, right after
  `call_command("migrate", ...)` and before `serve(...)` starts — this is the one place that runs
  exactly once per real server process launch, never during `manage.py test` or an arbitrary
  management command (confirmed by reading the actual entrypoint).

### 5.4 `server/scanner/rag/lsast_scanner.py` changes
- `lsast_scan_folder()` gains an optional `skip_fingerprints: set[str] = frozenset()` parameter.
  Every raw finding gets `fingerprint()` computed up front; findings whose fingerprint is in
  `skip_fingerprints` are excluded before entering the `ThreadPoolExecutor`/serial loop.
- The `outcomes = list(ex.map(...))` line is removed; the persist loop iterates `ex.map(...)`
  directly (or the serial list comprehension, for `LSAST_MAX_WORKERS=1`), persisting each result —
  with its fingerprint — the moment it's ready, instead of waiting for the full batch.
- `update_progress(scan_id, scanned=<processed so far>, total=<len(findings to process)>)` is
  called alongside the existing `findings=len(visible)` update in the same loop, so
  `Scan.files_scanned`/`total_files` (already wired through to the UI's percentage calculation)
  climb continuously instead of jumping from 0 to the final value.

### 5.5 `server/scanner/rag/scanner.py` (`scan_folder`) changes
- Accepts the retained `source_path` for both a fresh run and a resume — no branching needed at
  this layer beyond passing `skip_fingerprints` through to `lsast_scan_folder`.
- The AST-analysis failure branch (currently `update_progress(..., status="failed", ...)` when
  `analyze_folder()` raises) changes to `status="interrupted"` — per the §5.3 rule, this failure
  happens after extraction already succeeded, so `source_path` is valid and resuming is safe (worst
  case it just retries AST analysis, no worse than a fresh scan).

## 6. Data flow summary

**Normal run:** unchanged shape, except extraction lands in the durable `source_path` and findings
persist as they're verified rather than in a final burst. `source_path` is only deleted after
`status=completed`.

**Crash:** process dies; row is wherever it was. On next real server start, `run_server.py`'s
reconciliation finds it via `find_orphaned_scans()` and relabels it based on `cancel_requested`:
`"cancelled"` if the user had already asked to stop it before the crash, `"interrupted"` otherwise
(source retained either way, already-persisted findings intact from the live-persist change in
§5.4). Nothing auto-runs in either case.

**Explicit cancel:** `ScanCancelView` marks `cancel_requested`; the running loop notices between
findings and exits cleanly to `status="cancelled"`. Already-persisted findings and `source_path`
are retained exactly as in the crash case.

**Resume (either case):** `ScanResumeView` re-runs AST + detection over the retained
`source_path`, fingerprints the fresh finding set, filters out anything already persisted for this
`scan_id`, and only the remainder goes through the LLM verify+enrich loop. `Scan.findings` reflects
the union of prior + newly-processed. `source_path` is cleaned up only now.

## 7. Error handling

- **Source missing at resume time** (manual deletion, disk cleanup, or a scan predating this
  feature): `ScanResumeView` checks existence before starting; if absent, returns a clear error and
  leaves the row as-is — the user's only option is to discard and start a fresh scan, not a silent
  crash-loop.
- **Cancel racing a crash**: `cancel_requested` is written to the DB before the in-memory `Event`
  is set, so a crash in that gap is still correctly reconciled as `"cancelled"` (not
  `"interrupted"`) on next startup — same manual-resume behavior either way, but the status still
  tells the user why it stopped.
- **Detector nondeterminism across a resume** (e.g. a rules-pack update installed between the
  original run and the resume): new fingerprints that don't match anything persisted are processed
  as new findings — correct, conservative behavior. Fingerprints that no longer reproduce just
  leave the earlier persisted `Finding` rows in place, the same as any two scans run under
  different rule versions would differ.
- **One-scan-at-a-time interaction**: resume goes through the exact same `scan_thread`/
  `scan_thread_lock` gate a fresh scan does (the fix from earlier this session) — no new
  concurrency logic, no way for a resume to collide with a concurrently-submitted new scan.
- **Trial accounting**: `interrupted` is added to `trial._ACTIVE_STATUSES` (a pending-resume scan
  is genuinely unfinished business and should keep occupying its slot); `cancelled` is not — no
  slot was ever completed, matching how `failed` behaves today.

## 8. Testing

- **Unit**: `fingerprint()` stability (same file/line/rule_id → same hash; any difference → a
  different hash) and the resume-filter logic (given raw findings + a set of already-persisted
  fingerprints, the correct unmatched subset is selected).
- **Integration — crash + resume**: force an exception partway through a batch in a test, call the
  reconciliation function directly (simulating a process restart), resume, and assert: only the
  remaining findings are re-verified (via call-count on a mocked LLM verify), the final finding
  count is the union of both runs, and status ends `completed`.
- **Integration — cancel + resume**: cancel mid-scan, assert `status="cancelled"` and remaining
  findings untouched, then resume and assert it completes correctly with no re-verification of
  already-persisted findings.
- **Integration — source missing at resume**: delete `source_path` manually, call
  `ScanResumeView`, assert a clean error response and no crash.
- **Integration — live findings/progress**: assert a `Finding` row exists in the DB *before* the
  full batch finishes (not just at the end), and `Scan.files_scanned` climbs across the run rather
  than jumping straight from 0 to the final total.
- **Regression**: the full existing suite (228 tests as of this session, including the
  `scan_thread`-conflict tests touched earlier) stays green.
