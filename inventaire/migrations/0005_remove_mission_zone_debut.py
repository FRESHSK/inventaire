from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("inventaire", "0004_add_timestamps"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="mission",
            name="zone_debut",
        ),
    ]
