"""Vues de l'application Balance And Tax Safety."""
import json
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Max, Q
from django.db.models.deletion import ProtectedError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import (
    Appointment,
    AuthToken,
    Client,
    ClientMessage,
    ClientServiceSuivi,
    Collaborateur,
    CompteComptable,
    DeclarationFiscale,
    DevisRequest,
    DossierAttachment,
    DossierTask,
    EcritureComptable,
    Entreprise,
    LigneEcriture,
    Message,
    Payment,
    Prefacture,
    SecurityLog,
    Service,
    ServiceFollowUp,
    StaffProfile,
    StaffToken,
)
from .mail import send_auto_reply_and_notify
from .security import auth_service
from .security.audit import log_security
from .security.rbac import require_level, role_level_for_request
from .security.tokens import admin_token_ok, bearer_token, client_from_request, new_staff_token
from .services import comptabilite

OPENING_HOURS = range(9, 17)

ALLOWED_UPLOAD_EXTENSIONS = {
    "image": {"jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"},
    "pdf": {"pdf"},
    "office": {"doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods"},
    "texte": {"txt", "csv", "rtf"},
    "archive": {"zip", "rar", "7z", "tar", "gz"},
    "audio": {"mp3", "wav", "ogg", "aac", "m4a"},
    "video": {"mp4", "mov", "mkv", "avi", "webm", "m4v"},
}


def _attachment_payload(att, request=None):
    data = {
        "id": att.id,
        "name": att.original_name,
        "category": att.category,
        "size": att.size_display,
        "uploaded_by": att.get_uploaded_by_display(),
        "created_at": att.created_at.strftime("%d/%m/%Y"),
        "url": att.file.url,
    }
    if request is not None:
        data["url"] = request.build_absolute_uri(att.file.url)
    return data


def sitemap(request):
    base = settings.SITE_URL
    pages = ["", "services/", "devis/", "contact/", "rendezvous/"]
    urls = "\n".join(
        f'<url><loc>{base}{p}</loc><changefreq>monthly</changefreq><priority>{"1.0" if not p else "0.8"}</priority></url>'
        for p in pages
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n</urlset>"
    )
    return HttpResponse(xml, content_type="application/xml")


def robots(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/",
        "Disallow: /admin/",
        "",
        f"Sitemap: {settings.SITE_URL}sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def _slots():
    slots = []
    for hour in OPENING_HOURS:
        slots.append(f"{hour:02d}:00")
        slots.append(f"{hour:02d}:30")
    return slots


def _json(data, status=200):
    return JsonResponse(data, status=status, safe=False)


def _read_body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}


def _missing(body: dict, fields):
    return [f for f in fields if not (body.get(f) or "").strip()]


def _service_or_none(slug):
    if not slug:
        return None
    return Service.objects.filter(slug=slug).first()


def _service_title(service):
    return service.title if service else "—"


@require_GET
def api_services(request):
    services = list(Service.objects.filter(parent__isnull=True).values(
        "id", "slug", "title", "short_desc", "description", "icon", "price_hint"
    ))
    for s in services:
        s["subservices"] = list(
            Service.objects.filter(parent_id=s["id"]).values(
                "id", "slug", "title", "short_desc", "icon"
            )
        )
    return _json({"ok": True, "services": services})


@require_GET
def api_availability(request):
    day = request.GET.get("date", "")
    try:
        target = date.fromisoformat(day)
    except ValueError:
        return _json({"ok": False, "error": "Date invalide"}, 400)
    busy = set(
        Appointment.objects.filter(date=target)
        .exclude(status="annule")
        .values_list("time", flat=True)
    )
    available = [s for s in _slots() if s not in busy]
    return _json({"ok": True, "date": day, "slots": available})


@csrf_exempt
@require_POST
def api_contact(request):
    body = _read_body(request)
    missing = _missing(body, ["name", "email", "message"])
    if missing:
        return _json({"ok": False, "error": f"Champs manquants : {', '.join(missing)}"}, 400)

    Message.objects.create(
        name=body["name"].strip(),
        email=body["email"].strip(),
        phone=body.get("phone", "").strip(),
        subject=body.get("subject", "").strip(),
        message=body["message"].strip(),
    )
    send_auto_reply_and_notify(
        body["email"].strip(),
        "contact",
        [
            ("Nom", body["name"]),
            ("E-mail", body["email"]),
            ("Téléphone", body.get("phone", "")),
            ("Sujet", body.get("subject", "")),
            ("Message", body.get("message", "")),
        ],
    )
    return _json({"ok": True, "message": "Message envoyé. Réponse automatique envoyée par e-mail."})


@csrf_exempt
@require_POST
def api_devis(request):
    body = _read_body(request)
    missing = _missing(body, ["name", "email"])
    if missing:
        return _json({"ok": False, "error": f"Champs manquants : {', '.join(missing)}"}, 400)

    DevisRequest.objects.create(
        name=body["name"].strip(),
        email=body["email"].strip(),
        phone=body.get("phone", "").strip(),
        company=body.get("company", "").strip(),
        service=_service_or_none(body.get("service")),
        budget=body.get("budget", "").strip(),
        details=body.get("details", "").strip(),
    )
    send_auto_reply_and_notify(
        body["email"].strip(),
        "devis",
        [
            ("Nom", body["name"]),
            ("E-mail", body["email"]),
            ("Téléphone", body.get("phone", "")),
            ("Société", body.get("company", "")),
            ("Service", _service_title(_service_or_none(body.get("service")))),
            ("Budget", body.get("budget", "")),
            ("Détails", body.get("details", "")),
        ],
    )
    return _json({"ok": True, "message": "Demande de devis enregistrée. Réponse automatique envoyée par e-mail."})


@csrf_exempt
@require_POST
def api_rendezvous(request):
    body = _read_body(request)
    missing = _missing(body, ["name", "email", "date", "time"])
    if missing:
        return _json({"ok": False, "error": f"Champs manquants : {', '.join(missing)}"}, 400)

    try:
        day = date.fromisoformat(body["date"])
    except ValueError:
        return _json({"ok": False, "error": "Date invalide"}, 400)

    if day <= date.today():
        return _json({"ok": False, "error": "Choisissez une date future."}, 400)

    time = body["time"].strip()
    busy = Appointment.objects.filter(date=day).exclude(status="annule").values_list("time", flat=True)
    if time in busy:
        return _json(
            {"ok": False, "error": "Ce créneau vient d'être réservé. Veuillez en choisir un autre."}, 409
        )

    Appointment.objects.create(
        name=body["name"].strip(),
        email=body["email"].strip(),
        phone=body.get("phone", "").strip(),
        service=_service_or_none(body.get("service")),
        date=day,
        time=time,
        notes=body.get("notes", "").strip(),
    )
    send_auto_reply_and_notify(
        body["email"].strip(),
        "rendezvous",
        [
            ("Nom", body["name"]),
            ("E-mail", body["email"]),
            ("Téléphone", body.get("phone", "")),
            ("Service", _service_title(_service_or_none(body.get("service")))),
            ("Date", day.strftime("%d/%m/%Y")),
            ("Heure", time),
            ("Notes", body.get("notes", "")),
        ],
    )
    return _json({
        "ok": True,
        "message": f"Rendez-vous demandé le {day.strftime('%d/%m/%Y')} à {time}. Confirmation envoyée par e-mail.",
    })


# ---------------- API Client (Espace client) ----------------

def _bearer_token(request) -> str:
    return bearer_token(request)


def _client_from_request(request):
    return client_from_request(request)


@csrf_exempt
def api_client_register(request):
    if request.method != "POST":
        return _json({"ok": False, "error": "Méthode non autorisée"}, 405)
    result = auth_service.register(request, _read_body(request))
    return _json(result, status=result.pop("status", 200))


@csrf_exempt
def api_client_login(request):
    if request.method != "POST":
        return _json({"ok": False, "error": "Méthode non autorisée"}, 405)
    result = auth_service.login(request, _read_body(request))
    return _json(result, status=result.pop("status", 200))


@csrf_exempt
def api_client_logout(request):
    auth_service.logout(request)
    return _json({"ok": True})


@csrf_exempt
def api_client_dashboard(request):
    client = _client_from_request(request)
    if not client:
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    suivis = []
    for s in ClientServiceSuivi.objects.filter(client=client):
        tasks = [
            {
                "id": t.id,
                "titre": t.titre,
                "statut": t.get_statut_display(),
                "date_echeance": t.date_echeance.strftime("%d/%m/%Y") if t.date_echeance else "—",
                "repetition": t.get_repetition_display(),
            }
            for t in s.tasks.all()
        ]
        prefactures = [
            {"id": p.id, "numero": p.numero, "statut": p.get_statut_display()}
            for p in s.prefactures.all()
        ]
        attachments = [_attachment_payload(a, request) for a in s.attachments.all()]
        service_followups = [
            {
                "id": sf.id,
                "service": sf.service_title,
                "status": sf.get_status_display(),
                "start_date": sf.start_date.strftime("%d/%m/%Y") if sf.start_date else "—",
                "due_date": sf.due_date.strftime("%d/%m/%Y") if sf.due_date else "—",
                "notes": sf.notes,
                "tasks": [
                    {"titre": t.titre, "statut": t.get_statut_display(), "date_echeance": t.date_echeance.strftime("%d/%m/%Y") if t.date_echeance else "—"}
                    for t in sf.tasks.all()
                ],
            }
            for sf in s.service_followups.all()
        ]
        suivis.append({
            "id": s.id,
            "service": s.service_title,
            "montant": str(s.montant),
            "frequence": s.get_frequence_display(),
            "statut_paiement": s.get_statut_paiement_display(),
            "statut_service": s.get_statut_service_display(),
            "date_echeance": s.date_echeance.strftime("%d/%m/%Y") if s.date_echeance else "—",
            "commentaire": s.commentaire,
            "service_note": s.service_note,
            "tasks": tasks,
            "prefactures": prefactures,
            "attachments": attachments,
            "service_followups": service_followups,
        })
    declarations = [
        {
            "id": d.id,
            "type_declaration": d.get_type_declaration_display(),
            "periode": d.periode,
            "date_echeance_legale": d.date_echeance_legale.strftime("%d/%m/%Y"),
            "statut": d.get_statut_display(),
            "numero_quittance_ou_tej": d.numero_quittance_ou_tej or "—",
            "montant_a_payer": str(d.montant_a_payer),
            "notes_collaborateur": d.notes_collaborateur or "",
        }
        for d in DeclarationFiscale.objects.filter(client=client)
    ]
    return _json({"ok": True, "client": _client_payload(client), "suivis": suivis, "declarations": declarations})


