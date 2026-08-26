from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Service(models.Model):
    """Prestation proposée par le cabinet (services et sous-services)."""

    slug = models.SlugField(unique=True, verbose_name="Identifiant")
    title = models.CharField(max_length=120, verbose_name="Titre")
    short_desc = models.CharField(max_length=255, verbose_name="Résumé")
    description = models.TextField(verbose_name="Description")
    icon = models.CharField(max_length=30, default="briefcase", verbose_name="Icône")
    price_hint = models.CharField(max_length=80, blank=True, verbose_name="Indication tarifaire")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="subservices", verbose_name="Service parent (sous-service)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Service"
        verbose_name_plural = "Services"

    def __str__(self):
        return f"{self.parent.title} › {self.title}" if self.parent else self.title

    @property
    def parent_title(self):
        return self.parent.title if self.parent else "—"


class DevisRequest(models.Model):
    """Demande de devis envoyée depuis le site."""

    STATUS_CHOICES = [
        ("nouveau", "Nouveau"),
        ("en_cours", "En cours"),
        ("traite", "Traité"),
        ("annule", "Annulé"),
    ]
    name = models.CharField(max_length=120, verbose_name="Nom")
    email = models.EmailField(verbose_name="E-mail")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Téléphone")
    company = models.CharField(max_length=120, blank=True, verbose_name="Société")
    service = models.ForeignKey(
        Service, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Service"
    )
    budget = models.CharField(max_length=80, blank=True, verbose_name="Budget estimé")
    details = models.TextField(blank=True, verbose_name="Détails")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="nouveau", verbose_name="Statut")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Reçu le")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Demande de devis"
        verbose_name_plural = "Demandes de devis"

    def __str__(self):
        return f"Devis {self.name} ({self.created_at:%d/%m/%Y})"

    @property
    def service_title(self):
        return self.service.title if self.service else "—"


class Message(models.Model):
    """Message envoyé via la page contact."""

    STATUS_CHOICES = [
        ("nouveau", "Nouveau"),
        ("traite", "Traité"),
        ("annule", "Annulé"),
    ]
    name = models.CharField(max_length=120, verbose_name="Nom")
    email = models.EmailField(verbose_name="E-mail")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Téléphone")
    subject = models.CharField(max_length=200, blank=True, verbose_name="Sujet")
    message = models.TextField(verbose_name="Message")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="nouveau", verbose_name="Statut")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Reçu le")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Message"
        verbose_name_plural = "Messages"

    def __str__(self):
        return f"{self.subject or 'Sans sujet'} — {self.name}"


class Appointment(models.Model):
    """Demande de rendez-vous."""

    STATUS_CHOICES = [
        ("confirme", "Confirmé"),
        ("en_attente", "En attente"),
        ("annule", "Annulé"),
    ]
    name = models.CharField(max_length=120, verbose_name="Nom")
    email = models.EmailField(verbose_name="E-mail")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Téléphone")
    service = models.ForeignKey(
        Service, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Service"
    )
    date = models.DateField(verbose_name="Date")
    time = models.CharField(max_length=5, verbose_name="Heure")
    notes = models.TextField(blank=True, verbose_name="Notes")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="confirme", verbose_name="Statut")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Demandé le")

    class Meta:
        ordering = ["date", "time"]
        verbose_name = "Rendez-vous"
        verbose_name_plural = "Rendez-vous"

    def __str__(self):
        return f"{self.name} — {self.date} à {self.time}"

    @property
    def service_title(self):
        return self.service.title if self.service else "—"


class Client(models.Model):
    """Client du cabinet (espace admin + espace client)."""

    STATUT_CHOICES = [
        ("entreprise", "Entreprise"),
        ("personne_physique", "Personne physique"),
    ]
    user = models.OneToOneField(
        User, null=True, blank=True, on_delete=models.CASCADE, verbose_name="Compte utilisateur"
    )
    name = models.CharField(max_length=120, verbose_name="Nom")
    prenom = models.CharField(max_length=120, blank=True, verbose_name="Prénom")
    email = models.EmailField(verbose_name="E-mail")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Téléphone")
    company = models.CharField(max_length=120, blank=True, verbose_name="Raison sociale")
    adresse = models.CharField(max_length=255, blank=True, verbose_name="Adresse")
    statut_client = models.CharField(max_length=30, choices=STATUT_CHOICES, default="entreprise", verbose_name="Type de client")
    matricule_fiscale = models.CharField(max_length=100, blank=True, verbose_name="Matricule fiscale")
    cin = models.CharField(max_length=8, blank=True, verbose_name="Numéro de carte d'identité")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ajouté le")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        return f"{self.prenom or self.name} {self.name} ({self.company or self.matricule_fiscale or '—'})"

    @property
    def display_name(self):
        if self.statut_client == "entreprise" and self.company:
            return self.company
        return f"{self.prenom} {self.name}".strip()


