from local.auth_app.models.user_model import UserModel
from local.auth_app.models.orm import User
from local.auth_app.models.permission_model import PermissionModel
from local.auth_app.utils.password import hash_password


def is_setup_needed() -> bool:
    """True until at least one Admin account exists."""
    return not User.objects.filter(role__iexact="admin", deleted=False).exists()


def _seed_default_permissions():
    keys = PermissionModel.get_all_permission_keys()
    for role in ("user", "manager"):
        if not PermissionModel.get_permissions_for_role(role):
            PermissionModel.set_permissions_for_role(role, {k: False for k in keys})


def create_initial_admin(email: str, password: str, name: str, company: str = None):
    if not is_setup_needed():
        raise RuntimeError("Setup already completed: an admin account already exists.")
    admin = UserModel.create_user(
        email=email, hashed_password=hash_password(password),
        name=name, company=company, role="Admin",
    )
    _seed_default_permissions()
    # Start the offline license clock at first-run setup.
    from licenses.services.offline_license import get_state
    get_state()
    return admin
