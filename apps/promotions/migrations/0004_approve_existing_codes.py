from django.db import migrations


def approve_existing_codes(apps, schema_editor):
    """Les codes deja en ligne avant la validation admin restent actifs."""
    PromoCode = apps.get_model("promotions", "PromoCode")
    PromoCode.objects.filter(status="pending").update(status="approved")


class Migration(migrations.Migration):

    dependencies = [
        ("promotions", "0003_sectors_orders_abandon_promo_validation"),
    ]

    operations = [
        migrations.RunPython(approve_existing_codes, migrations.RunPython.noop),
    ]
