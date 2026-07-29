"""Resolve external scanner tool binaries + offline env for the bundled app.

The desktop build ships Syft, Grype, Cosign, and Grant binaries plus a snapshot
of the Grype vulnerability DB. Their locations are provided by the launcher via
env vars (or Django settings); in dev we fall back to the bare command name on
PATH. Keeping this in one place means the SBOM pipeline never hardcodes a path.
"""
import json
import os
import subprocess
from pathlib import Path

from django.conf import settings


def tool_path(name: str) -> str:
    """Path to a bundled tool binary, or the bare name (PATH) in dev.

    Resolution order: env ``<NAME>_BIN`` -> ``SCANNER_TOOLS_DIR/<name>[.exe]`` -> PATH.
    """
    override = os.getenv(f"{name.upper()}_BIN")
    if override:
        return override
    tools_dir = os.getenv("SCANNER_TOOLS_DIR") or getattr(settings, "SCANNER_TOOLS_DIR", None)
    if tools_dir:
        exe = name + (".exe" if os.name == "nt" else "")
        candidate = Path(tools_dir) / exe
        if candidate.exists():
            return str(candidate)
    return name


def grype_offline_env() -> dict:
    """os.environ plus the Grype offline pins (bundled DB, no network update)."""
    env = dict(os.environ)
    db_dir = os.getenv("GRYPE_DB_CACHE_DIR") or getattr(settings, "GRYPE_DB_CACHE_DIR", None)
    if db_dir:
        env["GRYPE_DB_CACHE_DIR"] = str(db_dir)
        env["GRYPE_DB_AUTO_UPDATE"] = "false"
        env["GRYPE_DB_VALIDATE_AGE"] = "false"
    return env


def get_semgrep_bin() -> str:
    """Resolve the Semgrep binary path.

    Order: SEMGREP_BIN env var → <SCANNER_TOOLS_DIR>/semgrep → bare "semgrep" (PATH).
    Delegates to the generic tool_path() resolver.
    """
    return tool_path("semgrep")


def get_semgrep_rules_dir() -> str:
    """Resolve the bundled Semgrep rule packs directory (empty if not bundled)."""
    return os.environ.get("SEMGREP_RULES_DIR", "").strip()


def get_privacy_rules_dir() -> str:
    """Custom PII/privacy rule pack shipped in-repo at scanner/rules/privacy/.

    Deliberately NOT part of SEMGREP_RULES_DIR: that tree is cloned from
    upstream github.com/semgrep/semgrep-rules and wholesale replaced on every
    re-stage (see scripts/offline_sbom/stage_semgrep_rules.py), which would
    silently delete hand-written rules living inside it. Resolved via __file__
    (same pattern as cosign_paths() below) so it works unchanged in dev-from-
    source and in the frozen app, where PyInstaller's datas= preserves the
    scanner/rules/privacy/ layout relative to this module.
    """
    candidate = Path(__file__).resolve().parent.parent / "rules" / "privacy"
    return str(candidate) if candidate.is_dir() else ""


def cosign_paths():
    """(private_key, public_key, signing_config) for cosign, env-overridable.

    ``COSIGN_KEY_DIR`` (e.g. ``%LOCALAPPDATA%\\CodeSense\\keys``) wins; otherwise
    the repo's ``server/keys`` dir (where ``init_sbom_signing`` writes them).
    """
    key_dir = os.getenv("COSIGN_KEY_DIR") or getattr(settings, "COSIGN_KEY_DIR", None)
    base = Path(key_dir) if key_dir else Path(__file__).resolve().parent.parent.parent / "keys"
    return (
        str((base / "cosign.key").resolve()),
        str((base / "cosign.pub").resolve()),
        str((base / "signing-config.json").resolve()),
    )


def ensure_cosign_keys() -> None:
    """Generate the cosign key pair + signing config on first use, if missing.

    ``init_sbom_signing`` (the Django management command this logic mirrors)
    is manual-only and never invoked anywhere in the packaged app's startup
    path (main.rs, Django AppConfig, or here) -- a genuinely fresh install has
    no keys directory at all, so the first SBOM scan would otherwise fail with
    a cosign error and no recovery path exposed in the GUI. Called lazily from
    _sign_sbom() so it self-heals on first real use instead of requiring an
    undocumented manual step. Idempotent: no-ops once the files exist.
    """
    private_key, public_key, signing_config = cosign_paths()
    key_dir = Path(private_key).parent
    key_dir.mkdir(parents=True, exist_ok=True)

    if not Path(private_key).exists() or not Path(public_key).exists():
        result = subprocess.run(
            [tool_path("cosign"), "generate-key-pair"],
            cwd=str(key_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=dict(os.environ),
        )
        if result.returncode != 0:
            raise Exception(f"Cosign key generation failed: {result.stderr}")

    if not Path(signing_config).exists():
        with open(signing_config, "w", encoding="utf-8") as f:
            json.dump(
                {"mediaType": "application/vnd.dev.sigstore.signingconfig.v0.2+json"},
                f, indent=2,
            )
