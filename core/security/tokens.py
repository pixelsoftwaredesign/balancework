"""Gestion des jetons Bearer (client et staff) en temps constant."""
import hmac

from django.conf import settings
from django.utils import timezone

from ..models import AuthToken, StaffToken

CLIENT_TOKEN_TTL_DAYS = int(getattr(settings, "CLIENT_TOKEN_TTL_DAYS", 30))
STAFF_TOKEN_TTL_DAYS = int(getattr(settings, "STAFF_TOKEN_TTL_DAYS", 7))


def bearer_token(request) -> str:
    """Extrait le jeton du header Authorization: Bearer <token>."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return ""


def _constant_time_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def admin_token_ok(token: str) -> bool:
    """Vérifie le jeton admin statique en comparaison à temps constant."""
    expected = getattr(settings, "ADMIN_TOKEN", "")
    if not expected or not token:
        return False
    return _constant_time_equal(expected, token)


def _touch(instance, *fields):
    try:
        instance.last_used_at = timezone.now()
        instance.save(update_fields=list(fields) + ["last_used_at"])
    except Exception:
        pass


def client_token_for_request(request):
    """Renvoie le AuthToken valide (non expiré) du client, ou None.

    Un jeton expiré est supprimé ; son usage est consigné dans le journal.
    """
    key = bearer_token(request)
    if not key:
        return None
    token = AuthToken.objects.filter(key=key).select_related("user").first()
    if not token:
        return None
    if not token.is_valid:
        token.delete()
        return None
    _touch(token, "expires_at")
    return token


def client_from_request(request):
    """Client authentifié depuis la requête, ou None."""
    token = client_token_for_request(request)
    if not token:
        return None
    return getattr(token.user, "client", None)


def staff_token_for_request(request):
    """Renvoie le StaffToken valide (non expiré, profil actif), ou None."""
    key = bearer_token(request)
    if not key:
        return None
    token = StaffToken.objects.filter(key=key).select_related("profile", "profile__user").first()
    if not token or not token.is_valid:
        return None
    _touch(token, "expires_at")
    return token


def staff_profile_for_request(request):
    """Profil staff authentifié depuis la requête, ou None (jeton admin statique => admin)."""
    token = staff_token_for_request(request)
    if token:
        return token.profile
    if admin_token_ok(bearer_token(request)):
        return None  # jeton statique : super administrateur
    return None


def new_client_token(user) -> AuthToken:
    """Crée (ou renouvelle) le jeton de l'espace client pour l'utilisateur."""
    import secrets

    token, _ = AuthToken.objects.get_or_create(user=user)
    token.key = secrets.token_hex(32)
    token.expires_at = timezone.now() + timezone.timedelta(days=CLIENT_TOKEN_TTL_DAYS)
    token.save()
    return token


def new_staff_token(profile) -> StaffToken:
    import secrets

    return StaffToken.objects.create(
        profile=profile,
        key=secrets.token_hex(32),
        expires_at=timezone.now() + timezone.timedelta(days=STAFF_TOKEN_TTL_DAYS),
    )
