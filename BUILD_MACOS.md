# Building the Code Sense offline macOS desktop app

This produces a single **Developer ID-signed, notarized, stapled `.dmg`** for **Apple
Silicon (arm64)** that runs fully offline — no MongoDB, no external LLM server, no
licensing server. It bundles the Django backend (SQLite), a quantized GGUF served by
llama.cpp (Metal), the SBOM toolchain, and a frozen Grype DB inside a Tauri shell.

> **Run these on an Apple Silicon Mac** with: Xcode Command Line Tools (`xcode-select
> --install`), Rust + `cargo`, Node + npm, Python 3.11+, an **Apple Developer ID
> Application** certificate in the login keychain, notarization credentials, and network
> access (to fetch tool binaries + the Grype DB once, and to notarize). The repo's code
> (Phases 1–7) is complete and CI-tested on Linux/macOS; the steps below are the
> artifact/packaging steps that require macOS + large downloads + signing and so were
> **not executed in CI**. This is the macOS counterpart of [`BUILD.md`](BUILD.md).

## What's already done in the code (Phases 1–7)
Identical to the Windows build — the backend, AI wiring, SBOM resolver, frontend, and
Tauri shell are cross-platform. The only macOS-specific code is in **P4**: the offline
license writes its redundant "second copy" to a plist at
`~/Library/Preferences/com.codesense.desktop.license.plist` (the Windows build uses the
registry), so deleting the per-user `license.json` alone does not reset the 90-day clock.

## Quick build (one command)

On an Apple Silicon Mac, after producing the GGUF (step 2) and obtaining a Metal
`llama-server`:

```bash
APPLE_SIGNING_IDENTITY="Developer ID Application: Acme (AB12CD34EF)" \
APPLE_ID=dev@acme.com APPLE_PASSWORD=abcd-efgh-ijkl-mnop APPLE_TEAM_ID=AB12CD34EF \
MODEL_GGUF=dist/model/astra-Q4_K_M.gguf \
LLAMA_SERVER=~/llama.cpp/build/bin/llama-server \
ICON_LOGO=client/public/CSlogo.png \
  ./scripts/build_macos.sh
```

`build_macos.sh` freezes the backend, downloads the SBOM toolchain, snapshots the Grype
DB, stages everything into the Tauri bundle, and builds + signs + notarizes + staples the
DMG. Omit the `APPLE_*` vars for an unsigned local test build (users would then need
`xattr -dr com.apple.quarantine "Code Sense.app"`). Manual breakdown below.

## Build steps

### 1. Backend → single binary (PyInstaller)
```bash
cd server
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pyinstaller
.venv/bin/pyinstaller codesense.spec
# -> server/dist/codesense-server   (a Mach-O arm64 binary, no .exe)
```
If hardened-runtime library validation later rejects the at-runtime-extracted dylibs even
with the entitlements below, rebuild as a PyInstaller `onedir` (cleaner per-file signing).

### 2. AI model → GGUF + Metal llama-server  (Phase 2)
```bash
LLAMA_CPP=~/llama.cpp QUANT=Q4_K_M scripts/offline_ai/convert_model_to_gguf.sh \
  Astra_Code_reviewer_full/Astra_Code_reviewer_full dist/model
```
**`llama-server` must be self-contained.** A default llama.cpp build dynamically links its
own `@rpath` dylibs (libllama, libggml-*) **and Homebrew's OpenSSL** — none of which exist
on a clean Mac, so the bundled sidecar would fail to launch. Build it **static** (Metal
embedded, no OpenSSL/curl), which yields a single ~16 MB binary linking only system libs:
```bash
cd ~/llama.cpp
cmake -B build-static -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
  -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DLLAMA_CURL=OFF \
  -DCMAKE_DISABLE_FIND_PACKAGE_OpenSSL=ON -DCMAKE_DISABLE_FIND_PACKAGE_CURL=ON
cmake --build build-static -j --target llama-server
# verify self-contained: `otool -L build-static/bin/llama-server` → only /System + /usr/lib
```

### 3. SBOM tools + frozen Grype DB  (Phase 3)
```bash
TARGET_OS=darwin TARGET_ARCH=arm64 scripts/offline_sbom/fetch_offline_tools.sh  # syft/grype/grant/cosign
GRYPE_DB_CACHE_DIR=dist/grype-db grype db update                                # DB snapshot
```

### 4. Stage Tauri bundle inputs
Tauri appends the target triple to `externalBin` names (`-aarch64-apple-darwin`), and
macOS needs **no WebView2** (system WKWebView):
```
binaries/codesense-server-aarch64-apple-darwin   (step 1)
binaries/llama-server-aarch64-apple-darwin       (step 2)
resources/tools/{syft,grype,grant,cosign}        (step 3)
resources/model/astra.gguf                       (step 2)
resources/grype-db/                              (step 3)
icons/{32x32.png,128x128.png,icon.icns}          (npx @tauri-apps/cli icon logo.png)
```

### 5. Build the signed/notarized installer  (Phase 6/7)
```bash
cd client
npm install
# APPLE_* exported in the environment drive codesign + notarytool + staple:
npx @tauri-apps/cli build --bundles app,dmg --config src-tauri/tauri.macos.conf.json
# -> client/src-tauri/target/release/bundle/dmg/Code Sense_0.1.0_aarch64.dmg
```
Signing uses the hardened runtime with `src-tauri/codesense.entitlements`
(`allow-jit`, `allow-unsigned-executable-memory`, `disable-library-validation`) — needed
by the PyInstaller-frozen Python and llama.cpp Metal. Trim to the minimum that still
launches after the first real build.

### 6. Verify signing, notarization & offline Gatekeeper
```bash
APP="client/src-tauri/target/release/bundle/macos/Code Sense.app"
codesign --verify --deep --strict "$APP"
spctl -a -t exec -vvv "$APP"                       # -> accepted, source=Developer ID
xcrun stapler validate client/src-tauri/target/release/bundle/dmg/*.dmg
```
**Stapling matters:** it lets Gatekeeper validate on a machine with **no network**, which
is the whole point of an offline product. Notarization itself needs network at build time
only.

## First-run behavior
Launch → Tauri starts `codesense-server` (migrates SQLite under
`~/Library/Application Support/com.codesense.desktop`) + `llama-server` → the UI detects no
admin and shows the setup wizard → creating the admin stamps the license `first_seen` (to
both `license.json` and the plist second copy). Tray: Open / Pause AI engine / Quit. The
app expires 90 days after first run (read-only grace thereafter).

## Per-build expiry / secret
Set before the build so they're baked into the backend env (or have the Tauri launcher
export them): `LICENSE_DURATION_DAYS`, `LICENSE_SECRET`, `DJANGO_SECRET_KEY` (else a
per-install key is generated and persisted under the app data dir).
