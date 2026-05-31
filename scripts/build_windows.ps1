#requires -Version 5.1
<#
.SYNOPSIS
  One-command Windows build for the Code Sense offline desktop app.

.DESCRIPTION
  Automates BUILD.md end-to-end on a Windows host:
    1. Freezes the Django backend into codesense-server.exe (PyInstaller).
    2. Downloads the SBOM toolchain (Syft/Grype/Grant/Cosign) - latest releases.
    3. Snapshots the Grype vulnerability DB for offline use.
    4. Stages every artifact into the Tauri bundle layout.
    5. Builds the NSIS installer.

  The two heavy AI inputs cannot be produced by this script (they need a built
  llama.cpp + the model), so pass them in:
    -ModelGguf    the quantized GGUF  (e.g. astra-q8_0.gguf)
    -LlamaServer  llama-server.exe    (a llama.cpp Windows release)

.PARAMETER ModelGguf   Path to the GGUF model file (copied into the bundle as astra.gguf).
.PARAMETER LlamaServer Path to llama-server.exe.
.PARAMETER WebView2    Path to a fixed-version WebView2 runtime folder (for a fully-offline installer).
.PARAMETER IconLogo    Square PNG used to generate app icons; defaults to client\public\CSlogo.png.
.PARAMETER SkipTools   Skip downloading the SBOM tools (use what's already staged).

.EXAMPLE
  .\scripts\build_windows.ps1 `
     -ModelGguf .\ai-artifacts\astra-q8_0.gguf `
     -LlamaServer .\ai-artifacts\llama-server.exe `
     -IconLogo .\client\public\CSlogo.png
#>
[CmdletBinding()]
param(
  [string]$ModelGguf,
  [string]$LlamaServer,
  [string]$WebView2,
  [string]$IconLogo,
  [switch]$SkipTools
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# --------------------------------------------------------------------------- #
# Paths + helpers
# --------------------------------------------------------------------------- #
$RepoRoot   = Split-Path -Parent $PSScriptRoot
$Server     = Join-Path $RepoRoot "server"
$Client     = Join-Path $RepoRoot "client"
$Tauri      = Join-Path $Client "src-tauri"
$BinDir     = Join-Path $Tauri "binaries"
$ResTools   = Join-Path $Tauri "resources\tools"
$ResModel   = Join-Path $Tauri "resources\model"
$ResGrypeDb = Join-Path $Tauri "resources\grype-db"
$Wv2Dir     = Join-Path $Tauri "webview2"

function Info($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    $m" -ForegroundColor Green }
function Die($m)  { Write-Host "ERROR: $m" -ForegroundColor Red; exit 1 }

function Assert-Cmd($name, $hint) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    Die "Required tool '$name' not found on PATH. $hint"
  }
}

function Ensure-Dir($p) { if (-not (Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null } }

# Run a native command and stop the build if it returns a non-zero exit code
# ($ErrorActionPreference='Stop' does NOT catch native exit codes).
function Invoke-Native([scriptblock]$Cmd, [string]$What) {
  & $Cmd
  if ($LASTEXITCODE -ne 0) { Die "$What failed (exit code $LASTEXITCODE)." }
}

# --------------------------------------------------------------------------- #
# 0. Prerequisites
# --------------------------------------------------------------------------- #
Info "Checking prerequisites"
Assert-Cmd python "Install Python 3.11+ from python.org (add to PATH)."
Assert-Cmd npm    "Install Node.js LTS from nodejs.org."
Assert-Cmd cargo  "Install Rust from rustup.rs."
Assert-Cmd rustc  "Install Rust from rustup.rs."
$hostLine = (& rustc -Vv | Select-String '^host:' | Select-Object -First 1)
if (-not $hostLine) { Die "Could not determine the Rust host triple from 'rustc -Vv'." }
$Triple = $hostLine.ToString().Split(' ')[-1].Trim()
Ok "Rust target triple: $Triple"
Ensure-Dir $BinDir; Ensure-Dir $ResTools; Ensure-Dir $ResModel; Ensure-Dir $ResGrypeDb

# --------------------------------------------------------------------------- #
# 1. Backend -> codesense-server.exe (PyInstaller)
# --------------------------------------------------------------------------- #
Info "Building backend executable (PyInstaller)"
Push-Location $Server
try {
  if (-not (Test-Path ".venv")) { Invoke-Native { python -m venv .venv } "venv creation" }
  Invoke-Native { & .\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet } "pip upgrade"
  Invoke-Native { & .\.venv\Scripts\pip.exe install -r requirements.txt pyinstaller --quiet } "pip install"
  Invoke-Native { & .\.venv\Scripts\pyinstaller.exe codesense.spec --noconfirm --clean } "PyInstaller"
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
  Die "Pass -ModelGguf <path to the .gguf model> (see scripts/offline_ai/)."
}
Copy-Item $ModelGguf (Join-Path $ResModel "astra.gguf") -Force
Ok "model staged as resources\model\astra.gguf"

# --------------------------------------------------------------------------- #
# 4. SBOM tools (Syft / Grype / Grant / Cosign) - latest releases via GitHub API
# --------------------------------------------------------------------------- #
if (-not $SkipTools) {
  Info "Downloading SBOM tools (latest windows_amd64 releases)"
  $tmp = Join-Path $env:TEMP ("cs-tools-" + [guid]::NewGuid())
  Ensure-Dir $tmp

  function Get-GhAsset($repo, $pattern, $outFile) {
    # Resolve the latest release and download the asset whose name matches $pattern.
    $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest" `
                             -Headers @{ "User-Agent" = "codesense-build" } -UseBasicParsing
    $asset = $rel.assets | Where-Object { $_.name -match $pattern } | Select-Object -First 1
    if (-not $asset) { Die "No asset matching '$pattern' in latest $repo release ($($rel.tag_name))." }
    Ok "$repo $($rel.tag_name) -> $($asset.name)"
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $outFile -UseBasicParsing
  }

  foreach ($tool in @("syft", "grype", "grant")) {
    $zip = Join-Path $tmp "$tool.zip"
    Get-GhAsset "anchore/$tool" "_windows_amd64\.zip$" $zip
    Expand-Archive -Path $zip -DestinationPath (Join-Path $tmp $tool) -Force
    Copy-Item (Join-Path (Join-Path $tmp $tool) "$tool.exe") (Join-Path $ResTools "$tool.exe") -Force
  }
  Get-GhAsset "sigstore/cosign" "cosign-windows-amd64\.exe$" (Join-Path $ResTools "cosign.exe")

  # OpenGrep (OSS Semgrep fork) — a single-file native binary, staged as
  # semgrep.exe (the launcher sets SEMGREP_BIN to <tools>\semgrep). Pinned to
  # match the macOS build (scripts/offline_sbom/fetch_offline_tools.sh) so both
  # platforms ship the same detector. Best-effort: a 404 is a warning (verify
  # the asset name on the build host), not a build abort — but without it the
  # packaged scan has no SAST detector.
  $OpengrepVersion = "1.4.0"
  $ogUrl = "https://github.com/opengrep/opengrep/releases/download/v$OpengrepVersion/opengrep_windows_x86_64.exe"
  try {
    Invoke-WebRequest -Uri $ogUrl -OutFile (Join-Path $ResTools "semgrep.exe") -UseBasicParsing
    Ok "opengrep $OpengrepVersion staged as resources\tools\semgrep.exe"
  } catch {
    Write-Warning "OpenGrep fetch failed ($ogUrl): $($_.Exception.Message). Verify the asset at https://github.com/opengrep/opengrep/releases; the packaged scan has no SAST detector until semgrep.exe is staged."
  }

  Remove-Item $tmp -Recurse -Force
  Ok "syft/grype/grant/cosign/semgrep staged in resources\tools"
} else { Info "Skipping SBOM tool download (-SkipTools)" }

