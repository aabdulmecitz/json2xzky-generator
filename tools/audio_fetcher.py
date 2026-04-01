#!/usr/bin/env python3
"""
audio_fetcher.py — MyInstants Audio Scraper (Standalone Tool)
==============================================================
Scans a scenario.json for missing sound files and downloads them
from MyInstants.com.

Usage:
    python tools/audio_fetcher.py assets/example/example_scenario.json
    python tools/audio_fetcher.py --query "vine boom"
"""

import json
import re
import sys
import urllib.parse
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ Missing dependencies. Run: pip install requests beautifulsoup4")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOUNDS_DIR = PROJECT_ROOT / "assets" / "sounds" / "mp3"
SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def download_from_myinstants(query: str, session=None) -> bool:
    """
    Search MyInstants for a sound, download the first result.
    Returns True on success.
    """
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})

    search_url = f"https://www.myinstants.com/en/search/?name={urllib.parse.quote_plus(query)}"

    try:
        resp = session.get(search_url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ❌ HTTP error: {e}")
        return False

    soup = BeautifulSoup(resp.text, "html.parser")
    mp3_url = None

    # Strategy 1: onclick attributes of play buttons
    for btn in soup.select(".small-button"):
        onclick = btn.get("onclick", "")
        match = re.search(r"play\('(.*?\.mp3)'", onclick)
        if match:
            mp3_url = match.group(1)
            break

    # Strategy 2: direct <a> links to .mp3
    if not mp3_url:
        for a_tag in soup.find_all("a", href=True):
            if ".mp3" in a_tag["href"]:
                mp3_url = a_tag["href"]
                break

    # Strategy 3: data-url attributes
    if not mp3_url:
        for el in soup.find_all(attrs={"data-url": True}):
            if ".mp3" in el["data-url"]:
                mp3_url = el["data-url"]
                break

    if not mp3_url:
        return False

    # Resolve relative URLs
    if mp3_url.startswith("//"):
        mp3_url = "https:" + mp3_url
    elif mp3_url.startswith("/"):
        mp3_url = "https://www.myinstants.com" + mp3_url

    # Download
    try:
        audio_resp = session.get(mp3_url, timeout=15)
        audio_resp.raise_for_status()
        safe_name = query.replace(" ", "_")
        out_path = SOUNDS_DIR / f"{safe_name}.mp3"
        out_path.write_bytes(audio_resp.content)
        return True
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return False


def resolve_scenario(filepath: str) -> int:
    """
    Scan a scenario JSON for missing sounds, download them.
    Returns the number of successfully downloaded files.
    """
    data = json.loads(Path(filepath).read_text(encoding="utf-8"))
    missing = set()

    for entry in data:
        for key in ("sound", "sound_query"):
            name = entry.get(key)
            if name and not (SOUNDS_DIR / f"{name}.mp3").exists():
                missing.add(name)

    if not missing:
        print("✅ All audio assets exist locally!")
        return 0

    print(f"🔎 Missing {len(missing)} sound(s): {missing}\n")
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    downloaded = 0
    for query in sorted(missing):
        print(f"  Fetching '{query}'...", end=" ")
        if download_from_myinstants(query, session):
            print("✅")
            downloaded += 1
        else:
            print("⚠️  not found")

    print(f"\n📊 Downloaded {downloaded}/{len(missing)} sounds")
    return downloaded


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python audio_fetcher.py <scenario.json>")
        print("  python audio_fetcher.py --query 'vine boom'")
        sys.exit(1)

    if sys.argv[1] == "--query":
        query = " ".join(sys.argv[2:])
        print(f"Fetching '{query}' from MyInstants...", end=" ")
        if download_from_myinstants(query):
            print(f"✅ Saved to {SOUNDS_DIR / query.replace(' ', '_')}.mp3")
        else:
            print("❌ Not found")
    else:
        resolve_scenario(sys.argv[1])


if __name__ == "__main__":
    main()
