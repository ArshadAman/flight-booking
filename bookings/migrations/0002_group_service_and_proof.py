from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="groupbooking",
            name="payment_proof_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="groupbooking",
            name="payment_proof_data",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.CreateModel(
            name="GroupServiceCase",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("case_id", models.CharField(blank=True, max_length=50, unique=True)),
                ("kind", models.CharField(choices=[("REBOOK", "Rebooking"), ("REFUND", "Refund")], max_length=10)),
                ("step", models.PositiveSmallIntegerField(default=1)),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("SUBMITTED", "Submitted"), ("DONE", "Done")], default="OPEN", max_length=20)),
                ("payload", models.JSONField(blank=True, default=dict)),
                (
                    "booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_cases",
                        to="bookings.groupbooking",
                    ),
                ),
            ],
            options={"abstract": False},
        ),
    ]
