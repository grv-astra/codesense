from .config import FINDING_MODEL, DB_LOCK
import logging

logger = logging.getLogger(__name__)
collection = FINDING_MODEL

def save_findings_to_db(findings):
    """Save findings to MongoDB database."""
    if not findings:
        return
    with DB_LOCK:
        try:
            collection.insert_many(findings)
        except Exception as e:
            logging.error(f"Error saving findings to database: {e}")

def get_severity_counts(scan_id):
    pipeline = [
        {"$match": {"scan_id": scan_id}},
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
    ]
    return list(collection.aggregate(pipeline))
