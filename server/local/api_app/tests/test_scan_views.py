import io
import os
import shutil
import tempfile
import threading
import zipfile
from datetime import datetime, timezone
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from licenses.services import trial
from local.api_app.models.orm import Finding, Scan, SbomScan
from local.api_app.views import scan_views
from local.api_app.views.scan_views import (
    GitHubRepoScanView,
    GrypeCreateView,
    ScanCancelView,
    ScanCreateView,
    SbomCreateView,
)


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


def _json_request(url, data):
    """Like _multipart_request but for views (GitHubRepoScanView) that read
    request.data as JSON rather than multipart form fields."""
    factory = APIRequestFactory()
    django_request = factory.post(url, data=data, format="json")
    request = Request(django_request, parsers=[JSONParser(), FormParser(), MultiPartParser()])
    request.user = {"id": "tester"}
    return request


def _join_scan_thread(timeout=5):
    """The pipeline (ScanCreateView/GitHubRepoScanView) runs in a daemon
    background thread; tests that assert on its outcome (status, source_path
    set post-clone) must wait for it to finish before reading the DB row."""
    t = scan_views.scan_thread
    if t is not None:
        t.join(timeout=timeout)


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

    def test_code_scan_bad_zip_leaves_source_path_empty(self):
        """A pre-extraction failure has nothing to resume -- source_path must
        stay unset, distinguishing it from the post-extraction 'interrupted'
        case where the source really is retained on disk."""
        bad_file = SimpleUploadedFile("bad.zip", b"not a real zip", content_type="application/zip")
        request = _multipart_request("/api/scans/create/", {
            "scan_name": "badzip-code-sourcepath", "project_id": "p1", "zip_file": bad_file,
        })
        response = ScanCreateView.post.__wrapped__(ScanCreateView(), request)
        self.assertEqual(response.status_code, 400)
        scan = Scan.objects.get(scan_name="badzip-code-sourcepath")
        self.assertEqual(scan.source_path, "")

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


@mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "5"})
class TrialSlotNotConsumedOnFailureTests(TestCase):
    """A scan that fails before/without ever reaching its pipeline's completion
    step must not consume a trial slot -- these are the same synchronous
    failure paths ScanCreationOrphanedRowTests exercises (bad zip, thread
    conflict), just asserting on trial.used()/can_start() instead of status.
    The background-thread pipeline-failure path (e.g. AST analysis raising) is
    covered separately by test_scanner.py's AST-failure test, which asserts
    scan_folder never reaches its trial.record_completion() call."""

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

    def test_code_scan_bad_zip_does_not_consume_a_slot(self):
        bad_file = SimpleUploadedFile("bad.zip", b"not a real zip", content_type="application/zip")
        request = _multipart_request("/api/scans/create/", {
            "scan_name": "badzip-code-trial", "project_id": "p1", "zip_file": bad_file,
        })
        ScanCreateView.post.__wrapped__(ScanCreateView(), request)
        self.assertEqual(trial.used(), 0)
        self.assertTrue(trial.can_start())

    def test_code_scan_thread_conflict_does_not_consume_a_slot(self):
        self._simulate_running_scan_thread()
        good_zip = SimpleUploadedFile("good.zip", _valid_zip_bytes(), content_type="application/zip")
        request = _multipart_request("/api/scans/create/", {
            "scan_name": "conflict-code-trial", "project_id": "p1", "zip_file": good_zip,
        })
        ScanCreateView.post.__wrapped__(ScanCreateView(), request)
        self.assertEqual(trial.used(), 0)

    def test_sbom_scan_bad_zip_does_not_consume_a_slot(self):
        bad_file = SimpleUploadedFile("bad.zip", b"not a real zip", content_type="application/zip")
        request = _multipart_request("/api/scans/sbom/create/", {
            "scan_name": "badzip-sbom-trial", "project_id": "p1", "zip_file": bad_file,
        })
        SbomCreateView.post.__wrapped__(SbomCreateView(), request)
        self.assertEqual(trial.used(), 0)
        self.assertTrue(trial.can_start())

    def test_sbom_scan_thread_conflict_does_not_consume_a_slot(self):
        self._simulate_running_scan_thread()
        good_zip = SimpleUploadedFile("good.zip", _valid_zip_bytes(), content_type="application/zip")
        request = _multipart_request("/api/scans/sbom/create/", {
            "scan_name": "conflict-sbom-trial", "project_id": "p1", "zip_file": good_zip,
        })
        SbomCreateView.post.__wrapped__(SbomCreateView(), request)
        self.assertEqual(trial.used(), 0)

    def test_grype_scan_thread_conflict_does_not_consume_a_slot(self):
        self._simulate_running_scan_thread()
        sbom_file = SimpleUploadedFile("existing.json", b"{}", content_type="application/json")
        request = _multipart_request("/api/scans/grype/create/", {
            "scan_name": "conflict-grype-trial", "project_id": "p1", "sbom_file": sbom_file,
        })
        GrypeCreateView.post.__wrapped__(GrypeCreateView(), request)
        self.assertEqual(trial.used(), 0)


