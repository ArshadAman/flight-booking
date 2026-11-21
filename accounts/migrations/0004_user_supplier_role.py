from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_address_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("CUSTOMER", "Customer"),
                    ("AGENT", "Agent"),
                    ("ADMIN", "Admin"),
                    ("SUPPLIER", "Supplier"),
                ],
                default="CUSTOMER",
                max_length=20,
            ),
        ),
    ]