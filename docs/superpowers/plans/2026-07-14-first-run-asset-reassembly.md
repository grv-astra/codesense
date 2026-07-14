# First-Run Asset Reassembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the full-size 7B model (4.68GB) and full grype vulnerability DB (2.56GB) inside a single Windows NSIS installer by splitting them into <2GB parts at build time and reassembling + checksum-verifying them into a writable per-user directory on first launch, fully offline.

**Architecture:** A new PowerShell script (`split_asset.ps1`) splits each large file into `.partNNN` shards + a `manifest.json` at build time; the existing `tauri.conf.json` resource globs pick these up automatically. A new Rust module (`asset_reassembly.rs`) streams the parts back together into `%LOCALAPPDATA%\com.codesense.desktop\{model,grype-db}\`, verifying sha256 as it writes. `main.rs` runs this on a background thread before spawning the `codesense-server`/`llama-server` sidecars, with one automatic retry on failure, and emits Tauri events a new React screen uses to show progress or a retry button.

**Tech Stack:** Rust (Tauri v2, `sha2` crate), PowerShell, React/TypeScript (`@tauri-apps/api` v2, TanStack Router, vitest + Testing Library).

**Spec:** `docs/superpowers/specs/2026-07-14-first-run-asset-reassembly-design.md`

---

## File structure

| File | Responsibility |
|---|---|
| `client/src-tauri/Cargo.toml` | Modify: add `sha2` dep, `tempfile` dev-dep |
| `client/src-tauri/src/asset_reassembly.rs` | Create: split/join core logic + unit tests (no Tauri dependency — pure filesystem I/O, independently testable) |
| `client/src-tauri/src/main.rs` | Modify: wire the module in, retry-with-backoff orchestration, Tauri command, `AppState` fields, `spawn_backend`/`spawn_llama` signature changes |
| `scripts/split_asset.ps1` | Create: build-time splitter |
| `scripts/build_windows.ps1` | Modify: call the splitter after staging the model and after the grype-db snapshot |
| `client/package.json` | Modify: add `@tauri-apps/api` |
| `client/src/hooks/use-asset-setup.ts` | Create: Tauri event listener → React state (IPC layer) |
| `client/src/hooks/use-asset-setup.test.ts` | Create: hook tests with mocked `@tauri-apps/api` |
| `client/src/components/setup/FirstRunSetup.tsx` | Create: pure presentational progress/error screen (no Tauri dependency — takes state as props) |
| `client/src/components/setup/FirstRunSetup.test.tsx` | Create: component tests with plain props |
| `client/src/routes/__root.tsx` | Modify: gate `<Outlet/>` behind asset-setup readiness |

---

### Task 1: Rust dependencies

**Files:**
- Modify: `client/src-tauri/Cargo.toml`

- [ ] **Step 1: Add the `sha2` runtime dependency and `tempfile` dev-dependency**

Replace the file's contents with:

```toml
[package]
name = "codesense"
version = "0.1.0"
description = "Code Sense — offline security scanning desktop app"
edition = "2021"

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2", features = ["tray-icon", "image-png"] }
tauri-plugin-shell = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
sha2 = "0.10"

[dev-dependencies]
tempfile = "3"
```

- [ ] **Step 2: Verify the crate still resolves**

Run: `cd client/src-tauri && cargo check --release`
Expected: compiles clean (no source changes yet, this only pulls in the two new crates).

- [ ] **Step 3: Commit**

```bash
git add client/src-tauri/Cargo.toml client/src-tauri/Cargo.lock
git commit -m "build(desktop): add sha2 + tempfile deps for asset reassembly"
```

---

### Task 2: `asset_reassembly.rs` core module (TDD)

**Files:**
- Create: `client/src-tauri/src/asset_reassembly.rs`

This module has **no Tauri dependency** — it operates purely on `&Path` arguments, which is what makes it unit-testable without a running Tauri app. `main.rs` (Task 3) resolves the real resource/target directories via Tauri APIs and passes plain paths in.

- [ ] **Step 1: Write the module with its test suite (RED)**

Create `client/src-tauri/src/asset_reassembly.rs`:

```rust
// Build-time-sharded asset reassembly. Both NSIS (32-bit mmap) and MSI (2GB
// CAB limit) reject single files over ~2GB; scripts/split_asset.ps1 splits
// the bundled model + grype-db into <2GB `.partNNN` shards + a manifest.json
// at build time. This module streams them back together on first launch,
// verifying a sha256 of the whole file. See
// docs/superpowers/specs/2026-07-14-first-run-asset-reassembly-design.md.

use std::fs::{self, File};
use std::io::{self, BufReader, BufWriter, Read, Write};
use std::path::{Path, PathBuf};

use serde::Deserialize;
use sha2::{Digest, Sha256};

#[derive(Debug)]
pub enum ReassemblyError {
    Io(io::Error),
    ManifestMissing,
    ManifestCorrupt(String),
    ChecksumMismatch { expected: String, actual: String },
}

impl From<io::Error> for ReassemblyError {
    fn from(e: io::Error) -> Self {
        ReassemblyError::Io(e)
    }
}

impl std::fmt::Display for ReassemblyError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ReassemblyError::Io(e) => write!(f, "I/O error: {e}"),
            ReassemblyError::ManifestMissing => write!(f, "manifest.json is missing"),
            ReassemblyError::ManifestCorrupt(msg) => write!(f, "manifest.json is corrupt: {msg}"),
            ReassemblyError::ChecksumMismatch { expected, actual } => {
                write!(f, "checksum mismatch: expected {expected}, got {actual}")
            }
        }
    }
}

#[derive(Debug, Deserialize)]
struct Manifest {
    file: String,
    total_size: u64,
    sha256: String,
    part_count: u32,
}

pub struct AssetSpec {
    pub file_name: &'static str,
}

pub const MODEL_ASSET: AssetSpec = AssetSpec { file_name: "astra.gguf" };
pub const GRYPE_DB_ASSET: AssetSpec = AssetSpec { file_name: "vulnerability.db" };

fn manifest_path(resource_dir: &Path, spec: &AssetSpec) -> PathBuf {
    resource_dir.join(format!("{}.manifest.json", spec.file_name))
}

fn part_path(resource_dir: &Path, spec: &AssetSpec, index: u32) -> PathBuf {
    resource_dir.join(format!("{}.part{:03}", spec.file_name, index))
}

fn done_marker_path(target_dir: &Path, spec: &AssetSpec) -> PathBuf {
    target_dir.join(format!("{}.done", spec.file_name))
}