class SourceRetentionTests(TestCase):
    """The extracted source must survive a scan (success or failure) instead of
    being deleted unconditionally -- that's the whole precondition for resume."""

    def test_source_path_recorded_and_retained_after_zip_scan(self):
        good_zip = SimpleUploadedFile("good.zip", _valid_zip_bytes(), content_type="application/zip")
        request = _multipart_request("/api/scans/create/", {
            "scan_name": "retained-code", "project_id": "p1", "zip_file": good_zip,
        })
        with mock.patch("local.api_app.views.scan_views.scan_folder", return_value=[]):
            response = ScanCreateView.post.__wrapped__(ScanCreateView(), request)
        self.assertEqual(response.status_code, 202)
        scan = Scan.objects.get(scan_name="retained-code")
        self.assertTrue(scan.source_path)
        self.assertTrue(os.path.isdir(scan.source_path))
        self.assertTrue(os.path.isfile(os.path.join(scan.source_path, "file.txt")))


class BackgroundPipelineSourceRetentionTests(TransactionTestCase):
    """Covers outcomes decided *inside* the background pipeline thread (status
    transitions, post-clone source_path). Must be a TransactionTestCase, not
    TestCase: as test_background_thread_db_cleanup.py documents, TestCase
    wraps each test in a transaction on the main connection, so a write
    committed by the background thread's own (separate) connection is either
    invisible to -- or lock-contended with -- a plain TestCase's queries.
    TransactionTestCase commits for real and flushes between tests instead."""

    def test_pipeline_failure_lands_interrupted_and_retains_source_on_disk(self):
        """The actual point of this commit: a failure *after* extraction must
        not be 'failed' (which historically implied nothing-to-resume) and
        must not delete the extracted source -- that's what makes resuming
        possible in a later task."""
        good_zip = SimpleUploadedFile("good.zip", _valid_zip_bytes(), content_type="application/zip")
        request = _multipart_request("/api/scans/create/", {
            "scan_name": "interrupted-code", "project_id": "p1", "zip_file": good_zip,
        })
        # The background thread must finish invoking the mocked scan_folder
        # *before* the patch is torn down, or it races the `with` exit and
        # ends up calling the real implementation instead.
        with mock.patch("local.api_app.views.scan_views.scan_folder", side_effect=RuntimeError("boom")):
            response = ScanCreateView.post.__wrapped__(ScanCreateView(), request)
            self.assertEqual(response.status_code, 202)
            _join_scan_thread()
        scan = Scan.objects.get(scan_name="interrupted-code")
        self.assertEqual(scan.status, "interrupted")
        self.assertTrue(scan.source_path)
        self.assertTrue(os.path.isdir(scan.source_path))
        self.assertTrue(os.path.isfile(os.path.join(scan.source_path, "file.txt")))

    def test_github_scan_records_source_path_after_successful_clone(self):
        cloned_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, cloned_dir, True)
        request = _json_request("/api/scans/github/create/", {
            "token": "t", "username": "u", "repo": "r", "branch": "main",
            "scan_name": "gh-retained", "project_id": "p1",
        })
        with mock.patch(
            "local.api_app.views.scan_views.scan_github_repo",
            new=mock.AsyncMock(return_value={"folder_path": cloned_dir}),
        ), mock.patch("local.api_app.views.scan_views.scan_folder", return_value=[]):
            response = GitHubRepoScanView.post.__wrapped__(GitHubRepoScanView(), request)
            self.assertEqual(response.status_code, 202)
            _join_scan_thread()
        scan = Scan.objects.get(scan_name="gh-retained")
        self.assertEqual(scan.source_path, cloned_dir)

    def test_github_scan_clone_failure_marks_failed_with_empty_source_path(self):
        """A clone failure means folder_path was never obtained -- source_path
        must stay empty and the row must land in 'failed', not 'interrupted'
        (there is nothing on disk to resume from)."""
        request = _json_request("/api/scans/github/create/", {
            "token": "t", "username": "u", "repo": "r", "branch": "main",
            "scan_name": "gh-clone-fail", "project_id": "p1",
        })
        with mock.patch(
            "local.api_app.views.scan_views.scan_github_repo",
            new=mock.AsyncMock(side_effect=RuntimeError("clone boom")),
        ):
            response = GitHubRepoScanView.post.__wrapped__(GitHubRepoScanView(), request)
            self.assertEqual(response.status_code, 202)
            _join_scan_thread()
        scan = Scan.objects.get(scan_name="gh-clone-fail")
        self.assertEqual(scan.status, "failed")
        self.assertEqual(scan.source_path, "")


