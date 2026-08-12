const API_BASE = window.BALANCEWORK_API || "";

const SITE = {
  name: "Balance And Tax Safety",
  phone: "+216 97 903 529",
  email: "contact@balancework.tn",
};

const NAV_LINKS = [
  { href: "/", label: "Accueil" },
  { href: "/services/", label: "Services" },
  { href: "/devis/", label: "Devis" },
  { href: "/rendezvous/", label: "Rendez-vous" },
  { href: "/espace-client/", label: "Espace client" },
  { href: "/espace-entreprise/", label: "Espace entreprise" },
  { href: "/contact/", label: "Contact" },
];

const FOOTER_LINKS = [
  { href: "/services/", label: "Nos services" },
  { href: "/devis/", label: "Demander un devis" },
  { href: "/rendezvous/", label: "Prendre rendez-vous" },
  { href: "/espace-client/", label: "Espace client" },
  { href: "/espace-entreprise/", label: "Espace entreprise" },
  { href: "/contact/", label: "Nous contacter" },
  { href: "/gestion/", label: "Espace admin" },
];

document.addEventListener("DOMContentLoaded", () => {
  injectHeader();
  injectFooter();
  setupMobileNav();
  setupForms();
  initServiceSelects();
});

function injectHeader() {
  const slot = document.getElementById("site-header");
  if (!slot) return;
  const current = location.pathname.replace(/\/$/, "");
  const links = NAV_LINKS.map(
    (l) =>
      `<a href="${l.href}" ${current === l.href.replace(/\/$/, "") ? 'style="background:var(--primary-light)"' : ""}>${l.label}</a>`,
  ).join("");
  slot.innerHTML = `
    <nav class="site-nav">
      <div class="site-nav-inner">
        <a class="brand" href="/">
          <span class="brand-mark">BT</span>
          <span>Balance And Tax Safety</span>
        </a>
        <button class="nav-toggle" aria-label="Menu">☰</button>
        <div class="nav-links" id="nav-links">
          ${links}
          <a class="nav-cta" href="/devis/">Demander un devis</a>
        </div>
      </div>
    </nav>`;
}

function injectFooter() {
  const slot = document.getElementById("site-footer");
  if (!slot) return;
  const links = FOOTER_LINKS.map((l) => `<a href="${l.href}">${l.label}</a>`).join("");
  slot.innerHTML = `
    <footer class="site-footer">
      <div class="footer-grid">
        <div>
          <h4>${SITE.name}</h4>
          <p>Cabinet de conseil fiscal, gestion et études de projets en Tunisie : conseil fiscal, déclarations, paie, sécurité sociale et facturation électronique TEJ.</p>
        </div>
        <div>
          <h4>Navigation</h4>
          ${links}
        </div>
        <div>
          <h4>Contact</h4>
          <p>Téléphone : <a href="tel:${SITE.phone.replace(/\s/g, "")}">${SITE.phone}</a></p>
          <p>Email : <a href="mailto:${SITE.email}">${SITE.email}</a></p>
          <p>Rue Allala El Fessi, El Hamma, Gabès, Tunisie</p>
        </div>
      </div>
      <div class="footer-bottom">© ${new Date().getFullYear()} ${SITE.name} — Tunis, Tunisie. Tous droits réservés. — <a href="https://pixelsoftwaredesign.xyz" rel="noopener" target="_blank">PixelSoftwareDesign</a></div>
    </footer>`;
}

function setupMobileNav() {
  const toggle = document.querySelector(".nav-toggle");
  const links = document.getElementById("nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", () => links.classList.toggle("open"));
  }
}

function showAlert(id, type, message) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = `alert show alert-${type}`;
  el.textContent = message;
}

function hideAlert(id) {
  const el = document.getElementById(id);
  if (el) el.className = "alert";
}

