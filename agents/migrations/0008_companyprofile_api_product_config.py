from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("agents", "0007_supplier_integration_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="api_product_config",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="B2B API / B2B / B2C product toggles for distribution admin UI.",
            ),
        ),
    ]