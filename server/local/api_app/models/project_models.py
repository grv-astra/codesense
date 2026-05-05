# projects/models.py
from bson import ObjectId
from datetime import datetime, timezone
from common.db import MongoDBClient

class ProjectModel:
    collection = MongoDBClient.get_database()["projects"]

    @staticmethod
    def serialize(project):
        if not project:
            return None
        return {
            "id": str(project["_id"]),
            "name": project["name"],
            "preset": project.get("preset", ""),
            "description": project.get("description", ""),
            "created_by": str(project["created_by"]),
            "created_at": project["created_at"].isoformat() if project.get("created_at") else None,
            "deleted": project.get("deleted", False)
        }

    @classmethod
    def create(cls, data):
        data["created_at"] = datetime.now(timezone.utc)
        data["deleted"] = False
        result = cls.collection.insert_one(data)
        return cls.serialize(cls.collection.find_one({"_id": result.inserted_id}))

    @classmethod
    def fetch_names(cls):
        try:
            # Only fetch _id and name
            cursor = cls.collection.find(
                {"deleted": False},
                projection={ "_id": 1, "name": 1 }
            )
            
            # Return only minimal project info
            projects = [
                { "id": str(doc["_id"]), "name": doc.get("name", "") }
                for doc in cursor
            ]
            return projects

        except Exception as e:
            return { "error": "Internal Server Error" }


    @classmethod
    def find_all(cls, page=1, limit=10):
        try:
            skip = (page - 1) * limit
            cursor = cls.collection.find({"deleted": False}).skip(skip).limit(limit)
            projects =  [cls.serialize(doc) for doc in cursor]

            total = cls.collection.count_documents({"deleted": False})
            return {
                "projects": projects,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "pages": (total + limit - 1) // limit
                }
            }
        except:
            { "error": "Internal Server Error" }

    @classmethod
    def find_by_id(cls, project_id):
        return cls.serialize(cls.collection.find_one({"_id": ObjectId(project_id)}))

    @classmethod
    def update(cls, project_id, data):
        cls.collection.update_one({"_id": ObjectId(project_id)}, {"$set": data})
        return cls.find_by_id(project_id)

    @classmethod
    def soft_delete(cls, project_id):
        cls.collection.update_one({"_id": ObjectId(project_id)}, {"$set": {"deleted": True}})
        return True
