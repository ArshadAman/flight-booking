from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


def seed_notices(apps, schema_editor):
    Notice = apps.get_model("agents", "Notice")
    if Notice.objects.exists():
        return
    Notice.objects.bulk_create(
        [
            Notice(
                category="airline",
                label="ALERT",
                title="Air India Kathmandu",
                body="Air India operations to Kathmandu suspended due to airport maintenance waivers.",
            ),
            Notice(
                category="airline",
                label="UPDATE",
                title="Indigo baggage",
                body="Indigo introduces extra bags luggage allowances for Gulf sectors starting next week.",
            ),
            Notice(
                category="finance",
                label="DEPOSIT WINDOW",
                title="Wallet deposit",
                body="Instant net banking wallet deposit service upgraded with 0% extra gateway charges.",
            ),
            Notice(
                category="finance",
                label="PROMOTION",
                title="Loyalty points",
                body="Earn 1.5% loyalty points bonus on credit card requests processed before Friday midnight.",
            ),
            Notice(
                category="contact",
                label="B2B HELPDESK",
                title="Support Desk: +91 99999-88888",
                body="Desk timings: 24/7 Hotline support",
            ),
            Notice(
                category="contact",
                label="ACCOUNT MANAGER",
                title="Anand Kumar (Sr Head)",
                body="anand.k@mytraveldeal.com",
            ),
            Notice(
                category="other",
                label="PORTAL SYSTEM",
                title="Mobile app",
                body="Dedicated B2B agent mobile ticketing application launching soon on Play Store.",
            ),
        ]
    )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("agents", "0003_supplier"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notice",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.CharField(choices=[("airline", "Airline"), ("finance", "Finance"), ("contact", "Contact"), ("other", "Other")], default="other", max_length=20)),
                ("label", models.CharField(blank=True, default="", max_length=40)),
                ("title", models.CharField(max_length=160)),
                ("body", models.TextField()),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["category", "-created_at"]},
        ),
        migrations.CreateModel(
            name="AgentCommission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.CharField(choices=[("flight", "Flight"), ("rebook", "Rebooking")], default="flight", max_length=20)),
                ("method", models.CharField(choices=[("none", "No Calculation"), ("flat", "Flat Calculation"), ("standard", "Standard Calculation"), ("simple", "Simple Calculation"), ("custom", "Custom Calculation")], default="none", max_length=20)),
                ("markup", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("agent", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="commissions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("agent", "category")}},
        ),
        migrations.RunPython(seed_notices, migrations.RunPython.noop),
    ]
