from .progress import update_progress
from .ast_parser import analyze_folder
from .lsast_scanner import lsast_scan_folder
from datetime import datetime, timezone
import traceback
import logging

logger = logging.getLogger(__name__)


def scan_folder(folder_path, scan_id, triggered_by, scan_name,
                 skip_fingerprints=frozenset(), cancel_event=None):
    """Run a vulnerability scan via the LSAST engine (the only engine).

    LSAST = Semgrep detects -> LLM verifier classifies each finding TP/FP ->
    fusion suppresses false positives and never silently drops a high-severity
    finding. This function owns the scan lifecycle (AST metrics -> in_progress ->
    completed/cancelled/interrupted) and returns the visible (non-suppressed)
    findings.

    ``skip_fingerprints``/``cancel_event`` support resuming an interrupted scan
    -- see scanner/rag/resume.py and local/api_app/views/scan_views.py.
    """
    # ----------------------------------------------------------
    # STEP 1 — AST ANALYSIS (LOC / functions / languages for the dashboard)
    # ----------------------------------------------------------
    try:
        ast_metrics = analyze_folder(folder_path)
        total_files = ast_metrics.get("total_files", 0)
        update_progress(scan_id=scan_id, metrics=ast_metrics, total=total_files)
        logger.info(
            "AST Completed → LOC: %s | Functions: %s | Languages: %s",
            ast_metrics.get("total_loc"),
            ast_metrics.get("total_functions"),
            ast_metrics.get("languages"),
        )
    except Exception as e:
        logger.error("AST Analysis failed: %s\n%s", e, traceback.format_exc())
        # The extracted source is retained (see scan_views.py) regardless of
        # this failure, so resuming is always safe -- worst case it just
        # retries AST analysis, no worse than a fresh scan. "failed" is
        # reserved for pre-extraction failures where there's nothing to resume.
        update_progress(
            scan_id=scan_id,
            error=str(e),
            status="interrupted",
            end_time=datetime.now(timezone.utc),
        )
        return []

    # ----------------------------------------------------------
    # STEP 2 — LSAST DETECTION + VERIFICATION
    # ----------------------------------------------------------
    update_progress(scan_id=scan_id, status="in_progress")
    visible, _filtered = lsast_scan_folder(
        folder_path, scan_id, triggered_by,
        skip_fingerprints=skip_fingerprints, cancel_event=cancel_event,
    )

    # ----------------------------------------------------------
    # STEP 3 — SCAN COMPLETE (or cancelled mid-way)
    # ----------------------------------------------------------
    if cancel_event is not None and cancel_event.is_set():
        update_progress(
            scan_id=scan_id,
            findings=len(visible),
            scanned=total_files,
            status="cancelled",
            end_time=datetime.now(timezone.utc),
        )
        logger.info("LSAST scan cancelled: %d findings persisted before stop for %s",
                    len(visible), scan_name or "Unknown")
        return visible

    update_progress(
        scan_id=scan_id,
        findings=len(visible),
        scanned=total_files,   # no per-file progress; on completion all files are done
        status="completed",
        end_time=datetime.now(timezone.utc),
    )
    # Consume a trial slot only on successful completion (no-op when trial mode is
    # off). Failures/cancellation return before reaching here, so they never count.
    try:
        from licenses.services import trial
        trial.record_completion()
    except Exception as exc:  # noqa: BLE001 — trial accounting must never sink a scan
        logger.warning("trial.record_completion failed: %s", exc)
    logger.info("LSAST scan completed: %d findings for %s", len(visible), scan_name or "Unknown")
    return visible
