# Code Sense — Tauri desktop shell (Phase 6)

A thin Rust shell (WebView2) that hosts the built React UI and owns two sidecars:

```
Code Sense.exe (Tauri)
├─ WebView2 window ── HTTP ─▶ codesense-server (Django/waitress) 127.0.0.1:8585
│                              └─ SQLite + cosign keys in %LOCALAPPDATA%\com.codesense.desktop
├─ sidecar ─▶ llama-server (llama.cpp) 127.0.0.1:8001  ← quantized GGUF
└─ tray: Open · Pause/Resume AI engine · Quit  (close = hide to tray)
```

`src/main.rs` spawns both sidecars on launch, wires the tray (Pause toggles
`llama-server` to free its RAM; Quit kills both sidecars; window-close hides to
tray so background scans continue), and sets the backend's env vars
(`CODESENSE_DATA_DIR`, `VLLM_BASE_URL`, `SCANNER_TOOLS_DIR`, `GRYPE_DB_CACHE_DIR`,
`COSIGN_KEY_DIR`) — the Phases 1–4 env contract.

## NOT built in CI
This sandbox has no Rust/Tauri/WebView2, so this scaffold is **not compiled here**.
Build + validate it on a Windows host. Minor Tauri 2.x API details may need
adjusting against the exact resolved crate versions.

## Prerequisites (Windows build host)
- Rust (stable) + `cargo`
- Tauri CLI: `npm i -D @tauri-apps/cli` (or `cargo install tauri-cli`)
- Node + the client deps (`npm install` in `client/`)

## Populate before building (gitignored — produced by Phases 2/3/7)
- `binaries/codesense-server-x86_64-pc-windows-msvc.exe` — PyInstaller backend (Phase 7)
- `binaries/llama-server-x86_64-pc-windows-msvc.exe` — llama.cpp (Phase 2)
- `binaries/syft.exe`, `grype.exe`, `grant.exe`, `cosign.exe` — `scripts/offline_sbom/fetch_offline_tools.sh` (Phase 3)
- `resources/model/astra-Q4_K_M.gguf` — `scripts/offline_ai/convert_model_to_gguf.sh` (Phase 2)
- `resources/grype-db/` — Grype DB snapshot (Phase 3)
- `webview2/` — fixed-version WebView2 runtime (for guaranteed-offline install)
- `icons/` — `32x32.png`, `128x128.png`, `icon.ico` (`npx @tauri-apps/cli icon path/to/logo.png` generates these)

> Tauri appends the target triple to `externalBin` names, hence the
> `-x86_64-pc-windows-msvc` suffix on the bundled binaries.

## Build
```bash
cd client
npm install
npx @tauri-apps/cli build      # runs `npm run build`, compiles Rust, bundles NSIS installer
# -> src-tauri/target/release/bundle/nsis/Code Sense_0.1.0_x64-setup.exe
```
Dev loop: `npx @tauri-apps/cli dev`.
