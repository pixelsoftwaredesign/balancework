from django.contrib import admin

from .models import (
    Appointment,
    CompteComptable,
    DevisRequest,
    EcritureComptable,
    Entreprise,
    LigneEcriture,
    Message,
    SecurityLog,
    Service,
    StaffProfile,
    StaffToken,
)


@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    list_display = ("raison_sociale", "client", "matricule_fiscale", "ville", "updated_at")
    search_fields = ("raison_sociale", "matricule_fiscale", "registre_commerce")


@admin.register(CompteComptable)
class CompteComptableAdmin(admin.ModelAdmin):
    list_display = ("numero", "intitule", "entreprise", "parent", "niveau")
    list_filter = ("entreprise",)
    search_fields = ("numero", "intitule")
    ordering = ("entreprise", "numero")


@admin.register(EcritureComptable)
class EcritureComptableAdmin(admin.ModelAdmin):
    list_display = ("numero_piece", "date", "libelle", "entreprise", "journal", "statut", "total_debit", "total_credit")
    list_filter = ("entreprise", "journal", "statut", "date")
    search_fields = ("numero_piece", "libelle")


@admin.register(LigneEcriture)
class LigneEcritureAdmin(admin.ModelAdmin):
    list_display = ("ecriture", "compte", "debit", "credit")
    list_filter = ("compte__entreprise",)
    autocomplete_fields = ("compte",)


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "level", "actif", "created_at")
    list_filter = ("role", "actif")
    search_fields = ("user__username", "user__email")


@admin.register(StaffToken)
class StaffTokenAdmin(admin.ModelAdmin):
    list_display = ("profile", "key", "created_at", "expires_at", "revoque", "last_used_at")
    list_filter = ("revoque", "profile__role")
    search_fields = ("key", "profile__user__username")


@admin.register(SecurityLog)
class SecurityLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "email", "ip", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("email", "ip", "actor__username", "details")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "price_hint")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(DevisRequest)
class DevisRequestAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "service_title", "budget", "status", "created_at")
    list_filter = ("status", "service", "created_at")
    search_fields = ("name", "email", "company")
    list_editable = ("status",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "message")
    list_editable = ("status",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "date", "time", "service_title", "status")
    list_filter = ("status", "date", "service")
    search_fields = ("name", "email", "phone")
    list_editable = ("status",)
