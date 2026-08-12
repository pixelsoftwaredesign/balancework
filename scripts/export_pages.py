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


def build():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    for url, dest in PAGES:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"
        html = resp.content.decode("utf-8")
        html = inject_config(html)
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