class Entreprise(models.Model):
    """Entreprise (tenant) rattachée à un compte client du cabinet."""

    FORME_CHOICES = [
        ("sarl", "SARL"),
        ("sarlu", "SARL unipersonnelle"),
        ("sa", "SA"),
        ("suarl", "SUARL"),
        ("snc", "SNC"),
        ("gie", "GIE"),
        ("autre", "Autre"),
    ]
    client = models.OneToOneField(
        Client, on_delete=models.CASCADE, related_name="entreprise", verbose_name="Client (tenant)"
    )
    raison_sociale = models.CharField(max_length=160, verbose_name="Raison sociale")
    matricule_fiscale = models.CharField(max_length=60, blank=True, verbose_name="Matricule fiscal")
    registre_commerce = models.CharField(max_length=100, blank=True, verbose_name="Registre de commerce (RCCM)")
    forme_juridique = models.CharField(max_length=30, choices=FORME_CHOICES, blank=True, verbose_name="Forme juridique")
    activite = models.CharField(max_length=160, blank=True, verbose_name="Activité exercée")
    adresse = models.CharField(max_length=255, blank=True, verbose_name="Adresse du siège")
    code_postal = models.CharField(max_length=20, blank=True, verbose_name="Code postal")
    ville = models.CharField(max_length=80, blank=True, verbose_name="Ville")
    telephone = models.CharField(max_length=30, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="E-mail")
    representant_legal = models.CharField(max_length=160, blank=True, verbose_name="Représentant légal (gérant)")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créée le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Mise à jour")

    class Meta:
        ordering = ["raison_sociale"]
        verbose_name = "Entreprise (tenant)"
        verbose_name_plural = "Entreprises (tenants)"

    def __str__(self):
        return self.raison_sociale


class ClientServiceSuivi(models.Model):
    """Suivi d'un dossier / service pour un client (Balance & Safety)."""

    STATUT_PAIEMENT_CHOICES = [
        ("en_attente", "En attente"),
        ("paye", "Payé"),
        ("retard", "En retard / impayé"),
    ]
    STATUT_SERVICE_CHOICES = [
        ("en_cours", "En cours de traitement"),
        ("valide", "Validé / déposé / conforme"),
        ("cloture", "Clôturé"),
    ]
    FREQUENCE_CHOICES = [
        ("ponctuel", "Ponctuel"),
        ("mensuel", "Mensuel"),
        ("trimestriel", "Trimestriel"),
        ("semestriel", "Semestriel"),
        ("annuel", "Annuel"),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="services", verbose_name="Client")
    type_service = models.ForeignKey(
        Service, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Type de service"
    )
    montant = models.DecimalField(max_digits=10, decimal_places=3, default=0, verbose_name="Prix (TND)")
    statut_paiement = models.CharField(max_length=20, choices=STATUT_PAIEMENT_CHOICES, default="en_attente", verbose_name="Statut de paiement")
    statut_service = models.CharField(max_length=20, choices=STATUT_SERVICE_CHOICES, default="en_cours", verbose_name="Suivi du service")
    date_echeance = models.DateField(null=True, blank=True, verbose_name="Échéance fiscale / sociale")
    frequence = models.CharField(max_length=20, choices=FREQUENCE_CHOICES, default="ponctuel", verbose_name="Répétition du service")
    commentaire = models.TextField(blank=True, verbose_name="Note du dossier")
    service_note = models.TextField(blank=True, verbose_name="Note du service (dans le dossier)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        ordering = ["date_echeance", "-id"]
        verbose_name = "Suivi & paiement client"
        verbose_name_plural = "Suivis & paiements clients"

    def __str__(self):
        return f"{self.client.name} — {self.type_service or '—'}"

    @property
    def client_name(self):
        return self.client.name

    @property
    def service_title(self):
        return self.type_service.title if self.type_service else "—"


class DossierTask(models.Model):
    """Tâche liée à un dossier client."""

    STATUT_CHOICES = [
        ("a_faire", "À faire"),
        ("en_cours", "En cours"),
        ("termine", "Terminé"),
    ]
    REPETITION_CHOICES = [
        ("ponctuel", "Ponctuel"),
        ("mensuel", "Mensuel"),
        ("trimestriel", "Trimestriel"),
        ("semestriel", "Semestriel"),
        ("annuel", "Annuel"),
    ]
    dossier = models.ForeignKey(ClientServiceSuivi, on_delete=models.CASCADE, related_name="tasks", verbose_name="Dossier")
    service_followup = models.ForeignKey(
        "ServiceFollowUp", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="tasks", verbose_name="Suivi de service lié",
    )
    titre = models.CharField(max_length=200, verbose_name="Titre")
    description = models.TextField(blank=True, verbose_name="Description")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="a_faire", verbose_name="Statut")
    date_echeance = models.DateField(null=True, blank=True, verbose_name="Échéance")
    repetition = models.CharField(max_length=20, choices=REPETITION_CHOICES, default="ponctuel", verbose_name="Répétition")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créée le")

    class Meta:
        ordering = ["date_echeance", "id"]
        verbose_name = "Tâche de dossier"
        verbose_name_plural = "Tâches de dossiers"

    def __str__(self):
        return f"{self.dossier} — {self.titre}"

    @property
    def client_name(self):
        return self.dossier.client.name

    @property
    def dossier_service(self):
        return self.dossier.service_title

    @property
    def followup_title(self):
        return f"{self.service_followup.service_title} (N°{self.service_followup.id})" if self.service_followup else "—"

    @property
    def followup_id(self):
        return self.service_followup.id if self.service_followup else None