# --------------------------------------------------------------------------- #
# 5. Grype DB snapshot (offline)
# --------------------------------------------------------------------------- #
Info "Snapshotting Grype vulnerability DB"
$grypeExe = Join-Path $ResTools "grype.exe"
if (Test-Path $grypeExe) {
  $env:GRYPE_DB_CACHE_DIR = $ResGrypeDb
  & $grypeExe db update
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "grype db update returned $LASTEXITCODE; the bundled CVE DB may be empty/stale."
  } else {
    Ok "Grype DB snapshot in resources\grype-db (frozen; AUTO_UPDATE off at runtime)"
  }
} else {
  Write-Warning "grype.exe not staged; skipping DB snapshot. Re-run without -SkipTools."
}

# --------------------------------------------------------------------------- #
# 5b. Semgrep rule packs (offline)
# --------------------------------------------------------------------------- #
# The launcher points SEMGREP_RULES_DIR (= `semgrep --config`) at this dir's
# ROOT. Semgrep aborts the whole scan with rc=7 ("invalid configuration file
# found") if --config loads any YAML lacking a top-level `rules:` key, and the
# upstream repo ships many (.pre-commit-config.yaml, CI workflows, nested
# *.test.yaml fixtures). The staging helper clones semgrep-rules and keeps only
# loadable rule files, leaving a valid --config target. Non-fatal on failure
# (the scan then finds nothing until rules are staged), matching the Grype DB
# step; needs git + network on the build host. Guarded by
# scripts\offline_sbom\tests\test_stage_semgrep_rules.py.
Info "Bundling Semgrep rule packs"
$RulesDir   = Join-Path $Tauri "resources\semgrep-rules"
$StageRules = Join-Path $PSScriptRoot "offline_sbom\stage_semgrep_rules.py"
& python $StageRules $RulesDir
if ($LASTEXITCODE -ne 0) {
  Write-Warning "semgrep-rules staging failed (needs git + network on the build host); the packaged scan will find nothing until rules are staged."
}

