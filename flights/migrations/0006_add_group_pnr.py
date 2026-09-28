from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flights", "0005_add_sales_closing_datetime"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentflightinventory",
            name="group_pnr",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional Group PNR (GPNR) for this inventory listing.",
                max_length=32,
            ),
        ),
    ]
