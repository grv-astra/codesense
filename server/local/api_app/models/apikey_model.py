import hashlib
import secrets
from datetime import datetime, timezone

from local.api_app.models.orm import APIKey

API_KEY_PREFIX = "csk_"


def generate_api_key() -> str:
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class ApiKeyModel:
    @staticmethod
    def create(project_id: str, name: str, created_by: str):
        plaintext = generate_api_key()
        row = APIKey.objects.create(
            project_id=project_id,
            name=name,
            key_hash=hash_api_key(plaintext),
            key_prefix=plaintext[:12],
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )
        return row, plaintext

    @staticmethod
    def find_by_hash(key_hash: str):
        return APIKey.objects.filter(key_hash=key_hash, revoked_at__isnull=True).first()

    @staticmethod
    def list_by_project(project_id: str):
        return APIKey.objects.filter(project_id=project_id).order_by("-created_at")

    @staticmethod
    def revoke(key_id: str, project_id: str):
        row = APIKey.objects.filter(id=key_id, project_id=project_id).first()
        if not row:
            return None
        row.revoked_at = datetime.now(timezone.utc)
        row.save(update_fields=["revoked_at"])
        return row

    @staticmethod
    def touch_last_used(key_id: str):
        APIKey.objects.filter(id=key_id).update(last_used_at=datetime.now(timezone.utc))
