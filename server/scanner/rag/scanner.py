from concurrent.futures import ThreadPoolExecutor, as_completed
from .files import get_source_files
from .analysis import scan_single_file
from .database import save_findings_to_db
from .progress import update_progress, display_progress
from .ast_parser import analyze_folder   # <-- NEW
from .llm import get_ready_llm
from datetime import datetime, timezone
import traceback
import logging
import os

logger = logging.getLogger(__name__)


def scan_folder(folder_path, scan_id, triggered_by, scan_name):
    """
    1. Perform AST analysis (LOC, functions, languages)
    2. Save metrics to scan document
    3. Perform vulnerability scan in parallel
    """

    # ----------------------------------------------------------
    # STEP 1 — AST ANALYSIS BEFORE STARTING THE SCAN
    # ----------------------------------------------------------
    try:
        logger.info("Running AST analysis before vulnerability scan...")
        ast_metrics = analyze_folder(folder_path)

        update_progress(
            scan_id=scan_id,
            metrics=ast_metrics  # store total_loc, total_functions, languages
        )

        logger.info(
            f"AST Completed → LOC: {ast_metrics['total_loc']} | "
            f"Functions: {ast_metrics['total_functions']} | "
            f"Languages: {ast_metrics['languages']}"
        )

    except Exception as e:
        logger.error(f"AST Analysis failed: {e}\n{traceback.format_exc()}")
        update_progress(scan_id=scan_id, error=str(e))
        return []

    # ----------------------------------------------------------
    # STEP 2 — GATHER SOURCE FILES
    # ----------------------------------------------------------
    source_files = get_source_files(folder_path)
    total_files = len(source_files)

    if not source_files:
        logger.warning(f"No source code files found in {folder_path}")
        update_progress(
            scan_id=scan_id,
            total=0,
            scanned=0,
            findings=0,
            status="completed",
            end_time=datetime.now(timezone.utc)
        )
        return []

    update_progress(scan_id=scan_id, total=total_files, scanned=0, status="in_progress")
    logger.info(f"Starting parallel scan of {total_files} files for project: {scan_name or 'Unknown'}")
    get_ready_llm()

    # ----------------------------------------------------------
    # STEP 3 — PARALLEL FILE VULNERABILITY SCAN
    # ----------------------------------------------------------
    all_findings = []
    failed_files = []
    completed_files = 0

    max_workers = int(os.getenv("SCAN_MAX_WORKERS", "4"))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(scan_single_file, file_path, scan_id, triggered_by): file_path
            for file_path in source_files
        }

        for future in as_completed(futures):
            file_path = futures[future]

            try:
                findings = future.result()
                if findings:
                    save_findings_to_db(findings)
                    all_findings.extend(findings)

            except Exception as e:
                failed_files.append(file_path)
                logger.error(f"Error scanning file {file_path}: {e}\n{traceback.format_exc()}")

            finally:
                completed_files += 1
                update_progress(
                    scan_id=scan_id,
                    scanned=completed_files,
                    findings=len(all_findings)
                )
                display_progress(scan_id)

    # ----------------------------------------------------------
    # STEP 4 — SCAN COMPLETE
    # ----------------------------------------------------------
    update_progress(
        scan_id=scan_id,
        findings=len(all_findings),
        status="completed",
        end_time=datetime.now(timezone.utc)
    )

    logger.info(
        f"Scan completed! {len(all_findings)} findings across {total_files} files."
    )

    if failed_files:
        logger.warning(f"{len(failed_files)} files failed during scan.")

    return all_findings
