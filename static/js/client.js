const BalanceClient = (() => {
  const API_BASE = window.BALANCEWORK_API || "";
  const TOKEN_KEY = "bts_client_token";

  function token() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  function showAlert(id, type, message) {
    const el = document.getElementById(id);
    el.className = `alert show alert-${type}`;
    el.textContent = message;
  }

  function clearAlert(id) {
    const el = document.getElementById(id);
    el.className = "alert";
    el.textContent = "";
  }

  async function api(path, options = {}) {
    const res = await fetch(API_BASE + path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
        ...(options.headers || {}),
      },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 401 && token()) {
        sessionExpired();
        throw new Error("Votre session a expiré. Veuillez vous reconnecter.");
      }
      throw new Error(data.error || "Erreur");
    }
    return data;
  }

  function sessionExpired() {
    stopAutoRefresh();
    localStorage.removeItem(TOKEN_KEY);
    const db = document.getElementById("dashboard-box");
    const auth = document.getElementById("auth-box");
    if (db) db.style.display = "none";
    if (auth) auth.style.display = "";
    showAlert("client-alert", "error", "Votre session a expiré. Veuillez vous reconnecter.");
  }

  async function apiForm(path, formData) {
    const res = await fetch(API_BASE + path, {
      method: "POST",
      headers: { ...(token() ? { Authorization: `Bearer ${token()}` } : {}) },
      body: formData,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Erreur");
    return data;
  }

  async function login(e) {
    e.preventDefault();
    clearAlert("client-alert");
    const btn = e.target.querySelector("button");
    btn.disabled = true;
    try {
      const data = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: document.getElementById("login-email").value.trim(),
          password: document.getElementById("login-password").value,
        }),
      });
      localStorage.setItem(TOKEN_KEY, data.token);
      showDashboard(data.client);
    } catch (err) {
      showAlert("client-alert", "error", err.message);
    } finally {
      btn.disabled = false;
    }
  }

  async function register(e) {
    e.preventDefault();
    clearAlert("client-alert");
    const btn = e.target.querySelector("button");
    btn.disabled = true;
    try {
      const data = await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          name: document.getElementById("reg-name").value.trim(),
          prenom: document.getElementById("reg-prenom").value.trim(),
          email: document.getElementById("reg-email").value.trim(),
          phone: document.getElementById("reg-phone").value.trim(),
          matricule_fiscale: document.getElementById("reg-matricule").value.trim(),
          cin: document.getElementById("reg-cin").value.trim(),
          password: document.getElementById("reg-password").value,
        }),
      });
      localStorage.setItem(TOKEN_KEY, data.token);
      showDashboard(data.client);
    } catch (err) {
      showAlert("client-alert", "error", err.message);
    } finally {
      btn.disabled = false;
    }
  }

  function logout() {
    stopAutoRefresh();
    api("/api/auth/logout", { method: "POST" }).catch(() => {});
    localStorage.removeItem(TOKEN_KEY);
    document.getElementById("dashboard-box").style.display = "none";
    document.getElementById("auth-box").style.display = "";
    clearAlert("client-alert");
  }

  function renderDeclarations(declarations) {
    const wrap = document.getElementById("declarations-content");
    if (!(declarations || []).length) {
      wrap.innerHTML = "";
      return;
    }
    const statutBadge = (s) => {
      const map = { "Déposé (Validé)": "confirme", "En retard": "annule", "En cours de vérification": "nouveau" };
      return `badge ${map[s] || "nouveau"}`;
    };
    const rows = declarations
      .map((d) => {
        const paye = parseFloat(d.montant_a_payer);
        const overdue = d.statut === "En retard";
        return `<tr>
          <td>${d.type_declaration}</td>
          <td>${escapeHtml(d.periode)}</td>
          <td>${d.date_echeance_legale}</td>
          <td><span class="${statutBadge(d.statut)}">${d.statut}</span></td>
          <td>${paye > 0 ? paye.toFixed(3) + " TND" : "0,00 TND"}</td>
          <td>${escapeHtml(d.numero_quittance_ou_tej)}</td>
        </tr>`;
      })
      .join("");
    wrap.innerHTML = `<div class="card">
      <h3>Mes déclarations fiscales</h3>
      <p style="color:#64748b;font-size:14px;margin:0 0 14px">Suivi des obligations déclaratives (DGI) gérées par votre cabinet.</p>
      <table class="admin-table">
        <thead><tr><th>Type</th><th>Période</th><th>Échéance légale</th><th>Statut</th><th>Montant à payer</th><th>N° quittance / TEJ</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  }

  function toggleDossierEdit(id) {
    const form = document.getElementById(`dossier-edit-${id}`);
    form.style.display = form.style.display === "none" ? "" : "none";
  }

  async function saveDossierEdit(id) {
    const description = document.getElementById(`de-desc-${id}`).value.trim();
    const serviceNote = document.getElementById(`de-service-note-${id}`).value.trim();
    if (!description) {
      showAlert("dashboard-alert", "error", "La note du dossier ne peut pas être vide.");
      return;
    }
    const btn = event.target;
    btn.disabled = true;
    try {
      await api(`/api/client/dossiers/${id}`, {
        method: "PUT",
        body: JSON.stringify({ description, service_note: serviceNote }),
      });
      showAlert("dashboard-alert", "success", "Dossier modifié.");
      api("/api/client/dashboard")
        .then((d) => renderSuivis(d.suivis || []))
        .catch(() => {});
    } catch (err) {
      showAlert("dashboard-alert", "error", err.message);
    } finally {
      btn.disabled = false;
    }
  }

  let lastSuivis = [];

  function renderSuivis(suivis) {
    lastSuivis = suivis || [];
    const wrap = document.getElementById("dashboard-content");
    if (!suivis.length) {
      wrap.innerHTML = '<p style="color:#64748b">Aucun dossier en cours pour le moment. Ouvrez un dossier ci-dessus.</p>';
      return;
    }
    const cards = suivis
      .map((s) => {
        const badge = s.statut_service === "Clôturé" ? "badge confirme" : "badge nouveau";
        const pay = s.statut_paiement === "Payé" ? "badge confirme" : "badge nouveau";

        const tasks = (s.tasks || []).length
          ? `<ul class="task-list">${s.tasks
              .map((t) => `<li><span class="badge ${t.statut === "Terminé" ? "confirme" : "nouveau"}">${t.statut}</span> ${escapeHtml(t.titre)} — <small>${t.date_echeance} · ${t.repetition}</small></li>`)
              .join("")}</ul>`
          : '<p class="muted-sm">Aucune tâche définie pour ce dossier.</p>';

        const serviceSuivis = (s.service_followups || []).length
          ? `<ul class="task-list">${s.service_followups
              .map(
                (sf) =>
                  `<li><span class="badge ${sf.status === "Terminé" || sf.status === "Clôturé" ? "confirme" : "nouveau"}">${sf.status}</span> ${escapeHtml(sf.service)} — <small>du ${sf.start_date} au ${sf.due_date}</small>${
                    sf.tasks.length ? `<br><small>↳ Tâches : ${sf.tasks.map((t) => escapeHtml(t.titre) + " (" + t.statut + ")").join(", ")}</small>` : ""
                  }</li>`,
              )
              .join("")}</ul>`
          : "";

        const prefactures = (s.prefactures || []).length
          ? `<p class="muted-sm">Préfactures : ${s.prefactures
              .map((p) => `<a href="#" onclick="event.preventDefault();BalanceClient.showPrefacture(${p.id})">${escapeHtml(p.numero)}</a> <span class="badge ${p.statut === "Payée" ? "confirme" : "nouveau"}">${p.statut}</span>`)
              .join(" · ")}</p>`
          : "";

        const attachments = (s.attachments || []).length
          ? `<ul class="att-list">${s.attachments
              .map(
                (a) =>
                  `<li><span class="att-ico att-${a.category}">${a.category}</span> <a href="${a.url}" target="_blank" rel="noopener">${escapeHtml(a.name)}</a> <small>(${a.size} · ${a.uploaded_by})</small>${
                    a.uploaded_by === "Vous" ? ` <a href="#" class="att-del" onclick="event.preventDefault();BalanceClient.deleteAttachment(${a.id})">✕</a>` : ""
                  }</li>`,
              )
              .join("")}</ul>`
          : '<p class="muted-sm">Aucune pièce jointe.</p>';

        const canEdit = s.statut_service === "En cours de traitement";
        const editForm = canEdit
          ? `<button class="btn btn-sm btn-outline" onclick="BalanceClient.toggleDossierEdit(${s.id})">Modifier la note</button>
          <div class="dossier-edit" id="dossier-edit-${s.id}" style="display:none">
            <label for="de-desc-${s.id}">Note du dossier</label>
            <textarea id="de-desc-${s.id}" rows="2">${escapeHtml(s.commentaire || "")}</textarea>
            <label for="de-service-note-${s.id}">Note du service (dans le dossier)</label>
            <textarea id="de-service-note-${s.id}" rows="2">${escapeHtml(s.service_note || "")}</textarea>
            <button class="btn btn-sm" onclick="BalanceClient.saveDossierEdit(${s.id})">Enregistrer</button>
          </div>`
          : "";

        return `<div class="dossier-card">
          <div class="dossier-head">
            <div>
              <strong>${escapeHtml(s.service)}</strong>
              <div class="dossier-meta">Échéance : ${s.date_echeance} · Fréquence : ${s.frequence} · Prix : ${s.montant} TND</div>
            </div>
            <div class="dossier-status">
              <span class="${badge}">${s.statut_service}</span>
              <span class="${pay}">${s.statut_paiement}</span>
            </div>
          </div>
          <p class="muted-sm">${escapeHtml(s.commentaire || "")}</p>
          ${s.service_note ? `<p class="muted-sm"><strong>Note du service :</strong> ${escapeHtml(s.service_note)}</p>` : ""}
          <div class="dossier-actions">${editForm}</div>
          ${serviceSuivis ? `<div class="dossier-block"><strong>Suivi du service</strong>${serviceSuivis}</div>` : ""}
          <div class="dossier-block"><strong>Tâches</strong>${tasks}</div>
          ${prefactures}
          <div class="dossier-block">
            <strong>Pièces jointes</strong>
            <div class="att-actions">
              ${attachments}
              <div class="upload-row">
                <input type="file" id="file-${s.id}" class="file-input" />
                <button class="btn btn-sm" onclick="BalanceClient.uploadAttachment(${s.id})">Ajouter un fichier</button>
                <small class="muted-sm">image · pdf · Excel · Word · txt · zip · audio · vidéo (20 Mo max)</small>
              </div>
            </div>
          </div>
        </div>`;
      })
      .join("");
    wrap.innerHTML = cards;
  }

  async function uploadAttachment(dossierId) {
    const input = document.getElementById(`file-${dossierId}`);
    if (!input.files.length) {
      showAlert("dashboard-alert", "error", "Choisissez un fichier.");
      return;
    }
    const fd = new FormData();
    fd.append("file", input.files[0]);
    try {
      await apiForm(`/api/client/dossiers/${dossierId}/attachments`, fd);
      showAlert("dashboard-alert", "success", "Fichier ajouté.");
      input.value = "";
      api("/api/client/dashboard")
        .then((d) => renderSuivis(d.suivis || []))
        .catch(() => {});
    } catch (err) {
      showAlert("dashboard-alert", "error", err.message);
    }
  }

  async function deleteAttachment(attachmentId) {
    try {
      await api(`/api/client/attachments/${attachmentId}`, { method: "DELETE" });
      api("/api/client/dashboard")
        .then((d) => renderSuivis(d.suivis || []))
        .catch(() => {});
    } catch (err) {
      showAlert("dashboard-alert", "error", err.message);
    }
  }

  async function showPrefacture(id) {
    try {
      const data = await api(`/api/client/prefacture/${id}`);
      const pf = data.prefacture;
      const cab = data.cabinet;
      const cl = data.client;
      const tva = parseFloat(pf.montant_ht) * (parseFloat(pf.taux_tva) / 100);
      const ttc = parseFloat(pf.montant_ttc);
      document.getElementById("prefacture-overlay").style.display = "flex";
      document.getElementById("prefacture-html").innerHTML = `
        <div class="pf-head">
          <div class="pf-logo">BT</div>
          <div>
            <h3>${escapeHtml(cab.nom)}</h3>
            <p class="muted-sm">${escapeHtml(cab.adresse)}<br>${escapeHtml(cab.email)} · ${escapeHtml(cab.telephone)}<br>Matricule fiscal : ${escapeHtml(cab.matricule)}</p>
          </div>
        </div>
        <h4 class="pf-title">PRÉFACTURE ${escapeHtml(pf.numero)}</h4>
        <p class="muted-sm">Date : ${pf.date} · Statut : <span class="badge nouveau">${pf.statut}</span></p>
        <p class="muted-sm">Client : <strong>${escapeHtml(cl.nom)}</strong> (${cl.statut})<br>${escapeHtml(cl.adresse || "")}<br>${cl.matricule_fiscale ? "Matricule fiscal : " + cl.matricule_fiscale : ""}${cl.cin ? " · CIN : " + cl.cin : ""}</p>
        <table class="admin-table pf-table">
          <thead><tr><th>Désignation</th><th>Fréquence</th><th>Montant HT</th><th>TVA ${pf.taux_tva}%</th><th>Montant TTC</th></tr></thead>
          <tbody><tr>
            <td>${escapeHtml(pf.service)}${pf.description ? "<br><small>" + escapeHtml(pf.description) + "</small>" : ""}</td>
            <td>${pf.frequence}</td>
            <td>${pf.montant_ht} TND</td>
            <td>${tva.toFixed(3)} TND</td>
            <td><strong>${ttc.toFixed(3)} TND</strong></td>
          </tr></tbody>
        </table>`;
    } catch (err) {
      showAlert("dashboard-alert", "error", err.message);
    }
  }

  function closePrefacture() {
    document.getElementById("prefacture-overlay").style.display = "none";
  }

  function printPrefacture() {
    const html = document.getElementById("prefacture-html").innerHTML;
    const w = window.open("", "_blank");
    w.document.write(`<html><head><title>Préfacture</title><style>body{font-family:Georgia,serif;color:#1e293b;padding:40px}.pf-logo{width:70px;height:70px;border-radius:50%;background:#b91c1c;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:26px}.pf-head{display:flex;gap:16px;align-items:center;margin-bottom:20px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #cbd5e1;padding:8px;text-align:left}th{background:#f1f5f9}.muted-sm{color:#64748b}</style></head><body>${html}</body></html>`);
    w.document.close();
    w.focus();
    w.print();
  }

  async function renderServices() {
    const sel = document.getElementById("dos-service");
    try {
      const data = await api("/api/services");
      if (!(data.services || []).length) {
        sel.innerHTML = '<option value="">— Aucun service disponible —</option>';
        return;
      }
      sel.innerHTML =
        `<option value="">— Choisir un service —</option>` +
        data.services
          .map((s) => {
            const subs = (s.subservices || [])
              .map((ss) => `<option value="${ss.id}">${escapeHtml(ss.title)}</option>`)
              .join("");
            const root = `<option value="${s.id}">${escapeHtml(s.title)} (racine)</option>`;
            return `<optgroup label="${escapeHtml(s.title)}">${subs ? subs + root : root}</optgroup>`;
          })
          .join("");
    } catch (e) {
      sel.innerHTML = '<option value="">Erreur de chargement</option>';
    }
  }

  function resetDossier() {
    document.getElementById("dos-service").value = "";
    document.getElementById("dos-description").value = "";
    document.getElementById("dos-service-note").value = "";
  }

  async function openDossier() {
    const serviceId = document.getElementById("dos-service").value;
    const desc = document.getElementById("dos-description").value.trim();
    if (!serviceId || !desc) {
      showAlert("dashboard-alert", "error", "Choisissez un service et décrivez votre besoin.");
      return;
    }
    const btn = event.target;
    btn.disabled = true;
    try {
      const data = await api("/api/client/dossiers", {
        method: "POST",
        body: JSON.stringify({
          type_service: parseInt(serviceId, 10),
          description: desc,
          service_note: document.getElementById("dos-service-note").value.trim(),
        }),
      });
      showAlert("dashboard-alert", "success", data.message);
      resetDossier();
      api("/api/client/dashboard")
        .then((d) => renderSuivis(d.suivis || []))
        .catch(() => {});
    } catch (err) {
      showAlert("dashboard-alert", "error", err.message);
    } finally {
      btn.disabled = false;
    }
  }

  let autoRefreshTimer = null;

  function startAutoRefresh() {
    stopAutoRefresh();
    autoRefreshTimer = setInterval(async () => {
      const ae = document.activeElement;
      if (ae && ["INPUT", "SELECT", "TEXTAREA"].includes(ae.tagName)) return;
      if (document.getElementById("prefacture-overlay").style.display === "flex") return;
      if (document.getElementById("dashboard-box").style.display === "none") return;
      try {
        const data = await api("/api/client/dashboard");
        renderDeclarations(data.declarations || []);
        renderSuivis(data.suivis || []);
        populateMessageContext();
        loadMessages();
      } catch (e) {}
    }, 20000);
  }

  function stopAutoRefresh() {
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer);
      autoRefreshTimer = null;
    }
  }

  function populateMessageContext() {
    const sel = document.getElementById("msg-dossier");
    if (!sel) return;
    sel.innerHTML =
      '<option value="">Tous les dossiers</option>' +
      (lastSuivis || []).map((s) => `<option value="${s.id}">${escapeHtml(s.service)} (N°${s.id})</option>`).join("");
    updateTaskOptions();
  }

  function updateTaskOptions() {
    const taskSel = document.getElementById("msg-task");
    const dossierEl = document.getElementById("msg-dossier");
    if (!taskSel || !dossierEl) return;
    const dossierId = dossierEl.value;
    let tasks = [];
    if (dossierId) {
      const s = (lastSuivis || []).find((x) => String(x.id) === String(dossierId));
      tasks = (s && s.tasks) || [];
    }
    taskSel.innerHTML =
      `<option value="">${dossierId ? "— Toutes les tâches du dossier —" : "— Aucune tâche précise —"}</option>` +
      tasks.map((t) => `<option value="${t.id}">${escapeHtml(t.titre)}</option>`).join("");
  }

  function onContextChange() {
    updateTaskOptions();
    loadMessages();
  }

  async function loadMessages() {
    const wrap = document.getElementById("messages-thread");
    const dossierEl = document.getElementById("msg-dossier");
    const taskEl = document.getElementById("msg-task");
    const dossierId = dossierEl ? dossierEl.value : "";
    const taskId = taskEl ? taskEl.value : "";
    const qs = [];
    if (dossierId) qs.push("dossier=" + encodeURIComponent(dossierId));
    if (taskId) qs.push("task=" + encodeURIComponent(taskId));
    try {
      const data = await api("/api/client/messages" + (qs.length ? "?" + qs.join("&") : ""));
      if (!(data.messages || []).length) {
        wrap.innerHTML = '<p style="color:#64748b">Aucun message pour le moment.</p>';
        return;
      }
      wrap.innerHTML = data.messages
        .map((m) => `<div class="msg ${m.direction === "admin" ? "msg-admin" : "msg-client"}">
          <strong>${m.direction === "admin" ? "Cabinet" : "Vous"}</strong> — <small>${m.created_at}</small>
          ${m.context_label && m.context_label !== "Général" ? `<br><small class="msg-context">↳ ${escapeHtml(m.context_label)}</small>` : ""}
          <p>${escapeHtml(m.text)}</p>
        </div>`)
        .join("");
      wrap.scrollTop = wrap.scrollHeight;
    } catch (e) {
      wrap.innerHTML = `<p style="color:#b91c1c">${e.message}</p>`;
    }
  }

  async function sendMessage() {
    const text = document.getElementById("msg-text").value.trim();
    if (!text) {
      showAlert("dashboard-alert", "error", "Écrivez un message.");
      return;
    }
    const btn = event.target;
    btn.disabled = true;
    const payload = { text };
    const dossierEl = document.getElementById("msg-dossier");
    const taskEl = document.getElementById("msg-task");
    if (dossierEl && dossierEl.value) payload.dossier = dossierEl.value;
    if (taskEl && taskEl.value) payload.task = taskEl.value;
    try {
      await api("/api/client/messages", { method: "POST", body: JSON.stringify(payload) });
      document.getElementById("msg-text").value = "";
      await loadMessages();
    } catch (err) {
      showAlert("dashboard-alert", "error", err.message);
    } finally {
      btn.disabled = false;
    }
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function populateProfile(client) {
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val || "";
    };
    set("prof-name", client.name);
    set("prof-prenom", client.prenom);
    set("prof-phone", client.phone);
    set("prof-adresse", client.adresse);
    set("prof-matricule", client.matricule_fiscale);
    set("prof-cin", client.cin);
  }

  async function saveProfile() {
    clearAlert("profile-alert");
    const btn = event.target;
    btn.disabled = true;
    try {
      await api("/api/client/profile", {
        method: "PUT",
        body: JSON.stringify({
          name: document.getElementById("prof-name").value.trim(),
          prenom: document.getElementById("prof-prenom").value.trim(),
          phone: document.getElementById("prof-phone").value.trim(),
          adresse: document.getElementById("prof-adresse").value.trim(),
          matricule_fiscale: document.getElementById("prof-matricule").value.trim(),
          cin: document.getElementById("prof-cin").value.trim(),
          old_password: document.getElementById("prof-old-password").value,
          new_password: document.getElementById("prof-new-password").value,
        }),
      });
      showAlert("profile-alert", "success", "Profil mis à jour.");
      document.getElementById("prof-old-password").value = "";
      document.getElementById("prof-new-password").value = "";
    } catch (err) {
      showAlert("profile-alert", "error", err.message);
    } finally {
      btn.disabled = false;
    }
  }

  function showDashboard(client) {
    document.getElementById("auth-box").style.display = "none";
    document.getElementById("dashboard-box").style.display = "";
    document.getElementById("client-welcome").textContent =
      `Bienvenue ${client.display_name || client.name}${client.matricule_fiscale ? " — Matricule : " + client.matricule_fiscale : ""}`;
    populateProfile(client);
    renderServices();
    startAutoRefresh();
    api("/api/client/dashboard")
      .then((data) => {
        renderDeclarations(data.declarations || []);
        renderSuivis(data.suivis || []);
        populateMessageContext();
        loadMessages();
      })
      .catch((err) => {
        document.getElementById("dashboard-content").innerHTML =
          `<div class="alert show alert-error">${err.message}</div>`;
      });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("login-form").addEventListener("submit", login);
    document.getElementById("register-form").addEventListener("submit", register);
    if (token()) {
      api("/api/client/dashboard")
        .then((data) => showDashboard(data.client))
        .catch(() => localStorage.removeItem(TOKEN_KEY));
    }
  });

  return { login, register, logout, openDossier, sendMessage, resetDossier, onContextChange, uploadAttachment, deleteAttachment, showPrefacture, closePrefacture, printPrefacture, saveProfile, toggleDossierEdit, saveDossierEdit };
})();
