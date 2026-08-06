"""Reset the trial scan counters (admin/operator action, run via `railway run`).

    python manage.py reset_trial                  # both counters back to 0
    python manage.py reset_trial --to 1            # both counters set to 1
    python manage.py reset_trial --type code --to 0  # only the code counter
"""
from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from local.api_app.models.orm import TrialUsage

_FIELDS = {"code": "code_scans_used", "sbom": "sbom_scans_used"}


class Command(BaseCommand):
    help = "Reset (or set) the trial scan-usage counter(s)."

    def add_arguments(self, parser):
        parser.add_argument("--to", type=int, default=0,
                            help="Value to set the counter(s) to (default 0).")
        parser.add_argument("--type", choices=["code", "sbom", "both"], default="both",
                            help="Which counter to reset (default both).")

    def handle(self, *args, **opts):
        value = max(0, opts["to"])
        fields = [_FIELDS[opts["type"]]] if opts["type"] != "both" else list(_FIELDS.values())
        update = {f: value for f in fields}
        update["updated_at"] = datetime.now(timezone.utc)

        row = TrialUsage.objects.first()
        if row is None:
            TrialUsage.objects.create(**update)
        else:
            TrialUsage.objects.filter(id=row.id).update(**update)
        self.stdout.write(self.style.SUCCESS(f"Trial counters set: {', '.join(f'{f}={value}' for f in fields)}."))
