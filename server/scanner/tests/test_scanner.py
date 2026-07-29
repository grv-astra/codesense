from unittest import mock

from django.test import SimpleTestCase

import scanner.rag.scanner as scanner_module


class ScanFolderTests(SimpleTestCase):
    """scan_folder is the LSAST entrypoint (the only engine) + scan lifecycle."""

    @mock.patch("licenses.services.trial.record_completion")
    @mock.patch.object(scanner_module, "lsast_scan_folder",
                       return_value=(["finding"], ["filtered"]))
    @mock.patch.object(scanner_module, "update_progress")
    @mock.patch.object(scanner_module, "analyze_folder",
                       return_value={"total_loc": 10, "total_functions": 2, "languages": ["python"]})
    def test_runs_lsast_and_marks_scan_completed(self, mock_ast, mock_update, mock_lsast, mock_trial):
        result = scanner_module.scan_folder("/x", "s1", "user-1", "Scan #1")
        # returns the visible findings from the LSAST pipeline
        self.assertEqual(result, ["finding"])
        # AST metrics recorded, LSAST detection invoked
        mock_ast.assert_called_once_with("/x")
        mock_lsast.assert_called_once_with("/x", "s1", "user-1")
        # a completed-status update happened with the visible findings count
        completed = [c for c in mock_update.call_args_list if c.kwargs.get("status") == "completed"]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].kwargs.get("findings"), 1)
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

    def test_no_legacy_engine_remains(self):
        # The legacy engine + SCAN_ENGINE flag were removed; LSAST is the only path.
        self.assertFalse(hasattr(scanner_module, "_legacy_scan_folder"))
        self.assertFalse(hasattr(scanner_module, "_lsast_scan_folder"))