# --------------------------------------------------------------------------- #
# 6. WebView2 fixed runtime + icons
# --------------------------------------------------------------------------- #
if ($WebView2 -and (Test-Path $WebView2)) {
  Info "Staging fixed-version WebView2 runtime"
  Ensure-Dir $Wv2Dir
  Copy-Item (Join-Path $WebView2 "*") $Wv2Dir -Recurse -Force
  Ok "WebView2 runtime staged"
}

# Default the icon source to a bundled logo so the Tauri build isn't blocked.
if (-not $IconLogo) {
  foreach ($cand in @("client\public\CSlogo.png", "client\public\logoCS.png")) {
    $p = Join-Path $RepoRoot $cand
    if (Test-Path $p) { $IconLogo = $p; break }
  }
}
if ($IconLogo -and (Test-Path $IconLogo)) {
  Info "Generating app icons from $IconLogo"
  Push-Location $Client
  try { Invoke-Native { npx --yes @tauri-apps/cli icon $IconLogo } "Tauri icon generation" }
  finally { Pop-Location }
  Ok "Icons generated into src-tauri\icons"
} else {
  Write-Warning "No icon source found; the Tauri build needs src-tauri\icons. Pass -IconLogo <square PNG>."
}

# --------------------------------------------------------------------------- #
# 7. Fail fast if WebView2 fixed runtime is required but missing
# --------------------------------------------------------------------------- #
$wv2HasFiles = (Test-Path $Wv2Dir) -and (@(Get-ChildItem $Wv2Dir -Force -ErrorAction SilentlyContinue).Count -gt 0)
$confJson = Join-Path $Tauri "tauri.conf.json"
if (-not $wv2HasFiles -and (Test-Path $confJson) -and (Select-String -Path $confJson -Pattern 'fixedRuntime' -Quiet)) {
  Write-Host "ERROR: tauri.conf.json requests a FIXED WebView2 runtime but src-tauri\webview2\ is empty." -ForegroundColor Red
  Write-Host "  Offline installer: re-run with -WebView2 <fixed-version-runtime-folder>" -ForegroundColor Yellow
  Write-Host "  Online installer : set webviewInstallMode.type to 'downloadBootstrapper' in" -ForegroundColor Yellow
  Write-Host "                     client\src-tauri\tauri.conf.json (and remove the 'path' line)." -ForegroundColor Yellow
  exit 1
}

# --------------------------------------------------------------------------- #
# 8. Frontend + Tauri installer
# --------------------------------------------------------------------------- #
Info "Building the Tauri installer (this compiles Rust + bundles - can take several minutes)"
Push-Location $Client
try {
  Invoke-Native { npm install } "npm install"
  Invoke-Native { npx --yes @tauri-apps/cli build } "Tauri build"
} finally { Pop-Location }

$bundle = Join-Path $Tauri "target\release\bundle\nsis"
Info "Build complete"
if (Test-Path $bundle) {
  Get-ChildItem $bundle -Filter *.exe | ForEach-Object { Ok "Installer: $($_.FullName)" }
} else {
  Write-Warning "NSIS bundle dir not found at $bundle - check the Tauri build output above."
}
