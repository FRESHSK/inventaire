import openpyxl
from django.contrib import admin, messages
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import path

from .admin_mixins import ExcelImportMixin
from .forms import ImportProduitsAttendusForm
from .models import (
    Client,
    Mission,
    Agent,
    Materiel,
    Zone,
    ProduitAttendu,
    Affectation,
    MouvementStock,
)


@admin.register(Client)
class ClientAdmin(ExcelImportMixin, admin.ModelAdmin):
    list_display = ("nom", "secteur", "contact")
    search_fields = ("nom", "secteur")

    import_colonnes = ["nom", "secteur", "contact"]

    def importer_ligne(self, mission, valeurs):
        nom = str(valeurs["nom"]).strip()
        _, cree = Client.objects.update_or_create(
            nom=nom,
            defaults={
                "secteur": str(valeurs.get("secteur") or "").strip(),
                "contact": str(valeurs.get("contact") or "").strip(),
            },
        )
        return cree


class ZoneInline(admin.TabularInline):
    model = Zone
    extra = 0
    fields = ("code_barres", "statut", "methode")


class ProduitAttenduInline(admin.TabularInline):
    model = ProduitAttendu
    extra = 0
    fields = ("sku", "quantite_prevue")


class AffectationInline(admin.TabularInline):
    model = Affectation
    extra = 0
    fields = ("agent", "materiel")


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "client", "lieu", "statut", "date_debut", "date_fin")
    list_filter = ("statut", "client")
    search_fields = ("lieu", "client__nom")
    inlines = [AffectationInline, ZoneInline, ProduitAttenduInline]


@admin.register(Agent)
class AgentAdmin(ExcelImportMixin, admin.ModelAdmin):
    list_display = ("nom", "contact", "role", "zone_courante")
    list_filter = ("role",)
    search_fields = ("nom",)

    import_colonnes = ["nom", "contact", "role"]

    def importer_ligne(self, mission, valeurs):
        nom = str(valeurs["nom"]).strip()
        role_brut = str(valeurs.get("role") or "").strip().lower()
        role = role_brut if role_brut in Agent.Role.values else Agent.Role.SCANNEUR
        _, cree = Agent.objects.update_or_create(
            nom=nom,
            defaults={
                "contact": str(valeurs.get("contact") or "").strip(),
                "role": role,
            },
        )
        return cree


@admin.register(Materiel)
class MaterielAdmin(ExcelImportMixin, admin.ModelAdmin):
    list_display = ("numero_serie", "type_materiel", "etat")
    list_filter = ("etat", "type_materiel")
    search_fields = ("numero_serie",)

    import_colonnes = ["numero_serie", "type_materiel", "etat"]

    def importer_ligne(self, mission, valeurs):
        numero_serie = str(valeurs["numero_serie"]).strip()
        etat_brut = str(valeurs.get("etat") or "").strip().lower()
        etat = etat_brut if etat_brut in Materiel.Etat.values else Materiel.Etat.DISPONIBLE
        type_materiel = str(valeurs.get("type_materiel") or "").strip() or "Chainway MC62"
        _, cree = Materiel.objects.update_or_create(
            numero_serie=numero_serie,
            defaults={"type_materiel": type_materiel, "etat": etat},
        )
        return cree


@admin.register(Zone)
class ZoneAdmin(ExcelImportMixin, admin.ModelAdmin):
    list_display = ("code_barres", "mission", "statut", "methode", "total_scanne")
    list_filter = ("statut", "methode", "mission")
    search_fields = ("code_barres",)
    actions = ["rouvrir_les_zones"]

    import_colonnes = ["code_barres", "methode"]
    import_besoin_mission = True

    @admin.display(description="Total scanné")
    def total_scanne(self, obj):
        total = obj.mouvements.aggregate(t=Sum("quantite"))["t"]
        return total or 0

    @admin.action(description="Rouvrir les zones sélectionnées (recomptage autorisé)")
    def rouvrir_les_zones(self, request, queryset):
        for zone in queryset:
            zone.rouvrir()
        self.message_user(request, f"{queryset.count()} zone(s) rouverte(s) pour recomptage.")

    def importer_ligne(self, mission, valeurs):
        code_barres = str(valeurs["code_barres"]).strip()
        methode_brut = str(valeurs.get("methode") or "").strip().lower()
        methode = methode_brut if methode_brut in Zone.Methode.values else Zone.Methode.SCAN_STRICT
        _, cree = Zone.objects.update_or_create(
            code_barres=code_barres,
            defaults={"mission": mission, "methode": methode},
        )
        return cree