fn load_manifest(resource_dir: &Path, spec: &AssetSpec) -> Result<Manifest, ReassemblyError> {
    let path = manifest_path(resource_dir, spec);
    if !path.exists() {
        return Err(ReassemblyError::ManifestMissing);
    }
    let text = fs::read_to_string(&path)?;
    let manifest: Manifest =
        serde_json::from_str(&text).map_err(|e| ReassemblyError::ManifestCorrupt(e.to_string()))?;
    if manifest.file != spec.file_name {
        return Err(ReassemblyError::ManifestCorrupt(format!(
            "manifest is for '{}', expected '{}'",
            manifest.file, spec.file_name
        )));
    }
    Ok(manifest)
}

/// Copies every file in `resource_dir` that is neither a `.partNNN` shard nor
/// the asset's own manifest into `target_dir` — the grype-db resource
/// directory also holds small companion metadata files (e.g. `metadata.json`,
/// `listing.json` from `grype db update`) that must sit alongside the
/// reassembled `vulnerability.db` for `GRYPE_DB_CACHE_DIR` to be a valid
/// cache directory.
fn copy_companion_files(
    resource_dir: &Path,
    spec: &AssetSpec,
    target_dir: &Path,
) -> Result<(), ReassemblyError> {
    let manifest_name = format!("{}.manifest.json", spec.file_name);
    let part_prefix = format!("{}.part", spec.file_name);
    for entry in fs::read_dir(resource_dir)? {
        let entry = entry?;
        let file_name = entry.file_name();
        let name = file_name.to_string_lossy();
        if name == manifest_name.as_str() || name.starts_with(&part_prefix) || name == spec.file_name {
            continue;
        }
        if entry.file_type()?.is_file() {
            fs::copy(entry.path(), target_dir.join(&*name))?;
        }
    }
    Ok(())
}

/// Ensures `spec`'s asset is fully reassembled and checksum-verified at
/// `target_dir/<file_name>`, reading its `.partNNN` shards + manifest from
/// `resource_dir`. Idempotent: returns immediately on subsequent calls once a
/// `.done` marker with a matching hash and a size-matching target file
/// exist — this avoids re-hashing a multi-gigabyte file on every launch.
/// Calls `progress(bytes_written, total_size)` periodically while streaming.
pub fn ensure_ready(
    resource_dir: &Path,
    target_dir: &Path,
    spec: &AssetSpec,
    mut progress: impl FnMut(u64, u64),
) -> Result<PathBuf, ReassemblyError> {
    fs::create_dir_all(target_dir)?;
    let target_path = target_dir.join(spec.file_name);
    let manifest = load_manifest(resource_dir, spec)?;
    let done_path = done_marker_path(target_dir, spec);

    if done_path.exists() {
        if let Ok(recorded_hash) = fs::read_to_string(&done_path) {
            if recorded_hash.trim() == manifest.sha256 {
                if let Ok(meta) = fs::metadata(&target_path) {
                    if meta.len() == manifest.total_size {
                        return Ok(target_path);
                    }
                }
            }
        }
    }

    let tmp_path = target_dir.join(format!("{}.tmp", spec.file_name));
    let _ = fs::remove_file(&tmp_path);

    {
        let mut writer = BufWriter::new(File::create(&tmp_path)?);
        let mut hasher = Sha256::new();
        let mut written: u64 = 0;
        let mut buf = [0u8; 1024 * 1024];

        for index in 0..manifest.part_count {
            let part = part_path(resource_dir, spec, index);
            let mut reader = BufReader::new(File::open(&part)?);
            loop {
                let n = reader.read(&mut buf)?;
                if n == 0 {
                    break;
                }
                writer.write_all(&buf[..n])?;
                hasher.update(&buf[..n]);
                written += n as u64;
                progress(written, manifest.total_size);
            }
        }
        writer.flush()?;

        let actual = format!("{:x}", hasher.finalize());
        if actual != manifest.sha256 {
            drop(writer);
            let _ = fs::remove_file(&tmp_path);
            return Err(ReassemblyError::ChecksumMismatch {
                expected: manifest.sha256,
                actual,
            });
        }
    }

    fs::rename(&tmp_path, &target_path)?;
    fs::write(&done_path, &manifest.sha256)?;
    copy_companion_files(resource_dir, spec, target_dir)?;

    Ok(target_path)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    const TEST_ASSET: AssetSpec = AssetSpec { file_name: "test.bin" };

    /// Writes `parts` as `test.bin.part000.. ` plus a matching manifest.json
    /// into `resource_dir`. Returns the concatenated bytes for assertions.
    fn write_fixture(resource_dir: &Path, parts: &[&[u8]]) -> Vec<u8> {
        let mut whole = Vec::new();
        for (i, part) in parts.iter().enumerate() {
            whole.extend_from_slice(part);
            fs::write(part_path(resource_dir, &TEST_ASSET, i as u32), part).unwrap();
        }
        let sha256 = format!("{:x}", Sha256::digest(&whole));
        let manifest = format!(
            r#"{{"file":"test.bin","total_size":{},"sha256":"{}","part_count":{}}}"#,
            whole.len(),
            sha256,
            parts.len(),
        );
        fs::write(manifest_path(resource_dir, &TEST_ASSET), manifest).unwrap();
        whole
    }

    #[test]
    fn reassembles_parts_into_the_expected_whole_file() {
        let resource_dir = tempdir().unwrap();
        let target_dir = tempdir().unwrap();
        let whole = write_fixture(resource_dir.path(), &[b"hello ", b"world", b"!"]);

        let mut calls = Vec::new();
        let result = ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |w, t| {
            calls.push((w, t));
        })
        .unwrap();

        assert_eq!(fs::read(&result).unwrap(), whole);
        assert!(!calls.is_empty(), "progress callback should fire at least once");
    }

    #[test]
    fn second_call_is_idempotent_and_skips_reading_parts() {
        let resource_dir = tempdir().unwrap();
        let target_dir = tempdir().unwrap();
        write_fixture(resource_dir.path(), &[b"abc", b"def"]);

        ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |_, _| {}).unwrap();

        // If the second call actually re-read the parts, deleting one here
        // would make it fail with an I/O error. It must not, because the
        // `.done` marker short-circuits it.
        fs::remove_file(part_path(resource_dir.path(), &TEST_ASSET, 0)).unwrap();

        let result = ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |_, _| {});
        assert!(result.is_ok());
    }

    #[test]
    fn corrupted_part_produces_checksum_mismatch_then_recovers_on_retry() {
        let resource_dir = tempdir().unwrap();
        let target_dir = tempdir().unwrap();
        write_fixture(resource_dir.path(), &[b"correct-bytes-1", b"correct-bytes-2"]);

        fs::write(part_path(resource_dir.path(), &TEST_ASSET, 0), b"corrupted!!!!!!").unwrap();

        let first = ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |_, _| {});
        assert!(matches!(first, Err(ReassemblyError::ChecksumMismatch { .. })));

        // Fix the part back to what the manifest expects and retry — this is
        // what main.rs's auto-retry-once policy does at the orchestration level.
        fs::write(part_path(resource_dir.path(), &TEST_ASSET, 0), b"correct-bytes-1").unwrap();
        let second = ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |_, _| {});
        assert!(second.is_ok());
    }

    #[test]
    fn truncated_last_part_is_detected_as_a_checksum_mismatch() {
        let resource_dir = tempdir().unwrap();
        let target_dir = tempdir().unwrap();
        write_fixture(resource_dir.path(), &[b"full-part-one", b"full-part-two"]);

        fs::write(part_path(resource_dir.path(), &TEST_ASSET, 1), b"trunc").unwrap();

        let result = ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |_, _| {});
        assert!(matches!(result, Err(ReassemblyError::ChecksumMismatch { .. })));
    }

    #[test]
    fn missing_manifest_is_reported_distinctly() {
        let resource_dir = tempdir().unwrap();
        let target_dir = tempdir().unwrap();
        // No fixture written — manifest.json is absent.

        let result = ensure_ready(resource_dir.path(), target_dir.path(), &TEST_ASSET, |_, _| {});
        assert!(matches!(result, Err(ReassemblyError::ManifestMissing)));
    }
}
```

- [ ] **Step 2: Note — this module isn't compiled yet**

`asset_reassembly.rs` exists as a file but nothing in `main.rs` declares `mod asset_reassembly;` yet, so `cargo test` won't find or run its tests until Task 3, Step 1 wires it in. There is no separate build/test action to run in this task — proceed directly to Task 3.

- [ ] **Step 3: Commit** (bundled with Task 3's commit, since the module isn't compiled until it's wired into `main.rs` — see Task 3 Step 4)

---

### Task 3: Wire reassembly into `main.rs`

**Files:**
- Modify: `client/src-tauri/src/main.rs`

This task has no unit tests of its own — `AppHandle`-dependent glue code isn't testable outside a running Tauri app. It's verified by `cargo check`/`cargo test` here and by the end-to-end acceptance protocol in Task 10, consistent with how this crate's other Tauri-lifecycle code has been verified (per the P0 session notes referenced in the spec).

- [ ] **Step 1: Replace the whole file**

Replace `client/src-tauri/src/main.rs` with:

```rust
// Code Sense desktop shell (Tauri v2).
//
// Owns two sidecars and the app lifecycle:
//   * codesense-server  — the Django backend (PyInstaller-frozen, served by waitress) on 127.0.0.1:8585
//   * llama-server      — llama.cpp serving the quantized GGUF on 127.0.0.1:8001
// Tray menu: Open / Pause AI engine (frees the model's RAM) / Quit. Closing the
// window hides to tray so background scans keep running; Quit tears down both
// sidecars cleanly so no orphan processes or held ports remain.
//
// Both sidecars depend on two large bundled assets (the GGUF model and the
// grype vulnerability DB) that ship as build-time-split `.partNNN` shards
// (see scripts/split_asset.ps1) because both NSIS and MSI reject single
// files over ~2GB. `asset_reassembly` streams them back together into a
// writable per-user directory before either sidecar spawns — see
// docs/superpowers/specs/2026-07-14-first-run-asset-reassembly-design.md.
//
// SCAFFOLD: this is NOT compiled in the CI sandbox (no Rust/Tauri/WebView2).
// Validate with `cargo tauri build` on a Windows host once binaries/, resources/,
// webview2/, and icons/ are populated (see README.md). Minor Tauri 2.x API
// details may need adjusting against the exact crate versions resolved.
#![cfg_attr(all(not(debug_assertions), target_os = "windows"), windows_subsystem = "windows")]

