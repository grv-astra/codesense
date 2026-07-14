# Code Sense — First-Run Asset Reassembly (Windows installer size workaround)

- **Date:** 2026-07-14
- **Status:** Approved design (pre-implementation)
- **Author:** Brainstormed with Claude
- **Repo:** `yacm`, `client/src-tauri/` (Tauri v2 desktop shell)

## 1. Problem statement

The Windows build cannot ship as a single installer today because two bundled assets exceed a
hard ~2GB per-file ceiling that both viable Windows installer formats enforce:

- `client/src-tauri/resources/model/astra.gguf` — 4.68GB (the bundled 7B-Instruct LLM).
- `client/src-tauri/resources/grype-db/vulnerability.db` — 2.56GB (the offline CVE database,
  a `grype db update` cache-directory snapshot staged by `scripts/build_windows.ps1`).

Verified live this session (not assumed):

- **NSIS**: the Tauri-fetched `makensis.exe` is 32-bit (confirmed via `file`) and fails with
  `File: failed creating mmap of …\astra.gguf` — a 32-bit process cannot mmap a file this large.
- **MSI/WiX**: switching `tauri.conf.json`'s `bundle.targets` to `"msi"` gets further (candle
  compiles, light.exe starts linking) but fails with
  `error LGHT0263: 'astra.gguf' is too large, file size must be less than 2147483648` (2^31 bytes)
  — the classic Windows Installer per-file CAB limit. This is a different ceiling than NSIS's, but
  it is not smaller, and WiX does **not** avoid it by default.

The client site is **fully air-gapped** (confirmed with the user) — no network access at install
time or ever afterward. This rules out any first-run-download or low-tier-model-swap mitigation;
the fix must work by splitting the existing full-size assets at build time and reassembling them
locally, with zero network dependency, before first use.

## 2. Goals / non-goals

### Goals
- Ship the **full** 7B-Instruct model and the **full** grype vulnerability DB, unchanged in
  content/quality, inside a single Windows installer.
- Work with the existing bundler (NSIS `.exe`) with no new bundled third-party binary.
- Reassembly must be fully offline, verified (checksummed), idempotent across launches, and
  recoverable from partial/corrupted state without requiring a reinstall in the common case.
- First-launch reassembly time (est. tens of seconds to a couple minutes, disk-speed dependent)
  must be visible to the user, not a silent hang.

### Non-goals
- Reducing model or grype-db size/quality (rejected — air-gapped client, no fallback fetch path).
- Changing the Windows bundler away from NSIS (WiX doesn't solve the underlying problem; not worth
  the switch).
- macOS packaging — `.dmg` has no equivalent size ceiling; this design is Windows-only.
- Shrinking on-disk footprint after install (see §3, disk footprint decision).

## 3. Locked decisions (from brainstorming)

| Topic | Decision |
|-------|----------|
| Overall strategy | Shard both large files at build time; reassemble on first launch (not low-tier model, not first-run network fetch, not loose-file/external-media installer) |
| Split/join mechanism | Custom raw split + JSON manifest + native Rust join (not 7-Zip volumes, not installer-native multi-`Media`) |
| First-run UX | Visible progress screen in the main window until reassembly completes |
| Failure handling | Auto-retry once from scratch; if it fails again, show a specific on-screen error + manual Retry button. No silent fallback to deterministic-only scanning. |
| Disk footprint | Keep installed shards permanently (~14GB combined for these two assets, not ~7GB) — simplest, and lets a wiped/moved data dir rebuild without reinstalling |
| Bundler | Stays NSIS (`tauri.conf.json` `bundle.targets: ["nsis"]`, already reverted after the MSI experiment) |

## 4. Architecture

