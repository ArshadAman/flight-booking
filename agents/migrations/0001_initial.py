import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryRestriction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "scope",
                    models.CharField(
                        choices=[("AIRLINE", "Airline"), ("ROUTE", "Route")],
                        max_length=20,
                    ),
                ),
                ("airline_code", models.CharField(blank=True, default="", max_length=10)),
                ("airline_name", models.CharField(blank=True, default="", max_length=100)),
                ("origin", models.CharField(blank=True, default="", max_length=3)),
                ("destination", models.CharField(blank=True, default="", max_length=3)),
                ("is_blocked", models.BooleanField(default=True)),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                (
                    "agent",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional agent scope. Null = global restriction.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inventory_restrictions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Inventory Restriction",
                "verbose_name_plural": "Inventory Restrictions",
                "ordering": ["-created_at"],
            },
        ),
    ]
