"""Mixin d'admin réutilisable pour ajouter un bouton "Importer depuis Excel"
sur la liste d'un modèle, avec création/mise à jour en masse.

Utilisé par Client, Agent, Materiel, Zone. ProduitAttendu garde sa propre
implémentation (déjà écrite et testée avant ce mixin) — pas de raison de la
retoucher pour l'instant, mais elle suit exactement le même principe.
"""
from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import path

from .import_utils import lire_excel_avec_entetes, valeur_colonne


class ExcelImportMixin:
    """À définir dans la sous-classe ModelAdmin :

    - import_colonnes : liste de noms de colonnes attendues en ligne 1 du
      fichier. Le premier élément est la colonne obligatoire (sert de clé
      pour update_or_create et de test de ligne vide) ; les suivantes sont
      optionnelles.
    - import_besoin_mission : bool — True si l'import doit être rattaché à
      une mission (affiche un sélecteur de mission dans le formulaire).
    - importer_ligne(self, mission, valeurs: dict) -> bool : à implémenter,
      reçoit un dict {colonne: valeur_brute_ou_None} pour une ligne, doit
      faire le update_or_create et renvoyer True si un objet a été créé
      (False si mis à jour).
    """

    import_colonnes: list[str] = []
    import_besoin_mission = False
    change_list_template = "admin/inventaire/import_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        opts = self.model._meta
        custom = [
            path(
                "importer-excel/",
                self.admin_site.admin_view(self.importer_excel_view),
                name=f"{opts.app_label}_{opts.model_name}_importer_excel",
            ),
        ]
        return custom + urls

    def get_import_form_class(self):
        from .models import Mission

        champs = {"fichier": forms.FileField(
            label="Fichier Excel (.xlsx)",
            help_text=f"Colonnes attendues en ligne 1 : {', '.join(self.import_colonnes)}.",
        )}
        if self.import_besoin_mission:
            champs["mission"] = forms.ModelChoiceField(queryset=Mission.objects.all(), label="Mission")
            # Django construit les champs dans l'ordre du dict — mission avant fichier.
            champs = {"mission": champs["mission"], "fichier": champs["fichier"]}
        return type("ImportForm", (forms.Form,), champs)

    def importer_excel_view(self, request):
        FormClass = self.get_import_form_class()

        if request.method == "POST":
            form = FormClass(request.POST, request.FILES)
            if form.is_valid():
                mission = form.cleaned_data.get("mission")
                fichier = form.cleaned_data["fichier"]

                try:
                    entetes, lignes = lire_excel_avec_entetes(fichier, self.import_colonnes[0])
                except ValueError as e:
                    messages.error(request, str(e))
                    return redirect("..")

                crees, mis_a_jour, avertissements = 0, 0, []
                for numero_ligne, ligne in enumerate(lignes, start=2):
                    valeurs = {col: valeur_colonne(entetes, ligne, col) for col in self.import_colonnes}
                    cle = valeurs[self.import_colonnes[0]]
                    if cle in (None, ""):
                        continue  # ligne vide, ignorée silencieusement
                    try:
                        cree = self.importer_ligne(mission, valeurs)
                        crees += int(cree)
                        mis_a_jour += int(not cree)
                    except Exception as e:  # noqa: BLE001 — on veut afficher l'erreur ligne par ligne
                        avertissements.append(f"Ligne {numero_ligne} : {e}")

                messages.success(request, f"Import terminé : {crees} créé(s), {mis_a_jour} mis à jour.")
                for avertissement in avertissements[:20]:
                    messages.warning(request, avertissement)
                if len(avertissements) > 20:
                    messages.warning(request, f"... et {len(avertissements) - 20} autre(s) avertissement(s).")

                return redirect("..")
        else:
            form = FormClass()

        return render(
            request,
            "admin/inventaire/import_form.html",
            {
                "form": form,
                "title": f"Importer {self.model._meta.verbose_name_plural} depuis Excel",
                "opts": self.model._meta,
            },
        )
