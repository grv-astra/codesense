from datetime import datetime, timezone

from django.db.utils import IntegrityError
from django.test import TestCase

from local.api_app.models.orm import APIKey


class ApiKeyModelTests(TestCase):
    def test_create_and_reload(self):
        created_at_value = datetime.now(timezone.utc)
        row = APIKey.objects.create(
            project_id="proj123",
            name="azure-devops-prod",
            key_hash="a" * 64,
            key_prefix="csk_abc123",
            created_by="user1",
            created_at=created_at_value,
        )
        reloaded = APIKey.objects.get(id=row.id)
        self.assertEqual(reloaded.project_id, "proj123")
        self.assertEqual(reloaded.name, "azure-devops-prod")
        self.assertEqual(reloaded.key_hash, "a" * 64)
        self.assertEqual(reloaded.key_prefix, "csk_abc123")
        self.assertEqual(reloaded.created_by, "user1")
        self.assertEqual(reloaded.created_at, created_at_value)
        self.assertIsNone(reloaded.last_used_at)
        self.assertIsNone(reloaded.revoked_at)

    def test_key_hash_uniqueness_enforced(self):
        APIKey.objects.create(
            project_id="proj123",
            name="azure-devops-prod",
            key_hash="b" * 64,
            key_prefix="csk_abc123",
            created_by="user1",
            created_at=datetime.now(timezone.utc),
        )
        with self.assertRaises(IntegrityError):
            APIKey.objects.create(
                project_id="proj456",
                name="github-actions-prod",
                key_hash="b" * 64,
                key_prefix="csk_def456",
                created_by="user2",
                created_at=datetime.now(timezone.utc),
            )
