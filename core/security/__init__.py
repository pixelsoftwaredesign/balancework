"""Couche sécurité : RBAC, jetons, throttling, journalisation.

Cette couche appartient au niveau "application/service" de l'architecture
3 couches (présentation -> services -> persistance). Les vues se limitent
à la présentation HTTP et délèguent toute la logique de sécurité ici.
"""
from . import auth_service
from .rbac import require_level, role_level_for_request

__all__ = [
    "auth_service",
    "require_level",
    "role_level_for_request",
]