@csrf_exempt
def api_client_prefacture(request, prefacture_id):
    client = _client_from_request(request)
    if not client:
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    pf = Prefacture.objects.filter(pk=prefacture_id, dossier__client=client).first()
    if not pf:
        return _json({"ok": False, "error": "Préfacture introuvable"}, 404)
    dossier = pf.dossier
    return _json({
        "ok": True,
        "prefacture": {
            "numero": pf.numero,
            "date": pf.date.strftime("%d/%m/%Y"),
            "montant_ht": str(pf.montant_ht),
            "taux_tva": str(pf.taux_tva),
            "montant_ttc": str(pf.montant_ttc),
            "statut": pf.get_statut_display(),
            "service": dossier.service_title,
            "frequence": dossier.get_frequence_display(),
            "description": dossier.commentaire,
        },
        "cabinet": {
            "nom": settings.SITE_NAME,
            "email": settings.SITE_EMAIL,
            "telephone": settings.SITE_PHONE,
            "adresse": settings.SITE_ADDRESS,
            "matricule": "1574T (à compléter)",
        },
        "client": {
            "nom": dossier.client.display_name,
            "adresse": dossier.client.adresse,
            "matricule_fiscale": dossier.client.matricule_fiscale,
            "cin": dossier.client.cin,
            "statut": dossier.client.get_statut_client_display(),
        },
    })


def _client_payload(client):
    return {
        "id": client.id,
        "name": client.name,
        "prenom": client.prenom,
        "display_name": f"{client.prenom} {client.name}".strip(),
        "email": client.email,
        "phone": client.phone,
        "adresse": client.adresse,
        "matricule_fiscale": client.matricule_fiscale,
        "cin": client.cin,
    }


@csrf_exempt
def api_client_create_dossier(request):
    client = _client_from_request(request)
    if not client:
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    if request.method != "POST":
        return _json({"ok": False, "error": "Méthode non autorisée"}, 405)
    body = _read_body(request)
    try:
        service = Service.objects.get(pk=int(body.get("type_service", 0)))
    except (ValueError, Service.DoesNotExist):
        return _json({"ok": False, "error": "Service introuvable."}, 400)
    description = (body.get("description") or "").strip()
    if not description:
        return _json({"ok": False, "error": "Décrivez votre besoin."}, 400)
    obj = ClientServiceSuivi.objects.create(
        client=client,
        type_service=service,
        montant=0,
        statut_paiement="en_attente",
        statut_service="en_cours",
        commentaire=description,
        service_note=(body.get("service_note") or "").strip(),
    )
    return _json({"ok": True, "id": obj.id, "message": "Dossier ouvert. Le cabinet vous répondra rapidement."})


@csrf_exempt
def api_client_update_dossier(request, dossier_id):
    client = _client_from_request(request)
    if not client:
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    dossier = ClientServiceSuivi.objects.filter(pk=dossier_id, client=client).first()
    if not dossier:
        return _json({"ok": False, "error": "Dossier introuvable"}, 404)
    if request.method != "PUT":
        return _json({"ok": False, "error": "Méthode non autorisée"}, 405)
    if dossier.statut_service != "en_cours":
        return _json({"ok": False, "error": "Modification possible uniquement pour un dossier en cours de traitement."}, 400)
    body = _read_body(request)
    fields_to_update = []
    if "description" in body:
        description = (body.get("description") or "").strip()
        if not description:
            return _json({"ok": False, "error": "La note du dossier ne peut pas être vide."}, 400)
        dossier.commentaire = description
        fields_to_update.append("commentaire")
    if "service_note" in body:
        dossier.service_note = (body.get("service_note") or "").strip()
        fields_to_update.append("service_note")
    if fields_to_update:
        dossier.save(update_fields=fields_to_update)
    return _json({"ok": True, "message": "Dossier modifié."})


@csrf_exempt
def api_client_profile(request):
    client = _client_from_request(request)
    if not client:
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    if request.method != "PUT":
        return _json({"ok": False, "error": "Méthode non autorisée"}, 405)
    body = _read_body(request)

    def _clean(key, maxlen=200):
        return (body.get(key) or "").strip()[:maxlen]

    if "name" in body:
        if not _clean("name"):
            return _json({"ok": False, "error": "Le nom est obligatoire."}, 400)
        client.name = _clean("name")
    if "prenom" in body:
        client.prenom = _clean("prenom")
    if "phone" in body:
        client.phone = _clean("phone", 30)
    if "adresse" in body:
        client.adresse = _clean("adresse", 300)
    if "matricule_fiscale" in body:
        client.matricule_fiscale = _clean("matricule_fiscale", 50)
    if "cin" in body:
        client.cin = _clean("cin", 50)
    if body.get("new_password"):
        old = body.get("old_password") or ""
        if not client.user or not client.user.check_password(old):
            return _json({"ok": False, "error": "Mot de passe actuel incorrect."}, 400)
        if len(body["new_password"]) < 6:
            return _json({"ok": False, "error": "Le nouveau mot de passe doit faire au moins 6 caractères."}, 400)
        client.user.set_password(body["new_password"])
        client.user.save()
    client.save()
    return _json({"ok": True, "message": "Profil mis à jour."})


@csrf_exempt
def api_client_entreprise(request):
    client = _client_from_request(request)
    if not client:
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    if request.method == "GET":
        if hasattr(client, "entreprise"):
            return _json({"ok": True, "entreprise": _entreprise_payload(client.entreprise)})
        return _json({"ok": True, "entreprise": None})
    if request.method == "PUT":
        body = _read_body(request)
        entreprise, created = Entreprise.objects.get_or_create(client=client)
        if created:
            comptabilite.plan_init(entreprise)
        for field in ("raison_sociale", "matricule_fiscale", "registre_commerce", "forme_juridique", "activite", "adresse", "code_postal", "ville", "telephone", "email", "representant_legal", "notes"):
            if field in body:
                val = (str(body.get(field)) or "").strip()[:300]
                if field == "forme_juridique" and val and val not in {f for f, _ in Entreprise.FORME_CHOICES}:
                    return _json({"ok": False, "error": "Forme juridique invalide."}, 400)
                setattr(entreprise, field, val)
        entreprise.save()
        return _json({"ok": True, "message": "Entreprise mise à jour.", "entreprise": _entreprise_payload(entreprise)})
    return _json({"ok": False, "error": "Méthode non autorisée"}, 405)


@csrf_exempt
def api_client_attachments(request, dossier_id):
    client = _client_from_request(request)
    if not client:
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    dossier = ClientServiceSuivi.objects.filter(pk=dossier_id, client=client).first()
    if not dossier:
        return _json({"ok": False, "error": "Dossier introuvable"}, 404)
    if request.method != "POST":
        return _json({"ok": False, "error": "Méthode non autorisée"}, 405)
    f = request.FILES.get("file")
    if not f:
        return _json({"ok": False, "error": "Aucun fichier reçu."}, 400)
    if f.size > settings.MAX_UPLOAD_SIZE:
        return _json({"ok": False, "error": "Fichier trop volumineux (20 Mo max)."}, 400)
    name = f.name or "fichier"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    allowed = {e for exts in ALLOWED_UPLOAD_EXTENSIONS.values() for e in exts}
    if ext not in allowed:
        return _json({"ok": False, "error": "Format non autorisé (image, pdf, Office, txt, zip, audio, vidéo)."}, 400)
    att = DossierAttachment.objects.create(
        dossier=dossier,
        file=f,
        original_name=name[:255],
        content_type=f.content_type or "",
        size=f.size,
        uploaded_by="client",
    )
    return _json({"ok": True, "attachment": _attachment_payload(att, request), "message": "Fichier ajouté au dossier."})


@csrf_exempt
def api_client_attachment_delete(request, attachment_id):
    client = _client_from_request(request)
    if not client:
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    att = DossierAttachment.objects.filter(pk=attachment_id, dossier__client=client).first()
    if not att:
        return _json({"ok": False, "error": "Fichier introuvable"}, 404)
    if request.method != "DELETE":
        return _json({"ok": False, "error": "Méthode non autorisée"}, 405)
    if att.uploaded_by != "client":
        return _json({"ok": False, "error": "Seuls les fichiers ajoutés par vous peuvent être supprimés."}, 400)
    att.file.delete(save=False)
    att.delete()
    return _json({"ok": True, "message": "Fichier supprimé."})


@csrf_exempt
def _message_payload(m):
    return {
        "id": m.id,
        "direction": m.direction,
        "text": m.text,
        "created_at": m.created_at.strftime("%d/%m/%Y %H:%M"),
        "dossier_id": m.dossier_id,
        "dossier_service": m.dossier_service,
        "service_id": m.service_id,
        "service_title": m.service_title,
        "task_id": m.task_id,
        "task_title": m.task_title,
        "context_label": m.context_label,
    }


def api_client_messages(request):
    client = _client_from_request(request)
    if not client:
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    if request.method == "GET":
        queryset = ClientMessage.objects.filter(client=client)
        dossier = request.GET.get("dossier", "").strip()
        task = request.GET.get("task", "").strip()
        service = request.GET.get("service", "").strip()
        if dossier.isdigit():
            queryset = queryset.filter(dossier_id=int(dossier))
        if task.isdigit():
            queryset = queryset.filter(task_id=int(task))
        if service.isdigit():
            queryset = queryset.filter(service_id=int(service))
        return _json({"ok": True, "messages": [_message_payload(m) for m in queryset]})
    if request.method == "POST":
        text = (request.body or b"").decode("utf-8", "replace")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {}
        text = (payload.get("text") or "").strip()
        if not text:
            return _json({"ok": False, "error": "Message vide."}, 400)
        dossier = None
        service = None
        task = None
        if (payload.get("dossier") or "").strip().isdigit():
            dossier = ClientServiceSuivi.objects.filter(pk=int(payload["dossier"]), client=client).first()
            if not dossier:
                return _json({"ok": False, "error": "Dossier introuvable pour ce compte."}, 400)
        if (payload.get("service") or "").strip().isdigit():
            service = Service.objects.filter(pk=int(payload["service"])).first()
            if not service:
                return _json({"ok": False, "error": "Service introuvable."}, 400)
        if (payload.get("task") or "").strip().isdigit():
            task = DossierTask.objects.filter(pk=int(payload["task"]), dossier__client=client).first()
            if not task:
                return _json({"ok": False, "error": "Tâche introuvable pour ce compte."}, 400)
            if dossier and task.dossier_id != dossier.id:
                return _json({"ok": False, "error": "La tâche n'appartient pas au dossier sélectionné."}, 400)
        if not service and dossier:
            service = dossier.type_service
        ClientMessage.objects.create(
            client=client, direction="client", text=text,
            dossier=dossier, service=service, task=task,
        )
        return _json({"ok": True, "message": "Message envoyé."})
    return _json({"ok": False, "error": "Méthode non autorisée"}, 405)


