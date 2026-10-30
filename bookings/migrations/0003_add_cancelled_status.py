from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0002_group_service_and_proof"),
    ]

    operations = [
        migrations.AlterField(
            model_name="groupbooking",
            name="status",
            field=models.CharField(
                choices=[
                    ("NEW_REQUEST", "New Request"),
                    ("FARE_QUOTED", "Fare Quoted"),
                    ("NEGOTIATION", "Negotiation"),
                    ("ACCEPTED", "Accepted"),
                    ("PAYMENT_PENDING", "Payment Pending"),
                    ("PARTIALLY_PAID", "Partially Paid"),
                    ("PAID", "Paid"),
                    ("PNR_CREATED", "PNR Created"),
                    ("NAME_SUBMITTED", "Name Submitted"),
                    ("TICKETED", "Ticketed"),
                    ("COMPLETED", "Completed"),
                    ("CANCELLED", "Cancelled"),
                ],
                default="NEW_REQUEST",
                max_length=50,
            ),
        ),
    ]