async function postForm(formEl, endpoint, alertId) {
  const btn = formEl.querySelector("button[type=submit]");
  hideAlert(alertId);
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = "Envoi en cours…";
  try {
    const data = Object.fromEntries(new FormData(formEl).entries());
    const res = await fetch(API_BASE + endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const result = await res.json();
    if (!res.ok) throw new Error(result.error || "Erreur inconnue");
    showAlert(alertId, "success", result.message);
    formEl.reset();
    if (alertId === "rdv-alert") {
      const slotWrap = document.getElementById("slot-wrap");
      if (slotWrap) slotWrap.innerHTML = '<p class="form-note">Sélectionnez une date pour voir les créneaux disponibles.</p>';
      const date = formEl.querySelector("#rdv-date");
      if (date) date.value = "";
    }
  } catch (err) {
    showAlert(alertId, "error", err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

function setupForms() {
  const contact = document.getElementById("contact-form");
  if (contact) contact.addEventListener("submit", (e) => {
    e.preventDefault();
    postForm(contact, "/api/contact", "contact-alert");
  });

  const devis = document.getElementById("devis-form");
  if (devis) devis.addEventListener("submit", (e) => {
    e.preventDefault();
    postForm(devis, "/api/devis", "devis-alert");
  });

  const rdv = document.getElementById("rendezvous-form");
  if (rdv) {
    const dateInput = rdv.querySelector("#rdv-date");
    const slotWrap = document.getElementById("slot-wrap");
    let selectedSlot = null;

    dateInput.addEventListener("change", async () => {
      const date = dateInput.value;
      if (!date) return;
      selectedSlot = null;
      const slots = await loadSlots(date);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const isToday = new Date(date + "T00:00:00") <= today;
      slotWrap.innerHTML =
        slots.length === 0
          ? '<p class="slot-empty">Aucun créneau disponible cette journée.</p>'
          : `<div class="slot-grid">${slots
              .map((s) => `<button type="button" class="slot" data-slot="${s}" ${isToday ? "disabled" : ""}>${s}</button>`)
              .join("")}</div>`;
      slotWrap.querySelectorAll(".slot").forEach((b) =>
        b.addEventListener("click", () => {
          slotWrap.querySelectorAll(".slot.selected").forEach((x) => x.classList.remove("selected"));
          b.classList.add("selected");
          selectedSlot = b.dataset.slot;
          const hidden = rdv.querySelector("#rdv-time");
          if (hidden) hidden.value = b.dataset.slot;
        }),
      );
    });

    rdv.addEventListener("submit", (e) => {
      e.preventDefault();
      if (!selectedSlot) {
        showAlert("rdv-alert", "error", "Veuillez choisir un créneau horaire.");
        return;
      }
      postForm(rdv, "/api/rendezvous", "rdv-alert");
    });
  }
}

async function loadSlots(date) {
  try {
    const res = await fetch(API_BASE + `/api/availability?date=${date}`);
    const data = await res.json();
    return data.slots || [];
  } catch {
    return [];
  }
}

async function initServiceSelects() {
  const selects = document.querySelectorAll("[data-services]");
  if (!selects.length) return;
  const res = await fetch(API_BASE + "/api/services");
  const data = await res.json();
  const services = data.services || [];
  selects.forEach((sel) => {
    services.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.slug;
      opt.textContent = s.title;
      sel.appendChild(opt);
      (s.subservices || []).forEach((ss) => {
        const sub = document.createElement("option");
        sub.value = ss.slug;
        sub.textContent = s.title + " › " + ss.title;
        sel.appendChild(sub);
      });
    });
  });
}

async function loadServices(targetId) {
  const wrap = document.getElementById(targetId);
  if (!wrap) return;
  const res = await fetch(API_BASE + "/api/services");
  const data = await res.json();
  const icons = { scale: "scale", calculator: "calculator", shield: "shield", briefcase: "briefcase", file: "file", eye: "eye", users: "users", cart: "cart", trending: "trending", link: "link", "user-check": "user-check", rocket: "rocket", target: "target" };
  wrap.innerHTML = (data.services || [])
    .map(
      (s) => `
      <div class="card">
        <div class="feature-icon">${iconSvg(icons[s.icon] || "briefcase")}</div>
        <h3>${s.title}</h3>
        <p>${s.short_desc}</p>
        <p style="font-size:14px">${s.description}</p>
        ${(s.subservices || []).length ? `<ul class="sub-service-list">${s.subservices.map((ss) => `<li><a href="/devis/?service=${ss.slug}">${ss.title}</a> <small>${ss.short_desc}</small></li>`).join("")}</ul>` : ""}
        <a class="btn" href="/devis/?service=${s.slug}">Demander un devis</a>
      </div>`,
    )
    .join("");
}

function iconSvg(name) {
  const paths = {
    scale: '<path d="M12 3v18M8 21h8M12 3L5 8M12 3l7 5M5 8h14v2a3 3 0 01-6 0M9 10a3 3 0 01-6 0M21 10a3 3 0 01-6 0"/>',
    calculator: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h.01M13 12h.01M9 16h.01M13 16h.01M16 16h.01M13 8h3"/>',
    shield: '<path d="M12 22s8-3 8-9V5l-8-3-8 3v8c0 6 8 9 8 9z"/><path d="M9 12l2 2 4-4"/>',
    briefcase: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2M3 12h18"/>',
    file: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M9 13h6M9 17h6"/>',
    eye: '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/>',
    users: '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>',
    cart: '<circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/>',
    trending: '<path d="M23 6l-9.5 9.5-5-5L1 18"/><path d="M17 6h6v6"/>',
    link: '<path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/>',
    "user-check": '<path d="M16 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="8.5" cy="7" r="4"/><path d="M17 11l2 2 4-4"/>',
    rocket: '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 00-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 012-3.95A12.88 12.88 0 0122 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 01-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
    target: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
  };
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths[name] || paths.briefcase}</svg>`;
}

window.BalanceSite = { loadServices };
