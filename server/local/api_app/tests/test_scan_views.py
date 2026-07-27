import io
import threading
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from local.api_app.models.orm import Scan, SbomScan
from local.api_app.views import scan_views
from local.api_app.views.scan_views import GrypeCreateView, ScanCreateView, SbomCreateView


def _multipart_request(url, data):
    """Build a DRF Request carrying multipart form/file data, bypassing the
    @require_permission auth wrapper entirely (tests call view.post.__wrapped__
    directly, mirroring test_finding_views.py's _call helper) -- so request.user
    must be set manually since the decorator normally does that."""
    factory = APIRequestFactory()
    django_request = factory.post(url, data=data, format="multipart")
    request = Request(django_request, parsers=[MultiPartParser(), FormParser(), JSONParser()])
    request.user = {"id": "tester"}
    return request


def _valid_zip_bytes():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("file.txt", "hello")
    return buf.getvalue()


class ScanCreationOrphanedRowTests(TestCase):
    """Regression coverage for a real bug found in production use: uploading a
    corrupt/invalid zip (or hitting the single-scan-at-a-time lock) left the
    just-created Scan/SbomScan row stuck at status="queued" forever, with the
    error response never reflected in the row -- so the dashboard/scan list
    showed it as permanently pending instead of failed."""

    def _simulate_running_scan_thread(self):
        stop_event = threading.Event()
        t = threading.Thread(target=stop_event.wait, daemon=True)
        t.start()
        scan_views.scan_thread = t

        def _cleanup():
            stop_event.set()
            t.join(timeout=1)
            scan_views.scan_thread = None

        self.addCleanup(_cleanup)

    def test_code_scan_bad_zip_marks_scan_failed(self):
        bad_file = SimpleUploadedFile("bad.zip", b"not a real zip", content_type="application/zip")
        request = _multipart_request("/api/scans/create/", {
            "scan_name": "badzip-code", "project_id": "p1", "zip_file": bad_file,
        })
        response = ScanCreateView.post.__wrapped__(ScanCreateView(), request)
        self.assertEqual(response.status_code, 400)
        scan = Scan.objects.get(scan_name="badzip-code")
        self.assertEqual(scan.status, "failed")

    def test_code_scan_thread_conflict_marks_scan_failed(self):
        self._simulate_running_scan_thread()
        good_zip = SimpleUploadedFile("good.zip", _valid_zip_bytes(), content_type="application/zip")
        request = _multipart_request("/api/scans/create/", {
            "scan_name": "conflict-code", "project_id": "p1", "zip_file": good_zip,
        })
        response = ScanCreateView.post.__wrapped__(ScanCreateView(), request)
        self.assertEqual(response.status_code, 409)
        scan = Scan.objects.get(scan_name="conflict-code")
        self.assertEqual(scan.status, "failed")

    def test_sbom_scan_bad_zip_marks_scan_failed(self):
        bad_file = SimpleUploadedFile("bad.zip", b"not a real zip", content_type="application/zip")
        request = _multipart_request("/api/scans/sbom/create/", {
            "scan_name": "badzip-sbom", "project_id": "p1", "zip_file": bad_file,
        })
        response = SbomCreateView.post.__wrapped__(SbomCreateView(), request)
        self.assertEqual(response.status_code, 400)
        scan = SbomScan.objects.get(scan_name="badzip-sbom")
        self.assertEqual(scan.status, "failed")

    def test_sbom_scan_thread_conflict_marks_scan_failed(self):
        self._simulate_running_scan_thread()
        good_zip = SimpleUploadedFile("good.zip", _valid_zip_bytes(), content_type="application/zip")
        request = _multipart_request("/api/scans/sbom/create/", {
            "scan_name": "conflict-sbom", "project_id": "p1", "zip_file": good_zip,
        })
        response = SbomCreateView.post.__wrapped__(SbomCreateView(), request)
        self.assertEqual(response.status_code, 409)
        scan = SbomScan.objects.get(scan_name="conflict-sbom")
        self.assertEqual(scan.status, "failed")

    def test_grype_scan_thread_conflict_marks_scan_failed(self):
        self._simulate_running_scan_thread()
        sbom_file = SimpleUploadedFile("existing.json", b"{}", content_type="application/json")
        request = _multipart_request("/api/scans/grype/create/", {
            "scan_name": "conflict-grype", "project_id": "p1", "sbom_file": sbom_file,
        })
        response = GrypeCreateView.post.__wrapped__(GrypeCreateView(), request)
        self.assertEqual(response.status_code, 409)
        scan = SbomScan.objects.get(scan_name="conflict-grype")
        self.assertEqual(scan.status, "failed")
