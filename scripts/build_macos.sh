#!/usr/bin/env bash
# One-command macOS build for the Code Sense offline desktop app (Apple Silicon).
#
# The macOS counterpart of scripts/build_windows.ps1. Automates BUILD_MACOS.md:
#   1. Freeze the Django backend into `codesense-server` (PyInstaller).
#   2. Stage the provided Metal `llama-server` + the quantized GGUF.
#   3. Download the SBOM toolchain (Syft/Grype/Grant/Cosign, darwin/arm64).
#   4. Snapshot the Grype vulnerability DB for offline use.
#   5. Generate app icons (.icns).
#   6. Build a signed + notarized + stapled .dmg via the Tauri bundler.
#
# The two heavy AI inputs cannot be produced here (they need a built llama.cpp +
# the multi-GB model), so pass them in:
#   MODEL_GGUF    the quantized GGUF (scripts/offline_ai/convert_model_to_gguf.sh)
#   LLAMA_SERVER  a Metal-enabled llama-server (a llama.cpp macOS release/build)
#
# Code signing + notarization are driven by Tauri from these env vars (export
# before running for a clean Gatekeeper install; omit for an unsigned local build):
#   APPLE_SIGNING_IDENTITY   "Developer ID Application: Name (TEAMID)"
#   APPLE_ID, APPLE_PASSWORD (app-specific), APPLE_TEAM_ID
#   — or — APPLE_API_KEY, APPLE_API_ISSUER, APPLE_API_KEY_PATH
#
# Per-build expiry/secret (baked into the frozen backend's env) — optional:
#   LICENSE_DURATION_DAYS, LICENSE_SECRET, DJANGO_SECRET_KEY
#
# Example:
#   APPLE_SIGNING_IDENTITY="Developer ID Application: Acme (AB12CD34EF)" \
#   APPLE_ID=dev@acme.com APPLE_PASSWORD=abcd-efgh-ijkl-mnop APPLE_TEAM_ID=AB12CD34EF \
#   MODEL_GGUF=dist/model/astra-Q4_K_M.gguf \
#   LLAMA_SERVER=~/llama.cpp/build/bin/llama-server \
#   ICON_LOGO=client/public/CSlogo.png \
#     scripts/build_macos.sh
set -euo pipefail

# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
MODEL_GGUF="${MODEL_GGUF:-}"
LLAMA_SERVER="${LLAMA_SERVER:-}"
ICON_LOGO="${ICON_LOGO:-}"
SKIP_TOOLS="${SKIP_TOOLS:-0}"
SYFT_VERSION="${SYFT_VERSION:-1.18.1}"
GRYPE_VERSION="${GRYPE_VERSION:-0.85.0}"
GRANT_VERSION="${GRANT_VERSION:-0.2.4}"
COSIGN_VERSION="${COSIGN_VERSION:-2.4.1}"

# --------------------------------------------------------------------------- #
# Paths + helpers
# --------------------------------------------------------------------------- #
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SERVER="$REPO_ROOT/server"
CLIENT="$REPO_ROOT/client"
TAURI="$CLIENT/src-tauri"
BIN_DIR="$TAURI/binaries"
RES_TOOLS="$TAURI/resources/tools"
RES_MODEL="$TAURI/resources/model"
RES_GRYPE_DB="$TAURI/resources/grype-db"

info() { printf '\033[36m==> %s\033[0m\n' "$1"; }
ok()   { printf '\033[32m    %s\033[0m\n' "$1"; }
die()  { printf '\033[31mERROR: %s\033[0m\n' "$1" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "Required tool '$1' not found. $2"; }

# --------------------------------------------------------------------------- #
# 0. Prerequisites
# --------------------------------------------------------------------------- #
info "Checking prerequisites"
need python3 "Install Python 3.11+ (python.org or Homebrew)."
need npm     "Install Node.js LTS (nodejs.org)."
need cargo   "Install Rust from rustup.rs."
need rustc   "Install Rust from rustup.rs."
need xcrun   "Install the Xcode Command Line Tools: xcode-select --install."