# ---------------- API Admin (jeton Bearer + RBAC) ----------------

def _authorized(request) -> bool:
    """Le jeton admin statique ou un jeton staff valide suffit."""
    return role_level_for_request(request) > 0


# Matrice RBAC : (niveau lecture, niveau écriture) par table admin.
ACCESS_LEVELS = {
    "devis_requests": (40, 60),
    "appointments": (40, 60),
    "messages": (40, 60),
    "types_service": (40, 80),
    "clients": (40, 80),
    "client_service_suivis": (40, 80),
    "client_messages": (40, 80),
    "dossier_tasks": (40, 80),
    "dossier_attachments": (40, 80),
    "service_followups": (40, 80),
    "prefactures": (60, 80),
    "declarations": (40, 80),
    "payments": (60, 80),
    "collaborateurs": (80, 100),
    "entreprises": (40, 60),
    "comptes": (60, 60),
    "ecritures": (60, 60),
}


def _table_allowed(request, table) -> bool:
    """Autorisation RBAC pour une table donnée (lecture vs écriture)."""
    read_level, write_level = ACCESS_LEVELS.get(table, (40, 80))
    needed = read_level if request.method == "GET" else write_level
    return role_level_for_request(request) >= needed


TABLES = {
    "devis_requests": (DevisRequest, ["id", "name", "email", "phone", "company", "budget", "details", "status", "created_at"], "service_title"),
    "appointments": (Appointment, ["id", "name", "email", "phone", "date", "time", "notes", "status"], "service_title"),
    "messages": (Message, ["id", "name", "email", "phone", "subject", "message", "status", "created_at"], None),
    "clients": (Client, ["id", "name", "prenom", "email", "phone", "company", "adresse", "statut_client", "matricule_fiscale", "cin", "notes", "created_at"], None),
    "payments": (Payment, ["id", "client_name", "dossier_service", "amount", "date", "status", "method", "notes", "created_at"], None),
    "service_followups": (ServiceFollowUp, ["id", "client_name", "service_title", "dossier_id", "dossier_label", "collaborateur_id", "collaborateur_name", "status", "start_date", "due_date", "notes", "created_at"], None),
    "types_service": (Service, ["id", "title", "slug", "short_desc", "parent_title"], None),
    "client_service_suivis": (ClientServiceSuivi, ["id", "client_name", "service_title", "montant", "statut_paiement", "statut_service", "date_echeance", "frequence", "commentaire", "service_note"], None),
    "client_messages": (ClientMessage, ["id", "client_name", "dossier_service", "service_title", "task_title", "direction", "text", "created_at"], None),
    "dossier_tasks": (DossierTask, ["id", "client_name", "dossier_service", "followup_title", "titre", "statut", "date_echeance", "repetition"], None),
    "prefactures": (Prefacture, ["id", "client_name", "dossier_service", "numero", "date", "montant_ht", "taux_tva", "montant_ttc", "statut"], None),
    "dossier_attachments": (DossierAttachment, ["id", "client_name", "dossier_service", "original_name", "category", "size", "uploaded_by", "created_at"], None),
    "declarations": (DeclarationFiscale, ["id", "client_name", "dossier_service", "type_declaration", "periode", "date_echeance_legale", "statut", "numero_quittance_ou_tej", "montant_a_payer", "notes_collaborateur"], None),
    "collaborateurs": (Collaborateur, ["id", "display_name", "fonction", "email", "telephone", "actif", "notes", "created_at"], None),
    "entreprises": (Entreprise, ["id", "client_id", "client_name", "raison_sociale", "matricule_fiscale", "registre_commerce", "forme_juridique", "activite", "adresse", "code_postal", "ville", "telephone", "email", "representant_legal", "notes", "updated_at"], None),
    "comptes": (CompteComptable, ["id", "entreprise_name", "classe", "niveau", "parent_id", "parent_label", "numero", "intitule", "active"], None),
    "ecritures": (EcritureComptable, ["id", "entreprise_name", "journal", "numero_piece", "date", "libelle", "statut", "total_debit", "total_credit", "equilibree", "nb_lignes"], None),
}


@csrf_exempt
def api_admin(request, table):
    if not _authorized(request):
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    spec = TABLES.get(table)
    if not spec:
        return _json({"ok": False, "error": "Table inconnue"}, 400)
    if not _table_allowed(request, table):
        return _json({"ok": False, "error": "Privilèges insuffisants pour cette table."}, 403)

    model, fields, extra = spec
    if request.method == "GET":
        queryset = model.objects.all()
        q = request.GET.get("q", "").strip()
        if q:
            try:
                queryset = queryset.filter(id=int(q))
            except ValueError:
                queryset = queryset.none()
        if table == "dossier_tasks":
            client_id = request.GET.get("client", "").strip()
            statut = request.GET.get("statut", "").strip()
            followup = request.GET.get("followup", "").strip()
            if client_id.isdigit():
                queryset = queryset.filter(dossier__client_id=int(client_id))
            if statut:
                queryset = queryset.filter(statut=statut)
            if followup.isdigit():
                queryset = queryset.filter(service_followup_id=int(followup))
        if table == "client_messages":
            client_id = request.GET.get("client", "").strip()
            dossier = request.GET.get("dossier", "").strip()
            service = request.GET.get("service", "").strip()
            task = request.GET.get("task", "").strip()
            if client_id.isdigit():
                queryset = queryset.filter(client_id=int(client_id))
            if dossier.isdigit():
                queryset = queryset.filter(dossier_id=int(dossier))
            if service.isdigit():
                queryset = queryset.filter(service_id=int(service))
            if task.isdigit():
                queryset = queryset.filter(task_id=int(task))
        if table == "service_followups":
            collab = request.GET.get("collaborateur", "").strip()
            if collab.isdigit():
                queryset = queryset.filter(collaborateur_id=int(collab))
        if table in ("comptes", "ecritures"):
            ent = request.GET.get("entreprise", "").strip()
            if ent.isdigit():
                queryset = queryset.filter(entreprise_id=int(ent))
        if table == "client_messages":
            queryset = queryset.order_by("-created_at")
        items = []
        for obj in queryset:
            item = {f: getattr(obj, f, "") for f in fields}
            if table == "entreprises":
                item["client_name"] = obj.client.display_name
            if table == "comptes":
                item["entreprise_name"] = obj.entreprise.raison_sociale
                item["parent_label"] = f"{obj.parent.numero} — {obj.parent.intitule}" if obj.parent else "—"
            if table == "ecritures":
                item["entreprise_name"] = obj.entreprise.raison_sociale
                item["total_debit"] = str(obj.total_debit)
                item["total_credit"] = str(obj.total_credit)
                item["equilibree"] = obj.est_equilibree
                item["nb_lignes"] = obj.lignes.count()
                item["lignes"] = [
                    {"id": l.id, "compte_id": l.compte_id, "numero": l.compte.numero, "intitule": l.compte.intitule, "libelle": l.libelle, "debit": str(l.debit), "credit": str(l.credit)}
                    for l in obj.lignes.select_related("compte").all()
                ]
            if extra:
                item[extra] = getattr(obj, extra, "—")
            if table == "dossier_attachments":
                item["url"] = request.build_absolute_uri(obj.file.url)
            items.append(item)
        return _json({"ok": True, "items": items})

    if request.method == "PUT":
        body = _read_body(request)
        try:
            obj = model.objects.get(pk=int(body.get("id", 0)))
        except (ValueError, model.DoesNotExist):
            return _json({"ok": False, "error": "Élément introuvable"}, 404)
        field = body.get("field", "status")
        value = body.get("status", "")

        def _valid_choices(obj, field):
            if field in ("statut_paiement",):
                return {s for s, _ in obj.STATUT_PAIEMENT_CHOICES}
            if field in ("statut_service",):
                return {s for s, _ in obj.STATUT_SERVICE_CHOICES}
            if field in ("frequence",):
                return {s for s, _ in obj.FREQUENCE_CHOICES}
            if field in ("repetition",):
                return {s for s, _ in obj.REPETITION_CHOICES}
            if field in ("type_declaration",):
                return {s for s, _ in obj.TYPE_DECLARATION_CHOICES}
            if field in ("status", "statut"):
                attr = "STATUT_CHOICES" if hasattr(obj, "STATUT_CHOICES") else "STATUS_CHOICES"
                return {s for s, _ in getattr(obj, attr, [])}
            return None

        valid = _valid_choices(obj, field)
        if valid is not None:
            if value not in valid:
                return _json({"ok": False, "error": "Statut invalide"}, 400)
        elif field in ("montant", "taux_tva", "montant_a_payer"):
            try:
                value = float(value)
            except ValueError:
                return _json({"ok": False, "error": "Valeur invalide"}, 400)
        elif field == "date_echeance" or field == "date_echeance_legale" or field == "start_date" or field == "due_date":
            try:
                date.fromisoformat(value)
            except ValueError:
                return _json({"ok": False, "error": "Date invalide (AAAA-MM-JJ)"}, 400)
        elif field in ("commentaire", "notes", "numero_quittance_ou_tej", "notes_collaborateur", "service_note", "titre", "description", "periode"):
            value = str(value)
        elif table == "service_followups" and field == "collaborateur":
            raw = str(value).strip()
            collab = None
            if raw.isdigit():
                collab = Collaborateur.objects.filter(pk=int(raw)).first()
                if not collab:
                    return _json({"ok": False, "error": "Collaborateur introuvable."}, 400)
            value = collab
        elif table == "collaborateurs" and field in ("nom", "prenom", "email", "telephone", "fonction", "notes"):
            value = str(value)
            if field == "email" and not value.strip():
                return _json({"ok": False, "error": "E-mail requis."}, 400)
            if field == "email":
                value = value.strip().lower()
                if Collaborateur.objects.exclude(pk=obj.pk).filter(email__iexact=value).exists():
                    return _json({"ok": False, "error": "Un collaborateur existe déjà avec cet e-mail."}, 400)
        elif table == "collaborateurs" and field == "actif":
            value = value in ("1", "true", "True", "on")
        elif table == "types_service" and field in ("title", "short_desc", "slug", "price_hint", "icon"):
            value = str(value)
            if field == "slug":
                slug = value.strip().lower().replace(" ", "-")
                if Service.objects.exclude(pk=obj.pk).filter(slug=slug).exists():
                    return _json({"ok": False, "error": "Un service existe déjà avec cet identifiant."}, 400)
                value = slug
        elif table == "types_service" and field == "parent":
            raw = str(value).strip()
            parent = None
            if raw.isdigit():
                parent = Service.objects.filter(pk=int(raw)).first()
                if not parent:
                    return _json({"ok": False, "error": "Service parent introuvable."}, 400)
                if parent.pk == obj.pk:
                    return _json({"ok": False, "error": "Un service ne peut pas être son propre parent."}, 400)
            value = parent
        elif table == "clients" and field in ("name", "prenom", "email", "phone", "company", "adresse", "statut_client", "matricule_fiscale", "cin", "notes"):
            value = str(value)
            if field == "name" and not value.strip():
                return _json({"ok": False, "error": "Nom requis."}, 400)
            if field == "statut_client" and value not in {s for s, _ in Client.STATUT_CHOICES}:
                return _json({"ok": False, "error": "Type de client invalide."}, 400)
        elif table == "entreprises" and field in ("raison_sociale", "matricule_fiscale", "registre_commerce", "forme_juridique", "activite", "adresse", "code_postal", "ville", "telephone", "email", "representant_legal", "notes"):
            value = str(value)
            if field == "forme_juridique" and value and value not in {f for f, _ in Entreprise.FORME_CHOICES}:
                return _json({"ok": False, "error": "Forme juridique invalide."}, 400)
        elif table == "comptes" and field in ("numero", "intitule"):
            value = str(value)
            if field == "numero":
                numero = value.strip()
                if not numero:
                    return _json({"ok": False, "error": "Numéro requis."}, 400)
                if CompteComptable.objects.filter(entreprise=obj.entreprise, numero=numero).exclude(pk=obj.pk).exists():
                    return _json({"ok": False, "error": "Un compte existe déjà avec ce numéro."}, 400)
                value = numero
        elif table == "comptes" and field == "active":
            value = value in ("1", "true", "True", "on")
        elif table == "comptes" and field == "parent":
            raw = str(value).strip()
            parent = None
            if raw.isdigit():
                parent = CompteComptable.objects.filter(pk=int(raw), entreprise=obj.entreprise).first()
                if not parent:
                    return _json({"ok": False, "error": "Compte parent introuvable."}, 400)
                if parent.pk == obj.pk:
                    return _json({"ok": False, "error": "Un compte ne peut pas être son propre parent."}, 400)
                anc = parent
                while anc.parent_id:
                    anc = anc.parent
                    if anc.pk == obj.pk:
                        return _json({"ok": False, "error": "Le parent ne peut pas être un descendant de ce compte."}, 400)
            value = parent
        elif table == "ecritures" and field in ("journal", "numero_piece", "date", "libelle", "statut"):
            if field == "journal" and value not in {j for j, _ in EcritureComptable.JOURNAL_CHOICES}:
                return _json({"ok": False, "error": "Journal invalide."}, 400)
            if field == "statut" and value not in {s for s, _ in EcritureComptable.STATUT_CHOICES}:
                return _json({"ok": False, "error": "Statut invalide."}, 400)
            if field == "date":
                try:
                    date.fromisoformat(value)
                except ValueError:
                    return _json({"ok": False, "error": "Date invalide (AAAA-MM-JJ)."}, 400)
            value = str(value)
        else:
            return _json({"ok": False, "error": "Champ non modifiable"}, 400)
        if not hasattr(obj, field):
            return _json({"ok": False, "error": "Champ invalide"}, 400)
        setattr(obj, field, value)
        obj.save(update_fields=[field])
        return _json({"ok": True})

    if request.method == "DELETE":
        body = _read_body(request)
        try:
            obj = model.objects.get(pk=int(body.get("id", 0)))
        except (ValueError, model.DoesNotExist):
            return _json({"ok": False, "error": "Élément introuvable"}, 404)
        if table == "types_service":
            if obj.subservices.exists():
                return _json({"ok": False, "error": "Supprimez d'abord les sous-services liés à ce service."}, 400)
            try:
                obj.delete()
            except ProtectedError:
                return _json({"ok": False, "error": "Ce service est utilisé par des dossiers clients : suppression impossible."}, 400)
            return _json({"ok": True, "message": "Service supprimé."})
        if table in ("client_messages", "client_service_suivis", "dossier_tasks", "service_followups", "prefactures", "dossier_attachments", "declarations", "payments", "devis_requests", "appointments", "messages", "collaborateurs", "entreprises", "clients", "comptes", "ecritures"):
            try:
                obj.delete()
            except ProtectedError:
                return _json({"ok": False, "error": "Élément utilisé ailleurs : suppression impossible."}, 400)
            return _json({"ok": True, "message": "Élément supprimé."})
        return _json({"ok": False, "error": "Suppression non disponible pour cette table."}, 400)

    if request.method == "POST":
        return _api_admin_create(request, table)

    return _json({"ok": False, "error": "Méthode non autorisée"}, 405)


