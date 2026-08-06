from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_app', '0006_scan_resume_fields'),
    ]

    operations = [
        migrations.RenameField(
            model_name='trialusage',
            old_name='scans_used',
            new_name='code_scans_used',
        ),
        migrations.AddField(
            model_name='trialusage',
            name='sbom_scans_used',
            field=models.IntegerField(default=0),
        ),
    ]
