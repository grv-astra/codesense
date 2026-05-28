# Building the Code Sense offline Windows desktop app

This produces a single NSIS installer that runs fully offline — no MongoDB, no
external LLM server, no licensing server. It bundles the Django backend (SQLite),
a quantized GGUF served by llama.cpp, the SBOM toolchain, and a frozen Grype DB
inside a Tauri shell.

> **Run these on a Windows build host** with: Rust + `cargo`, Node + npm, Python
> 3.11+, and network access (to fetch tool binaries + the Grype DB once). The
> repo's code (Phases 1–7) is complete and CI-tested on Linux/macOS; the steps
> below are the artifact/packaging steps that require Windows + large downloads
> and so were **not executed in CI**.

## What's already done in the code (Phases 1–7)
- **P1** MongoDB → SQLite (Django ORM); first-run setup endpoint. *(58 tests)*
- **P2** Dead RAG removed; `llm.py` is env-driven (points at a local llama-server).
- **P3** Syft/Grype/Grant/Cosign resolved from a bundled dir; Grype DB pinnable offline.
- **P4** Offline license (3 months from first run, tamper + clock-rollback aware,
  read-only grace). App is fully Mongo-free (pymongo removed).
- **P5** Frontend: fixed `127.0.0.1:8585` backend URL, first-run wizard, license banner.
- **P6** Tauri shell scaffold (`client/src-tauri/`): sidecars + tray + shutdown.
- **P7** Prod settings (DEBUG off, generated SECRET_KEY, locked ALLOWED_HOSTS/CORS);
  `server/run_server.py` (waitress entrypoint, verified) + PyInstaller spec.

## Quick build (one command)

On a Windows host with Rust, Node, and Python installed, after producing the
GGUF model (step 2 below) and obtaining `llama-server.exe`:

```powershell
.\scripts\build_windows.ps1 `
   -ModelGguf .\dist\model\astra-Q4_K_M.gguf `
   -LlamaServer C:\llama.cpp\build\bin\llama-server.exe `
   -WebView2 C:\webview2-fixed\ `
   -IconLogo .\client\public\CSlogo.png
```

`build_windows.ps1` freezes the backend, downloads the SBOM toolchain, snapshots
the Grype DB, stages everything into the Tauri bundle, and builds the NSIS
installer. The manual breakdown of what it does is below.

## Build steps

### 1. Backend → single exe (PyInstaller)
```powershell
cd server
py -m venv .venv; .venv\Scripts\pip install -r requirements.txt pyinstaller
.venv\Scripts\pyinstaller codesense.spec
# -> server\dist\codesense-server.exe   (verify: codesense-server.exe 127.0.0.1 8585)
```

### 2. AI model → GGUF + llama-server  (Phase 2)
```bash
LLAMA_CPP=~/llama.cpp QUANT=Q4_K_M scripts/offline_ai/convert_model_to_gguf.sh \
  Astra_Code_reviewer_full/Astra_Code_reviewer_full dist/model
# grab a prebuilt llama-server.exe from the llama.cpp releases
```

### 3. SBOM tools + frozen Grype DB  (Phase 3)
```bash
TARGET_OS=windows scripts/offline_sbom/fetch_offline_tools.sh   # syft/grype/grant/cosign .exe
GRYPE_DB_CACHE_DIR=dist/grype-db grype db update                # DB snapshot
```

### 4. Stage Tauri bundle inputs
Copy artifacts into `client/src-tauri/` (target-triple suffix on `externalBin`):
```
binaries/codesense-server-x86_64-pc-windows-msvc.exe   (step 1)
binaries/llama-server-x86_64-pc-windows-msvc.exe       (step 2)
binaries/{syft,grype,grant,cosign}.exe                 (step 3)
resources/model/astra-Q4_K_M.gguf                      (step 2)
resources/grype-db/                                    (step 3)
webview2/                                              (fixed-version WebView2 runtime)
icons/{32x32.png,128x128.png,icon.ico}                 (npx @tauri-apps/cli icon logo.png)
```

### 5. Build the installer  (Phase 6)
```bash
cd client
npm install
npx @tauri-apps/cli build
# -> client/src-tauri/target/release/bundle/nsis/Code Sense_0.1.0_x64-setup.exe
```

### 6. (Optional) Authenticode-sign the installer
```powershell
signtool sign /fd sha256 /a "Code Sense_0.1.0_x64-setup.exe"
```

## First-run behavior
Launch → Tauri starts `codesense-server` (migrates SQLite) + `llama-server` → the
UI detects no admin and shows the setup wizard → creating the admin stamps the
license `first_seen`. Tray: Open / Pause AI engine / Quit. The app expires 90 days
after first run (read-only grace thereafter); bump `LICENSE_DURATION_DAYS` or set
`LICENSE_SECRET` at build time as needed.

## Per-build expiry / secret
Set before `pyinstaller` so they're baked into the backend exe env (or have the
Tauri launcher export them): `LICENSE_DURATION_DAYS`, `LICENSE_SECRET`,
`DJANGO_SECRET_KEY` (else a per-install key is generated and persisted).
