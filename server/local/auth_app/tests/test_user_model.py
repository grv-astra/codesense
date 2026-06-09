from django.test import TestCase
from local.auth_app.models.user_model import UserModel


class UserModelTests(TestCase):
    def test_create_returns_serialized_user(self):
        user = UserModel.create_user(
            email="a@x.com", hashed_password="h", name="Ann", company="X", role="Admin"
        )
        self.assertEqual(user["email"], "a@x.com")
        self.assertEqual(user["role"], "admin")  # stored lowercase regardless of input casing
        self.assertFalse(user["deleted"])
        self.assertIn("id", user)
        self.assertIsNotNone(user["created_at"])

    def test_find_by_email_returns_raw_doc_with_password_and_id(self):
        UserModel.create_user(email="b@x.com", hashed_password="secret", name="B")
        raw = UserModel.find_by_email("b@x.com")
        self.assertEqual(raw["password"], "secret")
        self.assertEqual(raw["email"], "b@x.com")
        self.assertIn("_id", raw)
        self.assertEqual(raw["role"], "user")  # default role, stored lowercase

    def test_find_by_email_excludes_deleted(self):
        UserModel.create_user(email="c@x.com", hashed_password="h", name="C", deleted=True)
        self.assertIsNone(UserModel.find_by_email("c@x.com"))

    def test_find_by_id_serializes_and_find_raw_by_id_is_raw(self):
        created = UserModel.create_user(email="d@x.com", hashed_password="h", name="D")
        uid = created["id"]
        self.assertEqual(UserModel.find_by_id(uid)["email"], "d@x.com")
        self.assertEqual(UserModel.find_raw_by_id(uid)["password"], "h")
        self.assertIsNone(UserModel.find_by_id("nonexistent"))

    def test_update_user_sets_fields_and_updated_at(self):
        created = UserModel.create_user(email="e@x.com", hashed_password="h", name="E")
        updated = UserModel.update_user(created["id"], {"name": "E2"})
        self.assertEqual(updated["name"], "E2")

    def test_find_all_pagination_and_manager_excludes_admin(self):
        UserModel.create_user(email="m@x.com", hashed_password="h", name="M", role="manager")
        UserModel.create_user(email="ad@x.com", hashed_password="h", name="Ad", role="admin")
        as_manager = UserModel.find_all(page=1, limit=10, role="manager")
        emails = [u["email"] for u in as_manager["users"]]
        self.assertIn("m@x.com", emails)
        self.assertNotIn("ad@x.com", emails)
        self.assertEqual(as_manager["pagination"]["page"], 1)

    def test_exists_counts_regardless_of_deleted(self):
        UserModel.create_user(email="f@x.com", hashed_password="h", name="F", deleted=True)
        self.assertTrue(UserModel.exists("f@x.com"))
        self.assertFalse(UserModel.exists("none@x.com"))

    def test_delete_user_hard_deletes(self):
        created = UserModel.create_user(email="g@x.com", hashed_password="h", name="G")
        UserModel.delete_user(created["id"])
        self.assertIsNone(UserModel.find_raw_by_id(created["id"]))

    def test_find_protected_returns_raw_docs(self):
        UserModel.create_user(email="p@x.com", hashed_password="h", name="P", role="admin")
        rows = UserModel.find_protected(["admin", "manager", "user"])
        self.assertEqual(rows[0]["email"], "p@x.com")
        self.assertIn("_id", rows[0])
