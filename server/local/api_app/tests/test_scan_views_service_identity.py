from types import SimpleNamespace

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from local.api_app.tests.test_scan_views import _multipart_request
from local.api_app.views.scan_views import ScanCreateView, _service_identity_forbidden


class ServiceIdentityForbiddenTests(TestCase):
    def test_matching_project_is_allowed(self):
        request = SimpleNamespace(user={"id": "apikey:1", "role": "service", "project_id": "proj-A"})
        self.assertFalse(_service_identity_forbidden(request, "proj-A"))

    def test_mismatched_project_is_forbidden(self):
        request = SimpleNamespace(user={"id": "apikey:1", "role": "service", "project_id": "proj-B"})
        self.assertTrue(_service_identity_forbidden(request, "proj-A"))

    def test_human_jwt_identity_never_forbidden(self):
        request = SimpleNamespace(user={"id": "user1", "role": "admin"})
        self.assertFalse(_service_identity_forbidden(request, "proj-A"))

    def test_non_dict_user_never_forbidden(self):
        request = SimpleNamespace(user=None)
        self.assertFalse(_service_identity_forbidden(request, "proj-A"))


class ScanCreateServiceIdentityIntegrationTests(TestCase):
    def test_wrong_project_service_identity_gets_403(self):
        request = _multipart_request(
            "/api/scans/create/",
            {
                "scan_name": "test",
                "project_id": "proj-A",
                "zip_file": SimpleUploadedFile(
                    "x.zip", b"PK\x05\x06" + b"\x00" * 18, content_type="application/zip"
                ),
            },
        )
        request.user = {"id": "apikey:1", "role": "service", "project_id": "proj-B"}
        response = ScanCreateView.post.__wrapped__(ScanCreateView(), request)
        self.assertEqual(response.status_code, 403)
