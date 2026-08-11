from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from local.api_app.models.orm import APIKey
from local.api_app.models.project_models import ProjectModel


def _make_project(name="proj"):
    return ProjectModel.create({"name": name, "created_by": "admin1"})["id"]


class CreateApiKeyCommandTests(TestCase):
    def setUp(self):
        self.project_id = _make_project("proj1")

    def test_creates_exactly_one_row_and_prints_plaintext_once(self):
        out = StringIO()
        call_command("create_api_key", "--project", self.project_id, "--name", "azure-devops", stdout=out)

        self.assertEqual(APIKey.objects.filter(project_id=self.project_id).count(), 1)
        output = out.getvalue()
        self.assertIn("csk_", output)

        row = APIKey.objects.get(project_id=self.project_id)
        self.assertNotIn(row.key_hash, output)

    def test_unknown_project_errors_without_creating_a_row(self):
        self.assertRaises(
            CommandError,
            call_command,
            "create_api_key",
            "--project",
            "nonexistent",
            "--name",
            "x",
        )
        self.assertEqual(APIKey.objects.count(), 0)