mod asset_reassembly;

use std::path::PathBuf;
use std::sync::Mutex;

use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    path::BaseDirectory,
    tray::TrayIconBuilder,
    Emitter, Manager, RunEvent, WindowEvent,
};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

use asset_reassembly::{ensure_ready, ReassemblyError, GRYPE_DB_ASSET, MODEL_ASSET};

const BACKEND_PORT: &str = "8585";
const LLAMA_PORT: &str = "8001";

#[derive(Default)]
struct AppState {
    backend: Mutex<Option<CommandChild>>,
    llama: Mutex<Option<CommandChild>>,
    ai_paused: Mutex<bool>,
    model_path: Mutex<Option<PathBuf>>,
    grype_db_dir: Mutex<Option<PathBuf>>,
}

fn spawn_backend(app: &tauri::AppHandle, grype_db_dir: &std::path::Path) -> Option<CommandChild> {
    let data_dir = app.path().app_local_data_dir().ok()?;
    let _ = std::fs::create_dir_all(&data_dir);
    let keys_dir = data_dir.join("keys");
    let tools_dir = app
        .path()
        .resolve("resources/tools", BaseDirectory::Resource)
        .unwrap_or_default();

    let cmd = app
        .shell()
        .sidecar("codesense-server")
        .ok()?
        .env("CODESENSE_DATA_DIR", data_dir.to_string_lossy().to_string())
        .env("VLLM_BASE_URL", format!("http://127.0.0.1:{LLAMA_PORT}/v1"))
        .env("VLLM_MODEL", "astra-code-reviewer")
        .env("VLLM_API_KEY", "EMPTY")
        // Ship the instruction-tuned (Apache-2.0 Qwen2.5-Coder-Instruct) path, not
        // the legacy FIM one: the bundled GGUF is the instruct model and the
        // verifier/enricher emit/parse JSON only under instruct mode. Without this
        // the backend defaults to LLM_MODEL_MODE=fim (see llm.py::model_mode).
        .env("LLM_MODEL_MODE", "instruct")
        .env("SCANNER_TOOLS_DIR", tools_dir.to_string_lossy().to_string())
        .env("GRYPE_DB_CACHE_DIR", grype_db_dir.to_string_lossy().to_string())
        // Windows Semgrep/OpenGrep is `semgrep.exe`; the backend's SEMGREP_BIN
        // override is used verbatim (it does NOT append an extension — only the
        // SCANNER_TOOLS_DIR fallback does), so the ext must be correct here or the
        // packaged Windows app can't launch the engine and scans find nothing.
        .env(
            "SEMGREP_BIN",
            tools_dir
                .join(if cfg!(target_os = "windows") { "semgrep.exe" } else { "semgrep" })
                .to_string_lossy()
                .to_string(),
        )
        .env(
            "SEMGREP_RULES_DIR",
            app.path()
                .resolve("resources/semgrep-rules", BaseDirectory::Resource)
                .unwrap_or_default()
                .to_string_lossy()
                .to_string(),
        )
        .env("COSIGN_KEY_DIR", keys_dir.to_string_lossy().to_string())
        .args(["127.0.0.1", BACKEND_PORT]);

    match cmd.spawn() {
        Ok((mut rx, child)) => {
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) | CommandEvent::Stderr(line) => {
                            eprintln!("[backend] {}", String::from_utf8_lossy(&line));
                        }
                        _ => {}
                    }
                }
            });
            Some(child)
        }
        Err(e) => {
            eprintln!("failed to start backend: {e}");
            None
        }
    }
}

