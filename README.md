# Backend Système d'Inventaire — Phase 1 (base de données)

Projet Django contenant uniquement la base de données et l'admin, pour tester
manuellement toutes les règles métier avant de coder l'API et l'app MC62.

## Démarrage rapide

```bash
python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install django

pip install -r requirements.txt

python3 manage.py migrate
python3 manage.py createsuperuser

```

Ouvrir http://127.0.0.1:8000/admin/ et se connecter avec le superuser créé.

## Vérification automatique (optionnel, avant de tester à la main)

Un script rejoue 10 scénarios clés (mission unique active, verrouillage
automatique de zone, cohérence méthode/SKU, recomptage autorisé...) :

```bash
python3 manage.py shell < inventaire/sanity_check.py
```

Chaque ligne doit afficher `OK`. C'est un filet de sécurité, pas un
remplacement des tests manuels.

## Ce que tu peux tester dans l'admin

1. **Client** puis **Mission** (statut = Active). Essaie de créer une 2e
   mission active : doit être refusé. Tu peux aussi importer plusieurs
   clients d'un coup via **"Importer depuis Excel"** en haut de la liste
   **Clients** (colonnes : `nom`, `secteur`, `contact`).
2. Dans la mission, les inlines **Affectation**, **Zone**, **ProduitAttendu**
   permettent de tout créer en une seule page — ou utilise l'import en masse
   décrit ci-dessous pour Zone.
3. **Agents** et **Materiel** ont aussi un bouton **"Importer depuis Excel"**
   sur leur liste (colonnes : `nom`/`contact`/`role` pour Agent ;
   `numero_serie`/`type_materiel`/`etat` pour Materiel). Une valeur de
   `role` ou `etat` invalide retombe silencieusement sur la valeur par
   défaut plutôt que de faire planter l'import.
4. **Zones** : import en masse aussi disponible (colonnes `code_barres`,
   `methode`), avec un sélecteur de mission puisque chaque zone appartient
   à une mission. Pratique pour créer d'un coup toute une plage de codes
   séquentiels du rouleau vinyle plutôt qu'une zone à la fois.
5. Dans la liste **Produits attendus**, clique **"Importer depuis Excel
   (client)"** en haut à droite plutôt que "Ajouter" — choisis la mission et
   un fichier `.xlsx` avec les colonnes `sku` et `quantite_prevue` (voir
   `Template-ImportProduitsAttendus.xlsx`). Pas de colonne zone : c'est une
   donnée client, le zoning est fait par l'agence séparément pour le
   comptage terrain — la réconciliation se fait par SKU, au niveau de toute
   la mission.
6. Dans **Mouvements de stock**, simule des scans :
   - un scan sans SKU sur une zone "scan strict" → doit être refusé ;
   - un scan avec SKU sur une zone "saisie manuelle" → doit être refusé ;
   - un même agent qui scanne une zone A puis une zone B → la zone A doit se
     verrouiller automatiquement (vérifiable dans la liste des zones,
     colonne Statut) ;
   - un scan sur une zone déjà verrouillée → doit être refusé.
7. Pour rouvrir une zone verrouillée (recomptage autorisé) : coche la zone
   dans la liste **Zones** puis choisis l'action *"Rouvrir les zones
   sélectionnées (recomptage autorisé)"*.
8. Tous les modèles ont désormais `date_creation` et `date_modification`
   (remplies automatiquement). Sur une **Zone**, `date_modification` te donne
   gratuitement le moment exact où elle a été verrouillée — pas besoin de
   champ dédié.

## Import Excel : comment ça marche sous le capot

`inventaire/admin_mixins.py` contient `ExcelImportMixin`, réutilisé par
Client, Agent, Materiel et Zone. La première colonne déclarée dans
`import_colonnes` est obligatoire et sert de clé (une ligne dont la valeur
existe déjà met à jour l'enregistrement plutôt que d'en créer un nouveau).
Pour ajouter l'import à un nouveau modèle : hériter de `ExcelImportMixin`,
définir `import_colonnes` et implémenter `importer_ligne(self, mission,
valeurs)`. `ProduitAttendu` garde sa propre implémentation historique
(légèrement différente : pas de logique de repli sur valeur par défaut) —
elle pourrait être migrée vers le mixin plus tard si besoin, mais n'a pas
été retouchée pour ne pas re-tester ce qui marchait déjà.

## Ce qui n'est PAS encore fait (volontairement, phase 2+)

- API REST (Django REST Framework) pour que l'app Android du MC62 puisse
  envoyer des scans.
- Dashboard HTMX + SSE (synchronisation live).
- Application Android sur le MC62 (3 interfaces selon la méthode de zone).
- Mise en cache locale hors-ligne sur le MC62.
- Rapport de restitution client.

## Où vivent les règles métier

Toute la logique conditionnelle (zone verrouillée, verrouillage automatique,
cohérence méthode/SKU, mission unique active) est dans
`inventaire/models.py`, dans les méthodes `clean()` et `save()` de chaque
modèle — volontairement en code Python, pas en contraintes de base de
données, pour rester facile à faire évoluer.