class Prefacture(models.Model):
    """Préfacture / proforma émise pour un dossier client."""

    STATUT_CHOICES = [
        ("emise", "Émise"),
        ("payee", "Payée"),
        ("annulee", "Annulée"),
    ]
    dossier = models.ForeignKey(ClientServiceSuivi, on_delete=models.CASCADE, related_name="prefactures", verbose_name="Dossier")
    numero = models.CharField(max_length=30, unique=True, verbose_name="Numéro")
    date = models.DateField(verbose_name="Date")
    montant_ht = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Montant HT (TND)")
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, default=19.00, verbose_name="Taux TVA (%)")
    montant_ttc = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Montant TTC (TND)")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="emise", verbose_name="Statut")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créée le")

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Préfacture"
        verbose_name_plural = "Préfactures"

    def __str__(self):
        return f"{self.numero} — {self.montant_ttc} TND"

    @property
    def client_name(self):
        return self.dossier.client_name

    @property
    def dossier_service(self):
        return self.dossier.service_title


class DossierAttachment(models.Model):
    """Fichier attaché à un dossier client (image, pdf, office, zip, audio, vidéo…)."""

    UPLOADER_CHOICES = [
        ("client", "Client"),
        ("admin", "Cabinet"),
    ]
    dossier = models.ForeignKey(ClientServiceSuivi, on_delete=models.CASCADE, related_name="attachments", verbose_name="Dossier")
    file = models.FileField(upload_to="attachments/%Y/%m/", verbose_name="Fichier")
    original_name = models.CharField(max_length=255, verbose_name="Nom du fichier")
    content_type = models.CharField(max_length=120, blank=True, verbose_name="Type MIME")
    size = models.IntegerField(default=0, verbose_name="Taille (octets)")
    uploaded_by = models.CharField(max_length=10, choices=UPLOADER_CHOICES, default="client", verbose_name="Ajouté par")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ajouté le")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Pièce jointe"
        verbose_name_plural = "Pièces jointes"

    def __str__(self):
        return f"{self.original_name} ({self.dossier})"

    @property
    def client_name(self):
        return self.dossier.client_name

    @property
    def dossier_service(self):
        return self.dossier.service_title

    @property
    def category(self):
        ext = self.original_name.rsplit(".", 1)[-1].lower() if "." in self.original_name else ""
        image = {"jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"}
        pdf = {"pdf"}
        office = {"doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods"}
        txt = {"txt", "csv", "rtf"}
        archive = {"zip", "rar", "7z", "tar", "gz"}
        audio = {"mp3", "wav", "ogg", "aac", "m4a"}
        video = {"mp4", "mov", "mkv", "avi", "webm", "m4v"}
        if ext in image: return "image"
        if ext in pdf: return "pdf"
        if ext in office: return "office"
        if ext in txt: return "texte"
        if ext in archive: return "archive"
        if ext in audio: return "audio"
        if ext in video: return "video"
        return "autre"

    @property
    def size_display(self):
        size = self.size
        for unit in ("o", "Ko", "Mo", "Go"):
            if size < 1024:
                return f"{size:.0f} {unit}"
            size /= 1024
        return f"{size:.0f} Go"


