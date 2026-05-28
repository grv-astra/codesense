# local/auth_app/models/user_model.py

from bson import ObjectId
from datetime import datetime, timezone
from common.db import MongoDBClient
from pymongo.errors import PyMongoError

class UserModel:
    collection = MongoDBClient.get_database()["users"]

    @staticmethod
    def serialize_user(user):
        if not user:
            return None
        return {
            "id": str(user.get("_id")),
            "email": user.get("email"),
            "name": user.get("name"),
            "company": user.get("company"),
            "role": user.get("role", "User"),
            "deleted": user.get("deleted", True),
            "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
            "updated_at": user["updated_at"].isoformat() if user.get("updated_at") else None,
        }

    @staticmethod
    def find_all(page=1, limit=10, role="user"):
        try:
            skip = (page - 1) * limit

            if role == "manager":
                # Exclude admin users
                users_cursor = UserModel.collection.find(
                    {"deleted": False, "role": {"$ne": "admin"}}
                ).skip(skip).limit(limit)
                total = UserModel.collection.count_documents({"deleted": False, "role": {"$ne": "admin"}})
            else:
                users_cursor = UserModel.collection.find(
                    {"deleted": False}
                ).skip(skip).limit(limit)
                total = UserModel.collection.count_documents({"deleted": False})

            users = [UserModel.serialize_user(u) for u in users_cursor]

            return {
                "users": users,
                "pagination": {
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "pages": (total + limit - 1) // limit
                }
            }

        except PyMongoError as e:
            return {
                "users": [],
                "pagination": {
                    "total": 0,
                    "page": page,
                    "limit": limit,
                    "pages": 0
                },
                "error": "Database query failed. Please try again later."
            }

        except Exception as e:
            return {
                "users": [],
                "pagination": {
                    "total": 0,
                    "page": page,
                    "limit": limit,
                    "pages": 0
                },
                "error": "Unexpected error occurred. Please contact support."
            }
    
    @staticmethod
    def find_by_email(email: str):
        user = UserModel.collection.find_one({"email": email, "deleted": False })
        if not user:
            return None
        return user

    @staticmethod
    def find_by_id(user_id: str):
        try:
            user = UserModel.collection.find_one({"_id": ObjectId(user_id), "deleted": False})
            return UserModel.serialize_user(user)
        except Exception:
            return None

    @staticmethod
    def find_raw_by_id(user_id: str):
        try:
            return UserModel.collection.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None

    @staticmethod
    def create_user(email: str, hashed_password: str, name: str, company: str = None, role: str = "User", deleted: bool = False):
        now = datetime.now(timezone.utc)
        user_data = {
            "email": email,
            "password": hashed_password,
            "name": name,
            "company": company,
            "role": role,
            "deleted": deleted,
            "created_at": now,
            "updated_at": now,
        }
        result = UserModel.collection.insert_one(user_data)
        return UserModel.find_by_id(result.inserted_id)

    @staticmethod
    def update_user(user_id: str, update_data: dict):
        update_data["updated_at"] = datetime.now(timezone.utc)
        UserModel.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        return UserModel.find_by_id(user_id)

    @staticmethod
    def delete_user(user_id: str):
        return UserModel.collection.delete_one({"_id": ObjectId(user_id)})

    @staticmethod
    def exists(email: str) -> bool:
        return UserModel.collection.count_documents({"email": email}) > 0
