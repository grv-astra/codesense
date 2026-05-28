from datetime import datetime, timezone
from local.api_app.models.orm import Project


def _iso(dt):
    return dt.isoformat() if dt else None


class ProjectModel:
    @staticmethod
    def serialize(project):
        if project is None:
            return None
        return {
            "id": str(project.id),
            "name": project.name,
            "preset": project.preset or "",
            "description": project.description or "",
            "created_by": str(project.created_by),
            "created_at": _iso(project.created_at),
            "deleted": project.deleted,
        }

    @classmethod
    def create(cls, data):
        project = Project.objects.create(
            name=data["name"],
            preset=data.get("preset", ""),
            description=data.get("description", ""),
            created_by=str(data.get("created_by", "")),
            created_at=datetime.now(timezone.utc),
            deleted=False,
        )
        return cls.serialize(project)

    @classmethod
    def fetch_names(cls):
        return [
            {"id": str(p.id), "name": p.name}
            for p in Project.objects.filter(deleted=False).only("id", "name")
        ]

    @classmethod
    def find_all(cls, page=1, limit=10):
        skip = (page - 1) * limit
        qs = Project.objects.filter(deleted=False)
        total = qs.count()
        rows = list(qs.order_by("created_at")[skip:skip + limit])
        return {
            "projects": [cls.serialize(p) for p in rows],
            "pagination": {
                "total": total, "page": page, "limit": limit,
                "pages": (total + limit - 1) // limit if limit else 0,
            },
        }

    @classmethod
    def find_by_id(cls, project_id):
        return cls.serialize(Project.objects.filter(id=project_id).first())

    @classmethod
    def update(cls, project_id, data):
        Project.objects.filter(id=project_id).update(**data)
        return cls.find_by_id(project_id)

    @classmethod
    def soft_delete(cls, project_id):
        Project.objects.filter(id=project_id).update(deleted=True)
        return True