TRIPLE="$(rustc -Vv | awk '/^host:/{print $2}')"
ok "Rust host triple: $TRIPLE"
[ "$TRIPLE" = "aarch64-apple-darwin" ] || \
  echo "    WARNING: this build targets Apple Silicon (aarch64-apple-darwin); host is $TRIPLE."
mkdir -p "$BIN_DIR" "$RES_TOOLS" "$RES_MODEL" "$RES_GRYPE_DB"

if [ -z "${APPLE_SIGNING_IDENTITY:-}" ]; then
  echo "    WARNING: APPLE_SIGNING_IDENTITY unset — building UNSIGNED (no notarization)."
  echo "             Users would need: xattr -dr com.apple.quarantine 'Code Sense.app'"
fi

# --------------------------------------------------------------------------- #
# 1. Backend -> codesense-server (PyInstaller)
# --------------------------------------------------------------------------- #
info "Building backend executable (PyInstaller)"
(
  cd "$SERVER"
  [ -d .venv ] || python3 -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip --quiet
  ./.venv/bin/pip install -r requirements.txt pyinstaller --quiet
  ./.venv/bin/pyinstaller codesense.spec --noconfirm --clean
)
[ -f "$SERVER/dist/codesense-server" ] || die "PyInstaller did not produce server/dist/codesense-server"
cp "$SERVER/dist/codesense-server" "$BIN_DIR/codesense-server-$TRIPLE"
chmod +x "$BIN_DIR/codesense-server-$TRIPLE"
ok "codesense-server-$TRIPLE staged"

# --------------------------------------------------------------------------- #
# 2. llama-server (provided, Metal-enabled)
# --------------------------------------------------------------------------- #
info "Staging llama-server"
[ -n "$LLAMA_SERVER" ] && [ -f "$LLAMA_SERVER" ] || \
  die "Set LLAMA_SERVER=<path to a macOS llama-server> (a llama.cpp release/build)."
cp "$LLAMA_SERVER" "$BIN_DIR/llama-server-$TRIPLE"
chmod +x "$BIN_DIR/llama-server-$TRIPLE"
ok "llama-server-$TRIPLE staged"

# --------------------------------------------------------------------------- #
# 3. Model GGUF (provided)
# --------------------------------------------------------------------------- #
info "Staging model GGUF"
[ -n "$MODEL_GGUF" ] && [ -f "$MODEL_GGUF" ] || \
  die "Set MODEL_GGUF=<path to astra-Q4_K_M.gguf> (see scripts/offline_ai/)."
cp "$MODEL_GGUF" "$RES_MODEL/astra.gguf"
ok "astra.gguf staged"

# --------------------------------------------------------------------------- #
# 4. SBOM tools (Syft / Grype / Grant / Cosign, darwin/arm64)
# --------------------------------------------------------------------------- #
if [ "$SKIP_TOOLS" != "1" ]; then
  info "Downloading SBOM tools (darwin/arm64)"
  TARGET_OS=darwin TARGET_ARCH=arm64 OUT="$RES_TOOLS" \
    SYFT_VERSION="$SYFT_VERSION" GRYPE_VERSION="$GRYPE_VERSION" \
    GRANT_VERSION="$GRANT_VERSION" COSIGN_VERSION="$COSIGN_VERSION" \
    bash "$SCRIPT_DIR/offline_sbom/fetch_offline_tools.sh"
  ok "syft/grype/grant/cosign staged in resources/tools"
else
  info "Skipping SBOM tool download (SKIP_TOOLS=1)"
fi

# --------------------------------------------------------------------------- #
# 5. Grype DB snapshot (offline)
# --------------------------------------------------------------------------- #
info "Snapshotting Grype vulnerability DB"
if [ -x "$RES_TOOLS/grype" ]; then
  GRYPE_DB_CACHE_DIR="$RES_GRYPE_DB" "$RES_TOOLS/grype" db update
  ok "Grype DB snapshot in resources/grype-db (frozen; AUTO_UPDATE off at runtime)"
else
  echo "    WARNING: resources/tools/grype not staged; skipping DB snapshot (re-run without SKIP_TOOLS=1)."
fi

