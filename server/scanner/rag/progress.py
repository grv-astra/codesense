from datetime import datetime, timezone
from local.api_app.models.orm import Scan


def update_progress(scan_id, scanned=None, total=None, status=None,
                    end_time=None, findings=None, error=None, metrics=None):
    """Update scan progress + AST metrics on the SQLite Scan row."""
    fields = {"last_updated": datetime.now(timezone.utc)}
    if scanned is not None:
        fields["files_scanned"] = scanned
    if total is not None:
        fields["total_files"] = total
    if status is not None:
        fields["status"] = status
    if end_time is not None:
        fields["end_time"] = end_time
    if findings is not None:
        fields["findings"] = findings
    if error is not None:
        fields["error"] = error
    if metrics is not None:
        fields["metrics"] = metrics
    Scan.objects.filter(id=scan_id).update(**fields)


def get_scan_progress(scan_id):
    scan = Scan.objects.filter(id=scan_id).first()
    if not scan:
        return None
    progress = {
        "project_name": scan.scan_name or "Unknown",
        "status": scan.status or "unknown",
        "start_time": scan.created_at,
        "end_time": scan.end_time,
        "total": scan.total_files or 0,
        "scanned": scan.files_scanned or 0,
        "findings": scan.findings or 0,
        "error": scan.error,
        "metrics": scan.metrics or {},
    }
    progress["percentage"] = (
        int((progress["scanned"] / progress["total"]) * 100) if progress["total"] else 0
    )
    return progress


def display_progress(scan_id):
    progress = get_scan_progress(scan_id)
    if not progress:
        print("No progress found for given scan ID.")
        return
    print("\n" + "=" * 50)
    print("SCAN PROGRESS")
    print("=" * 50)
    print(f"Project          : {progress['project_name']}")
    print(f"Status           : {progress['status'].upper()}")
    print(f"Total Files      : {progress['total']}")
    print(f"Files Scanned    : {progress['scanned']}")
    print(f"Completed        : {progress['percentage']}%")
    print(f"Findings         : {progress['findings']}")
    if progress.get("error"):
        print(f"Error            : {progress['error']}")
    print("=" * 50 + "\n")
