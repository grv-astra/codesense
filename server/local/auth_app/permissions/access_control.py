from local.auth_app.models.permission_model import PermissionModel

def has_permission(user: dict, permission: str) -> bool:
    role = (user.get("role") or "").lower()
    if not role:
        return False

    if role == "admin":
        return True  # Admin bypass

    role_permissions = PermissionModel.get_permissions_for_role(role)
    return role_permissions.get(permission, False)
