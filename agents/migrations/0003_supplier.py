from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0002_agentauditlog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(blank=True, default="", max_length=20, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("contact_name", models.CharField(blank=True, default="", max_length=120)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("phone", models.CharField(blank=True, default="", max_length=20)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("denied", "Denied")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("inventory_count", models.PositiveIntegerField(default=0)),
                ("notes", models.CharField(blank=True, default="", max_length=255)),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="supplier_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Supplier",
                "verbose_name_plural": "Suppliers",
                "ordering": ["-created_at"],
            },
        ),
    ]
