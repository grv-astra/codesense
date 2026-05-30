"""Resolve external scanner tool binaries + offline env for the bundled app.

The desktop build ships Syft, Grype, Cosign, and Grant binaries plus a snapshot
of the Grype vulnerability DB. Their locations are provided by the launcher via
env vars (or Django settings); in dev we fall back to the bare command name on
PATH. Keeping this in one place means the SBOM pipeline never hardcodes a path.
"""
import os
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
