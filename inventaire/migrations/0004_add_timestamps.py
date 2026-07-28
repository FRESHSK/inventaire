# Écrite à la main plutôt que via makemigrations : l'invite interactive de
# détection de renommage (horodatage -> date_creation sur MouvementStock)
# bloquait en environnement non-interactif. Le résultat est exactement ce que
# makemigrations aurait généré en répondant "non, ce n'est pas un renommage"
# à chaque question : un RemoveField + AddField distincts pour MouvementStock,
# et un simple AddField x2 pour les 7 autres modèles.

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventaire', '0003_remove_affectation_role'),
    ]

    operations = [
        # --- Client ---
        migrations.AddField(
            model_name='client',
            name='date_creation',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='client',
            name='date_modification',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        # --- Mission ---
        migrations.AddField(
            model_name='mission',
            name='date_creation',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='mission',
            name='date_modification',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        # --- Agent ---
        migrations.AddField(
            model_name='agent',
            name='date_creation',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='agent',
            name='date_modification',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        # --- Materiel ---
        migrations.AddField(
            model_name='materiel',
            name='date_creation',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='materiel',
            name='date_modification',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        # --- Zone ---
        migrations.AddField(
            model_name='zone',
            name='date_creation',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='zone',
            name='date_modification',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        # --- ProduitAttendu ---
        migrations.AddField(
            model_name='produitattendu',
            name='date_creation',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='produitattendu',
            name='date_modification',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        # --- Affectation ---
        migrations.AddField(
            model_name='affectation',
            name='date_creation',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='affectation',
            name='date_modification',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        # --- MouvementStock : horodatage -> date_creation + date_modification ---
        migrations.RemoveField(
            model_name='mouvementstock',
            name='horodatage',
        ),
        migrations.AddField(
            model_name='mouvementstock',
            name='date_creation',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='mouvementstock',
            name='date_modification',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name='mouvementstock',
            options={'ordering': ['-date_creation'], 'verbose_name': 'Mouvement de stock', 'verbose_name_plural': 'Mouvements de stock'},
        ),
    ]
