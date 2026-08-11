from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from local.api_app.models.apikey_model import ApiKeyModel
from local.auth_app.permissions.decorators import require_permission


class _DummyCreateScanView:
    @require_permission("create_scan")
    def post(self, request):
        return {"ok": True, "user": request.user}


class _DummyUpdateProjectView:
    @require_permission("update_project")
    def post(self, request):
        return {"ok": True}


def _request_with_auth(header_value):
    factory = APIRequestFactory()
    django_request = factory.post("/whatever/", data={}, format="json")
    request = Request(django_request)
    request.META["HTTP_AUTHORIZATION"] = header_value
    return request


class RequirePermissionApiKeyTests(TestCase):
    def test_valid_api_key_grants_create_scan(self):
        _, plaintext = ApiKeyModel.create(project_id="proj1", name="ci", created_by="admin1")
        request = _request_with_auth(f"Bearer {plaintext}")
        response = _DummyCreateScanView().post(request)
        self.assertEqual(response["ok"], True)
        self.assertEqual(response["user"]["role"], "service")
        self.assertEqual(response["user"]["project_id"], "proj1")

    def test_revoked_api_key_rejected(self):
        row, plaintext = ApiKeyModel.create(project_id="proj1", name="ci", created_by="admin1")
        ApiKeyModel.revoke(row.id, "proj1")
        request = _request_with_auth(f"Bearer {plaintext}")
        response = _DummyCreateScanView().post(request)
        self.assertEqual(response.status_code, 401)

    def test_unknown_api_key_rejected(self):
        request = _request_with_auth("Bearer csk_totallyunknown")
        response = _DummyCreateScanView().post(request)
        self.assertEqual(response.status_code, 401)

    def test_api_key_cannot_access_non_create_scan_permission(self):
        _, plaintext = ApiKeyModel.create(project_id="proj1", name="ci", created_by="admin1")
        request = _request_with_auth(f"Bearer {plaintext}")
        response = _DummyUpdateProjectView().post(request)
        self.assertEqual(response.status_code, 403)
