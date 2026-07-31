from django.apps import AppConfig


class TerrainConfig(AppConfig):
    """Interface de saisie terrain pour le MC21/MC62 (scan via navigateur en mode
    kiosk). Ne contient aucune règle métier -- elle appelle simplement les
    models de `inventaire`, qui restent la seule source de vérité pour la
    validation (voir inventaire/models.py, MouvementStock.clean()/save()).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "terrain"
    verbose_name = "Terrain (scan)"
