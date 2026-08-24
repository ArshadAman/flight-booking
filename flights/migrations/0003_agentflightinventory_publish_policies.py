from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flights", "0002_agentflightinventory_segments"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentflightinventory",
            name="is_published",
            field=models.BooleanField(
                default=True,
                help_text="When True, inventory appears on For Sale and in flight search.",
            ),
        ),
        migrations.AddField(
            model_name="agentflightinventory",
            name="apis_required",
            field=models.BooleanField(
                default=False,
                help_text="Whether passport/API passenger details are required for booking.",
            ),
        ),
        migrations.AddField(
            model_name="agentflightinventory",
            name="policies",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Cancellation / change / refund policy text for this inventory.",
                null=True,
            ),
        ),
    ]
