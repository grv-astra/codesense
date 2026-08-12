# local/auth_app/management/commands/create_admin_user.py

import os
import secrets
import string

from django.conf import settings
from django.core.management.base import BaseCommand
from local.auth_app.models.user_model import UserModel
from local.auth_app.utils.password import hash_password
from local.auth_app.utils.account_integrity import register_user

_PASSWORD_SYMBOLS = "!@$%*?&"  # matches validate_strong_password's accepted set
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + _PASSWORD_SYMBOLS


def _generate_password(length: int = 20) -> str:
    while True:
        candidate = "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))
        if (
            any(c.isupper() for c in candidate)
            and any(c.islower() for c in candidate)
            and any(c.isdigit() for c in candidate)
            and any(c in _PASSWORD_SYMBOLS for c in candidate)
        ):
            return candidate


class Command(BaseCommand):
    help = "Create the initial admin user if none exists yet (there's no sign-up UI otherwise)"

    def handle(self, *args, **kwargs):
        default_email = os.getenv("CODESENSE_ADMIN_EMAIL", "admin@codesense.dev")
        default_username = "admin"
        default_company = "CodeSense"
        default_role = "admin"

        existing_user = UserModel.find_by_email(default_email)
        if existing_user:
            register_user(existing_user, created_by="bootstrap")
            self.stdout.write(self.style.WARNING("Default admin already exists."))
            return

        password = os.getenv("CODESENSE_ADMIN_PASSWORD")
        generated = password is None
        if generated:
            # Persisted so a restart before anyone has logged in doesn't hand
            # out a second, different password nobody captured the first time.
            password_file = settings.DATA_DIR / "initial_admin_password"
            if password_file.exists():
                password = password_file.read_text(encoding="utf-8").strip()
            else:
                password = _generate_password()
                password_file.write_text(password, encoding="utf-8")

        hashed = hash_password(password)
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

        if generated:
            self.stdout.write(self.style.SUCCESS(
                f"Default admin created: {default_email} / {password}\n"
                f"No CODESENSE_ADMIN_PASSWORD was set, so this was generated and saved to "
                f"{password_file} -- change it after first login."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(f"Default admin created: {default_email}"))
