import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flights", "0003_agentflightinventory_publish_policies"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="agentflightinventory",
            name="seats_held",
            field=models.IntegerField(
                default=0,
                help_text="Seats temporarily held (not yet confirmed).",
            ),
        ),
        migrations.AddField(
            model_name="agentflightinventory",
            name="waitlist_count",
            field=models.IntegerField(
                default=0,
                help_text="Number of passengers currently waitlisted for this flight.",
            ),
        ),
        migrations.AddField(
            model_name="agentflightinventory",
            name="is_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Admin kill-switch. When False, inventory is hidden from all channels.",
            ),
        ),
        migrations.CreateModel(
            name="InventoryHold",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("HOLD", "Seat Hold"),
                            ("WAITLIST", "Waitlist"),
                            ("CONFIRMED", "Confirmed"),
                            ("CANCELLED", "Cancelled"),
                            ("EXPIRED", "Expired"),
                        ],
                        default="HOLD",
                        max_length=20,
                    ),
                ),
                ("seats", models.PositiveIntegerField(default=1)),
                ("contact_name", models.CharField(blank=True, default="", max_length=120)),
                ("contact_email", models.EmailField(blank=True, default="", max_length=254)),
                ("contact_mobile", models.CharField(blank=True, default="", max_length=20)),
                ("notes", models.TextField(blank=True, default="")),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                (
                    "inventory",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="holds",
                        to="flights.agentflightinventory",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inventory_holds",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
