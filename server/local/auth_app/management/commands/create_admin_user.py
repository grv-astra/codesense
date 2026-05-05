# local/auth_app/management/commands/create_admin_user.py

from django.core.management.base import BaseCommand
from local.auth_app.models.user_model import UserModel
from local.auth_app.utils.password import hash_password
from local.auth_app.utils.account_integrity import register_user

class Command(BaseCommand):
    help = "Create a default admin user"

    def handle(self, *args, **kwargs):
        default_email = "admin@codesense.dev"
        default_password = "Admin@123"
        default_username = "admin"
        default_company = "CodeSense"
        default_role = "admin"

        existing_user = UserModel.find_by_email(default_email)
        if existing_user:
            register_user(existing_user, created_by="bootstrap")
            self.stdout.write(self.style.WARNING("Default admin already exists."))
        else:
            hashed = hash_password(default_password)
            UserModel.create_user(
                email=default_email,
                hashed_password=hashed,
                name=default_username,
                company=default_company,
                role=default_role
            )
            db_user = UserModel.find_by_email(default_email)
            if db_user:
                register_user(db_user, created_by="bootstrap")
            self.stdout.write(self.style.SUCCESS("Default admin created successfully."))