class ScanCancelViewTests(TestCase):
    def _make_scan(self, status="in_progress"):
        return Scan.objects.create(
            project_id="p1", scan_name="cancel-me", status=status,
            created_at=datetime.now(timezone.utc), deleted=False,
        )

    def _cancel_request(self, scan_id):
        factory = APIRequestFactory()
        django_request = factory.post(f"/api/scans/{scan_id}/cancel/")
        request = Request(django_request, parsers=[JSONParser()])
        request.user = {"id": "tester"}
        return request

    def test_sets_cancel_requested_and_returns_202(self):
        scan = self._make_scan()
        request = self._cancel_request(scan.id)
        response = ScanCancelView.post.__wrapped__(ScanCancelView(), request, scan_id=scan.id)
        self.assertEqual(response.status_code, 202)
        scan.refresh_from_db()
        self.assertTrue(scan.cancel_requested)

    def test_sets_the_in_memory_event_for_the_running_scan(self):
        scan = self._make_scan()
        event = threading.Event()
        scan_views._cancel_events[scan.id] = event
        self.addCleanup(scan_views._cancel_events.pop, scan.id, None)
        request = self._cancel_request(scan.id)
        ScanCancelView.post.__wrapped__(ScanCancelView(), request, scan_id=scan.id)
        self.assertTrue(event.is_set())

    def test_404_for_unknown_scan(self):
        request = self._cancel_request("no-such-id")
        response = ScanCancelView.post.__wrapped__(ScanCancelView(), request, scan_id="no-such-id")
        self.assertEqual(response.status_code, 404)

    def test_409_for_already_terminal_scan(self):
        scan = self._make_scan(status="completed")
        request = self._cancel_request(scan.id)
        response = ScanCancelView.post.__wrapped__(ScanCancelView(), request, scan_id=scan.id)
        self.assertEqual(response.status_code, 409)

    def test_queued_scan_with_no_live_event_still_returns_202_via_db_only(self):
        """A 'queued' scan has no _cancel_events entry yet (registered only once
        the background thread starts) -- cancellation must still succeed via the
        DB flag alone, for the pipeline to pick up once it actually starts."""
        scan = self._make_scan(status="queued")
        self.assertNotIn(scan.id, scan_views._cancel_events)
        request = self._cancel_request(scan.id)
        response = ScanCancelView.post.__wrapped__(ScanCancelView(), request, scan_id=scan.id)
        self.assertEqual(response.status_code, 202)
        scan.refresh_from_db()
        self.assertTrue(scan.cancel_requested)


