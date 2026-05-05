from datetime import datetime, timezone
from bson import ObjectId
from common.db import MongoDBClient

SCAN_COLLECTION = MongoDBClient.get_database()["scans"]


def update_progress(
    scan_id,
    scanned=None,
    total=None,
    status=None,
    end_time=None,
    findings=None,
    error=None,
    metrics=None
):
    """Update scan progress + AST metrics in MongoDB scan document."""

    update_fields = {"last_updated": datetime.now(timezone.utc)}

    if scanned is not None:
        update_fields["files_scanned"] = scanned

    if total is not None:
        update_fields["total_files"] = total

    if status is not None:
        update_fields["status"] = status

    if end_time is not None:
        update_fields["end_time"] = end_time

    if findings is not None:
        update_fields["findings"] = findings

    if error is not None:
        update_fields["error"] = error

    # --- NEW: AST Metrics ---
    if metrics is not None:
        update_fields["metrics"] = metrics

    SCAN_COLLECTION.update_one(
        {"_id": ObjectId(scan_id)},
        {"$set": update_fields}
    )


def get_scan_progress(scan_id):
    """Fetch scan progress + AST metrics from MongoDB."""
    scan = SCAN_COLLECTION.find_one(
        {"_id": ObjectId(scan_id)},
        {
            "scan_name": 1,
            "status": 1,
            "total_files": 1,
            "files_scanned": 1,
            "findings": 1,
            "created_at": 1,
            "last_updated": 1,
            "end_time": 1,
            "error": 1,
            "metrics": 1          # <-- NEW
        }
    )

    if not scan:
        return None

    progress = {
        "project_name": scan.get("scan_name", "Unknown"),
        "status": scan.get("status", "unknown"),
        "start_time": scan.get("created_at"),
        "end_time": scan.get("end_time"),
        "total": scan.get("total_files", 0),
        "scanned": scan.get("files_scanned", 0),
        "findings": scan.get("findings", 0),
        "error": scan.get("error"),
        "metrics": scan.get("metrics", {})
    }

    progress["percentage"] = (
        int((progress["scanned"] / progress["total"]) * 100)
        if progress["total"] else 0
    )

    return progress


def display_progress(scan_id):
    """Pretty-print scan progress including AST metrics."""
    progress = get_scan_progress(scan_id)
    if not progress:
        print("No progress found for given scan ID.")
        return

    print("\n" + "=" * 50)
    print("SCAN PROGRESS")
    print("=" * 50)
    print(f"Project          : {progress['project_name']}")
    print(f"Status           : {progress['status'].upper()}")
    print(f"Start Time       : {progress['start_time']}")

    if progress["status"] == "completed":
        print(f"End Time         : {progress['end_time']}")

    print(f"Total Files      : {progress['total']}")
    print(f"Files Scanned    : {progress['scanned']}")
    print(f"Files Remaining  : {progress['total'] - progress['scanned']}")
    print(f"Completed        : {progress['percentage']}%")
    print(f"Findings         : {progress['findings']}")

    if progress.get("error"):
        print(f"⚠️ Error         : {progress['error']}")

    # --- NEW: AST Metrics Display ---
    metrics = progress.get("metrics", {})

    if metrics:
        print("\n--- AST METRICS ---")
        print(f"Total LOC        : {metrics.get('total_loc', 'N/A')}")
        print(f"Functions        : {metrics.get('total_functions', 'N/A')}")
        print(f"Languages        : {', '.join(metrics.get('languages', [])) if metrics.get('languages') else 'N/A'}")

    print("=" * 50 + "\n")
