# scanner/models/license_model.py
from bson import ObjectId
from datetime import datetime
from common.db import MongoDBClient

class LicenseModel:
    collection = MongoDBClient.get_database()["licenses"]

    @staticmethod
    def serialize(license_doc):
        if not license_doc:
            return None
        return {
            "id": str(license_doc["_id"]),
            "client_id": license_doc["client_id"],
            "license_key": license_doc["license_key"],
            "type": license_doc.get("type", "standard"),
            "features": license_doc.get("features", {}),
            "valid_from": license_doc.get("valid_from"),
            "valid_until": license_doc.get("valid_until"),
            "status": license_doc.get("status", "inactive"),
            "issued_to": license_doc.get("issued_to", ""),
            "created_at": license_doc.get("created_at"),
            "updated_at": license_doc.get("updated_at"),
        }

    @classmethod
    def upsert(cls, license_data: dict):
        """
        Insert or update license for a client.
        """
        license_data["updated_at"] = datetime.utcnow()
        cls.collection.update_one(
            {"client_id": license_data["client_id"]},
            {"$set": license_data, "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True,
        )
        return cls.find_by_client(license_data["client_id"])

    @classmethod
    def find_by_client(cls, client_id: str):
        license_doc = cls.collection.find_one({"client_id": client_id})
        return cls.serialize(license_doc)

    @classmethod
    def delete(cls, client_id: str):
        result = cls.collection.delete_one({"client_id": client_id})
        return result.deleted_count == 1