class ScanCancelViewAtomicityTests(TestCase):
    """A separate read-then-write would let a scan that finishes naturally in the
    gap between the two get incorrectly stamped cancel_requested=True and a false
    202. The fix folds the status check into the conditional UPDATE itself."""

    def _cancel_request(self, scan_id):
        factory = APIRequestFactory()
        django_request = factory.post(f"/api/scans/{scan_id}/cancel/")
        request = Request(django_request, parsers=[JSONParser()])
        request.user = {"id": "tester"}
        return request

    def test_409_when_scan_completes_between_read_and_write(self):
        scan = Scan.objects.create(
            project_id="p1", scan_name="finishes-in-the-gap", status="in_progress",
            created_at=datetime.now(timezone.utc), deleted=False,
        )
        request = self._cancel_request(scan.id)

        real_find_by_id = scan_views.ScanModel.find_by_id

        def find_by_id_then_complete(scan_id):
            result = real_find_by_id(scan_id=scan_id)
            # Simulate the scan finishing naturally right after the read.
            Scan.objects.filter(id=scan_id).update(status="completed")
            return result

        with mock.patch.object(
            scan_views.ScanModel, "find_by_id", side_effect=find_by_id_then_complete
        ):
            response = ScanCancelView.post.__wrapped__(ScanCancelView(), request, scan_id=scan.id)

        self.assertEqual(response.status_code, 409)
        scan.refresh_from_db()
        self.assertFalse(scan.cancel_requested)


class RunLsastPipelineCancelSyncTests(TestCase):
    """Covers the cancel-while-queued race: ScanCancelView can persist
    cancel_requested=True to the DB before the pipeline's threading.Event even
    exists (it's only created once the background thread starts). Without a
    sync step, _run_lsast_pipeline would start with a fresh, unset Event and
    silently ignore the already-persisted cancellation."""

    def test_pre_set_cancel_requested_flag_sets_the_fresh_event_before_work_starts(self):
        scan = Scan.objects.create(
            project_id="p1", scan_name="cancel-while-queued", status="queued",
            created_at=datetime.now(timezone.utc), deleted=False, cancel_requested=True,
        )
        source_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, source_dir, True)
        event = threading.Event()

        observed_event_state = {}

        def fake_scan_folder(**kwargs):
            # By the time scan_folder is invoked, the pipeline must already have
            # synced the DB flag onto the event -- the real scan_folder honors
            # cancel_event and would bail out immediately in this state.
            observed_event_state["was_set"] = kwargs["cancel_event"].is_set()
            return []

        with mock.patch("local.api_app.views.scan_views.scan_folder", side_effect=fake_scan_folder):
            scan_views._run_lsast_pipeline(
                scan.id, source_dir, "tester", "cancel-while-queued", cancel_event=event,
            )

        self.assertTrue(event.is_set())
        self.assertTrue(observed_event_state.get("was_set"))


