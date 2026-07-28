"""Utilitaires partagés pour l'import Excel en masse, utilisés par
ExcelImportMixin (admin_mixins.py). Isolé ici pour rester réutilisable même
en dehors de l'admin plus tard (ex: import en ligne de commande).
"""
import openpyxl


def lire_excel_avec_entetes(fichier, colonne_requise):
    """Charge un classeur Excel, lit la ligne 1 comme en-têtes (en minuscules,
    espaces retirés), vérifie que `colonne_requise` y figure.

    Retourne (entetes: list[str], lignes: list[tuple]) où lignes exclut la
    ligne d'en-tête. Lève ValueError si le fichier est vide ou si la colonne
    requise est absente.
    """
    classeur = openpyxl.load_workbook(fichier, data_only=True)
    feuille = classeur.active
    lignes = list(feuille.iter_rows(values_only=True))

    if not lignes:
        raise ValueError("Le fichier est vide.")

    entetes = [str(c).strip().lower() if c is not None else "" for c in lignes[0]]
    if colonne_requise not in entetes:
        raise ValueError(f"Colonne obligatoire manquante en ligne 1 : '{colonne_requise}'.")

    return entetes, lignes[1:]


def valeur_colonne(entetes, ligne, colonne):
    """Renvoie la valeur d'une colonne nommée pour une ligne donnée, ou None
    si la colonne n'existe pas dans le fichier (colonne optionnelle absente).
    """
    if colonne not in entetes:
        return None
    return ligne[entetes.index(colonne)]
