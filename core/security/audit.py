"""Journal de sécurité (SecurityLog)."""
import json
from ipaddress import ip_address

from django.contrib.auth.models import User

from ..models import SecurityLog

_SAFE_FIELDS = {"email", "action", "role", "token_type", "reason"}


def client_ip(request) -> str:
    """Extrait l'IP client en tenant compte des proxys (Cloudflare/Railway)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    remote = request.META.get("REMOTE_ADDR", "")
    if remote:
        try:
            return str(ip_address(remote))
        except ValueError:
            return remote
    return ""


def _safe_details(details) -> str:
    if isinstance(details, dict):
        cleaned = {k: v for k, v in details.items() if k in _SAFE_FIELDS}
        return json.dumps(cleaned, ensure_ascii=False)[:400]
    return str(details or "")[:400]


def log_security(action: str, request=None, actor=None, email="", ip="", details="") -> None:
    """Consigne un événement de sécurité sans jamais lever d'exception."""
    try:
        actor_user = None
        if isinstance(actor, User):
            actor_user = actor
        elif actor is not None:
            actor_user = getattr(actor, "user", None)
            if not isinstance(actor_user, User):
                actor_user = None
        SecurityLog.objects.create(
            action=action,
            actor=actor_user,
            email=(email or "")[:254],
            ip=ip or (client_ip(request) if request is not None else "")[:39] or None,
            details=_safe_details(details),
        )
    except Exception:
        pass