class ClientMessage(models.Model):
    """Message échangé entre le client et le cabinet."""

    DIRECTION_CHOICES = [
        ("client", "Client"),
        ("admin", "Cabinet"),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="messages", verbose_name="Client")
    dossier = models.ForeignKey(
        "ClientServiceSuivi", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="messages", verbose_name="Dossier lié",
    )
    service = models.ForeignKey(
        Service, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="messages", verbose_name="Service lié",
    )
    task = models.ForeignKey(
        DossierTask, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="messages", verbose_name="Tâche liée",
    )
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default="client", verbose_name="Émetteur")
    text = models.TextField(verbose_name="Message")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Envoyé le")

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Message client"
        verbose_name_plural = "Messages clients"

    def __str__(self):
        return f"[{self.get_direction_display()}] {self.client.name} — {self.text[:40]}"

    @property
    def client_name(self):
        return self.client.name

    @property
    def dossier_service(self):
        return f"{self.dossier.service_title} (N°{self.dossier.id})" if self.dossier else "—"

    @property
    def service_title(self):
        return self.service.title if self.service else "—"

    @property
    def task_title(self):
        return self.task.titre if self.task else "—"

    @property
    def context_label(self):
        parts = []
        if self.dossier:
            parts.append(self.dossier_service)
        if self.task:
            parts.append(f"Tâche : {self.task_title}")
        return " · ".join(parts) if parts else "Général"


class AuthToken(models.Model):
    """Jeton d'accès à l'espace client (durée de vie limitée, rotation au login)."""

    key = models.CharField(max_length=64, unique=True, verbose_name="Jeton")
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Utilisateur")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    expires_at = models.DateTimeField(verbose_name="Expire le", null=True, blank=True)
    last_used_at = models.DateTimeField(verbose_name="Dernier usage", null=True, blank=True)

    def __str__(self):
        return f"Token {self.user.username}"

    @property
    def is_valid(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True


class StaffProfile(models.Model):
    """Profil RBAC d'un membre du cabinet (jetons admin par rôle)."""

    ROLE_CHOICES = [
        ("admin", "Administrateur"),
        ("gestionnaire", "Gestionnaire"),
        ("comptable", "Comptable"),
        ("lecture", "Lecture seule"),
    ]
    ROLE_LEVELS = {"admin": 100, "gestionnaire": 80, "comptable": 60, "lecture": 40}

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff_profile", verbose_name="Utilisateur")
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default="lecture", verbose_name="Rôle")
    actif = models.BooleanField(default=True, verbose_name="Compte actif")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        verbose_name = "Profil staff"
        verbose_name_plural = "Profils staff"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

    @property
    def level(self):
        return self.ROLE_LEVELS.get(self.role, 0)


class StaffToken(models.Model):
    """Jeton Bearer d'accès à l'API admin, rattaché à un profil staff (RBAC)."""

    key = models.CharField(max_length=64, unique=True, verbose_name="Jeton")
    profile = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="tokens", verbose_name="Profil")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    expires_at = models.DateTimeField(verbose_name="Expire le", null=True, blank=True)
    last_used_at = models.DateTimeField(verbose_name="Dernier usage", null=True, blank=True)
    revoque = models.BooleanField(default=False, verbose_name="Révoqué")

    def __str__(self):
        return f"StaffToken {self.profile}"

    @property
    def is_valid(self):
        if self.revoque:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return self.profile.actif


