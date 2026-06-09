from django.test import TestCase
from rest_framework.exceptions import ValidationError

from local.auth_app.services.setup import is_setup_needed, create_initial_admin
from local.auth_app.models.permission_model import PermissionModel


class SetupServiceTests(TestCase):
    def test_setup_needed_when_no_admin(self):
        self.assertTrue(is_setup_needed())

    def test_create_initial_admin_rejects_weak_password(self):
        with self.assertRaises(ValidationError):
            create_initial_admin("weak@x.com", "weak", "Weak Admin")
        # no admin should have been created
        self.assertTrue(is_setup_needed())

    def test_create_initial_admin_seeds_admin_and_blocks_second_run(self):
        admin = create_initial_admin("root@x.com", "Str0ng!Pass1", "Root")
        self.assertEqual(admin["role"], "admin")  # roles are stored lowercase
        self.assertFalse(is_setup_needed())
        # default role permissions seeded
        self.assertEqual(PermissionModel.get_permissions_for_role("user"),
                         {k: False for k in PermissionModel.get_all_permission_keys()})
        with self.assertRaises(RuntimeError):
            create_initial_admin("second@x.com", "Str0ng!Pass1", "Second")
