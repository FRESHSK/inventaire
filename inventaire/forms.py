from django import forms

from .models import Mission


class ImportProduitsAttendusForm(forms.Form):
    """Formulaire d'import en masse du stock théorique client (section 3 de
    la spec : le client transmet ses données produits avant la mission).

    Fichier Excel attendu avec une ligne d'en-tête et les colonnes :
    - sku (obligatoire)
    - quantite_prevue (obligatoire, nombre entier)

    Pas de colonne zone : c'est une donnée du client, qui ne connaît pas le
    zoning fait par l'agence pour le comptage sur le terrain.
    """

    mission = forms.ModelChoiceField(
        queryset=Mission.objects.all(),
        label="Mission",
        help_text="Les produits importés seront rattachés à cette mission.",
    )
    fichier = forms.FileField(
        label="Fichier Excel du client (.xlsx)",
        help_text="Colonnes attendues en ligne 1 : sku, quantite_prevue.",
    )

    def clean_fichier(self):
        fichier = self.cleaned_data["fichier"]
        if not fichier.name.lower().endswith((".xlsx", ".xlsm")):
            raise forms.ValidationError("Le fichier doit être un Excel .xlsx (export direct du client).")
        return fichier