fn spawn_llama(app: &tauri::AppHandle, model_path: &std::path::Path) -> Option<CommandChild> {
    let cmd = app
        .shell()
        .sidecar("llama-server")
        .ok()?
        .args([
            "--model",
            &model_path.to_string_lossy(),
            "--host",
            "127.0.0.1",
            "--port",
            LLAMA_PORT,
            "--ctx-size",
            "8192",
            "--alias",
            "astra-code-reviewer",
            "--api-key",
            "EMPTY",
            "--jinja",
        ]);

    // The Windows llama-server.exe is a thin (~9KB) launcher that dynamically
    // links its runtime DLLs (llama-server-impl.dll, llama.dll, ggml*.dll,
    // mtmd.dll, libomp*). A PATH-prepend workaround here was proven insufficient
    // (the loader still failed to resolve them). The real fix lives in
    // tauri.conf.json: `bundle.resources` maps resources/llama-runtime/*.dll to
    // target "" (= $RESOURCES root), which on Windows IS the same directory
    // Tauri installs the sidecar exe into — so the DLLs are simply beside it on
    // disk and the default Windows DLL search order finds them with no code
    // needed here. No-op on macOS (single Metal binary; the dir is absent there).
    match cmd.spawn() {
        Ok((mut rx, child)) => {
            let app = app.clone();
            let spawned_at = std::time::Instant::now();
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) | CommandEvent::Stderr(line) => {
                            eprintln!("[llama] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Terminated(payload) => {
                            // A deliberate "Pause AI" toggle or app quit also kills this
                            // process and produces a Terminated event, so only treat a
                            // termination in the first few seconds as a startup failure
                            // (the crash-on-launch symptom this check targets).
                            if spawned_at.elapsed() < std::time::Duration::from_secs(5) {
                                eprintln!(
                                    "[llama] AI engine failed to start (exit code {:?}) — scans will run deterministic-only, no AI verify/enrich.",
                                    payload.code
                                );
                                if let Some(tray) = app.tray_by_id("main") {
                                    let _ = tray.set_tooltip(Some(
                                        "Code Sense — AI engine failed to start (deterministic-only scans)",
                                    ));
                                }
                            } else {
                                eprintln!("[llama] AI engine stopped (exit code {:?})", payload.code);
                            }
                        }
                        CommandEvent::Error(err) => {
                            eprintln!("[llama] AI engine spawn error: {err}");
                        }
                        _ => {}
                    }
                }
            });
            Some(child)
        }
        Err(e) => {
            eprintln!("failed to start llama-server: {e}");
            None
        }
    }
}

/// Runs `ensure_ready` for one asset with the auto-retry-once policy: on
/// failure, discard any partial output and try exactly once more before
/// giving up. Emits `asset-setup-progress` events for the frontend's
/// first-run setup screen as it streams.
fn reassemble_with_retry(
    app: &tauri::AppHandle,
    asset_name: &str,
    resource_dir: &std::path::Path,
    target_dir: &std::path::Path,
    spec: &asset_reassembly::AssetSpec,
) -> Result<PathBuf, ReassemblyError> {
    let mut last_err = None;
    for _attempt in 0..2 {
        let app_for_progress = app.clone();
        let name_for_progress = asset_name.to_string();
        let result = ensure_ready(resource_dir, target_dir, spec, |written, total| {
            let _ = app_for_progress.emit(
                "asset-setup-progress",
                serde_json::json!({ "asset": name_for_progress, "bytes": written, "total": total }),
            );
        });
        match result {
            Ok(path) => return Ok(path),
            Err(e) => last_err = Some(e),
        }
    }
    Err(last_err.expect("loop runs at least once"))
}

/// Reassembles both bundled assets (model, grype-db) on a background thread,
/// then spawns both sidecars once they're verified ready. Emits
/// `asset-setup-complete` on success or `asset-setup-failed` (with a
/// specific reason) if either asset fails after its retry — the sidecars are
/// never spawned against unverified assets. Re-entrant: also used as the
/// `retry_asset_setup` command's implementation.
fn ensure_assets_then_spawn(app: tauri::AppHandle) {
    std::thread::spawn(move || {
        let model_resource = app
            .path()
            .resolve("resources/model", BaseDirectory::Resource)
            .unwrap_or_default();
        let grype_resource = app
            .path()
            .resolve("resources/grype-db", BaseDirectory::Resource)
            .unwrap_or_default();
        let data_dir = app.path().app_local_data_dir().unwrap_or_default();
        let model_target_dir = data_dir.join("model");
        let grype_target_dir = data_dir.join("grype-db");

        let model_path = match reassemble_with_retry(
            &app, "model", &model_resource, &model_target_dir, &MODEL_ASSET,
        ) {
            Ok(path) => path,
            Err(e) => {
                let _ = app.emit(
                    "asset-setup-failed",
                    serde_json::json!({ "asset": "model", "reason": e.to_string() }),
                );
                return;
            }
        };

        if let Err(e) = reassemble_with_retry(
            &app, "grype-db", &grype_resource, &grype_target_dir, &GRYPE_DB_ASSET,
        ) {
            let _ = app.emit(
                "asset-setup-failed",
                serde_json::json!({ "asset": "grype-db", "reason": e.to_string() }),
            );
            return;
        }

        {
            let state = app.state::<AppState>();
            *state.model_path.lock().unwrap() = Some(model_path.clone());
            *state.grype_db_dir.lock().unwrap() = Some(grype_target_dir.clone());
        }

        let _ = app.emit("asset-setup-complete", ());

        let state = app.state::<AppState>();
        *state.backend.lock().unwrap() = spawn_backend(&app, &grype_target_dir);
        *state.llama.lock().unwrap() = spawn_llama(&app, &model_path);
    });
}

#[tauri::command]
fn retry_asset_setup(app: tauri::AppHandle) {
    ensure_assets_then_spawn(app);
}

