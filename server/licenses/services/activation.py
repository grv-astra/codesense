"""Offline, one-time activation gate for a packaged desktop build.

The build ships with a baked-in password hash (ACTIVATION_PASSWORD_HASH env
var, set by the Tauri launcher). The plaintext password is never given to
the client -- only whoever deploys the app types it once, during setup, on
the client's own machine. Until activated, every API route is blocked (see
ActivationRequiredMiddleware). Once activated, the record is bound to THIS
machine's hardware fingerprint and signed + stored in two places (file +
registry) -- same tamper-resistance pattern as offline_license.py -- so
copying the activated app folder to a different machine does not carry the
activation with it; that machine would need the password again.

Deliberately a no-op (always "activated") when ACTIVATION_PASSWORD_HASH is
unset -- dev-from-source and any build that doesn't opt into this gate is
unaffected.
"""
import hashlib
import hmac
import json
import os
import platform
from pathlib import Path

import bcrypt
from django.conf import settings

from licenses.services.offline_license import _secret as _signing_secret

_REG_PATH = r"Software\CodeSense"
_REG_VALUE = "activation"


def _password_hash() -> str:
    return os.getenv("ACTIVATION_PASSWORD_HASH") or getattr(settings, "ACTIVATION_PASSWORD_HASH", "") or ""


def is_configured() -> bool:
    """False when this build doesn't opt into the activation gate at all."""
    return bool(_password_hash())


def verify_password(password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), _password_hash().encode("utf-8"))
    except Exception:
        return False


def machine_fingerprint() -> str:
    """A stable per-machine identifier, hashed (the raw value is never stored).

    Windows: the per-install MachineGuid (registry) -- the same stability
    guarantee offline_license.py's registry store already relies on.
    Non-Windows: a best-effort fallback (this app only ships as a Windows
    desktop build today).
    """
    raw = None
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Microsoft\Cryptography") as key:
                raw, _ = winreg.QueryValueEx(key, "MachineGuid")
        except Exception:
            raw = None
    if not raw:
        raw = f"{platform.node()}:{platform.machine()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sign(machine_hash: str) -> str:
    # Reuses the license system's per-install signing key (offline_license.py)
    # rather than a second constant -- one signing key per install is enough.
    return hmac.new(_signing_secret(), machine_hash.encode("utf-8"), hashlib.sha256).hexdigest()


def _make_record() -> dict:
    mh = machine_fingerprint()
    return {"machine_hash": mh, "sig": _sign(mh)}


def _is_valid(rec) -> bool:
    if not isinstance(rec, dict) or "machine_hash" not in rec or "sig" not in rec:
        return False
    try:
        expected = _sign(rec["machine_hash"])
    except Exception:
        return False
    return hmac.compare_digest(expected, str(rec.get("sig", "")))


def _file_path() -> Path:
    return Path(getattr(settings, "DATA_DIR")) / "activation.json"


def _file_read():
    p = _file_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _file_write(rec: dict):
    p = _file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec), encoding="utf-8")


def _registry_read():
    if os.name != "nt":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as key:
            raw, _ = winreg.QueryValueEx(key, _REG_VALUE)
            return json.loads(raw)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _registry_write(rec: dict):
    if os.name != "nt":
        return
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as key:
            winreg.SetValueEx(key, _REG_VALUE, 0, winreg.REG_SZ, json.dumps(rec))
    except Exception:
        pass


def is_activated() -> bool:
    """True once a valid, THIS-machine-bound activation record exists.

    Always True when the build doesn't opt into the gate (no password
    baked in) -- dev-from-source and non-gated builds are unaffected.
    """
    if not is_configured():
        return True
    current = machine_fingerprint()
    for rec in (_file_read(), _registry_read()):
        if rec and rec.get("machine_hash") == current and _is_valid(rec):
            return True
    return False


def activate(password: str) -> bool:
    """Verify the one-time password and, if correct, bind activation to this
    machine. Returns True on success. Idempotent -- calling again after
    already-activated just re-writes the same record."""
    if not is_configured():
        return True
    if not verify_password(password):
        return False
    rec = _make_record()
    _file_write(rec)
    _registry_write(rec)
    return True
