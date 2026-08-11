from django.test import TestCase

from local.api_app.models.apikey_model import ApiKeyModel
from local.api_app.models.project_models import ProjectModel
from local.api_app.views.apikey_views import ApiKeyListCreateView, ApiKeyRevokeView


class _FakeRequest:
    def __init__(self, user=None, data=None):
        self.user = user or {"id": "admin1", "role": "admin"}
        self.data = data or {}


def _make_project(name="proj"):
    return ProjectModel.create({"name": name, "created_by": "admin1"})["id"]


class ApiKeyListCreateViewTests(TestCase):
    def setUp(self):
        self.project_id = _make_project("proj1")

    def test_create_returns_plaintext_once(self):
        request = _FakeRequest(data={"name": "azure-devops-prod"})
        response = ApiKeyListCreateView.post.__wrapped__(
            ApiKeyListCreateView(), request, project_id=self.project_id
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["key"].startswith("csk_"))
        self.assertEqual(response.data["name"], "azure-devops-prod")

    def test_create_requires_name(self):
        request = _FakeRequest(data={})
        response = ApiKeyListCreateView.post.__wrapped__(
            ApiKeyListCreateView(), request, project_id=self.project_id
        )
        self.assertEqual(response.status_code, 400)

    def test_list_never_returns_plaintext_or_hash(self):
        ApiKeyModel.create(project_id=self.project_id, name="ci-1", created_by="admin1")
        request = _FakeRequest()
        response = ApiKeyListCreateView.get.__wrapped__(
            ApiKeyListCreateView(), request, project_id=self.project_id
        )
        self.assertEqual(response.status_code, 200)
        row = response.data[0]
        self.assertNotIn("key", row)
        self.assertNotIn("key_hash", row)
        self.assertEqual(row["name"], "ci-1")

    def test_get_unknown_project_returns_404(self):
        request = _FakeRequest()
        response = ApiKeyListCreateView.get.__wrapped__(
            ApiKeyListCreateView(), request, project_id="does-not-exist"
        )
        self.assertEqual(response.status_code, 404)

    def test_create_unknown_project_returns_404(self):
        request = _FakeRequest(data={"name": "azure-devops-prod"})
        response = ApiKeyListCreateView.post.__wrapped__(
            ApiKeyListCreateView(), request, project_id="does-not-exist"
        )
        self.assertEqual(response.status_code, 404)


class ApiKeyRevokeViewTests(TestCase):
    def setUp(self):
        self.project_id = _make_project("proj1")

    def test_revoke_sets_revoked_at(self):
        row, _ = ApiKeyModel.create(project_id=self.project_id, name="ci", created_by="admin1")
        request = _FakeRequest()
        response = ApiKeyRevokeView.post.__wrapped__(
            ApiKeyRevokeView(), request, project_id=self.project_id, key_id=row.id
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["revoked_at"])

    def test_revoke_unknown_key_returns_404(self):
        request = _FakeRequest()
        response = ApiKeyRevokeView.post.__wrapped__(
            ApiKeyRevokeView(), request, project_id=self.project_id, key_id="nope"
        )
        self.assertEqual(response.status_code, 404)

    def test_revoke_unknown_project_returns_404(self):
        row, _ = ApiKeyModel.create(project_id=self.project_id, name="ci", created_by="admin1")
        request = _FakeRequest()
        response = ApiKeyRevokeView.post.__wrapped__(
            ApiKeyRevokeView(), request, project_id="does-not-exist", key_id=row.id
        )
        self.assertEqual(response.status_code, 404)


class ApiKeyCrossProjectIsolationTests(TestCase):
    """Mirrors test_scan_views_service_identity.py's project-scoping proof: the
    model layer already filters by project_id, but nothing exercised that at
    the view layer for API keys until now."""

    def setUp(self):
        self.proj1_id = _make_project("proj1")
        self.proj2_id = _make_project("proj2")

    def test_list_only_returns_keys_for_requested_project(self):
        ApiKeyModel.create(project_id=self.proj1_id, name="proj1-key", created_by="admin1")
        ApiKeyModel.create(project_id=self.proj2_id, name="proj2-key", created_by="admin1")

        request = _FakeRequest()
        response = ApiKeyListCreateView.get.__wrapped__(
            ApiKeyListCreateView(), request, project_id=self.proj1_id
        )
        self.assertEqual(response.status_code, 200)
        names = [row["name"] for row in response.data]
        self.assertEqual(names, ["proj1-key"])

    def test_revoke_with_mismatched_project_returns_404_and_leaves_key_active(self):
        row, _ = ApiKeyModel.create(project_id=self.proj2_id, name="proj2-key", created_by="admin1")

        request = _FakeRequest()
        response = ApiKeyRevokeView.post.__wrapped__(
            ApiKeyRevokeView(), request, project_id=self.proj1_id, key_id=row.id
        )
        self.assertEqual(response.status_code, 404)

        row.refresh_from_db()
        self.assertIsNone(row.revoked_at)
