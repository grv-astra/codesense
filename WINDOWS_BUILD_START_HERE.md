# Code Sense — Windows build: START HERE

This bundle contains the complete Code Sense source (all 7 phases) plus the
build automation. Build it into the offline desktop installer in one command —
after installing the toolchain and supplying two large AI files that can't ship
inside a source zip.

## 1. Install the toolchain (one-time, on the Windows machine)
- **Python 3.11+** — https://www.python.org/downloads/  (check "Add to PATH")
- **Node.js LTS** — https://nodejs.org/
- **Rust** — https://rustup.rs/  (installs `cargo`, `rustc`)
- **Visual Studio Build Tools** with the "Desktop development with C++" workload
  (Tauri/Rust need the MSVC linker) — https://visualstudio.microsoft.com/downloads/
- WebView2 runtime is already on Windows 10/11; only needed explicitly for a
  *fully offline* installer (see step 2).

`winget` one-liner (run in an elevated PowerShell):
```powershell
winget install -e Python.Python.3.12 OpenJS.NodeJS.LTS Rustlang.Rustup Microsoft.VisualStudio.2022.BuildTools
```

## 2. Supply the two AI files (large/external — not in this zip)
- **`astra-Q4_K_M.gguf`** — the quantized model. Produce it on a box with
  [llama.cpp](https://github.com/ggml-org/llama.cpp) + the Astra model using
  `scripts/offline_ai/convert_model_to_gguf.sh`, or copy a pre-converted GGUF.
- **`llama-server.exe`** — download from a llama.cpp Windows release.
- *(optional, for a guaranteed-offline installer)* a **fixed-version WebView2
  runtime** folder — https://developer.microsoft.com/microsoft-edge/webview2/

> The SBOM tools (Syft/Grype/Grant/Cosign) and the Grype vulnerability DB are
> downloaded automatically by the build script (needs internet *during the build*).

## 3. Build (one command)
From the extracted folder, in PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1 `
   -ModelGguf C:\path\to\astra-Q4_K_M.gguf `
   -LlamaServer C:\path\to\llama-server.exe `
   -WebView2 C:\path\to\webview2-fixed\ `
   -IconLogo .\client\public\CSlogo.png
```
(`-WebView2` and `-IconLogo` are optional.)

## 4. Result
```
client\src-tauri\target\release\bundle\nsis\Code Sense_0.1.0_x64-setup.exe
```
Install it; first launch runs the setup wizard (create admin), then the app runs
offline for 90 days. Full detail and the manual step-by-step are in **BUILD.md**.
