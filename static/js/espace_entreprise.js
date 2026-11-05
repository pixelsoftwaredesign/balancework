const BalanceEntrep = (() => {
  const API_BASE = window.BALANCEWORK_API || "";
  const TOKEN_KEY = "bts_client_token";

  let comptaData = null;
  let comptaSub = "plan";
  let leafComptes = [];
  let facturesData = null;
  let tejData = null;

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
    const tabs = {
      compta: ["compta-content", "tab-compta"],
      factures: ["factures-content", "tab-factures"],
      tej: ["tej-content", "tab-tej"],
      dossiers: ["dossiers-content", "tab-dossiers"],
    };
    Object.keys(tabs).forEach((key) => {
      const [boxId, btnId] = tabs[key];
      const box = document.getElementById(boxId);
      const btn = document.getElementById(btnId);
      const active = key === tab;
      if (box) box.style.display = active ? "" : "none";
      if (btn) btn.className = active ? "btn btn-sm" : "btn btn-sm btn-outline";
    });
    if (tab === "compta") loadCompta();
    else if (tab === "factures") loadFactures();
    else if (tab === "tej") loadTej();
    else loadDossiers();
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

  // ---------------- Facturation tenant ----------------

  const TAUX_RS_JS = { acquisition: 1, honoraires_reel: 3, honoraires_forfait: 10, loyer: 10, dividendes: 10, cession: 5, non_resident: 10 };
  const TIMBRE_JS = 1;
  const SEUIL_JS = 1000;

  async function loadFactures() {
    const wrap = document.getElementById("factures-content");
    try {
      facturesData = await api("/api/client/factures");
    } catch (e) {
      wrap.innerHTML = `<div class="alert show alert-error">${escapeHtml(e.message)}</div>`;
      return;
    }
    const items = facturesData.factures || [];
    wrap.innerHTML = `
      <div class="card" style="margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
          <div>
            <h3 style="margin:0">Facturation</h3>
            <p class="muted-sm" style="margin:6px 0 0">Ventes et achats avec TVA, droit de timbre (1 TND ≥ 1 000 TND TTC) et retenue à la source. ${items.length} facture(s).</p>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-sm" onclick="BalanceEntrep.factureForm('vente')">＋ Facture de vente</button>
            <button class="btn btn-sm btn-outline" onclick="BalanceEntrep.factureForm('achat')">＋ Facture d'achat</button>
            <button class="btn btn-sm btn-outline" onclick="BalanceEntrep.loadFactures()">⟳ Recharger</button>
            <button class="btn btn-sm btn-outline" onclick="BalanceEntrep.facturesExportExcel()">⬇ Export Excel</button>
          </div>
        </div>
      </div>
      <div id="facture-form"></div>
      <table class="admin-table"><thead><tr>
        <th>N°</th><th>Type</th><th>Date</th><th>Tiers</th><th>Nature</th>
        <th>HT</th><th>TVA</th><th>TTC</th><th>Timbre</th><th>Retenue</th><th>Net</th><th>Statut</th><th></th>
      </tr></thead><tbody>
        ${items.map((f) => factureRow(f)).join("") || '<tr><td colspan="13"><p class="muted-sm">Aucune facture.</p></td></tr>'}
      </tbody></table>`;
  }

  function factureRow(f) {
    const badge = f.statut === "valide" ? "confirme" : f.statut === "annulee" ? "annule" : "nouveau";
    const ecr = f.ecriture_id ? ` <span class="badge confirme">Écriture N°${f.ecriture_id}</span>` : "";
    const rsBadge = parseFloat(f.retenue_source_montant) > 0 ? ` (${f.retenue_source_taux} %)` : "";
    return `<tr>
      <td><strong>${escapeHtml(f.numero)}</strong>${ecr}</td>
      <td>${f.type_facture === "vente" ? "Vente" : "Achat"}</td>
      <td>${f.date}</td>
      <td>${escapeHtml(f.tiers)}<br><span class="muted-sm">${escapeHtml(f.tiers_identifiant || "—")}</span></td>
      <td>${f.type_facture === "achat" ? escapeHtml(f.nature_label) : "—"}</td>
      <td>${f.montant_ht}</td>
      <td>${f.montant_tva}</td>
      <td><strong>${f.montant_ttc}</strong></td>
      <td>${f.timbre_fiscal}</td>
      <td>${f.retenue_source_montant}${rsBadge}</td>
      <td><strong>${f.net_a_payer}</strong></td>
      <td>
        <select class="status-select" onchange="BalanceEntrep.factureStatut(${f.id}, this.value)">
          <option value="brouillon" ${f.statut === "brouillon" ? "selected" : ""}>Brouillon</option>
          <option value="valide" ${f.statut === "valide" ? "selected" : ""}>Validée</option>
          <option value="annulee" ${f.statut === "annulee" ? "selected" : ""}>Annulée</option>
        </select>
      </td>
      <td>
        <button class="btn btn-sm btn-danger" onclick="BalanceEntrep.factureDelete(${f.id})">Supprimer</button>
      </td>
    </tr>`;
  }

  function factureForm(type) {
    const slot = document.getElementById("facture-form");
    if (!slot) return;
    slot.innerHTML = `<div class="card explorer-form">
      <h4 style="margin:0 0 10px">${type === "vente" ? "Nouvelle facture de vente" : "Nouvelle facture d'achat"}</h4>
      <form id="facture-form-f" class="form-grid" style="margin:0">
        <input type="hidden" name="type_facture" value="${type}" />
        <div class="form-group"><label>N° facture *</label><input name="numero" type="text" required /></div>
        <div class="form-group"><label>Date *</label><input name="date" type="date" required value="${new Date().toISOString().slice(0, 10)}" /></div>
        <div class="form-group full"><label>Tiers (raison sociale / nom) *</label><input name="tiers" type="text" required /></div>
        <div class="form-group"><label>Type d'identifiant fiscal</label>
          <select name="tiers_identifiant_type">
            <option value="matricule">Matricule fiscal</option>
            <option value="cin">CIN</option>
            <option value="passeport">Passeport</option>
            <option value="cartesejour">Carte de séjour</option>
          </select>
        </div>
        <div class="form-group"><label>Numéro d'identifiant</label><input name="tiers_identifiant" type="text" placeholder="Ex : 1234567A" /></div>
        ${type === "achat" ? `<div class="form-group full"><label>Nature de l'opération (retenue à la source)</label>
          <select name="nature_operation" onchange="BalanceEntrep.facturePreview()">
            <option value="acquisition">Acquisition de biens/services (≥ 1 000 TND TTC)</option>
            <option value="honoraires_reel">Honoraires — régime réel (3 %)</option>
            <option value="honoraires_forfait">Honoraires forfait / commissions (10 %)</option>
            <option value="loyer">Loyers (10 %)</option>
            <option value="dividendes">Dividendes (10 %)</option>
            <option value="cession">Cession de valeurs mobilières / immeubles (2,5-15 %)</option>
            <option value="non_resident">Non-résidents (5-25 %)</option>
          </select>
        </div>` : ""}
        ${type === "achat" ? `<div class="form-group"><label>Taux de retenue à la source (%)</label><input name="retenue_source_taux" type="number" step="0.01" min="0" max="100" placeholder="Auto selon nature" oninput="BalanceEntrep.facturePreview()" /></div>` : ""}
        <div class="form-group"><label>Montant HT (TND) *</label><input name="montant_ht" type="number" step="0.001" min="0.001" required oninput="BalanceEntrep.facturePreview()" /></div>
        <div class="form-group"><label>Taux de TVA</label>
          <select name="taux_tva" onchange="BalanceEntrep.facturePreview()">
            <option value="19">19 %</option>
            <option value="13">13 %</option>
            <option value="7">7 %</option>
            <option value="0">0 % (exonérée)</option>
          </select>
        </div>
        <div class="form-group full"><div id="facture-preview" class="muted-sm"></div></div>
        <div class="form-group full" style="display:flex;gap:8px">
          <button class="btn" type="submit">Enregistrer (brouillon)</button>
          <button class="btn btn-outline" type="button" onclick="BalanceEntrep.factureFormCancel()">Annuler</button>
        </div>
      </form>
    </div>`;
    slot.querySelector("#facture-form-f").addEventListener("submit", (e) => {
      e.preventDefault();
      factureSave();
    });
    facturePreview();
  }

  function factureFormCancel() {
    const slot = document.getElementById("facture-form");
    if (slot) slot.innerHTML = "";
  }

  function facturePreview() {
    const el = document.getElementById("facture-preview");
    const form = document.getElementById("facture-form-f");
    if (!el || !form) return;
    const ht = parseFloat(form.montant_ht.value) || 0;
    const tva = (ht * (parseFloat(form.taux_tva.value) || 0)) / 100;
    const ttc = ht + tva;
    const timbre = ttc >= SEUIL_JS ? TIMBRE_JS : 0;
    let rs = 0;
    let taux = 0;
    if (form.type_facture.value === "achat") {
      const manual = parseFloat(form.retenue_source_taux && form.retenue_source_taux.value);
      if (!isNaN(manual) && manual >= 0) {
        taux = manual;
      } else {
        taux = TAUX_RS_JS[form.nature_operation.value] || 0;
        if (form.nature_operation.value === "acquisition" && ttc < SEUIL_JS) taux = 0;
      }
      if (taux > 0) rs = ((ttc - timbre) * taux) / 100;
    }
    const net = ttc - rs;
    el.innerHTML = `Aperçu : HT <strong>${ht.toFixed(3)}</strong> + TVA <strong>${tva.toFixed(3)}</strong> = TTC <strong>${ttc.toFixed(3)}</strong> · Timbre <strong>${timbre.toFixed(3)}</strong>${form.type_facture.value === "achat" ? ` · Retenue <strong>${rs.toFixed(3)}</strong> (${taux} %)` : ""} · Net <strong>${net.toFixed(3)}</strong>`;
  }

  async function factureSave() {
    const form = document.getElementById("facture-form-f");
    if (!form) return;
    const payload = {
      action: "facture_create",
      type_facture: form.type_facture.value,
      numero: form.numero.value.trim(),
      date: form.date.value,
      tiers: form.tiers.value.trim(),
      tiers_identifiant_type: form.tiers_identifiant_type.value,
      tiers_identifiant: form.tiers_identifiant.value.trim(),
      montant_ht: form.montant_ht.value,
      taux_tva: form.taux_tva.value,
    };
    if (form.type_facture.value === "achat") {
      payload.nature_operation = form.nature_operation.value;
      if (form.retenue_source_taux && form.retenue_source_taux.value.trim() !== "") {
        payload.retenue_source_taux = form.retenue_source_taux.value.trim();
      }
    }
    try {
      await api("/api/client/factures", { method: "POST", body: JSON.stringify(payload) });
      factureFormCancel();
      await loadFactures();
    } catch (e) {
      showAlert("dashboard-alert", "error", e.message);
    }
  }

  async function factureStatut(id, statut) {
    try {
      await api("/api/client/factures", { method: "POST", body: JSON.stringify({ action: "facture_statut", id, statut }) });
      tejData = null;
      await loadFactures();
    } catch (e) {
      showAlert("dashboard-alert", "error", e.message);
      await loadFactures();
    }
  }

  async function factureDelete(id) {
    if (!confirm("Supprimer cette facture (et son écriture si générée) ?")) return;
    try {
      await api("/api/client/factures", { method: "POST", body: JSON.stringify({ action: "facture_delete", id }) });
      await loadFactures();
    } catch (e) {
      showAlert("dashboard-alert", "error", e.message);
    }
  }

  // ---------------- TEJ : retenue à la source ----------------

  async function apiNoThrow(path, options = {}) {
    const res = await fetch(API_BASE + path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
        ...(options.headers || {}),
      },
    });
    const data = await res.json().catch(() => ({}));
    return { status: res.status, data };
  }

  async function loadTej() {
    const wrap = document.getElementById("tej-content");
    wrap.innerHTML = `
      <div class="card" style="margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
          <div>
            <h3 style="margin:0">TEJ — Retenue à la source (tej.finances.gov.tn)</h3>
            <p class="muted-sm" style="margin:6px 0 12px">Export mensuel <strong>CCT-RS-V2</strong> des certificats de retenue à la source opérés sur vos factures d'achat <strong>validées</strong>. Base de calcul : (TTC − timbre) × taux, jamais le HT. Seuil : 1 000 TND TTC par opération (acquisitions). Déclaration avant le <strong>28 du mois suivant</strong>.</p>
          </div>
          <button class="btn btn-sm btn-outline" onclick="BalanceEntrep.loadTej()">⟳ Recharger</button>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
          <label style="font-weight:600">Mois de déclaration</label>
          <input type="month" id="tej-mois" value="${new Date().toISOString().slice(0, 7)}" style="padding:6px" />
          <button class="btn btn-sm" onclick="BalanceEntrep.tejCheck()">Vérifier la conformité</button>
          <button class="btn btn-sm btn-outline" onclick="BalanceEntrep.tejExport()">⬇ Exporter le XML TEJ</button>
          <button class="btn btn-sm btn-outline" onclick="BalanceEntrep.tejExportExcel()">⬇ Exporter Excel TEJ</button>
        </div>
      </div>
      <div id="tej-result"><p class="muted-sm">Sélectionnez un mois puis vérifiez la conformité des factures avant export.</p></div>`;
  }

  async function tejCheck() {
    const mois = document.getElementById("tej-mois").value;
    const result = document.getElementById("tej-result");
    if (!mois) return;
    result.innerHTML = `<p>Vérification…</p>`;
    const { status, data } = await apiNoThrow(`/api/client/tej?mois=${mois}`);
    tejData = status === 200 ? data : null;
    renderTej(status, data);
  }

  function renderTej(status, data) {
    const result = document.getElementById("tej-result");
    if (!result) return;
    if (status === 400 && data && data.controles) {
      const points = (data.controles || []).flatMap((c) => (c.points || []).map((p) => ({ ...p, numero: c.numero, tiers: c.tiers })));
      const erreurs = points.filter((p) => p.niveau === "erreur");
      const avertis = points.filter((p) => p.niveau === "avertissement");
      result.innerHTML = `
        <div class="alert show ${erreurs.length ? "alert-error" : "alert-success"}">
          ${erreurs.length ? `${erreurs.length} erreur(s) bloquante(s)` : "Aucune erreur bloquante"} · ${avertis.length} avertissement(s).
        </div>
        ${points.length ? `<div class="card"><strong>Contrôles de conformité</strong><ul style="margin:8px 0 0;padding-left:18px">${points.map((p) => `<li style="color:${p.niveau === "erreur" ? "#991b1b" : "#92400e"}">${p.niveau === "erreur" ? "✗" : "⚠"} ${escapeHtml(p.numero)} — ${escapeHtml(p.tiers)} : ${escapeHtml(p.message)}</li>`).join("")}</ul></div>` : ""}`;
      return;
    }
    if (status !== 200) {
      result.innerHTML = `<div class="alert show alert-error">${escapeHtml((data && data.error) || "Erreur")}</div>`;
      return;
    }
    const t = data.totaux || {};
    const certs = data.certificats || [];
    const erreurs = (data.controles || []).flatMap((c) => (c.points || []).filter((p) => p.niveau === "erreur"));
    result.innerHTML = `
      <div class="alert show alert-success" style="margin-bottom:12px">Déclaration conforme TEJ (CCT-RS-V2) — ${String(data.mois).padStart(2, "0")}/${data.annee} · Déclarant : ${escapeHtml(data.declarant)}.</div>
      ${erreurs.length ? `<div class="alert show alert-error">${erreurs.length} erreur(s) bloquante(s) signalée(s).</div>` : ""}
      <div class="card" style="margin-bottom:12px">
        <strong>Totaux de la déclaration</strong>
        <table class="admin-table" style="margin-top:8px">
          <tbody>
            <tr><td>Certificats</td><td><strong>${t.nb_certificats}</strong></td><td>Opérations</td><td><strong>${t.nb_operations}</strong></td></tr>
            <tr><td>Total TTC</td><td><strong>${t.total_ttc}</strong> TND</td><td>Total retenue</td><td><strong>${t.total_retenue}</strong> TND</td></tr>
            <tr><td>Total timbre</td><td>${t.total_timbre} TND</td><td>Total net servi</td><td>${t.total_net} TND</td></tr>
          </tbody>
        </table>
      </div>
      <div class="card">
        <strong>Certificats par bénéficiaire</strong>
        ${certs.map((c) => `
          <div style="margin:10px 0;border-top:1px solid #e2e8f0;padding-top:8px">
            <p style="margin:0"><strong>${escapeHtml(c.tiers)}</strong> — ${escapeHtml(c.identifiant_type)} : ${escapeHtml(c.identifiant)} (${c.operations.length} opération(s))</p>
            <table class="admin-table" style="margin-top:6px"><thead><tr><th>N°</th><th>Date paiement</th><th>HT</th><th>TTC</th><th>Retenue</th><th>Net servi</th></tr></thead><tbody>
              ${(c.operations || []).map((o) => `<tr><td>${escapeHtml(o.numero)}</td><td>${o.date}</td><td>${o.montant_ht}</td><td>${o.montant_ttc}</td><td><strong>${o.montant_rs}</strong></td><td>${o.montant_net_servi}</td></tr>`).join("")}
            </tbody></table>
            <p class="muted-sm" style="margin:4px 0 0">Référence certificat : ${escapeHtml((c.operations[0] || {}).ref)}</p>
          </div>`).join("") || '<p class="muted-sm">Aucun certificat.</p>'}
      </div>`;
  }

  async function tejExport() {
    const mois = document.getElementById("tej-mois").value;
    if (!mois) return;
    let data = tejData;
    const monthNum = parseInt(mois.slice(5), 10);
    if (!data || data.mois !== monthNum) {
      const { status, data: d } = await apiNoThrow(`/api/client/tej?mois=${mois}`);
      if (status !== 200) {
        showAlert("dashboard-alert", "error", d.error || "Export impossible");
        renderTej(status, d);
        return;
      }
      data = d;
    }
    const blob = new Blob([data.xml], { type: "application/xml;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `TEJ_RS_${mois}_${(data.declarant || "entreprise").replace(/[^a-zA-Z0-9]+/g, "_").slice(0, 30)}.xml`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function facturesExportExcel() {
    const url = API_BASE + "/api/client/factures/export";
    const res = await fetch(url, { headers: { ...(token() ? { Authorization: `Bearer ${token()}` } : {}) } });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      showAlert("dashboard-alert", "error", data.error || "Export impossible");
      return;
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "factures.xlsx";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function tejExportExcel() {
    const mois = document.getElementById("tej-mois").value;
    if (!mois) return;
    const url = API_BASE + `/api/client/tej/export?mois=${mois}`;
    const res = await fetch(url, { headers: { ...(token() ? { Authorization: `Bearer ${token()}` } : {}) } });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      showAlert("dashboard-alert", "error", data.error || "Export impossible");
      renderTej(res.status, data);
      return;
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `TEJ_RS_${mois}.xlsx`;
    a.click();
    URL.revokeObjectURL(a.href);
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
    loadFactures,
    factureForm,
    factureFormCancel,
    facturePreview,
    factureStatut,
    factureDelete,
    loadTej,
    tejCheck,
    tejExport,
    facturesExportExcel,
    tejExportExcel,
    showPrefacture,
    closePrefacture,
    printPrefacture,
  };
})();
