from django.test import TestCase

from local.api_app.models.apikey_model import ApiKeyModel
from local.auth_app.utils.api_key_auth import is_api_key, resolve_api_key


class IsApiKeyTests(TestCase):
    def test_recognizes_api_key_prefix(self):
        self.assertTrue(is_api_key("csk_abc123"))

    def test_rejects_jwt_shaped_token(self):
        self.assertFalse(is_api_key("eyJhbGciOiJIUzI1NiJ9.payload.sig"))


class ResolveApiKeyTests(TestCase):
    def test_resolves_valid_key_to_service_identity(self):
        row, plaintext = ApiKeyModel.create(project_id="proj9", name="ci", created_by="admin1")
        identity = resolve_api_key(plaintext)
        self.assertEqual(
            identity, {"id": f"apikey:{row.id}", "role": "service", "project_id": "proj9"}
        )

    def test_updates_last_used_on_resolve(self):
        row, plaintext = ApiKeyModel.create(project_id="proj9", name="ci", created_by="admin1")
        resolve_api_key(plaintext)
        row.refresh_from_db()
        self.assertIsNotNone(row.last_used_at)

    def test_returns_none_for_unknown_key(self):
        self.assertIsNone(resolve_api_key("csk_doesnotexist"))

    def test_returns_none_for_revoked_key(self):
        row, plaintext = ApiKeyModel.create(project_id="proj9", name="ci", created_by="admin1")
        ApiKeyModel.revoke(row.id, "proj9")
        self.assertIsNone(resolve_api_key(plaintext))
