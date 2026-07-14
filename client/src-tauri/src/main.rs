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
use std::sync::atomic::{AtomicBool, Ordering};
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
    /// Guards against two concurrent `ensure_assets_then_spawn` runs (startup
    /// racing a `retry_asset_setup` call) both writing the same `.tmp` file.
    setup_in_progress: AtomicBool,
    /// Set at the start of `shutdown()` so an in-flight reassembly that
    /// finishes afterwards knows not to spawn sidecars nobody will kill.
    quitting: AtomicBool,
    /// Mirrors the last `asset-setup-*` event so a webview that finishes
    /// loading and registers its listeners *after* reassembly already
    /// completed (the common case once `.done` markers exist — reassembly
    /// then takes well under a second, easily beating the webview's JS
    /// bootstrap) can still learn the outcome via `get_asset_setup_status`
    /// instead of waiting forever for an event that already fired.
    setup_status: Mutex<SetupStatus>,
}

#[derive(Clone, Default)]
enum SetupStatus {
    #[default]
    Pending,
    Ready,
    Failed {
        asset: String,
        reason: String,
    },
}

impl SetupStatus {
    fn to_json(&self) -> serde_json::Value {
        match self {
            SetupStatus::Pending => serde_json::json!({ "status": "pending" }),
            SetupStatus::Ready => serde_json::json!({ "status": "ready" }),
            SetupStatus::Failed { asset, reason } => {
                serde_json::json!({ "status": "failed", "asset": asset, "reason": reason })
            }
        }
    }
}

/// RAII guard that resets `AppState::setup_in_progress` back to `false` on
/// every exit path (normal return, early return, or panic) out of
/// `ensure_assets_then_spawn`'s thread body. Owns a cloned `AppHandle`
/// (cheap — it's a handle, not the state itself) so it isn't tied to the
/// lifetime of any single `state.setup_in_progress` borrow.
struct SetupInProgressGuard {
    app: tauri::AppHandle,
}

impl Drop for SetupInProgressGuard {
    fn drop(&mut self) {
        self.app
            .state::<AppState>()
            .setup_in_progress
            .store(false, Ordering::SeqCst);
    }
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
            // ManifestMissing/ManifestCorrupt indicate a packaging defect, not
            // a transient condition — retrying can never succeed, so bail out
            // on the first attempt instead of burning a second identical try.
            Err(e @ (ReassemblyError::ManifestMissing | ReassemblyError::ManifestCorrupt(_))) => {
                return Err(e);
            }
            Err(e) => last_err = Some(e),
        }
    }
    Err(last_err.expect("loop runs at least once"))
}

/// Records a failure in `AppState::setup_status` (so a webview that wasn't
/// listening yet can pick it up via `get_asset_setup_status`) and emits
/// `asset-setup-failed` for webviews that already are.
fn fail_setup(app: &tauri::AppHandle, asset: &str, reason: String) {
    let state = app.state::<AppState>();
    *state.setup_status.lock().unwrap() = SetupStatus::Failed {
        asset: asset.to_string(),
        reason: reason.clone(),
    };
    let _ = app.emit(
        "asset-setup-failed",
        serde_json::json!({ "asset": asset, "reason": reason }),
    );
}

