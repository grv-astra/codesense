from bson import ObjectId
from datetime import datetime, timezone
from common.db import MongoDBClient

class FindingModel:
    collection = MongoDBClient.get_database()["findings"]

    @staticmethod
    def serialize(finding):
        if not finding:
            return None

        return {
            "id": str(finding["_id"]),
            "scan_id": str(finding["scan_id"]),
            "created_by": str(finding.get("created_by", "")),
            "cwe": finding.get("cwe", ""),
            "cvss_vector": finding.get("cvss_vector", ""),
            "cvss_score": finding.get("cvss_score", ""),
            "code": finding.get("code", ""),
            "title": finding.get("title", ""),
            "description": finding.get("description", ""),
            "severity": finding.get("severity", ""),
            "file_path": finding.get("file_path", ""),
            "code_snip": finding.get("code_snip", ""),
            "security_risk": finding.get("security_risk", ""),
            "mitigation": finding.get("mitigation", ""),
            "status": finding.get("status", "open"),
            "deleted": finding.get("deleted", False),
            "approved": finding.get("approved", False),
            "reference": finding.get("reference", ""),
            "created_at": finding["created_at"].isoformat() if finding.get("created_at") else None,
        }

    @classmethod
    def insert_many(cls, findings: list[dict]):
        if not findings:
            return []

        for f in findings:
            f["scan_id"] = ObjectId(f["scan_id"]) if isinstance(f.get("scan_id"), str) else f.get("scan_id")
            f["created_by"] = ObjectId(f["created_by"]) if isinstance(f.get("created_by"), str) else f.get("created_by")
            f["created_at"] = f.get("created_at", datetime.now(timezone.utc))
            f["status"] = f.get("status", "open")
            f["deleted"] = f.get("deleted", False)
            f["approved"] = f.get("approved", False)

        result = cls.collection.insert_many(findings)
        inserted = cls.collection.find({"_id": {"$in": result.inserted_ids}})
        return [cls.serialize(doc) for doc in inserted]
    
    @classmethod
    def find_by_id(cls, finding_id: str):
        return cls.serialize(cls.collection.find_one({
            "_id": ObjectId(finding_id)
        }))
    
    @classmethod
    def find_all(cls):
        cursor = cls.collection.find({
            "deleted": False
        })
        return [cls.serialize(doc) for doc in cursor]
    
    @classmethod
    def find_all_by_scan(cls, scan_id: str):
        cursor = cls.collection.find({
            "scan_id": ObjectId(scan_id),
            "deleted": False
        })
        return [cls.serialize(doc) for doc in cursor]
    
    @classmethod
    def find_by_scan(cls, scan_id: str, page=1, limit=10):
        try:
            skip = (page - 1) * limit
            cursor = cls.collection.find({
                "scan_id": ObjectId(scan_id),
                "deleted": False
            }).skip(skip).limit(limit)
            findings = [cls.serialize(doc) for doc in cursor]

            total = cls.collection.count_documents({"scan_id": ObjectId(scan_id), "deleted": False})
            return {
                "findings": findings,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "pages": (total + limit - 1) // limit
                }
            }
        except:
            return {
                "error": "Internal Server Error"
            }

    @classmethod
    def find_by_project(cls, project_id: str):
        scan_ids = MongoDBClient.get_database()["scans"].find({"project_id": ObjectId(project_id)}, {"_id": 1})
        scan_ids = [doc["_id"] for doc in scan_ids]
        if not scan_ids:
            return []
        cursor = cls.collection.find({"scan_id": {"$in": scan_ids}, "deleted": False})
        return [cls.serialize(doc) for doc in cursor]

    @classmethod
    def soft_delete(cls, finding_id: str):
        result = cls.collection.update_one(
            {"_id": ObjectId(finding_id)},
            {"$set": {"deleted": True}}
        )
        return result.modified_count
    
    @classmethod
    def soft_delete_by_scan(cls, scan_id: str):
        result = cls.collection.update_many(
            {"scan_id": ObjectId(scan_id)},
            {"$set": {"deleted": True}}
        )
        return result.modified_count

    @classmethod
    def toggle_approved(cls, finding_id: str):
        finding = cls.collection.find_one({"_id": ObjectId(finding_id)}, {"approved": 1})
        if not finding:
            return None  # No finding found

        new_status = not finding.get("approved", False)
        result = cls.collection.update_one(
            {"_id": ObjectId(finding_id)},
            {"$set": {"approved": new_status}}
        )
        if result.modified_count != 1:
            return None

        return {"id": finding_id, "approved": new_status}

