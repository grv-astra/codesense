import shutil
from datetime import datetime, timezone
from pathlib import Path
from django.db.models import Q
from local.api_app.models.orm import SbomScan, SbomFinding, SbomLicenseFinding

_FINDING_FIELDS = ["scan_id", "package_name", "package_version", "package_type",
                   "cve_id", "severity", "description", "cvss", "fix_versions", "created_at"]
_LICENSE_FIELDS = ["scan_id", "package_name", "package_version", "package_type",
                   "license", "decision", "locations", "created_at"]


def _iso(dt):
    return dt.isoformat() if dt else None


class SbomModel:
    @staticmethod
    def serialize(scan):
        if scan is None:
            return None
        return {
            "id": str(scan.id),
            "project_id": str(scan.project_id),
            "scan_name": scan.scan_name or "",
            "status": scan.status or "queued",
            "created_at": _iso(scan.created_at),
            "triggered_by": str(scan.triggered_by or ""),
            "dependencies_scanned": scan.dependencies_scanned,
            "vulnerabilities": scan.vulnerabilities,
            "severity_counts": scan.severity_counts,
            "ecosystems": scan.ecosystems,
            "sbom_format": scan.sbom_format or "syft-json",
            "end_time": _iso(scan.end_time),
        }

    @staticmethod
    def finding_serialize(f):
        if f is None:
            return None
        cvss = [
            {
                "type": c.get("type"), "version": c.get("version"), "vector": c.get("vector"),
                "base_score": c.get("metrics", {}).get("baseScore"),
                "exploitability_score": c.get("metrics", {}).get("exploitabilityScore"),
                "impact_score": c.get("metrics", {}).get("impactScore"),
            }
            for c in (f.cvss or [])
        ]
        return {
            "id": str(f.id),
            "scan_id": str(f.scan_id),
            "package": {"name": f.package_name or "", "version": f.package_version or "",
                        "type": f.package_type or ""},
            "cve_id": f.cve_id or "",
            "severity": (f.severity or "").lower(),
            "description": f.description or "",
            "cvss": cvss,
            "cvss_score": (f.cvss[0].get("metrics", {}).get("baseScore") if f.cvss else None),
            "fix_versions": f.fix_versions or [],
            "created_at": _iso(f.created_at),
        }

    @staticmethod
    def license_finding_serialize(f):
        if f is None:
            return None
        lic = f.license or {}
        return {
            "id": str(f.id),
            "scan_id": str(f.scan_id),
            "package": {"name": f.package_name or "", "version": f.package_version or "",
                        "type": f.package_type or ""},
            "license": {
                "id": lic.get("id"), "reference": lic.get("reference"),
                "osi_approved": lic.get("osi_approved"),
                "risk_category": lic.get("risk_category"), "risk_level": lic.get("risk_level"),
            },
            "decision": f.decision or "",
            "locations": f.locations or [],
            "created_at": _iso(f.created_at),
        }

    @classmethod
    def create(cls, data: dict):
        scan = SbomScan.objects.create(
            project_id=str(data["project_id"]),
            scan_name=data.get("scan_name", ""),
            triggered_by=str(data.get("triggered_by", "")),
            status="queued",
            created_at=datetime.now(timezone.utc),
            deleted=False,
            dependencies_scanned=0, vulnerabilities=0,
            severity_counts={"critical": 0, "high": 0, "medium": 0, "low": 0, "negligible": 0},
            ecosystems=[], sbom_format="syft-json", end_time=None,
        )
        return cls.find_by_id(scan.id)

    @classmethod
    def update_status(cls, scan_id: str, new_status: str):
        SbomScan.objects.filter(id=scan_id).update(status=new_status)
        return cls.find_by_id(scan_id)

    @classmethod
    def update_progress(cls, scan_id: str, **kwargs):
        allowed = ["dependencies_scanned", "vulnerabilities", "severity_counts",
                   "ecosystems", "status", "end_time"]
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if fields:
            SbomScan.objects.filter(id=scan_id).update(**fields)
        return cls.find_by_id(scan_id)

    @classmethod
    def update_scan_fields(cls, scan_id: str, fields: dict):
        """Persist extra scan metadata (sbom_signing, sbom_artifact, license_policy)."""
        allowed = ["sbom_signing", "sbom_artifact", "license_policy"]
        data = {k: v for k, v in fields.items() if k in allowed}
        if data:
            SbomScan.objects.filter(id=scan_id).update(**data)

    @classmethod
    def insert_findings(cls, findings: list[dict]):
        objs = []
        for f in findings:
            data = {k: f[k] for k in _FINDING_FIELDS if k in f}
            data["scan_id"] = str(data.get("scan_id", ""))
            data.setdefault("created_at", datetime.now(timezone.utc))
            objs.append(SbomFinding(**data))
        SbomFinding.objects.bulk_create(objs)

    @classmethod
    def insert_license_findings(cls, findings: list[dict]):
        objs = []
        for f in findings:
            data = {k: f[k] for k in _LICENSE_FIELDS if k in f}
            data["scan_id"] = str(data.get("scan_id", ""))
            data.setdefault("created_at", datetime.now(timezone.utc))
            objs.append(SbomLicenseFinding(**data))
        SbomLicenseFinding.objects.bulk_create(objs)

    @classmethod
    def find_by_id(cls, scan_id: str):
        return cls.serialize(SbomScan.objects.filter(id=scan_id).first())

    @classmethod
    def find_by_project(cls, project_id: str, page=1, limit=10, search=""):
        skip = (page - 1) * limit
        qs = SbomScan.objects.filter(project_id=project_id)
        s = (search or "").strip()
        if s:
            qs = qs.filter(Q(scan_name__icontains=s) | Q(status__icontains=s))
        total = qs.count()
        rows = list(qs[skip:skip + limit])
        return {
            "scans": [cls.serialize(s) for s in rows],
            "pagination": {"total": total, "page": page, "limit": limit,
                           "pages": (total + limit - 1) // limit if limit else 0},
        }

    @classmethod
    def delete_scan(cls, scan_id: str):
        try:
            deleted, _ = SbomScan.objects.filter(id=scan_id).delete()
            SbomFinding.objects.filter(scan_id=scan_id).delete()
            SbomLicenseFinding.objects.filter(scan_id=scan_id).delete()
            # sbom_pipeline.py writes SBOM/grype/grant reports + the cosign signature
            # bundle to output/<scan_id>/ -- remove it too, or every deleted scan
            # leaks those artifacts on disk forever.
            shutil.rmtree(Path("output") / str(scan_id), ignore_errors=True)
            return bool(deleted)
        except Exception:
            return False

    @classmethod
    def find_sbom_findings_all(cls, scan_id: str):
        return [cls.finding_serialize(f) for f in SbomFinding.objects.filter(scan_id=scan_id)]

    @classmethod
    def find_by_sbom_scan(cls, scan_id: str, page=1, limit=10, search=""):
        skip = (page - 1) * limit
        qs = SbomFinding.objects.filter(scan_id=scan_id)
        s = (search or "").strip()
        if s:
            qs = qs.filter(
                Q(package_name__icontains=s) | Q(package_version__icontains=s)
                | Q(package_type__icontains=s) | Q(cve_id__icontains=s)
                | Q(severity__icontains=s) | Q(description__icontains=s)
            )
        total = qs.count()
        rows = list(qs[skip:skip + limit])
        return {
            "findings": [cls.finding_serialize(f) for f in rows],
            "pagination": {"total": total, "page": page, "limit": limit,
                           "pages": (total + limit - 1) // limit if limit else 0},
        }

    @classmethod
    def find_license_findings_all(cls, scan_id: str):
        return [cls.license_finding_serialize(f)
                for f in SbomLicenseFinding.objects.filter(scan_id=scan_id)]

    @classmethod
    def find_license_findings_by_scan(cls, scan_id: str, page=1, limit=10, search=""):
        skip = (page - 1) * limit
        qs = SbomLicenseFinding.objects.filter(scan_id=scan_id)
        s = (search or "").strip()
        if s:
            qs = qs.filter(
                Q(package_name__icontains=s) | Q(package_version__icontains=s)
                | Q(package_type__icontains=s) | Q(decision__icontains=s)
            )
        total = qs.count()
        rows = list(qs[skip:skip + limit])
        return {
            "licenses": [cls.license_finding_serialize(f) for f in rows],
            "pagination": {"total": total, "page": page, "limit": limit,
                           "pages": (total + limit - 1) // limit if limit else 0},
        }

    @classmethod
    def find_license_by_risk(cls, scan_id: str, risk_level: str):
        rows = SbomLicenseFinding.objects.filter(scan_id=scan_id, license__risk_level=risk_level)
        return [cls.license_finding_serialize(f) for f in rows]