```
Build time (Windows only):
  astra.gguf (4.68GB) ──split_asset.ps1──▶ astra.gguf.part000..partNNN + astra.gguf.manifest.json
  vulnerability.db (2.56GB) ──split_asset.ps1──▶ vulnerability.db.part000..partNNN + manifest.json
  (original monolithic files deleted; never embedded; existing tauri.conf.json resource globs
   pick up whatever files exist in resources/model/ and resources/grype-db/ — no config changes)

First launch (client machine, fully offline):
  main.rs setup() ──background thread──▶ asset_reassembly::ensure_ready() × 2 (model, grype-db)
    reads manifest + parts from read-only install dir
    streams into %LOCALAPPDATA%\com.codesense.desktop\{model,grype-db}\<file>
    verifies sha256 while writing, reports byte progress via Tauri events
  React "first-run setup" screen shows progress until both assets ready
  ──▶ spawn_backend()/spawn_llama() now use the writable reassembled paths
      (previously resolved resources/model/astra.gguf and resources/grype-db/ directly)

Subsequent launches:
  ensure_ready() sees a verified `.done` marker + matching file size ──▶ returns immediately,
  no re-hashing of multi-GB files, setup screen resolves near-instantly
```

## 5. Components

### 5.1 `scripts/split_asset.ps1` (new, build-time)
- Input: a file path, target part size (default ~1.8GB — safety margin under the 2GB/2^31 boundary
  hit by both NSIS and MSI).
- Computes sha256 of the whole input file.
- Splits into `<name>.part000`, `<name>.part001`, … (zero-padded, stable sort order).
- Writes `<name>.manifest.json`: `{ "file": "<name>", "total_size": N, "sha256": "…", "part_size": N, "part_count": N }`.
- Deletes the original monolithic file.
- Invoked from `scripts/build_windows.ps1` right after the existing `astra.gguf` copy step and
  right after the existing `grype.exe db update` snapshot step — both places already know the
  final on-disk path of the large file.

### 5.2 `client/src-tauri/src/asset_reassembly.rs` (new)
- `struct AssetSpec { resource_subdir: &'static str, file_name: &'static str }` — two instances:
  one for `resources/model` / `astra.gguf`, one for `resources/grype-db` / `vulnerability.db`.
- `fn ensure_ready(app: &AppHandle, spec: &AssetSpec, progress: impl FnMut(u64, u64)) -> Result<PathBuf, ReassemblyError>`:
  1. Target = `app_local_data_dir()/<resource_subdir>/<file_name>`.
  2. Read the bundled (read-only) `manifest.json` for expected `total_size` + `sha256`.
  3. If a `<file_name>.done` marker exists, contains a hash matching the manifest, and the target
     file's size matches `total_size` → return `Ok(target)` immediately (no hashing).
  4. Otherwise: delete any stale `.tmp`, stream-copy `part000..partNNN` into `<file_name>.tmp`
     (buffered I/O, e.g. 1MB chunks), hashing incrementally and calling `progress(written, total)`
     per chunk.
  5. Compare final hash to manifest. Mismatch → delete `.tmp`, return
     `Err(ReassemblyError::ChecksumMismatch)`. Match → rename `.tmp` → final name (atomic on the
     same volume), write `.done` with the verified hash, return `Ok(target)`.
