"""Force l'indexation Google via l'API Indexing (compte de service Firebase/GCP).

Usage:
    python scripts/google_indexing.py chemin/vers/cle-service-account.json [url1 url2 ...]

Sans URL : indexe les pages par défaut du site (accueil + services).
"""
import sys
from pathlib import Path

import google.auth.transport.requests
import google.oauth2.service_account
import requests

SCOPE = "https://www.googleapis.com/auth/indexing"
ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"

DEFAULT_URLS = [
    "https://balancetaxsafety.pages.dev/",
    "https://balancetaxsafety.pages.dev/services/",
    "https://balancetaxsafety.pages.dev/devis/",
    "https://balancetaxsafety.pages.dev/contact/",
    "https://balancetaxsafety.pages.dev/rendezvous/",
]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    key_path = Path(sys.argv[1])
    urls = sys.argv[2:] or DEFAULT_URLS

    creds = google.oauth2.service_account.Credentials.from_service_account_file(
        key_path, scopes=[SCOPE]
    )
    creds.refresh(google.auth.transport.requests.Request())
    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}

    for url in urls:
        resp = requests.post(
            ENDPOINT,
            headers=headers,
            json={"url": url, "type": "URL_UPDATED"},
            timeout=30,
        )
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        print(f"{resp.status_code}  {url}  {body if resp.status_code == 200 else body}")


if __name__ == "__main__":
    main()
