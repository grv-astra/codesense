from datetime import datetime, timedelta, timezone

from local.auth_app.permissions.decorators import require_authentication
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.db import MongoDBClient


def _safe_collection_exists(db, name: str) -> bool:
    return name in db.list_collection_names()


def _severity_defaults() -> dict:
    return {"critical": 0, "high": 0, "medium": 0, "low": 0}


class DashboardView(APIView):
    @require_authentication()
    def get(self, request):
        try:
            db = MongoDBClient.get_database()
            collections = set(db.list_collection_names())

            total_users = db.users.count_documents({"deleted": False}) if "users" in collections else 0
            total_projects = db.projects.count_documents({"deleted": False}) if "projects" in collections else 0
            total_scans = db.scans.count_documents({"deleted": False}) if "scans" in collections else 0
            total_findings = db.findings.count_documents({"deleted": False}) if "findings" in collections else 0

            system_status = self._get_system_status(db) if "scans" in collections else {"counts": {}, "total_scans": 0}
            severity_counts = self._get_severity_counts(db) if "findings" in collections else _severity_defaults()
            language_distribution = self._get_language_distribution(db) if "scans" in collections else []
            findings_trend = self._get_findings_trend(db) if "findings" in collections else []
            top_cwe = self._get_top_cwe(db) if "findings" in collections else []
            scans_by_project = self._get_scans_by_project(db) if "scans" in collections and "projects" in collections else []
            scan_distribution = self._get_scan_distribution(db) if "scans" in collections else []

            response_data = {
                "top_counts": {
                    "users": total_users,
                    "projects": total_projects,
                    "scans": total_scans,
                    "findings": total_findings,
                },
                "system_status": system_status,
                "count_by_severity": severity_counts,
                "language_distribution": language_distribution,
                "findings_trend": findings_trend,
                "top_cwe": top_cwe,
                "scans_by_project": scans_by_project,
                "scan_distribution": scan_distribution,
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def _get_system_status(self, db):
        pipeline = [
            {"$match": {"deleted": False}},
            {
                "$facet": {
                    "status_counts": [
                        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
                    ],
                    "total_scans": [{"$count": "total"}],
                }
            },
            {
                "$project": {
                    "counts": {
                        "$arrayToObject": {
                            "$map": {
                                "input": "$status_counts",
                                "as": "item",
                                "in": {"k": "$$item._id", "v": "$$item.count"},
                            }
                        }
                    },
                    "total_scans": {"$ifNull": [{"$arrayElemAt": ["$total_scans.total", 0]}, 0]},
                }
            },
        ]

        result = list(db.scans.aggregate(pipeline))
        return result[0] if result else {"counts": {}, "total_scans": 0}

    def _get_severity_counts(self, db):
        pipeline = [
            {"$match": {"deleted": False}},
            {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
        ]

        counts = _severity_defaults()
        for item in db.findings.aggregate(pipeline):
            severity = str(item.get("_id", "")).lower()
            if severity in counts:
                counts[severity] = item.get("count", 0)
        return counts

    def _get_language_distribution(self, db):
        pipeline = [
            {"$match": {"deleted": False, "metrics.languages.0": {"$exists": True}}},
            {"$unwind": "$metrics.languages"},
            {
                "$group": {
                    "_id": "$metrics.languages",
                    "vulnerabilities": {"$sum": {"$ifNull": ["$findings", 0]}},
                    "scans": {"$sum": 1},
                }
            },
            {"$sort": {"vulnerabilities": -1, "scans": -1, "_id": 1}},
            {"$limit": 8},
            {
                "$project": {
                    "_id": 0,
                    "language": "$_id",
                    "vulnerabilities": 1,
                    "scans": 1,
                }
            },
        ]
        return list(db.scans.aggregate(pipeline))

    def _get_findings_trend(self, db):
        start_date = datetime.now(timezone.utc) - timedelta(days=6)
        pipeline = [
            {"$match": {"deleted": False, "created_at": {"$gte": start_date}}},
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                        "severity": "$severity",
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.date": 1}},
        ]

        grouped = {}
        for item in db.findings.aggregate(pipeline):
            date_key = item["_id"]["date"]
            severity = str(item["_id"].get("severity", "")).lower()
            if date_key not in grouped:
                grouped[date_key] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            if severity in grouped[date_key]:
                grouped[date_key][severity] = item["count"]

        trend = []
        for offset in range(7):
            day = (start_date + timedelta(days=offset)).date()
            key = day.strftime("%Y-%m-%d")
            values = grouped.get(key, {"critical": 0, "high": 0, "medium": 0, "low": 0})
            total = values["critical"] + values["high"] + values["medium"] + values["low"]
            trend.append(
                {
                    "date": day.strftime("%b %d"),
                    **values,
                    "total": total,
                }
            )
        return trend

    def _get_top_cwe(self, db):
        pipeline = [
            {"$match": {"deleted": False, "cwe": {"$nin": ["", None]}}},
            {"$group": {"_id": "$cwe", "count": {"$sum": 1}}},
            {"$sort": {"count": -1, "_id": 1}},
            {"$limit": 10},
        ]

        results = []
        for item in db.findings.aggregate(pipeline):
            cwe_value = str(item.get("_id", ""))
            parts = cwe_value.split(":", 1)
            cwe_id = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else cwe_id
            results.append({"id": cwe_id, "name": name, "count": item.get("count", 0)})
        return results

    def _get_scans_by_project(self, db):
        pipeline = [
            {"$match": {"deleted": False}},
            {
                "$lookup": {
                    "from": "projects",
                    "localField": "project_id",
                    "foreignField": "_id",
                    "as": "project",
                }
            },
            {"$unwind": {"path": "$project", "preserveNullAndEmptyArrays": True}},
            {
                "$group": {
                    "_id": "$project_id",
                    "project": {"$first": {"$ifNull": ["$project.name", "Unknown Project"]}},
                    "scans": {"$sum": 1},
                    "findings": {"$sum": {"$ifNull": ["$findings", 0]}},
                    "critical": {
                        "$sum": {
                            "$cond": [{"$gte": [{"$ifNull": ["$findings", 0]}, 1]}, 0, 0]
                        }
                    },
                }
            },
            {"$sort": {"findings": -1, "scans": -1, "project": 1}},
            {"$limit": 10},
        ]

        base_rows = list(db.scans.aggregate(pipeline))
        if not base_rows or not _safe_collection_exists(db, "findings"):
            return [
                {
                    "project": row.get("project", "Unknown Project"),
                    "scans": row.get("scans", 0),
                    "findings": row.get("findings", 0),
                    "critical": 0,
                }
                for row in base_rows
            ]

        critical_pipeline = [
            {"$match": {"deleted": False, "severity": "critical"}},
            {
                "$lookup": {
                    "from": "scans",
                    "localField": "scan_id",
                    "foreignField": "_id",
                    "as": "scan",
                }
            },
            {"$unwind": {"path": "$scan", "preserveNullAndEmptyArrays": False}},
            {"$match": {"scan.deleted": False}},
            {"$group": {"_id": "$scan.project_id", "critical": {"$sum": 1}}},
        ]
        critical_map = {str(item["_id"]): item["critical"] for item in db.findings.aggregate(critical_pipeline)}

        return [
            {
                "project": row.get("project", "Unknown Project"),
                "scans": row.get("scans", 0),
                "findings": row.get("findings", 0),
                "critical": critical_map.get(str(row.get("_id")), 0),
            }
            for row in base_rows
        ]

    def _get_scan_distribution(self, db):
        pipeline = [
            {"$match": {"deleted": False}},
            {
                "$group": {
                    "_id": {"$ifNull": ["$source", "zip"]},
                    "value": {"$sum": 1},
                }
            },
            {"$sort": {"value": -1, "_id": 1}},
        ]

        palette = {
            "zip": "#8b5cf6",
            "github": "#ec4899",
        }
        labels = {
            "zip": "ZIP Upload",
            "github": "GitHub Repo",
        }

        results = []
        for item in db.scans.aggregate(pipeline):
            source = str(item.get("_id", "zip"))
            results.append(
                {
                    "name": labels.get(source, source.title()),
                    "value": item.get("value", 0),
                    "color": palette.get(source, "#bf0000"),
                }
            )
        return results
