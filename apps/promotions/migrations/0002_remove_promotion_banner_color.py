from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("promotions", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="promotion",
            name="banner_color",
        ),
    ]
