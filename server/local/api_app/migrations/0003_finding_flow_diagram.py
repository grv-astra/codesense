from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_app', '0002_finding_confidence_finding_rule_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='finding',
            name='flow_diagram',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