class SecurityLog(models.Model):
    """Journal de sécurité : connexions, échecs, tokens, actions sensibles."""

    ACTION_CHOICES = [
        ("login_ok", "Connexion réussie"),
        ("login_fail", "Échec de connexion"),
        ("register", "Inscription"),
        ("token_expired", "Jeton expiré"),
        ("token_created", "Jeton créé"),
        ("token_revoked", "Jeton révoqué"),
        ("throttled", "Tentative bloquée (trop d'échecs)"),
        ("staff_created", "Membre staff créé"),
        ("role_changed", "Rôle modifié"),
    ]
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, verbose_name="Action")
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Utilisateur concerné")
    email = models.CharField(max_length=254, blank=True, verbose_name="E-mail")
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="Adresse IP")
    details = models.CharField(max_length=400, blank=True, verbose_name="Détails")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Le")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Journal de sécurité"
        verbose_name_plural = "Journal de sécurité"

    def __str__(self):
        return f"{self.action} {self.email or self.actor or ''} {self.created_at:%d/%m/%Y %H:%M}"


class Payment(models.Model):
    """Paiement d'un client."""

    STATUS_CHOICES = [
        ("en_attente", "En attente"),
        ("partiel", "Partiel"),
        ("paye", "Payé"),
        ("retard", "En retard"),
        ("annule", "Annulé"),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Client")
    dossier = models.ForeignKey(
        ClientServiceSuivi, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="payments", verbose_name="Dossier lié",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant (TND)")
    date = models.DateField(verbose_name="Date")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="en_attente", verbose_name="Statut")
    method = models.CharField(max_length=80, blank=True, verbose_name="Mode de paiement")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"

    def __str__(self):
        return f"{self.amount} TND — {self.client.name} ({self.date})"

    @property
    def client_name(self):
        return self.client.name

    @property
    def dossier_service(self):
        return f"{self.dossier.service_title} (N°{self.dossier.id})" if self.dossier else "—"


class Collaborateur(models.Model):
    """Collaborateur du cabinet (personnel)."""

    nom = models.CharField(max_length=100, verbose_name="Nom")
    prenom = models.CharField(max_length=100, blank=True, verbose_name="Prénom")
    email = models.EmailField(verbose_name="E-mail")
    telephone = models.CharField(max_length=30, blank=True, verbose_name="Téléphone")
    fonction = models.CharField(max_length=120, blank=True, verbose_name="Fonction / Poste")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ajouté le")

    class Meta:
        ordering = ["nom", "prenom", "id"]
        verbose_name = "Collaborateur"
        verbose_name_plural = "Personnel (collaborateurs)"

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return f"{self.prenom} {self.nom}".strip() or self.email


class ServiceFollowUp(models.Model):
    """Suivi d'un service souscrit par un client."""

    STATUS_CHOICES = [
        ("en_attente", "En attente"),
        ("en_cours", "En cours"),
        ("termine", "Terminé"),
        ("cloture", "Clôturé"),
        ("annule", "Annulé"),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Client")
    dossier = models.ForeignKey(
        "ClientServiceSuivi", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="service_followups", verbose_name="Dossier associé",
    )
    service = models.ForeignKey(
        Service, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Service"
    )
    collaborateur = models.ForeignKey(
        Collaborateur, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="followups", verbose_name="Collaborateur assigné",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="en_attente", verbose_name="Statut")
    start_date = models.DateField(null=True, blank=True, verbose_name="Date de début")
    due_date = models.DateField(null=True, blank=True, verbose_name="Échéance")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Suivi de service"
        verbose_name_plural = "Suivis de service"

    def __str__(self):
        return f"{self.client.name} — {self.service or '—'}"

    @property
    def client_name(self):
        return self.client.display_name

    @property
    def service_title(self):
        return self.service.title if self.service else "—"

    @property
    def dossier_label(self):
        return f"{self.dossier.service_title} (N°{self.dossier.id})" if self.dossier else "—"

    @property
    def dossier_id(self):
        return self.dossier.id if self.dossier else None

    @property
    def collaborateur_name(self):
        return self.collaborateur.display_name if self.collaborateur else "—"

    @property
    def collaborateur_id(self):
        return self.collaborateur.id if self.collaborateur else None

    @property
    def dossier_tasks(self):
        return self.dossier.tasks.all() if self.dossier else DossierTask.objects.none()


class DeclarationFiscale(models.Model):
    """Suivi des échéances et déclarations fiscales (DGI Tunisie)."""

    TYPE_DECLARATION_CHOICES = [
        ("mensuelle", "Déclaration Mensuelle (TVA / RS)"),
        ("acompte", "Acompte Provisionnel IS / IRPP"),
        ("annuelle", "Bilan & Liasse Fiscale Annuelle"),
        ("autre", "Autre Déclaration Spécifique"),
    ]
    STATUT_CHOICES = [
        ("a_faire", "À préparer"),
        ("en_cours", "En cours de vérification"),
        ("depose", "Déposé (Validé)"),
        ("retard", "En retard"),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="declarations", verbose_name="Client")
    dossier = models.ForeignKey(
        ClientServiceSuivi, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="declarations", verbose_name="Dossier lié",
    )
    type_declaration = models.CharField(max_length=20, choices=TYPE_DECLARATION_CHOICES, verbose_name="Type de déclaration")
    periode = models.CharField(max_length=80, verbose_name="Période (ex : Mois de Juillet 2026 / Exercice 2025)")
    date_echeance_legale = models.DateField(verbose_name="Date limite légale")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="a_faire", verbose_name="Statut du dossier")
    numero_quittance_ou_tej = models.CharField(max_length=150, blank=True, null=True, verbose_name="N° quittance / accusé de dépôt")
    montant_a_payer = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name="Montant net à payer (TND)")
    notes_collaborateur = models.TextField(blank=True, null=True, verbose_name="Remarques internes ou conseils")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        ordering = ["date_echeance_legale", "-id"]
        verbose_name = "Déclaration fiscale"
        verbose_name_plural = "Suivi des déclarations fiscales"

    def __str__(self):
        return f"{self.client.display_name} — {self.get_type_declaration_display()} ({self.periode})"

    @property
    def client_name(self):
        return self.client.display_name

    @property
    def dossier_service(self):
        return f"{self.dossier.service_title} (N°{self.dossier.id})" if self.dossier else "—"


