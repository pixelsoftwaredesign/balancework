import json
from datetime import date, timedelta

from django.test import TestCase, override_settings

from .models import (
    Appointment,
    Client,
    ClientMessage,
    ClientServiceSuivi,
    Collaborateur,
    DeclarationFiscale,
    DevisRequest,
    DossierTask,
    Message,
    Payment,
    Service,
    ServiceFollowUp,
)


class ApiServicesTests(TestCase):
    def test_services_list(self):
        res = self.client.get("/api/services")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertGreaterEqual(len(data["services"]), 9)
        slugs = [s["slug"] for s in data["services"]]
        self.assertIn("conseil-fiscal", slugs)
        self.assertNotIn("balance", slugs)
        self.assertIn("tax", slugs)
        self.assertIn("safety", slugs)
        self.assertIn("tej", slugs)
        self.assertIn("accompagnement", slugs)


class ApiFormsTests(TestCase):
    def test_contact(self):
        res = self.client.post(
            "/api/contact",
            data=json.dumps({"name": "Hajer", "email": "h@test.tn", "message": "Bonjour"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])
        self.assertEqual(Message.objects.count(), 1)

    def test_contact_missing_fields(self):
        res = self.client.post(
            "/api/contact",
            data=json.dumps({"name": "Hajer"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)

    def test_devis(self):
        res = self.client.post(
            "/api/devis",
            data=json.dumps({"name": "Client", "email": "c@test.tn", "service": "tax"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])
        devis = DevisRequest.objects.get()
        self.assertEqual(devis.service.slug, "tax")
        self.assertEqual(devis.status, "nouveau")

    def test_rendezvous_and_conflict(self):
        day = (date.today() + timedelta(days=2)).isoformat()
        payload = {"name": "R", "email": "r@test.tn", "date": day, "time": "10:30"}
        ok = self.client.post("/api/rendezvous", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(ok.status_code, 200)
        conflict = self.client.post("/api/rendezvous", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(Appointment.objects.count(), 1)


class ApiAdminTests(TestCase):
    @override_settings(ADMIN_TOKEN="secret-test")
    def test_requires_token(self):
        res = self.client.get("/api/admin/devis_requests")
        self.assertEqual(res.status_code, 401)

    @override_settings(ADMIN_TOKEN="secret-test")
    def test_list_and_update_status(self):
        DevisRequest.objects.create(name="A", email="a@test.tn")
        headers = {"HTTP_AUTHORIZATION": "Bearer secret-test"}

        res = self.client.get("/api/admin/devis_requests", **headers)
        self.assertEqual(res.status_code, 200)
        item = res.json()["items"][0]
        self.assertEqual(item["name"], "A")

        res = self.client.put(
            "/api/admin/devis_requests",
            data=json.dumps({"id": item["id"], "status": "traite"}),
            content_type="application/json",
            **headers,
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])
        self.assertEqual(DevisRequest.objects.get().status, "traite")


class SeoTests(TestCase):
    def test_sitemap_and_robots(self):
        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertContains(sitemap, "<urlset")
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertContains(robots, "sitemap.xml")


@override_settings(ADMIN_TOKEN="secret-test")
class ServiceCrudAdminTests(TestCase):
    def setUp(self):
        self.h = {"HTTP_AUTHORIZATION": "Bearer secret-test"}

    def test_create_update_subservice_delete(self):
        res = self.client.post(
            "/api/admin/types_service",
            data=json.dumps({"title": "Audit Comptable", "slug": "audit-comptable", "short_desc": "Audit", "description": "Audit complet", "price_hint": "Sur devis", "icon": "clipboard"}),
            content_type="application/json",
            **self.h,
        )
        self.assertEqual(res.status_code, 200)
        parent_id = res.json()["id"]
        parent = Service.objects.get(pk=parent_id)
        self.assertIsNone(parent.parent)

        res = self.client.post(
            "/api/admin/types_service",
            data=json.dumps({"title": "Audit Externe", "slug": "audit-externe", "short_desc": "AE", "parent": str(parent_id)}),
            content_type="application/json",
            **self.h,
        )
        self.assertEqual(res.status_code, 200)
        sub = Service.objects.get(pk=res.json()["id"])
        self.assertEqual(sub.parent_id, parent_id)

        res = self.client.put(
            "/api/admin/types_service",
            data=json.dumps({"id": sub.id, "field": "title", "status": "Audit Externe Complet"}),
            content_type="application/json",
            **self.h,
        )
        self.assertEqual(res.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.title, "Audit Externe Complet")

        res = self.client.delete("/api/admin/types_service", data=json.dumps({"id": parent_id}), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 400)

        res = self.client.delete("/api/admin/types_service", data=json.dumps({"id": sub.id}), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Service.objects.filter(pk=sub.id).exists())

        res = self.client.delete("/api/admin/types_service", data=json.dumps({"id": parent_id}), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Service.objects.filter(pk=parent_id).exists())

    def test_cannot_delete_service_used_by_dossier(self):
        client = Client.objects.create(name="C", email="c@test.tn", phone="1")
        svc = Service.objects.create(title="S", slug="s", short_desc="d", description="x")
        ClientServiceSuivi.objects.create(client=client, type_service=svc)
        res = self.client.delete("/api/admin/types_service", data=json.dumps({"id": svc.id}), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 400)
        self.assertTrue(Service.objects.filter(pk=svc.id).exists())


class ClientMessageContextTests(TestCase):
    def setUp(self):
        res = self.client.post(
            "/api/auth/register",
            data=json.dumps({"name": "Doe", "prenom": "Jane", "email": "j@test.tn", "phone": "123", "matricule_fiscale": "1574T", "password": "password123"}),
            content_type="application/json",
        )
        self.token = res.json()["token"]
        self.client_model = Client.objects.get(email="j@test.tn")
        self.svc = Service.objects.create(title="Fiscalité", slug="fiscal", short_desc="f", description="x")
        self.dossier = ClientServiceSuivi.objects.create(client=self.client_model, type_service=self.svc, montant=100)
        self.h = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_send_message_linked_to_dossier_and_task(self):
        task = DossierTask.objects.create(dossier=self.dossier, titre="Déposer la TVA")
        res = self.client.post(
            "/api/client/messages",
            data=json.dumps({"text": "Où en est la déclaration ?", "dossier": str(self.dossier.id), "task": str(task.id)}),
            content_type="application/json",
            **self.h,
        )
        self.assertEqual(res.status_code, 200)
        msg = ClientMessage.objects.get()
        self.assertEqual(msg.dossier_id, self.dossier.id)
        self.assertEqual(msg.task_id, task.id)
        self.assertEqual(msg.service_id, self.svc.id)
        self.assertEqual(msg.context_label, f"Fiscalité (N°{self.dossier.id}) · Tâche : Déposer la TVA")

    def test_filter_messages_by_dossier(self):
        DossierTask.objects.create(dossier=self.dossier, titre="Déposer la TVA")
        self.client.post(
            "/api/client/messages",
            data=json.dumps({"text": "Suivi dossier", "dossier": str(self.dossier.id)}),
            content_type="application/json",
            **self.h,
        )
        res = self.client.get(f"/api/client/messages?dossier={self.dossier.id}", **self.h)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["messages"]), 1)
        self.assertEqual(res.json()["messages"][0]["dossier_service"], f"Fiscalité (N°{self.dossier.id})")

    def test_reject_task_of_another_dossier(self):
        other = ClientServiceSuivi.objects.create(client=self.client_model, type_service=self.svc)
        task2 = DossierTask.objects.create(dossier=other, titre="Autre tâche")
        res = self.client.post(
            "/api/client/messages",
            data=json.dumps({"text": "x", "dossier": str(self.dossier.id), "task": str(task2.id)}),
            content_type="application/json",
            **self.h,
        )
        self.assertEqual(res.status_code, 400)


@override_settings(ADMIN_TOKEN="secret-test")
class AdminMessagingContextTests(TestCase):
    def setUp(self):
        self.h = {"HTTP_AUTHORIZATION": "Bearer secret-test"}
        self.client_model = Client.objects.create(name="Doe Jane", email="j@test.tn", phone="123")
        self.svc = Service.objects.create(title="Fiscalité", slug="fiscal", short_desc="f", description="x")
        self.dossier = ClientServiceSuivi.objects.create(client=self.client_model, type_service=self.svc, montant=100)
        self.task = DossierTask.objects.create(dossier=self.dossier, titre="Déposer la TVA")

    def test_admin_reply_keeps_service_and_task_context(self):
        res = self.client.post(
            "/api/admin/client_messages",
            data=json.dumps({
                "client": str(self.client_model.id), "text": "Bien reçu",
                "dossier": str(self.dossier.id), "service": str(self.svc.id), "task": str(self.task.id),
            }),
            content_type="application/json",
            **self.h,
        )
        self.assertEqual(res.status_code, 200)
        msg = ClientMessage.objects.get(direction="admin")
        self.assertEqual(msg.dossier_id, self.dossier.id)
        self.assertEqual(msg.service_id, self.svc.id)
        self.assertEqual(msg.task_id, self.task.id)

    def test_admin_reject_task_of_another_client(self):
        other = Client.objects.create(name="Autre", email="autre@test.tn", phone="2")
        other_dossier = ClientServiceSuivi.objects.create(client=other, type_service=self.svc)
        other_task = DossierTask.objects.create(dossier=other_dossier, titre="Autre")
        res = self.client.post(
            "/api/admin/client_messages",
            data=json.dumps({"client": str(self.client_model.id), "text": "x", "task": str(other_task.id)}),
            content_type="application/json",
            **self.h,
        )
        self.assertEqual(res.status_code, 400)

    def test_admin_message_filters_by_dossier_service_task(self):
        ClientMessage.objects.create(client=self.client_model, direction="client", text="bonjour", dossier=self.dossier, service=self.svc, task=self.task)
        ClientMessage.objects.create(client=self.client_model, direction="client", text="général")
        for qs, expected in [
            (f"dossier={self.dossier.id}", 1),
            (f"service={self.svc.id}", 1),
            (f"task={self.task.id}", 1),
            ("dossier=999", 0),
        ]:
            res = self.client.get(f"/api/admin/client_messages?{qs}", **self.h)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(res.json()["items"]), expected)

    def test_admin_message_detail_returns_thread_and_context(self):
        m1 = ClientMessage.objects.create(client=self.client_model, direction="client", text="Où en est la TVA ?", dossier=self.dossier, service=self.svc, task=self.task)
        ClientMessage.objects.create(client=self.client_model, direction="admin", text="Déposée.", dossier=self.dossier, service=self.svc, task=self.task)
        res = self.client.get(f"/api/admin/detail/client_messages/{m1.id}", **self.h)
        self.assertEqual(res.status_code, 200)
        item = res.json()["item"]
        self.assertEqual(len(item["thread"]), 2)
        self.assertEqual(item["service_id"], self.svc.id)
        self.assertEqual(item["task_id"], self.task.id)


@override_settings(ADMIN_TOKEN="secret-test")
class AdminExplorerTests(TestCase):
    def setUp(self):
        self.h = {"HTTP_AUTHORIZATION": "Bearer secret-test"}
        self.client_model = Client.objects.create(name="Doe Jane", email="j@test.tn", phone="123")
        self.svc = Service.objects.create(title="Fiscalité", slug="fiscal", short_desc="f", description="x")
        self.dossier = ClientServiceSuivi.objects.create(client=self.client_model, type_service=self.svc, montant=100)
        DossierTask.objects.create(dossier=self.dossier, titre="Déposer la TVA")

    def test_explorer_requires_token(self):
        self.assertEqual(self.client.get("/api/admin/explorer").status_code, 401)

    def test_explorer_lists_clients_with_dossier_count(self):
        res = self.client.get("/api/admin/explorer", **self.h)
        self.assertEqual(res.status_code, 200)
        clients = res.json()["clients"]
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["dossier_count"], 1)

    def test_explorer_client_dossiers_with_counts(self):
        res = self.client.get(f"/api/admin/explorer/{self.client_model.id}", **self.h)
        self.assertEqual(res.status_code, 200)
        dossiers = res.json()["dossiers"]
        self.assertEqual(len(dossiers), 1)
        self.assertEqual(dossiers[0]["task_count"], 1)
        self.assertEqual(dossiers[0]["declaration_count"], 0)
        self.assertEqual(dossiers[0]["payment_count"], 0)

    def test_explorer_detail_includes_declarations_and_payments(self):
        DeclarationFiscale.objects.create(
            client=self.client_model, dossier=self.dossier,
            type_declaration="mensuelle", periode="Juillet 2026", date_echeance_legale="2026-08-20",
        )
        Payment.objects.create(client=self.client_model, dossier=self.dossier, amount=100, date="2026-08-01")
        res = self.client.get(f"/api/admin/detail/client_service_suivis/{self.dossier.id}", **self.h)
        self.assertEqual(res.status_code, 200)
        item = res.json()["item"]
        self.assertEqual(len(item["declarations"]), 1)
        self.assertEqual(len(item["payments"]), 1)


@override_settings(ADMIN_TOKEN="secret-test")
class CollaborateurAdminTests(TestCase):
    def setUp(self):
        self.h = {"HTTP_AUTHORIZATION": "Bearer secret-test"}

    def test_create_list_edit_actif_delete(self):
        res = self.client.post(
            "/api/admin/collaborateurs",
            data=json.dumps({"prenom": "Slim", "nom": "Ben Ali", "email": "slim@cabinet.tn", "telephone": "22", "fonction": "Comptable"}),
            content_type="application/json",
            **self.h,
        )
        self.assertEqual(res.status_code, 200)
        cid = res.json()["id"]
        collab = Collaborateur.objects.get(pk=cid)
        self.assertEqual(collab.display_name, "Slim Ben Ali")
        self.assertTrue(collab.actif)

        res = self.client.get("/api/admin/collaborateurs", **self.h)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["items"]), 1)
        self.assertEqual(res.json()["items"][0]["display_name"], "Slim Ben Ali")

        res = self.client.put(
            "/api/admin/collaborateurs",
            data=json.dumps({"id": cid, "field": "actif", "status": "false"}),
            content_type="application/json",
            **self.h,
        )
        self.assertEqual(res.status_code, 200)
        collab.refresh_from_db()
        self.assertFalse(collab.actif)

        res = self.client.delete("/api/admin/collaborateurs", data=json.dumps({"id": cid}), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Collaborateur.objects.filter(pk=cid).exists())

    def test_duplicate_email_rejected(self):
        Collaborateur.objects.create(nom="A", email="dup@cabinet.tn")
        res = self.client.post(
            "/api/admin/collaborateurs",
            data=json.dumps({"nom": "B", "email": "DUP@cabinet.tn"}),
            content_type="application/json",
            **self.h,
        )
        self.assertEqual(res.status_code, 400)


