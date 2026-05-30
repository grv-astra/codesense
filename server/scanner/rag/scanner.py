from .progress import update_progress
from .ast_parser import analyze_folder
from .lsast_scanner import lsast_scan_folder
from datetime import datetime, timezone
import traceback
import logging

logger = logging.getLogger(__name__)


def scan_folder(folder_path, scan_id, triggered_by, scan_name):
    """Run a vulnerability scan via the LSAST engine (the only engine).

    LSAST = Semgrep detects → LLM verifier classifies each finding TP/FP →
    fusion suppresses false positives and never silently drops a high-severity
    finding. This function owns the scan lifecycle (AST metrics → in_progress →
    completed) and returns the visible (non-suppressed) findings.
    """
    # ----------------------------------------------------------
    # STEP 1 — AST ANALYSIS (LOC / functions / languages for the dashboard)
    # ----------------------------------------------------------
    try:
        ast_metrics = analyze_folder(folder_path)
        update_progress(scan_id=scan_id, metrics=ast_metrics)
        logger.info(
            "AST Completed → LOC: %s | Functions: %s | Languages: %s",
            ast_metrics.get("total_loc"),
            ast_metrics.get("total_functions"),
            ast_metrics.get("languages"),
        )
    except Exception as e:
        logger.error("AST Analysis failed: %s\n%s", e, traceback.format_exc())
        update_progress(scan_id=scan_id, error=str(e))
        return []

    # ----------------------------------------------------------
    # STEP 2 — LSAST DETECTION + VERIFICATION
    # ----------------------------------------------------------
    update_progress(scan_id=scan_id, status="in_progress")
    visible, _filtered = lsast_scan_folder(folder_path, scan_id, triggered_by)

    # ----------------------------------------------------------
    # STEP 3 — SCAN COMPLETE
    # ----------------------------------------------------------
    update_progress(
        scan_id=scan_id,
        findings=len(visible),
        status="completed",
        end_time=datetime.now(timezone.utc),
    )
    logger.info("LSAST scan completed: %d findings for %s", len(visible), scan_name or "Unknown")
    return visible
