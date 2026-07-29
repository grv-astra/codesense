"""Reset the trial scan counter (admin/operator action, run via `railway run`).

    python manage.py reset_trial            # back to 0
    python manage.py reset_trial --to 1     # set a specific used count
"""
from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from local.api_app.models.orm import TrialUsage


class Command(BaseCommand):
    help = "Reset (or set) the trial scan-usage counter."

    def add_arguments(self, parser):
        parser.add_argument("--to", type=int, default=0,
                            help="Value to set scans_used to (default 0).")

    def handle(self, *args, **opts):
        value = max(0, opts["to"])
        row = TrialUsage.objects.first()
        if row is None:
            TrialUsage.objects.create(scans_used=value, updated_at=datetime.now(timezone.utc))
        else:
            TrialUsage.objects.filter(id=row.id).update(
                scans_used=value, updated_at=datetime.now(timezone.utc))
        self.stdout.write(self.style.SUCCESS(f"Trial scans_used set to {value}."))