@csrf_exempt
def api_admin_dashboard(request):
    if not _authorized(request):
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    followups = ServiceFollowUp.objects.select_related("client", "service", "collaborateur")[:8]
    recent_followups = [
        {
            "id": f.id,
            "client_name": f.client.display_name,
            "service_title": f.service_title,
            "collaborateur_name": f.collaborateur_name,
            "status": f.get_status_display(),
            "due_date": f.due_date.strftime("%d/%m/%Y") if f.due_date else "—",
        }
        for f in followups
    ]
    msgs = ClientMessage.objects.select_related("client", "dossier").order_by("-created_at")[:6]
    recent_messages = [
        {
            "id": m.id,
            "client_name": m.client.display_name,
            "direction": m.direction,
            "text": m.text[:120],
            "context_label": m.context_label,
            "created_at": m.created_at.strftime("%d/%m/%Y %H:%M"),
        }
        for m in msgs
    ]
    pays = Payment.objects.select_related("client")[:6]
    recent_payments = [
        {
            "id": p.id,
            "client_name": p.client_name,
            "amount": str(p.amount),
            "date": p.date.strftime("%d/%m/%Y"),
            "status": p.get_status_display(),
        }
        for p in pays
    ]
    counts = {
        "devis_nouveaux": DevisRequest.objects.filter(status="nouveau").count(),
        "messages_nouveaux": Message.objects.filter(status="nouveau").count(),
        "messages_clients": ClientMessage.objects.count(),
        "clients": Client.objects.count(),
        "dossiers_actifs": ClientServiceSuivi.objects.exclude(statut_service="cloture").count(),
        "paiements_retard": Payment.objects.filter(status__in=["retard", "en_attente"]).count(),
        "declarations_retard": DeclarationFiscale.objects.filter(statut="retard").count(),
        "suivis_en_cours": ServiceFollowUp.objects.filter(status="en_cours").count(),
        "collaborateurs_actifs": Collaborateur.objects.filter(actif=True).count(),
    }

    # Notifications chronologiques : messages clients sans réponse + tâches à faire
    # Thread = dossier (ou tâche) ; un message général sans contexte est son propre fil.
    grouped = (
        ClientMessage.objects.filter(Q(dossier__isnull=False) | Q(task__isnull=False))
        .values("dossier_id", "task_id")
        .annotate(last=Max("pk"))
    )
    unanswered_ids = list(
        ClientMessage.objects.filter(dossier__isnull=True, task__isnull=True).values_list("pk", flat=True)
    )
    unanswered_ids += [d["last"] for d in grouped]
    pending_messages = ClientMessage.objects.filter(
        pk__in=unanswered_ids, direction="client"
    ).select_related("client", "dossier", "service", "task")
    feed = [
        {
            "kind": "message",
            "sort_date": m.created_at.isoformat(),
            "date": m.created_at.strftime("%d/%m/%Y %H:%M"),
            "id": m.id,
            "client_name": m.client.display_name,
            "text": m.text[:140],
            "context_label": m.context_label,
            "dossier_id": m.dossier_id,
            "service_id": m.service_id,
            "task_id": m.task_id,
        }
        for m in pending_messages
    ]
    for t in DossierTask.objects.filter(statut__in=["a_faire", "en_cours"]).select_related(
        "dossier__client", "service_followup"
    ):
        due = t.date_echeance or t.created_at.date()
        feed.append({
            "kind": "tache",
            "sort_date": due.isoformat(),
            "date": due.strftime("%d/%m/%Y"),
            "id": t.id,
            "client_name": t.dossier.client.display_name,
            "titre": t.titre,
            "statut": t.get_statut_display(),
            "statut_code": t.statut,
            "dossier_service": t.dossier.service_title,
            "dossier_id": t.dossier_id,
            "followup_title": t.followup_title,
            "overdue": bool(t.date_echeance and t.date_echeance < date.today() and t.statut != "termine"),
        })
    feed.sort(key=lambda x: x["sort_date"])
    return _json({
        "ok": True,
        "counts": counts,
        "recent_followups": recent_followups,
        "recent_messages": recent_messages,
        "recent_payments": recent_payments,
        "notifications": feed,
        "notifications_counts": {
            "messages": sum(1 for x in feed if x["kind"] == "message"),
            "taches": sum(1 for x in feed if x["kind"] == "tache"),
        },
    })


@csrf_exempt
def api_admin_explorer(request, client_id=None):
    if not _authorized(request):
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    if client_id is None:
        clients = [
            {
                "id": c.id,
                "name": c.display_name,
                "email": c.email,
                "phone": c.phone,
                "dossier_count": c.services.count(),
            }
            for c in Client.objects.prefetch_related("services").order_by("name", "id")
        ]
        return _json({"ok": True, "clients": clients})
    client = Client.objects.filter(pk=client_id).first()
    if not client:
        return _json({"ok": False, "error": "Client introuvable"}, 404)
    dossiers = []
    for d in ClientServiceSuivi.objects.filter(client=client).prefetch_related("tasks", "prefactures", "attachments", "messages", "declarations", "payments"):
        dossiers.append({
            "id": d.id,
            "service": d.service_title,
            "service_id": d.type_service.id if d.type_service else None,
            "montant": str(d.montant),
            "frequence": d.get_frequence_display(),
            "statut_paiement": d.get_statut_paiement_display(),
            "statut_service": d.get_statut_service_display(),
            "date_echeance": d.date_echeance.strftime("%d/%m/%Y") if d.date_echeance else "—",
            "commentaire": d.commentaire,
            "task_count": d.tasks.count(),
            "followup_count": d.service_followups.count(),
            "prefacture_count": d.prefactures.count(),
            "attachment_count": d.attachments.count(),
            "message_count": d.messages.count(),
            "declaration_count": d.declarations.count(),
            "payment_count": d.payments.count(),
        })
    return _json({
        "ok": True,
        "client": {
            "id": client.id,
            "name": client.display_name,
            "email": client.email,
            "phone": client.phone,
            "matricule_fiscale": client.matricule_fiscale,
            "cin": client.cin,
            "adresse": client.adresse,
            "notes": client.notes,
        },
        "dossiers": dossiers,
    })


