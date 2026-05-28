# Offline SBOM/SCA tooling (Phase 3)

The SBOM pipeline (`server/scanner/services/sbom_pipeline.py`) shells out to
**Syft** (SBOM), **Grype** (CVEs), **Grant** (licenses), and **Cosign** (signing).
Phase 3 made every invocation resolve through `scanner/services/tools.py` so the
desktop build uses *bundled* binaries and a *frozen* Grype DB instead of PATH +
network.

## How resolution works (no code change needed at runtime)
The launcher (Tauri, Phase 6) sets these env vars; the pipeline reads them:

| Env var | Purpose |
|---|---|
| `SCANNER_TOOLS_DIR` | dir holding `syft(.exe)`, `grype(.exe)`, `grant(.exe)`, `cosign(.exe)` |
| `SYFT_BIN` / `GRYPE_BIN` / `GRANT_BIN` / `COSIGN_BIN` | per-tool absolute path override |
| `GRYPE_DB_CACHE_DIR` | bundled Grype vuln-DB snapshot (also sets `GRYPE_DB_AUTO_UPDATE=false`) |
| `COSIGN_KEY_DIR` | dir holding `cosign.key` / `cosign.pub` / `signing-config.json` |

In dev (none set) it falls back to bare command names on PATH — unchanged behavior.

## Build-host steps (needs network; not runnable in CI sandbox)

```bash
# 1) Download the four Windows binaries into dist/tools/windows
TARGET_OS=windows TARGET_ARCH=amd64 scripts/offline_sbom/fetch_offline_tools.sh

# 2) Snapshot the Grype vulnerability DB (portable across OSes)
GRYPE_DB_CACHE_DIR=dist/grype-db grype db update   # uses your local grype once
#    -> ship dist/grype-db with the app; Grype reads it offline with AUTO_UPDATE=false

# 3) Generate the Cosign keypair locally (offline, no transparency log)
cd server && .venv/bin/python manage.py init_sbom_signing   # writes server/keys/
#    -> on Windows the launcher points COSIGN_KEY_DIR at %LOCALAPPDATA%\CodeSense\keys
```

## Caveats validated on the build host
- **CVE data is frozen** at snapshot time (acceptable for a 3-month license). Refresh by re-running step 2 at each repackage.
- **Cosign offline flags**: `verify-blob` already uses `--insecure-ignore-tlog=true`. Confirm the bundled cosign version's `sign-blob --signing-config` works without network on your Windows build; if not, switch to key-only signing (`--tlog-upload=false --yes`). This must be verified with the actual cosign binary — it could not be exercised in the sandbox.
