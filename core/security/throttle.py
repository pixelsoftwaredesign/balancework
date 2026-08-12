"""Throttling (limitation de tentatives) basé sur le journal de sécurité."""
from datetime import timedelta

from django.utils import timezone

from ..models import SecurityLog
from .audit import client_ip, log_security

DEFAULT_LIMIT = 5
DEFAULT_WINDOW_MINUTES = 15


def record_failure(request, email="", details="") -> None:
    """Consigne un échec d'authentification (base du compteur de throttling)."""
    log_security("login_fail", request, email=email, details=details or {"reason": "invalid_credentials"})


def is_throttled(request, email="", limit=DEFAULT_LIMIT, window_minutes=DEFAULT_WINDOW_MINUTES) -> bool:
    """Vrai si la limite de tentatives échouées est dépassée (par e-mail et/ou IP)."""
    since = timezone.now() - timedelta(minutes=window_minutes)
    qs = SecurityLog.objects.filter(action="login_fail", created_at__gte=since)
    if email:
        qs = qs.filter(email=email)
    ip = client_ip(request)
    if ip:
        qs = qs.filter(ip=ip)
    if qs.count() >= limit:
        log_security("throttled", request, email=email, details={"reason": "rate_limit", "ip": ip})
        return True
    return False
