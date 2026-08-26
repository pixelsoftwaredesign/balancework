import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

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
    DossierTask,
    EcritureComptable,
    Entreprise,
    Facture,
    LigneEcriture,
    Message,
    Payment,
    SecurityLog,
    Service,
    ServiceFollowUp,
    StaffProfile,
    StaffToken,
)
from .plan_comptable import seed_plan_comptable
from .security.tokens import new_client_token


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


@override_settings(ADMIN_TOKEN="secret-test")
class ComptabiliteTests(TestCase):
    def setUp(self):
        self.h = {"HTTP_AUTHORIZATION": "Bearer secret-test"}
        self.client_model = Client.objects.create(name="Doe", email="d@test.tn", phone="1")
        self.entreprise = Entreprise.objects.create(
            client=self.client_model, raison_sociale="Doe & Fils SARL"
        )
        seed_plan_comptable(self.entreprise)
        self.compte_treso = CompteComptable.objects.get(entreprise=self.entreprise, numero="5311")
        self.compte_vente = CompteComptable.objects.get(entreprise=self.entreprise, numero="707")
        self.compte_charge = CompteComptable.objects.get(entreprise=self.entreprise, numero="607")

    def _post_ecriture(self, lignes, statut="valide", piece="PC-001"):
        return self.client.post(
            "/api/admin/ecritures",
            data=json.dumps({
                "entreprise": self.entreprise.id,
                "journal": "od",
                "numero_piece": piece,
                "date": "2026-08-01",
                "libelle": "Vente prestation",
                "statut": statut,
                "lignes": lignes,
            }),
            content_type="application/json",
            **self.h,
        )

    def test_seed_plan_comptable_structure(self):
        classes = CompteComptable.objects.filter(entreprise=self.entreprise, parent__isnull=True)
        self.assertEqual(classes.count(), 7)
        self.assertEqual(list(classes.values_list("numero", flat=True)), ["1", "2", "3", "4", "5", "6", "7"])
        self.assertGreater(CompteComptable.objects.filter(entreprise=self.entreprise).count(), 30)
        compte = CompteComptable.objects.get(entreprise=self.entreprise, numero="5311")
        self.assertEqual(compte.niveau, 3)  # Classe 5 > 53 > 531 > 5311
        self.assertTrue(compte.is_leaf)

    def test_plan_api_tree_and_init(self):
        res = self.client.get(f"/api/admin/comptabilite/plan/{self.entreprise.id}", **self.h)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["plan"]), 7)
        self.assertEqual(data["plan"][0]["numero"], "1")
        # init sans doublon
        res2 = self.client.post(f"/api/admin/comptabilite/plan/init/{self.entreprise.id}", **self.h)
        self.assertFalse(res2.json()["seeded"])

    def test_ecriture_validee_alimente_grand_livre_et_bilan(self):
        res = self._post_ecriture([
            {"compte": self.compte_treso.id, "debit": "1000", "credit": ""},
            {"compte": self.compte_vente.id, "debit": "", "credit": "1000"},
        ])
        self.assertEqual(res.status_code, 200, res.json())
        ecr = EcritureComptable.objects.get()
        self.assertTrue(ecr.est_equilibree)
        gl = self.client.get(f"/api/admin/comptabilite/grand-livre/{self.entreprise.id}", **self.h).json()
        by_num = {c["numero"]: c for c in gl["comptes"]}
        self.assertEqual(by_num["5311"]["solde_debiteur"], "1000.000")
        self.assertEqual(by_num["707"]["solde_crediteur"], "1000.000")
        self.assertEqual(gl["total_debit"], gl["total_credit"])
        bilan = self.client.get(f"/api/admin/comptabilite/bilan/{self.entreprise.id}", **self.h).json()
        self.assertEqual(bilan["bilan"]["total_actif"], bilan["bilan"]["total_passif"])
        self.assertEqual(bilan["resultat"]["resultat"], "1000.000")

    def test_ecriture_desequilibree_rejetee(self):
        res = self._post_ecriture([
            {"compte": self.compte_treso.id, "debit": "500", "credit": ""},
            {"compte": self.compte_vente.id, "debit": "", "credit": "400"},
        ])
        self.assertEqual(res.status_code, 400)
        self.assertEqual(EcritureComptable.objects.count(), 0)

    def test_ecriture_brouillon_non_prise_en_compte_bilan(self):
        self._post_ecriture([
            {"compte": self.compte_treso.id, "debit": "2000", "credit": ""},
            {"compte": self.compte_vente.id, "debit": "", "credit": "2000"},
        ], statut="brouillon")
        bilan = self.client.get(f"/api/admin/comptabilite/bilan/{self.entreprise.id}", **self.h).json()
        self.assertEqual(bilan["resultat"]["resultat"], "0.000")

    def test_ajout_compte_custom(self):
        res = self.client.post(
            "/api/admin/comptes",
            data=json.dumps({
                "entreprise": self.entreprise.id,
                "parent": self.compte_charge.id,
                "numero": "6071",
                "intitule": "Achats de prestations",
            }),
            content_type="application/json",
            **self.h,
        )
        self.assertEqual(res.status_code, 200, res.json())
        c = CompteComptable.objects.get(entreprise=self.entreprise, numero="6071")
        self.assertEqual(c.parent_id, self.compte_charge.id)


