from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0006_supplier_portal_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplier",
            name="integration_config",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]