class CompteComptable(models.Model):
    """Plan comptable tunisien : Classe (1-7) > Compte > Sous-compte > Compte enfant."""

    entreprise = models.ForeignKey(
        Entreprise, on_delete=models.CASCADE, related_name="comptes", verbose_name="Entreprise (tenant)"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="enfants", verbose_name="Compte parent"
    )
    numero = models.CharField(max_length=20, verbose_name="Numéro de compte")
    intitule = models.CharField(max_length=200, verbose_name="Intitulé")
    active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        ordering = ["numero"]
        unique_together = [("entreprise", "numero")]
        verbose_name = "Compte comptable"
        verbose_name_plural = "Plan comptable"

    def __str__(self):
        return f"{self.numero} — {self.intitule}"

    @property
    def classe(self):
        return self.numero[:1] if self.numero else ""

    @property
    def niveau(self):
        n = 0
        cur = self
        while cur.parent_id:
            n += 1
            cur = cur.parent
        return n

    @property
    def is_leaf(self):
        return not self.enfants.exists()


class EcritureComptable(models.Model):
    """Pièce comptable : un journal contenant des lignes débit/crédit équilibrées."""

    JOURNAL_CHOICES = [
        ("od", "Opérations diverses"),
        ("ventes", "Journal des ventes"),
        ("achats", "Journal des achats"),
        ("banque", "Journal de banque"),
        ("caisse", "Journal de caisse"),
    ]
    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("valide", "Validé"),
    ]
    entreprise = models.ForeignKey(
        Entreprise, on_delete=models.CASCADE, related_name="ecritures", verbose_name="Entreprise (tenant)"
    )
    journal = models.CharField(max_length=20, choices=JOURNAL_CHOICES, default="od", verbose_name="Journal")
    numero_piece = models.CharField(max_length=40, verbose_name="N° pièce")
    date = models.DateField(verbose_name="Date")
    libelle = models.CharField(max_length=255, verbose_name="Libellé")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="brouillon", verbose_name="Statut")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créée le")

    class Meta:
        ordering = ["date", "-id"]
        verbose_name = "Écriture comptable"
        verbose_name_plural = "Journaux et pièces"

    def __str__(self):
        return f"{self.numero_piece} — {self.libelle} ({self.date})"

    @property
    def total_debit(self):
        return self.lignes.aggregate(s=models.Sum("debit"))["s"] or 0

    @property
    def total_credit(self):
        return self.lignes.aggregate(s=models.Sum("credit"))["s"] or 0

    @property
    def est_equilibree(self):
        return round(self.total_debit, 3) == round(self.total_credit, 3)


