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

chmod +x "$OUT"/* 2>/dev/null || true
echo "Tools in: $OUT"
ls -la "$OUT"
