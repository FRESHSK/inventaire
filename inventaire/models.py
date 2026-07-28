"""
Modèles du système de gestion d'inventaire externalisé.

Correspond au diagramme de classes UML validé en discussion (v2) :
Client, Mission, Agent, Materiel, Zone, ProduitAttendu, Affectation, MouvementStock.

Les règles métier "conditionnelles" (zone verrouillée -> rejet, verrouillage
automatique au changement de zone, cohérence méthode/SKU) sont volontairement
implémentées ici en Python (clean()/save()), pas comme contraintes de base de
données -- voir section 5.2 de la spec technique.
"""
from django.core.exceptions import ValidationError
from django.db import models


class TimestampedModel(models.Model):
    """Base abstraite : trace automatiquement la création et la dernière
    modification de chaque enregistrement, sur tous les modèles — utile pour
    l'historique (ex: Zone.date_modification donne gratuitement le moment où
    une zone a été verrouillée, sans champ dédié).
    """

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Client(TimestampedModel):
    """Entreprise commanditaire de l'inventaire."""

    nom = models.CharField(max_length=200)
    secteur = models.CharField(max_length=120, blank=True)
    contact = models.CharField(max_length=200, blank=True, help_text="Nom, téléphone ou email du contact client")

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Mission(TimestampedModel):
    """Un inventaire donné, chez un client, à une date précise.

    Une seule mission doit être active à la fois (voir clean()).
    """

    class Statut(models.TextChoices):
        PREPARATION = "preparation", "Préparation"
        ACTIVE = "active", "Active"
        TERMINEE = "terminee", "Terminée"

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="missions")
    lieu = models.CharField(max_length=200, blank=True, help_text="Entrepôt / magasin / adresse")
    date_debut = models.DateTimeField(null=True, blank=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.PREPARATION)

    class Meta:
        verbose_name = "Mission"
        verbose_name_plural = "Missions"
        ordering = ["-date_debut"]

    def __str__(self):
        return f"{self.client} — {self.lieu or 'mission'} ({self.get_statut_display()})"

    def clean(self):
        if self.statut == self.Statut.ACTIVE:
            deja_active = Mission.objects.filter(statut=self.Statut.ACTIVE).exclude(pk=self.pk)
            if deja_active.exists():
                raise ValidationError(
                    {"statut": "Une seule mission peut être active à la fois. "
                               f"Mission déjà active : {deja_active.first()}."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Agent(TimestampedModel):
    """Personnel recruté mission par mission (vacataire)."""

    class Role(models.TextChoices):
        SCANNEUR = "scanneur", "Scanneur"
        CHEF_EQUIPE = "chef_equipe", "Chef d'équipe"

    nom = models.CharField(max_length=200)
    contact = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SCANNEUR)
    zone_courante = models.ForeignKey(
        "Zone", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Dernière zone scannée par cet agent — utilisée pour le verrouillage automatique.",
    )

    class Meta:
        verbose_name = "Agent"
        verbose_name_plural = "Agents"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Materiel(TimestampedModel):
    """Parc de scanners MC62 (et autre matériel : imprimante d'étiquettes, etc.)."""

    class Etat(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible"
        EN_SERVICE = "en_service", "En service"
        MAINTENANCE = "maintenance", "Maintenance"

    numero_serie = models.CharField(max_length=100, unique=True)
    type_materiel = models.CharField(max_length=100, default="Chainway MC62")
    etat = models.CharField(max_length=20, choices=Etat.choices, default=Etat.DISPONIBLE)

    class Meta:
        verbose_name = "Matériel"
        verbose_name_plural = "Matériel"
        ordering = ["numero_serie"]

    def __str__(self):
        return f"{self.type_materiel} — {self.numero_serie} ({self.get_etat_display()})"


class Zone(TimestampedModel):
    """Unité physique adressable (étagère, box, palette...) identifiée par une
    étiquette code-barres séquentielle, avec sa méthode de comptage assignée.
    """

    class Statut(models.TextChoices):
        DEVERROUILLEE = "deverrouillee", "Déverrouillée"
        VERROUILLEE = "verrouillee", "Verrouillée"

    class Methode(models.TextChoices):
        SCAN_STRICT = "scan_strict", "Scan strict"
        SCAN_MULTIPLICATEUR = "scan_multiplicateur", "Scan + multiplicateur"
        SAISIE_MANUELLE = "saisie_manuelle", "Saisie manuelle agrégée"

    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="zones")
    code_barres = models.CharField(max_length=50, unique=True, help_text="Numéro séquentiel de l'étiquette vinyle")
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.DEVERROUILLEE)
    methode = models.CharField(max_length=30, choices=Methode.choices, default=Methode.SCAN_STRICT)

    class Meta:
        verbose_name = "Zone"
        verbose_name_plural = "Zones"
        ordering = ["code_barres"]

    def __str__(self):
        return f"Zone {self.code_barres} ({self.get_statut_display()})"

    def rouvrir(self):
        """Réouverture manuelle par le responsable (recomptage autorisé).
        Ne supprime PAS les anciens MouvementStock : ça reste une action
        manuelle et volontaire de l'utilisateur, comme décidé en discussion.
        """
        self.statut = self.Statut.DEVERROUILLEE
        self.save(update_fields=["statut", "date_modification"])


