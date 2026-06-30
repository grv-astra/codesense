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
.PARAMETER ModelTier   Device tier the bundled model targets: low|mid|high (default mid = the
                       Apache Qwen2.5-Coder-7B-Instruct). Recorded/logged; the actual source file
                       is -ModelGguf (explicit wins). Mirrors server\scanner\rag\model_tiers.py.
.PARAMETER LlamaServer Path to llama-server.exe. Its sibling runtime DLLs (ggml*/llama*/mtmd/libomp)
                       are auto-staged into resources\llama-runtime so the bundled launcher can load.
.PARAMETER WebView2    Path to a fixed-version WebView2 runtime folder (for a fully-offline installer).
.PARAMETER IconLogo    Square PNG used to generate app icons; defaults to client\public\CSlogo.png.
.PARAMETER SkipTools   Skip downloading the SBOM tools (use what's already staged).
.PARAMETER SigningCert Path to an Authenticode code-signing cert (.pfx). When set (and the SDK's
                       signtool is on PATH) the produced installer is signed; the .pfx password is
                       read from $env:WINDOWS_CERT_PASSWORD. Omit for an unsigned local build.

.EXAMPLE
  .\scripts\build_windows.ps1 `
     -ModelGguf .\ai-artifacts\astra-q8_0.gguf `
     -LlamaServer .\ai-artifacts\llama-server.exe `
     -IconLogo .\client\public\CSlogo.png
#>
[CmdletBinding()]
param(
  [string]$ModelGguf,
  [ValidateSet("low", "mid", "high")]
  [string]$ModelTier = "mid",
  [string]$LlamaServer,
  [string]$WebView2,
  [string]$IconLogo,
  [switch]$SkipTools,
  [string]$SigningCert
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
$ResLlamaRt = Join-Path $Tauri "resources\llama-runtime"
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
Ensure-Dir $BinDir; Ensure-Dir $ResTools; Ensure-Dir $ResModel; Ensure-Dir $ResLlamaRt; Ensure-Dir $ResGrypeDb

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

# A shared-library llama.cpp build ships llama-server.exe as a thin launcher that
# dynamically links its runtime DLLs (llama-server-impl.dll, llama.dll,
# llama-common.dll, ggml*.dll, mtmd.dll, libomp*). Tauri places the sidecar exe at
# the install ROOT, so those DLLs must travel too; stage every *.dll sitting beside
# llama-server.exe into resources\llama-runtime, which the launcher prepends to the
# child PATH (see client\src-tauri\src\main.rs::spawn_llama). A single-file static
# build has no sibling DLLs and this simply stages nothing.
$LlamaSrcDir = Split-Path -Parent (Resolve-Path $LlamaServer)
$llamaDlls = @(Get-ChildItem -Path $LlamaSrcDir -Filter *.dll -File -ErrorAction SilentlyContinue)
if ($llamaDlls.Count -gt 0) {
  foreach ($dll in $llamaDlls) { Copy-Item $dll.FullName (Join-Path $ResLlamaRt $dll.Name) -Force }
  Ok "$($llamaDlls.Count) llama runtime DLL(s) staged into resources\llama-runtime"
} else {
  Info "No sibling DLLs next to llama-server.exe (assuming a static build)."
}

# --------------------------------------------------------------------------- #
# 3. Model GGUF (provided)
# --------------------------------------------------------------------------- #
Info "Staging model GGUF (tier: $ModelTier)"
if (-not $ModelGguf -or -not (Test-Path $ModelGguf)) {
  Die "Pass -ModelGguf <path to the .gguf model> (see scripts/offline_ai/). Target tier '$ModelTier' (mid = Apache 7B-Instruct)."
}
Copy-Item $ModelGguf (Join-Path $ResModel "astra.gguf") -Force
$gb = [math]::Round((Get-Item $ModelGguf).Length / 1GB, 2)
Ok "model ($ModelTier tier, $gb GB) staged as resources\model\astra.gguf"

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
  # platforms ship the same detector. The real Windows asset is
  # opengrep_windows_x86.exe (NOT _x86_64); a failed fetch is FATAL because an
  # app with no SAST engine detects nothing.
  $OpengrepVersion = "1.22.0"
  $ogUrl = "https://github.com/opengrep/opengrep/releases/download/v$OpengrepVersion/opengrep_windows_x86.exe"
  $ogOut = Join-Path $ResTools "semgrep.exe"
  Invoke-WebRequest -Uri $ogUrl -OutFile $ogOut -UseBasicParsing
  $ogSize = (Get-Item $ogOut).Length
  if ($ogSize -lt 1000000) {
    throw "Staged OpenGrep is only $ogSize bytes (<1MB) — fetch failed or wrong asset ($ogUrl). Verify at https://github.com/opengrep/opengrep/releases"
  }
  Ok "opengrep $OpengrepVersion staged as resources\tools\semgrep.exe ($ogSize bytes)"

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
$installers = @()
if (Test-Path $bundle) {
  $installers = @(Get-ChildItem $bundle -Filter *.exe -File)
}

# --------------------------------------------------------------------------- #
# 9. Authenticode sign the installer (only when a cert is supplied)
# --------------------------------------------------------------------------- #
# Mirrors the macOS APPLE_SIGNING_IDENTITY gate: with no cert this is a no-op +
# warning, so an unsigned local/CI build still completes. signtool ships with the
# Windows SDK; it is usually not on PATH, so fall back to the newest copy under
# Program Files. Password comes from $env:WINDOWS_CERT_PASSWORD (never a param, so
# it stays out of the process table / history).
function Find-SignTool {
  $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $roots = @("${env:ProgramFiles(x86)}\Windows Kits\10\bin", "$env:ProgramFiles\Windows Kits\10\bin")
  foreach ($root in $roots) {
    if (Test-Path $root) {
      $found = Get-ChildItem $root -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
               Where-Object { $_.FullName -match '\\x64\\' } |
               Sort-Object FullName -Descending | Select-Object -First 1
      if ($found) { return $found.FullName }
    }
  }
  return $null
}

if ($SigningCert) {
  Info "Signing the installer (Authenticode)"
  if (-not (Test-Path $SigningCert)) { Die "Signing cert not found: $SigningCert" }
  if ($installers.Count -eq 0) { Die "No installer to sign (NSIS bundle missing)." }
  $signtool = Find-SignTool
  if (-not $signtool) { Die "signtool.exe not found. Install the Windows 10/11 SDK (Signing Tools)." }
  if (-not $env:WINDOWS_CERT_PASSWORD) {
    Write-Warning "WINDOWS_CERT_PASSWORD not set; signtool will prompt or fail for a password-protected .pfx."
  }
  foreach ($inst in $installers) {
    $signArgs = @("sign", "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256",
                  "/f", $SigningCert)
    if ($env:WINDOWS_CERT_PASSWORD) { $signArgs += @("/p", $env:WINDOWS_CERT_PASSWORD) }
    $signArgs += $inst.FullName
    Invoke-Native { & $signtool @signArgs } "signtool sign $($inst.Name)"
    Invoke-Native { & $signtool verify /pa $inst.FullName } "signtool verify $($inst.Name)"
    Ok "Signed + verified: $($inst.Name)"
  }
} else {
  Write-Warning "No -SigningCert supplied: installer is UNSIGNED. SmartScreen will warn users on first run."
}

# --------------------------------------------------------------------------- #
# 10. Report
# --------------------------------------------------------------------------- #
Info "Build complete"
if ($installers.Count -gt 0) {
  foreach ($inst in $installers) {
    $sizeMb = [math]::Round($inst.Length / 1MB, 1)
    Ok "Installer: $($inst.FullName) ($sizeMb MB)"
  }
} else {
  Write-Warning "NSIS bundle dir not found at $bundle - check the Tauri build output above."
}
