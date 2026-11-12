from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tickets", "0008_ticketamendment_ticketcancellation"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticketcancellation",
            name="requested_by",
            field=models.ForeignKey(
                blank=True,
                help_text="Agent or admin user who submitted the refund claim.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ticket_refund_claims",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