@override_settings(ADMIN_TOKEN="secret-test")
class ServiceFollowUpCollaborateurTests(TestCase):
    def setUp(self):
        self.h = {"HTTP_AUTHORIZATION": "Bearer secret-test"}
        self.client_model = Client.objects.create(name="Doe", email="d@test.tn", phone="1")
        self.svc = Service.objects.create(title="TVA", slug="tva", short_desc="t", description="x")
        self.dossier = ClientServiceSuivi.objects.create(client=self.client_model, type_service=self.svc)
        self.collab = Collaborateur.objects.create(nom="Slim", email="slim@cabinet.tn")

    def test_create_followup_with_collaborateur_and_filter(self):
        res = self.client.post(
            "/api/admin/service_followups",
            data=json.dumps({
                "client": str(self.client_model.id), "dossier": str(self.dossier.id),
                "type_service": str(self.svc.id), "collaborateur": str(self.collab.id),
                "status": "en_cours",
            }),
            content_type="application/json",
            **self.h,
        )
        self.assertEqual(res.status_code, 200)
        fup = ServiceFollowUp.objects.get()
        self.assertEqual(fup.collaborateur_id, self.collab.id)

        res = self.client.get(f"/api/admin/service_followups?collaborateur={self.collab.id}", **self.h)
        self.assertEqual(res.status_code, 200)
        items = res.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["collaborateur_name"], "Slim")

    def test_assign_collaborateur_via_put(self):
        fup = ServiceFollowUp.objects.create(client=self.client_model, dossier=self.dossier, service=self.svc)
        res = self.client.put(
            "/api/admin/service_followups",
            data=json.dumps({"id": fup.id, "field": "collaborateur", "status": str(self.collab.id)}),
            content_type="application/json",
            **self.h,
        )
        self.assertEqual(res.status_code, 200)
        fup.refresh_from_db()
        self.assertEqual(fup.collaborateur_id, self.collab.id)