fn kill(slot: &Mutex<Option<CommandChild>>) {
    if let Some(child) = slot.lock().unwrap().take() {
        let _ = child.kill();
    }
}

fn shutdown(app: &tauri::AppHandle) {
    let state = app.state::<AppState>();
    kill(&state.backend);
    kill(&state.llama);
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![retry_asset_setup])
        .setup(|app| {
            let handle = app.handle().clone();
            ensure_assets_then_spawn(handle);

            let open = MenuItem::with_id(app, "open", "Open Code Sense", true, None::<&str>)?;
            let pause = MenuItem::with_id(app, "pause_ai", "Pause / resume AI engine", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let sep = PredefinedMenuItem::separator(app)?;
            let menu = Menu::with_items(app, &[&open, &pause, &sep, &quit])?;

            TrayIconBuilder::with_id("main")
                .tooltip("Code Sense")
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(move |app, event| match event.id().as_ref() {
                    "open" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "pause_ai" => {
                        // Toggle the llama-server sidecar to free / restore its RAM.
                        let state = app.state::<AppState>();
                        let mut paused = state.ai_paused.lock().unwrap();
                        if *paused {
                            let model_path = state.model_path.lock().unwrap().clone();
                            if let Some(model_path) = model_path {
                                let child = spawn_llama(app, &model_path);
                                *state.llama.lock().unwrap() = child;
                                *paused = false;
                            }
                        } else {
                            kill(&state.llama);
                            *paused = true;
                        }
                    }
                    "quit" => {
                        shutdown(app);
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                // Hide to tray instead of exiting so background scans continue.
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building Code Sense")
        .run(|app, event| {
            if let RunEvent::ExitRequested { .. } = event {
                shutdown(app);
            }
        });
}
```

- [ ] **Step 2: Run the asset_reassembly unit tests now that the module is wired in**

Run: `cd client/src-tauri && cargo test --release asset_reassembly::tests`
Expected: `test result: ok. 5 passed; 0 failed`

- [ ] **Step 3: Verify the whole crate compiles**

Run: `cd client/src-tauri && cargo check --release`
Expected: clean compile, no errors. Warnings about unused `PathBuf` import etc. should not appear — if they do, remove the unused import.

- [ ] **Step 4: Commit** (covers both Task 2 and Task 3 — the module and its wiring)

```bash
git add client/src-tauri/src/asset_reassembly.rs client/src-tauri/src/main.rs
git commit -m "feat(desktop): reassemble sharded model + grype-db on first launch

Both NSIS and MSI reject single files over ~2GB; the bundled 4.68GB model
and 2.56GB grype-db now ship as build-time-split parts (scripts/split_asset.ps1,
next commit) and get streamed back together with a sha256 check before either
sidecar spawns. One automatic retry on failure, then a distinct
asset-setup-failed event instead of a silent deterministic-only fallback."
```

---

### Task 4: Build-time splitter script

**Files:**
- Create: `scripts/split_asset.ps1`

No existing PowerShell test harness in this repo (Pester or otherwise) — verified per this task by a manual round-trip check, consistent with how other build-script changes in this project have been verified.

- [ ] **Step 1: Write the script**

Create `scripts/split_asset.ps1`:

```powershell
<#
.SYNOPSIS
  Splits a file into <2GB parts + a manifest.json, to work around the
  Windows installer size ceilings both NSIS (32-bit mmap) and MSI (2GB CAB
  limit) enforce on single bundled files. See
  docs/superpowers/specs/2026-07-14-first-run-asset-reassembly-design.md.

.PARAMETER Path        The file to split. Deleted after a successful split.
.PARAMETER PartSizeMB  Size of each part in MB (default 1800, safely under
                       the 2048MB/2^31-byte ceiling).
#>
param(
  [Parameter(Mandatory = $true)][string]$Path,
  [int]$PartSizeMB = 1800
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Path)) {
  throw "split_asset.ps1: input file not found: $Path"
}

$fullPath = (Resolve-Path $Path).Path
$dir = Split-Path $fullPath -Parent
$name = Split-Path $fullPath -Leaf
$partSizeBytes = [int64]$PartSizeMB * 1MB

Write-Host "Computing sha256 of $name ..."
$sha256 = (Get-FileHash -Path $fullPath -Algorithm SHA256).Hash.ToLowerInvariant()
$totalSize = (Get-Item $fullPath).Length

Write-Host "Splitting $name ($totalSize bytes) into ~$PartSizeMB MB parts..."
$buffer = New-Object byte[] (16MB)
$reader = [System.IO.File]::OpenRead($fullPath)
$partIndex = 0
try {
  while ($true) {
    $partPath = Join-Path $dir ("{0}.part{1:D3}" -f $name, $partIndex)
    $writer = [System.IO.File]::Create($partPath)
    $wroteAny = $false
    try {
      $remaining = $partSizeBytes
      while ($remaining -gt 0) {
        $toRead = [Math]::Min($buffer.Length, $remaining)
        $read = $reader.Read($buffer, 0, $toRead)
        if ($read -le 0) { break }
        $writer.Write($buffer, 0, $read)
        $remaining -= $read
        $wroteAny = $true
      }
    } finally {
      $writer.Close()
    }
    if (-not $wroteAny) {
      Remove-Item $partPath -Force
      break
    }
    $partIndex++
  }
} finally {
  $reader.Close()
}

$partCount = $partIndex
$manifest = [ordered]@{
  file       = $name
  total_size = $totalSize
  sha256     = $sha256
  part_count = $partCount
}
$manifestPath = Join-Path $dir "$name.manifest.json"
$manifest | ConvertTo-Json | Set-Content -Path $manifestPath -Encoding utf8NoBOM

Remove-Item $fullPath -Force

Write-Host "Split $name into $partCount part(s); manifest written to $manifestPath; original deleted."
```

- [ ] **Step 2: Manually verify a round-trip on a throwaway test file**

Run (from the repo root, in the `yacm` PowerShell environment):

```powershell
$testFile = Join-Path $env:TEMP "split-test.bin"
$rand = New-Object byte[] (5MB)
(New-Object Random).NextBytes($rand)
[System.IO.File]::WriteAllBytes($testFile, $rand)
$originalHash = (Get-FileHash $testFile -Algorithm SHA256).Hash

& .\scripts\split_asset.ps1 -Path $testFile -PartSizeMB 2

# Reassemble manually and compare.
$dir = Split-Path $testFile -Parent
$name = Split-Path $testFile -Leaf
$manifest = Get-Content (Join-Path $dir "$name.manifest.json") | ConvertFrom-Json
$outStream = [System.IO.File]::Create((Join-Path $dir "rebuilt.bin"))
for ($i = 0; $i -lt $manifest.part_count; $i++) {
  $partPath = Join-Path $dir ("{0}.part{1:D3}" -f $name, $i)
  $bytes = [System.IO.File]::ReadAllBytes($partPath)
  $outStream.Write($bytes, 0, $bytes.Length)
}
$outStream.Close()
$rebuiltHash = (Get-FileHash (Join-Path $dir "rebuilt.bin") -Algorithm SHA256).Hash

if ($rebuiltHash -eq $manifest.sha256 -and $rebuiltHash -eq $originalHash) {
  Write-Host "PASS: round-trip hash matches ($rebuiltHash)"
} else {
  Write-Error "FAIL: hash mismatch (original=$originalHash manifest=$($manifest.sha256) rebuilt=$rebuiltHash)"
}
Remove-Item (Join-Path $dir "$name.part*"), (Join-Path $dir "$name.manifest.json"), (Join-Path $dir "rebuilt.bin") -Force
```

Expected: `PASS: round-trip hash matches (...)`, and that the original 5MB file split into 3 parts (2MB, 2MB, 1MB).

- [ ] **Step 3: Commit**

```bash
git add scripts/split_asset.ps1
git commit -m "build(windows): add split_asset.ps1 for the <2GB installer size workaround"
```

---

### Task 5: Wire the splitter into `build_windows.ps1`

**Files:**
- Modify: `scripts/build_windows.ps1:152-158` (model staging)
- Modify: `scripts/build_windows.ps1:209-221` (grype-db snapshot)

- [ ] **Step 1: Split the model GGUF right after it's staged**

In `scripts/build_windows.ps1`, find:

```powershell
Copy-Item $ModelGguf (Join-Path $ResModel "astra.gguf") -Force
$gb = [math]::Round((Get-Item $ModelGguf).Length / 1GB, 2)
Ok "model ($ModelTier tier, $gb GB) staged as resources\model\astra.gguf"
```

Replace with:

```powershell
Copy-Item $ModelGguf (Join-Path $ResModel "astra.gguf") -Force
$gb = [math]::Round((Get-Item $ModelGguf).Length / 1GB, 2)
Ok "model ($ModelTier tier, $gb GB) staged as resources\model\astra.gguf"

Info "Splitting model into <2GB parts (NSIS/MSI installer size workaround)"
& (Join-Path $PSScriptRoot "split_asset.ps1") -Path (Join-Path $ResModel "astra.gguf")
Ok "model split into parts + manifest.json in resources\model"
```

- [ ] **Step 2: Split the grype-db snapshot right after it's produced**

In the same file, find:

```powershell
Info "Snapshotting Grype vulnerability DB"
$grypeExe = Join-Path $ResTools "grype.exe"
if (Test-Path $grypeExe) {
  $env:GRYPE_DB_CACHE_DIR = $ResGrypeDb
  & $grypeExe db update
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "grype db update returned $LASTEXITCODE; the bundled CVE DB may be empty/stale."
  } else {
    Ok "Grype DB snapshot in resources\grype-db (frozen; AUTO_UPDATE off at runtime)"
  }
} else {
  Write-Warning "grype.exe not staged; skipping DB snapshot. Re-run without -SkipTools."
}
```

Replace with:

```powershell
Info "Snapshotting Grype vulnerability DB"
$grypeExe = Join-Path $ResTools "grype.exe"
if (Test-Path $grypeExe) {
  $env:GRYPE_DB_CACHE_DIR = $ResGrypeDb
  & $grypeExe db update
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "grype db update returned $LASTEXITCODE; the bundled CVE DB may be empty/stale."
  } else {
    Ok "Grype DB snapshot in resources\grype-db (frozen; AUTO_UPDATE off at runtime)"
    $vulnDb = Join-Path $ResGrypeDb "vulnerability.db"
    if (Test-Path $vulnDb) {
      Info "Splitting vulnerability.db into <2GB parts (NSIS/MSI installer size workaround)"
      & (Join-Path $PSScriptRoot "split_asset.ps1") -Path $vulnDb
      Ok "vulnerability.db split into parts + manifest.json in resources\grype-db"
    } else {
      Write-Warning "vulnerability.db not found at $vulnDb after db update; skipping split."
    }
  }
} else {
  Write-Warning "grype.exe not staged; skipping DB snapshot. Re-run without -SkipTools."
}
```

- [ ] **Step 3: Sanity-check the script still parses**

Run: `powershell -NoProfile -Command "& { . { $null = Get-Content .\scripts\build_windows.ps1 -Raw | Out-Null }; [System.Management.Automation.PSParser]::Tokenize((Get-Content .\scripts\build_windows.ps1 -Raw), [ref]$null) | Out-Null; Write-Host 'parses OK' }"`
Expected: `parses OK`, no parser exceptions.

- [ ] **Step 4: Commit**

```bash
git add scripts/build_windows.ps1
git commit -m "build(windows): split model + vulnerability.db after staging"
```

---

### Task 6: Add the `@tauri-apps/api` frontend dependency

**Files:**
- Modify: `client/package.json`

- [ ] **Step 1: Install the package**

Run: `cd client && npm install @tauri-apps/api@^2`
Expected: `package.json` gains `"@tauri-apps/api": "^2.x.x"` under `dependencies`, `package-lock.json` updates.

- [ ] **Step 2: Verify it resolves correctly**

Run: `cd client && npx tsc --noEmit`
Expected: clean (no new type errors — nothing imports it yet).

- [ ] **Step 3: Commit**

```bash
git add client/package.json client/package-lock.json
git commit -m "build(client): add @tauri-apps/api for first-run setup events"
```

---

### Task 7: `use-asset-setup` hook (TDD)

**Files:**
- Create: `client/src/hooks/use-asset-setup.ts`
- Test: `client/src/hooks/use-asset-setup.test.ts`

- [ ] **Step 1: Write the failing test**

Create `client/src/hooks/use-asset-setup.test.ts`:

```ts
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';

const listeners: Record<string, (event: { payload: unknown }) => void> = {};

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn((eventName: string, callback: (event: { payload: unknown }) => void) => {
    listeners[eventName] = callback;
    return Promise.resolve(() => {
      delete listeners[eventName];
    });
  }),
}));

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(),
}));

