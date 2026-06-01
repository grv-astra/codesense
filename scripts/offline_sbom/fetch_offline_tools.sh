#!/usr/bin/env bash
# Download Syft / Grype / Grant / Cosign release binaries for the target OS/arch
# into dist/tools/<os>. Run on a BUILD machine with network access; the binaries
# are bundled into the Tauri app (see scripts/offline_sbom/README.md).
#
# Versions are pinned for reproducibility — bump as needed.
set -euo pipefail

TARGET_OS="${TARGET_OS:-windows}"     # windows | linux | darwin
TARGET_ARCH="${TARGET_ARCH:-amd64}"
OUT="${OUT:-dist/tools/$TARGET_OS}"

SYFT_VERSION="${SYFT_VERSION:-1.18.1}"
GRYPE_VERSION="${GRYPE_VERSION:-0.85.0}"
GRANT_VERSION="${GRANT_VERSION:-0.2.4}"
COSIGN_VERSION="${COSIGN_VERSION:-2.4.1}"

mkdir -p "$OUT"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
ext=""; [ "$TARGET_OS" = "windows" ] && ext=".exe"

dl() { echo "  $1"; curl -fsSL "$1" -o "$2"; }

# anchore tools ship as .zip (windows) / .tar.gz (unix)
fetch_anchore() {
  local tool="$1" ver="$2" base="https://github.com/anchore/$1/releases/download/v$2"
  if [ "$TARGET_OS" = "windows" ]; then
    dl "$base/${tool}_${ver}_${TARGET_OS}_${TARGET_ARCH}.zip" "$tmp/$tool.zip"
    unzip -o -q "$tmp/$tool.zip" -d "$tmp/$tool"
  else
    dl "$base/${tool}_${ver}_${TARGET_OS}_${TARGET_ARCH}.tar.gz" "$tmp/$tool.tgz"
    mkdir -p "$tmp/$tool"; tar -xzf "$tmp/$tool.tgz" -C "$tmp/$tool"
  fi
  cp "$tmp/$tool/${tool}${ext}" "$OUT/${tool}${ext}"
}

echo "Fetching Syft $SYFT_VERSION ..."  ; fetch_anchore syft  "$SYFT_VERSION"
echo "Fetching Grype $GRYPE_VERSION ..."; fetch_anchore grype "$GRYPE_VERSION"
echo "Fetching Grant $GRANT_VERSION ..."; fetch_anchore grant "$GRANT_VERSION"

echo "Fetching Cosign $COSIGN_VERSION ..."
dl "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-${TARGET_OS}-${TARGET_ARCH}${ext}" "$OUT/cosign${ext}"

# ------------- OpenGrep (SAST detector) -------------
# OpenGrep is the maintained OSS fork of Semgrep; it ships single-file native
# binaries (Semgrep itself is a Python package, awkward to bundle) with the same
# rule language. We stage it as `semgrep`/`semgrep.exe` so the launcher's
# SEMGREP_BIN points at it. Asset names are the real ones published at
# https://github.com/opengrep/opengrep/releases (verified for v1.22.0): the
# self-contained CLI is opengrep_<os>_<arch> (NOT the opengrep-core_* tarballs),
# and the arch token differs by OS (osx uses arm64/x86, manylinux uses
# aarch64/x86, windows is x86.exe).
OPENGREP_VERSION="${OPENGREP_VERSION:-1.22.0}"
case "$TARGET_OS/$TARGET_ARCH" in
  darwin/arm64)  OG_ASSET="opengrep_osx_arm64" ;;
  darwin/amd64)  OG_ASSET="opengrep_osx_x86" ;;
  linux/arm64)   OG_ASSET="opengrep_manylinux_aarch64" ;;
  linux/amd64)   OG_ASSET="opengrep_manylinux_x86" ;;
  windows/amd64) OG_ASSET="opengrep_windows_x86.exe" ;;
  *) echo "ERROR: no OpenGrep release asset for $TARGET_OS/$TARGET_ARCH" >&2; exit 1 ;;
esac
echo "Fetching OpenGrep $OPENGREP_VERSION ($OG_ASSET) ..."
# dl uses `curl -f`, so a 404 aborts the build (NOT swallowed) — shipping an app
# with no SAST engine is exactly the failure this fatal path prevents.
dl "https://github.com/opengrep/opengrep/releases/download/v${OPENGREP_VERSION}/${OG_ASSET}" \
   "$OUT/semgrep${ext}"
# Sanity-check the size: the real CLI is ~40MB; anything under 1MB means a
# partial/empty/HTML-error download slipped through.
sz=$(wc -c < "$OUT/semgrep${ext}" 2>/dev/null || echo 0)
if [ "$sz" -lt 1000000 ]; then
  echo "ERROR: staged OpenGrep is only ${sz}B (<1MB) — fetch failed or wrong asset." >&2
  echo "       Verify the asset name at https://github.com/opengrep/opengrep/releases" >&2
  exit 1
fi
echo "  staged: $OUT/semgrep${ext} (${sz} bytes)"

chmod +x "$OUT"/* 2>/dev/null || true
echo "Tools in: $OUT"
ls -la "$OUT"
