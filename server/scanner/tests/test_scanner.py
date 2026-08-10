from unittest import mock

from django.test import SimpleTestCase

import scanner.rag.scanner as scanner_module
from scanner.rag.semgrep_detector import SemgrepDetectionError


class ScanFolderTests(SimpleTestCase):
    """scan_folder is the LSAST entrypoint (the only engine) + scan lifecycle."""

    @mock.patch("licenses.services.trial.record_completion")
    @mock.patch.object(scanner_module, "lsast_scan_folder",
                       return_value=(["finding"], ["filtered"]))
    @mock.patch.object(scanner_module, "update_progress")
    @mock.patch.object(scanner_module, "analyze_folder",
                       return_value={"total_loc": 10, "total_functions": 2, "languages": ["python"],
                                     "total_files": 5})
    def test_runs_lsast_and_marks_scan_completed(self, mock_ast, mock_update, mock_lsast, mock_trial):
        result = scanner_module.scan_folder("/x", "s1", "user-1", "Scan #1")
        # returns the visible findings from the LSAST pipeline
        self.assertEqual(result, ["finding"])
        # AST metrics recorded, LSAST detection invoked
        mock_ast.assert_called_once_with("/x")
        mock_lsast.assert_called_once_with(
            "/x", "s1", "user-1",
            skip_fingerprints=frozenset(), cancel_event=None,
        )
        # a completed-status update happened with the visible findings count
        completed = [c for c in mock_update.call_args_list if c.kwargs.get("status") == "completed"]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].kwargs.get("findings"), 1)
        # Regression: total_files must be re-asserted (not just files_scanned) at
        # completion, using the real AST-derived file count -- previously the
        # LSAST loop's per-finding progress updates could leave total_files
        # holding a findings count instead, with nothing correcting it back.
        self.assertEqual(completed[0].kwargs.get("total"), 5)
        self.assertEqual(completed[0].kwargs.get("scanned"), 5)
        # a successful completion consumes a trial slot (no-op when trial mode is off)
        mock_trial.assert_called_once()

    @mock.patch("licenses.services.trial.record_completion")
    @mock.patch.object(scanner_module, "lsast_scan_folder")
    @mock.patch.object(scanner_module, "update_progress")
    @mock.patch.object(scanner_module, "analyze_folder", side_effect=RuntimeError("ast boom"))
    def test_records_error_and_returns_empty_on_ast_failure(self, mock_ast, mock_update, mock_lsast, mock_trial):
        result = scanner_module.scan_folder("/x", "s1", "user-1", "Scan #1")
        self.assertEqual(result, [])
        mock_lsast.assert_not_called()
        error_calls = [c for c in mock_update.call_args_list if c.kwargs.get("error")]
        self.assertTrue(error_calls)
        # Regression: an AST failure used to leave the row's status untouched
        # (whatever the caller set before invoking scan_folder, typically
        # "queued") -- scan_folder returns [] normally rather than raising, so
        # the calling view's own except-block status="failed" update is never
        # reached either. The row was stuck "queued" forever with no way to
        # tell it had actually failed. Must be marked "interrupted" here
        # instead of "failed" -- the extracted source is retained regardless
        # of this failure (see scan_views.py), so resuming is always safe.
        self.assertEqual(error_calls[0].kwargs.get("status"), "interrupted")
        self.assertIsNotNone(error_calls[0].kwargs.get("end_time"))
        # an AST-analysis failure returns before STEP 3, so no trial slot is consumed
        mock_trial.assert_not_called()

    @mock.patch("licenses.services.trial.record_completion")
    @mock.patch.object(scanner_module, "lsast_scan_folder", side_effect=RuntimeError("lsast boom"))
    @mock.patch.object(scanner_module, "update_progress")
    @mock.patch.object(scanner_module, "analyze_folder",
                       return_value={"total_loc": 10, "total_functions": 2, "languages": ["python"]})
    def test_lsast_failure_propagates_and_does_not_consume_a_trial_slot(self, mock_ast, mock_update, mock_lsast, mock_trial):
        # Unlike the AST-analysis failure above, a STEP 2 (LSAST) failure is not
        # caught inside scan_folder itself -- it propagates to the caller
        # (ScanCreateView/GitHubRepoScanView's run_scan(), which marks the row
        # failed). Either way, STEP 3's trial.record_completion() is unreached.
        with self.assertRaisesMessage(RuntimeError, "lsast boom"):
            scanner_module.scan_folder("/x", "s1", "user-1", "Scan #1")
        mock_trial.assert_not_called()

    @mock.patch("licenses.services.trial.record_completion")
    @mock.patch.object(scanner_module, "lsast_scan_folder",
                       side_effect=SemgrepDetectionError("Semgrep/OpenGrep did not finish within 300s"))
    @mock.patch.object(scanner_module, "update_progress")
    @mock.patch.object(scanner_module, "analyze_folder",
                       return_value={"total_loc": 10, "total_functions": 2, "languages": ["python"],
                                     "total_files": 5})
    def test_detector_timeout_marks_interrupted_not_completed(self, mock_ast, mock_update, mock_lsast, mock_trial):
        # Regression: unlike a generic LSAST failure (which propagates
        # uncaught, see test_lsast_failure_propagates_...), a detector timeout
        # is caught here specifically so the scan row never lands on
        # status="completed" with a phantom 0-findings result -- that looked
        # identical to a genuinely clean scan.
        result = scanner_module.scan_folder("/x", "s1", "user-1", "Scan #1")
        self.assertEqual(result, [])
        status_calls = [c.kwargs.get("status") for c in mock_update.call_args_list
                        if c.kwargs.get("status")]
        self.assertIn("interrupted", status_calls)
        self.assertNotIn("completed", status_calls)
        error_calls = [c for c in mock_update.call_args_list if c.kwargs.get("error")]
        self.assertTrue(error_calls)
        self.assertIn("did not finish within 300s", error_calls[0].kwargs.get("error"))
        mock_trial.assert_not_called()

    def test_no_legacy_engine_remains(self):
        # The legacy engine + SCAN_ENGINE flag were removed; LSAST is the only path.
        self.assertFalse(hasattr(scanner_module, "_legacy_scan_folder"))
        self.assertFalse(hasattr(scanner_module, "_lsast_scan_folder"))

    @mock.patch.object(scanner_module, "lsast_scan_folder")
    @mock.patch.object(scanner_module, "analyze_folder", side_effect=RuntimeError("ast boom"))
    @mock.patch.object(scanner_module, "update_progress")
    def test_ast_failure_now_marks_interrupted_not_failed(self, mock_progress, _analyze, _lsast):
        scanner_module.scan_folder(folder_path="/tmp/code", scan_id="s1", triggered_by="u1", scan_name="n")
        # Find the call that set the terminal status.
        status_calls = [c.kwargs.get("status") for c in mock_progress.call_args_list
                        if c.kwargs.get("status")]
        self.assertIn("interrupted", status_calls)
        self.assertNotIn("failed", status_calls)

    @mock.patch.object(scanner_module, "lsast_scan_folder")
    @mock.patch.object(scanner_module, "analyze_folder",
                       return_value={"total_files": 1, "total_functions": 1, "total_loc": 10, "languages": ["python"]})
    @mock.patch.object(scanner_module, "update_progress")
    def test_cancelled_run_marks_status_cancelled(self, mock_progress, _analyze, mock_lsast):
        import threading
        cancel_event = threading.Event()
        cancel_event.set()  # already cancelled by the time lsast_scan_folder returns
        mock_lsast.return_value = ([{"cwe": "CWE-89"}], [])
        scanner_module.scan_folder(folder_path="/tmp/code", scan_id="s1", triggered_by="u1", scan_name="n",
                                    cancel_event=cancel_event)
        status_calls = [c.kwargs.get("status") for c in mock_progress.call_args_list
                        if c.kwargs.get("status")]
        self.assertIn("cancelled", status_calls)
        self.assertNotIn("completed", status_calls)
        # Regression guard: the cancelled-status call must NOT overwrite the
        # incrementally-tracked `scanned` value with total_files -- that would
        # claim a full scan happened despite status="cancelled".
        cancelled_call = next(c for c in mock_progress.call_args_list
                               if c.kwargs.get("status") == "cancelled")
        self.assertNotIn("scanned", cancelled_call.kwargs)

    @mock.patch("licenses.services.trial.record_completion")
    @mock.patch.object(scanner_module, "lsast_scan_folder")
    @mock.patch.object(scanner_module, "analyze_folder",
                       return_value={"total_files": 1, "total_functions": 1, "total_loc": 10, "languages": ["python"]})
    @mock.patch.object(scanner_module, "update_progress")
    def test_skip_fingerprints_passed_through_to_lsast(self, _progress, _analyze, mock_lsast, _trial):
        mock_lsast.return_value = ([], [])
        skip = frozenset({"abc"})
        scanner_module.scan_folder(folder_path="/tmp/code", scan_id="s1", triggered_by="u1", scan_name="n",
                                    skip_fingerprints=skip)
        self.assertEqual(mock_lsast.call_args.kwargs["skip_fingerprints"], skip)
