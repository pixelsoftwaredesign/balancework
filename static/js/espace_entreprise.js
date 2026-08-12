const BalanceEntrep = (() => {
  const API_BASE = window.BALANCEWORK_API || "";
  const TOKEN_KEY = "bts_client_token";

  let comptaData = null;
  let comptaSub = "plan";
  let leafComptes = [];

  function token() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  function showAlert(id, type, message) {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = `alert show alert-${type}`;
    el.textContent = message;
  }

  function clearAlert(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = "alert";
    el.textContent = "";
  }

  function escapeHtml(str) {
    return String(str == null ? "" : str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
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
    localStorage.removeItem(TOKEN_KEY);
    const db = document.getElementById("dashboard-box");
    const auth = document.getElementById("auth-box");
    if (db) db.style.display = "none";
    if (auth) auth.style.display = "";
    showAlert("client-alert", "error", "Votre session a expiré. Veuillez vous reconnecter.");
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
    api("/api/auth/logout", { method: "POST" }).catch(() => {});
    localStorage.removeItem(TOKEN_KEY);
    document.getElementById("dashboard-box").style.display = "none";
    document.getElementById("auth-box").style.display = "";
    clearAlert("client-alert");
  }

  async function showDashboard(client) {
    document.getElementById("auth-box").style.display = "none";
    document.getElementById("dashboard-box").style.display = "";
    document.getElementById("client-welcome").textContent = `Bienvenue, ${client.prenom || client.name} ${client.name}`.trim();
    clearAlert("client-alert");
    comptaData = null;
    showTab("compta");
  }

  function showTab(tab) {
    const cBtn = document.getElementById("tab-compta");
    const dBtn = document.getElementById("tab-dossiers");
    const cBox = document.getElementById("compta-content");
    const dBox = document.getElementById("dossiers-content");
    if (tab === "compta") {
      cBtn.className = "btn btn-sm";
      dBtn.className = "btn btn-sm btn-outline";
      cBox.style.display = "";
      dBox.style.display = "none";
      loadCompta();
    } else {
      dBtn.className = "btn btn-sm";
      cBtn.className = "btn btn-sm btn-outline";
      dBox.style.display = "";
      cBox.style.display = "none";
      loadDossiers();
    }
  }

  // ---------------- Comptabilité tenant ----------------

  async function loadCompta() {
    const wrap = document.getElementById("compta-content");
    if (!comptaData) {
      wrap.innerHTML = `<p>Chargement…</p>`;
      try {
        comptaData = await api("/api/client/comptabilite");
      } catch (e) {
        wrap.innerHTML = `<div class="alert show alert-error">${escapeHtml(e.message)}</div>`;
        return;
      }
    }
    const ent = comptaData.entreprise;
    leafComptes = collectComptes(comptaData.plan || []);
    wrap.innerHTML = `
      <div class="card" style="margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
          <div>
            <h3 style="margin:0">${escapeHtml(ent.raison_sociale)}</h3>
            <p class="muted-sm" style="margin:6px 0 0">
              ${[ent.forme_juridique, ent.matricule_fiscale, ent.registre_commerce, ent.ville].filter(Boolean).join(" · ") || "Entreprise (tenant)"}
            </p>
          </div>
          <button class="btn btn-sm btn-outline" onclick="BalanceEntrep.refreshCompta()">⟳ Recharger</button>
        </div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px">
        <button class="btn btn-sm" id="sub-plan" onclick="BalanceEntrep.comptaSubView('plan')">Plan comptable</button>
        <button class="btn btn-sm btn-outline" id="sub-ecritures" onclick="BalanceEntrep.comptaSubView('ecritures')">Journaux &amp; pièces</button>
        <button class="btn btn-sm btn-outline" id="sub-grandlivre" onclick="BalanceEntrep.comptaSubView('grandlivre')">Grand livre</button>
        <button class="btn btn-sm btn-outline" id="sub-bilan" onclick="BalanceEntrep.comptaSubView('bilan')">Bilan &amp; résultat</button>
      </div>
      <div id="compta-body"></div>`;
    comptaSubView(comptaSub);
  }

  async function refreshCompta() {
    comptaData = null;
    loadCompta();
  }

  function collectComptes(nodes) {
    const out = [];
    (nodes || []).forEach((n) => {
      out.push(n);
      out.push(...collectComptes(n.enfants));
    });
    return out;
  }

  async function comptaSubView(sub) {
    comptaSub = sub;
    ["plan", "ecritures", "grandlivre", "bilan"].forEach((s) => {
      const btn = document.getElementById(`sub-${s}`);
      if (btn) btn.className = s === sub ? "btn btn-sm" : "btn btn-sm btn-outline";
    });
    if (sub === "plan") renderPlan();
    else if (sub === "ecritures") renderEcritures();
    else if (sub === "grandlivre") renderGrandLivre();
    else renderBilan();
  }

  // Plan comptable

  function renderPlan() {
    const body = document.getElementById("compta-body");
    const plan = comptaData.plan || [];
    body.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px">
        <strong>Plan comptable tunisien — ${comptaData.plan_total} comptes</strong>
        <button class="btn btn-sm" onclick="BalanceEntrep.comptaAddCompte(null)">＋ Ajouter une classe / compte racine</button>
      </div>
      <div id="compta-compte-form"></div>
      ${plan.length ? `<ul class="plan-tree">${plan.map((n) => planRow(n, 0)).join("")}</ul>` : `<p class="muted-sm">Aucun compte dans le plan.</p>`}`;
  }

  function planRow(n, depth) {
    const pad = depth * 18;
    return `<li>
      <div class="plan-row" style="margin-left:${pad}px">
        <span class="plan-num">${escapeHtml(n.numero)}</span>
        <span class="plan-int">${escapeHtml(n.intitule)}</span>
        ${n.active ? "" : ' <span class="badge annule">inactif</span>'}
        <span class="explorer-actions">
          <button class="btn btn-sm btn-outline" onclick="BalanceEntrep.comptaEditCompte(${n.id})">Modifier</button>
          <button class="btn btn-sm btn-outline" onclick="BalanceEntrep.comptaAddCompte(${n.id})">＋ Sous-compte</button>
          <button class="btn btn-sm btn-danger" onclick="BalanceEntrep.comptaDeleteCompte(${n.id})">Supprimer</button>
        </span>
      </div>
      ${n.enfants && n.enfants.length ? `<ul>${n.enfants.map((e) => planRow(e, depth + 1)).join("")}</ul>` : ""}
    </li>`;
  }

  function comptaAddCompte(parentId) {
    const slot = document.getElementById("compta-compte-form");
    if (!slot) return;
    slot.innerHTML = `<div class="card explorer-form">
      <h4 style="margin:0 0 10px">Ajouter un compte${parentId ? " (sous-compte)" : " (classe / racine)"}</h4>
      <form id="compta-compte-form-f" class="form-grid" style="margin:0">
        <div class="form-group"><label>Numéro *</label><input name="numero" type="text" required /></div>
        <div class="form-group"><label>Intitulé *</label><input name="intitule" type="text" required /></div>
        <input type="hidden" name="parent" value="${parentId || ""}" />
        <div class="form-group full" style="display:flex;gap:8px">
          <button class="btn" type="submit">Enregistrer</button>
          <button class="btn btn-outline" type="button" onclick="BalanceEntrep.comptaCompteFormCancel()">Annuler</button>
        </div>
      </form>
    </div>`;
    slot.querySelector("#compta-compte-form-f").addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(slot.querySelector("#compta-compte-form-f"));
      comptaSaveCompte({ numero: fd.get("numero"), intitule: fd.get("intitule"), parent: fd.get("parent") });
    });
  }

  async function comptaEditCompte(id) {
    const slot = document.getElementById("compta-compte-form");
    if (!slot) return;
    const row = leafComptes.find((c) => c.id === id) || {};
    slot.innerHTML = `<div class="card explorer-form">
      <h4 style="margin:0 0 10px">Modifier le compte ${escapeHtml(row.numero || "")}</h4>
      <form id="compta-compte-form-f" class="form-grid" style="margin:0">
        <div class="form-group"><label>Numéro *</label><input name="numero" type="text" required value="${escapeHtml(row.numero || "")}" /></div>
        <div class="form-group"><label>Intitulé *</label><input name="intitule" type="text" required value="${escapeHtml(row.intitule || "")}" /></div>
        <div class="form-group"><label>Actif</label><select name="active">
          <option value="true" ${row.active ? "selected" : ""}>Oui</option>
          <option value="false" ${!row.active ? "selected" : ""}>Non</option>
        </select></div>
        <div class="form-group full" style="display:flex;gap:8px">
          <button class="btn" type="submit">Enregistrer</button>
          <button class="btn btn-outline" type="button" onclick="BalanceEntrep.comptaCompteFormCancel()">Annuler</button>
        </div>
      </form>
    </div>`;
    slot.querySelector("#compta-compte-form-f").addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(slot.querySelector("#compta-compte-form-f"));
      comptaSaveCompte({ id, numero: fd.get("numero"), intitule: fd.get("intitule"), active: fd.get("active") }, true);
    });
  }

  async function comptaSaveCompte(payload, isEdit) {
    try {
      if (isEdit) {
        for (const field of ["numero", "intitule", "active"]) {
          await api("/api/client/comptabilite", {
            method: "POST",
            body: JSON.stringify({ action: "compte_update", id: payload.id, field, value: payload[field] }),
          });
        }
      } else {
        await api("/api/client/comptabilite", {
          method: "POST",
          body: JSON.stringify({ action: "compte_create", numero: payload.numero, intitule: payload.intitule, parent: payload.parent }),
        });
      }
      await refreshCompta();
    } catch (e) {
      showAlert("dashboard-alert", "error", e.message);
    }
  }

  function comptaCompteFormCancel() {
    const slot = document.getElementById("compta-compte-form");
    if (slot) slot.innerHTML = "";
  }

  async function comptaDeleteCompte(id) {
    const row = leafComptes.find((c) => c.id === id) || {};
    if (!confirm(`Supprimer le compte ${row.numero ? row.numero + " — " : ""}${row.intitule || ""} ?`)) return;
    try {
      await api("/api/client/comptabilite", { method: "DELETE", body: JSON.stringify({ kind: "compte", id }) });
      await refreshCompta();
    } catch (e) {
      showAlert("dashboard-alert", "error", e.message);
    }
  }

  // Journaux & pièces

  function renderEcritures() {
    const body = document.getElementById("compta-body");
    const items = comptaData.ecritures || [];
    body.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px">
        <strong>Journaux & pièces comptables</strong>
        <button class="btn btn-sm" onclick="BalanceEntrep.comptaEcritureForm()">＋ Nouvelle pièce</button>
      </div>
      <div id="compta-ecriture-form"></div>
      <table class="admin-table"><thead><tr><th>N°</th><th>Date</th><th>Journal</th><th>Pièce</th><th>Libellé</th><th>Débit</th><th>Crédit</th><th>Statut</th><th></th></tr></thead><tbody>
        ${items.map((w) => `<tr>
          <td><strong>N°${w.id}</strong></td>
          <td>${w.date}</td>
          <td>${escapeHtml(w.journal.replace(/_/g, " "))}</td>
          <td>${escapeHtml(w.numero_piece)}</td>
          <td>${escapeHtml(w.libelle)}</td>
          <td>${w.total_debit}</td>
          <td>${w.total_credit}</td>
          <td>
            <select class="status-select" onchange="BalanceEntrep.comptaEcritureStatut(${w.id}, this.value)">
              <option value="brouillon" ${w.statut === "brouillon" ? "selected" : ""}>Brouillon</option>
              <option value="valide" ${w.statut === "valide" ? "selected" : ""}>Validé</option>
            </select>
          </td>
          <td>
            <button class="btn btn-sm btn-outline" onclick="BalanceEntrep.comptaVoirEcriture(${w.id})">Lignes</button>
            <button class="btn btn-sm btn-danger" onclick="BalanceEntrep.comptaDeleteEcriture(${w.id})">Supprimer</button>
          </td>
        </tr>`).join("") || '<tr><td colspan="9"><p class="muted-sm">Aucune écriture.</p></td></tr>'}
      </tbody></table>`;
  }

  async function comptaEcritureStatut(id, statut) {
    try {
      await api("/api/client/comptabilite", { method: "POST", body: JSON.stringify({ action: "ecriture_statut", id, statut }) });
      await refreshCompta();
    } catch (e) {
      showAlert("dashboard-alert", "error", e.message);
    }
  }

  async function comptaVoirEcriture(id) {
    const w = (comptaData.ecritures || []).find((r) => r.id === id);
    if (!w) return;
    const lines = (w.lignes || [])
      .map((l) => `<tr><td><strong>${escapeHtml(l.numero)}</strong> ${escapeHtml(l.intitule)}</td><td>${escapeHtml(l.libelle || "—")}</td><td style="text-align:right">${l.debit}</td><td style="text-align:right">${l.credit}</td></tr>`)
      .join("");
    document.getElementById("dashboard-alert").innerHTML = "";
    showAlert("dashboard-alert", "info", "");
    const body = document.getElementById("compta-body");
    const prev = body.innerHTML;
    body.insertAdjacentHTML("afterbegin", `<div class="card" style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <strong>Pièce N°${w.id} — ${escapeHtml(w.libelle)}</strong>
        <button class="btn btn-sm btn-outline" onclick="BalanceEntrep.comptaCloseEcriture(this)">Fermer</button>
      </div>
      <p class="muted-sm">${w.date} · ${escapeHtml(w.journal)} · ${escapeHtml(w.numero_piece)} · ${w.equilibree ? "Équilibrée" : "Déséquilibrée"}</p>
      <table class="admin-table"><thead><tr><th>Compte</th><th>Libellé</th><th>Débit</th><th>Crédit</th></tr></thead><tbody>
        ${lines}
      </tbody><tfoot><tr><td colspan="2"><strong>Totaux</strong></td><td style="text-align:right"><strong>${w.total_debit}</strong></td><td style="text-align:right"><strong>${w.total_credit}</strong></td></tr></tfoot></table>
    </div>`);
  }

  function comptaCloseEcriture(btn) {
    const card = btn.closest(".card");
    if (card) card.remove();
  }

  async function comptaDeleteEcriture(id) {
    if (!confirm("Supprimer cette pièce et ses lignes ?")) return;
    try {
      await api("/api/client/comptabilite", { method: "DELETE", body: JSON.stringify({ kind: "ecriture", id }) });
      await refreshCompta();
    } catch (e) {
      showAlert("dashboard-alert", "error", e.message);
    }
  }

  async function comptaEcritureForm() {
    const slot = document.getElementById("compta-ecriture-form");
    if (!slot) return;
    const compteOpts = `<option value="">— Compte —</option>` + leafComptes.map((c) => `<option value="${c.id}">${c.numero} — ${escapeHtml(c.intitule)}</option>`).join("");
    slot.innerHTML = `<div class="card explorer-form">
      <h4 style="margin:0 0 10px">Nouvelle pièce comptable</h4>
      <form id="compta-ecriture-form-f" class="form-grid" style="margin:0">
        <div class="form-group"><label>Journal *</label><select name="journal">
          <option value="od">Opérations diverses (OD)</option>
          <option value="ventes">Ventes</option>
          <option value="achats">Achats</option>
          <option value="banque">Banque</option>
          <option value="caisse">Caisse</option>
        </select></div>
        <div class="form-group"><label>N° pièce *</label><input name="numero_piece" type="text" required /></div>
        <div class="form-group"><label>Date *</label><input name="date" type="date" required value="${new Date().toISOString().slice(0, 10)}" /></div>
        <div class="form-group full"><label>Libellé *</label><input name="libelle" type="text" required /></div>
        <div class="form-group full"><label>Lignes d'écriture (le total débit doit être égal au total crédit)</label>
          <table class="admin-table" id="compta-lignes"><thead><tr><th>Compte</th><th>Libellé</th><th>Débit</th><th>Crédit</th><th></th></tr></thead><tbody></tbody></table>
        </div>
        <div class="form-group full" style="display:flex;gap:8px;align-items:center">
          <button class="btn btn-sm btn-outline" type="button" onclick="BalanceEntrep.comptaAddEcritureLine()">＋ Ajouter une ligne</button>
          <span class="muted-sm">Total débit : <strong id="compta-total-debit">0.000</strong> — Total crédit : <strong id="compta-total-credit">0.000</strong></span>
        </div>
        <div class="form-group full" style="display:flex;gap:8px">
          <button class="btn" type="submit">Enregistrer la pièce</button>
          <button class="btn btn-outline" type="button" onclick="BalanceEntrep.comptaEcritureFormCancel()">Annuler</button>
        </div>
      </form>
    </div>`;
    slot.querySelector("#compta-ecriture-form-f").addEventListener("submit", (e) => {
      e.preventDefault();
      comptaSaveEcriture();
    });
    comptaAddEcritureLine();
    comptaAddEcritureLine();
  }

  function comptaAddEcritureLine() {
    const tbody = document.querySelector("#compta-lignes tbody");
    if (!tbody) return;
    const compteOpts = `<option value="">— Compte —</option>` + leafComptes.map((c) => `<option value="${c.id}">${c.numero} — ${escapeHtml(c.intitule)}</option>`).join("");
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><select class="compta-ligne-compte">${compteOpts}</select></td>
      <td><input class="compta-ligne-libelle" type="text" style="min-width:160px" /></td>
      <td><input class="compta-ligne-debit" type="number" step="0.001" min="0" value="0" style="width:110px" oninput="BalanceEntrep.comptaUpdateTotaux()" /></td>
      <td><input class="compta-ligne-credit" type="number" step="0.001" min="0" value="0" style="width:110px" oninput="BalanceEntrep.comptaUpdateTotaux()" /></td>
      <td><button class="btn btn-sm btn-danger" type="button" onclick="BalanceEntrep.comptaRemoveLigne(this)">✕</button></td>`;
    tbody.appendChild(tr);
    comptaUpdateTotaux();
  }

  function comptaRemoveLigne(btn) {
    const tr = btn.closest("tr");
    if (tr && document.querySelectorAll("#compta-lignes tbody tr").length > 1) {
      tr.remove();
      comptaUpdateTotaux();
    }
  }

  function comptaUpdateTotaux() {
    const rows = document.querySelectorAll("#compta-lignes tbody tr");
    let d = 0, c = 0;
    rows.forEach((tr) => {
      d += parseFloat(tr.querySelector(".compta-ligne-debit").value) || 0;
      c += parseFloat(tr.querySelector(".compta-ligne-credit").value) || 0;
    });
    const dl = document.getElementById("compta-total-debit");
    const cl = document.getElementById("compta-total-credit");
    if (dl) dl.textContent = d.toFixed(3);
    if (cl) cl.textContent = c.toFixed(3);
    if (dl && cl) {
      const ok = Math.abs(d - c) < 0.001;
      dl.closest("span").style.color = ok ? "" : "#c0392b";
      cl.closest("span").style.color = ok ? "" : "#c0392b";
    }
  }

  async function comptaSaveEcriture() {
    const rows = document.querySelectorAll("#compta-lignes tbody tr");
    const lignes = [];
    for (const tr of rows) {
      const compte = tr.querySelector(".compta-ligne-compte").value;
      if (!compte) continue;
      lignes.push({
        compte: parseInt(compte, 10),
        libelle: tr.querySelector(".compta-ligne-libelle").value,
        debit: tr.querySelector(".compta-ligne-debit").value,
        credit: tr.querySelector(".compta-ligne-credit").value,
      });
    }
    const fd = new FormData(document.getElementById("compta-ecriture-form-f"));
    try {
      await api("/api/client/comptabilite", {
        method: "POST",
        body: JSON.stringify({
          action: "ecriture_create",
          journal: fd.get("journal"),
          numero_piece: fd.get("numero_piece"),
          date: fd.get("date"),
          libelle: fd.get("libelle"),
          statut: "brouillon",
          lignes,
        }),
      });
      document.getElementById("compta-ecriture-form").innerHTML = "";
      await refreshCompta();
    } catch (e) {
      showAlert("dashboard-alert", "error", e.message);
    }
  }

  function comptaEcritureFormCancel() {
    const slot = document.getElementById("compta-ecriture-form");
    if (slot) slot.innerHTML = "";
  }

  // Grand livre / Balance

  function renderGrandLivre() {
    const body = document.getElementById("compta-body");
    const gl = comptaData.grand_livre || {};
    const comptes = gl.comptes || [];
    body.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px">
        <strong>Grand livre / Balance</strong>
      </div>
      <table class="admin-table"><thead><tr><th>Compte</th><th>Intitulé</th><th>Débit</th><th>Crédit</th><th>Solde débiteur</th><th>Solde créditeur</th></tr></thead><tbody>
        ${comptes.map((c) => `<tr>
          <td><strong>${escapeHtml(c.numero)}</strong></td>
          <td>${escapeHtml(c.intitule)}</td>
          <td>${c.debit}</td>
          <td>${c.credit}</td>
          <td>${c.solde_debiteur}</td>
          <td>${c.solde_crediteur}</td>
        </tr>`).join("") || '<tr><td colspan="6"><p class="muted-sm">Aucun mouvement validé.</p></td></tr>'}
      </tbody><tfoot><tr><td colspan="2"><strong>Totaux</strong></td>
        <td><strong>${gl.total_debit || "0.000"}</strong></td>
        <td><strong>${gl.total_credit || "0.000"}</strong></td>
        <td colspan="2"></td></tr></tfoot></table>
      <h4 style="margin:16px 0 8px">Détail des mouvements (${(gl.mouvements || []).length})</h4>
      <table class="admin-table"><thead><tr><th>Date</th><th>Pièce</th><th>Compte</th><th>Libellé</th><th>Débit</th><th>Crédit</th></tr></thead><tbody>
        ${(gl.mouvements || []).map((m) => `<tr>
          <td>${m.date}</td><td>${escapeHtml(m.piece)}</td>
          <td><strong>${escapeHtml(m.numero)}</strong></td>
          <td>${escapeHtml(m.libelle)}</td>
          <td>${m.debit}</td><td>${m.credit}</td>
        </tr>`).join("") || '<tr><td colspan="6"><p class="muted-sm">Aucun mouvement.</p></td></tr>'}
      </tbody></table>`;
  }

  // Bilan & résultat

  function renderBilan() {
    const body = document.getElementById("compta-body");
    const bilanData = comptaData.bilan || {};
    const bl = bilanData.bilan || {};
    const res = bilanData.resultat || {};
    const srows = (detail) => (detail || []).map((d) => `<tr><td>${escapeHtml(d.numero)}</td><td>${escapeHtml(d.intitule)}</td><td style="text-align:right">${d.montant}</td></tr>`).join("");
    const section = (label, sec) => `
      <div class="card"><h4 style="margin:0 0 8px">${escapeHtml(label)}</h4>
        <table class="admin-table"><tbody>
          ${srows(sec.detail)}
          ${(sec.detail && sec.detail.length) ? "" : '<tr><td colspan="3"><span class="muted-sm">—</span></td></tr>'}
        </tbody><tfoot><tr><td colspan="2"><strong>Total</strong></td><td style="text-align:right"><strong>${sec.total}</strong></td></tr></tfoot></table>
      </div>`;
    body.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px">
        <strong>Bilan & résultat</strong>
      </div>
      <div class="grid-2" style="gap:16px">
        <div>
          <h4>Actif</h4>
          ${(bl.actif || []).map((a) => section(a.label, a)).join("")}
        </div>
        <div>
          <h4>Passif</h4>
          ${(bl.passif || []).map((a) => section(a.label, a)).join("")}
        </div>
      </div>
      <div class="card" style="margin-top:14px">
        <h4 style="margin:0 0 8px">Total bilan</h4>
        <p style="margin:0"><strong>Actif :</strong> ${bl.total_actif || "0.000"} TND &nbsp;·&nbsp; <strong>Passif :</strong> ${bl.total_passif || "0.000"} TND</p>
      </div>
      <div class="grid-2" style="gap:16px;margin-top:16px">
        <div>${section("Charges (classe 6)", res.charges || { total: "0.000" })}</div>
        <div>${section("Produits (classe 7)", res.produits || { total: "0.000" })}</div>
      </div>
      <div class="card" style="margin-top:14px">
        <h4 style="margin:0 0 8px">Résultat de l'exercice</h4>
        <p style="margin:0"><strong>${res.resultat || "0.000"} TND</strong></p>
      </div>`;
  }

  // ---------------- Dossiers & suivi (rappel) ----------------

  async function loadDossiers() {
    const wrap = document.getElementById("dossiers-content");
    wrap.innerHTML = `<p>Chargement…</p>`;
    try {
      const [compta, dash] = await Promise.all([
        api("/api/client/comptabilite"),
        api("/api/client/dashboard"),
      ]);
      const ent = compta.entreprise;
      renderDossiers(wrap, ent, dash);
    } catch (e) {
      wrap.innerHTML = `<div class="alert show alert-error">${escapeHtml(e.message)}</div>`;
    }
  }

  function renderDossiers(wrap, ent, dash) {
    const suivis = dash.suivis || [];
    const declarations = dash.declarations || [];
    const cards = suivis.map((s) => {
      const badge = s.statut_service === "Clôturé" ? "badge confirme" : "badge nouveau";
      const pay = s.statut_paiement === "Payé" ? "badge confirme" : "badge nouveau";
      const tasks = (s.tasks || []).length
        ? `<ul class="task-list">${s.tasks.map((t) => `<li><span class="badge ${t.statut === "Terminé" ? "confirme" : "nouveau"}">${t.statut}</span> ${escapeHtml(t.titre)} — <small>${t.date_echeance} · ${t.repetition}</small></li>`).join("")}</ul>`
        : '<p class="muted-sm">Aucune tâche définie pour ce dossier.</p>';
      const serviceSuivis = (s.service_followups || []).length
        ? `<ul class="task-list">${s.service_followups.map((sf) => `<li><span class="badge ${sf.status === "Terminé" || sf.status === "Clôturé" ? "confirme" : "nouveau"}">${sf.status}</span> ${escapeHtml(sf.service)} — <small>du ${sf.start_date} au ${sf.due_date}</small></li>`).join("")}</ul>`
        : "";
      const prefactures = (s.prefactures || []).length
        ? `<p class="muted-sm">Préfactures : ${s.prefactures.map((p) => `<a href="#" onclick="event.preventDefault();BalanceEntrep.showPrefacture(${p.id})">${escapeHtml(p.numero)}</a> <span class="badge ${p.statut === "Payée" ? "confirme" : "nouveau"}">${p.statut}</span>`).join(" · ")}</p>`
        : "";
      const attachments = (s.attachments || []).length
        ? `<ul class="att-list">${s.attachments.map((a) => `<li><span class="att-ico att-${a.category}">${a.category}</span> <a href="${a.url}" target="_blank" rel="noopener">${escapeHtml(a.name)}</a> <small>(${a.size} · ${a.uploaded_by})</small></li>`).join("")}</ul>`
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
        ${serviceSuivis ? `<div class="dossier-block"><strong>Suivi du service</strong>${serviceSuivis}</div>` : ""}
        <div class="dossier-block"><strong>Tâches</strong>${tasks}</div>
        ${prefactures}
        <div class="dossier-block"><strong>Pièces jointes</strong>${attachments || '<p class="muted-sm">Aucune pièce jointe.</p>'}</div>
      </div>`;
    }).join("");

    const statutBadge = (s) => {
      const map = { "Déposé (Validé)": "confirme", "En retard": "annule", "En cours de vérification": "nouveau" };
      return `badge ${map[s] || "nouveau"}`;
    };
    const declRows = declarations.map((d) => {
      const paye = parseFloat(d.montant_a_payer);
      return `<tr>
        <td>${d.type_declaration}</td>
        <td>${escapeHtml(d.periode)}</td>
        <td>${d.date_echeance_legale}</td>
        <td><span class="${statutBadge(d.statut)}">${d.statut}</span></td>
        <td>${paye > 0 ? paye.toFixed(3) + " TND" : "0,00 TND"}</td>
        <td>${escapeHtml(d.numero_quittance_ou_tej)}</td>
      </tr>`;
    }).join("");

    wrap.innerHTML = `
      <div class="card" style="margin-bottom:16px">
        <h3 style="margin:0">${escapeHtml(ent.raison_sociale)}</h3>
        <p class="muted-sm" style="margin:6px 0 0">${[ent.forme_juridique, ent.matricule_fiscale, ent.registre_commerce, ent.ville, ent.email, ent.telephone].filter(Boolean).join(" · ")}</p>
      </div>
      <h3>Mes dossiers et services</h3>
      <p class="muted-sm">Suivi des dossiers gérés par votre cabinet (rappel).</p>
      ${suivis.length ? cards : '<p style="color:#64748b">Aucun dossier en cours pour le moment.</p>'}
      ${declarations.length ? `<div class="card" style="margin-top:20px">
        <h3>Mes déclarations fiscales</h3>
        <table class="admin-table">
          <thead><tr><th>Type</th><th>Période</th><th>Échéance légale</th><th>Statut</th><th>Montant à payer</th><th>N° quittance / TEJ</th></tr></thead>
          <tbody>${declRows}</tbody>
        </table>
      </div>` : ""}`;
  }

  // Préfacture (rappel)

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

  function init() {
    document.getElementById("login-form").addEventListener("submit", login);
    document.getElementById("register-form").addEventListener("submit", register);
    if (token()) {
      api("/api/client/dashboard")
        .then((d) => showDashboard(d.client))
        .catch(() => {});
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  return {
    init,
    logout,
    showTab,
    refreshCompta,
    comptaSubView,
    comptaAddCompte,
    comptaEditCompte,
    comptaCompteFormCancel,
    comptaDeleteCompte,
    comptaEcritureStatut,
    comptaEcritureForm,
    comptaEcritureFormCancel,
    comptaAddEcritureLine,
    comptaRemoveLigne,
    comptaUpdateTotaux,
    comptaVoirEcriture,
    comptaCloseEcriture,
    comptaDeleteEcriture,
    showPrefacture,
    closePrefacture,
    printPrefacture,
  };
})();