import { useAssetSetup } from './use-asset-setup';
import { invoke } from '@tauri-apps/api/core';

describe('useAssetSetup', () => {
  beforeEach(() => {
    for (const key of Object.keys(listeners)) delete listeners[key];
    vi.clearAllMocks();
  });

  test('starts pending and transitions to ready on asset-setup-complete', async () => {
    const { result } = renderHook(() => useAssetSetup());
    expect(result.current.status).toBe('pending');

    await waitFor(() => expect(listeners['asset-setup-complete']).toBeDefined());
    act(() => {
      listeners['asset-setup-complete']({ payload: undefined });
    });

    expect(result.current.status).toBe('ready');
  });

  test('tracks per-asset progress while pending', async () => {
    const { result } = renderHook(() => useAssetSetup());
    await waitFor(() => expect(listeners['asset-setup-progress']).toBeDefined());

    act(() => {
      listeners['asset-setup-progress']({ payload: { asset: 'model', bytes: 500, total: 1000 } });
    });

    expect(result.current.status).toBe('pending');
    if (result.current.status === 'pending') {
      expect(result.current.progress.model).toEqual({ bytes: 500, total: 1000 });
    }
  });

  test('transitions to failed with reason and retry() calls retry_asset_setup', async () => {
    const { result } = renderHook(() => useAssetSetup());
    await waitFor(() => expect(listeners['asset-setup-failed']).toBeDefined());

    act(() => {
      listeners['asset-setup-failed']({ payload: { asset: 'grype-db', reason: 'disk full' } });
    });

    expect(result.current.status).toBe('failed');
    if (result.current.status === 'failed') {
      expect(result.current.reason).toBe('disk full');
    }

    act(() => {
      result.current.retry();
    });
    expect(invoke).toHaveBeenCalledWith('retry_asset_setup');
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd client && npx vitest run src/hooks/use-asset-setup.test.ts`
Expected: FAIL — `Cannot find module './use-asset-setup'` (the hook doesn't exist yet).

- [ ] **Step 3: Write the hook**

Create `client/src/hooks/use-asset-setup.ts`:

```ts
import { useCallback, useEffect, useState } from 'react';
import { listen } from '@tauri-apps/api/event';
import { invoke } from '@tauri-apps/api/core';

export type AssetSetupState =
  | { status: 'pending'; progress: Record<string, { bytes: number; total: number }> }
  | { status: 'ready' }
  | { status: 'failed'; asset: string; reason: string };

type ProgressPayload = { asset: string; bytes: number; total: number };
type FailedPayload = { asset: string; reason: string };

export function useAssetSetup(): AssetSetupState & { retry: () => void } {
  const [state, setState] = useState<AssetSetupState>({ status: 'pending', progress: {} });

  useEffect(() => {
    let cancelled = false;
    const unlisten: Array<() => void> = [];

    listen<ProgressPayload>('asset-setup-progress', (event) => {
      setState((prev) =>
        prev.status === 'pending'
          ? {
              status: 'pending',
              progress: {
                ...prev.progress,
                [event.payload.asset]: { bytes: event.payload.bytes, total: event.payload.total },
              },
            }
          : prev,
      );
    }).then((fn) => {
      if (cancelled) fn();
      else unlisten.push(fn);
    });

    listen('asset-setup-complete', () => {
      setState({ status: 'ready' });
    }).then((fn) => {
      if (cancelled) fn();
      else unlisten.push(fn);
    });

    listen<FailedPayload>('asset-setup-failed', (event) => {
      setState({ status: 'failed', asset: event.payload.asset, reason: event.payload.reason });
    }).then((fn) => {
      if (cancelled) fn();
      else unlisten.push(fn);
    });

    return () => {
      cancelled = true;
      unlisten.forEach((fn) => fn());
    };
  }, []);

  const retry = useCallback(() => {
    setState({ status: 'pending', progress: {} });
    void invoke('retry_asset_setup');
  }, []);

  return { ...state, retry };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd client && npx vitest run src/hooks/use-asset-setup.test.ts`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add client/src/hooks/use-asset-setup.ts client/src/hooks/use-asset-setup.test.ts
git commit -m "feat(client): add useAssetSetup hook listening for first-run setup events"
```

---

### Task 8: `FirstRunSetup` presentational component (TDD)

**Files:**
- Create: `client/src/components/setup/FirstRunSetup.tsx`
- Test: `client/src/components/setup/FirstRunSetup.test.tsx`

This component takes the hook's state as a **prop** rather than calling `useAssetSetup()` itself, so it has no Tauri dependency and its tests need no mocking — matching the existing `UpdatedFinding.test.tsx` pattern of plain-props rendering.

- [ ] **Step 1: Write the failing test**

Create `client/src/components/setup/FirstRunSetup.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import { FirstRunSetup } from './FirstRunSetup';

describe('FirstRunSetup', () => {
  test('shows progress percentage while pending', () => {
    render(
      <FirstRunSetup
        state={{
          status: 'pending',
          progress: { model: { bytes: 50, total: 100 } },
          retry: vi.fn(),
        }}
      />,
    );
    expect(screen.getByText(/50%/)).toBeInTheDocument();
  });

  test('shows the failure reason and calls retry on click', () => {
    const retry = vi.fn();
    render(
      <FirstRunSetup state={{ status: 'failed', asset: 'grype-db', reason: 'disk full', retry }} />,
    );
    expect(screen.getByText(/disk full/)).toBeInTheDocument();
    screen.getByRole('button', { name: /retry/i }).click();
    expect(retry).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd client && npx vitest run src/components/setup/FirstRunSetup.test.tsx`
Expected: FAIL — `Cannot find module './FirstRunSetup'`.

- [ ] **Step 3: Write the component**

Create `client/src/components/setup/FirstRunSetup.tsx`:

```tsx
import type { AssetSetupState } from '@/hooks/use-asset-setup';

const ASSET_LABELS: Record<string, string> = {
  model: 'AI model',
  'grype-db': 'vulnerability database',
};

type Props = {
  state: AssetSetupState & { retry: () => void };
};

export function FirstRunSetup({ state }: Props) {
  if (state.status === 'ready') {
    return null;
  }

  if (state.status === 'failed') {
    return (
      <div className="min-h-screen flex items-center justify-center p-4" style={{ backgroundColor: '#2D2D2D' }}>
        <div className="w-full max-w-md rounded-2xl bg-white text-black shadow-2xl overflow-hidden px-8 py-8 text-center space-y-4">
          <h1 className="text-2xl font-bold">Setup failed</h1>
          <p className="text-sm text-gray-600">
            Couldn't prepare the {ASSET_LABELS[state.asset] ?? state.asset}: {state.reason}
          </p>
          <button
            type="button"
            className="w-full py-3 rounded-lg text-white"
            style={{ backgroundColor: '#BF0000' }}
            onClick={state.retry}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const entries = Object.entries(state.progress);
  const totalBytes = entries.reduce((sum, [, p]) => sum + p.total, 0);
  const writtenBytes = entries.reduce((sum, [, p]) => sum + p.bytes, 0);
  const percent = totalBytes > 0 ? Math.round((writtenBytes / totalBytes) * 100) : 0;

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ backgroundColor: '#2D2D2D' }}>
      <div className="w-full max-w-md rounded-2xl bg-white text-black shadow-2xl overflow-hidden px-8 py-8 text-center space-y-4">
        <h1 className="text-2xl font-bold">Setting up Code Sense</h1>
        <p className="text-sm text-gray-600">
          Preparing the AI model and vulnerability database (first launch only)…
        </p>
        <div className="w-full h-2 rounded-full bg-gray-200 overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${percent}%`, backgroundColor: '#BF0000' }} />
        </div>
        <p className="text-xs text-gray-500">{percent}%</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd client && npx vitest run src/components/setup/FirstRunSetup.test.tsx`
Expected: `2 passed`

- [ ] **Step 5: Type-check**

Run: `cd client && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add client/src/components/setup/FirstRunSetup.tsx client/src/components/setup/FirstRunSetup.test.tsx
git commit -m "feat(client): add FirstRunSetup progress/error screen"
```

---

### Task 9: Gate the app behind asset-setup readiness

**Files:**
- Modify: `client/src/routes/__root.tsx`

- [ ] **Step 1: Replace the file**

Replace `client/src/routes/__root.tsx` with:

```tsx
import { createRootRoute, Outlet } from '@tanstack/react-router'
import { Toaster } from "@/components/atomic/sonner"
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAssetSetup } from '@/hooks/use-asset-setup';
import { FirstRunSetup } from '@/components/setup/FirstRunSetup';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000, // 1 minute
      retry: 1,
    },
  },
});

