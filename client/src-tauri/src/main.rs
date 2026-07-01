// Code Sense desktop shell (Tauri v2).
//
// Owns two sidecars and the app lifecycle:
//   * codesense-server  — the Django backend (PyInstaller-frozen, served by waitress) on 127.0.0.1:8585
//   * llama-server      — llama.cpp serving the quantized GGUF on 127.0.0.1:8001
// Tray menu: Open / Pause AI engine (frees the model's RAM) / Quit. Closing the
// window hides to tray so background scans keep running; Quit tears down both
// sidecars cleanly so no orphan processes or held ports remain.
//
// SCAFFOLD: this is NOT compiled in the CI sandbox (no Rust/Tauri/WebView2).
// Validate with `cargo tauri build` on a Windows host once binaries/, resources/,
// webview2/, and icons/ are populated (see README.md). Minor Tauri 2.x API
// details may need adjusting against the exact crate versions resolved.
#![cfg_attr(all(not(debug_assertions), target_os = "windows"), windows_subsystem = "windows")]

use std::sync::Mutex;

use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    path::BaseDirectory,
    tray::TrayIconBuilder,
    Manager, RunEvent, WindowEvent,
};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const BACKEND_PORT: &str = "8585";
const LLAMA_PORT: &str = "8001";

#[derive(Default)]
struct AppState {
    backend: Mutex<Option<CommandChild>>,
    llama: Mutex<Option<CommandChild>>,
    ai_paused: Mutex<bool>,
}

fn spawn_backend(app: &tauri::AppHandle) -> Option<CommandChild> {
    let data_dir = app.path().app_local_data_dir().ok()?;
    let _ = std::fs::create_dir_all(&data_dir);
    let keys_dir = data_dir.join("keys");
    let tools_dir = app
        .path()
        .resolve("resources/tools", BaseDirectory::Resource)
        .unwrap_or_default();
    let grype_db = app
        .path()
        .resolve("resources/grype-db", BaseDirectory::Resource)
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
        .env("GRYPE_DB_CACHE_DIR", grype_db.to_string_lossy().to_string())
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

fn spawn_llama(app: &tauri::AppHandle) -> Option<CommandChild> {
    let model = app
        .path()
        .resolve("resources/model/astra.gguf", BaseDirectory::Resource)
        .ok()?;
    let mut cmd = app
        .shell()
        .sidecar("llama-server")
        .ok()?
        .args([
            "--model",
            &model.to_string_lossy(),
            "--host",
            "127.0.0.1",
            "--port",
            LLAMA_PORT,
            "--ctx-size",
            "4096",
            "--alias",
            "astra-code-reviewer",
            "--api-key",
            "EMPTY",
        ]);

    // The Windows llama-server.exe is a thin (~9KB) launcher that dynamically
    // links its runtime DLLs (llama-server-impl.dll, llama.dll, ggml*.dll,
    // mtmd.dll, libomp*). The build stages those into resources/llama-runtime/;
    // the sidecar exe lives at the install root, so the DLLs are NOT beside it.
    // Prepend the runtime dir to the child's PATH so the loader resolves them.
    // No-op on macOS (single Metal binary; the dir is absent there).
    #[cfg(target_os = "windows")]
    if let Ok(runtime) = app
        .path()
        .resolve("resources/llama-runtime", BaseDirectory::Resource)
    {
        if runtime.is_dir() {
            let prev = std::env::var("PATH").unwrap_or_default();
            cmd = cmd.env("PATH", format!("{};{}", runtime.to_string_lossy(), prev));
        }
    }

    cmd.spawn().map(|(_rx, child)| child).ok()
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
        .setup(|app| {
            let handle = app.handle().clone();
            {
                let state = app.state::<AppState>();
                *state.backend.lock().unwrap() = spawn_backend(&handle);
                *state.llama.lock().unwrap() = spawn_llama(&handle);
            }

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
                            let child = spawn_llama(app);
                            *state.llama.lock().unwrap() = child;
                            *paused = false;
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
