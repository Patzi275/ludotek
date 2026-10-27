"""Steam store lookups (public endpoints, no API key). Talks to Steam only: no DB access.

Every URL is built here from fixed hosts; appids are checked to be ints. Store requests
are throttled (Steam allows about 200 per 5 minutes); the image CDN is not.
"""
import html
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .names import match_score

STORE = "https://store.steampowered.com"
CDN = "https://cdn.cloudflare.steamstatic.com"
IMAGE_HOST_SUFFIX = ".steamstatic.com"  # header images come from shared.akamai.steamstatic.com
MAX_JSON = 2 * 1024 * 1024
MIN_INTERVAL = 1.5  # seconds between two store requests
AUTO_THRESHOLD = 0.75  # lowest match_score the automatic fill accepts
# Store titles that are never the game itself.
NOT_A_GAME_RE = re.compile(r"\b(soundtrack|ost|demo|dlc|artbook|art book|season pass)\b", re.I)
# Our language codes -> Steam's "l" parameter.
STEAM_LANGS = {"fr": "french", "en": "english", "de": "german", "es": "spanish", "it": "italian", "pt": "portuguese"}
TAG_RE = re.compile(r"<[^>]+>")

_throttle = threading.Lock()
_last_call = 0.0


class SteamError(Exception):
    """Steam could not be reached or answered something unusable."""


class RateLimited(SteamError):
    """Steam answered HTTP 429: too many requests."""


def valid_appid(appid):
    return isinstance(appid, int) and not isinstance(appid, bool) and 0 < appid < 10 ** 8


def _get_json(url):
    global _last_call
    with _throttle:
        wait = _last_call + MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": "Ludotek"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read(MAX_JSON + 1)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimited(str(e))
        raise SteamError(str(e))
    except (OSError, ValueError) as e:
        raise SteamError(str(e))
    if len(data) > MAX_JSON:
        raise SteamError("response too large")
    try:
        return json.loads(data)
    except ValueError as e:
        raise SteamError(str(e))


def search(name):
    """Store search: [{"appid", "name", "thumb"}] in Steam's relevance order."""
    query = urllib.parse.urlencode({"term": name, "l": "english", "cc": "us"})
    data = _get_json(f"{STORE}/api/storesearch/?{query}")
    items = data.get("items") if isinstance(data, dict) else None
    out = []
    for item in items or []:
        if isinstance(item, dict) and valid_appid(item.get("id")) and isinstance(item.get("name"), str):
            thumb = item.get("tiny_image")
            out.append({"appid": item["id"], "name": item["name"],
                        "thumb": thumb if is_steam_image(thumb) else None})
    return out


def rank(name, candidates):
    """Candidates that may be the game, best first, each with its "score".

    Store titles that are clearly not a game are dropped; ties keep Steam's order.
    """
    scored = [dict(c, score=match_score(name, c["name"])) for c in candidates if not NOT_A_GAME_RE.search(c["name"])]
    return sorted(scored, key=lambda c: -c["score"])  # sorted() is stable: Steam's order breaks ties


def clean_description(text):
    text = html.unescape(TAG_RE.sub(" ", text or ""))
    return re.sub(r"\s+", " ", text).strip()[:5000]


def details(appid, lang):
    """{"type", "name", "description", "header"} of a store page, in our language if Steam has it."""
    if not valid_appid(appid):
        raise SteamError("invalid appid")
    query = urllib.parse.urlencode({"appids": appid, "l": STEAM_LANGS.get(lang, "english"), "filters": "basic"})
    data = _get_json(f"{STORE}/api/appdetails?{query}")
    entry = data.get(str(appid)) if isinstance(data, dict) else None
    if not isinstance(entry, dict) or not entry.get("success") or not isinstance(entry.get("data"), dict):
        raise SteamError("no store page")
    d = entry["data"]
    header = d.get("header_image")
    return {"type": str(d.get("type", "")), "name": str(d.get("name", "")),
            "description": clean_description(d.get("short_description")),
            "header": header if is_steam_image(header) else None}


def is_steam_image(url):
    """Only https images from Steam's CDN are ever downloaded or shown."""
    if not isinstance(url, str):
        return False
    parts = urllib.parse.urlparse(url)
    return parts.scheme == "https" and (parts.hostname or "").endswith(IMAGE_HOST_SUFFIX)


def cover_urls(appid, header=None):
    """Portrait cover first (3:4, like the cards), then the landscape header as fallback."""
    urls = [f"{CDN}/steam/apps/{appid}/library_600x900.jpg"] if valid_appid(appid) else []
    return urls + ([header] if is_steam_image(header) else [])
