from django.test import TestCase

from local.api_app.models.apikey_model import (
    API_KEY_PREFIX,
    ApiKeyModel,
    generate_api_key,
    hash_api_key,
)


class GenerateApiKeyTests(TestCase):
    def test_generate_api_key_has_prefix(self):
        key = generate_api_key()
        self.assertTrue(key.startswith(API_KEY_PREFIX))
        self.assertGreater(len(key), len(API_KEY_PREFIX) + 20)

    def test_generate_api_key_is_unique(self):
        self.assertNotEqual(generate_api_key(), generate_api_key())

    def test_hash_api_key_is_deterministic_sha256(self):
        key = "csk_sometestvalue"
        self.assertEqual(hash_api_key(key), hash_api_key(key))
        self.assertEqual(len(hash_api_key(key)), 64)


class ApiKeyModelTests(TestCase):
    def test_create_returns_row_and_plaintext(self):
        row, plaintext = ApiKeyModel.create(project_id="proj1", name="ci", created_by="admin1")
        self.assertTrue(plaintext.startswith(API_KEY_PREFIX))
        self.assertEqual(row.project_id, "proj1")
        self.assertEqual(row.key_hash, hash_api_key(plaintext))
        self.assertEqual(row.key_prefix, plaintext[:12])

    def test_find_by_hash_excludes_revoked(self):
        row, plaintext = ApiKeyModel.create(project_id="proj1", name="ci", created_by="admin1")
        found = ApiKeyModel.find_by_hash(hash_api_key(plaintext))
        self.assertEqual(found.id, row.id)

        ApiKeyModel.revoke(row.id, "proj1")
        self.assertIsNone(ApiKeyModel.find_by_hash(hash_api_key(plaintext)))

    def test_list_by_project_orders_newest_first(self):
        row1, _ = ApiKeyModel.create(project_id="proj2", name="first", created_by="admin1")
        row2, _ = ApiKeyModel.create(project_id="proj2", name="second", created_by="admin1")
        rows = list(ApiKeyModel.list_by_project("proj2"))
        self.assertEqual([r.id for r in rows], [row2.id, row1.id])

    def test_revoke_unknown_key_returns_none(self):
        self.assertIsNone(ApiKeyModel.revoke("nonexistent", "proj1"))

    def test_touch_last_used_sets_timestamp(self):
        row, _ = ApiKeyModel.create(project_id="proj1", name="ci", created_by="admin1")
        self.assertIsNone(row.last_used_at)
        ApiKeyModel.touch_last_used(row.id)
        row.refresh_from_db()
        self.assertIsNotNone(row.last_used_at)
