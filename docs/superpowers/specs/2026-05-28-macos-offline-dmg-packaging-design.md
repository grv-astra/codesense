# Code Sense — Offline macOS Desktop Packaging (DMG, Apple Silicon)

- **Date:** 2026-05-28
- **Status:** Approved design (implementation in progress)
- **Author:** Brainstormed with Claude
- **Repo:** `yacm` (client = React/Vite, server = Django, model = `Astra_Code_reviewer_full`)
- **Companion:** mirrors [`2026-05-28-windows-offline-tauri-packaging-design.md`](2026-05-28-windows-offline-tauri-packaging-design.md); see [`BUILD_MACOS.md`](../../../BUILD_MACOS.md).

## 1. Problem statement

We need the macOS counterpart of the offline Windows desktop app: a **single, installable
macOS desktop application** shipped as a **Developer ID-signed, notarized, stapled `.dmg`**
that runs fully **offline** (no MongoDB, no external LLM server, no central license
server), feels native (Tauri shell + tray), and enforces the same 3-month-from-first-run
license that degrades to read-only on expiry.

Phases 1–6 of the offline initiative are already cross-platform, so this is the macOS
re-target of **Phase 7 (packaging)** plus **one backend gap**: the offline license's
redundant "second copy" is implemented via the Windows registry and no-ops on macOS.

## 2. Goals / non-goals

### Goals
- One `.dmg` producing one launchable `.app`; clean Gatekeeper install (no "unidentified developer" / "damaged" warnings).
- Self-contained: SQLite, bundled AI inference (Metal), bundled SBOM tooling, offline license — identical functionality (SAST + SBOM/SCA, projects, findings, RBAC, dashboard) to the Windows build.
- Reuse the existing Tauri shell and PyInstaller/sidecar pipeline; add only macOS-specific packaging + the license second store.

### Non-goals
- Universal / Intel (x86_64) builds — **arm64 only** (additive follow-up).
- Auto-update / online license renewal; `.pkg` installer; migrating a live dataset.
- Cryptographically unbreakable DRM (same "casual misuse" threat model as Windows).

## 3. Locked decisions (from brainstorming)

| Topic | Decision |
|-------|----------|
| Target hardware | **Apple Silicon (arm64)**, `aarch64-apple-darwin` |
| Distribution | **Developer ID** codesign → **notarize + staple** `.dmg` |
| License 2nd copy | **plist "registry analogue"** at `~/Library/Preferences/com.codesense.desktop.license.plist` (outside the data dir) |
| AI acceleration | **Metal-enabled** `llama-server` (one-line swap to a CPU build for strict Windows parity) |
| Installer style | Tauri `dmg` target (drag-to-Applications) |

## 4. Architecture (vs. the EXE)

Same shape as Windows with three substitutions: **WKWebView replaces WebView2** (part of
macOS — the entire WebView2 fixed-runtime bundling step disappears); the bundle target is
`app`+`dmg`; binaries carry the `aarch64-apple-darwin` triple suffix.

```
┌──────────────── Code Sense.app (Tauri) ─────────────────────────────┐
│  WKWebView window ──HTTP──▶ Django (waitress, 127.0.0.1:8585)        │
│  (React UI, prebuilt)        ├─ SQLite (~/Library/Application Support)│
│  system tray + menu          ├─ spawns ▶ llama-server (GGUF, Metal)   │
│                              └─ shells ▶ syft / grype / grant / cosign│
└───────────────────────────────────────────────────────────────────────┘
```
All listeners bind to **127.0.0.1 only**. Sidecar/lifecycle/tray logic
([`client/src-tauri/src/main.rs`](../../../client/src-tauri/src/main.rs)) is already
cross-platform; `app_local_data_dir()` resolves to
`~/Library/Application Support/com.codesense.desktop`.

## 5. Reused unchanged

- [`server/run_server.py`](../../../server/run_server.py) — waitress entrypoint (OS-agnostic).
- [`server/codesense.spec`](../../../server/codesense.spec) — PyInstaller; run **on macOS** → a Mach-O `codesense-server`.
- The Tauri shell, the frontend (fixed `127.0.0.1:8585` URL, first-run wizard, license UX), and the env contract (`CODESENSE_DATA_DIR`, `VLLM_*`, `SCANNER_TOOLS_DIR`, `GRYPE_DB_CACHE_DIR`, `COSIGN_KEY_DIR`).
- [`scripts/offline_sbom/fetch_offline_tools.sh`](../../../scripts/offline_sbom/fetch_offline_tools.sh) (already supports `TARGET_OS=darwin TARGET_ARCH=arm64`) and [`scripts/offline_ai/convert_model_to_gguf.sh`](../../../scripts/offline_ai/convert_model_to_gguf.sh) (OS-independent).