class LigneEcriture(models.Model):
    """Ligne de journal : débit et/ou crédit sur un compte du plan comptable."""

    ecriture = models.ForeignKey(
        EcritureComptable, on_delete=models.CASCADE, related_name="lignes", verbose_name="Écriture"
    )
    compte = models.ForeignKey(
        CompteComptable, on_delete=models.PROTECT, related_name="lignes", verbose_name="Compte"
    )
    libelle = models.CharField(max_length=255, blank=True, verbose_name="Libellé de ligne")
    debit = models.DecimalField(max_digits=15, decimal_places=3, default=0, verbose_name="Débit")
    credit = models.DecimalField(max_digits=15, decimal_places=3, default=0, verbose_name="Crédit")

    class Meta:
        ordering = ["id"]
        verbose_name = "Ligne d'écriture"
        verbose_name_plural = "Lignes d'écritures"

    def __str__(self):
        return f"{self.compte.numero} — {self.debit}/{self.credit}"


class Facture(models.Model):
    """Facturation tenant : vente/achat, TVA, droit de timbre et retenue à la source (TEJ)."""

    TYPE_CHOICES = [
        ("vente", "Facture de vente"),
        ("achat", "Facture d'achat"),
    ]
    STATUT_CHOICES = [
        ("brouillon", "Brouillon"),
        ("valide", "Validée"),
        ("annulee", "Annulée"),
    ]
    IDENTIFIANT_CHOICES = [
        ("matricule", "Matricule fiscal"),
        ("cin", "CIN"),
        ("passeport", "Passeport"),
        ("cartesejour", "Carte de séjour"),
    ]
    NATURE_CHOICES = [
        ("acquisition", "Acquisition de biens/services (≥ 1 000 TND)"),
        ("honoraires_reel", "Honoraires — régime réel (3 %)"),
        ("honoraires_forfait", "Honoraires forfait / commissions (10 %)"),
        ("loyer", "Loyers (10 %)"),
        ("dividendes", "Dividendes (10 %)"),
        ("cession", "Cession de valeurs mobilières / immeubles (2,5-15 %)"),
        ("non_resident", "Non-résidents (5-25 %)"),
    ]
    TAUX_TVA_CHOICES = [
        ("0", "0 % (exonérée)"),
        ("7", "7 %"),
        ("13", "13 %"),
        ("19", "19 %"),
    ]

    entreprise = models.ForeignKey(
        Entreprise, on_delete=models.CASCADE, related_name="factures", verbose_name="Entreprise (tenant)"
    )
    type_facture = models.CharField(max_length=10, choices=TYPE_CHOICES, default="vente", verbose_name="Type de facture")
    numero = models.CharField(max_length=40, verbose_name="N° facture")
    date = models.DateField(verbose_name="Date")
    tiers = models.CharField(max_length=200, verbose_name="Raison sociale / Nom du tiers")
    tiers_identifiant_type = models.CharField(
        max_length=20, choices=IDENTIFIANT_CHOICES, default="matricule", verbose_name="Type d'identifiant fiscal"
    )
    tiers_identifiant = models.CharField(max_length=60, blank=True, verbose_name="Identifiant fiscal (MF/CIN…)")
    nature_operation = models.CharField(
        max_length=20, choices=NATURE_CHOICES, default="acquisition", verbose_name="Nature de l'opération (retenue à la source)"
    )
    montant_ht = models.DecimalField(max_digits=12, decimal_places=3, verbose_name="Montant HT (TND)")
    taux_tva = models.DecimalField(max_digits=4, decimal_places=2, default=19, verbose_name="Taux de TVA (%)")
    montant_tva = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name="Montant TVA (TND)")
    montant_ttc = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name="Montant TTC (TND)")
    timbre_fiscal = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name="Droit de timbre (TND)")
    retenue_source_taux = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Taux de retenue à la source (%)")
    retenue_source_montant = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name="Montant retenue à la source (TND)")
    net_a_payer = models.DecimalField(max_digits=12, decimal_places=3, default=0, verbose_name="Net à payer (TTC − retenue)")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="brouillon", verbose_name="Statut")
    ecriture = models.OneToOneField(
        EcritureComptable, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="facture", verbose_name="Écriture comptable générée",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créée le")

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Facture (tenant)"
        verbose_name_plural = "Facturation (tenants)"

    def __str__(self):
        return f"{self.get_type_facture_display()} {self.numero} — {self.tiers} ({self.date})"
