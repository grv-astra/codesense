#requires -Version 5.1
<#
.SYNOPSIS
  One-command Windows build for the Code Sense offline desktop app.

.DESCRIPTION
  Automates BUILD.md end-to-end on a Windows host:
    1. Freezes the Django backend into codesense-server.exe (PyInstaller).
    2. Downloads the SBOM toolchain (Syft/Grype/Grant/Cosign).
    3. Snapshots the Grype vulnerability DB for offline use.
    4. Stages every artifact into the Tauri bundle layout.
    5. Builds the NSIS installer.

  The two heavy AI inputs cannot be produced by this script (they need a built
  llama.cpp + the 6 GB model), so pass them in:
    -ModelGguf    the quantized GGUF  (scripts/offline_ai/convert_model_to_gguf.sh)
    -LlamaServer  llama-server.exe    (a llama.cpp release)

.PARAMETER ModelGguf   Path to astra-Q4_K_M.gguf.
.PARAMETER LlamaServer Path to llama-server.exe.
.PARAMETER WebView2    Path to a fixed-version WebView2 runtime folder (for fully-offline install).
.PARAMETER IconLogo    Optional square PNG; if given, app icons are generated with the Tauri CLI.
.PARAMETER SkipTools   Skip downloading the SBOM tools (use what's already staged).

.EXAMPLE
  .\scripts\build_windows.ps1 `
     -ModelGguf .\dist\model\astra-Q4_K_M.gguf `
     -LlamaServer C:\llama.cpp\build\bin\llama-server.exe `
     -WebView2 C:\webview2-fixed\ `
     -IconLogo .\client\public\CSlogo.png
#>
[CmdletBinding()]
param(
  [string]$ModelGguf,
  [string]$LlamaServer,
  [string]$WebView2,
  [string]$IconLogo,
  [switch]$SkipTools,
  [string]$SyftVersion   = "1.18.1",
  [string]$GrypeVersion  = "0.85.0",
  [string]$GrantVersion  = "0.2.4",
  [string]$CosignVersion = "2.4.1"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# --------------------------------------------------------------------------- #
# Paths + helpers
# --------------------------------------------------------------------------- #
$RepoRoot  = Split-Path -Parent $PSScriptRoot
$Server    = Join-Path $RepoRoot "server"
$Client    = Join-Path $RepoRoot "client"
$Tauri     = Join-Path $Client "src-tauri"
$BinDir    = Join-Path $Tauri "binaries"
$ResTools  = Join-Path $Tauri "resources\tools"
$ResModel  = Join-Path $Tauri "resources\model"
$ResGrypeDb= Join-Path $Tauri "resources\grype-db"
$Wv2Dir    = Join-Path $Tauri "webview2"

function Info($m)  { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)    { Write-Host "    $m" -ForegroundColor Green }
function Die($m)   { Write-Error $m; exit 1 }

function Assert-Cmd($name, $hint) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    Die "Required tool '$name' not found on PATH. $hint"
  }
}

