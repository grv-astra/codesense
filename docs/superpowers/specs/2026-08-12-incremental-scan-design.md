# Incremental scan — Design

2026-08-12. Scoped in a brainstorming session per handoff `09-2026-08-11-vcredist-webview2-cosign-grype-login-fixes-handoff.md`'s "Next priorities" #1 (incremental scan), the second of two SUPER PRIORITY items — priority 1 (CI/CD scan trigger via project-scoped API keys, see `2026-08-11-cicd-api-key-scan-trigger-design.md`) shipped first per the user's explicit build-order call.

## Goal

On a repeat scan of a project whose source hasn't fully changed since its last scan, only re-run the detection/verification pipeline on files that actually changed — carry forward findings for everything else — instead of re-scanning the whole project every time. Applies uniformly to both scan trigger paths (zip upload and GitHub-repo clone), automatically, with no new API surface.

## Background (confirmed by code survey this session)

- The scan pipeline (`lsast_scan_folder()` in `server/scanner/rag/lsast_scanner.py`) runs a full directory walk every time — `run_semgrep(folder_path)` hands the whole folder to OpenGrep's own walker, with no comparison against any prior run. No file-level diffing mechanism exists anywhere in the codebase today.
- `server/scanner/rag/resume.py` already has a fingerprinting mechanism (`sha256(file_path + start_line + rule_id)`), but it's scoped to resuming **one interrupted scan** (skipping findings already persisted for that same `scan_id`) — a different problem from detecting source changes between two separate, completed scans.
- `Scan` (`server/local/api_app/models/orm.py`) has no commit/version/manifest field today; `Finding` has a `fingerprint` field but it's only meaningful within a single scan's resume context. `ScanModel.find_by_project` already gives scan history ordered by `created_at`, usable as the basis for baseline lookup.
- **Blocking bug found during this scoping session**: `Finding.file_path` is stored as the detector's raw, **absolute** path — which is always under `%TEMP%\codesense-media\scans\<scan_id>\source\...`, with a different `<scan_id>` embedded on every single scan. Confirmed empirically (OpenGrep reports absolute paths when given an absolute target) and by tracing the full chain: `semgrep_detector.py` → `finding_normalizer.py` → persistence → frontend, with no path normalization anywhere. This is also a client-facing leak (the raw temp path is shown directly in the UI, e.g. `UpdatedFinding.tsx`) — but critically, it means `Finding.file_path` can **never** match across two different scans, even for byte-identical unchanged files, which would silently defeat any carry-forward-by-path matching. This must be fixed as part of this feature, not as a follow-on — see Task 0 below.

## Decisions made this session (with rationale)

