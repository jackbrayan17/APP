from django.db import migrations
from django.utils.crypto import get_random_string


def fill_delivery_codes(apps, schema_editor):
    """Les commandes existantes recoivent un code de livraison a 4 chiffres."""
    Order = apps.get_model("orders", "Order")
    for order in Order.objects.filter(delivery_code="").only("id"):
        Order.objects.filter(pk=order.pk).update(delivery_code=get_random_string(4, "0123456789"))


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_sectors_orders_abandon_promo_validation"),
    ]

    operations = [
        migrations.RunPython(fill_delivery_codes, migrations.RunPython.noop),
    ]
