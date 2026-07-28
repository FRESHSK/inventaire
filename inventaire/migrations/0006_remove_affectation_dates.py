from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("inventaire", "0005_remove_mission_zone_debut"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="affectation",
            name="date_debut",
        ),
        migrations.RemoveField(
            model_name="affectation",
            name="date_fin",
        ),
    ]