1. **Build order**: this follows the CI/CD API-key feature (already shipped), per the user's earlier explicit call.
2. **Change-detection trigger: content-hash manifest only**, not git-diff. Rationale: zip uploads have no git history to diff against, and both scan types (decision 3 below) need uniform support — a single mechanism with no special-casing beats a hybrid that only pays off for repos with git history already available.
3. **Both scan types get incremental support** (zip upload and GitHub-repo clone), not GitHub-only-first. Confirmed explicitly by the user in an earlier round this session.
4. **Ruleset staleness invalidates the baseline.** If the bundled Semgrep ruleset changed since a project's last scan, the next scan runs as a full scan even if source is unchanged — a rare, one-time-per-rule-update fallback, not a standing policy that negates the optimization in the common case. Confirmed explicitly by the user after discussing the tradeoff.
5. **Carry-forward findings: reuse persisted findings as-is** for unchanged files — no re-detection, no re-verification. Correctness against ruleset drift is covered by decision 4; correctness against verifier/model drift between scans is an accepted tradeoff (see "Explicitly out of scope" below).
   - **Considered and rejected for now**: not duplicating carried-forward findings at all, instead reconstructing "the complete finding set for scan N" at read time by walking back through baseline scans. Rejected because it makes every baseline scan load-bearing forever (can't delete/archive scan N-1 without breaking scan N's ability to show its findings, absent a separate compaction mechanism), and query complexity grows with how long a project's scan history gets. Copy-forward keeps every scan simple, self-contained, and trivially queryable/deletable on its own — worth the storage tradeoff (see the flagged concern below).
   - **Provenance without full non-duplication**: `Finding` gains a `first_seen_scan_id` field. A freshly-detected finding points to its own scan. A carried-forward copy keeps the **original** `first_seen_scan_id` (not the immediate parent's) — so after many consecutive incremental scans, a finding still correctly shows "first seen in scan 1," not just "seen in the last scan." Gives the trackback/provenance the user actually wants, cheaply, without chain-walking fragility.
   - **Flagged, not addressed now**: copy-forward means a project scanned frequently (e.g. via the CI/CD API-key feature triggering a scan on every push) with a large, stable finding set will duplicate those finding rows on every scan. Not urgent — finding rows are small, so this is bounded row growth, not a storage crisis — but a real cost that compounds with automated, frequent scanning. Deliberately deferred; a natural fit for a later retention/compaction pass (same spirit as the already-spawned source-directory cleanup item), not this feature.
6. **Automatic, not opt-in.** Any scan for a project with a valid baseline (completed prior scan, matching ruleset version) automatically runs incremental — no new request parameter, no UI change. Falls back to a full scan whenever no valid baseline exists (first scan, prior scan not completed, or ruleset changed).
7. **`Finding.file_path` normalization is a prerequisite, folded into this plan as its first task** (not shipped separately first, not deferred). Without it, the carry-forward mechanism's path-matching is broken from day one. Fixing it here also resolves the client-facing absolute-path leak as a side effect.
8. **Source-directory retention/cleanup is explicitly out of scope for this feature** — flagged as a separate, independent concern (spawned as its own background task during this session) since incremental scanning never needs the *old* source content, only the old *manifest* (hashes), so this feature has no dependency on whether/how source directories get cleaned up.

## Architecture

### Task 0 (prerequisite): normalize `Finding.file_path`

`normalize()` in `server/scanner/rag/finding_normalizer.py` gains a `scan_root: str` parameter — the same `folder_path` already threaded through `lsast_scan_folder()` → the detector. Before building the `file_path` string (currently `f"{f.file_path} [{f.start_line},{f.end_line}]"`), strip `scan_root` from `f.file_path` via `os.path.relpath`, normalize path separators to `/` (so the stored value is platform-consistent — the codebase already supports macOS builds per `CLAUDE.md`), and use the resulting relative path in its place. This changes what's stored in `Finding.file_path` for **every** scan going forward (not just incremental ones), and fixes the temp-path leak already visible in the frontend today.

### Data model

Two new fields on `Scan` (`server/local/api_app/models/orm.py`):
- `file_manifest` — `JSONField`, `{relative_file_path: sha256_content_hash}` for every file present at scan time. Blank/null on scans that predate this feature and on scans where computing it isn't meaningful (e.g. failed scans).
- `ruleset_version` — `CharField`, a hash of the bundled Semgrep rules directory contents, computed once (cached, not re-hashed per scan — re-hashing a rules directory on every single scan start would be wasteful) and stamped onto every `Scan` row at creation.

One new field on `Finding`:
- `first_seen_scan_id` — `CharField`, nullable/blank for pre-existing findings. Set to the finding's own `scan_id` when freshly detected; preserved unchanged (not reset to the immediate parent) across every subsequent carry-forward copy, so provenance survives arbitrarily many consecutive incremental scans. See decision 5's "Provenance without full non-duplication" note above.

### New module: `server/scanner/rag/incremental.py`

Pure, independently testable functions with no DB or detector coupling:
- `compute_file_manifest(folder_path) -> dict[str, str]` — walks the source tree, hashes each file's content (SHA-256), keys by path relative to `folder_path` (same normalization as Task 0, so manifest keys and `Finding.file_path` values are directly comparable).
- `find_baseline_scan(project_id, ruleset_version) -> Scan | None` — the most recent scan for `project_id` with `status="completed"`, a non-empty `file_manifest`, and `ruleset_version` matching the current one. `None` if no such scan exists.
- `diff_manifests(old, new) -> (changed_or_new, unchanged, removed)` — three sets of relative paths. `changed_or_new`: hash differs between old/new, or the path is new. `unchanged`: same hash in both. `removed`: present in `old`, absent from `new` (needs no further handling — it simply won't appear in the new source, so nothing gets scanned or copied for it).

### Orchestration

Invoked from `scan_folder()` in `server/scanner/rag/scanner.py` — the existing layer that already owns scan lifecycle/status before delegating to `lsast_scan_folder()`. Sequence per scan:
1. Compute (or reuse the already-cached) current `ruleset_version`.
2. `find_baseline_scan(project_id, ruleset_version)`. None found → proceed exactly as today (full scan), then persist the new `file_manifest`/`ruleset_version` on this scan for future baselining.
3. Baseline found → `compute_file_manifest(folder_path)`, `diff_manifests(baseline.file_manifest, new_manifest)`.
4. Restrict the detector pass to `changed_or_new` files only (see the open implementation question below on how OpenGrep invocation needs to change to support this).
5. Run the normal pipeline (detector → normalize → verify → fuse → enrich → persist) only over `changed_or_new` files' results.
6. Bulk-copy `Finding` rows from the baseline scan where `file_path` is in `unchanged` into the new scan (new `id`/`scan_id`, all other fields copied as-is except `first_seen_scan_id` — preserved from the source row if already set, otherwise set to the baseline scan's id) — no detector invocation, no LLM verifier call for these.
7. Persist the new `file_manifest`/`ruleset_version` on the new scan.

## Error handling

- Manifest computation failure (e.g. unreadable file) — degrade to treating that file as `changed_or_new` (safe default: over-scan rather than silently skip), don't fail the whole scan.
- No baseline found for any reason (first scan, prior scan not completed, ruleset changed) — transparently falls back to today's full-scan behavior; this is not an error path, it's the expected common case for a project's first scan.
- Bulk-copy of carried-forward findings failing partway — should not leave the new scan in a half-copied state; wrap in a transaction so it's all-or-nothing, falling back to full detection for the affected files if the copy can't complete (exact fallback mechanics to be nailed down at plan time).

## Testing

- Unit tests for `compute_file_manifest`, `find_baseline_scan`, `diff_manifests` in isolation (no DB/detector needed for the first two; `find_baseline_scan` needs a DB fixture).
- Unit tests for the `finding_normalizer.py` path-normalization change — absolute path in, relative path out, across both Windows-style and POSIX-style inputs.
- Integration test: two sequential scans of the same project, second scan with one file changed, one unchanged, one removed, one added — assert the new scan's findings include fresh detection for changed/new files, carried-forward findings for the unchanged file, and nothing for the removed file's old findings.
- Integration test: three sequential scans, source unchanged across all three — assert the third scan's carried-forward findings still have `first_seen_scan_id` pointing to the first scan, not the second (provenance survives multiple carry-forward hops, not just one).
- Integration test: ruleset-version bump between two scans — assert the second scan runs as a full scan (no carry-forward) despite unchanged source.
- Regression: existing full-scan test suite must stay green — a project's first-ever scan (no baseline) must behave identically to today.

## Explicitly out of scope / deferred (YAGNI)

- Re-verifying carried-forward findings through the LLM verifier (decision 5) — accepted as a tradeoff; only ruleset-version drift is guarded against, not verifier/model drift between scans.
- Any new API parameter or UI affordance to control incremental vs. full scanning (decision 6) — fully automatic for this pass.
- Source-directory retention/cleanup policy (decision 8) — flagged as an independent, already-spawned background task, not part of this feature.
- **Finding-row storage growth from repeated copy-forward across many scans** (decision 5) — explicitly deferred, not solved here. Frequent automated scanning (e.g. via the CI/CD API-key feature) on a project with a large, stable finding set will duplicate those rows on every scan; bounded and not urgent today, but flagged for a future retention/compaction pass if it turns out to matter at real scale.
- Git-diff-based change detection (decision 2) — content-hash manifest is the sole mechanism.
- Rename detection — a renamed file is treated as "old path removed + new path added" (full detection on the new path), which is the safe default; no special-casing planned.

## Open items for the implementation plan

- **Whether OpenGrep's CLI can be scoped to an explicit file list**, or whether restricting detection to `changed_or_new` files requires copying just those files into a scoped temporary subdirectory before invoking the detector (mirroring an existing workaround already in this codebase for a different OpenGrep/git-working-tree quirk documented in `CLAUDE.md`). Needs a quick investigation spike before the orchestration task is implemented, since it affects how step 4 above is actually built.
- Exact transaction/fallback mechanics for a partially-failed bulk-copy of carried-forward findings (error handling section, last bullet).
- Where `ruleset_version` computation is cached (in-process memoization vs. a small persisted cache keyed by a mtime/hash of the rules directory) — avoid re-hashing the rules directory on every scan start without over-engineering a cache invalidation scheme.
