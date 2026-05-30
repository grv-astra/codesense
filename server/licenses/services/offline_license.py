"""Offline, self-contained license check.

Model: the license runs for ``LICENSE_DURATION_DAYS`` (default 90) from FIRST RUN.
On first launch we record a signed ``first_seen`` stamp; thereafter we compute
state from it. There is no network and no central server.

Tamper model — explicitly "stops a normal user copying it / changing the date",
NOT a determined reverse-engineer:
  * The stamp is HMAC-signed with an embedded secret, so editing license.json
    by hand invalidates it (-> TAMPERED). (HMAC, not Ed25519: the app both signs
    and verifies its own stamp, so asymmetric keys add no value here. For a
    vendor-issued license file you would switch to Ed25519 with the public key
    embedded.)
  * The stamp is written to TWO places — a file in DATA_DIR and a second OS store
    (Windows registry / macOS plist outside DATA_DIR) — and we take the EARLIEST
    valid ``first_seen``, so deleting one copy doesn't reset the clock.
  * A monotonic ``last_seen`` high-water-mark detects system-clock rollback.

In production the embedded secret should be injected/obfuscated at build time.
"""
import hashlib
import hmac
import json
import os
import plistlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.conf import settings

ACTIVE = "active"
EXPIRING = "expiring"
EXPIRED = "expired"
TAMPERED = "tampered"

EXPIRING_WINDOW_DAYS = 7
_REG_PATH = r"Software\CodeSense"
_REG_VALUE = "license"


def _secret() -> bytes:
    explicit = os.getenv("LICENSE_SECRET") or getattr(settings, "LICENSE_SECRET", None)
    if explicit:
        return explicit.encode("utf-8")
    # No explicit secret: derive a per-install key from this install's SECRET_KEY
    # (unique + persisted on first run) rather than a constant shared by every build.
    base = getattr(settings, "SECRET_KEY", "") or ""
    return hashlib.sha256(("codesense-offline-license-v1:" + base).encode("utf-8")).digest()


def _duration() -> timedelta:
    return timedelta(days=int(getattr(settings, "LICENSE_DURATION_DAYS", 90)))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _sign(first_seen: str, last_seen: str) -> str:
    canonical = json.dumps(
        {"first_seen": first_seen, "last_seen": last_seen},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hmac.new(_secret(), canonical, hashlib.sha256).hexdigest()


def _make_record(first_seen: datetime, last_seen: datetime) -> dict:
    fs, ls = _iso(first_seen), _iso(last_seen)
    return {"first_seen": fs, "last_seen": ls, "sig": _sign(fs, ls)}


def _is_valid(rec) -> bool:
    if not isinstance(rec, dict) or "sig" not in rec:
        return False
    try:
        expected = _sign(rec.get("first_seen", ""), rec.get("last_seen", ""))
    except Exception:
        return False
    return hmac.compare_digest(expected, str(rec.get("sig", "")))


# --------------------------------------------------------------------------- #
# Storage backends — file (cross-platform) + registry (Windows) + plist (macOS)
# --------------------------------------------------------------------------- #
def _file_path() -> Path:
    return Path(getattr(settings, "DATA_DIR")) / "license.json"


def _file_read():
    p = _file_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"__corrupt__": True}  # present but unreadable -> treat as tamper


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
        return {"__corrupt__": True}


def _registry_write(rec: dict):
    if os.name != "nt":
        return
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as key:
            winreg.SetValueEx(key, _REG_VALUE, 0, winreg.REG_SZ, json.dumps(rec))
    except Exception:
        pass


def _plist_path() -> Path:
    """Second store on macOS — a plist OUTSIDE DATA_DIR (the registry analogue)."""
    override = getattr(settings, "LICENSE_PLIST_PATH", None)
    if override:
        return Path(override)
    return Path.home() / "Library" / "Preferences" / "com.codesense.desktop.license.plist"


def _plist_read():
    # Read directly via plistlib (not `defaults`) so cfprefsd never caches/clobbers it.
    if sys.platform != "darwin":
        return None
    p = _plist_path()
    if not p.exists():
        return None
    try:
        with p.open("rb") as fh:
            return plistlib.load(fh)
    except Exception:
        return {"__corrupt__": True}


def _plist_write(rec: dict):
    if sys.platform != "darwin":
        return
    try:
        p = _plist_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("wb") as fh:
            plistlib.dump(rec, fh)
    except Exception:
        pass


def _write_all(rec: dict):
    _file_write(rec)
    _registry_write(rec)
    _plist_write(rec)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def _state_payload(state, first_seen=None, expires_at=None, days_remaining=0):
    return {
        "state": state,
        "first_seen": _iso(first_seen) if first_seen else None,
        "expires_at": _iso(expires_at) if expires_at else None,
        "days_remaining": max(0, days_remaining),
    }


def get_state() -> dict:
    """Compute (and self-heal) the license state. Idempotently stamps first run.

    Returns {state, first_seen, expires_at, days_remaining}.
    """
    sources = [r for r in (_file_read(), _registry_read(), _plist_read()) if r is not None]

    if not sources:
        now = _now()
        _write_all(_make_record(now, now))
        return _compute(now, now)

    # Any present-but-invalid copy = tampering.
    if any(not _is_valid(r) for r in sources):
        return _state_payload(TAMPERED)

    first_seen = min(_parse(r["first_seen"]) for r in sources)
    last_seen = max(_parse(r["last_seen"]) for r in sources)
    now = _now()

    if now < last_seen:  # system clock rolled back below the high-water-mark
        return _state_payload(TAMPERED, first_seen=first_seen)

    _write_all(_make_record(first_seen, max(last_seen, now)))
    return _compute(first_seen, now)


def _compute(first_seen: datetime, now: datetime) -> dict:
    expires_at = first_seen + _duration()
    remaining = expires_at - now
    if remaining <= timedelta(0):
        state = EXPIRED
    elif remaining <= timedelta(days=EXPIRING_WINDOW_DAYS):
        state = EXPIRING
    else:
        state = ACTIVE
    return _state_payload(state, first_seen, expires_at, remaining.days)


def is_write_blocked() -> bool:
    """True when the app must refuse new scans / data writes (read-only grace)."""
    return get_state()["state"] in (EXPIRED, TAMPERED)
