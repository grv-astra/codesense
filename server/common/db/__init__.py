# common/db/__init__.py

from pymongo import MongoClient, errors
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class MongoDBClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            try:
                mongo_uri = getattr(settings, "MONGO_URI", "mongodb://localhost:27017")
                client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
                client.admin.command("ping")
                cls._instance = client
                logger.info("MongoDB connection established.")
            except errors.ServerSelectionTimeoutError as e:
                logger.error(f"MongoDB connection failed: {e}")
                raise ConnectionError("Could not connect to MongoDB server.")
        return cls._instance

    @classmethod
    def get_database(cls, db_name=None):
        client = cls()
        db_name = db_name or getattr(settings, "MONGO_DB_NAME", "test")
        return client[db_name]