def _task_payload(t):
    return {
        "id": t.id,
        "titre": t.titre,
        "description": t.description,
        "statut": t.get_statut_display(),
        "date_echeance": t.date_echeance.strftime("%d/%m/%Y") if t.date_echeance else "—",
        "repetition": t.get_repetition_display(),
        "dossier_id": t.dossier_id,
        "dossier_service": t.dossier_service,
        "followup_id": t.followup_id,
        "followup_title": t.followup_title,
    }


def _dossier_payload(d):
    return {
        "id": d.id,
        "client_id": d.client.id,
        "client_name": d.client.display_name,
        "client_contact": f"{d.client.email} · {d.client.phone}",
        "service": d.service_title,
        "service_id": d.type_service.id if d.type_service else None,
        "montant": str(d.montant),
        "frequence": d.get_frequence_display(),
        "statut_paiement": d.get_statut_paiement_display(),
        "statut_service": d.get_statut_service_display(),
        "date_echeance": d.date_echeance.strftime("%d/%m/%Y") if d.date_echeance else "—",
        "commentaire": d.commentaire,
        "service_note": d.service_note,
        "tasks": [_task_payload(t) for t in d.tasks.all()],
        "prefactures": [
            {"id": p.id, "numero": p.numero, "date": p.date.strftime("%d/%m/%Y"), "montant_ttc": str(p.montant_ttc), "statut": p.get_statut_display()}
            for p in d.prefactures.all()
        ],
        "service_followups": [
            {
                "id": s.id,
                "service": s.service_title,
                "status": s.get_status_display(),
                "start_date": s.start_date.strftime("%d/%m/%Y") if s.start_date else "—",
                "due_date": s.due_date.strftime("%d/%m/%Y") if s.due_date else "—",
                "notes": s.notes,
                "tasks": [_task_payload(t) for t in s.dossier_tasks],
            }
            for s in d.service_followups.all()
        ],
        "attachments": [
            {
                "id": a.id,
                "name": a.original_name,
                "url": a.file.url,
                "size": a.size_display,
                "category": a.category,
                "uploaded_by": a.get_uploaded_by_display(),
            }
            for a in d.attachments.all()
        ],
        "messages": [
            {
                "id": m.id,
                "direction": m.direction,
                "text": m.text,
                "created_at": m.created_at.strftime("%d/%m/%Y %H:%M"),
                "context_label": m.context_label,
            }
            for m in d.messages.all()
        ],
        "declarations": [
            {
                "id": df.id,
                "type_declaration": df.get_type_declaration_display(),
                "periode": df.periode,
                "date_echeance_legale": df.date_echeance_legale.strftime("%d/%m/%Y"),
                "statut": df.get_statut_display(),
                "montant_a_payer": str(df.montant_a_payer),
                "numero_quittance_ou_tej": df.numero_quittance_ou_tej or "—",
            }
            for df in d.declarations.all()
        ],
        "payments": [
            {
                "id": p.id,
                "amount": str(p.amount),
                "date": p.date.strftime("%d/%m/%Y"),
                "status": p.get_status_display(),
            }
            for p in d.payments.all()
        ],
    }


def _entreprise_payload(e):
    return {
        "id": e.id,
        "client_id": e.client_id,
        "raison_sociale": e.raison_sociale,
        "matricule_fiscale": e.matricule_fiscale,
        "registre_commerce": e.registre_commerce,
        "forme_juridique": e.forme_juridique,
        "activite": e.activite,
        "adresse": e.adresse,
        "code_postal": e.code_postal,
        "ville": e.ville,
        "telephone": e.telephone,
        "email": e.email,
        "representant_legal": e.representant_legal,
        "notes": e.notes,
        "created_at": e.created_at.strftime("%d/%m/%Y"),
        "updated_at": e.updated_at.strftime("%d/%m/%Y"),
    }


@csrf_exempt
def api_admin_fiche(request, client_id):
    if not _authorized(request):
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    client = Client.objects.filter(pk=client_id).first()
    if not client:
        return _json({"ok": False, "error": "Client introuvable"}, 404)

    if request.method == "PUT":
        body = _read_body(request)

        def _c(key, maxlen=200):
            return (body.get(key) or "").strip()[:maxlen]

        for field in ("name", "prenom", "email", "phone", "company", "adresse", "statut_client", "matricule_fiscale", "cin", "notes"):
            if field in body:
                value = _c(field, 300 if field in ("adresse", "notes") else 200)
                if field == "name" and not value:
                    return _json({"ok": False, "error": "Nom requis."}, 400)
                if field == "statut_client" and value not in {s for s, _ in Client.STATUT_CHOICES}:
                    return _json({"ok": False, "error": "Type de client invalide."}, 400)
                setattr(client, field, value)
        client.save()
        ent = body.get("entreprise") or {}
        if isinstance(ent, dict) and ent:
            entreprise, _ = Entreprise.objects.get_or_create(client=client)
            for field in ("raison_sociale", "matricule_fiscale", "registre_commerce", "forme_juridique", "activite", "adresse", "code_postal", "ville", "telephone", "email", "representant_legal", "notes"):
                if field in ent:
                    val = (str(ent.get(field)) or "").strip()[:300]
                    if field == "forme_juridique" and val and val not in {f for f, _ in Entreprise.FORME_CHOICES}:
                        return _json({"ok": False, "error": "Forme juridique invalide."}, 400)
                    setattr(entreprise, field, val)
            entreprise.save()
        return _json({"ok": True, "message": "Fiche mise à jour."})

    if request.method == "POST":
        entreprise, created = Entreprise.objects.get_or_create(client=client)
        if created:
            comptabilite.plan_init(entreprise)
        return _json({"ok": True, "created": created, "entreprise": _entreprise_payload(entreprise)})

    dossiers = []
    for d in ClientServiceSuivi.objects.filter(client=client).prefetch_related("tasks", "prefactures", "attachments", "messages", "declarations", "payments"):
        dossiers.append({
            "id": d.id,
            "service": d.service_title,
            "montant": str(d.montant),
            "frequence": d.get_frequence_display(),
            "statut_paiement": d.get_statut_paiement_display(),
            "statut_service": d.get_statut_service_display(),
            "date_echeance": d.date_echeance.strftime("%d/%m/%Y") if d.date_echeance else "—",
            "task_count": d.tasks.count(),
            "followup_count": d.service_followups.count(),
            "prefacture_count": d.prefactures.count(),
            "declaration_count": d.declarations.count(),
            "payment_count": d.payments.count(),
            "message_count": d.messages.count(),
        })
    unanswered_ids = [
        d["last"]
        for d in ClientMessage.objects.filter(client=client)
        .values("dossier_id", "task_id")
        .annotate(last=Max("pk"))
    ]
    return _json({
        "ok": True,
        "client": {
            "id": client.id,
            "name": client.name,
            "prenom": client.prenom,
            "display_name": client.display_name,
            "email": client.email,
            "phone": client.phone,
            "company": client.company,
            "adresse": client.adresse,
            "statut_client": client.statut_client,
            "matricule_fiscale": client.matricule_fiscale,
            "cin": client.cin,
            "notes": client.notes,
            "created_at": client.created_at.strftime("%d/%m/%Y"),
            "has_account": bool(client.user_id),
        },
        "entreprise": _entreprise_payload(client.entreprise) if hasattr(client, "entreprise") else None,
        "dossiers": dossiers,
        "stats": {
            "dossiers_actifs": ClientServiceSuivi.objects.filter(client=client).exclude(statut_service="cloture").count(),
            "declarations_en_retard": DeclarationFiscale.objects.filter(client=client, statut="retard").count(),
            "paiements_en_attente": Payment.objects.filter(client=client, status__in=["en_attente", "retard"]).count(),
            "messages_sans_reponse": ClientMessage.objects.filter(pk__in=unanswered_ids, direction="client").count(),
        },
    })


def _comptabilite_entreprise(entreprise_id):
    return comptabilite.entreprise_for_id(entreprise_id)


def _validated_lignes(entreprise, request):
    frm = request.GET.get("from") or ""
    to = request.GET.get("to") or ""
    return comptabilite.validated_lignes(
        entreprise,
        from_date=comptabilite.parse_date(frm),
        to_date=comptabilite.parse_date(to),
    )


@csrf_exempt
@require_level(60)  # comptable et au-dessus
def api_admin_plan(request, entreprise_id):
    if not _authorized(request):
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    entreprise = _comptabilite_entreprise(entreprise_id)
    if not entreprise:
        return _json({"ok": False, "error": "Entreprise introuvable"}, 404)
    return _json({
        "ok": True,
        "entreprise": {"id": entreprise.id, "raison_sociale": entreprise.raison_sociale},
        "plan": comptabilite.plan_tree(entreprise),
        "total": entreprise.comptes.count(),
    })


@csrf_exempt
@require_level(60)
def api_admin_plan_init(request, entreprise_id):
    if not _authorized(request):
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    entreprise = _comptabilite_entreprise(entreprise_id)
    if not entreprise:
        return _json({"ok": False, "error": "Entreprise introuvable"}, 404)
    seeded = comptabilite.plan_init(entreprise)
    return _json({"ok": True, "seeded": seeded, "total": entreprise.comptes.count()})


@csrf_exempt
@require_level(60)
def api_admin_grand_livre(request, entreprise_id):
    if not _authorized(request):
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    entreprise = _comptabilite_entreprise(entreprise_id)
    if not entreprise:
        return _json({"ok": False, "error": "Entreprise introuvable"}, 404)
    frm = comptabilite.parse_date(request.GET.get("from") or "")
    to = comptabilite.parse_date(request.GET.get("to") or "")
    data = comptabilite.grand_livre(entreprise, from_date=frm, to_date=to)
    data.update({"ok": True, "entreprise": {"id": entreprise.id, "raison_sociale": entreprise.raison_sociale}})
    return _json(data)


