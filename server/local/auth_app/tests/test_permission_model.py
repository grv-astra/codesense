from django.test import TestCase
from local.auth_app.models.permission_model import PermissionModel


class PermissionModelTests(TestCase):
    def test_admin_role_grants_all_keys(self):
        perms = PermissionModel.get_permissions_for_role("Admin")
        self.assertEqual(set(perms.keys()), set(PermissionModel.get_all_permission_keys()))
        self.assertTrue(all(perms.values()))

    def test_set_then_get_roundtrip_and_upsert(self):
        PermissionModel.set_permissions_for_role("manager", {"view_projects": True})
        self.assertEqual(PermissionModel.get_permissions_for_role("manager"), {"view_projects": True})
        PermissionModel.set_permissions_for_role("manager", {"view_projects": False})
        self.assertEqual(PermissionModel.get_permissions_for_role("manager"), {"view_projects": False})

    def test_unknown_role_returns_empty(self):
        self.assertEqual(PermissionModel.get_permissions_for_role("ghost"), {})
