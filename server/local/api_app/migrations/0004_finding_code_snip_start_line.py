from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api_app', '0003_finding_flow_diagram'),
    ]

    operations = [
        migrations.AddField(
            model_name='finding',
            name='code_snip_start_line',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
