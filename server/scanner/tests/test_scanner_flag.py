import os
from unittest import mock

from django.test import SimpleTestCase

import scanner.rag.scanner as scanner_module


class ScannerFeatureFlagRoutingTests(SimpleTestCase):
    @mock.patch.object(scanner_module, "_lsast_scan_folder", return_value=["v"])
    @mock.patch.object(scanner_module, "_legacy_scan_folder")
    def test_lsast_engine_routes_to_lsast(self, mock_legacy, mock_lsast):
        with mock.patch.dict(os.environ, {"SCAN_ENGINE": "lsast"}, clear=False):
            result = scanner_module.scan_folder("/x", "s1", "user-1", "Scan #1")
        mock_lsast.assert_called_once()
        mock_legacy.assert_not_called()
        self.assertEqual(result, ["v"])

    @mock.patch.object(scanner_module, "_lsast_scan_folder")
    @mock.patch.object(scanner_module, "_legacy_scan_folder", return_value=[])
    def test_legacy_engine_routes_to_legacy(self, mock_legacy, mock_lsast):
        with mock.patch.dict(os.environ, {"SCAN_ENGINE": "legacy"}, clear=False):
            scanner_module.scan_folder("/x", "s1", "user-1", "Scan #1")
        mock_legacy.assert_called_once()
        mock_lsast.assert_not_called()

    @mock.patch.object(scanner_module, "_lsast_scan_folder")
    @mock.patch.object(scanner_module, "_legacy_scan_folder", return_value=[])
    def test_default_engine_is_legacy(self, mock_legacy, mock_lsast):
        with mock.patch.dict(os.environ, {"SCAN_ENGINE": ""}, clear=False):
            scanner_module.scan_folder("/x", "s1", "user-1", "Scan #1")
        mock_legacy.assert_called_once()
        mock_lsast.assert_not_called()


class LsastLifecycleWrapperTests(SimpleTestCase):
    @mock.patch.object(scanner_module, "lsast_scan_folder", return_value=(["finding"], ["filtered"]))
    @mock.patch.object(scanner_module, "update_progress")
    @mock.patch.object(scanner_module, "analyze_folder", return_value={"total_loc": 10, "total_functions": 2, "languages": ["python"]})
    def test_lsast_wrapper_marks_scan_completed(self, mock_ast, mock_update, mock_lsast):
        result = scanner_module._lsast_scan_folder("/x", "s1", "user-1", "Scan #1")
        # returns the visible findings
        self.assertEqual(result, ["finding"])
        # AST metrics were recorded
        mock_ast.assert_called_once_with("/x")
        # a completed-status update happened with the visible findings count
        completed_calls = [c for c in mock_update.call_args_list
                           if c.kwargs.get("status") == "completed"]
        self.assertEqual(len(completed_calls), 1)
        self.assertEqual(completed_calls[0].kwargs.get("findings"), 1)

    @mock.patch.object(scanner_module, "lsast_scan_folder")
    @mock.patch.object(scanner_module, "update_progress")
    @mock.patch.object(scanner_module, "analyze_folder", side_effect=RuntimeError("ast boom"))
    def test_lsast_wrapper_records_error_and_returns_empty_on_ast_failure(self, mock_ast, mock_update, mock_lsast):
        result = scanner_module._lsast_scan_folder("/x", "s1", "user-1", "Scan #1")
        self.assertEqual(result, [])
        mock_lsast.assert_not_called()
        error_calls = [c for c in mock_update.call_args_list if c.kwargs.get("error")]
        self.assertTrue(error_calls)
