from datetime import datetime, timezone
from local.auth_app.models.orm import User


def _iso(dt):
    return dt.isoformat() if dt else None


class UserModel:
    @staticmethod
    def serialize_user(user):
        """Accepts an ORM User or a raw dict; returns the public user dict."""
        if user is None:
            return None
        if isinstance(user, dict):
            return {
                "id": str(user.get("_id") or user.get("id")),
                "email": user.get("email"),
                "name": user.get("name"),
                "company": user.get("company"),
                "role": user.get("role", "User"),
                "deleted": user.get("deleted", True),
                "created_at": _iso(user.get("created_at")),
                "updated_at": _iso(user.get("updated_at")),
            }
        return {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "company": user.company,
            "role": user.role or "User",
            "deleted": user.deleted,
            "created_at": _iso(user.created_at),
            "updated_at": _iso(user.updated_at),
        }

    @staticmethod
    def _raw(user):
        """Raw-doc shape that auth/account-integrity code expects (incl. password, _id)."""
        if user is None:
            return None
        return {
            "_id": str(user.id),
            "email": user.email,
            "password": user.password,
            "name": user.name,
            "company": user.company,
            "role": user.role or "User",
            "deleted": user.deleted,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    @staticmethod
    def find_all(page=1, limit=10, role="user"):
        skip = (page - 1) * limit
        qs = User.objects.filter(deleted=False)
        if role == "manager":
            qs = qs.exclude(role="admin")
        total = qs.count()
        rows = list(qs.order_by("created_at")[skip:skip + limit])
        return {
            "users": [UserModel.serialize_user(u) for u in rows],
            "pagination": {
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit if limit else 0,
            },
        }

    @staticmethod
    def find_by_email(email: str):
        user = User.objects.filter(email=email, deleted=False).first()
        return UserModel._raw(user)

    @staticmethod
    def find_by_id(user_id: str):
        return UserModel.serialize_user(
            User.objects.filter(id=user_id, deleted=False).first()
        )

    @staticmethod
    def find_raw_by_id(user_id: str):
        return UserModel._raw(User.objects.filter(id=user_id).first())

    @staticmethod
    def create_user(email, hashed_password, name, company=None, role="User", deleted=False):
        now = datetime.now(timezone.utc)
        user = User.objects.create(
            email=email, password=hashed_password, name=name, company=company,
            role=role, deleted=deleted, created_at=now, updated_at=now,
        )
        return UserModel.find_by_id(user.id)

    @staticmethod
    def update_user(user_id: str, update_data: dict):
        fields = dict(update_data)
        fields["updated_at"] = datetime.now(timezone.utc)
        User.objects.filter(id=user_id).update(**fields)
        return UserModel.find_by_id(user_id)

    @staticmethod
    def delete_user(user_id: str):
        return User.objects.filter(id=user_id).delete()

    @staticmethod
    def exists(email: str) -> bool:
        return User.objects.filter(email=email).exists()

    @staticmethod
    def find_protected(roles):
        rows = User.objects.filter(role__in=list(roles), deleted=False)
        return [UserModel._raw(u) for u in rows]
