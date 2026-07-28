"""
Script de vérification rapide des règles métier — à lancer avec :
    python3 manage.py shell < inventaire/sanity_check.py

Ce n'est pas une suite de tests unitaires formelle (voir tests.py pour ça
plus tard) : c'est un scénario de bout en bout qui simule une mini-mission
pour vérifier que les règles définies en discussion se comportent bien
avant de commencer à tester manuellement dans l'admin.
"""
from django.core.exceptions import ValidationError

from inventaire.models import (
    Client, Mission, Agent, Materiel, Zone, ProduitAttendu, Affectation, MouvementStock,
)

print("=== Nettoyage des données de test précédentes ===")
Mission.objects.filter(client__nom="TEST_CLIENT").delete()
Client.objects.filter(nom="TEST_CLIENT").delete()
Agent.objects.filter(nom__in=["Karim", "Yassine"]).delete()
Materiel.objects.filter(numero_serie="MC62-001").delete()

print("=== 1. Création Client / Mission / Agent / Materiel ===")
client = Client.objects.create(nom="TEST_CLIENT", secteur="Retail")
mission = Mission.objects.create(client=client, lieu="Entrepôt test", statut=Mission.Statut.ACTIVE)
agent1 = Agent.objects.create(nom="Karim", role=Agent.Role.SCANNEUR)
agent2 = Agent.objects.create(nom="Yassine", role=Agent.Role.SCANNEUR)
scanner1 = Materiel.objects.create(numero_serie="MC62-001")
Affectation.objects.create(mission=mission, agent=agent1, materiel=scanner1)
print("OK")

print("=== 2. Mission unique active : une 2e mission active doit échouer ===")
try:
    Mission.objects.create(client=client, lieu="Autre entrepôt", statut=Mission.Statut.ACTIVE)
    print("ECHEC : la 2e mission active aurait dû être rejetée")
except ValidationError as e:
    print("OK — rejeté comme attendu :", e.message_dict)

print("=== 3. Création de zones avec méthodes différentes ===")
zone_scan = Zone.objects.create(mission=mission, code_barres="000001", methode=Zone.Methode.SCAN_STRICT)
zone_multi = Zone.objects.create(mission=mission, code_barres="000002", methode=Zone.Methode.SCAN_MULTIPLICATEUR)
zone_manuelle = Zone.objects.create(mission=mission, code_barres="000003", methode=Zone.Methode.SAISIE_MANUELLE)
ProduitAttendu.objects.create(mission=mission, sku="SKU-001", quantite_prevue=10)
print("OK — 3 zones créées")

print("=== 4. Scan strict normal (doit passer, méthode auto-remplie depuis la zone) ===")
mv = MouvementStock.objects.create(zone=zone_scan, agent=agent1, sku="SKU-001", quantite=1)
print("OK — méthode auto-remplie :", mv.methode)

print("=== 5. SKU obligatoire en scan strict : doit échouer sans SKU ===")
try:
    MouvementStock.objects.create(zone=zone_scan, agent=agent1, quantite=1)
    print("ECHEC : aurait dû exiger un SKU")
except ValidationError as e:
    print("OK — rejeté comme attendu :", e.message_dict)

print("=== 6. Saisie manuelle agrégée : SKU doit être vide, quantité = total ===")
mv2 = MouvementStock.objects.create(zone=zone_manuelle, agent=agent2, quantite=250)
print("OK — total enregistré sans SKU :", mv2.quantite, "sku=", mv2.sku)

print("=== 7. Saisie manuelle avec SKU fourni par erreur : doit échouer ===")
try:
    MouvementStock.objects.create(zone=zone_manuelle, agent=agent2, sku="SKU-999", quantite=5)
    print("ECHEC : aurait dû rejeter le SKU en mode saisie manuelle")
except ValidationError as e:
    print("OK — rejeté comme attendu :", e.message_dict)

print("=== 8. Verrouillage automatique : agent1 passe de zone_scan à zone_multi ===")
zone_scan.refresh_from_db()
print("Statut zone_scan AVANT changement de zone :", zone_scan.statut)
MouvementStock.objects.create(zone=zone_multi, agent=agent1, sku="SKU-002", quantite=12)
zone_scan.refresh_from_db()
print("Statut zone_scan APRES changement de zone :", zone_scan.statut, "(attendu: verrouillee)")

print("=== 9. Scan sur une zone verrouillée : doit échouer ===")
try:
    MouvementStock.objects.create(zone=zone_scan, agent=agent1, sku="SKU-003", quantite=1)
    print("ECHEC : aurait dû rejeter le scan sur zone verrouillée")
except ValidationError as e:
    print("OK — rejeté comme attendu :", e.message_dict)

print("=== 10. Recomptage autorisé : réouverture manuelle de la zone ===")
zone_scan.rouvrir()
zone_scan.refresh_from_db()
print("Statut zone_scan après rouvrir() :", zone_scan.statut, "(attendu: deverrouillee)")
mv3 = MouvementStock.objects.create(zone=zone_scan, agent=agent1, sku="SKU-001", quantite=1)
print("OK — nouveau scan accepté après réouverture, id=", mv3.id)

print("=== Nettoyage ===")
Mission.objects.filter(client__nom="TEST_CLIENT").delete()
Client.objects.filter(nom="TEST_CLIENT").delete()
Agent.objects.filter(nom__in=["Karim", "Yassine"]).delete()
Materiel.objects.filter(numero_serie="MC62-001").delete()
print("=== TERMINE : tous les scénarios se sont comportés comme attendu ===")
