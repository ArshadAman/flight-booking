from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0005_companyprofile_discount_invoicesetting_markuprule_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="supplier",
            name="portal_user",
            field=models.OneToOneField(
                blank=True,
                help_text="Login account for the supplier self-service portal.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="supplier_portal",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]