- For the grype-db asset specifically: also copy the small companion metadata files (everything in
  `resources/grype-db/` that isn't `.part*`/`.manifest.json`) into the writable grype-db directory,
  so `GRYPE_DB_CACHE_DIR` points at a complete, valid grype cache directory rather than just the
  one large file.
- `ReassemblyError` variants: `Io(std::io::Error)`, `ChecksumMismatch`, `ManifestMissing`,
  `ManifestCorrupt` — the last two indicate a packaging bug, not a transient runtime condition.

### 5.3 `main.rs` changes
- `setup()` now runs both `ensure_ready` calls (model, then grype-db — sequential, not parallel,
  to avoid doubling peak disk I/O on the same drive) on a background thread *before*
  `spawn_backend`/`spawn_llama` are called.
- Progress is emitted as Tauri events (e.g. `asset-setup-progress { asset, bytes, total }`,
  `asset-setup-complete`, `asset-setup-failed { asset, reason }`) for the frontend to consume.
- Auto-retry: on any `ensure_ready` error, delete partial output and retry once automatically. If
  the retry also fails, emit `asset-setup-failed` with the specific reason and do **not** proceed
  to spawn either sidecar until the user retries successfully.
- `spawn_backend(app, grype_db_path)` / `spawn_llama(app, model_path)` are changed to accept the
  already-reassembled writable paths instead of resolving `resources/model/astra.gguf` and
  `resources/grype-db` via `BaseDirectory::Resource` themselves.

### 5.4 First-run setup screen (new, `client/src/`)
- Small React component/route that listens for the three Tauri events above.
- Shows a progress bar (bytes across both assets) while waiting.
- On `asset-setup-failed`, shows the specific reason plus a "Retry" button that re-invokes setup.
- On `asset-setup-complete`, yields to the normal app shell.
- On every launch after the first, `ensure_ready` resolves near-instantly for both assets, so in
  practice this screen either doesn't appear or appears for a single frame.

## 6. Data flow summary

**Build time:** stage full-size asset → split into `.partNNN` + manifest → delete monolithic
original. Repeated for both `astra.gguf` and `vulnerability.db`. No `tauri.conf.json` changes —
existing glob-based `bundle.resources` entries already stage whatever files exist in those
directories.

**First launch:** window opens showing the setup screen → background thread reassembles model,
then grype-db, emitting progress → on success, sidecars spawn with the writable paths, normal UI
takes over → on failure, one silent auto-retry, then a clear on-screen error with manual retry;
sidecars never spawn on unverified assets, and there is no silent deterministic-only fallback.

**Subsequent launches:** `.done` marker + cheap size check short-circuits reassembly; setup
resolves immediately.

## 7. Error handling

- Every reassembly writes to `<file>.tmp` and only renames to the final name after a verified
  checksum match — a crash, power loss, or forced quit mid-reassembly never leaves a file that
  looks valid. The next launch detects the missing final file/marker and cleanly redoes the work
  from the always-intact, read-only installed parts.
- Exactly one automatic retry per asset per launch attempt; a second consecutive failure surfaces
  a specific reason (disk full / checksum mismatch / shard read error) rather than a generic
  message, since the client site is air-gapped and can't lean on remote support to diagnose a
  vague failure.
- `ManifestMissing`/`ManifestCorrupt` are treated as a packaging defect (not retryable) and should
  surface a distinct "reinstall required" message rather than looping retries against a build that
  can never succeed.

## 8. Testing

- **Unit tests (Rust, TDD)** for `asset_reassembly.rs` using small synthetic multi-part fixtures in
  a temp dir. Note: this is the **first** Rust test code in `client/src-tauri/` — there is no
  existing `#[test]`/`#[cfg(test)]` precedent in this crate to follow, so the harness (plain
  `#[cfg(test)] mod tests` with `tempfile`-style temp dirs, no new test framework dependency) is
  being introduced by this feature:
  - correct reassembly of N parts into the expected byte-identical whole file;
  - checksum match on success;
  - idempotent no-op on a second call (assert parts are not re-read once `.done` + size match);
  - a corrupted middle part produces `ChecksumMismatch`, and a subsequent call (simulating the
    orchestration-level retry) recovers cleanly from intact parts;
  - a truncated last part is detected (size mismatch against manifest) rather than silently
    accepted.
- **Build-script check** for `split_asset.ps1`: split a known test file, reassemble with a small
  verification script, diff against the original byte-for-byte. (No existing Pester/PowerShell
  test harness in this repo — a documented manual verification step is acceptable here, consistent
  with how other build-script changes in this project have been verified.)
- **End-to-end acceptance**, reusing the live-verification protocol already used for the P0 AI fix:
  real `npx tauri build`, run the built `codesense.exe` against a fresh (deleted)
  `app_local_data_dir` to simulate first launch, confirm progress events fire and both sidecars
  start only after reassembly completes; run it a second time and confirm reassembly is skipped;
  deliberately flip a byte in one installed part and confirm the retry-then-fail-with-reason path
  behaves as designed.
