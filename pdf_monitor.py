import os
import json
import requests
from bs4 import BeautifulSoup

# --- CONFIG ---
WEBSITE_URL = os.getenv(
    "WEBSITE_URL",
    "https://www.lingen.de/bauen-wirtschaft/wohnbaugebiete/aktuelle-grundstuecksvergabe/brockhausen-1.html"
)
STATE_PATH = os.getenv("STATE_PATH", "last_pdf_links.json")

# Pushover keys will be injected via GitHub Secrets
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_APP_TOKEN = os.getenv("PUSHOVER_APP_TOKEN")
WEBSITE_URL = os.getenv("WEBSITE_URL")

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Lingen-PDF-Monitor/1.0; +github-actions)"
}


def find_pdf_links(url: str) -> set:
    r = requests.get(url, timeout=30, headers=HTTP_HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            links.add(requests.compat.urljoin(url, href))
    return links


def load_old_links() -> set:
    if not os.path.exists(STATE_PATH):
        return set()
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data) if isinstance(data, list) else set(data or [])
    except Exception as e:
        print("Could not load state:", e)
        return set()


def save_links(links: set):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(list(links)), f, ensure_ascii=False, indent=2)


def send_push(msg: str):
    if not (PUSHOVER_USER_KEY and PUSHOVER_APP_TOKEN):
        print("Pushover keys missing – no notification sent.")
        return
    try:
        r = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": PUSHOVER_APP_TOKEN,
                "user": PUSHOVER_USER_KEY,
                "title": "Lingen PDF Monitor",
                "message": msg,
            },
            timeout=30,
        )
        if r.status_code == 200:
            print("Pushover notification sent.")
        else:
            print("Pushover failed:", r.status_code, r.text)
    except Exception as e:
        print("Pushover exception:", e)


def main():
    try:
        current = find_pdf_links(WEBSITE_URL)
    except Exception as e:
        print("Error fetching/parsing page:", e)
        return

    old = load_old_links()
    new = current - old

    if new:
        msg = "Neue PDFs entdeckt:\n" + "\n".join(sorted(new))
        send_push(msg)
        save_links(current)
        print("New PDFs found:", *sorted(new), sep="\n- ")
    else:
        print("No new PDFs found.")


if __name__ == "__main__":

    main()