@override_settings(ADMIN_TOKEN="secret-test")
class SecurityRbacTests(TestCase):
    def _staff(self, role):
        user = User.objects.create_user(username=f"u-{role}", email=f"{role}@cabinet.tn", password="mdp12345678")
        return StaffProfile.objects.create(user=user, role=role)

    def test_jeton_staff_lecture_lit_mais_ne_ecrit_pas(self):
        profil = self._staff("lecture")
        token = StaffToken.objects.create(profile=profil, key="tok_lecture")
        h = {"HTTP_AUTHORIZATION": "Bearer tok_lecture"}
        # lecture OK
        res = self.client.get("/api/admin/entreprises", **h)
        self.assertEqual(res.status_code, 200)
        # écriture refusée (comptes = niveau 60)
        res = self.client.post(
            "/api/admin/comptes",
            data=json.dumps({"entreprise": 1, "numero": "9999", "intitule": "X"}),
            content_type="application/json",
            **h,
        )
        self.assertEqual(res.status_code, 403)

    def test_jeton_staff_comptable_ecrit_comptes(self):
        profil = self._staff("comptable")
        StaffToken.objects.create(profile=profil, key="tok_comptable")
        h = {"HTTP_AUTHORIZATION": "Bearer tok_comptable"}
        client = Client.objects.create(name="C", email="c@rbac.tn", phone="1")
        entreprise = Entreprise.objects.create(client=client, raison_sociale="RBAC SARL")
        res = self.client.post(
            "/api/admin/comptes",
            data=json.dumps({"entreprise": entreprise.id, "numero": "9998", "intitule": "Compte test"}),
            content_type="application/json",
            **h,
        )
        self.assertEqual(res.status_code, 200, res.json())
        self.assertTrue(CompteComptable.objects.filter(numero="9998").exists())

    def test_gestion_staff_admin_uniquement(self):
        profil = self._staff("gestionnaire")
        StaffToken.objects.create(profile=profil, key="tok_gest")
        h = {"HTTP_AUTHORIZATION": "Bearer tok_gest"}
        res = self.client.get("/api/admin/staff", **h)
        self.assertEqual(res.status_code, 403)
        # jeton admin statique : autorisé
        res = self.client.get("/api/admin/staff", **self.h if hasattr(self, "h") else {"HTTP_AUTHORIZATION": "Bearer secret-test"})
        self.assertEqual(res.status_code, 200)

    def test_creation_staff_et_token(self):
        h = {"HTTP_AUTHORIZATION": "Bearer secret-test"}
        res = self.client.post(
            "/api/admin/staff",
            data=json.dumps({"username": "hajer", "email": "hajer@cabinet.tn", "full_name": "Hajer Ghiloufi", "password": "mdp12345678", "role": "comptable"}),
            content_type="application/json",
            **h,
        )
        self.assertEqual(res.status_code, 200, res.json())
        profil = StaffProfile.objects.get(user__username="hajer")
        res = self.client.post("/api/admin/staff/token", data=json.dumps({"profile": profil.id}), content_type="application/json", **h)
        self.assertEqual(res.status_code, 200)
        key = res.json()["key"]
        token = StaffToken.objects.get(key=key)
        self.assertTrue(token.is_valid)
        res = self.client.delete("/api/admin/staff/token", data=json.dumps({"id": token.id}), content_type="application/json", **h)
        self.assertEqual(res.status_code, 200)
        token.refresh_from_db()
        self.assertTrue(token.revoque)
        self.assertFalse(token.is_valid)

    def test_journal_securite_alimente(self):
        h = {"HTTP_AUTHORIZATION": "Bearer secret-test"}
        self.client.post("/api/auth/register", data=json.dumps({
            "name": "S", "prenom": "T", "email": "sec@test.tn", "phone": "1",
            "matricule_fiscale": "99X", "password": "mdp12345678",
        }), content_type="application/json")
        res = self.client.get("/api/admin/security/log", **h)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any(e["action"] == "register" for e in res.json()["items"]))


