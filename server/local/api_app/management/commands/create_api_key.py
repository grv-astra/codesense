from django.core.management.base import BaseCommand

from local.api_app.models.apikey_model import ApiKeyModel


class Command(BaseCommand):
    help = "Create a project-scoped CI API key. Prints the plaintext key once — it is never stored or shown again."

    def add_arguments(self, parser):
        parser.add_argument("--project", required=True, help="Project ID the key is scoped to")
        parser.add_argument("--name", required=True, help="Human label for the key, e.g. 'azure-devops-prod'")

    def handle(self, *args, **options):
        row, plaintext = ApiKeyModel.create(
            project_id=options["project"],
            name=options["name"],
            created_by="cli",
        )
        self.stdout.write(self.style.SUCCESS(f"Created API key '{row.name}' for project {row.project_id}:"))
        self.stdout.write(plaintext)
        self.stdout.write(self.style.WARNING("Store this now — it will not be shown again."))
