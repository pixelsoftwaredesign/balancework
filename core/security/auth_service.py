"""Service d'authentification espace client (register / login / logout)."""
import re
import secrets

from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from ..models import AuthToken, Client
from .audit import log_security
from .throttle import is_throttled, record_failure
from .tokens import bearer_token, new_client_token

MIN_PASSWORD_LENGTH = 8


def password_policy_errors(password: str):
    """Renvoie la liste des violations de la politique de mot de passe."""
    errors = []
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères.")
    if not re.search(r"[A-Za-z]", password):
        errors.append("Le mot de passe doit contenir au moins une lettre.")
    if not re.search(r"\d", password):
        errors.append("Le mot de passe doit contenir au moins un chiffre.")
    if len(set(password.lower())) < 4:
        errors.append("Le mot de passe est trop répétitif.")
    return errors


def _client_payload(client):
    return {
        "id": client.id,
        "name": client.display_name,
        "email": client.email,
        "company": client.company,
        "statut_client": client.statut_client,
    }


def register(request, body: dict):
    """Inscription d'un client : validation, création User+Client, jeton."""
    name = (body.get("name") or "").strip()
    prenom = (body.get("prenom") or "").strip()
    email = (body.get("email") or "").strip().lower()
    phone = (body.get("phone") or "").strip()
    password = body.get("password") or ""
    matricule = (body.get("matricule_fiscale") or "").strip()
    cin = (body.get("cin") or "").strip()

    missing = [f for f in ("name", "prenom", "email", "phone", "password") if not (body.get(f) or "").strip()]
    if missing:
        return {"ok": False, "status": 400, "error": f"Champs manquants : {', '.join(missing)}"}
    if not matricule and not cin:
        return {"ok": False, "status": 400, "error": "Indiquez au moins le matricule fiscal ou le numéro de carte d'identité."}
    if User.objects.filter(username=email).exists():
        return {"ok": False, "status": 400, "error": "Un compte existe déjà avec cet e-mail."}
    policy = password_policy_errors(password)
    if policy:
        return {"ok": False, "status": 400, "error": " ".join(policy)}

    user = User.objects.create_user(username=email, email=email, first_name=prenom, last_name=name, password=password)
    client = Client.objects.create(
        user=user, name=name, prenom=prenom, email=email, phone=phone,
        matricule_fiscale=matricule, cin=cin,
    )
    token = new_client_token(user)
    log_security("register", request, actor=user, email=email)
    return {"ok": True, "status": 201, "token": token.key, "client": _client_payload(client)}


def login(request, body: dict):
    """Connexion client avec throttling et rotation du jeton."""
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        return {"ok": False, "status": 400, "error": "E-mail et mot de passe requis."}
    if is_throttled(request, email=email):
        return {"ok": False, "status": 429, "error": "Trop de tentatives. Réessayez dans quelques minutes."}

    user = authenticate(username=email, password=password)
    if not user or not hasattr(user, "client"):
        record_failure(request, email=email)
        return {"ok": False, "status": 401, "error": "Identifiants invalides."}

    token = new_client_token(user)
    log_security("login_ok", request, actor=user, email=email)
    return {"ok": True, "status": 200, "token": token.key, "client": _client_payload(user.client)}


def logout(request) -> None:
    AuthToken.objects.filter(key=bearer_token(request)).delete()
