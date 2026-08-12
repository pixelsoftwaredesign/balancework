"""RBAC : niveaux de rôle et contrôle d'accès sur l'API admin."""
from functools import wraps

from django.contrib.auth.models import User
from django.http import JsonResponse

from ..models import StaffProfile
from .tokens import admin_token_ok, bearer_token, staff_token_for_request


def role_level_for_request(request) -> int:
    """Niveau de rôle de la requête admin (jeton statique = super admin = 1000)."""
    token = staff_token_for_request(request)
    if token:
        return token.profile.level
    if admin_token_ok(bearer_token(request)):
        return 1000
    return 0


def require_level(min_level: int):
    """Décore une vue admin : refuse si le niveau du jeton est insuffisant."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            level = role_level_for_request(request)
            if level == 0:
                return JsonResponse({"ok": False, "error": "Non autorisé"}, status=401)
            if level < min_level:
                return JsonResponse(
                    {"ok": False, "error": "Privilèges insuffisants pour cette action."},
                    status=403,
                )
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def role_levels() -> dict:
    """Expose la matrice des rôles et leurs niveaux."""
    return {r: StaffProfile.ROLE_LEVELS[r] for r, _ in StaffProfile.ROLE_CHOICES}
