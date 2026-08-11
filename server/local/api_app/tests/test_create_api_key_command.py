from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from local.api_app.models.orm import APIKey


class CreateApiKeyCommandTests(TestCase):
    def test_creates_exactly_one_row_and_prints_plaintext_once(self):
        out = StringIO()
        call_command("create_api_key", "--project", "proj1", "--name", "azure-devops", stdout=out)

        self.assertEqual(APIKey.objects.filter(project_id="proj1").count(), 1)
        output = out.getvalue()
        self.assertIn("csk_", output)

        row = APIKey.objects.get(project_id="proj1")
        self.assertNotIn(row.key_hash, output)
