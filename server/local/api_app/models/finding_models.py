from datetime import datetime, timezone
from django.db.models import Q
from local.api_app.models.orm import Finding, Scan

_FIELDS = [
    "scan_id", "created_by", "cwe", "cvss_vector", "cvss_score", "code", "title",
    "description", "severity", "file_path", "code_snip", "security_risk",
    "mitigation", "status", "deleted", "approved", "reference", "created_at",
    "rule_id", "confidence", "verifier_reason", "flow_diagram", "code_snip_start_line",
]


def _iso(dt):
    return dt.isoformat() if dt else None


class FindingModel:
    @staticmethod
    def serialize(finding):
        if finding is None:
            return None
        return {
            "id": str(finding.id),
            "scan_id": str(finding.scan_id),
            "created_by": str(finding.created_by or ""),
            "cwe": finding.cwe or "",
            "cvss_vector": finding.cvss_vector or "",
            "cvss_score": finding.cvss_score or "",
            "code": finding.code or "",
            "title": finding.title or "",
            "description": finding.description or "",
            "severity": finding.severity or "",
            "file_path": finding.file_path or "",
            "code_snip": finding.code_snip or "",
            "security_risk": finding.security_risk or "",
            "mitigation": finding.mitigation or "",
            "status": finding.status or "open",
            "deleted": finding.deleted,
            "approved": finding.approved,
            "reference": finding.reference or "",
            "created_at": _iso(finding.created_at),
            "rule_id": finding.rule_id or "",
            "confidence": finding.confidence,        # float | None (None on pre-W7 rows)
            "verifier_reason": finding.verifier_reason or "",
            "flow_diagram": finding.flow_diagram or [],
            "code_snip_start_line": finding.code_snip_start_line,   # int | None (None on pre-existing rows)
        }

    @classmethod
    def insert_many(cls, findings: list[dict]):
        if not findings:
            return []
        objs = []
        for f in findings:
            data = {k: f[k] for k in _FIELDS if k in f}  # drop unknown keys (lines, affected, ...)
            data["scan_id"] = str(data.get("scan_id", ""))
            data["created_by"] = str(data.get("created_by", ""))
            data.setdefault("created_at", datetime.now(timezone.utc))
            data.setdefault("status", "open")
            data.setdefault("deleted", False)
            data.setdefault("approved", False)
            objs.append(Finding(**data))
        created = Finding.objects.bulk_create(objs)
        return [cls.serialize(o) for o in created]

    @classmethod
    def find_by_id(cls, finding_id: str):
        return cls.serialize(Finding.objects.filter(id=finding_id).first())

    @classmethod
    def find_all(cls):
        return [cls.serialize(f) for f in Finding.objects.filter(deleted=False)]

    @classmethod
    def find_all_by_scan(cls, scan_id: str):
        return [cls.serialize(f) for f in Finding.objects.filter(scan_id=scan_id, deleted=False)]

    @classmethod
    def find_by_scan(cls, scan_id: str, page=1, limit=10, search=""):
        skip = (page - 1) * limit
        qs = Finding.objects.filter(scan_id=scan_id, deleted=False)
        s = (search or "").strip()
        if s:
            qs = qs.filter(
                Q(title__icontains=s) | Q(description__icontains=s)
                | Q(cwe__icontains=s) | Q(severity__icontains=s)
                | Q(file_path__icontains=s) | Q(security_risk__icontains=s)
                | Q(mitigation__icontains=s) | Q(status__icontains=s)
                | Q(code__icontains=s)
            )
        total = qs.count()
        rows = list(qs[skip:skip + limit])
        return {
            "findings": [cls.serialize(f) for f in rows],
            "pagination": {
                "total": total, "page": page, "limit": limit,
                "pages": (total + limit - 1) // limit if limit else 0,
            },
        }

    @classmethod
    def find_by_project(cls, project_id: str):
        scan_ids = list(Scan.objects.filter(project_id=project_id).values_list("id", flat=True))
        if not scan_ids:
            return []
        rows = Finding.objects.filter(scan_id__in=scan_ids, deleted=False)
        return [cls.serialize(f) for f in rows]

    @classmethod
    def soft_delete(cls, finding_id: str):
        return Finding.objects.filter(id=finding_id).update(deleted=True)

    @classmethod
    def soft_delete_by_scan(cls, scan_id: str):
        return Finding.objects.filter(scan_id=scan_id).update(deleted=True)

    @classmethod
    def toggle_approved(cls, finding_id: str):
        finding = Finding.objects.filter(id=finding_id).first()
        if not finding:
            return None
        finding.approved = not finding.approved
        finding.save(update_fields=["approved"])
        return {"id": finding_id, "approved": finding.approved}
