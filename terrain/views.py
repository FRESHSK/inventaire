"""Vues terrain pour le MC21/MC62 en mode kiosk (navigateur + scanner en mode
"keyboard emulator"). Volontairement limité au scan strict pour l'instant --
scan+multiplicateur et saisie manuelle viendront plus tard sans toucher à ceci.

Démarche (voir discussion "Option B") : l'agent démarre en choisissant son
Affectation (agent + matériel), pas de zone -- la zone est détectée
dynamiquement au premier scan d'une étiquette de zone, puis change à chaque
nouveau scan de zone rencontré. Tout code qui ne correspond à aucune Zone
est traité comme un article (connu ou non -- la réconciliation avec le
stock théorique du client se fait plus tard, au niveau de la mission, pas
ici, comme pour ProduitAttendu).

Aucune règle métier ici : ces vues se contentent de construire un
MouvementStock et de le sauvegarder -- toute la validation (zone verrouillée,
cohérence méthode/SKU...) reste dans inventaire.models.MouvementStock.

La vue `scan` répond en JSON si la requête vient du fetch() du template
(en-tête X-Requested-With), et garde un comportement classique
POST + redirection sinon -- filet de sécurité si jamais le JavaScript ne
s'exécute pas correctement sur le MC21.
"""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render

from inventaire.models import Affectation, Agent, Materiel, Mission, MouvementStock, Zone


def _est_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def config(request):
    """Écran de démarrage : l'agent choisit lui-même son Agent + son
    Matériel (pas de liste d'Affectations pré-créées par le responsable --
    voir discussion). Un enregistrement Affectation est créé ou mis à jour
    en base pour garder une trace de qui a quel scanner, comme avant.

    Si le Matériel choisi est déjà affecté à un autre agent pour la mission
    active, on ne réaffecte jamais silencieusement : on redemande
    confirmation (champ caché `confirme`) avant d'écraser l'ancienne
    affectation.
    """
    mission = Mission.objects.filter(statut=Mission.Statut.ACTIVE).first()
    agents = Agent.objects.order_by("nom")
    materiels = Materiel.objects.exclude(etat=Materiel.Etat.MAINTENANCE).order_by("numero_serie")
    confirmation = None

    if request.method == "POST" and mission:
        agent_id = request.POST.get("agent")
        materiel_id = request.POST.get("materiel")
        confirme = request.POST.get("confirme") == "1"

        if not agent_id or not materiel_id:
            messages.error(request, "Choisis un agent et un matériel avant de continuer.")
        else:
            try:
                agent = Agent.objects.get(pk=agent_id)
                materiel = Materiel.objects.get(pk=materiel_id)
            except (Agent.DoesNotExist, Materiel.DoesNotExist):
                messages.error(request, "Agent ou matériel introuvable.")
            else:
                existante = Affectation.objects.filter(mission=mission, materiel=materiel).select_related("agent").first()

                if existante and existante.agent_id != agent.id and not confirme:
                    confirmation = {
                        "agent_id": agent.id,
                        "materiel_id": materiel.id,
                        "ancien_agent": existante.agent.nom,
                        "nouvel_agent": agent.nom,
                        "materiel": str(materiel),
                    }
                else:
                    if existante and existante.agent_id != agent.id:
                        existante.agent = agent
                        existante.save(update_fields=["agent", "date_modification"])
                        affectation = existante
                    elif existante:
                        affectation = existante
                    else:
                        affectation = Affectation.objects.create(mission=mission, agent=agent, materiel=materiel)

                    request.session["terrain_agent_id"] = affectation.agent_id
                    request.session["terrain_materiel_id"] = affectation.materiel_id
                    request.session["terrain_zone_id"] = None
                    request.session["terrain_scan_count"] = 0
                    return redirect("terrain:scan")

    return render(
        request,
        "terrain/config.html",
        {"mission": mission, "agents": agents, "materiels": materiels, "confirmation": confirmation},
    )


