from datetime import datetime, timezone
from local.api_app.models.orm import Scan, Finding


def _iso(dt):
    return dt.isoformat() if dt else None


class ScanModel:
    @staticmethod
    def serialize(scan):
        if scan is None:
            return None
        return {
            "id": str(scan.id),
            "project_id": str(scan.project_id),
            "scan_name": scan.scan_name or "",
            "status": scan.status or "queued",
            "source": scan.source or "zip",
            "created_at": _iso(scan.created_at),
            "triggered_by": str(scan.triggered_by or ""),
            "total_files": scan.total_files,
            "files_scanned": scan.files_scanned,
            "findings": scan.findings,
            "error": scan.error or "",
            "end_time": _iso(scan.end_time),
            "metrics": scan.metrics or {"total_functions": 0, "total_loc": 0, "languages": []},
        }

    @classmethod
    def create(cls, data: dict):
        scan = Scan.objects.create(
            project_id=str(data["project_id"]),
            scan_name=data.get("scan_name", ""),
            triggered_by=str(data.get("triggered_by", "")),
            source=data.get("source", "zip"),
            status="queued",
            created_at=datetime.now(timezone.utc),
            deleted=False,
            total_files=0, files_scanned=0, findings=0, end_time=None,
        )
        return cls.find_by_id(scan.id)

    @classmethod
    def update_status(cls, scan_id: str, new_status: str):
        Scan.objects.filter(id=scan_id).update(status=new_status)
        return cls.find_by_id(scan_id)

    @classmethod
    def update_progress(cls, scan_id: str, **kwargs):
        allowed = ["total_files", "files_scanned", "findings", "end_time", "status"]
        fields = {k: kwargs[k] for k in allowed if k in kwargs}
        if fields:
            Scan.objects.filter(id=scan_id).update(**fields)
        return cls.find_by_id(scan_id)

    @classmethod
    def find_by_id(cls, scan_id: str):
        return cls.serialize(Scan.objects.filter(id=scan_id).first())

    @classmethod
    def find_by_project(cls, project_id: str, page=1, limit=10):
        skip = (page - 1) * limit
        qs = Scan.objects.filter(project_id=project_id)
        total = qs.count()
        rows = list(qs.order_by("created_at")[skip:skip + limit])
        return {
            "scans": [cls.serialize(s) for s in rows],
            "pagination": {
                "total": total, "page": page, "limit": limit,
                "pages": (total + limit - 1) // limit if limit else 0,
            },
        }

    @classmethod
    def delete_scan(cls, scan_id: str):
        try:
            deleted, _ = Scan.objects.filter(id=scan_id).delete()
            Finding.objects.filter(scan_id=scan_id).delete()
            return bool(deleted)
        except Exception:
            return False
