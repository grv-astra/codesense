import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from licenses.middleware import ReadOnlyGraceMiddleware
from licenses.services import offline_license as lic


def _ok_view(request):
    return JsonResponse({"ok": True})


class ReadOnlyGraceMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self._ov = override_settings(
            DATA_DIR=self.dir,
            LICENSE_DURATION_DAYS=90,
            LICENSE_PLIST_PATH=str(Path(self.dir) / "second_store.plist"),
        )
        self._ov.enable()
        # Isolate the Windows registry backend (no-op on macOS/Linux) so these
        # tests don't read/write the REAL HKCU\Software\CodeSense stamp — an
        # expired test stamp would otherwise corrupt the live app's license.
        self._reg = {}
        self._reg_read = mock.patch.object(
            lic, "_registry_read", side_effect=lambda: self._reg.get("rec"))
        self._reg_write = mock.patch.object(
            lic, "_registry_write", side_effect=lambda rec: self._reg.__setitem__("rec", rec))
        self._reg_read.start()
        self._reg_write.start()
        self.mw = ReadOnlyGraceMiddleware(_ok_view)
        self.rf = RequestFactory()

    def tearDown(self):
        self._reg_read.stop()
        self._reg_write.stop()
        self._ov.disable()

    def _expire(self):
        past = datetime.now(timezone.utc) - timedelta(days=100)
        lic._file_write(lic._make_record(past, past))

    def test_active_allows_write(self):
        lic.get_state()  # stamp active
        self.assertEqual(self.mw(self.rf.post("/api/scans/create/")).status_code, 200)

    def test_expired_blocks_write(self):
        self._expire()
        resp = self.mw(self.rf.post("/api/scans/create/"))
        self.assertEqual(resp.status_code, 403)

    def test_expired_allows_read(self):
        self._expire()
        self.assertEqual(self.mw(self.rf.get("/api/scans/123/")).status_code, 200)

    def test_expired_allows_login_setup_and_license(self):
        self._expire()
        self.assertEqual(self.mw(self.rf.post("/api/auth/login/")).status_code, 200)
        self.assertEqual(self.mw(self.rf.post("/api/auth/setup/admin/")).status_code, 200)
        self.assertEqual(self.mw(self.rf.get("/api/license/")).status_code, 200)

    def test_non_api_paths_untouched(self):
        self._expire()
        self.assertEqual(self.mw(self.rf.post("/something-else/")).status_code, 200)
