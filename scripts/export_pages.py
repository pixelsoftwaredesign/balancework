"""Export statique du site pour Cloudflare Pages.

Rend chaque page Django en HTML statique dans ./pages_build,
pointant l'API vers le backend Railway.
"""
import os
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "balancework.settings")
os.environ["SITE_URL"] = "https://balancetaxsafety.pages.dev/"
os.environ["ALLOWED_HOSTS"] = "testserver,localhost,127.0.0.1"
os.environ["DB_ENGINE"] = "sqlite"
os.environ["DEBUG"] = "1"

import django

django.setup()

from django.test import Client

API_BASE = os.environ.get("PAGES_API_BASE", "https://web-production-18826.up.railway.app")

OUT = BASE_DIR / "pages_build"

PAGES = [
    ("/", "index.html"),
    ("/services/", "services/index.html"),
    ("/devis/", "devis/index.html"),
    ("/contact/", "contact/index.html"),
    ("/rendezvous/", "rendezvous/index.html"),
    ("/gestion/", "gestion/index.html"),
    ("/espace-client/", "espace-client/index.html"),
    ("/espace-entreprise/", "espace-entreprise/index.html"),
]

client = Client()

SERVICE_ICON_PATHS = {
    "scale": '<path d="M12 3v18M8 21h16M12 3L5 8M12 3l7 5M5 8h14v2a3 3 0 01-6 0M9 10a3 3 0 01-6 0M21 10a3 3 0 01-6 0"/>',
    "calculator": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h.01M13 12h.01M9 16h.01M13 16h.01M16 16h.01M13 8h3"/>',
    "shield": '<path d="M12 22s8-3 8-9V5l-8-3-8 3v8c0 6 8 9 8 9z"/><path d="M9 12l2 2 4-4"/>',
    "briefcase": '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2M3 12h18"/>',
    "file": '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M9 13h6M9 17h6"/>',
    "eye": '<path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/>',
    "users": '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>',
    "cart": '<circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/>',
    "trending": '<path d="M23 6l-9.5 9.5-5-5L1 18"/><path d="M17 6h6v6"/>',
    "link": '<path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/>',
    "user-check": '<path d="M16 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="8.5" cy="7" r="4"/><path d="M17 11l2 2 4-4"/>',
    "rocket": '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 00-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 012-3.95A12.88 12.88 0 0122 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 01-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
}


def icon_svg(name: str) -> str:
    d = SERVICE_ICON_PATHS.get(name or "", SERVICE_ICON_PATHS["briefcase"])
    return (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round">{d}</svg>'
    )


def prerender_services_grid() -> str:
    """Rend la grille de services côté serveur (SEO JS : contenu visible sans JS)."""
    from core.models import Service

    cards = []
    for s in Service.objects.filter(parent__isnull=True):
        sub_html = ""
        subs = list(s.subservices.all())
        if subs:
            lis = "".join(
                f'<li><a href="/devis/?service={ss.slug}">{ss.title}</a> <small>{ss.short_desc}</small></li>'
                for ss in subs
            )
            sub_html = f'<ul class="sub-service-list">{lis}</ul>'
        cards.append(
            '<div class="card">'
            f'<div class="feature-icon">{icon_svg(s.icon)}</div>'
            f"<h3>{s.title}</h3>"
            f"<p>{s.short_desc}</p>"
            f'<p style="font-size:14px">{s.description}</p>'
            f"{sub_html}"
            f'<a class="btn" href="/devis/?service={s.slug}">Demander un devis</a>'
            "</div>"
        )
    return "".join(cards)


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    grid_html = prerender_services_grid()

    for url, dest in PAGES:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"
        html = resp.content.decode("utf-8")
        html = inject_config(html)
        if "<p>Chargement…</p>" in html:
            html = html.replace(
                '<div class="grid-3" id="services-grid"><p>Chargement…</p></div>',
                f'<div class="grid-3" id="services-grid">{grid_html}</div>',
            )
        target = OUT / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        print(f"OK {url} -> pages_build/{dest}")

    for url, dest in [
        ("/sitemap.xml", "sitemap.xml"),
        ("/robots.txt", "robots.txt"),
    ]:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"
        (OUT / dest).write_text(resp.content.decode("utf-8"), encoding="utf-8")
        print(f"OK {url} -> pages_build/{dest}")

    shutil.copytree(BASE_DIR / "static", OUT / "static")
    for src in (BASE_DIR / "static").glob("google*.html"):
        shutil.copy2(src, OUT / src.name)
    for src in (BASE_DIR / "static").glob("*.txt"):
        shutil.copy2(src, OUT / src.name)
    (OUT / "config.js").write_text(
        f'window.BALANCEWORK_API = "{API_BASE}";\n', encoding="utf-8"
    )
    (OUT / "_redirects").write_text(
        "/services /services/\n/devis /devis/\n/contact /contact/\n"
        "/rendezvous /rendezvous/\n/gestion /gestion/\n"
        "/espace-client /espace-client/\n/espace-entreprise /espace-entreprise/\n",
        encoding="utf-8",
    )
    print("OK static/ config.js _redirects")


def inject_config(html):
    for script in ["/static/js/main.js", "/static/js/admin.js", "/static/js/client.js", "/static/js/espace_entreprise.js"]:
        if script in html:
            html = html.replace(
                f'<script src="{script}">',
                '<script src="/config.js"></script>\n  <script src="'
                + script
                + '">',
            )
    return html


if __name__ == "__main__":
    build()
