from django.test import TestCase
from local.api_app.models.project_models import ProjectModel


class ProjectModelTests(TestCase):
    def test_create_serializes_with_string_ids(self):
        p = ProjectModel.create({"name": "P1", "description": "d", "created_by": "user123"})
        self.assertEqual(p["name"], "P1")
        self.assertEqual(p["created_by"], "user123")
        self.assertFalse(p["deleted"])
        self.assertIsNotNone(p["created_at"])

    def test_find_by_id_and_fetch_names(self):
        p = ProjectModel.create({"name": "P2", "created_by": "u"})
        self.assertEqual(ProjectModel.find_by_id(p["id"])["name"], "P2")
        names = ProjectModel.fetch_names()
        self.assertIn({"id": p["id"], "name": "P2"}, names)

    def test_find_all_excludes_deleted_and_paginates(self):
        ProjectModel.create({"name": "A", "created_by": "u"})
        d = ProjectModel.create({"name": "B", "created_by": "u"})
        ProjectModel.soft_delete(d["id"])
        result = ProjectModel.find_all(page=1, limit=10)
        names = [p["name"] for p in result["projects"]]
        self.assertIn("A", names)
        self.assertNotIn("B", names)
        self.assertEqual(result["pagination"]["total"], 1)

    def test_update(self):
        p = ProjectModel.create({"name": "C", "created_by": "u"})
        updated = ProjectModel.update(p["id"], {"name": "C2"})
        self.assertEqual(updated["name"], "C2")
