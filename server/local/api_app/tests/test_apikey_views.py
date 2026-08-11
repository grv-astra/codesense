from django.test import TestCase

from local.api_app.models.apikey_model import ApiKeyModel
from local.api_app.views.apikey_views import ApiKeyListCreateView, ApiKeyRevokeView


class _FakeRequest:
    def __init__(self, user=None, data=None):
        self.user = user or {"id": "admin1", "role": "admin"}
        self.data = data or {}


class ApiKeyListCreateViewTests(TestCase):
    def test_create_returns_plaintext_once(self):
        request = _FakeRequest(data={"name": "azure-devops-prod"})
        response = ApiKeyListCreateView.post.__wrapped__(
            ApiKeyListCreateView(), request, project_id="proj1"
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["key"].startswith("csk_"))
        self.assertEqual(response.data["name"], "azure-devops-prod")

    def test_create_requires_name(self):
        request = _FakeRequest(data={})
        response = ApiKeyListCreateView.post.__wrapped__(
            ApiKeyListCreateView(), request, project_id="proj1"
        )
        self.assertEqual(response.status_code, 400)

    def test_list_never_returns_plaintext_or_hash(self):
        ApiKeyModel.create(project_id="proj1", name="ci-1", created_by="admin1")
        request = _FakeRequest()
        response = ApiKeyListCreateView.get.__wrapped__(
            ApiKeyListCreateView(), request, project_id="proj1"
        )
        self.assertEqual(response.status_code, 200)
        row = response.data[0]
        self.assertNotIn("key", row)
        self.assertNotIn("key_hash", row)
        self.assertEqual(row["name"], "ci-1")


class ApiKeyRevokeViewTests(TestCase):
    def test_revoke_sets_revoked_at(self):
        row, _ = ApiKeyModel.create(project_id="proj1", name="ci", created_by="admin1")
        request = _FakeRequest()
        response = ApiKeyRevokeView.post.__wrapped__(
            ApiKeyRevokeView(), request, project_id="proj1", key_id=row.id
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["revoked_at"])

    def test_revoke_unknown_key_returns_404(self):
        request = _FakeRequest()
        response = ApiKeyRevokeView.post.__wrapped__(
            ApiKeyRevokeView(), request, project_id="proj1", key_id="nope"
        )
        self.assertEqual(response.status_code, 404)
