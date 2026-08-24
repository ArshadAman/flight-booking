from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0006_ticket_agent_cancellation_reason_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="booking_channel",
            field=models.CharField(
                blank=True,
                choices=[("B2C", "B2C"), ("B2B", "B2B")],
                default="B2C",
                help_text="Commercial channel categorization for admin reporting (B2B vs B2C).",
                max_length=8,
            ),
        ),
    ]
