from datetime import datetime, timezone
from local.auth_app.models.orm import RolePermission


class PermissionModel:
    @staticmethod
    def get_permissions_for_role(role: str) -> dict:
        if (role or "").lower() == "admin":
            return {key: True for key in PermissionModel.get_all_permission_keys()}
        row = RolePermission.objects.filter(role=role).first()
        return row.permissions if row else {}

    @staticmethod
    def set_permissions_for_role(role: str, permissions: dict):
        RolePermission.objects.update_or_create(
            role=role,
            defaults={"permissions": permissions, "updated_at": datetime.now(timezone.utc)},
        )

    @staticmethod
    def get_all_permission_keys() -> list:
        return [
            "create_project", "delete_project", "update_project", "view_projects",
            "view_scans", "create_scan", "update_scan", "delete_scan",
            "view_findings", "validate_finding", "delete_finding",
            "create_report", "update_report", "delete_report", "view_reports",
        ]