class ProduitAttendu(TimestampedModel):
    """Stock théorique fourni par le client avant la mission.

    Pas de lien vers Zone ici volontairement : c'est une donnée du CLIENT
    (SKU + quantité attendue), et le client ne connaît pas le zoning —
    le découpage en zones est fait par l'agence pour les besoins du
    comptage, pas par le client. La réconciliation se fait donc par SKU,
    au niveau de la mission entière, pas zone par zone.
    """

    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="produits_attendus")
    sku = models.CharField(max_length=100)
    quantite_prevue = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Produit attendu"
        verbose_name_plural = "Produits attendus"
        unique_together = [("mission", "sku")]
        ordering = ["sku"]

    def __str__(self):
        return f"{self.sku} — {self.quantite_prevue} attendu(s)"


class Affectation(TimestampedModel):
    """Classe d'association : attribution d'un scanner (Materiel) à un Agent,
    pour une Mission donnée. Remplie manuellement par le responsable en début
    de mission — pas de lien permanent scanner <-> agent.

    Pas de champ role ici : le rôle est déjà porté par Agent.role
    (scanneur / chef d'équipe) — le dupliquer sur l'affectation serait
    redondant et risquerait de désynchroniser les deux.
    """

    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="affectations")
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="affectations")
    materiel = models.ForeignKey(Materiel, on_delete=models.CASCADE, related_name="affectations")

    class Meta:
        verbose_name = "Affectation"
        verbose_name_plural = "Affectations"
        unique_together = [("mission", "materiel")]

    def __str__(self):
        return f"{self.materiel} → {self.agent} ({self.mission})"


class MouvementStock(TimestampedModel):
    """Un scan (ou une saisie de quantité) réalisé par un agent dans une zone.

    Règles appliquées dans clean()/save() :
    - zone verrouillée -> rejet ;
    - méthode du mouvement doit correspondre à la méthode de la zone ;
    - SKU obligatoire sauf en saisie manuelle agrégée (où il doit être vide) ;
    - changement de zone par le même agent -> verrouillage automatique de
      l'ancienne zone.
    """

    class Methode(models.TextChoices):
        SCAN_STRICT = "scan_strict", "Scan strict"
        SCAN_MULTIPLICATEUR = "scan_multiplicateur", "Scan + multiplicateur"
        SAISIE_MANUELLE = "saisie_manuelle", "Saisie manuelle agrégée"

    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="mouvements")
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="mouvements")
    sku = models.CharField(max_length=100, blank=True, null=True)
    quantite = models.PositiveIntegerField(default=1)
    methode = models.CharField(max_length=30, choices=Methode.choices, blank=True)

    class Meta:
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"{self.zone} — {self.sku or 'total zone'} x{self.quantite}"

    def clean(self):
        errors = {}

        if self.zone_id and self.zone.statut == Zone.Statut.VERROUILLEE:
            errors["zone"] = "Zone verrouillée : scan refusé."

        if self.zone_id and self.methode and self.methode != self.zone.methode:
            errors["methode"] = (
                f"La méthode du mouvement ({self.get_methode_display()}) doit correspondre "
                f"à la méthode définie pour la zone ({self.zone.get_methode_display()})."
            )

        if self.methode == self.Methode.SAISIE_MANUELLE:
            if self.sku:
                errors["sku"] = "Pas de SKU en mode saisie manuelle agrégée : c'est un total pour toute la zone."
        elif self.methode:
            if not self.sku:
                errors["sku"] = "Le SKU est obligatoire pour cette méthode de comptage."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Auto-remplissage de la méthode depuis la zone si absente (l'agent
        # ne choisit jamais la méthode sur le terrain, elle vient de la zone).
        if self.zone_id and not self.methode:
            self.methode = self.zone.methode

        self.full_clean()

        # Verrouillage automatique : si cet agent était sur une autre zone,
        # on la verrouille avant d'enregistrer ce nouveau mouvement.
        if self.agent.zone_courante_id and self.agent.zone_courante_id != self.zone_id:
            ancienne_zone = self.agent.zone_courante
            if ancienne_zone.statut != Zone.Statut.VERROUILLEE:
                ancienne_zone.statut = Zone.Statut.VERROUILLEE
                ancienne_zone.save(update_fields=["statut", "date_modification"])

        super().save(*args, **kwargs)

        if self.agent.zone_courante_id != self.zone_id:
            self.agent.zone_courante = self.zone
            self.agent.save(update_fields=["zone_courante", "date_modification"])