@csrf_exempt
@require_level(60)
def api_admin_bilan(request, entreprise_id):
    if not _authorized(request):
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    entreprise = _comptabilite_entreprise(entreprise_id)
    if not entreprise:
        return _json({"ok": False, "error": "Entreprise introuvable"}, 404)
    frm = comptabilite.parse_date(request.GET.get("from") or "")
    to = comptabilite.parse_date(request.GET.get("to") or "")
    data = comptabilite.bilan(entreprise, from_date=frm, to_date=to)
    data.update({"ok": True, "entreprise": {"id": entreprise.id, "raison_sociale": entreprise.raison_sociale}})
    return _json(data)


# ---------------- RBAC : gestion du staff (admin uniquement) ----------------

@csrf_exempt
@require_level(100)
def api_admin_staff(request):
    """Gestion des profils staff : lecture, création, rôle, activation, suppression."""
    if request.method == "GET":
        profiles = StaffProfile.objects.select_related("user").prefetch_related("tokens")
        items = [{
            "id": p.id,
            "user_id": p.user_id,
            "username": p.user.username,
            "full_name": p.user.get_full_name() or p.user.username,
            "email": p.user.email,
            "role": p.role,
            "role_label": p.get_role_display(),
            "level": p.level,
            "actif": p.actif,
            "tokens": [{
                "id": t.id,
                "key": t.key[:12] + "…",
                "created_at": t.created_at.strftime("%d/%m/%Y %H:%M"),
                "expires_at": t.expires_at.strftime("%d/%m/%Y %H:%M") if t.expires_at else "—",
                "revoque": t.revoque,
            } for t in p.tokens.all()],
        } for p in profiles]
        return _json({
            "ok": True,
            "items": items,
            "roles": {r: StaffProfile.ROLE_LEVELS[r] for r, _ in StaffProfile.ROLE_CHOICES},
        })

    if request.method == "POST":
        body = _read_body(request)
        username = (body.get("username") or "").strip()
        email = (body.get("email") or "").strip().lower()
        full_name = (body.get("full_name") or "").strip()
        password = body.get("password") or ""
        role = body.get("role") or "lecture"
        if not username or not email or not password:
            return _json({"ok": False, "error": "Nom d'utilisateur, e-mail et mot de passe requis."}, 400)
        if role not in {r for r, _ in StaffProfile.ROLE_CHOICES}:
            return _json({"ok": False, "error": "Rôle invalide."}, 400)
        if User.objects.filter(username=username).exists() or User.objects.filter(username=email).exists():
            return _json({"ok": False, "error": "Cet utilisateur existe déjà."}, 400)
        user = User.objects.create_user(username=username, email=email, password=password)
        parts = full_name.split(" ", 1)
        user.first_name = parts[0]
        if len(parts) > 1:
            user.last_name = parts[1]
        user.is_staff = True
        user.save()
        profile = StaffProfile.objects.create(user=user, role=role)
        log_security("staff_created", request, actor=user, email=email, details={"role": role})
        return _json({"ok": True, "id": profile.id})

    if request.method == "PUT":
        body = _read_body(request)
        profile = StaffProfile.objects.filter(pk=int(body.get("id", 0))).first()
        if not profile:
            return _json({"ok": False, "error": "Profil introuvable."}, 404)
        field = body.get("field", "")
        value = body.get("status", "")
        if field == "role":
            if value not in {r for r, _ in StaffProfile.ROLE_CHOICES}:
                return _json({"ok": False, "error": "Rôle invalide."}, 400)
            log_security("role_changed", request, actor=profile.user, details={"role": value})
            profile.role = value
            profile.save(update_fields=["role"])
        elif field == "actif":
            profile.actif = str(value).lower() in ("true", "1", "yes")
            profile.save(update_fields=["actif"])
        else:
            return _json({"ok": False, "error": "Champ non modifiable."}, 400)
        return _json({"ok": True})

    if request.method == "DELETE":
        body = _read_body(request)
        profile = StaffProfile.objects.filter(pk=int(body.get("id", 0))).first()
        if not profile:
            return _json({"ok": False, "error": "Profil introuvable."}, 404)
        profile.user.delete()
        return _json({"ok": True, "message": "Membre supprimé."})

    return _json({"ok": False, "error": "Méthode non autorisée"}, 405)


@csrf_exempt
@require_level(100)
def api_admin_staff_token(request):
    """Création / révocation de jetons staff."""
    if request.method == "POST":
        body = _read_body(request)
        profile = StaffProfile.objects.filter(pk=int(body.get("profile", 0))).first()
        if not profile:
            return _json({"ok": False, "error": "Profil introuvable."}, 404)
        token = new_staff_token(profile)
        log_security("token_created", request, actor=profile.user, details={"token_type": "staff"})
        return _json({"ok": True, "id": token.id, "key": token.key})

    if request.method == "DELETE":
        body = _read_body(request)
        token = StaffToken.objects.filter(pk=int(body.get("id", 0))).first()
        if not token:
            return _json({"ok": False, "error": "Jeton introuvable."}, 404)
        token.revoque = True
        token.save(update_fields=["revoque"])
        log_security("token_revoked", request, actor=token.profile.user, details={"token_type": "staff"})
        return _json({"ok": True, "message": "Jeton révoqué."})

    return _json({"ok": False, "error": "Méthode non autorisée"}, 405)


@csrf_exempt
@require_level(100)
def api_admin_security_log(request):
    """Journal de sécurité (100 dernières entrées)."""
    entries = SecurityLog.objects.select_related("actor")[:100]
    items = [{
        "id": e.id,
        "action": e.action,
        "action_label": e.get_action_display(),
        "actor": e.actor.username if e.actor else "",
        "email": e.email,
        "ip": e.ip or "",
        "details": e.details,
        "created_at": e.created_at.strftime("%d/%m/%Y %H:%M:%S"),
    } for e in entries]
    return _json({"ok": True, "items": items})


@csrf_exempt
def api_admin_detail(request, table, obj_id):
    if not _authorized(request):
        return _json({"ok": False, "error": "Non autorisé"}, 401)
    if table == "client_service_suivis":
        obj = ClientServiceSuivi.objects.filter(pk=obj_id).select_related("client", "type_service").first()
        if not obj:
            return _json({"ok": False, "error": "Dossier introuvable"}, 404)
        payload = _dossier_payload(obj)
        payload["type"] = "dossier"
        return _json({"ok": True, "item": payload})
    if table == "service_followups":
        obj = ServiceFollowUp.objects.filter(pk=obj_id).select_related("client", "service", "dossier").first()
        if not obj:
            return _json({"ok": False, "error": "Suivi service introuvable"}, 404)
        item = {
            "type": "service",
            "id": obj.id,
            "client_id": obj.client.id,
            "client_name": obj.client.display_name,
            "service": obj.service_title,
            "service_id": obj.service.id if obj.service else None,
            "status": obj.get_status_display(),
            "start_date": obj.start_date.strftime("%d/%m/%Y") if obj.start_date else "—",
            "due_date": obj.due_date.strftime("%d/%m/%Y") if obj.due_date else "—",
            "notes": obj.notes,
        }
        if obj.dossier:
            d = _dossier_payload(obj.dossier)
            item["dossier"] = {"id": d["id"], "service": d["service"], "montant": d["montant"], "frequence": d["frequence"], "statut_service": d["statut_service"], "statut_paiement": d["statut_paiement"], "date_echeance": d["date_echeance"], "tasks": d["tasks"]}
        else:
            item["dossier"] = None
        item["tasks"] = [_task_payload(t) for t in obj.tasks.all()]
        return _json({"ok": True, "item": item})
    if table == "dossier_tasks":
        obj = DossierTask.objects.filter(pk=obj_id).select_related("dossier__client", "dossier__type_service", "service_followup").first()
        if not obj:
            return _json({"ok": False, "error": "Tâche introuvable"}, 404)
        item = {
            "type": "task",
            "id": obj.id,
            "titre": obj.titre,
            "description": obj.description,
            "statut": obj.get_statut_display(),
            "date_echeance": obj.date_echeance.strftime("%d/%m/%Y") if obj.date_echeance else "—",
            "repetition": obj.get_repetition_display(),
            "followup": {
                "id": obj.service_followup.id,
                "service": obj.service_followup.service_title,
                "status": obj.service_followup.get_status_display(),
            } if obj.service_followup else None,
            "dossier": {
                "id": obj.dossier.id,
                "service": obj.dossier.service_title,
                "client_name": obj.dossier.client.display_name,
                "statut_service": obj.dossier.get_statut_service_display(),
                "statut_paiement": obj.dossier.get_statut_paiement_display(),
                "montant": str(obj.dossier.montant),
            },
        }
        return _json({"ok": True, "item": item})
    if table == "client_messages":
        obj = ClientMessage.objects.filter(pk=obj_id).select_related("client", "dossier", "service", "task").first()
        if not obj:
            return _json({"ok": False, "error": "Message introuvable"}, 404)
        thread = ClientMessage.objects.filter(client=obj.client)
        if obj.dossier:
            thread = thread.filter(dossier_id=obj.dossier_id)
        item = {
            "type": "message",
            "id": obj.id,
            "direction": obj.direction,
            "text": obj.text,
            "created_at": obj.created_at.strftime("%d/%m/%Y %H:%M"),
            "client_id": obj.client.id,
            "client_name": obj.client.display_name,
            "dossier_id": obj.dossier_id,
            "dossier_service": obj.dossier_service,
            "service_id": obj.service_id,
            "service_title": obj.service_title,
            "task_id": obj.task_id,
            "task_title": obj.task_title,
            "context_label": obj.context_label,
            "thread": [_message_payload(m) for m in thread],
        }
        return _json({"ok": True, "item": item})
    if table == "types_service":
        obj = Service.objects.filter(pk=obj_id).select_related("parent").prefetch_related("subservices").first()
        if not obj:
            return _json({"ok": False, "error": "Service introuvable"}, 404)
        item = {
            "type": "service",
            "id": obj.id,
            "title": obj.title,
            "slug": obj.slug,
            "short_desc": obj.short_desc,
            "description": obj.description,
            "icon": obj.icon,
            "price_hint": obj.price_hint,
            "parent_id": obj.parent_id,
            "parent_title": obj.parent_title,
            "subservices": [
                {"id": s.id, "title": s.title, "slug": s.slug, "short_desc": s.short_desc}
                for s in obj.subservices.all()
            ],
        }
        return _json({"ok": True, "item": item})
    return _json({"ok": False, "error": "Table non suivie"}, 400)