## 6. License redundant store on macOS (the only code change)

[`server/licenses/services/offline_license.py`](../../../server/licenses/services/offline_license.py)
already takes the **earliest valid `first_seen` across all sources** and self-heals; the
`last_seen` high-water-mark detects clock rollback. We add a macOS source next to the
no-op `_registry_*`:

- `_plist_read()` / `_plist_write()` (gated on `sys.platform == "darwin"`, stdlib `plistlib`) read/write the signed record **directly** (not via `defaults`/NSUserDefaults, so cfprefsd never caches it).
- Path defaults to `~/Library/Preferences/com.codesense.desktop.license.plist` — **outside** `DATA_DIR` — and is overridable via `settings.LICENSE_PLIST_PATH` (used for hermetic tests).
- Wired into `_write_all()` and the `get_state()` sources list. Record shape unchanged.

Net effect: deleting the per-user `license.json` no longer resets the 90-day clock,
matching the Windows file+registry tamper bar.

## 7. Packaging changes / new files

- [`client/src-tauri/tauri.macos.conf.json`](../../../client/src-tauri/tauri.macos.conf.json) — `bundle.targets: ["app","dmg"]`, `bundle.macOS` (`minimumSystemVersion 11.0`, `entitlements`, DMG window layout); passed via `--config` so the base config stays Windows-valid.
- [`client/src-tauri/codesense.entitlements`](../../../client/src-tauri/codesense.entitlements) — `allow-jit`, `allow-unsigned-executable-memory`, `disable-library-validation` (PyInstaller-frozen Python + llama.cpp Metal under hardened runtime); trim after first signed build.
- `client/src-tauri/tauri.conf.json` — add `icons/icon.icns` to the icon array.
- [`scripts/build_macos.sh`](../../../scripts/build_macos.sh) — mirror of `build_windows.ps1`: PyInstaller → stage sidecars/model/tools/Grype-DB → icons → `tauri build --bundles app,dmg`. Signing/notarization/stapling driven by `APPLE_*` env vars.
- `BUILD_MACOS.md` — the macOS build runbook.

## 8. Signing, notarization & offline Gatekeeper

Codesign the `.app` and all nested sidecars (`codesense-server`, `llama-server`,
syft/grype/grant/cosign) with a **Developer ID Application** cert under the hardened
runtime; then `notarytool` + **staple**. Tauri performs all of this when
`APPLE_SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID` (or an App Store
Connect API key) are present. **Stapling is required** so a freshly-installed,
network-disconnected Mac validates the app on first launch (notarization needs network at
build time only). Verify with `codesign --verify --deep`, `spctl -a -t exec`, and
`xcrun stapler validate`.

## 9. Data & filesystem layout (macOS)

- **App:** `/Applications/Code Sense.app` (backend + llama-server + GGUF + syft/grype/grant/cosign + Grype DB + embedded license public key inside `Resources`).
- **Per-user data:** `~/Library/Application Support/com.codesense.desktop/` — `app.sqlite3`, Cosign keys, `license.json`, logs, scan temp.
- **License 2nd copy:** `~/Library/Preferences/com.codesense.desktop.license.plist`.
- **Ports:** backend `127.0.0.1:8585`, `llama-server` `127.0.0.1:8001`.

## 10. Testing strategy

- **Unit:** reuse the existing backend suite; add macOS license-store tests (recover-from-plist after deleting `license.json`; forged-plist → `TAMPERED`). All license tests override `LICENSE_PLIST_PATH` to a temp path so the suite stays hermetic on macOS build hosts.
- **E2E on a clean, network-disconnected Apple Silicon Mac:** mount DMG → drag to `/Applications` → launch (proves stapling) → first-run wizard → AI code scan (Metal) + SBOM scan → dashboard/findings → tray Pause AI / Quit / relaunch → simulate expiry + clock rollback → confirm read-only grace + banner → delete `license.json` and confirm the clock does **not** reset.

## 11. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Hardened runtime blocks frozen Python / Metal JIT | Ship the entitlements (§7); smoke-test signed sidecars early; `onedir` fallback for PyInstaller |
| Nested sidecars unsigned → app won't launch on arm64 | Sign every binary before bundling; Tauri signs nested code; verify with `codesign --verify --deep` |
| Notarization requires build-time network | One-time at build; runtime stays fully offline via the stapled ticket |
| Grype DB staleness | Refresh at each repackage (same as Windows) |
| Future Intel-Mac request | Out of scope (arm64-only); a universal build is an additive follow-up |
