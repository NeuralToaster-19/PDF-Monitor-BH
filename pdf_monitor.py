import os
import json
import requests
from bs4 import BeautifulSoup

# ----------------------------
# CONFIG (all overrideable via env)
# ----------------------------
WEBSITE_URL = os.getenv(
    "WEBSITE_URL",
    # Fallback (you can change this or rely on the Secret)
    "https://www.lingen.de/bauen-wirtschaft/wohnbaugebiete/aktuelle-grundstuecksvergabe/brockhausen-1.html",
)
STATE_PATH = os.getenv("STATE_PATH", "state/last_pdf_links.json")

# Pushover secrets are injected by the workflow
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_APP_TOKEN = os.getenv("PUSHOVER_APP_TOKEN")

HTTP_HEADERS = {
    # Be a polite client; some sites block default Python UA
    "User-Agent": "Mozilla/5.0 (compatible; Lingen-PDF-Monitor/1.0; +github-actions)"
}


def find_pdf_links(url: str) -> set:
    """Return a set of absolute URLs for all PDFs linked on the page."""
    r = requests.get(url, timeout=30, headers=HTTP_HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().endswith(".pdf"):
            links.add(requests.compat.urljoin(url, href))
    return links


def load_old_links() -> set:
    """Load previously seen links from STATE_PATH (returns empty set if none)."""
    if not os.path.exists(STATE_PATH):
        return set()
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(data)
        # tolerate other JSON structures
        return set(data or [])
    except Exception as e:
        print("Warning: could not load state:", e)
        return set()


def save_links(links: set):
    """Persist current set of links to STATE_PATH (creates parent dir if needed)."""
    parent = os.path.dirname(STATE_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(links), f, ensure_ascii=False, indent=2)


def send_push(message: str):
    """Send a Pushover notification if keys are present."""
    if not (PUSHOVER_USER_KEY and PUSHOVER_APP_TOKEN):
        print("Pushover keys missing – no notification sent.")
        return
    try:
        resp = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": PUSHOVER_APP_TOKEN,
                "user": PUSHOVER_USER_KEY,
                "title": "Lingen PDF Monitor",
                "message": message,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            print("Pushover: sent.")
        else:
            print("Pushover error:", resp.status_code, resp.text)
    except Exception as e:
        print("Pushover exception:", e)


def main():
    try:
        current = find_pdf_links(WEBSITE_URL)
    except Exception as e:
        print("Error fetching/parsing page:", e)
        return

    if not current:
        print("No PDF links found on the page.")
        return

    old = load_old_links()
    new = current - old

    if new:
        msg = "Neue PDFs entdeckt:\n" + "\n".join(sorted(new))
        send_push(msg)
        save_links(current)
        print("New PDFs detected:", *sorted(new), sep="\n- ")
    else:
        print("No new PDFs.")


if __name__ == "__main__":
    main()