def _api_admin_create(request, table):
    if table == "dossier_attachments":
        try:
            dossier = ClientServiceSuivi.objects.get(pk=int(request.POST.get("dossier", 0)))
        except (ValueError, ClientServiceSuivi.DoesNotExist):
            return _json({"ok": False, "error": "Dossier introuvable."}, 400)
        f = request.FILES.get("file")
        if not f:
            return _json({"ok": False, "error": "Aucun fichier reçu."}, 400)
        if f.size > settings.MAX_UPLOAD_SIZE:
            return _json({"ok": False, "error": "Fichier trop volumineux (20 Mo max)."}, 400)
        name = f.name or "fichier"
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        allowed = {e for exts in ALLOWED_UPLOAD_EXTENSIONS.values() for e in exts}
        if ext not in allowed:
            return _json({"ok": False, "error": "Format non autorisé."}, 400)
        att = DossierAttachment.objects.create(
            dossier=dossier,
            file=f,
            original_name=name[:255],
            content_type=f.content_type or "",
            size=f.size,
            uploaded_by="admin",
        )
        return _json({"ok": True, "id": att.id})

    body = _read_body(request)

    if table == "clients":
        name = (body.get("name") or "").strip()
        email = (body.get("email") or "").strip()
        if not name or not email:
            return _json({"ok": False, "error": "Nom et e-mail requis."}, 400)
        if Client.objects.filter(email__iexact=email).exists():
            return _json({"ok": False, "error": "Un client existe déjà avec cet e-mail."}, 400)
        statut_client = body.get("statut_client") or "entreprise"
        if statut_client not in {s for s, _ in Client.STATUT_CHOICES}:
            return _json({"ok": False, "error": "Type de client invalide."}, 400)
        client = Client.objects.create(
            name=name,
            prenom=(body.get("prenom") or "").strip(),
            email=email,
            phone=(body.get("phone") or "").strip(),
            company=(body.get("company") or "").strip(),
            adresse=(body.get("adresse") or "").strip(),
            statut_client=statut_client,
            matricule_fiscale=(body.get("matricule_fiscale") or "").strip(),
            cin=(body.get("cin") or "").strip(),
            notes=(body.get("notes") or "").strip(),
        )
        return _json({"ok": True, "id": client.id})

    if table == "client_service_suivis":
        try:
            client = Client.objects.get(pk=int(body.get("client", 0)))
        except (ValueError, Client.DoesNotExist):
            return _json({"ok": False, "error": "Client introuvable."}, 400)
        try:
            service = Service.objects.get(pk=int(body.get("type_service", 0)))
        except (ValueError, Service.DoesNotExist):
            return _json({"ok": False, "error": "Service introuvable."}, 400)
        montant = (body.get("montant") or "").strip()
        try:
            montant = float(montant)
        except ValueError:
            return _json({"ok": False, "error": "Montant invalide."}, 400)
        echeance = (body.get("date_echeance") or "").strip()
        if echeance:
            try:
                date.fromisoformat(echeance)
            except ValueError:
                return _json({"ok": False, "error": "Date d'échéance invalide (AAAA-MM-JJ)."}, 400)
        paiement = body.get("statut_paiement", "en_attente")
        service_statut = body.get("statut_service", "en_cours")
        valid_p = {s for s, _ in ClientServiceSuivi.STATUT_PAIEMENT_CHOICES}
        valid_s = {s for s, _ in ClientServiceSuivi.STATUT_SERVICE_CHOICES}
        if paiement not in valid_p or service_statut not in valid_s:
            return _json({"ok": False, "error": "Statut invalide."}, 400)
        obj = ClientServiceSuivi.objects.create(
            client=client,
            type_service=service,
            montant=montant,
            statut_paiement=paiement,
            statut_service=service_statut,
            date_echeance=echeance or None,
            commentaire=(body.get("commentaire") or "").strip(),
            service_note=(body.get("service_note") or "").strip(),
        )
        titre = (body.get("tache_titre") or "").strip()
        if titre:
            task_echeance = (body.get("tache_echeance") or "").strip()
            if task_echeance:
                try:
                    date.fromisoformat(task_echeance)
                except ValueError:
                    return _json({"ok": False, "error": "Date d'échéance de la tâche invalide."}, 400)
            repetition = body.get("tache_repetition", "ponctuel")
            valid_r = {s for s, _ in DossierTask.REPETITION_CHOICES}
            if repetition not in valid_r:
                repetition = "ponctuel"
            DossierTask.objects.create(
                dossier=obj,
                titre=titre,
                date_echeance=task_echeance or None,
                repetition=repetition,
            )
        return _json({"ok": True, "id": obj.id})

    if table == "prefactures":
        try:
            dossier = ClientServiceSuivi.objects.get(pk=int(body.get("dossier", 0)))
        except (ValueError, TypeError, ClientServiceSuivi.DoesNotExist):
            return _json({"ok": False, "error": "Dossier introuvable."}, 400)
        try:
            tva = float(body.get("taux_tva", 19) or 19)
        except ValueError:
            return _json({"ok": False, "error": "TVA invalide."}, 400)
        montant_ht = dossier.montant or 0
        montant_ttc = Decimal(montant_ht) * (Decimal("1") + Decimal(str(tva)) / Decimal("100"))
        numero = f"PF-{date.today().year}-{Prefacture.objects.count() + 1:03d}"
        while Prefacture.objects.filter(numero=numero).exists():
            numero = f"PF-{date.today().year}-{Prefacture.objects.count() + 2:03d}"
        pf = Prefacture.objects.create(
            dossier=dossier,
            numero=numero,
            date=date.today(),
            montant_ht=montant_ht,
            taux_tva=tva,
            montant_ttc=montant_ttc,
        )
        return _json({"ok": True, "id": pf.id, "numero": pf.numero})

    if table == "dossier_tasks":
        try:
            dossier = ClientServiceSuivi.objects.get(pk=int(body.get("dossier", 0)))
        except (ValueError, TypeError, ClientServiceSuivi.DoesNotExist):
            return _json({"ok": False, "error": "Dossier introuvable."}, 400)
        followup = None
        if (body.get("service_followup") or "").strip().isdigit():
            followup = ServiceFollowUp.objects.filter(
                pk=int(body["service_followup"]), dossier_id=dossier.id, client_id=dossier.client_id
            ).first()
            if not followup:
                return _json({"ok": False, "error": "Suivi de service invalide pour ce dossier."}, 400)
        titre = (body.get("titre") or "").strip()
        if not titre:
            return _json({"ok": False, "error": "Titre de la tâche requis."}, 400)
        statut = body.get("statut", "a_faire")
        repetition = body.get("repetition", "ponctuel")
        valid_st = {s for s, _ in DossierTask.STATUT_CHOICES}
        valid_rp = {s for s, _ in DossierTask.REPETITION_CHOICES}
        if statut not in valid_st or repetition not in valid_rp:
            return _json({"ok": False, "error": "Statut ou répétition invalide."}, 400)
        echeance = (body.get("date_echeance") or "").strip()
        if echeance:
            try:
                date.fromisoformat(echeance)
            except ValueError:
                return _json({"ok": False, "error": "Date d'échéance invalide (AAAA-MM-JJ)."}, 400)
        task = DossierTask.objects.create(
            dossier=dossier,
            service_followup=followup,
            titre=titre,
            description=(body.get("description") or "").strip(),
            statut=statut,
            date_echeance=echeance or None,
            repetition=repetition,
        )
        return _json({"ok": True, "id": task.id})

    if table == "declarations":
        try:
            client = Client.objects.get(pk=int(body.get("client", 0)))
        except (ValueError, TypeError, Client.DoesNotExist):
            return _json({"ok": False, "error": "Client introuvable."}, 400)
        dossier = None
        if (body.get("dossier") or "").strip().isdigit():
            dossier = ClientServiceSuivi.objects.filter(pk=int(body["dossier"]), client=client).first()
            if not dossier:
                return _json({"ok": False, "error": "Dossier introuvable pour ce client."}, 400)
        type_declaration = body.get("type_declaration", "")
        statut = body.get("statut", "a_faire")
        if type_declaration not in {s for s, _ in DeclarationFiscale.TYPE_DECLARATION_CHOICES}:
            return _json({"ok": False, "error": "Type de déclaration invalide."}, 400)
        if statut not in {s for s, _ in DeclarationFiscale.STATUT_CHOICES}:
            return _json({"ok": False, "error": "Statut invalide."}, 400)
        periode = (body.get("periode") or "").strip()
        echeance = (body.get("date_echeance_legale") or "").strip()
        if not periode or not echeance:
            return _json({"ok": False, "error": "Période et date limite légale requises."}, 400)
        try:
            date.fromisoformat(echeance)
        except ValueError:
            return _json({"ok": False, "error": "Date limite légale invalide (AAAA-MM-JJ)."}, 400)
        try:
            montant = float(body.get("montant_a_payer") or 0)
        except ValueError:
            return _json({"ok": False, "error": "Montant invalide."}, 400)
        decl = DeclarationFiscale.objects.create(
            client=client,
            dossier=dossier,
            type_declaration=type_declaration,
            periode=periode,
            date_echeance_legale=echeance,
            statut=statut,
            numero_quittance_ou_tej=(body.get("numero_quittance_ou_tej") or "").strip(),
            montant_a_payer=montant,
            notes_collaborateur=(body.get("notes_collaborateur") or "").strip(),
        )
        return _json({"ok": True, "id": decl.id})

    if table == "payments":
        try:
            client = Client.objects.get(pk=int(body.get("client", 0)))
        except (ValueError, TypeError, Client.DoesNotExist):
            return _json({"ok": False, "error": "Client introuvable."}, 400)
        dossier = None
        if (body.get("dossier") or "").strip().isdigit():
            dossier = ClientServiceSuivi.objects.filter(pk=int(body["dossier"]), client=client).first()
            if not dossier:
                return _json({"ok": False, "error": "Dossier introuvable pour ce client."}, 400)
        try:
            amount = float(body.get("amount", 0))
        except ValueError:
            return _json({"ok": False, "error": "Montant invalide."}, 400)
        pay_date = (body.get("date") or "").strip() or date.today().isoformat()
        try:
            date.fromisoformat(pay_date)
        except ValueError:
            return _json({"ok": False, "error": "Date invalide (AAAA-MM-JJ)."}, 400)
        status = body.get("status", "en_attente")
        if status not in {s for s, _ in Payment.STATUS_CHOICES}:
            return _json({"ok": False, "error": "Statut invalide."}, 400)
        obj = Payment.objects.create(
            client=client, dossier=dossier, amount=amount, date=pay_date,
            status=status, method=(body.get("method") or "").strip(),
            notes=(body.get("notes") or "").strip(),
        )
        return _json({"ok": True, "id": obj.id})

    if table == "service_followups":
        client = None
        if (body.get("client") or "").strip().isdigit():
            client = Client.objects.filter(pk=int(body["client"])).first()
        dossier = None
        if (body.get("dossier") or "").strip().isdigit():
            dossier = ClientServiceSuivi.objects.filter(pk=int(body["dossier"])).first()
            if not dossier:
                return _json({"ok": False, "error": "Dossier associé introuvable."}, 400)
            client = dossier.client
        if not client:
            return _json({"ok": False, "error": "Client introuvable."}, 400)
        try:
            service = Service.objects.get(pk=int(body.get("type_service", 0)))
        except (ValueError, TypeError, Service.DoesNotExist):
            return _json({"ok": False, "error": "Service introuvable."}, 400)
        status = body.get("status", "en_attente")
        if status not in {s for s, _ in ServiceFollowUp.STATUS_CHOICES}:
            return _json({"ok": False, "error": "Statut invalide."}, 400)
        start_date = (body.get("start_date") or "").strip()
        due_date = (body.get("due_date") or "").strip()
        for field_name, val in (("start_date", start_date), ("due_date", due_date)):
            if val:
                try:
                    date.fromisoformat(val)
                except ValueError:
                    return _json({"ok": False, "error": f"Date {field_name} invalide (AAAA-MM-JJ)."}, 400)
        collab = None
        if (body.get("collaborateur") or "").strip().isdigit():
            collab = Collaborateur.objects.filter(pk=int(body["collaborateur"])).first()
        sf = ServiceFollowUp.objects.create(
            client=client,
            dossier=dossier,
            service=service,
            collaborateur=collab,
            status=status,
            start_date=start_date or None,
            due_date=due_date or None,
            notes=(body.get("notes") or "").strip(),
        )
        return _json({"ok": True, "id": sf.id})

    if table == "collaborateurs":
        nom = (body.get("nom") or "").strip()
        email = (body.get("email") or "").strip().lower()
        if not nom or not email:
            return _json({"ok": False, "error": "Nom et e-mail requis."}, 400)
        if Collaborateur.objects.filter(email__iexact=email).exists():
            return _json({"ok": False, "error": "Un collaborateur existe déjà avec cet e-mail."}, 400)
        obj = Collaborateur.objects.create(
            nom=nom,
            prenom=(body.get("prenom") or "").strip(),
            email=email,
            telephone=(body.get("telephone") or "").strip(),
            fonction=(body.get("fonction") or "").strip(),
            actif=(body.get("actif", "true") in ("1", "true", "True", "on", "")),
            notes=(body.get("notes") or "").strip(),
        )
        return _json({"ok": True, "id": obj.id})

    if table == "client_messages":
        try:
            client = Client.objects.get(pk=int(body.get("client", 0)))
        except (ValueError, Client.DoesNotExist):
            return _json({"ok": False, "error": "Client introuvable."}, 400)
        text = (body.get("text") or "").strip()
        if not text:
            return _json({"ok": False, "error": "Message vide."}, 400)
        dossier = None
        service = None
        task = None
        if (body.get("dossier") or "").strip().isdigit():
            dossier = ClientServiceSuivi.objects.filter(pk=int(body["dossier"]), client=client).first()
            if not dossier:
                return _json({"ok": False, "error": "Dossier introuvable pour ce client."}, 400)
        if (body.get("service") or "").strip().isdigit():
            service = Service.objects.filter(pk=int(body["service"])).first()
            if not service:
                return _json({"ok": False, "error": "Service introuvable."}, 400)
        if (body.get("task") or "").strip().isdigit():
            task = DossierTask.objects.filter(pk=int(body["task"]), dossier__client=client).first()
            if not task:
                return _json({"ok": False, "error": "Tâche introuvable pour ce client."}, 400)
            if dossier and task.dossier_id != dossier.id:
                return _json({"ok": False, "error": "La tâche n'appartient pas au dossier sélectionné."}, 400)
        if not service and dossier:
            service = dossier.type_service
        obj = ClientMessage.objects.create(
            client=client, direction="admin", text=text,
            dossier=dossier, service=service, task=task,
        )
        return _json({"ok": True, "id": obj.id})

    if table == "types_service":
        slug = (body.get("slug") or "").strip().lower().replace(" ", "-")
        title = (body.get("title") or "").strip()
        if not slug or not title:
            return _json({"ok": False, "error": "Titre et identifiant requis."}, 400)
        if Service.objects.filter(slug=slug).exists():
            return _json({"ok": False, "error": "Un service existe déjà avec cet identifiant."}, 400)
        parent = None
        if (body.get("parent") or "").strip().isdigit():
            parent = Service.objects.filter(pk=int(body["parent"])).first()
        obj = Service.objects.create(
            slug=slug,
            title=title,
            short_desc=(body.get("short_desc") or "")[:255],
            description=(body.get("description") or ""),
            icon=(body.get("icon") or "briefcase"),
            price_hint=(body.get("price_hint") or ""),
            parent=parent,
        )
        return _json({"ok": True, "id": obj.id})

    if table == "entreprises":
        try:
            client = Client.objects.get(pk=int(body.get("client", 0)))
        except (ValueError, Client.DoesNotExist):
            return _json({"ok": False, "error": "Client introuvable."}, 400)
        if Entreprise.objects.filter(client=client).exists():
            return _json({"ok": False, "error": "Ce client a déjà une entreprise."}, 400)
        raison = (body.get("raison_sociale") or "").strip()
        if not raison:
            return _json({"ok": False, "error": "Raison sociale requise."}, 400)
        forme = (body.get("forme_juridique") or "").strip()
        if forme and forme not in {f for f, _ in Entreprise.FORME_CHOICES}:
            return _json({"ok": False, "error": "Forme juridique invalide."}, 400)
        obj = Entreprise.objects.create(
            client=client,
            raison_sociale=raison,
            matricule_fiscale=(body.get("matricule_fiscale") or "").strip(),
            registre_commerce=(body.get("registre_commerce") or "").strip(),
            forme_juridique=forme,
            activite=(body.get("activite") or "").strip(),
            adresse=(body.get("adresse") or "").strip(),
            code_postal=(body.get("code_postal") or "").strip(),
            ville=(body.get("ville") or "").strip(),
            telephone=(body.get("telephone") or "").strip(),
            email=(body.get("email") or "").strip(),
            representant_legal=(body.get("representant_legal") or "").strip(),
            notes=(body.get("notes") or "").strip(),
        )
        comptabilite.plan_init(obj)
        return _json({"ok": True, "id": obj.id})

    if table == "comptes":
        try:
            entreprise = Entreprise.objects.get(pk=int(body.get("entreprise", 0)))
        except (ValueError, Entreprise.DoesNotExist):
            return _json({"ok": False, "error": "Entreprise introuvable."}, 400)
        numero = (body.get("numero") or "").strip()
        intitule = (body.get("intitule") or "").strip()
        if not numero or not intitule:
            return _json({"ok": False, "error": "Numéro et intitulé requis."}, 400)
        if CompteComptable.objects.filter(entreprise=entreprise, numero=numero).exists():
            return _json({"ok": False, "error": "Un compte existe déjà avec ce numéro."}, 400)
        parent = None
        parent_raw = str(body.get("parent") or "").strip()
        if parent_raw.isdigit():
            parent = CompteComptable.objects.filter(pk=int(parent_raw), entreprise=entreprise).first()
            if not parent:
                return _json({"ok": False, "error": "Compte parent introuvable."}, 400)
        obj = CompteComptable.objects.create(
            entreprise=entreprise, parent=parent, numero=numero, intitule=intitule
        )
        return _json({"ok": True, "id": obj.id})

    if table == "ecritures":
        try:
            entreprise = Entreprise.objects.get(pk=int(body.get("entreprise", 0)))
        except (ValueError, Entreprise.DoesNotExist):
            return _json({"ok": False, "error": "Entreprise introuvable."}, 400)
        try:
            date_e = date.fromisoformat((body.get("date") or "").strip())
        except ValueError:
            return _json({"ok": False, "error": "Date invalide (AAAA-MM-JJ)."}, 400)
        numero_piece = (body.get("numero_piece") or "").strip()
        libelle = (body.get("libelle") or "").strip()
        if not numero_piece or not libelle:
            return _json({"ok": False, "error": "N° pièce et libellé requis."}, 400)
        journal = body.get("journal", "od")
        if journal not in {j for j, _ in EcritureComptable.JOURNAL_CHOICES}:
            return _json({"ok": False, "error": "Journal invalide."}, 400)
        lignes = body.get("lignes") or []
        if len(lignes) < 2:
            return _json({"ok": False, "error": "Une pièce doit avoir au moins deux lignes."}, 400)
        rows = []
        for i, ln in enumerate(lignes):
            try:
                compte = CompteComptable.objects.get(pk=int(ln.get("compte", 0)), entreprise=entreprise)
            except (ValueError, CompteComptable.DoesNotExist):
                return _json({"ok": False, "error": f"Compte invalide sur la ligne {i + 1}."}, 400)
            try:
                debit = Decimal(str(ln.get("debit", 0) or 0))
                credit = Decimal(str(ln.get("credit", 0) or 0))
            except Exception:
                return _json({"ok": False, "error": f"Montant invalide sur la ligne {i + 1}."}, 400)
            if debit < 0 or credit < 0:
                return _json({"ok": False, "error": "Montants négatifs interdits."}, 400)
            if debit == 0 and credit == 0:
                return _json({"ok": False, "error": f"Ligne {i + 1} : renseignez un débit ou un crédit."}, 400)
            rows.append((compte, (ln.get("libelle") or "").strip()[:255], debit, credit))
        if sum(r[2] for r in rows) != sum(r[3] for r in rows):
            return _json({"ok": False, "error": "La pièce n'est pas équilibrée (total débit ≠ total crédit)."}, 400)
        statut = body.get("statut", "brouillon")
        if statut not in {s for s, _ in EcritureComptable.STATUT_CHOICES}:
            return _json({"ok": False, "error": "Statut invalide."}, 400)
        obj = EcritureComptable.objects.create(
            entreprise=entreprise, journal=journal, numero_piece=numero_piece,
            date=date_e, libelle=libelle, statut=statut,
        )
        for compte, lib, debit, credit in rows:
            obj.lignes.create(compte=compte, libelle=lib, debit=debit, credit=credit)
        return _json({"ok": True, "id": obj.id})

    return _json({"ok": False, "error": "Création non disponible pour cette table."}, 400)