function Ensure-Dir($p) { if (-not (Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null } }

# --------------------------------------------------------------------------- #
# 0. Prerequisites
# --------------------------------------------------------------------------- #
Info "Checking prerequisites"
Assert-Cmd python "Install Python 3.11+ from python.org."
Assert-Cmd npm    "Install Node.js LTS from nodejs.org."
Assert-Cmd cargo  "Install Rust from rustup.rs."
Assert-Cmd rustc  "Install Rust from rustup.rs."
$Triple = ((& rustc -Vv) | Select-String '^host:').ToString().Split(' ')[-1].Trim()
Ok "Rust target triple: $Triple"
Ensure-Dir $BinDir; Ensure-Dir $ResTools; Ensure-Dir $ResModel; Ensure-Dir $ResGrypeDb

# --------------------------------------------------------------------------- #
# 1. Backend -> codesense-server.exe (PyInstaller)
# --------------------------------------------------------------------------- #
Info "Building backend executable (PyInstaller)"
Push-Location $Server
try {
  if (-not (Test-Path ".venv")) { python -m venv .venv }
  & .\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
  & .\.venv\Scripts\pip.exe install -r requirements.txt pyinstaller --quiet
  & .\.venv\Scripts\pyinstaller.exe codesense.spec --noconfirm --clean
  $built = Join-Path $Server "dist\codesense-server.exe"
  if (-not (Test-Path $built)) { Die "PyInstaller did not produce dist\codesense-server.exe" }
  Copy-Item $built (Join-Path $BinDir "codesense-server-$Triple.exe") -Force
  Ok "codesense-server-$Triple.exe staged"
} finally { Pop-Location }

# --------------------------------------------------------------------------- #
# 2. llama-server (provided)
# --------------------------------------------------------------------------- #
Info "Staging llama-server"
if (-not $LlamaServer -or -not (Test-Path $LlamaServer)) {
  Die "Pass -LlamaServer <path to llama-server.exe> (download from a llama.cpp release)."
}
Copy-Item $LlamaServer (Join-Path $BinDir "llama-server-$Triple.exe") -Force
Ok "llama-server-$Triple.exe staged"

# --------------------------------------------------------------------------- #
# 3. Model GGUF (provided)
# --------------------------------------------------------------------------- #
Info "Staging model GGUF"
if (-not $ModelGguf -or -not (Test-Path $ModelGguf)) {
  Die "Pass -ModelGguf <path to astra-Q4_K_M.gguf> (see scripts/offline_ai/)."
}
Copy-Item $ModelGguf (Join-Path $ResModel "astra.gguf") -Force
Ok "astra-Q4_K_M.gguf staged"

# --------------------------------------------------------------------------- #
# 4. SBOM tools (Syft / Grype / Grant / Cosign)
# --------------------------------------------------------------------------- #
if (-not $SkipTools) {
  Info "Downloading SBOM tools (windows_amd64)"
  $tmp = Join-Path $env:TEMP ("cs-tools-" + [guid]::NewGuid())
  Ensure-Dir $tmp
  function Get-Anchore($tool, $ver) {
    $url = "https://github.com/anchore/$tool/releases/download/v$ver/${tool}_${ver}_windows_amd64.zip"
    $zip = Join-Path $tmp "$tool.zip"
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath (Join-Path $tmp $tool) -Force
    Copy-Item (Join-Path $tmp "$tool\$tool.exe") (Join-Path $ResTools "$tool.exe") -Force
  }
  Get-Anchore "syft"  $SyftVersion
  Get-Anchore "grype" $GrypeVersion
  Get-Anchore "grant" $GrantVersion
  $cosignUrl = "https://github.com/sigstore/cosign/releases/download/v$CosignVersion/cosign-windows-amd64.exe"
  Invoke-WebRequest -Uri $cosignUrl -OutFile (Join-Path $ResTools "cosign.exe") -UseBasicParsing
  Remove-Item $tmp -Recurse -Force
  Ok "syft/grype/grant/cosign staged in resources\tools"
} else { Info "Skipping SBOM tool download (-SkipTools)" }

# --------------------------------------------------------------------------- #
# 5. Grype DB snapshot (offline)
# --------------------------------------------------------------------------- #
Info "Snapshotting Grype vulnerability DB"
$grypeExe = Join-Path $ResTools "grype.exe"
if (Test-Path $grypeExe) {
  $env:GRYPE_DB_CACHE_DIR = $ResGrypeDb
  & $grypeExe db update
  Ok "Grype DB snapshot in resources\grype-db (frozen; AUTO_UPDATE off at runtime)"
} else {
  Write-Warning "grype.exe not staged; skipping DB snapshot. Re-run without -SkipTools."
}

# --------------------------------------------------------------------------- #
# 6. WebView2 fixed runtime + icons
# --------------------------------------------------------------------------- #
if ($WebView2 -and (Test-Path $WebView2)) {
  Info "Staging fixed-version WebView2 runtime"
  Ensure-Dir $Wv2Dir
  Copy-Item (Join-Path $WebView2 "*") $Wv2Dir -Recurse -Force
  Ok "WebView2 runtime staged"
} else {
  Write-Warning "No -WebView2 provided. For a guaranteed-offline installer, stage a fixed-version runtime into src-tauri\webview2\ (see src-tauri\README.md)."
}

if ($IconLogo -and (Test-Path $IconLogo)) {
  Info "Generating app icons from $IconLogo"
  Push-Location $Client
  try { npx --yes @tauri-apps/cli icon $IconLogo } finally { Pop-Location }
  Ok "Icons generated into src-tauri\icons"
}

# --------------------------------------------------------------------------- #
# 7. Frontend + Tauri installer
# --------------------------------------------------------------------------- #
Info "Building the Tauri installer"
Push-Location $Client
try {
  npm install
  npx --yes @tauri-apps/cli build
} finally { Pop-Location }

$bundle = Join-Path $Tauri "target\release\bundle\nsis"
Info "Build complete"
if (Test-Path $bundle) {
  Get-ChildItem $bundle -Filter *.exe | ForEach-Object { Ok "Installer: $($_.FullName)" }
} else {
  Write-Warning "NSIS bundle dir not found at $bundle — check the Tauri build output above."
}