class ScanResumeViewTests(TransactionTestCase):
    """TransactionTestCase, not TestCase -- test_starts_the_pipeline_and_
    clears_cancel_requested spawns a real background pipeline thread with its
    own DB connection; per BackgroundPipelineSourceRetentionTests above, a
    plain TestCase's wrapping transaction on the main connection lock-contends
    with that thread's separate connection against the same sqlite file."""
    def _make_scan(self, status="interrupted", source_path=None, cancel_requested=False):
        from datetime import datetime, timezone
        return Scan.objects.create(
            project_id="p1", scan_name="resume-me", status=status,
            created_at=datetime.now(timezone.utc), deleted=False,
            source_path=source_path or "", cancel_requested=cancel_requested,
        )

    def _resume_request(self, scan_id):
        factory = APIRequestFactory()
        django_request = factory.post(f"/api/scans/{scan_id}/resume/")
        request = Request(django_request, parsers=[JSONParser()])
        request.user = {"id": "tester"}
        return request

    def test_404_for_unknown_scan(self):
        from local.api_app.views.scan_views import ScanResumeView
        request = self._resume_request("no-such-id")
        response = ScanResumeView.post.__wrapped__(ScanResumeView(), request, scan_id="no-such-id")
        self.assertEqual(response.status_code, 404)

    def test_409_for_a_non_resumable_status(self):
        # The source_path/os.path.isdir check runs before the atomic status
        # update, so source_path must point at a real directory here -- else
        # this would trip the 410 path instead of exercising the 409 the
        # test is actually about.
        import tempfile
        from local.api_app.views.scan_views import ScanResumeView
        source_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, source_dir, True)
        scan = self._make_scan(status="completed", source_path=source_dir)
        request = self._resume_request(scan.id)
        response = ScanResumeView.post.__wrapped__(ScanResumeView(), request, scan_id=scan.id)
        self.assertEqual(response.status_code, 409)

    def test_410_when_source_path_missing_on_disk(self):
        from local.api_app.views.scan_views import ScanResumeView
        scan = self._make_scan(source_path="/tmp/does-not-exist-at-all-xyz")
        request = self._resume_request(scan.id)
        response = ScanResumeView.post.__wrapped__(ScanResumeView(), request, scan_id=scan.id)
        self.assertEqual(response.status_code, 410)
        scan.refresh_from_db()
        self.assertEqual(scan.status, "failed")

    def test_starts_the_pipeline_and_clears_cancel_requested(self):
        import tempfile
        from local.api_app.views.scan_views import ScanResumeView
        source_dir = tempfile.mkdtemp()
        scan = self._make_scan(source_path=source_dir, cancel_requested=True)
        request = self._resume_request(scan.id)
        # The view starts a real background thread for the pipeline; it must
        # finish invoking the mocked scan_folder *before* the patch is torn
        # down (join inside the `with`), or it races the `with` exit and ends
        # up calling the real implementation instead -- see
        # BackgroundPipelineSourceRetentionTests above, which hits the same
        # hazard. Joining also releases the thread's DB connection before
        # teardown, avoiding a locked sqlite test DB file on Windows.
        with mock.patch("local.api_app.views.scan_views.scan_folder", return_value=[]):
            response = ScanResumeView.post.__wrapped__(ScanResumeView(), request, scan_id=scan.id)
            self.assertEqual(response.status_code, 202)
            _join_scan_thread()
        scan.refresh_from_db()
        self.assertFalse(scan.cancel_requested)

    def test_skip_fingerprints_flows_from_persisted_findings_to_the_pipeline_call(self):
        """already_done_fingerprints(scan_id) must actually reach the
        pipeline's skip_fingerprints kwarg -- this is the whole point of
        resume (skip re-verifying/re-enriching what a prior attempt already
        persisted). Mocks _run_lsast_pipeline itself (not just scan_folder)
        so the call's kwargs are directly inspectable."""
        import tempfile
        from local.api_app.views.scan_views import ScanResumeView
        source_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, source_dir, True)
        scan = self._make_scan(source_path=source_dir)
        Finding.objects.create(
            scan_id=scan.id, fingerprint="already-persisted-fp",
            created_at=datetime.now(timezone.utc),
        )
        request = self._resume_request(scan.id)
        with mock.patch("local.api_app.views.scan_views._run_lsast_pipeline") as mock_pipeline:
            response = ScanResumeView.post.__wrapped__(ScanResumeView(), request, scan_id=scan.id)
            self.assertEqual(response.status_code, 202)
            _join_scan_thread()
        mock_pipeline.assert_called_once()
        _, kwargs = mock_pipeline.call_args
        self.assertIn("already-persisted-fp", kwargs["skip_fingerprints"])

    def test_conflicts_with_an_already_running_scan(self):
        from local.api_app.views import scan_views
        from local.api_app.views.scan_views import ScanResumeView
        scan = self._make_scan(source_path="/tmp/whatever-exists-or-not")
        stop_event = threading.Event()
        t = threading.Thread(target=stop_event.wait, daemon=True)
        t.start()
        scan_views.scan_thread = t
        def _cleanup():
            stop_event.set(); t.join(timeout=1); scan_views.scan_thread = None
        self.addCleanup(_cleanup)
        os.makedirs(scan.source_path, exist_ok=True)
        self.addCleanup(lambda: __import__("shutil").rmtree(scan.source_path, ignore_errors=True))
        request = self._resume_request(scan.id)
        response = ScanResumeView.post.__wrapped__(ScanResumeView(), request, scan_id=scan.id)
        self.assertEqual(response.status_code, 409)