@admin.register(ProduitAttendu)
class ProduitAttenduAdmin(admin.ModelAdmin):
    """Le stock théorique se remplit normalement par IMPORT (bouton en haut
    de la liste), pas ligne par ligne — le client envoie un Excel avec
    potentiellement des milliers de références. La saisie manuelle via
    "Ajouter" reste possible pour corriger une ligne ponctuelle.
    """

    list_display = ("sku", "mission", "quantite_prevue")
    list_filter = ("mission",)
    search_fields = ("sku",)
    change_list_template = "admin/inventaire/produitattendu/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "importer-excel/",
                self.admin_site.admin_view(self.importer_excel),
                name="inventaire_produitattendu_importer_excel",
            ),
        ]
        return custom_urls + urls

    def importer_excel(self, request):
        """Lit le fichier Excel du client et crée/actualise les ProduitAttendu
        correspondants. Colonnes attendues en ligne 1 : sku, quantite_prevue.

        Pas de colonne zone : c'est une donnée client, et le client ne
        connaît pas le zoning fait par l'agence pour le comptage.
        """
        if request.method == "POST":
            form = ImportProduitsAttendusForm(request.POST, request.FILES)
            if form.is_valid():
                mission = form.cleaned_data["mission"]
                fichier = form.cleaned_data["fichier"]

                classeur = openpyxl.load_workbook(fichier, data_only=True)
                feuille = classeur.active
                lignes = list(feuille.iter_rows(values_only=True))

                if not lignes:
                    messages.error(request, "Le fichier est vide.")
                    return redirect("..")

                entetes = [str(c).strip().lower() if c is not None else "" for c in lignes[0]]
                try:
                    idx_sku = entetes.index("sku")
                    idx_qte = entetes.index("quantite_prevue")
                except ValueError:
                    messages.error(
                        request,
                        "Colonnes introuvables : la ligne 1 doit contenir 'sku' et 'quantite_prevue'.",
                    )
                    return redirect("..")

                crees, mis_a_jour, avertissements = 0, 0, []

                for numero_ligne, ligne in enumerate(lignes[1:], start=2):
                    sku = str(ligne[idx_sku]).strip() if ligne[idx_sku] not in (None, "") else ""
                    if not sku:
                        continue  # ligne vide, on l'ignore silencieusement

                    try:
                        quantite = int(ligne[idx_qte] or 0)
                    except (TypeError, ValueError):
                        avertissements.append(f"Ligne {numero_ligne} : quantité invalide, mise à 0.")
                        quantite = 0

                    _, cree = ProduitAttendu.objects.update_or_create(
                        mission=mission, sku=sku,
                        defaults={"quantite_prevue": quantite},
                    )
                    crees += int(cree)
                    mis_a_jour += int(not cree)

                messages.success(
                    request,
                    f"Import terminé pour {mission} : {crees} produit(s) créé(s), {mis_a_jour} mis à jour.",
                )
                for avertissement in avertissements[:20]:
                    messages.warning(request, avertissement)
                if len(avertissements) > 20:
                    messages.warning(request, f"... et {len(avertissements) - 20} autre(s) avertissement(s).")

                return redirect("..")
        else:
            form = ImportProduitsAttendusForm()

        return render(
            request,
            "admin/inventaire/produitattendu/import_form.html",
            {"form": form, "title": "Importer les produits attendus depuis un fichier Excel client", "opts": self.model._meta},
        )


@admin.register(Affectation)
class AffectationAdmin(admin.ModelAdmin):
    list_display = ("mission", "agent", "materiel")
    list_filter = ("mission",)


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = ("date_creation", "zone", "agent", "sku", "quantite", "methode")
    list_filter = ("methode", "zone__mission", "zone")
    search_fields = ("sku",)
    readonly_fields = ("date_creation", "date_modification")
    # Simule un scan : cet écran sert de banc de test manuel pour toutes les
    # règles (zone verrouillée, cohérence méthode/SKU, verrouillage auto).