/// Reassembles both bundled assets (model, grype-db) on a background thread,
/// then spawns both sidecars once they're verified ready. Emits
/// `asset-setup-complete` on success or `asset-setup-failed` (with a
/// specific reason) if either asset fails after its retry — the sidecars are
/// never spawned against unverified assets. Re-entrant: also used as the
/// `retry_asset_setup` command's implementation.
///
/// Also mirrors the outcome into `AppState::setup_status` rather than
/// relying solely on these events: once `.done` markers exist, reassembly
/// completes in well under a second — often faster than the webview can
/// finish loading its JS and registering event listeners, so an event-only
/// signal can fire before anyone is listening and be lost forever. The
/// frontend's `get_asset_setup_status` command call (issued right after it
/// registers its listeners) closes that race by picking up whatever already
/// happened; the listeners remain necessary for the slower first-run case
/// where reassembly is still in progress when the frontend mounts.
fn ensure_assets_then_spawn(app: tauri::AppHandle) {
    std::thread::spawn(move || {
        // Startup and `retry_asset_setup` (exposed to the frontend) can both
        // land here concurrently. A retry request that arrives while one run
        // is already in flight is simply a no-op, not queued or errored — it
        // must NOT proceed, since two runs would race on the same `.tmp` path.
        if app
            .state::<AppState>()
            .setup_in_progress
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
        {
            return;
        }
        // From here on, every exit path (early return or normal completion)
        // must clear the flag again — the guard does that on drop.
        let _guard = SetupInProgressGuard { app: app.clone() };

        let model_resource = match app.path().resolve("resources/model", BaseDirectory::Resource) {
            Ok(p) => p,
            Err(_) => {
                fail_setup(&app, "model", "failed to resolve resources/model directory".to_string());
                return;
            }
        };
        let grype_resource = match app.path().resolve("resources/grype-db", BaseDirectory::Resource) {
            Ok(p) => p,
            Err(_) => {
                fail_setup(&app, "grype-db", "failed to resolve resources/grype-db directory".to_string());
                return;
            }
        };
        let data_dir = match app.path().app_local_data_dir() {
            Ok(p) => p,
            Err(_) => {
                // This failure blocks both assets, not just the model — "setup"
                // isn't a real asset name, signaling a setup-wide failure.
                fail_setup(&app, "setup", "failed to resolve app data directory".to_string());
                return;
            }
        };
        let model_target_dir = data_dir.join("model");
        let grype_target_dir = data_dir.join("grype-db");

        let model_path = match reassemble_with_retry(
            &app, "model", &model_resource, &model_target_dir, &MODEL_ASSET,
        ) {
            Ok(path) => path,
            Err(e) => {
                let reason = if matches!(e, ReassemblyError::ManifestMissing | ReassemblyError::ManifestCorrupt(_)) {
                    format!("reinstall required: {e}")
                } else {
                    e.to_string()
                };
                fail_setup(&app, "model", reason);
                return;
            }
        };

        if let Err(e) = reassemble_with_retry(
            &app, "grype-db", &grype_resource, &grype_target_dir, &GRYPE_DB_ASSET,
        ) {
            let reason = if matches!(e, ReassemblyError::ManifestMissing | ReassemblyError::ManifestCorrupt(_)) {
                format!("reinstall required: {e}")
            } else {
                e.to_string()
            };
            fail_setup(&app, "grype-db", reason);
            return;
        }

        {
            let state = app.state::<AppState>();
            *state.model_path.lock().unwrap() = Some(model_path.clone());
            *state.grype_db_dir.lock().unwrap() = Some(grype_target_dir.clone());
        }

        // If the user quit while reassembly was still running, shutdown()
        // already ran and there is nothing left to kill these sidecars — so
        // don't start them, and don't bother signaling a UI that's going away.
        if app.state::<AppState>().quitting.load(Ordering::SeqCst) {
            return;
        }

        *app.state::<AppState>().setup_status.lock().unwrap() = SetupStatus::Ready;
        let _ = app.emit("asset-setup-complete", ());

        let state = app.state::<AppState>();
        *state.backend.lock().unwrap() = spawn_backend(&app, &grype_target_dir);
        *state.llama.lock().unwrap() = spawn_llama(&app, &model_path);
    });
}

#[tauri::command]
fn get_asset_setup_status(app: tauri::AppHandle) -> serde_json::Value {
    app.state::<AppState>().setup_status.lock().unwrap().to_json()
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
    // Set before killing anything so a reassembly thread that's still running
    // sees it and skips spawning sidecars we'd otherwise never get to kill.
    state.quitting.store(true, Ordering::SeqCst);
    kill(&state.backend);
    kill(&state.llama);
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![retry_asset_setup, get_asset_setup_status])
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
