from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0004_inventory_hold_waitlist'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentflightinventory',
            name='sales_closing_datetime',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Optional cutoff datetime — sales stop at this time even if seats are available.',
            ),
        ),
    ]
