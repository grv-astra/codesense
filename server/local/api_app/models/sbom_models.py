from bson import ObjectId
from datetime import datetime, timezone
from common.db import MongoDBClient


class SbomModel:
    scans_collection = MongoDBClient.get_database()["sbom_scans"]
    findings_collection = MongoDBClient.get_database()["sbom_findings"]
    licenses_findings_collection = MongoDBClient.get_database()["sbom_licenses_findings"]
    
    @staticmethod
    def serialize(scan):
        if not scan:
            return None

        return {
            "id": str(scan["_id"]),
            "project_id": str(scan["project_id"]),
            "scan_name": scan.get("scan_name", ""),

            "status": scan.get("status", "queued"),

            "created_at": scan["created_at"].isoformat()
            if scan.get("created_at")
            else None,

            "triggered_by": str(scan.get("triggered_by", "")),
            "dependencies_scanned": scan.get("dependencies_scanned", 0),

            "vulnerabilities": scan.get("vulnerabilities", 0),

            "severity_counts": scan.get(
                "severity_counts",
                {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                    "negligible": 0,
                },
            ),

            "ecosystems": scan.get("ecosystems", []),

            "sbom_format": scan.get("sbom_format", "syft-json"),

            "end_time": scan["end_time"].isoformat()
            if scan.get("end_time")
            else None,
        }

    @staticmethod
    def finding_serialize(finding):
        if not finding:
            return None

        return {
            "id": str(finding.get("_id", "")),

            "scan_id": str(finding.get("scan_id", "")),

            "package": {
                "name": finding.get("package_name", ""),
                "version": finding.get("package_version", ""),
                "type": finding.get("package_type", ""),
            },

            "cve_id": finding.get("cve_id", ""),

            "severity": finding.get("severity", "").lower(),

            "description": finding.get("description", ""),

            "cvss": [
                {
                    "type": cvss.get("type"),
                    "version": cvss.get("version"),
                    "vector": cvss.get("vector"),
                    "base_score": cvss.get("metrics", {}).get("baseScore"),
                    "exploitability_score": cvss.get("metrics", {}).get("exploitabilityScore"),
                    "impact_score": cvss.get("metrics", {}).get("impactScore"),
                }
                for cvss in finding.get("cvss", [])
            ],

            # convenience field (helps frontend avoid parsing array)
            "cvss_score": (
                finding.get("cvss", [{}])[0]
                .get("metrics", {})
                .get("baseScore")
                if finding.get("cvss")
                else None
            ),

            "fix_versions": finding.get("fix_versions", []),

            "created_at": (
                finding["created_at"].isoformat()
                if finding.get("created_at")
                else None
            ),
        }
    
    @staticmethod
    def license_finding_serialize(finding):
        if not finding:
            return None

        return {
            "id": str(finding.get("_id", "")),

            "scan_id": str(finding.get("scan_id", "")),

            "package": {
                "name": finding.get("package_name", ""),
                "version": finding.get("package_version", ""),
                "type": finding.get("package_type", ""),
            },

            "license": {
                "id": finding.get("license", {}).get("id"),
                "reference": finding.get("license", {}).get("reference"),
                "osi_approved": finding.get("license", {}).get("osi_approved"),
                "risk_category": finding.get("license", {}).get("risk_category"),
                "risk_level": finding.get("license", {}).get("risk_level"),
            },

            "decision": finding.get("decision", ""),

            "locations": finding.get("locations", []),

            "created_at": (
                finding["created_at"].isoformat()
                if finding.get("created_at")
                else None
            ),
        }

    @classmethod
    def create(cls, data: dict):
        data["project_id"] = (
            ObjectId(data["project_id"])
            if isinstance(data.get("project_id"), str)
            else data["project_id"]
        )

        if "triggered_by" in data:
            data["triggered_by"] = (
                ObjectId(data["triggered_by"])
                if isinstance(data["triggered_by"], str)
                else data["triggered_by"]
            )

        data["created_at"] = datetime.now(timezone.utc)
        data["status"] = "queued"
        data["deleted"] = False

        data["dependencies_scanned"] = 0
        data["vulnerabilities"] = 0

        data["severity_counts"] = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "negligible": 0,
        }

        data["ecosystems"] = []
        data["sbom_format"] = "syft-json"

        data["end_time"] = None

        result = cls.scans_collection.insert_one(data)

        return cls.find_by_id(result.inserted_id)

    @classmethod
    def update_status(cls, scan_id: str, new_status: str):
        cls.scans_collection.update_one(
            {"_id": ObjectId(scan_id)},
            {"$set": {"status": new_status}},
        )
        return cls.find_by_id(scan_id)

    @classmethod
    def update_progress(cls, scan_id: str, **kwargs):

        allowed = [
            "dependencies_scanned",
            "vulnerabilities",
            "severity_counts",
            "ecosystems",
            "status",
            "end_time",
        ]

        update_fields = {k: v for k, v in kwargs.items() if k in allowed}

        if update_fields:
            cls.scans_collection.update_one(
                {"_id": ObjectId(scan_id)},
                {"$set": update_fields},
            )

        return cls.find_by_id(scan_id)

    @classmethod
    def find_by_id(cls, scan_id: str):
        scan = cls.scans_collection.find_one({"_id": ObjectId(scan_id)})
        return cls.serialize(scan)

    @classmethod
    def find_by_project(cls, project_id: str, page=1, limit=10):

        skip = (page - 1) * limit

        cursor = (
            cls.scans_collection
            .find({"project_id": ObjectId(project_id)})
            .skip(skip)
            .limit(limit)
        )

        scans = [cls.serialize(doc) for doc in cursor]

        total = cls.scans_collection.count_documents(
            {"project_id": ObjectId(project_id)}
        )

        return {
            "scans": scans,
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit,
            },
        }

    @classmethod
    def delete_scan(cls, scan_id: str):
        try:
            scan_result = cls.scans_collection.delete_one(
                {"_id": ObjectId(scan_id)}
            )

            cls.findings_collection.delete_many(
                {"scan_id": ObjectId(scan_id)}
            )

            return bool(scan_result.deleted_count)

        except Exception:
            return False
        
    @classmethod
    def find_sbom_findings_all(cls, scan_id: str):
        cursor = cls.findings_collection.find({
            "scan_id": ObjectId(scan_id)
        })
        return [cls.finding_serialize(doc) for doc in cursor]
    
    @classmethod
    def find_by_sbom_scan(cls, scan_id: str, page=1, limit=10):
        try:
            skip = (page - 1) * limit
            cursor = cls.findings_collection.find({
                "scan_id": ObjectId(scan_id),
            }).skip(skip).limit(limit)
            findings = [cls.finding_serialize(doc) for doc in cursor]

            total = cls.findings_collection.count_documents({"scan_id": ObjectId(scan_id)})
            return {
                "findings": findings,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "pages": (total + limit - 1) // limit
                }
            }
        except Exception as e:
            return {
                "error": "Internal Server Error"
            }
    
    @classmethod
    def find_license_findings_all(cls, scan_id: str):
        cursor = cls.licenses_findings_collection.find({
            "scan_id": ObjectId(scan_id)
        })
        return [cls.license_finding_serialize(doc) for doc in cursor]
    
    @classmethod
    def find_license_findings_by_scan(cls, scan_id: str, page=1, limit=10):
        try:
            skip = (page - 1) * limit

            cursor = cls.licenses_findings_collection.find({
                "scan_id": ObjectId(scan_id),
            }).skip(skip).limit(limit)

            licenses = [cls.license_finding_serialize(doc) for doc in cursor]

            total = cls.licenses_findings_collection.count_documents({
                "scan_id": ObjectId(scan_id)
            })

            return {
                "licenses": licenses,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "pages": (total + limit - 1) // limit
                }
            }

        except Exception:
            return {
                "error": "Internal Server Error"
            }
        
    @classmethod
    def find_license_by_risk(cls, scan_id: str, risk_level: str):
        cursor = cls.licenses_findings_collection.find({
            "scan_id": ObjectId(scan_id),
            "license.risk_level": risk_level
        })

        return [cls.license_finding_serialize(doc) for doc in cursor]