def scan(request):
    """Boucle de scan : un seul champ qui accepte soit le code d'une zone
    (bascule le contexte, aucun MouvementStock créé) soit n'importe quel
    autre code (enregistré comme article scanné dans la zone active).
    """
    agent_id = request.session.get("terrain_agent_id")
    materiel_id = request.session.get("terrain_materiel_id")
    ajax = _est_ajax(request)

    if not agent_id or not materiel_id:
        if ajax:
            return JsonResponse({"success": False, "erreur": "Session expirée."}, status=400)
        messages.error(request, "Session expirée : rechoisis une affectation.")
        return redirect("terrain:config")

    try:
        agent = Agent.objects.get(pk=agent_id)
        materiel = Materiel.objects.get(pk=materiel_id)
    except (Agent.DoesNotExist, Materiel.DoesNotExist):
        if ajax:
            return JsonResponse({"success": False, "erreur": "Agent ou matériel introuvable."}, status=400)
        messages.error(request, "Agent ou matériel introuvable.")
        return redirect("terrain:config")

    if request.method == "POST":
        code = (request.POST.get("code") or "").strip()

        if not code:
            if ajax:
                return JsonResponse({"success": False, "erreur": "Code vide."}, status=400)
            messages.error(request, "Code vide, réessaie.")
            return redirect("terrain:scan")

        zone_scannee = Zone.objects.filter(code_barres=code).first()

        if zone_scannee:
            if zone_scannee.methode != Zone.Methode.SCAN_STRICT:
                erreur = (
                    f"La zone {zone_scannee.code_barres} n'est pas en scan strict -- "
                    "cette interface ne gère pas encore les autres méthodes."
                )
                if ajax:
                    return JsonResponse({"success": False, "erreur": erreur}, status=400)
                messages.error(request, erreur)
                return redirect("terrain:scan")

            request.session["terrain_zone_id"] = zone_scannee.id
            if ajax:
                return JsonResponse(
                    {
                        "success": True,
                        "zone_switch": True,
                        "zone_code": zone_scannee.code_barres,
                        "count": request.session.get("terrain_scan_count", 0),
                    }
                )
            messages.success(request, f"Zone {zone_scannee.code_barres} active.")
            return redirect("terrain:scan")

        zone_id = request.session.get("terrain_zone_id")
        if not zone_id:
            erreur = "Scanne d'abord le code de la zone."
            if ajax:
                return JsonResponse({"success": False, "erreur": erreur}, status=400)
            messages.error(request, erreur)
            return redirect("terrain:scan")

        try:
            zone = Zone.objects.get(pk=zone_id)
        except Zone.DoesNotExist:
            request.session["terrain_zone_id"] = None
            erreur = "Zone active introuvable, rescanne une zone."
            if ajax:
                return JsonResponse({"success": False, "erreur": erreur}, status=400)
            messages.error(request, erreur)
            return redirect("terrain:scan")

        mouvement = MouvementStock(zone=zone, agent=agent, sku=code, quantite=1, methode=Zone.Methode.SCAN_STRICT)
        try:
            mouvement.save()
        except ValidationError as exc:
            message_list = exc.messages if hasattr(exc, "messages") else [str(exc)]
            erreur = " ".join(message_list)
            if ajax:
                return JsonResponse({"success": False, "erreur": erreur}, status=400)
            messages.error(request, erreur)
            return redirect("terrain:scan")

        request.session["terrain_scan_count"] = request.session.get("terrain_scan_count", 0) + 1
        if ajax:
            return JsonResponse(
                {
                    "success": True,
                    "zone_switch": False,
                    "sku": code,
                    "count": request.session["terrain_scan_count"],
                }
            )
        messages.success(request, code)
        return redirect("terrain:scan")

    zone_id = request.session.get("terrain_zone_id")
    zone = Zone.objects.filter(pk=zone_id).first() if zone_id else None
    scan_count = request.session.get("terrain_scan_count", 0)

    return render(
        request,
        "terrain/scan.html",
        {"agent": agent, "materiel": materiel, "zone": zone, "scan_count": scan_count},
    )
