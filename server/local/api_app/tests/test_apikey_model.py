from datetime import datetime, timezone

from django.test import TestCase

from local.api_app.models.orm import APIKey


class ApiKeyModelTest(TestCase):
    def test_create_and_reload(self):
        row = APIKey.objects.create(
            project_id="proj123",
            name="azure-devops-prod",
            key_hash="a" * 64,
            key_prefix="csk_abc123",
            created_by="user1",
            created_at=datetime.now(timezone.utc),
        )
        reloaded = APIKey.objects.get(id=row.id)
        self.assertEqual(reloaded.project_id, "proj123")
        self.assertEqual(reloaded.name, "azure-devops-prod")
        self.assertEqual(reloaded.key_hash, "a" * 64)
        self.assertEqual(reloaded.key_prefix, "csk_abc123")
        self.assertIsNone(reloaded.last_used_at)
        self.assertIsNone(reloaded.revoked_at)