function RootComponent() {
  const assetSetup = useAssetSetup();

  return (
    <QueryClientProvider client={queryClient}>
      {assetSetup.status === 'ready' ? <Outlet /> : <FirstRunSetup state={assetSetup} />}
      <Toaster />
    </QueryClientProvider>
  );
}

export const Route = createRootRoute({
  component: RootComponent,
})
```

- [ ] **Step 2: Type-check and run the full client test suite**

Run: `cd client && npx tsc --noEmit && npx vitest run`
Expected: `tsc` clean; vitest shows all suites passing (the pre-existing `UpdatedFinding.test.tsx` plus the two new suites from Tasks 7–8).

- [ ] **Step 3: Commit**

```bash
git add client/src/routes/__root.tsx
git commit -m "feat(client): gate the app shell behind first-run asset setup"
```

---

### Task 10: End-to-end acceptance (manual, on the Windows build host)

**Files:** none (verification only)

- [ ] **Step 1: Full build with the real assets**

Run: `cd client && npx --yes @tauri-apps/cli@2 build`
Expected: succeeds; confirm in the build log that `resources/model/` and `resources/grype-db/` in `target/release/` contain `.partNNN` + `.manifest.json` files and **not** a bare `astra.gguf`/`vulnerability.db` (those only get created at runtime, in `%LOCALAPPDATA%`).

- [ ] **Step 2: Simulate a genuine first launch**

Run (kill any lingering processes first, per the project's known gotcha):

```powershell
Get-Process codesense,codesense-server,llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item "$env:LOCALAPPDATA\com.codesense.desktop" -Recurse -Force -ErrorAction SilentlyContinue
Start-Process "client\src-tauri\target\release\codesense.exe"
```

Expected: window opens showing "Setting up Code Sense" with a progress percentage climbing from 0 toward 100 over roughly the time it takes to copy ~7GB on this disk; then the normal app UI appears. Confirm via `Get-ChildItem "$env:LOCALAPPDATA\com.codesense.desktop"` that `model\astra.gguf`, `model\astra.gguf.done`, `grype-db\vulnerability.db`, and `grype-db\vulnerability.db.done` all exist, and that `llm_health()` reports ok (reuse the P0 session's verification approach: hit the backend's health endpoint or run a real scan and check `metrics.llm.available`).

- [ ] **Step 3: Confirm the second launch skips reassembly**

Run: `Start-Process "client\src-tauri\target\release\codesense.exe"` again (without deleting `%LOCALAPPDATA%` this time).
Expected: the "Setting up" screen either doesn't appear or flashes for under a second — no multi-minute wait — since `ensure_ready` short-circuits on the `.done` markers.

- [ ] **Step 4: Confirm the retry-then-fail path**

```powershell
Get-Process codesense,codesense-server,llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item "$env:LOCALAPPDATA\com.codesense.desktop" -Recurse -Force -ErrorAction SilentlyContinue
# Corrupt one installed shard so reassembly's checksum verification must fail.
$part = "client\src-tauri\target\release\resources\model\astra.gguf.part000"
$bytes = [System.IO.File]::ReadAllBytes($part)
$bytes[0] = $bytes[0] -bxor 0xFF
[System.IO.File]::WriteAllBytes($part, $bytes)
Start-Process "client\src-tauri\target\release\codesense.exe"
```

Expected: the app auto-retries once (still fails, since the corrupted byte persists on disk) and then shows the "Setup failed" screen with a checksum-mismatch reason and a Retry button — not a silent fall-through to deterministic-only scanning. Restore the original byte (`$bytes[0] = $bytes[0] -bxor 0xFF` again, since XOR is self-inverse) and click Retry to confirm it recovers.

- [ ] **Step 5: Restore the corrupted shard and clean up test state**

```powershell
Get-Process codesense,codesense-server,llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
```

(The byte was already restored in Step 4 before clicking Retry — this step just ensures no test processes are left running.)

---

## Self-review notes

- **Spec coverage:** §5.1 (splitter) → Tasks 4–5. §5.2 (Rust module) → Task 2. §5.3 (main.rs) → Task 3. §5.4 (frontend) → Tasks 6–9. §8 (testing) → Task 2's unit tests + Task 10's e2e protocol. All spec sections have a corresponding task.
- **Type/name consistency checked:** `AssetSpec`, `ReassemblyError`, `ensure_ready`, `MODEL_ASSET`/`GRYPE_DB_ASSET` (Task 2) match their use in Task 3. The Tauri command name `retry_asset_setup` (Task 3's `#[tauri::command] fn retry_asset_setup`) matches the frontend's `invoke('retry_asset_setup')` string (Task 7) exactly — Tauri's `generate_handler!` macro uses the Rust function name verbatim as the invoke key. `AssetSetupState`'s three variants (`pending`/`ready`/`failed`) are used identically across Tasks 7, 8, and 9.
- **Out of scope, confirmed with the user:** cleaning up the pre-existing dirty `week6` working tree (uncommitted P0-fix changes, `downloadBootstrapper` webview setting, etc.) is a separate, later effort and is not touched by any task above.
