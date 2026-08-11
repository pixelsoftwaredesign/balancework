const BalanceAdmin = (() => {
  const API_BASE = window.BALANCEWORK_API || "";
  const TOKEN_KEY = "bts_admin_token";
  let currentTab = "dashboard";

  const TITLES = {
    dashboard: "Aperçu général",
    client_messages: "Messagerie clients",
    clients: "Gestion clients",
    explorer: "Explorateur dossiers",
    client_service_suivis: "Dossiers clients",
    dossier_tasks: "Tâches",
    service_followups: "Suivi services",
    prefactures: "Préfactures",
    dossier_attachments: "Pièces jointes",
    declarations: "Déclarations fiscales",
    payments: "Paiements",
    collaborateurs: "Gestion personnel",
    devis_requests: "Demandes de devis",
    appointments: "Rendez-vous",
    messages: "Messages du site",
    types_service: "Types de service",
  };

  const STATUS_OPTIONS = {
    devis_requests: ["nouveau", "en_cours", "traite", "annule"],
    appointments: ["confirme", "en_attente", "annule"],
    messages: ["nouveau", "traite", "annule"],
    payments: ["en_attente", "partiel", "paye", "retard", "annule"],
    service_followups: ["en_attente", "en_cours", "termine", "cloture", "annule"],
    client_service_suivis: {
      statut_paiement: ["en_attente", "paye", "retard"],
      statut_service: ["en_cours", "valide", "cloture"],
      frequence: ["ponctuel", "mensuel", "trimestriel", "semestriel", "annuel"],
    },
    dossier_tasks: { statut: ["a_faire", "en_cours", "termine"], repetition: ["ponctuel", "mensuel", "trimestriel", "semestriel", "annuel"] },
    prefactures: { statut: ["emise", "payee", "annulee"] },
    declarations: {
      statut: ["a_faire", "en_cours", "depose", "retard"],
      type_declaration: ["mensuelle", "acompte", "annuelle", "autre"],
    },
  };

  function token() {
    return sessionStorage.getItem(TOKEN_KEY) || "";
  }

  async function api(path, options = {}) {
    const res = await fetch(API_BASE + path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token()}`,
        ...(options.headers || {}),
      },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Erreur");
    return data;
  }

  function login() {
    const input = document.getElementById("token-input");
    const err = document.getElementById("login-error");
    sessionStorage.setItem(TOKEN_KEY, input.value.trim());
    api("/api/admin/dashboard")
      .then(() => {
        err.className = "alert";
        showPanel();
      })
      .catch(() => {
        sessionStorage.removeItem(TOKEN_KEY);
        err.className = "alert show alert-error";
        err.textContent = "Jeton invalide.";
      });
  }

  function logout() {
    sessionStorage.removeItem(TOKEN_KEY);
    document.getElementById("admin-panel").style.display = "none";
    document.getElementById("login-box").style.display = "";
  }

  function showPanel() {
    document.getElementById("login-box").style.display = "none";
    document.getElementById("admin-panel").style.display = "";
    loadTab(currentTab);
  }

  function switchTab(tab) {
    currentTab = tab;
    stopLive();
    document.querySelectorAll(".admin-nav button").forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === tab);
    });
    const title = document.getElementById("admin-title");
    if (title) title.textContent = TITLES[tab] || "Administration";
    document.getElementById("create-box").style.display = "none";
    document.getElementById("create-box").innerHTML = "";
    document.getElementById("create-btn").style.display = CREATE_FORMS[tab] ? "" : "none";
    loadTab(tab);
  }

  const CREATE_FORMS = {
    clients: [
      { name: "name", label: "Nom *", type: "text" },
      { name: "prenom", label: "Prénom", type: "text" },
      { name: "email", label: "E-mail *", type: "email" },
      { name: "phone", label: "Téléphone", type: "text" },
      { name: "company", label: "Société", type: "text" },
      { name: "matricule_fiscale", label: "Matricule fiscale", type: "text" },
      { name: "cin", label: "CIN", type: "text" },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
    client_service_suivis: [
      { name: "client", label: "Client *", type: "select", source: "/api/admin/clients", valueKey: "id", textKey: (c) => c.name },
      { name: "type_service", label: "Service *", type: "select", source: "/api/admin/types_service", valueKey: "id", textKey: (s) => s.title },
      { name: "montant", label: "Montant (TND) *", type: "number", step: "0.001" },
      { name: "statut_paiement", label: "Statut paiement", type: "select", options: ["en_attente", "paye", "retard"] },
      { name: "statut_service", label: "Statut dossier", type: "select", options: ["en_cours", "valide", "cloture"] },
      { name: "date_echeance", label: "Échéance (AAAA-MM-JJ)", type: "date" },
      { name: "commentaire", label: "Note du dossier", type: "textarea" },
      { name: "service_note", label: "Note du service (dans le dossier)", type: "textarea" },
      { name: "tache_titre", label: "Tâche — titre (optionnel)", type: "text" },
      { name: "tache_echeance", label: "Tâche — échéance (AAAA-MM-JJ)", type: "date" },
      { name: "tache_repetition", label: "Tâche — répétition", type: "select", options: ["ponctuel", "mensuel", "trimestriel", "semestriel", "annuel"] },
    ],
    client_messages: [
      { name: "client", label: "Client *", type: "select", source: "/api/admin/clients", valueKey: "id", textKey: (c) => c.name },
      { name: "dossier", label: "Dossier lié (optionnel)", type: "select", source: "/api/admin/client_service_suivis", valueKey: "id", textKey: (d) => d.client_name + " — " + d.service_title + " (N°" + d.id + ")" },
      { name: "service", label: "Service lié (optionnel)", type: "select", source: "/api/admin/types_service", valueKey: "id", textKey: (s) => s.title },
      { name: "task", label: "Tâche liée (optionnel)", type: "select", source: "/api/admin/dossier_tasks", valueKey: "id", textKey: (t) => t.client_name + " — " + t.titre + " (N°" + t.id + ")" },
      { name: "text", label: "Réponse au client *", type: "textarea" },
    ],
    dossier_tasks: [
      { name: "dossier", label: "Dossier *", type: "select", source: "/api/admin/client_service_suivis", valueKey: "id", textKey: (d) => d.client_name + " — " + d.service_title },
      { name: "service_followup", label: "Suivi de service lié (optionnel)", type: "select", source: "/api/admin/service_followups", valueKey: "id", textKey: (s) => s.client_name + " — " + s.service_title + " (N°" + s.id + ")" },
      { name: "titre", label: "Titre de la tâche *", type: "text" },
      { name: "description", label: "Description", type: "textarea" },
      { name: "statut", label: "Statut", type: "select", options: ["a_faire", "en_cours", "termine"] },
      { name: "date_echeance", label: "Échéance (AAAA-MM-JJ)", type: "date" },
      { name: "repetition", label: "Répétition", type: "select", options: ["ponctuel", "mensuel", "trimestriel", "semestriel", "annuel"] },
    ],
    dossier_attachments: [
      { name: "dossier", label: "Dossier *", type: "select", source: "/api/admin/client_service_suivis", valueKey: "id", textKey: (d) => d.client_name + " — " + d.service_title },
      { name: "file", label: "Fichier *", type: "file" },
    ],
    prefactures: [
      { name: "dossier", label: "Dossier *", type: "select", source: "/api/admin/client_service_suivis", valueKey: "id", textKey: (d) => d.client_name + " — " + d.service_title },
      { name: "taux_tva", label: "Taux TVA (%)", type: "number", step: "0.01" },
    ],
    declarations: [
      { name: "client", label: "Client *", type: "select", source: "/api/admin/clients", valueKey: "id", textKey: (c) => c.name },
      { name: "type_declaration", label: "Type de déclaration *", type: "select", options: ["mensuelle", "acompte", "annuelle", "autre"] },
      { name: "periode", label: "Période (ex : Mois de Juillet 2026) *", type: "text" },
      { name: "date_echeance_legale", label: "Date limite légale *", type: "date" },
      { name: "statut", label: "Statut", type: "select", options: ["a_faire", "en_cours", "depose", "retard"] },
      { name: "montant_a_payer", label: "Montant net à payer (TND)", type: "number", step: "0.001" },
      { name: "numero_quittance_ou_tej", label: "N° quittance / accusé de dépôt", type: "text" },
      { name: "notes_collaborateur", label: "Remarques internes ou conseils", type: "textarea" },
    ],
    types_service: {
      id: "types_service",
      label: "Ajouter un service",
      fields: [
        { name: "parent", label: "Service parent (sous-service)", type: "select", source: "/api/admin/types_service", valueKey: "id", textKey: (s) => (s.parent_title !== "—" ? s.parent_title + " › " + s.title : s.title + " (service principal)") },
        { name: "title", label: "Titre *", type: "text" },
        { name: "slug", label: "Identifiant (slug) *", type: "text" },
        { name: "short_desc", label: "Résumé *", type: "text" },
        { name: "description", label: "Description", type: "textarea" },
        { name: "price_hint", label: "Indication tarifaire", type: "text" },
        { name: "icon", label: "Icône", type: "text" },
      ],
    },
    service_followups: [
      { name: "client", label: "Client *", type: "select", source: "/api/admin/clients", valueKey: "id", textKey: (c) => c.name },
      { name: "dossier", label: "Dossier associé *", type: "select", source: "/api/admin/client_service_suivis", valueKey: "id", textKey: (d) => d.client_name + " — " + d.service_title + " (N°" + d.id + ")" },
      { name: "type_service", label: "Service *", type: "select", source: "/api/admin/types_service", valueKey: "id", textKey: (s) => s.title },
      { name: "collaborateur", label: "Collaborateur assigné", type: "select", source: "/api/admin/collaborateurs", valueKey: "id", textKey: (s) => s.display_name },
      { name: "status", label: "Statut", type: "select", options: ["en_attente", "en_cours", "termine", "cloture", "annule"] },
      { name: "start_date", label: "Date de début (AAAA-MM-JJ)", type: "date" },
      { name: "due_date", label: "Échéance (AAAA-MM-JJ)", type: "date" },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
    collaborateurs: [
      { name: "prenom", label: "Prénom", type: "text" },
      { name: "nom", label: "Nom *", type: "text" },
      { name: "email", label: "E-mail *", type: "email" },
      { name: "telephone", label: "Téléphone", type: "text" },
      { name: "fonction", label: "Fonction / Poste", type: "text" },
      { name: "actif", label: "Actif", type: "select", options: ["true", "false"] },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
    payments: [
      { name: "client", label: "Client *", type: "select", source: "/api/admin/clients", valueKey: "id", textKey: (c) => c.name },
      { name: "dossier", label: "Dossier lié (optionnel)", type: "select", source: "/api/admin/client_service_suivis", valueKey: "id", textKey: (d) => d.client_name + " — " + d.service_title + " (N°" + d.id + ")" },
      { name: "amount", label: "Montant (TND) *", type: "number", step: "0.01" },
      { name: "date", label: "Date (AAAA-MM-JJ)", type: "date" },
      { name: "status", label: "Statut", type: "select", options: ["en_attente", "partiel", "paye", "retard", "annule"] },
      { name: "method", label: "Mode de paiement", type: "text" },
      { name: "notes", label: "Notes", type: "textarea" },
    ],
  };

  const COLUMNS = {
    devis_requests: [
      { key: "id", label: "N°" },
      { key: "name", label: "Nom" },
      { key: "email", label: "E-mail" },
      { key: "phone", label: "Tél." },
      { key: "company", label: "Société" },
      { key: "service_title", label: "Service" },
      { key: "budget", label: "Budget" },
      { key: "details", label: "Détails" },
      { key: "status", label: "Statut" },
      { key: "created_at", label: "Reçu le" },
    ],
    appointments: [
      { key: "id", label: "N°" },
      { key: "name", label: "Nom" },
      { key: "email", label: "E-mail" },
      { key: "phone", label: "Tél." },
      { key: "service_title", label: "Service" },
      { key: "date", label: "Date" },
      { key: "time", label: "Heure" },
      { key: "notes", label: "Notes" },
      { key: "status", label: "Statut" },
    ],
    messages: [
      { key: "id", label: "N°" },
      { key: "name", label: "Nom" },
      { key: "email", label: "E-mail" },
      { key: "phone", label: "Tél." },
      { key: "subject", label: "Sujet" },
      { key: "message", label: "Message" },
      { key: "status", label: "Statut" },
    ],
    clients: [
      { key: "id", label: "N°" },
      { key: "name", label: "Nom" },
      { key: "email", label: "E-mail" },
      { key: "phone", label: "Tél." },
      { key: "company", label: "Société" },
      { key: "notes", label: "Notes" },
      { key: "created_at", label: "Ajouté le" },
    ],
    payments: [
      { key: "id", label: "N°" },
      { key: "client_name", label: "Client" },
      { key: "dossier_service", label: "Dossier" },
      { key: "amount", label: "Montant (TND)" },
      { key: "date", label: "Date" },
      { key: "status", label: "Statut" },
      { key: "method", label: "Mode" },
      { key: "notes", label: "Notes" },
    ],
    service_followups: [
      { key: "id", label: "N°" },
      { key: "client_name", label: "Client" },
      { key: "service_title", label: "Service" },
      { key: "dossier_label", label: "Dossier" },
      { key: "collaborateur_name", label: "Collaborateur" },
      { key: "status", label: "Statut" },
      { key: "start_date", label: "Début" },
      { key: "due_date", label: "Échéance" },
      { key: "notes", label: "Notes" },
    ],
    collaborateurs: [
      { key: "id", label: "N°" },
      { key: "display_name", label: "Nom complet" },
      { key: "fonction", label: "Fonction" },
      { key: "email", label: "E-mail" },
      { key: "telephone", label: "Tél." },
      { key: "actif", label: "Actif" },
      { key: "notes", label: "Notes" },
    ],
    types_service: [
      { key: "id", label: "N°" },
      { key: "parent_title", label: "Service parent" },
      { key: "title", label: "Service" },
      { key: "slug", label: "Identifiant" },
      { key: "short_desc", label: "Résumé" },
    ],
    client_service_suivis: [
      { key: "id", label: "N°" },
      { key: "client_name", label: "Client" },
      { key: "service_title", label: "Service" },
      { key: "montant", label: "Montant (TND)" },
      { key: "statut_paiement", label: "Paiement" },
      { key: "statut_service", label: "Dossier" },
      { key: "date_echeance", label: "Échéance" },
      { key: "frequence", label: "Fréquence" },
      { key: "commentaire", label: "Note dossier" },
      { key: "service_note", label: "Note service" },
    ],
    dossier_tasks: [
      { key: "id", label: "N°" },
      { key: "client_name", label: "Client" },
      { key: "dossier_service", label: "Dossier" },
      { key: "followup_title", label: "Suivi service" },
      { key: "titre", label: "Tâche" },
      { key: "statut", label: "Statut" },
      { key: "date_echeance", label: "Échéance" },
      { key: "repetition", label: "Répétition" },
    ],
    prefactures: [
      { key: "id", label: "N°" },
      { key: "client_name", label: "Client" },
      { key: "dossier_service", label: "Dossier" },
      { key: "numero", label: "Numéro" },
      { key: "date", label: "Date" },
      { key: "montant_ttc", label: "TTC (TND)" },
      { key: "statut", label: "Statut" },
    ],
    declarations: [
      { key: "id", label: "N°" },
      { key: "client_name", label: "Client" },
      { key: "type_declaration", label: "Type" },
      { key: "periode", label: "Période" },
      { key: "date_echeance_legale", label: "Échéance légale" },
      { key: "statut", label: "Statut" },
      { key: "numero_quittance_ou_tej", label: "N° quittance / TEJ" },
      { key: "montant_a_payer", label: "Montant (TND)" },
      { key: "notes_collaborateur", label: "Notes" },
    ],
    client_messages: [
      { key: "id", label: "N°" },
      { key: "client_name", label: "Client" },
      { key: "dossier_service", label: "Dossier" },
      { key: "service_title", label: "Service" },
      { key: "task_title", label: "Tâche" },
      { key: "direction", label: "Sens" },
      { key: "text", label: "Message" },
      { key: "created_at", label: "Date" },
    ],
    dossier_attachments: [
      { key: "id", label: "N°" },
      { key: "client_name", label: "Client" },
      { key: "dossier_service", label: "Dossier" },
      { key: "original_name", label: "Fichier" },
      { key: "category", label: "Type" },
      { key: "size", label: "Taille" },
      { key: "uploaded_by", label: "Ajouté par" },
      { key: "created_at", label: "Ajouté le" },
    ],
  };

  const DETAIL_TABLES = ["client_service_suivis", "service_followups", "dossier_tasks", "types_service", "client_messages"];

  const EDIT_FIELDS = {
    client_service_suivis: {
      montant: { type: "number", step: "0.001" },
      frequence: { type: "select", options: ["ponctuel", "mensuel", "trimestriel", "semestriel", "annuel"] },
      date_echeance: { type: "date" },
      statut_paiement: { type: "select", options: ["en_attente", "paye", "retard"] },
      statut_service: { type: "select", options: ["en_cours", "valide", "cloture"] },
      commentaire: { type: "text" },
      service_note: { type: "text" },
    },
    service_followups: {
      status: { type: "select", options: ["en_attente", "en_cours", "termine", "cloture", "annule"] },
      start_date: { type: "date" },
      due_date: { type: "date" },
      notes: { type: "text" },
    },
    dossier_tasks: {
      statut: { type: "select", options: ["a_faire", "en_cours", "termine"] },
      titre: { type: "text" },
      date_echeance: { type: "date" },
      repetition: { type: "select", options: ["ponctuel", "mensuel", "trimestriel", "semestriel", "annuel"] },
    },
    types_service: {
      title: { type: "text" },
      slug: { type: "text" },
      short_desc: { type: "text" },
      price_hint: { type: "text" },
      icon: { type: "text" },
    },
    declarations: {
      statut: { type: "select", options: ["a_faire", "en_cours", "depose", "retard"] },
      type_declaration: { type: "select", options: ["mensuelle", "acompte", "annuelle", "autre"] },
      date_echeance_legale: { type: "date" },
      numero_quittance_ou_tej: { type: "text" },
      montant_a_payer: { type: "number", step: "0.001" },
      notes_collaborateur: { type: "text" },
    },
    collaborateurs: {
      nom: { type: "text" },
      prenom: { type: "text" },
      email: { type: "text" },
      telephone: { type: "text" },
      fonction: { type: "text" },
      notes: { type: "text" },
    },
    prefactures: {
      statut: { type: "select", options: ["emise", "payee", "annulee"] },
      taux_tva: { type: "number", step: "0.01" },
    },
    payments: {
      amount: { type: "number", step: "0.01" },
      date: { type: "date" },
      status: { type: "select", options: ["en_attente", "partiel", "paye", "retard", "annule"] },
    },
  };

  const EXPLORER_EDIT_FIELDS = {
    dossier_tasks: ["titre", "description", "statut", "date_echeance", "repetition"],
    service_followups: ["status", "start_date", "due_date", "notes"],
    declarations: ["type_declaration", "periode", "date_echeance_legale", "statut", "numero_quittance_ou_tej", "montant_a_payer", "notes_collaborateur"],
    prefactures: ["statut", "taux_tva"],
    payments: ["status", "amount", "date"],
  };

  const ROW_ACTIONS = {
    types_service: (item) => `
      <button class="btn btn-sm" onclick="BalanceAdmin.addSubService(${item.id}, '${escapeHtml(String(item.title)).replace(/'/g, "\\'")}')">＋ sous-service</button>
      <button class="btn btn-sm btn-danger" onclick="BalanceAdmin.deleteService(${item.id}, '${escapeHtml(String(item.title)).replace(/'/g, "\\'")}')">Supprimer</button>`,
    collaborateurs: (item) => `
      <button class="btn btn-sm btn-danger" onclick="BalanceAdmin.deleteCollaborateur(${item.id}, '${escapeHtml(String(item.display_name)).replace(/'/g, "\\'")}')">Supprimer</button>`,
  };

  let liveOn = false;
  let liveTimer = null;
  let currentDetail = null;
  let collabCache = [];

  async function ensureCollabs() {
    if (collabCache.length) return;
    try {
      const data = await api("/api/admin/collaborateurs");
      collabCache = data.items || [];
    } catch (e) {}
  }

  function stopLive() {
    liveOn = false;
    if (liveTimer) {
      clearInterval(liveTimer);
      liveTimer = null;
    }
  }

  function setLive(on) {
    liveOn = on;
    const btn = document.getElementById("live-btn");
    if (btn) {
      btn.textContent = on ? "Temps réel : ON" : "Temps réel : OFF";
      btn.classList.toggle("btn-outline", !on);
    }
    if (on) {
      if (!liveTimer) liveTimer = setInterval(refreshLive, 15000);
    } else if (liveTimer) {
      clearInterval(liveTimer);
      liveTimer = null;
    }
  }

  async function refreshLive() {
    const ae = document.activeElement;
    if (ae && ["INPUT", "SELECT", "TEXTAREA"].includes(ae.tagName)) return;
    if (document.getElementById("admin-detail-overlay").style.display === "flex") return;
    try {
      if (currentTab === "dashboard") await loadDashboard();
      else await applyFilters();
    } catch (e) {}
  }

  async function loadTab(tab) {
    const wrap = document.getElementById("tab-content");
    if (tab === "dashboard") {
      loadDashboard();
      return;
    }
    if (tab === "explorer") {
      loadExplorer();
      return;
    }
    const detail = DETAIL_TABLES.includes(tab);
    const liveBtn = `<button id="live-btn" class="btn btn-sm" onclick="BalanceAdmin.toggleLive()">Temps réel : OFF</button>`;
    let toolbar = "";
    if (tab === "dossier_tasks") {
      toolbar = `<div class="tab-toolbar">
        <select id="tm-client" onchange="BalanceAdmin.applyFilters()"><option value="">Tous les clients</option></select>
        <select id="tm-statut" onchange="BalanceAdmin.applyFilters()"><option value="">Tous les statuts</option></select>
        <select id="tm-followup" onchange="BalanceAdmin.applyFilters()"><option value="">Tous les suivis de service</option></select>
        ${liveBtn}
      </div>`;
    } else if (tab === "client_messages") {
      toolbar = `<div class="tab-toolbar">
        <select id="msg-client" onchange="BalanceAdmin.applyFilters()"><option value="">Tous les clients</option></select>
        <select id="msg-dossier" onchange="BalanceAdmin.applyFilters()"><option value="">Tous les dossiers</option></select>
        <select id="msg-service" onchange="BalanceAdmin.applyFilters()"><option value="">Tous les services</option></select>
        <select id="msg-task" onchange="BalanceAdmin.applyFilters()"><option value="">Toutes les tâches</option></select>
        <input id="id-search" placeholder="Filtrer par N° (ID)…" oninput="BalanceAdmin.applyFilters()" />
        ${liveBtn}
      </div>`;
    } else if (tab === "service_followups") {
      toolbar = `<div class="tab-toolbar">
        <select id="fu-collab" onchange="BalanceAdmin.applyFilters()"><option value="">Tous les collaborateurs</option></select>
        <input id="id-search" placeholder="Filtrer par N° (ID)…" oninput="BalanceAdmin.applyFilters()" />
        ${liveBtn}
      </div>`;
    } else if (detail) {
      toolbar = `<div class="tab-toolbar"><input id="id-search" placeholder="Filtrer par N° (ID)…" oninput="BalanceAdmin.applyFilters()" /><small>Recherche par identifiant du dossier / service / tâche</small>${liveBtn}</div>`;
    } else {
      toolbar = `<div class="tab-toolbar">${liveBtn}</div>`;
    }
    wrap.innerHTML = `<div id="tab-toolbar">${toolbar}</div><div id="tab-table"><p>Chargement…</p></div>`;
    try {
      if (tab === "dossier_tasks") await populateTaskFilters();
      if (tab === "client_messages") await populateMessageFilters();
      if (tab === "service_followups") {
        await ensureCollabs();
        const fuSel = document.getElementById("fu-collab");
        if (fuSel) fuSel.innerHTML = `<option value="">Tous les collaborateurs</option>${collabCache.map((x) => `<option value="${x.id}">${escapeHtml(x.display_name)}</option>`).join("")}`;
      }
      const data = await api(`/api/admin/${tab}`);
      renderTable(tab, data.items || []);
      setLive(true);
    } catch (e) {
      document.getElementById("tab-table").innerHTML = `<div class="alert show alert-error">${e.message}</div>`;
      setLive(false);
    }
  }

  async function populateTaskFilters() {
    const cSel = document.getElementById("tm-client");
    const fSel = document.getElementById("tm-followup");
    const stSel = document.getElementById("tm-statut");
    stSel.innerHTML = `<option value="">Tous les statuts</option>${["a_faire", "en_cours", "termine"].map((s) => `<option value="${s}">${s.replace("_", " ")}</option>`).join("")}`;
    try {
      const clients = await api("/api/admin/clients");
      cSel.innerHTML = `<option value="">Tous les clients</option>${(clients.items || []).map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("")}`;
    } catch (e) {}
    try {
      const fups = await api("/api/admin/service_followups");
      fSel.innerHTML = `<option value="">Tous les suivis de service</option>${(fups.items || []).map((s) => `<option value="${s.id}">${escapeHtml(s.client_name + " — " + s.service_title + " (N°" + s.id + ")")}</option>`).join("")}`;
    } catch (e) {}
  }

  async function populateMessageFilters() {
    const cSel = document.getElementById("msg-client");
    const dSel = document.getElementById("msg-dossier");
    const sSel = document.getElementById("msg-service");
    const tSel = document.getElementById("msg-task");
    if (!cSel) return;
    try {
      const clients = await api("/api/admin/clients");
      cSel.innerHTML = `<option value="">Tous les clients</option>${(clients.items || []).map((c) => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("")}`;
    } catch (e) {}
    try {
      const dossiers = await api("/api/admin/client_service_suivis");
      dSel.innerHTML = `<option value="">Tous les dossiers</option>${(dossiers.items || []).map((d) => `<option value="${d.id}">${escapeHtml(d.client_name + " — " + d.service_title + " (N°" + d.id + ")")}</option>`).join("")}`;
    } catch (e) {}
    try {
      const services = await api("/api/admin/types_service");
      sSel.innerHTML = `<option value="">Tous les services</option>${(services.items || []).map((s) => `<option value="${s.id}">${escapeHtml(s.title)}</option>`).join("")}`;
    } catch (e) {}
    try {
      const tasks = await api("/api/admin/dossier_tasks");
      tSel.innerHTML = `<option value="">Toutes les tâches</option>${(tasks.items || []).map((t) => `<option value="${t.id}">${escapeHtml(t.client_name + " — " + t.titre + " (N°" + t.id + ")")}</option>`).join("")}`;
    } catch (e) {}
  }

  async function applyFilters() {
    const wrap = document.getElementById("tab-table");
    if (!wrap) return;
    if (currentTab === "dashboard" || currentTab === "explorer") return;
    try {
      const qs = [];
      const c = document.getElementById("tm-client");
      const st = document.getElementById("tm-statut");
      const f = document.getElementById("tm-followup");
      const msgC = document.getElementById("msg-client");
      const msgD = document.getElementById("msg-dossier");
      const msgS = document.getElementById("msg-service");
      const msgT = document.getElementById("msg-task");
      const fuC = document.getElementById("fu-collab");
      const id = document.getElementById("id-search");
      if (c && c.value) qs.push("client=" + encodeURIComponent(c.value));
      if (st && st.value) qs.push("statut=" + encodeURIComponent(st.value));
      if (f && f.value) qs.push("followup=" + encodeURIComponent(f.value));
      if (msgC && msgC.value) qs.push("client=" + encodeURIComponent(msgC.value));
      if (msgD && msgD.value) qs.push("dossier=" + encodeURIComponent(msgD.value));
      if (msgS && msgS.value) qs.push("service=" + encodeURIComponent(msgS.value));
      if (msgT && msgT.value) qs.push("task=" + encodeURIComponent(msgT.value));
      if (fuC && fuC.value) qs.push("collaborateur=" + encodeURIComponent(fuC.value));
      if (id && id.value.trim()) qs.push("q=" + encodeURIComponent(id.value.trim()));
      const data = await api(`/api/admin/${currentTab}${qs.length ? "?" + qs.join("&") : ""}`);
      renderTable(currentTab, data.items || []);
    } catch (e) {
      wrap.innerHTML = `<div class="alert show alert-error">${e.message}</div>`;
    }
  }

  function toggleLive() {
    setLive(!liveOn);
  }

  function renderTable(tab, items) {
    const wrap = document.getElementById("tab-table");
    if (!items.length) {
      wrap.innerHTML = '<p style="color:#64748b">Aucun élément pour le moment.</p>';
      return;
    }
    const detail = DETAIL_TABLES.includes(tab);
    const cols = COLUMNS[tab];
    const head = cols.map((c) => `<th>${c.label}</th>`).join("");
    const body = items
      .map((item) => {
        const cells = cols
          .map((c) => {
            const value = item[c.key];
            if (tab === "service_followups" && c.key === "collaborateur_name") {
              const opts = ['<option value="">— Aucun —</option>']
                .concat(collabCache.map((x) => `<option value="${x.id}" ${Number(item.collaborateur_id) === Number(x.id) ? "selected" : ""}>${escapeHtml(x.display_name)}</option>`))
                .join("");
              return `<td><select class="status-select" data-table="${tab}" data-field="collaborateur" data-id="${item.id}" onchange="BalanceAdmin.saveField(this)">${opts}</select></td>`;
            }
            if (tab === "collaborateurs" && c.key === "actif") {
              return `<td><select class="status-select" data-table="${tab}" data-field="actif" data-id="${item.id}" onchange="BalanceAdmin.saveField(this)">
                <option value="true" ${value ? "selected" : ""}>Actif</option>
                <option value="false" ${!value ? "selected" : ""}>Inactif</option>
              </select></td>`;
            }
            if (c.key === "status" || c.key === "statut_paiement" || c.key === "statut_service" || c.key === "frequence" || c.key === "repetition" || c.key === "type_declaration" || (c.key === "statut" && tab !== "dossier_attachments")) {
              const opts = Array.isArray(STATUS_OPTIONS[tab])
                ? STATUS_OPTIONS[tab]
                : (STATUS_OPTIONS[tab] || {})[c.key] || [];
              if (!opts.length) return `<td>${value == null || value === "" ? "—" : escapeHtml(String(value))}</td>`;
              return `<td><select class="status-select" data-table="${tab}" data-field="${c.key}" data-id="${item.id}" onchange="BalanceAdmin.saveField(this)">
                ${opts.map((s) => `<option value="${s}" ${value === s ? "selected" : ""}>${s.replace("_", " ")}</option>`).join("")}
              </select></td>`;
            }
            if (c.key === "original_name" && item.url) {
              return `<td><a href="${item.url}" target="_blank" rel="noopener">${escapeHtml(String(value))}</a></td>`;
            }
            const editCfg = (EDIT_FIELDS[tab] || {})[c.key];
            if (editCfg && editCfg.type !== "select") {
              const raw = value == null || value === "" ? "" : String(value);
              return `<td><input class="inline-edit" type="${editCfg.type}" ${editCfg.step ? `step="${editCfg.step}"` : ""} data-table="${tab}" data-field="${c.key}" data-id="${item.id}" value="${escapeHtml(raw)}" onchange="BalanceAdmin.saveField(this)" /></td>`;
            }
            return `<td>${value == null || value === "" ? "—" : escapeHtml(String(value))}</td>`;
          })
          .join("");
        const actions = [];
        if (ROW_ACTIONS[tab]) actions.push(ROW_ACTIONS[tab](item));
        if (detail) actions.push(`<button class="btn btn-sm" onclick="BalanceAdmin.showDetail('${tab}', ${item.id})">Détail</button>`);
        return `<tr>${cells}${actions.length ? `<td>${actions.join(" ")}</td>` : "<td></td>"}</tr>`;
      })
      .join("");
    wrap.innerHTML = `<table class="admin-table"><thead><tr>${head}<th></th></tr></thead><tbody>${body}</tbody></table>`;
  }

  function statusBadge(statut) {
    const cls = { "Clôturé": "confirme", "Payé": "confirme", "Validé / déposé / conforme": "confirme", "Déposé (Validé)": "confirme", "Terminé": "confirme", "En retard": "annule", "En retard / impayé": "annule", "Annulé": "annule", "Annulée": "annule" };
    return `<span class="badge ${cls[statut] || "nouveau"}">${statut}</span>`;
  }

  async function showDetail(tab, id) {
    currentDetail = { tab, id };
    try {
      const [data, listData] = await Promise.all([
        api(`/api/admin/detail/${tab}/${id}`),
        api(`/api/admin/${tab}?q=${id}`),
      ]);
      const it = data.item;
      const raw = (listData.items || []).find((r) => String(r.id) === String(id)) || {};
      document.getElementById("admin-detail-overlay").style.display = "flex";
      const wrap = document.getElementById("admin-detail-body");
      let html = "";
      if (it.type === "dossier") {
        html = `
          <h3>Dossier N°${it.id} — ${escapeHtml(it.service)}</h3>
          <p class="muted-sm">Client : <strong>${escapeHtml(it.client_name)}</strong> · ${escapeHtml(it.client_contact)}</p>
          <table class="admin-table">
            ${editRow(tab, "montant", id, raw.montant, "Prix (TND)")}
            ${editRow(tab, "frequence", id, raw.frequence, "Fréquence")}
            ${editRow(tab, "date_echeance", id, raw.date_echeance, "Échéance")}
            ${editRow(tab, "statut_service", id, raw.statut_service, "Statut dossier")}
            ${editRow(tab, "statut_paiement", id, raw.statut_paiement, "Statut paiement")}
            ${editRow(tab, "commentaire", id, raw.commentaire, "Note du dossier")}
            ${editRow(tab, "service_note", id, raw.service_note, "Note du service")}
          </table>
          <h4>Tâches du dossier</h4>
          ${it.tasks.length ? `<ul class="task-list">${it.tasks.map((t) => `<li>${statusBadge(t.statut)} ${escapeHtml(t.titre)} — <small>${t.date_echeance} · ${t.repetition}</small></li>`).join("")}</ul>` : '<p class="muted-sm">Aucune tâche.</p>'}
          <h4>Suivi du service (dans le dossier)</h4>
          ${it.service_followups.length ? `<ul class="task-list">${it.service_followups.map((s) => `<li>${statusBadge(s.status)} ${escapeHtml(s.service)} — <small>début ${s.start_date} · fin ${s.due_date}</small>${s.tasks.length ? `<br><small>↳ Tâches : ${s.tasks.map((t) => escapeHtml(t.titre)).join(", ")}</small>` : ""}</li>`).join("")}</ul>` : '<p class="muted-sm">Aucun suivi de service lié.</p>'}
          <h4>Préfactures</h4>
          ${it.prefactures.length ? `<ul class="task-list">${it.prefactures.map((p) => `<li>${escapeHtml(p.numero)} — ${p.montant_ttc} TND — ${statusBadge(p.statut)}</li>`).join("")}</ul>` : '<p class="muted-sm">Aucune préfacture.</p>'}`;
      } else if (it.type === "service" && tab === "service_followups") {
        html = `
          <h3>Suivi service N°${it.id} — ${escapeHtml(it.service)}</h3>
          <p class="muted-sm">Client : <strong>${escapeHtml(it.client_name)}</strong></p>
          <table class="admin-table">
            ${editRow(tab, "status", id, raw.status, "Statut")}
            ${editRow(tab, "start_date", id, raw.start_date, "Date de début")}
            ${editRow(tab, "due_date", id, raw.due_date, "Échéance")}
            ${editRow(tab, "notes", id, raw.notes, "Notes")}
          </table>
          ${it.dossier ? `
            <h4>Dossier associé (service inclus dans le dossier)</h4>
            <table class="admin-table">
              <tr><td>Dossier</td><td>N°${it.dossier.id} — ${escapeHtml(it.dossier.service)}</td></tr>
              <tr><td>Prix (TND)</td><td>${it.dossier.montant}</td></tr>
              <tr><td>Fréquence</td><td>${it.dossier.frequence}</td></tr>
              <tr><td>Échéance</td><td>${it.dossier.date_echeance}</td></tr>
              <tr><td>Statut dossier</td><td>${statusBadge(it.dossier.statut_service)}</td></tr>
              <tr><td>Statut paiement</td><td>${statusBadge(it.dossier.statut_paiement)}</td></tr>
            </table>
            <h4>Tâches du service (issues du dossier)</h4>
            ${it.dossier.tasks.length ? `<ul class="task-list">${it.dossier.tasks.map((t) => `<li>${statusBadge(t.statut)} ${escapeHtml(t.titre)} — <small>${t.date_echeance} · ${t.repetition}</small></li>`).join("")}</ul>` : '<p class="muted-sm">Aucune tâche.</p>'}`
          : '<p class="muted-sm">Aucun dossier associé à ce suivi de service.</p>'}`;
      } else if (it.type === "task") {
        html = `
          <h3>Tâche N°${it.id} — ${escapeHtml(it.titre)}</h3>
          <table class="admin-table">
            ${editRow(tab, "titre", id, raw.titre, "Tâche")}
            ${editRow(tab, "statut", id, raw.statut, "Statut")}
            ${editRow(tab, "date_echeance", id, raw.date_echeance, "Échéance")}
            ${editRow(tab, "repetition", id, raw.repetition, "Répétition")}
            <tr><td>Description</td><td>${escapeHtml(it.description || "—")}</td></tr>
          </table>
          ${it.followup ? `
          <h4>Suivi de service lié</h4>
          <table class="admin-table">
            <tr><td>Suivi</td><td>${escapeHtml(it.followup.service)} (N°${it.followup.id})</td></tr>
            <tr><td>Statut</td><td>${statusBadge(it.followup.status)}</td></tr>
          </table>` : ""}
          <h4>Dossier (tâche incluse dans le dossier)</h4>
          <table class="admin-table">
            <tr><td>Dossier</td><td>N°${it.dossier.id} — ${escapeHtml(it.dossier.service)}</td></tr>
            <tr><td>Client</td><td>${escapeHtml(it.dossier.client_name)}</td></tr>
            <tr><td>Statut dossier</td><td>${statusBadge(it.dossier.statut_service)}</td></tr>
            <tr><td>Statut paiement</td><td>${statusBadge(it.dossier.statut_paiement)}</td></tr>
            <tr><td>Prix (TND)</td><td>${it.dossier.montant}</td></tr>
          </table>`;
      } else if (it.type === "service") {
        html = `
          <h3>Service — ${escapeHtml(it.title)}</h3>
          <p class="muted-sm">Identifiant : ${escapeHtml(it.slug)}${it.parent_id ? ` · Parent : ${escapeHtml(it.parent_title)}` : " · Service principal"}</p>
          <table class="admin-table">
            ${editRow(tab, "title", id, raw.title, "Titre")}
            ${editRow(tab, "slug", id, raw.slug, "Identifiant (slug)")}
            ${editRow(tab, "short_desc", id, raw.short_desc, "Résumé")}
            ${editRow(tab, "price_hint", id, raw.price_hint, "Indication tarifaire")}
            ${editRow(tab, "icon", id, raw.icon, "Icône")}
            <tr><td>Service parent</td><td><select id="detail-parent" class="inline-edit" data-table="${tab}" data-field="parent" data-id="${id}" onchange="BalanceAdmin.saveField(this)"><option value="">Chargement…</option></select></td></tr>
            <tr><td>Description</td><td>${escapeHtml(it.description || "—")}</td></tr>
          </table>
          <h4>Sous-services</h4>
          ${it.subservices.length ? `<ul class="task-list">${it.subservices.map((s) => `<li>${escapeHtml(s.title)} — <small>${escapeHtml(s.slug)}</small></li>`).join("")}</ul>` : '<p class="muted-sm">Aucun sous-service. Utilisez « ＋ sous-service » dans la liste.</p>'}`;
      } else if (it.type === "message") {
        const msgs = (it.thread || []).map(
          (m) => `<div class="msg ${m.direction === "admin" ? "msg-admin" : "msg-client"}">
            <strong>${m.direction === "admin" ? "Cabinet" : it.client_name}</strong> — <small>${m.created_at}</small>
            ${m.context_label && m.context_label !== "Général" ? `<br><small class="msg-context">↳ ${escapeHtml(m.context_label)}</small>` : ""}
            <p>${escapeHtml(m.text)}</p>
          </div>`,
        ).join("");
        html = `
          <h3>Messagerie — ${escapeHtml(it.client_name)}</h3>
          <p class="muted-sm">Contexte : <span class="msg-context">${escapeHtml(it.context_label)}</span></p>
          <table class="admin-table" style="max-width:560px">
            <tr><td>Dossier</td><td>${it.dossier_id ? "N°" + it.dossier_id + " — " + escapeHtml(it.dossier_service) : "—"}</td></tr>
            <tr><td>Service</td><td>${it.service_id ? "N°" + it.service_id + " — " + escapeHtml(it.service_title) : "—"}</td></tr>
            <tr><td>Tâche</td><td>${it.task_id ? "N°" + it.task_id + " — " + escapeHtml(it.task_title) : "—"}</td></tr>
          </table>
          <div class="thread-box">${msgs || '<p class="muted-sm">Aucun message.</p>'}</div>
          <div class="form-group" style="margin-top:12px">
            <label for="reply-text">Réponse du cabinet</label>
            <textarea id="reply-text" rows="2" placeholder="Votre réponse…"></textarea>
          </div>
          <button class="btn" onclick="BalanceAdmin.replyMessage(${it.client_id}, ${it.dossier_id || "null"}, ${it.service_id || "null"}, ${it.task_id || "null"})">Envoyer la réponse</button>`;
      }
      wrap.innerHTML = html;
      if (it.type === "service") populateParentSelect(id, it.parent_id);
    } catch (e) {
      alert(e.message);
    }
  }

  function closeDetail() {
    document.getElementById("admin-detail-overlay").style.display = "none";
  }

  async function saveField(el) {
    try {
      await api(`/api/admin/${el.dataset.table}`, {
        method: "PUT",
        body: JSON.stringify({
          id: Number(el.dataset.id),
          field: el.dataset.field || "status",
          status: el.value,
        }),
      });
      el.classList.add("saved");
      setTimeout(() => el.classList.remove("saved"), 1200);
    } catch (e) {
      alert(e.message);
      loadTab(currentTab);
    }
  }

  const updateStatus = saveField;

  function editControl(tab, field, id, rawValue) {
    const cfg = (EDIT_FIELDS[tab] || {})[field];
    if (!cfg) return null;
    const val = rawValue == null ? "" : String(rawValue);
    const attrs = `data-table="${tab}" data-field="${field}" data-id="${id}"`;
    if (cfg.type === "select") {
      return `<select class="inline-edit" ${attrs} onchange="BalanceAdmin.saveField(this)">${cfg.options
        .map((o) => `<option value="${o}" ${val === o ? "selected" : ""}>${o.replace(/_/g, " ")}</option>`)
        .join("")}</select>`;
    }
    if (cfg.type === "date") {
      return `<input class="inline-edit" type="date" ${attrs} value="${val}" onchange="BalanceAdmin.saveField(this)" />`;
    }
    return `<input class="inline-edit" type="${cfg.type}" ${cfg.step ? `step="${cfg.step}"` : ""} ${attrs} value="${escapeHtml(val)}" onchange="BalanceAdmin.saveField(this)" />`;
  }

  function editRow(tab, field, id, rawValue, label) {
    const control = editControl(tab, field, id, rawValue);
    return control
      ? `<tr><td>${label}</td><td>${control}</td></tr>`
      : `<tr><td>${label}</td><td>${rawValue == null || rawValue === "" ? "—" : escapeHtml(String(rawValue))}</td></tr>`;
  }

  function escapeHtml(str) {
    return str.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function fieldHtml(f) {
    const id = "cf-" + f.name;
    if (f.type === "select" && f.options) {
      const opts = f.options.map((o) => `<option value="${o}">${o.replace("_", " ")}</option>`).join("");
      return `<select id="${id}" ${f.label.includes("*") ? "required" : ""}><option value="">— Choisir —</option>${opts}</select>`;
    }
    if (f.type === "select") {
      return `<select id="${id}" ${f.label.includes("*") ? "required" : ""}><option value="">Chargement…</option></select>`;
    }
    if (f.type === "textarea") {
      return `<textarea id="${id}" rows="2"></textarea>`;
    }
    if (f.type === "file") {
      return `<input id="${id}" type="file" required />`;
    }
    return `<input id="${id}" type="${f.type}" ${f.step ? `step="${f.step}"` : ""} ${f.label.includes("*") ? "required" : ""} />`;
  }

  async function buildCreateForm() {
    const cfgRaw = CREATE_FORMS[currentTab];
    const cfg = Array.isArray(cfgRaw) ? cfgRaw : cfgRaw.fields;
    const box = document.getElementById("create-box");
    const fields = cfg
      .map((f) => `<div class="form-group"><label for="cf-${f.name}">${f.label}</label>${fieldHtml(f)}</div>`)
      .join("");
    box.innerHTML = `<div class="card">
      <h3 style="margin:0 0 14px">Ajouter — ${currentTab.replace(/_/g, " ")}</h3>
      <form id="create-form" class="form-grid" style="margin:0">
        ${fields}
        <div class="form-group full" style="display:flex;gap:8px">
          <button class="btn" type="submit">Enregistrer</button>
          <button class="btn btn-outline" type="button" onclick="BalanceAdmin.toggleCreate()">Annuler</button>
        </div>
      </form>
    </div>`;

    for (const f of cfg) {
      if (f.type === "select" && f.source) {
        const el = document.getElementById("cf-" + f.name);
        try {
          const data = await api(f.source);
          const opts = (data.items || [])
            .map((it) => `<option value="${it[f.valueKey]}">${f.textKey(it)}</option>`)
            .join("");
          el.innerHTML = `<option value="">— Choisir —</option>${opts}`;
        } catch (e) {
          el.innerHTML = `<option value="">— Erreur de chargement —</option>`;
        }
      }
    }
    document.getElementById("create-form").addEventListener("submit", submitCreate);
  }

  async function submitCreate(e) {
    e.preventDefault();
    const cfgRaw = CREATE_FORMS[currentTab];
    const cfg = Array.isArray(cfgRaw) ? cfgRaw : cfgRaw.fields;
    const hasFile = cfg.some((f) => f.type === "file");
    const fd = new FormData();
    const payload = {};
    for (const f of cfg) {
      const el = document.getElementById("cf-" + f.name);
      if (f.type === "file") {
        if (!el.files.length) {
          alert(`Champ requis : ${f.label}`);
          return;
        }
        fd.append(f.name, el.files[0]);
      } else {
        payload[f.name] = el.value.trim();
        if (f.label.includes("*") && !payload[f.name]) {
          alert(`Champ requis : ${f.label}`);
          return;
        }
        if (hasFile) fd.append(f.name, payload[f.name]);
      }
    }
    try {
      if (hasFile) {
        const res = await fetch(API_BASE + `/api/admin/${currentTab}`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token()}` },
          body: fd,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Erreur");
      } else {
        await api(`/api/admin/${currentTab}`, { method: "POST", body: JSON.stringify(payload) });
      }
      document.getElementById("create-box").style.display = "none";
      document.getElementById("create-box").innerHTML = "";
      loadTab(currentTab);
    } catch (err) {
      alert(err.message);
    }
  }

  function toggleCreate() {
    const box = document.getElementById("create-box");
    const shown = box.style.display !== "none";
    box.style.display = shown ? "none" : "";
    if (!shown) buildCreateForm();
  }

  async function addSubService(parentId, parentLabel) {
    if (currentTab !== "types_service") switchTab("types_service");
    document.getElementById("create-btn").style.display = "none";
    const box = document.getElementById("create-box");
    box.style.display = "";
    await buildCreateForm();
    const parentSel = document.getElementById("cf-parent");
    if (parentSel) parentSel.value = String(parentId);
    const h = box.querySelector("h3");
    if (h) h.textContent = `Ajouter un sous-service à « ${parentLabel} »`;
    const titleEl = document.getElementById("cf-title");
    if (titleEl) titleEl.focus();
  }

  async function deleteService(id, title) {
    if (!confirm(`Supprimer le service « ${title} » ?`)) return;
    try {
      const data = await api(`/api/admin/types_service`, { method: "DELETE", body: JSON.stringify({ id }) });
      alert(data.message || "Service supprimé.");
      applyFilters();
    } catch (e) {
      alert(e.message);
    }
  }

  async function populateParentSelect(serviceId, currentParentId) {
    const sel = document.getElementById("detail-parent");
    if (!sel) return;
    try {
      const data = await api("/api/admin/types_service");
      const opts = ['<option value="">— Aucun (service principal) —</option>'];
      for (const s of data.items || []) {
        if (Number(s.id) === Number(serviceId)) continue;
        const label = s.parent_title !== "—" ? s.parent_title + " › " + s.title : s.title + " (service principal)";
        opts.push(`<option value="${s.id}" ${Number(s.id) === Number(currentParentId) ? "selected" : ""}>${escapeHtml(label)}</option>`);
      }
      sel.innerHTML = opts.join("");
    } catch (e) {}
  }

  async function replyMessage(clientId, dossierId, serviceId, taskId) {
    const textEl = document.getElementById("reply-text");
    const text = (textEl.value || "").trim();
    if (!text) {
      alert("Écrivez une réponse.");
      return;
    }
    const payload = { client: clientId, text };
    if (dossierId) payload.dossier = String(dossierId);
    if (serviceId) payload.service = String(serviceId);
    if (taskId) payload.task = String(taskId);
    try {
      await api(`/api/admin/client_messages`, { method: "POST", body: JSON.stringify(payload) });
      textEl.value = "";
      alert("Réponse envoyée.");
      if (currentDetail) showDetail(currentDetail.tab, currentDetail.id);
    } catch (e) {
      alert(e.message);
    }
  }

  let explorerClientId = null;

  async function loadExplorer() {
    const wrap = document.getElementById("tab-content");
    wrap.innerHTML = `<div id="tab-toolbar"><button class="btn btn-sm" onclick="BalanceAdmin.loadExplorer()">⟳ Recharger</button><small class="muted-sm" style="margin-left:10px">Explorateur : client → dossiers → détail complet (tâches, suivis, préfactures, pièces jointes, messages, déclarations, paiements).</small></div><div id="tab-table"><p>Chargement…</p></div>`;
    explorerClientId = null;
    try {
      const data = await api("/api/admin/explorer");
      renderExplorerClients(data.clients || []);
    } catch (e) {
      document.getElementById("tab-table").innerHTML = `<div class="alert show alert-error">${e.message}</div>`;
    }
  }

  function renderExplorerClients(clients) {
    const wrap = document.getElementById("tab-table");
    if (!clients.length) {
      wrap.innerHTML = '<p style="color:#64748b">Aucun client pour le moment.</p>';
      return;
    }
    wrap.innerHTML = `<table class="admin-table"><thead><tr><th>Client</th><th>Contact</th><th>Dossiers</th><th></th></tr></thead><tbody>
      ${clients.map((c) => `<tr>
        <td><strong>${escapeHtml(c.name)}</strong></td>
        <td>${escapeHtml(c.email)}${c.phone ? " · " + escapeHtml(c.phone) : ""}</td>
        <td><span class="badge ${c.dossier_count ? "nouveau" : "confirme"}">${c.dossier_count}</span></td>
        <td><button class="btn btn-sm" onclick="BalanceAdmin.explorerDossiers(${c.id})">Explorer ses dossiers</button></td>
      </tr>`).join("")}
    </tbody></table>`;
  }

  async function explorerDossiers(clientId) {
    explorerClientId = clientId;
    const wrap = document.getElementById("tab-table");
    wrap.innerHTML = '<p>Chargement…</p>';
    try {
      const data = await api(`/api/admin/explorer/${clientId}`);
      const c = data.client;
      const dossiers = data.dossiers || [];
      document.getElementById("tab-toolbar").innerHTML = `<button class="btn btn-sm" onclick="BalanceAdmin.loadExplorer()">← Liste des clients</button> <strong>${escapeHtml(c.name)}</strong> <small class="muted-sm">${c.email}</small>`;
      const rows = dossiers.map((d) => `<tr>
        <td><strong>N°${d.id}</strong></td>
        <td>${escapeHtml(d.service)}</td>
        <td>${d.montant} TND · ${d.frequence}</td>
        <td><span class="badge ${d.statut_service === "Clôturé" ? "confirme" : "nouveau"}">${d.statut_service}</span></td>
        <td><span class="badge ${d.statut_paiement === "Payé" ? "confirme" : "nouveau"}">${d.statut_paiement}</span></td>
        <td>${d.date_echeance}</td>
        <td>${d.task_count} tâches · ${d.followup_count} suivis · ${d.prefacture_count} préfactures · ${d.attachment_count} pièces · ${d.message_count} messages · ${d.declaration_count} déclarations · ${d.payment_count} paiements</td>
        <td><button class="btn btn-sm" onclick="BalanceAdmin.explorerDossier(${d.id})">Ouvrir</button></td>
      </tr>`).join("");
      wrap.innerHTML = `<table class="admin-table"><thead><tr><th>N°</th><th>Service</th><th>Prix / Fréquence</th><th>Dossier</th><th>Paiement</th><th>Échéance</th><th>Éléments liés</th><th></th></tr></thead><tbody>
        ${rows || '<tr><td colspan="8"><p style="color:#64748b">Aucun dossier pour ce client.</p></td></tr>'}
      </tbody></table>`;
    } catch (e) {
      wrap.innerHTML = `<div class="alert show alert-error">${e.message}</div>`;
    }
  }

  async function explorerDossier(dossierId) {
    const wrap = document.getElementById("tab-table");
    wrap.innerHTML = '<p>Chargement…</p>';
    try {
      const data = await api(`/api/admin/detail/client_service_suivis/${dossierId}`);
      const it = data.item;
      const addBtn = (table, label) => `<button class="btn btn-sm" onclick="BalanceAdmin.explorerAdd('${table}', ${it.id}, ${it.client_id})">＋ ${label}</button>`;
      const tasks = it.tasks.length ? `<ul class="task-list">${it.tasks.map((t) => `<li>${statusBadge(t.statut)} ${escapeHtml(t.titre)} — <small>${t.date_echeance} · ${t.repetition}</small> <span class="explorer-actions">${explorerItemActions("dossier_tasks", t.id, t.titre, it.id)}</span></li>`).join("")}</ul>` : '<p class="muted-sm">Aucune tâche.</p>';
      const followups = it.service_followups.length ? `<ul class="task-list">${it.service_followups.map((s) => `<li>${statusBadge(s.status)} ${escapeHtml(s.service)} — <small>du ${s.start_date} au ${s.due_date}</small> <span class="explorer-actions">${explorerItemActions("service_followups", s.id, s.service, it.id)}</span></li>`).join("")}</ul>` : '<p class="muted-sm">Aucun suivi de service.</p>';
      const prefactures = it.prefactures.length ? `<ul class="task-list">${it.prefactures.map((p) => `<li>${escapeHtml(p.numero)} — ${p.montant_ttc} TND — ${statusBadge(p.statut)} <span class="explorer-actions">${explorerItemActions("prefactures", p.id, p.numero, it.id)}</span></li>`).join("")}</ul>` : '<p class="muted-sm">Aucune préfacture.</p>';
      const attachments = it.attachments.length ? `<ul class="task-list">${it.attachments.map((a) => `<li><a href="${a.url}" target="_blank" rel="noopener">${escapeHtml(a.name)}</a> <small>(${a.size} · ${a.category} · ${a.uploaded_by})</small> <span class="explorer-actions">${explorerItemActions("dossier_attachments", a.id, a.name, it.id, false)}</span></li>`).join("")}</ul>` : '<p class="muted-sm">Aucune pièce jointe.</p>';
      const messages = it.messages.length ? `<div class="thread-box">${it.messages.map((m) => `<div class="msg ${m.direction === "admin" ? "msg-admin" : "msg-client"}"><strong>${m.direction === "admin" ? "Cabinet" : escapeHtml(it.client_name)}</strong> — <small>${m.created_at}</small><p>${escapeHtml(m.text)}</p>${explorerItemActions("client_messages", m.id, "message", it.id, false)}</div>`).join("")}</div>` : '<p class="muted-sm">Aucun message.</p>';
      const declarations = it.declarations.length ? `<ul class="task-list">${it.declarations.map((df) => `<li>${statusBadge(df.statut)} ${escapeHtml(df.type_declaration)} — ${escapeHtml(df.periode)} · éch. ${df.date_echeance_legale}${df.montant_a_payer !== "0.000" ? " · " + df.montant_a_payer + " TND" : ""} <span class="explorer-actions">${explorerItemActions("declarations", df.id, df.periode, it.id)}</span></li>`).join("")}</ul>` : '<p class="muted-sm">Aucune déclaration liée.</p>';
      const payments = it.payments.length ? `<ul class="task-list">${it.payments.map((p) => `<li>${p.amount} TND — ${p.date} — ${statusBadge(p.status)} <span class="explorer-actions">${explorerItemActions("payments", p.id, "paiement", it.id)}</span></li>`).join("")}</ul>` : '<p class="muted-sm">Aucun paiement lié.</p>';
      document.getElementById("tab-toolbar").innerHTML = `<button class="btn btn-sm" onclick="BalanceAdmin.explorerDossiers(${it.client_id})">← Retour aux dossiers du client</button> <strong>Dossier N°${it.id}</strong>`;
      wrap.innerHTML = `
        <div class="dossier-card">
          <div class="dossier-head">
            <div>
              <strong>N°${it.id} — ${escapeHtml(it.service)}</strong>
              <div class="dossier-meta">Client : ${escapeHtml(it.client_name)} (${escapeHtml(it.client_contact)}) · ${it.montant} TND · ${it.frequence} · Échéance ${it.date_echeance}</div>
            </div>
            <div class="dossier-status">
              <span class="${it.statut_service === "Clôturé" ? "badge confirme" : "badge nouveau"}">${it.statut_service}</span>
              <span class="${it.statut_paiement === "Payé" ? "badge confirme" : "badge nouveau"}">${it.statut_paiement}</span>
            </div>
          </div>
          ${it.commentaire ? `<p class="muted-sm">${escapeHtml(it.commentaire)}</p>` : ""}
          ${it.service_note ? `<p class="muted-sm"><strong>Note du service :</strong> ${escapeHtml(it.service_note)}</p>` : ""}
          <div class="dossier-block"><strong>Tâches</strong> ${addBtn("dossier_tasks", "Ajouter")}<div id="explorer-add-dossier_tasks"></div>${tasks}</div>
          <div class="dossier-block"><strong>Suivi du service</strong> ${addBtn("service_followups", "Ajouter")}<div id="explorer-add-service_followups"></div>${followups}</div>
          <div class="dossier-block"><strong>Déclarations fiscales</strong> ${addBtn("declarations", "Ajouter")}<div id="explorer-add-declarations"></div>${declarations}</div>
          <div class="dossier-block"><strong>Préfactures</strong> ${addBtn("prefactures", "Ajouter")}<div id="explorer-add-prefactures"></div>${prefactures}</div>
          <div class="dossier-block"><strong>Paiements</strong> ${addBtn("payments", "Ajouter")}<div id="explorer-add-payments"></div>${payments}</div>
          <div class="dossier-block"><strong>Pièces jointes</strong> ${addBtn("dossier_attachments", "Ajouter")}<div id="explorer-add-dossier_attachments"></div>${attachments}</div>
          <div class="dossier-block"><strong>Messagerie</strong> ${addBtn("client_messages", "Répondre")}<div id="explorer-add-client_messages"></div>${messages}</div>
        </div>`;
    } catch (e) {
      wrap.innerHTML = `<div class="alert show alert-error">${e.message}</div>`;
    }
  }

  function explorerItemActions(table, id, label, dossierId, canEdit = true) {
    const lab = String(label).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
    const edit = canEdit ? `<button class="btn btn-sm btn-outline" onclick="BalanceAdmin.explorerEdit('${table}', ${id}, ${dossierId})">Modifier</button> ` : "";
    return `${edit}<button class="btn btn-sm btn-danger" onclick="BalanceAdmin.explorerDelete('${table}', ${id}, '${lab}', ${dossierId})">Supprimer</button>`;
  }

  async function explorerAdd(table, dossierId, clientId) {
    const slot = document.getElementById(`explorer-add-${table}`);
    if (!slot) return;
    const cfgRaw = CREATE_FORMS[table];
    const cfg = Array.isArray(cfgRaw) ? cfgRaw : cfgRaw.fields;
    const fields = cfg.filter((f) => f.name !== "client" && f.name !== "dossier").map((f) => `<div class="form-group"><label>${f.label}</label>${explorerAddControl(f)}</div>`).join("");
    slot.innerHTML = `<div class="card explorer-form">
      <h4 style="margin:0 0 10px">Ajouter — ${table.replace(/_/g, " ")}</h4>
      <form id="explorer-form" class="form-grid" style="margin:0">
        ${fields}
        <input type="hidden" name="dossier" value="${dossierId}" />
        <input type="hidden" name="client" value="${clientId}" />
        <div style="display:flex;gap:8px">
          <button class="btn" type="submit">Enregistrer</button>
          <button class="btn btn-outline" type="button" onclick="BalanceAdmin.explorerCancel('${table}')">Annuler</button>
        </div>
      </form>
    </div>`;
    await populateExplorerSelects(slot, cfg);
    slot.querySelector("#explorer-form").addEventListener("submit", (e) => { e.preventDefault(); submitExplorerForm(table, dossierId, "add"); });
  }

  async function explorerEdit(table, id, dossierId) {
    const slot = document.getElementById(`explorer-add-${table}`);
    if (!slot) return;
    try {
      const data = await api(`/api/admin/${table}?q=${id}`);
      const row = (data.items || []).find((r) => String(r.id) === String(id)) || {};
      const fields = EXPLORER_EDIT_FIELDS[table] || [];
      const controls = fields.map((f) => `<div class="form-group"><label>${f.replace(/_/g, " ")}</label>${explorerEditControl(table, f, row[f])}</div>`).join("");
      slot.innerHTML = `<div class="card explorer-form">
        <h4 style="margin:0 0 10px">Modifier — N°${id}</h4>
        <form id="explorer-form" class="form-grid" style="margin:0">
          ${controls}
          <div style="display:flex;gap:8px">
            <button class="btn" type="submit">Enregistrer</button>
            <button class="btn btn-outline" type="button" onclick="BalanceAdmin.explorerCancel('${table}')">Annuler</button>
          </div>
        </form>
      </div>`;
      slot.querySelector("#explorer-form").addEventListener("submit", (e) => { e.preventDefault(); submitExplorerForm(table, dossierId, "edit", id); });
    } catch (e) { alert(e.message); }
  }

  function explorerEditControl(table, field, val) {
    const cfg = (EDIT_FIELDS[table] || {})[field];
    const v = val == null || val === "" ? "" : String(val);
    const opts = Array.isArray(STATUS_OPTIONS[table]) ? STATUS_OPTIONS[table] : (STATUS_OPTIONS[table] || {})[field];
    const selOpts = (cfg && cfg.type === "select") ? cfg.options : opts;
    const name = `ef-${field}`;
    if (selOpts && selOpts.length) {
      return `<select name="${name}" class="inline-edit">${selOpts.map((o) => `<option value="${o}" ${String(v) === o ? "selected" : ""}>${o.replace(/_/g, " ")}</option>`).join("")}</select>`;
    }
    if (cfg && cfg.type === "date") return `<input name="${name}" type="date" class="inline-edit" value="${v}" />`;
    if (cfg && cfg.type === "number") return `<input name="${name}" type="number" ${cfg.step ? `step="${cfg.step}"` : ""} class="inline-edit" value="${v}" />`;
    if (["notes", "notes_collaborateur", "description", "commentaire", "periode", "service_note", "text"].includes(field)) {
      return `<textarea name="${name}" rows="2" class="inline-edit">${escapeHtml(v)}</textarea>`;
    }
    return `<input name="${name}" type="text" class="inline-edit" value="${escapeHtml(v)}" />`;
  }

  function explorerAddControl(f) {
    const name = f.name;
    if (f.type === "select" && f.options) {
      const opts = f.options.map((o) => `<option value="${o}" ${!f.label.includes("*") && o === f.options[0] ? "selected" : ""}>${o.replace(/_/g, " ")}</option>`).join("");
      return `<select name="${name}" ${f.label.includes("*") ? "required" : ""}>${f.label.includes("*") ? '<option value="">— Choisir —</option>' : ""}${opts}</select>`;
    }
    if (f.type === "select") return `<select name="${name}" ${f.label.includes("*") ? "required" : ""}><option value="">Chargement…</option></select>`;
    if (f.type === "textarea") return `<textarea name="${name}" rows="2"></textarea>`;
    if (f.type === "file") return `<input name="${name}" type="file" required />`;
    return `<input name="${name}" type="${f.type}" ${f.step ? `step="${f.step}"` : ""} ${f.label.includes("*") ? "required" : ""} />`;
  }

  async function populateExplorerSelects(slot, cfg) {
    for (const f of cfg) {
      if (f.type === "select" && f.source) {
        const sel = slot.querySelector(`[name="${f.name}"]`);
        if (!sel) continue;
        try {
          const data = await api(f.source);
          sel.innerHTML = f.label.includes("*") ? '<option value="">— Choisir —</option>' : "";
          sel.innerHTML += (data.items || []).map((it) => `<option value="${it[f.valueKey]}">${escapeHtml(String(f.textKey(it)))}</option>`).join("");
        } catch (e) {
          sel.innerHTML = '<option value="">Erreur</option>';
        }
      }
    }
  }

  async function explorerDelete(table, id, label, dossierId) {
    if (!confirm(`Supprimer ${label} (N°${id}) ?`)) return;
    try {
      await api(`/api/admin/${table}`, { method: "DELETE", body: JSON.stringify({ id }) });
      await explorerDossier(dossierId);
    } catch (e) { alert(e.message); }
  }

  function explorerCancel(table) {
    const slot = document.getElementById(`explorer-add-${table}`);
    if (slot) slot.innerHTML = "";
  }

  async function submitExplorerForm(table, dossierId, mode, id) {
    const form = document.getElementById("explorer-form");
    if (!form) return;
    const slot = form.closest(".explorer-form");
    const cfgRaw = CREATE_FORMS[table];
    const cfg = Array.isArray(cfgRaw) ? cfgRaw : cfgRaw.fields;
    const hasFile = (cfg || []).some((f) => f.type === "file");
    try {
      if (mode === "add") {
        if (hasFile) {
          const fd = new FormData(form);
          const res = await fetch(API_BASE + `/api/admin/${table}`, { method: "POST", headers: { Authorization: `Bearer ${token()}` }, body: fd });
          const resData = await res.json();
          if (!res.ok) throw new Error(resData.error || "Erreur");
        } else {
          const payload = {};
          new FormData(form).forEach((value, key) => { payload[key] = value; });
          await api(`/api/admin/${table}`, { method: "POST", body: JSON.stringify(payload) });
        }
      } else {
        const data = {};
        new FormData(form).forEach((value, key) => { data[key.replace(/^ef-/, "")] = value; });
        for (const [field, value] of Object.entries(data)) {
          if (!field) continue;
          if (["date", "date_echeance", "start_date", "due_date", "date_echeance_legale"].includes(field) && value === "") continue;
          await api(`/api/admin/${table}`, { method: "PUT", body: JSON.stringify({ id, field, status: value }) });
        }
      }
      if (slot) slot.remove();
      await explorerDossier(dossierId);
    } catch (e) { alert(e.message); }
  }

  async function loadDashboard() {
    const wrap = document.getElementById("tab-content");
    wrap.innerHTML = `<div id="tab-toolbar"><button id="live-btn" class="btn btn-sm" onclick="BalanceAdmin.toggleLive()">Temps réel : OFF</button><small class="muted-sm" style="margin-left:10px">Suivi des services et activité en temps réel (rafraîchissement toutes les 15 s).</small></div><div id="tab-table"><p>Chargement…</p></div>`;
    try {
      const data = await api("/api/admin/dashboard");
      renderDashboard(data);
      setLive(true);
    } catch (e) {
      document.getElementById("tab-table").innerHTML = `<div class="alert show alert-error">${e.message}</div>`;
      setLive(false);
    }
  }

  function renderDashboard(data) {
    const c = data.counts;
    const nc = data.notifications_counts || { messages: 0, taches: 0 };
    const cards = [
      { label: "Demandes de devis", value: c.devis_nouveaux, extra: "nouveau", tab: "devis_requests" },
      { label: "Messages du site", value: c.messages_nouveaux, extra: "nouveau", tab: "messages" },
      { label: "Messages clients", value: c.messages_clients, extra: "messagerie", tab: "client_messages" },
      { label: "Réponses à donner", value: nc.messages, extra: "messages sans réponse", tab: "client_messages" },
      { label: "Tâches à faire", value: nc.taches, extra: "à traiter", tab: "dossier_tasks" },
      { label: "Clients", value: c.clients, extra: "comptes", tab: "clients" },
      { label: "Dossiers actifs", value: c.dossiers_actifs, extra: "en cours", tab: "client_service_suivis" },
      { label: "Paiements en attente", value: c.paiements_retard, extra: "à relancer", tab: "payments" },
      { label: "Déclarations en retard", value: c.declarations_retard, extra: "à traiter", tab: "declarations" },
      { label: "Suivis en cours", value: c.suivis_en_cours, extra: "temps réel", tab: "service_followups" },
      { label: "Personnel actif", value: c.collaborateurs_actifs, extra: "collaborateurs", tab: "collaborateurs" },
    ];
    const cardsHtml = cards.map((k) => `<div class="dash-card" onclick="BalanceAdmin.switchTab('${k.tab}')"><div class="dash-value">${k.value}</div><div class="dash-label">${k.label}</div><div class="dash-extra">${k.extra}</div></div>`).join("");
    const fuRows = (data.recent_followups || []).map((f) => `<tr>
      <td><strong>${escapeHtml(f.client_name)}</strong></td>
      <td>${escapeHtml(f.service_title)}</td>
      <td>${escapeHtml(f.collaborateur_name)}</td>
      <td>${statusBadge(f.status)}</td>
      <td>${f.due_date}</td>
      <td><button class="btn btn-sm" onclick="BalanceAdmin.showDetail('service_followups', ${f.id})">Détail</button></td>
    </tr>`).join("");
    const msgRows = (data.recent_messages || []).map((m) => `<tr>
      <td><strong>${escapeHtml(m.client_name)}</strong></td>
      <td>${m.direction === "admin" ? "Cabinet →" : "Client →"}</td>
      <td>${escapeHtml(m.text)}${m.context_label && m.context_label !== "Général" ? `<div class="msg-context">↳ ${escapeHtml(m.context_label)}</div>` : ""}</td>
      <td>${m.created_at}</td>
    </tr>`).join("");
    const payRows = (data.recent_payments || []).map((p) => `<tr>
      <td><strong>${escapeHtml(p.client_name)}</strong></td>
      <td>${p.amount} TND</td>
      <td>${p.date}</td>
      <td>${statusBadge(p.status)}</td>
    </tr>`).join("");
    const notifRows = (data.notifications || []).map((n) => {
      if (n.kind === "message") {
        return `<tr>
          <td><span class="badge nouveau">Message</span></td>
          <td><strong>${escapeHtml(n.client_name)}</strong></td>
          <td>${escapeHtml(n.text)}${n.context_label && n.context_label !== "Général" ? `<div class="msg-context">↳ ${escapeHtml(n.context_label)}</div>` : ""}</td>
          <td>${n.date}</td>
          <td><button class="btn btn-sm" onclick="BalanceAdmin.showDetail('client_messages', ${n.id})">Répondre</button></td>
        </tr>`;
      }
      return `<tr class="${n.overdue ? "row-overdue" : ""}">
        <td><span class="badge ${n.overdue ? "annule" : "nouveau"}">Tâche</span></td>
        <td><strong>${escapeHtml(n.titre)}</strong> <small class="muted-sm">— ${escapeHtml(n.client_name)}</small></td>
        <td>${escapeHtml(n.dossier_service)}${n.followup_title !== "—" ? `<div class="msg-context">↳ ${escapeHtml(n.followup_title)}</div>` : ""}</td>
        <td>${n.date}${n.overdue ? ' <span class="badge annule">en retard</span>' : ""}</td>
        <td>
          <button class="btn btn-sm" onclick="BalanceAdmin.markTaskDone(${n.id})">Terminer</button>
          <button class="btn btn-sm btn-outline" onclick="BalanceAdmin.showDetail('dossier_tasks', ${n.id})">Détail</button>
        </td>
      </tr>`;
    }).join("");
    document.getElementById("tab-table").innerHTML = `
      <div class="dash-grid">${cardsHtml}</div>
      <h4>Notifications — messages sans réponse &amp; tâches à faire (chronologique)</h4>
      <table class="admin-table"><thead><tr><th>Type</th><th>Qui / Quoi</th><th>Contexte</th><th>Date</th><th></th></tr></thead><tbody>${notifRows || '<tr><td colspan="5"><p style="color:#64748b">Aucune notification. Tout est à jour.</p></td></tr>'}</tbody></table>
      <h4>Suivi des services — temps réel</h4>
      <table class="admin-table"><thead><tr><th>Client</th><th>Service</th><th>Collaborateur</th><th>Statut</th><th>Échéance</th><th></th></tr></thead><tbody>${fuRows || '<tr><td colspan="6"><p style="color:#64748b">Aucun suivi de service.</p></td></tr>'}</tbody></table>
      <div class="dash-cols">
        <div><h4>Derniers messages clients</h4><table class="admin-table"><thead><tr><th>Client</th><th>Sens</th><th>Message</th><th>Date</th></tr></thead><tbody>${msgRows || '<tr><td colspan="4"><p style="color:#64748b">Aucun message.</p></td></tr>'}</tbody></table></div>
        <div><h4>Derniers paiements</h4><table class="admin-table"><thead><tr><th>Client</th><th>Montant</th><th>Date</th><th>Statut</th></tr></thead><tbody>${payRows || '<tr><td colspan="4"><p style="color:#64748b">Aucun paiement.</p></td></tr>'}</tbody></table></div>
      </div>`;
  }

  async function deleteCollaborateur(id, name) {
    if (!confirm(`Supprimer le collaborateur « ${name} » ?`)) return;
    try {
      await api("/api/admin/collaborateurs", { method: "DELETE", body: JSON.stringify({ id }) });
      collabCache = [];
      applyFilters();
    } catch (e) {
      alert(e.message);
    }
  }

  async function markTaskDone(id) {
    if (!confirm("Marquer cette tâche comme terminée ?")) return;
    try {
      await api("/api/admin/dossier_tasks", { method: "PUT", body: JSON.stringify({ id, field: "statut", status: "termine" }) });
      loadDashboard();
    } catch (e) {
      alert(e.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (token()) {
      api("/api/admin/dashboard")
        .then(showPanel)
        .catch(() => sessionStorage.removeItem(TOKEN_KEY));
    }
  });

  return { login, logout, switchTab, saveField, toggleCreate, showDetail, closeDetail, applyFilters, toggleLive, addSubService, deleteService, replyMessage, loadExplorer, explorerDossiers, explorerDossier, explorerAdd, explorerEdit, explorerDelete, explorerCancel, deleteCollaborateur, markTaskDone };
})();