# --------------------------------------------------------------------------- #
# 5b. Semgrep rule packs (offline)
# --------------------------------------------------------------------------- #
# The launcher points SEMGREP_RULES_DIR (= `semgrep --config`) at this dir's
# ROOT. Semgrep aborts the entire scan with rc=7 ("invalid configuration file
# found") if --config loads any YAML lacking a top-level `rules:` key — and the
# upstream repo ships plenty (.pre-commit-config.yaml, CI workflows, nested
# */*.test.yaml fixtures), so an UNPRUNED clone makes a packaged scan silently
# find NOTHING. stage_semgrep_rules.py clones the repo and keeps only loadable
# rule files, leaving a valid --config target. A marker makes re-runs skip the
# re-clone; a clone failure is a warning, not a build abort (like the Grype DB
# step). Regression-guarded by scripts/offline_sbom/tests/test_stage_semgrep_rules.py.
info "Bundling Semgrep rule packs"
RULES_DIR="$TAURI/resources/semgrep-rules"
python3 "$SCRIPT_DIR/offline_sbom/stage_semgrep_rules.py" "$RULES_DIR" \
  || echo "    WARNING: semgrep-rules staging failed (see above); a packaged scan finds nothing until rules are staged."

# --------------------------------------------------------------------------- #
# 6. App icons (.icns + pngs). No WebView2 step — macOS uses the system WKWebView.
# --------------------------------------------------------------------------- #
if [ -n "$ICON_LOGO" ] && [ -f "$ICON_LOGO" ]; then
  info "Generating app icons from $ICON_LOGO"
  (cd "$CLIENT" && npx --yes @tauri-apps/cli icon "$ICON_LOGO")
  ok "Icons (incl. icon.icns) generated into src-tauri/icons"
else
  echo "    NOTE: no ICON_LOGO provided; ensure src-tauri/icons/icon.icns already exists."
fi

# --------------------------------------------------------------------------- #
# 7. Frontend + signed/notarized DMG (Tauri bundler)
# --------------------------------------------------------------------------- #
info "Building the macOS app + DMG (Tauri signs the .app + nested sidecars, notarizes, staples)"
(
  cd "$CLIENT"
  npm install
  # CI=true makes Tauri's bundle_dmg.sh skip the Finder/AppleScript window-styling
  # step, which fails on headless / CI / SSH builds with no GUI session. The result
  # is a plain but fully functional drag-to-Applications DMG. (On an interactive
  # desktop you can drop CI=true to get the styled window layout.)
  CI=true npx --yes @tauri-apps/cli build --bundles app,dmg --config src-tauri/tauri.macos.conf.json
)

DMG_DIR="$TAURI/target/release/bundle/dmg"
info "Build complete"
if compgen -G "$DMG_DIR/*.dmg" >/dev/null; then
  for f in "$DMG_DIR"/*.dmg; do ok "Installer: $f"; done
  echo
  echo "    Verify:  codesign --verify --deep --strict \"$TAURI/target/release/bundle/macos/Code Sense.app\""
  echo "             spctl -a -t exec -vvv \"$TAURI/target/release/bundle/macos/Code Sense.app\""
  echo "             xcrun stapler validate \"$DMG_DIR\"/*.dmg"
else
  # Tauri's bundle_dmg.sh shells out to Finder/hdiutil and can still fail in headless
  # environments even with CI=true. Fall back to building the DMG directly from the .app.
  app_bundle="$TAURI/target/release/bundle/macos/Code Sense.app"
  [ -d "$app_bundle" ] || die "No .app bundle at $app_bundle — check the Tauri build output above."
  info "Tauri produced no .dmg; building it directly with hdiutil"
  staging="$(mktemp -d)"
  cp -Rc "$app_bundle" "$staging/Code Sense.app" 2>/dev/null || cp -R "$app_bundle" "$staging/Code Sense.app"
  ln -s /Applications "$staging/Applications"
  mkdir -p "$DMG_DIR"
  out_dmg="$DMG_DIR/Code Sense_0.1.0_aarch64.dmg"
  hdiutil create -volname "Code Sense" -srcfolder "$staging" -ov -format UDZO "$out_dmg"
  rm -rf "$staging"
  ok "Installer (hdiutil fallback): $out_dmg"
fi
