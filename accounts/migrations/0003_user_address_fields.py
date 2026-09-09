from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_created_at_user_updated_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="address_line",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="user",
            name="city",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