@override_settings(ADMIN_TOKEN="secret-test")
class AdminDashboardTests(TestCase):
    def setUp(self):
        self.h = {"HTTP_AUTHORIZATION": "Bearer secret-test"}
        self.client_model = Client.objects.create(name="Doe", email="d@test.tn", phone="1")
        self.svc = Service.objects.create(title="TVA", slug="tva", short_desc="t", description="x")
        self.dossier = ClientServiceSuivi.objects.create(client=self.client_model, type_service=self.svc)
        self.collab = Collaborateur.objects.create(nom="Slim", email="slim@cabinet.tn")
        ServiceFollowUp.objects.create(client=self.client_model, dossier=self.dossier, service=self.svc, collaborateur=self.collab, status="en_cours")

    def test_dashboard_requires_token(self):
        self.assertEqual(self.client.get("/api/admin/dashboard").status_code, 401)

    def test_dashboard_counts_and_recent_followups(self):
        res = self.client.get("/api/admin/dashboard", **self.h)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["counts"]["clients"], 1)
        self.assertEqual(data["counts"]["dossiers_actifs"], 1)
        self.assertEqual(data["counts"]["suivis_en_cours"], 1)
        self.assertEqual(data["counts"]["collaborateurs_actifs"], 1)
        self.assertEqual(len(data["recent_followups"]), 1)
        self.assertEqual(data["recent_followups"][0]["collaborateur_name"], "Slim")

    def test_dashboard_notifications_chronological(self):
        task_todo = DossierTask.objects.create(dossier=self.dossier, titre="Déposer la TVA", date_echeance="2026-08-10")
        task_done = DossierTask.objects.create(dossier=self.dossier, titre="Terminée", statut="termine")
        ClientMessage.objects.create(client=self.client_model, direction="client", text="Où en est mon dossier ?")
        ClientMessage.objects.create(client=self.client_model, direction="client", text="Merci !")
        answered = ClientMessage.objects.create(client=self.client_model, direction="client", text="Question résolue ?", dossier=self.dossier)
        ClientMessage.objects.create(client=self.client_model, direction="admin", text="C'est réglé.", dossier=self.dossier)
        res = self.client.get("/api/admin/dashboard", **self.h)
        data = res.json()
        nc = data["notifications_counts"]
        self.assertEqual(nc["messages"], 2)  # messages généraux sans réponse, pas le message répondi
        self.assertEqual(nc["taches"], 1)  # seule la tâche à faire est notifiée
        feed = data["notifications"]
        self.assertTrue(all(x["sort_date"] <= y["sort_date"] for x, y in zip(feed, feed[1:])))
        msg = next(x for x in feed if x["kind"] == "message")
        self.assertEqual(msg["client_name"], "Doe")
        task = next(x for x in feed if x["kind"] == "tache")
        self.assertEqual(task["titre"], "Déposer la TVA")
        self.assertTrue(task["overdue"])
