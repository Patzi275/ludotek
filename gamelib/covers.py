"""Cover images stored as .bibliotheque/covers/<id>.<ext>."""
import re
import time
import urllib.request

from . import config
from .config import COVER_NAME_RE, IMAGE_TYPES, MAX_IMAGE
from .storage import DB, LOCK, save_db


def sniff_image(data):
    """Return the extension based on the actual bytes, not the file name."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"GIF8"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def fetch_image(url):
    if not re.match(r"^https?://", url or "", re.I):
        raise ValueError("URL invalide (http ou https attendu).")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Ludex"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read(MAX_IMAGE + 1)
    if len(data) > MAX_IMAGE:
        raise ValueError("Image trop lourde (15 Mo max).")
    return data


def read_cover(name):
    """(bytes, content type) of a stored cover, or None. The name is validated first."""
    fp = config.COVERS_DIR / name
    if COVER_NAME_RE.match(name) and fp.is_file():
        return fp.read_bytes(), IMAGE_TYPES[fp.suffix]
    return None


def remove_cover_files(iid):
    if config.COVERS_DIR.is_dir():
        for old in config.COVERS_DIR.glob(iid + ".*"):
            try:
                old.unlink()
            except OSError:
                pass


def set_cover(iid, data):
    ext = sniff_image(data)
    if not ext:
        raise ValueError("Format non supporté (PNG, JPG, WEBP ou GIF).")
    with LOCK:
        rec = DB["items"].get(iid)
        if rec is None:
            raise ValueError("Élément inconnu.")
        config.COVERS_DIR.mkdir(parents=True, exist_ok=True)
        remove_cover_files(iid)
        (config.COVERS_DIR / (iid + ext)).write_bytes(data)
        rec["cover"] = iid + ext
        rec["cover_v"] = int(time.time())
    save_db()


def clear_cover(iid):
    with LOCK:
        rec = DB["items"].get(iid)
        if rec is None:
            raise ValueError("Élément inconnu.")
        remove_cover_files(iid)
        rec.pop("cover", None)
        rec.pop("cover_v", None)
    save_db()
