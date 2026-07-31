"""Vues terrain pour le MC21/MC62 en mode kiosk (navigateur + scanner en mode
"keyboard emulator"). Volontairement limité au scan strict pour l'instant --
scan+multiplicateur et saisie manuelle viendront plus tard sans toucher à ceci.

Aucune règle métier ici : ces vues se contentent de construire un
MouvementStock et de le sauvegarder -- toute la validation (zone verrouillée,
cohérence méthode/SKU...) reste dans inventaire.models.MouvementStock, comme
pour l'admin. Voir la discussion "séparation des apps" : terrain ne duplique
jamais la logique de inventaire.
"""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse

from inventaire.models import Agent, MouvementStock, Zone


def config(request):
    """Écran de démarrage : choix de la zone (scan strict uniquement pour
    l'instant) et de l'agent, une fois par session de comptage.
    """
    if request.method == "POST":
        zone_id = request.POST.get("zone")
        agent_id = request.POST.get("agent")

        if not zone_id or not agent_id:
            messages.error(request, "Choisis une zone et un agent avant de continuer.")
        else:
            request.session["terrain_scan_count"] = 0
            url = f"{reverse('terrain:scan')}?zone={zone_id}&agent={agent_id}"
            return redirect(url)

    zones = Zone.objects.filter(methode=Zone.Methode.SCAN_STRICT).select_related("mission").order_by("code_barres")
    agents = Agent.objects.order_by("nom")

    return render(request, "terrain/config.html", {"zones": zones, "agents": agents})


def scan(request):
    """Boucle de scan : un seul champ SKU, toujours en focus, qui crée un
    MouvementStock à chaque soumission puis revient sur le même écran
    (pattern Post/Redirect/Get) pour enchaîner les scans sans repasser par
    les menus.
    """
    zone_id = request.GET.get("zone")
    agent_id = request.GET.get("agent")

    if not zone_id or not agent_id:
        messages.error(request, "Session expirée : rechoisis une zone et un agent.")
        return redirect("terrain:config")

    try:
        zone = Zone.objects.select_related("mission").get(pk=zone_id)
        agent = Agent.objects.get(pk=agent_id)
    except (Zone.DoesNotExist, Agent.DoesNotExist):
        messages.error(request, "Zone ou agent introuvable.")
        return redirect("terrain:config")

    if zone.methode != Zone.Methode.SCAN_STRICT:
        messages.error(
            request,
            f"La zone {zone.code_barres} n'est pas en scan strict -- "
            "cette interface ne gère pas encore les autres méthodes.",
        )
        return redirect("terrain:config")

    if request.method == "POST":
        sku = (request.POST.get("sku") or "").strip()

        if not sku:
            messages.error(request, "Code-barres vide, réessaie.")
        else:
            mouvement = MouvementStock(
                zone=zone,
                agent=agent,
                sku=sku,
                quantite=1,
                methode=Zone.Methode.SCAN_STRICT,
            )
            try:
                mouvement.save()
            except ValidationError as exc:
                message_list = exc.messages if hasattr(exc, "messages") else [str(exc)]
                messages.error(request, " ".join(message_list))
            else:
                request.session["terrain_scan_count"] = request.session.get("terrain_scan_count", 0) + 1
                messages.success(request, sku)

        url = f"{reverse('terrain:scan')}?zone={zone.id}&agent={agent.id}"
        return redirect(url)

    scan_count = request.session.get("terrain_scan_count", 0)
    return render(
        request,
        "terrain/scan.html",
        {"zone": zone, "agent": agent, "scan_count": scan_count},
    )
