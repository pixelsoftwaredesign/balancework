from django.urls import path, re_path
from django.views.generic import TemplateView
from django.views.static import serve

from django.conf import settings

from . import views

urlpatterns = [
    # Pages
    path("", TemplateView.as_view(template_name="index.html"), name="accueil"),
    path("services/", TemplateView.as_view(template_name="services.html"), name="services"),
    path("devis/", TemplateView.as_view(template_name="devis.html"), name="devis"),
    path("contact/", TemplateView.as_view(template_name="contact.html"), name="contact"),
    path("rendezvous/", TemplateView.as_view(template_name="rendezvous.html"), name="rendezvous"),
    path("gestion/", TemplateView.as_view(template_name="admin.html"), name="admin_site"),
    path("espace-client/", TemplateView.as_view(template_name="espace_client.html"), name="espace_client"),

    # API publique
    path("api/services", views.api_services, name="api_services"),
    path("api/availability", views.api_availability, name="api_availability"),
    path("api/contact", views.api_contact, name="api_contact"),
    path("api/devis", views.api_devis, name="api_devis"),
    path("api/rendezvous", views.api_rendezvous, name="api_rendezvous"),

    # API espace client
    path("api/auth/register", views.api_client_register, name="api_client_register"),
    path("api/auth/login", views.api_client_login, name="api_client_login"),
    path("api/auth/logout", views.api_client_logout, name="api_client_logout"),
    path("api/client/dashboard", views.api_client_dashboard, name="api_client_dashboard"),
    path("api/client/dossiers", views.api_client_create_dossier, name="api_client_create_dossier"),
    path("api/client/dossiers/<int:dossier_id>", views.api_client_update_dossier, name="api_client_update_dossier"),
    path("api/client/profile", views.api_client_profile, name="api_client_profile"),
    path("api/client/dossiers/<int:dossier_id>/attachments", views.api_client_attachments, name="api_client_attachments"),
    path("api/client/attachments/<int:attachment_id>", views.api_client_attachment_delete, name="api_client_attachment_delete"),
    path("api/client/prefacture/<int:prefacture_id>", views.api_client_prefacture, name="api_client_prefacture"),
    path("api/client/messages", views.api_client_messages, name="api_client_messages"),

    # API admin (jeton Bearer)
    path("api/admin/detail/<str:table>/<int:obj_id>", views.api_admin_detail, name="api_admin_detail"),
    path("api/admin/explorer/<int:client_id>", views.api_admin_explorer, name="api_admin_explorer_client"),
    path("api/admin/explorer", views.api_admin_explorer, name="api_admin_explorer"),
    path("api/admin/<str:table>", views.api_admin, name="api_admin"),

    # SEO
    path("sitemap.xml", views.sitemap, name="sitemap"),
    path("robots.txt", views.robots, name="robots"),
]

# Fichiers uploadés (media) servis par Django en dev comme en prod
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
