import hashlib
import json
import os
from datetime import datetime, timezone

from django.conf import settings
from local.auth_app.models.user_model import UserModel

DEFAULT_LICENSE_DIR = "./license_data"
PROTECTED_ROLES = {"admin", "manager", "user"}


def _license_dir():
    configured_dir = getattr(settings, "LOCAL_KEYS_DIR", None)
    if configured_dir and os.path.exists(configured_dir):
        return configured_dir
    return DEFAULT_LICENSE_DIR


def _registry_path():
    return os.path.join(_license_dir(), "protected_accounts.json")


def _safe_string(value):
    return "" if value is None else str(value)


def _password_fingerprint(password_hash):
    if not password_hash:
        return ""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()


def _user_snapshot(user, created_by=None):
    role = _safe_string(user.get("role")).lower()
    return {
        "id": _safe_string(user.get("_id") or user.get("id")),
        "email": _safe_string(user.get("email")).strip().lower(),
        "name": _safe_string(user.get("name")),
        "company": _safe_string(user.get("company")),
        "role": role,
        "deleted": bool(user.get("deleted", False)),
        "password_fingerprint": _password_fingerprint(user.get("password", "")),
        "created_by": created_by or "codesense",
        "created_at": _safe_string(user.get("created_at")),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_registry():
    path = _registry_path()
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_registry(registry):
    path = _registry_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)


def should_track_user(user):
    role = _safe_string(user.get("role")).lower()
    return role in PROTECTED_ROLES


def register_user(user, created_by=None):
    if not user or not should_track_user(user):
        return
    registry = _load_registry()
    snapshot = _user_snapshot(user, created_by=created_by)
    registry[snapshot["email"]] = snapshot
    _save_registry(registry)


def unregister_user(user):
    if not user:
        return
    email = _safe_string(user.get("email")).strip().lower()
    registry = _load_registry()
    if email in registry:
        registry.pop(email, None)
        _save_registry(registry)


def sync_protected_accounts(created_by="provisioning"):
    registry = {}
    cursor = UserModel.collection.find({"role": {"$in": list(PROTECTED_ROLES)}, "deleted": False})
    for user in cursor:
        snapshot = _user_snapshot(user, created_by=created_by)
        registry[snapshot["email"]] = snapshot
    _save_registry(registry)


def verify_user(user):
    if not user:
        return None

    email = _safe_string(user.get("email")).strip().lower()
    registry = _load_registry()
    expected = registry.get(email)
    if not expected:
        return None

    current = _user_snapshot(user, created_by=expected.get("created_by"))
    changed_fields = []
    compare_fields = ["id", "email", "name", "company", "role", "deleted", "password_fingerprint"]
    for field in compare_fields:
        if current.get(field) != expected.get(field):
            changed_fields.append(field)

    if not changed_fields:
        return None

    return {
        "message": "Unauthorized: protected CodeSense account details were modified locally.",
        "account": {
            "email": expected.get("email"),
            "name": expected.get("name"),
            "company": expected.get("company"),
            "role": expected.get("role"),
            "created_by": expected.get("created_by"),
            "created_at": expected.get("created_at"),
        },
        "current_account": {
            "email": current.get("email"),
            "name": current.get("name"),
            "company": current.get("company"),
            "role": current.get("role"),
            "deleted": current.get("deleted"),
        },
        "changed_fields": changed_fields,
    }


def verify_payload_user(payload):
    if not payload:
        return None

    user = None
    user_id = _safe_string(payload.get("id"))
    email = _safe_string(payload.get("email")).strip().lower()

    if user_id:
        user = UserModel.find_raw_by_id(user_id)
    if not user and email:
        user = UserModel.find_by_email(email)

    if not user:
        return {
            "message": "Unauthorized: protected CodeSense account is missing locally.",
            "account": {
                "id": user_id,
                "email": email,
                "role": _safe_string(payload.get("role")).lower(),
            },
            "changed_fields": ["missing_account"],
        }

    return verify_user(user)