class ClientAuthSecurityTests(TestCase):
    def test_politique_mot_de_passe_faible_refusee(self):
        res = self.client.post("/api/auth/register", data=json.dumps({
            "name": "D", "prenom": "E", "email": "faible@test.tn", "phone": "1",
            "matricule_fiscale": "12A", "password": "12345",
        }), content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("au moins 8 caractères", res.json()["error"])

    def test_token_client_expire_est_rejete(self):
        res = self.client.post("/api/auth/register", data=json.dumps({
            "name": "D", "prenom": "E", "email": "exp@test.tn", "phone": "1",
            "matricule_fiscale": "13B", "password": "mdp12345678",
        }), content_type="application/json")
        token = AuthToken.objects.get(user__email="exp@test.tn")
        token.expires_at = timezone.now() - timedelta(days=1)
        token.save(update_fields=["expires_at"])
        h = {"HTTP_AUTHORIZATION": f"Bearer {token.key}"}
        res = self.client.get("/api/client/dashboard", **h)
        self.assertEqual(res.status_code, 401)
        self.assertFalse(AuthToken.objects.filter(pk=token.pk).exists())

    def test_login_throttle_apres_echecs(self):
        for i in range(6):
            res = self.client.post("/api/auth/login", data=json.dumps({
                "email": "absent@test.tn", "password": "wrong-pass",
            }), content_type="application/json")
        self.assertEqual(res.status_code, 429)
        self.assertEqual(SecurityLog.objects.filter(action="throttled").count(), 1)

    def test_mot_de_passe_hache_non_renvoye(self):
        res = self.client.post("/api/auth/register", data=json.dumps({
            "name": "D", "prenom": "E", "email": "hash@test.tn", "phone": "1",
            "matricule_fiscale": "14C", "password": "mdp12345678",
        }), content_type="application/json")
        self.assertNotIn("password", json.dumps(res.json()))
        user = User.objects.get(email="hash@test.tn")
        self.assertNotEqual(user.password, "mdp12345678")


@override_settings(ADMIN_TOKEN="secret-test")
class ClientEntrepriseCrudAdminTests(TestCase):
    """CRUD clients (admin) + entreprises tenant avec plan comptable seedé."""

    def setUp(self):
        self.h = {"HTTP_AUTHORIZATION": "Bearer secret-test"}

    def test_creation_client_et_mise_a_jour_statut(self):
        res = self.client.post("/api/admin/clients", data=json.dumps({
            "name": "Tunisie", "prenom": "Trans", "email": "trans@admin.tn",
            "phone": "22110011", "statut_client": "entreprise", "matricule_fiscale": "222333/7/A/M/000",
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200, res.json())
        cid = res.json()["id"]
        client = Client.objects.get(pk=cid)
        self.assertEqual(client.statut_client, "entreprise")
        self.assertEqual(client.display_name, "Trans Tunisie")
        res = self.client.put("/api/admin/clients", data=json.dumps({
            "id": cid, "field": "statut_client", "status": "personne_physique",
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200, res.json())
        client.refresh_from_db()
        self.assertEqual(client.statut_client, "personne_physique")

    def test_creation_entreprise_seed_plan_et_unicite(self):
        client = Client.objects.create(name="SARL", email="ent@admin.tn", phone="1", statut_client="entreprise")
        res = self.client.post("/api/admin/entreprises", data=json.dumps({
            "client": client.id, "raison_sociale": "Balance & Co SARL",
            "forme_juridique": "sarl", "ville": "Tunis",
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200, res.json())
        entreprise = Entreprise.objects.get(client=client)
        self.assertGreater(entreprise.comptes.count(), 30)
        # double création refusée
        res = self.client.post("/api/admin/entreprises", data=json.dumps({
            "client": client.id, "raison_sociale": "Doublon SARL",
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 400)

    def test_delete_entreprise_et_client(self):
        client = Client.objects.create(name="Del", email="del@admin.tn", phone="1")
        entreprise = Entreprise.objects.create(client=client, raison_sociale="Del SARL")
        res = self.client.delete("/api/admin/entreprises", data=json.dumps({"id": entreprise.id}), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200, res.json())
        res = self.client.delete("/api/admin/clients", data=json.dumps({"id": client.id}), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200, res.json())
        self.assertFalse(Client.objects.filter(pk=client.id).exists())

    def test_liste_entreprises_avec_nom_client(self):
        client = Client.objects.create(name="List", email="list@admin.tn", phone="1")
        Entreprise.objects.create(client=client, raison_sociale="List SARL")
        res = self.client.get("/api/admin/entreprises", **self.h)
        self.assertEqual(res.status_code, 200)
        item = next(i for i in res.json()["items"] if i["id"] == client.entreprise.id)
        self.assertEqual(item["raison_sociale"], "List SARL")
        self.assertEqual(item["client_name"], "List")


class EspaceEntrepriseComptabiliteTests(TestCase):
    """Espace entreprise (tenant) : /api/client/comptabilite."""

    def setUp(self):
        self.client_model = Client.objects.create(
            name="Tenant", email="tenant@espace.tn", phone="1",
            user=User.objects.create_user(username="tenant@espace.tn", email="tenant@espace.tn", password="mdp12345678"),
        )
        token = new_client_token(self.client_model.user)
        self.h = {"HTTP_AUTHORIZATION": f"Bearer {token.key}"}

    def _entreprise(self):
        ent = Entreprise.objects.create(client=self.client_model, raison_sociale="Tenant SARL")
        seed_plan_comptable(ent)
        return ent

    def test_requiert_authentification(self):
        res = self.client.get("/api/client/comptabilite")
        self.assertEqual(res.status_code, 401)

    def test_404_sans_entreprise_associee(self):
        res = self.client.get("/api/client/comptabilite", **self.h)
        self.assertEqual(res.status_code, 404)

    def test_get_plan_et_bilan_bien_formes(self):
        ent = self._entreprise()
        res = self.client.get("/api/client/comptabilite", **self.h)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["entreprise"]["id"], ent.id)
        self.assertGreater(data["plan_total"], 30)
        self.assertEqual(len(data["plan"]), 7)  # 7 classes
        self.assertIn("bilan", data["bilan"])
        self.assertIn("resultat", data["bilan"])
        self.assertEqual(data["ecritures"], [])

    def test_creation_statut_suppression_ecriture(self):
        self._entreprise()
        treso = CompteComptable.objects.get(entreprise=self.client_model.entreprise, numero="5311")
        caisse = CompteComptable.objects.get(entreprise=self.client_model.entreprise, numero="541")
        res = self.client.post("/api/client/comptabilite", data=json.dumps({
            "action": "ecriture_create", "journal": "banque", "numero_piece": "T-001",
            "date": "2026-08-12", "libelle": "Dépôt en banque",
            "lignes": [
                {"compte": treso.id, "debit": "1000.000", "credit": "0"},
                {"compte": caisse.id, "debit": "0", "credit": "1000.000"},
            ],
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200, res.json())
        eid = res.json()["id"]
        res = self.client.post("/api/client/comptabilite", data=json.dumps({
            "action": "ecriture_statut", "id": eid, "statut": "valide",
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200)
        data = self.client.get("/api/client/comptabilite", **self.h).json()
        self.assertEqual(data["ecritures"][0]["statut"], "valide")
        self.assertEqual(data["grand_livre"]["total_debit"], data["grand_livre"]["total_credit"])
        self.assertEqual(data["bilan"]["resultat"]["resultat"], "0.000")
        res = self.client.delete("/api/client/comptabilite", data=json.dumps({
            "kind": "ecriture", "id": eid,
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(EcritureComptable.objects.filter(entreprise=self.client_model.entreprise).count(), 0)

    def test_piece_desequilibree_refusee(self):
        self._entreprise()
        treso = CompteComptable.objects.get(entreprise=self.client_model.entreprise, numero="5311")
        caisse = CompteComptable.objects.get(entreprise=self.client_model.entreprise, numero="541")
        res = self.client.post("/api/client/comptabilite", data=json.dumps({
            "action": "ecriture_create", "journal": "od", "numero_piece": "T-002",
            "date": "2026-08-12", "libelle": "Déséquilibrée",
            "lignes": [
                {"compte": treso.id, "debit": "500", "credit": "0"},
                {"compte": caisse.id, "debit": "0", "credit": "400"},
            ],
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(EcritureComptable.objects.count(), 0)

    def test_compte_protege_si_utilise_et_creation_compte(self):
        self._entreprise()
        treso = CompteComptable.objects.get(entreprise=self.client_model.entreprise, numero="5311")
        charge = CompteComptable.objects.get(entreprise=self.client_model.entreprise, numero="607")
        res = self.client.post("/api/client/comptabilite", data=json.dumps({
            "action": "ecriture_create", "journal": "od", "numero_piece": "T-003",
            "date": "2026-08-12", "libelle": "Charge",
            "lignes": [
                {"compte": charge.id, "debit": "100", "credit": "0"},
                {"compte": treso.id, "debit": "0", "credit": "100"},
            ],
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200, res.json())
        # compte utilisé : suppression protégée
        res = self.client.delete("/api/client/comptabilite", data=json.dumps({
            "kind": "compte", "id": treso.id,
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 400)
        # création compte personnalisé sous la classe 6
        res = self.client.post("/api/client/comptabilite", data=json.dumps({
            "action": "compte_create", "parent": charge.id, "numero": "6071", "intitule": "Achats de prestations",
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200, res.json())
        self.assertTrue(CompteComptable.objects.filter(entreprise=self.client_model.entreprise, numero="6071").exists())
        # compte libre : suppression OK
        libre = CompteComptable.objects.create(entreprise=self.client_model.entreprise, numero="9999", intitule="À supprimer")
        res = self.client.delete("/api/client/comptabilite", data=json.dumps({
            "kind": "compte", "id": libre.id,
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200)

    def test_client_ne_voit_pas_entreprise_d_autrui(self):
        self._entreprise()
        autre = Client.objects.create(
            name="Autre", email="autre@espace.tn", phone="2",
            user=User.objects.create_user(username="autre@espace.tn", email="autre@espace.tn", password="mdp12345678"),
        )
        autre_ent = Entreprise.objects.create(client=autre, raison_sociale="Autre SARL")
        res = self.client.post("/api/client/comptabilite", data=json.dumps({
            "action": "compte_create", "numero": "9998", "intitule": "Intrusion",
        }), content_type="application/json", **self.h)
        # crée un compte dans la propre entreprise (pas dans celle d'autrui)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(autre_ent.comptes.filter(numero="9998").exists())
        # suppression d'une écriture d'autrui → 404
        res = self.client.delete("/api/client/comptabilite", data=json.dumps({
            "kind": "ecriture", "id": 999999,
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 404)


class FacturationTejTests(TestCase):
    """Facturation tenant + conformité TEJ (retenue à la source, CCT-RS-V2)."""

    def setUp(self):
        self.client_model = Client.objects.create(
            name="Tenant", email="fac@espace.tn", phone="1",
            user=User.objects.create_user(username="fac@espace.tn", email="fac@espace.tn", password="mdp12345678"),
        )
        self.entreprise = Entreprise.objects.create(client=self.client_model, raison_sociale="Facturation SARL")
        seed_plan_comptable(self.entreprise)
        token = new_client_token(self.client_model.user)
        self.h = {"HTTP_AUTHORIZATION": f"Bearer {token.key}"}

    def _facture(self, type_facture="achat", numero="FA-001", tiers="Prestataire Y",
                 identifiant="9988776B", nature="honoraires_reel", ht="2000.000", tva="19"):
        return self.client.post("/api/client/factures", data=json.dumps({
            "action": "facture_create", "type_facture": type_facture, "numero": numero,
            "date": "2026-08-05", "tiers": tiers,
            "tiers_identifiant_type": "matricule", "tiers_identifiant": identifiant,
            "nature_operation": nature, "montant_ht": ht, "taux_tva": tva,
        }), content_type="application/json", **self.h)

    def test_calculs_service_retenue_et_timbre(self):
        from core.services import facturation
        m = facturation.calculer_montants("2000.000", "19", "honoraires_reel", "achat")
        self.assertEqual(str(m["montant_ttc"]), "2380.000")
        self.assertEqual(str(m["timbre_fiscal"]), "1.000")
        self.assertEqual(str(m["retenue_source_taux"]), "3.00")
        self.assertEqual(str(m["retenue_source_montant"]), "71.370")
        self.assertEqual(str(m["net_a_payer"]), "2308.630")
        # acquisition sous le seuil de 1 000 TND → pas de retenue
        m2 = facturation.calculer_montants("500.000", "19", "acquisition", "achat")
        self.assertEqual(str(m2["retenue_source_montant"]), "0.000")
        # vente : pas de retenue, mais droit de timbre si ≥ 1 000 TND TTC
        m3 = facturation.calculer_montants("2000.000", "19", "acquisition", "vente")
        self.assertEqual(str(m3["timbre_fiscal"]), "1.000")
        self.assertEqual(str(m3["retenue_source_montant"]), "0.000")

    def test_facture_achat_validee_genere_ecriture(self):
        res = self._facture()
        self.assertEqual(res.status_code, 200, res.json())
        fid = res.json()["id"]
        f = Facture.objects.get(pk=fid)
        self.assertEqual(str(f.retenue_source_montant), "71.370")
        res = self.client.post("/api/client/factures", data=json.dumps({
            "action": "facture_statut", "id": fid, "statut": "valide",
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200, res.json())
        f.refresh_from_db()
        ecr = f.ecriture
        self.assertIsNotNone(ecr)
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.journal, "achats")
        lignes = {l.compte.numero: (l.debit, l.credit) for l in ecr.lignes.all()}
        self.assertEqual(str(lignes["637"][0]), "2000.000")
        self.assertEqual(str(lignes["445"][1]), "71.370")
        self.assertEqual(str(lignes["401"][1]), "2308.630")
        self.assertEqual(str(lignes["442"][0]), "380.000")

    def test_facture_vente_ecriture(self):
        res = self._facture(type_facture="vente", numero="FV-001", ht="1000.000")
        self.assertEqual(res.status_code, 200, res.json())
        fid = res.json()["id"]
        self.client.post("/api/client/factures", data=json.dumps({
            "action": "facture_statut", "id": fid, "statut": "valide",
        }), content_type="application/json", **self.h)
        f = Facture.objects.get(pk=fid)
        lignes = {l.compte.numero: (l.debit, l.credit) for l in f.ecriture.lignes.all()}
        self.assertEqual(str(lignes["431"][0]), "1190.000")
        self.assertEqual(str(lignes["707"][1]), "1000.000")
        self.assertEqual(str(lignes["443"][1]), "190.000")
        self.assertTrue(f.ecriture.est_equilibree)

    def test_facture_validee_non_modifiable_et_annulee_supprime_ecriture(self):
        fid = self._facture().json()["id"]
        self.client.post("/api/client/factures", data=json.dumps({
            "action": "facture_statut", "id": fid, "statut": "valide",
        }), content_type="application/json", **self.h)
        # facture validée (écriture validée) : modification refusée
        res = self.client.post("/api/client/factures", data=json.dumps({
            "action": "facture_update", "id": fid, "field": "tiers", "value": "Autre",
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 400)
        # annulation directe refusée tant que l'écriture est validée
        res = self.client.post("/api/client/factures", data=json.dumps({
            "action": "facture_statut", "id": fid, "statut": "annulee",
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 400)
        # repasser l'écriture en brouillon, puis annuler la facture → écriture supprimée
        f = Facture.objects.get(pk=fid)
        ecr_id = f.ecriture_id
        self.client.post("/api/client/comptabilite", data=json.dumps({
            "action": "ecriture_statut", "id": ecr_id, "statut": "brouillon",
        }), content_type="application/json", **self.h)
        res = self.client.post("/api/client/factures", data=json.dumps({
            "action": "facture_statut", "id": fid, "statut": "annulee",
        }), content_type="application/json", **self.h)
        self.assertEqual(res.status_code, 200, res.json())
        f.refresh_from_db()
        self.assertIsNone(f.ecriture_id)
        self.assertFalse(EcritureComptable.objects.filter(pk=ecr_id).exists())

    def test_export_tej_xml_conforme(self):
        self._facture(numero="FA-001", tiers="Prestataire Y", identifiant="9988776B", ht="2000.000")
        fid = Facture.objects.get(numero="FA-001").id
        self.client.post("/api/client/factures", data=json.dumps({
            "action": "facture_statut", "id": fid, "statut": "valide",
        }), content_type="application/json", **self.h)
        res = self.client.get("/api/client/tej?mois=2026-08", **self.h)
        self.assertEqual(res.status_code, 200, res.json())
        data = res.json()
        self.assertEqual(data["totaux"]["nb_certificats"], 1)
        self.assertEqual(data["totaux"]["total_retenue"], "71.370")
        self.assertIn("<DeclarationsRS>", data["xml"])
        self.assertIn("<MatriculeFiscal>9988776B</MatriculeFiscal>", data["xml"])
        # montants en millimes entiers
        self.assertIn("<MontantNetServi>2308630</MontantNetServi>", data["xml"])
        self.assertIn(f"<Ref_certif_chez_declarant>RS-{fid:06d}</Ref_certif_chez_declarant>", data["xml"])
        self.assertIn("<MoisDepot>08</MoisDepot>", data["xml"])

    def test_export_tej_regroupe_par_beneficiaire_et_bloque_non_conforme(self):
        self._facture(numero="FA-001", tiers="Prestataire Y", identifiant="9988776B", ht="2000.000")
        self._facture(numero="FA-002", tiers="Prestataire Y", identifiant="9988776B", ht="1000.000")
        for numero in ("FA-001", "FA-002"):
            fid = Facture.objects.get(numero=numero).id
            self.client.post("/api/client/factures", data=json.dumps({
                "action": "facture_statut", "id": fid, "statut": "valide",
            }), content_type="application/json", **self.h)
        data = self.client.get("/api/client/tej?mois=2026-08", **self.h).json()
        self.assertEqual(data["totaux"]["nb_certificats"], 1)
        self.assertEqual(data["totaux"]["nb_operations"], 2)
        # facture non conforme (identifiant manquant) → export bloqué
        self._facture(numero="FA-003", tiers="Fournisseur Z", identifiant="", ht="500.000")
        fid = Facture.objects.get(numero="FA-003").id
        self.client.post("/api/client/factures", data=json.dumps({
            "action": "facture_statut", "id": fid, "statut": "valide",
        }), content_type="application/json", **self.h)
        res = self.client.get("/api/client/tej?mois=2026-08", **self.h)
        self.assertEqual(res.status_code, 400)
        self.assertIn("FA-003", res.json()["error"])
        self.assertTrue(any(c["numero"] == "FA-003" for c in res.json()["controles"]))

    def test_facture_sans_entreprise_404(self):
        sans = Client.objects.create(
            name="Sans", email="sans@espace.tn", phone="3",
            user=User.objects.create_user(username="sans@espace.tn", email="sans@espace.tn", password="mdp12345678"),
        )
        t = new_client_token(sans.user)
        res = self.client.get("/api/client/factures", **{"HTTP_AUTHORIZATION": f"Bearer {t.key}"})
        self.assertEqual(res.status_code, 404)
