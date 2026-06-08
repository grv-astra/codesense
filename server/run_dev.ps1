# run_dev.ps1 — launch the Code Sense backend FROM SOURCE with the staged
# offline scanner tools wired in (dev convenience; the packaged Tauri app sets
# these env vars itself). Run from the server\ directory:
#     .\run_dev.ps1
#
# Prereqs (one-time, already done during setup):
#   - server\.venv created + requirements installed
#   - dist\tools\windows\{semgrep,syft,grype,cosign}.exe  (scripts\offline_sbom\fetch_offline_tools.sh)
#   - dist\semgrep-rules\                                  (scripts\offline_sbom\stage_semgrep_rules.py)
#   - dist\grype-db\                                       (grype db update)
#   - server\keys\                                         (manage.py init_sbom_signing)
#
# NOTE: grant is not available on Windows (no upstream build), so SBOM *license*
# findings are skipped; vulnerability + signing still work. The LLM stages fail
# open (no astra.gguf / VLLM_BASE_URL) — findings kept as low-confidence TP.

$ErrorActionPreference = "Stop"
$server = $PSScriptRoot
$repo   = Split-Path $server -Parent
$tools  = Join-Path $repo "dist\tools\windows"

$env:SCANNER_TOOLS_DIR = $tools
$env:SEMGREP_BIN        = Join-Path $tools "semgrep.exe"
$env:SEMGREP_RULES_DIR  = Join-Path $repo "dist\semgrep-rules"
$env:GRYPE_DB_CACHE_DIR = Join-Path $repo "dist\grype-db"
$env:COSIGN_KEY_DIR     = Join-Path $server "keys"
$env:COSIGN_PASSWORD    = "admin@123" # must match the password used by init_sbom_signing / generate-key-pair
                                      # (PowerShell drops an empty-string env var, so use a non-empty dev password)
# Leave VLLM_BASE_URL unset -> LLM verifier/enricher fail open (no local model).

Write-Host "SCANNER_TOOLS_DIR = $env:SCANNER_TOOLS_DIR"
Write-Host "SEMGREP_BIN       = $env:SEMGREP_BIN"
Write-Host "SEMGREP_RULES_DIR = $env:SEMGREP_RULES_DIR"
Write-Host "GRYPE_DB_CACHE_DIR= $env:GRYPE_DB_CACHE_DIR"
Write-Host "COSIGN_KEY_DIR    = $env:COSIGN_KEY_DIR"
Write-Host "Starting Code Sense backend on http://127.0.0.1:8585 ..."

& (Join-Path $server ".venv\Scripts\python.exe") (Join-Path $server "run_server.py") 127.0.0.1 8585
