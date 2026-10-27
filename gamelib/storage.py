"""The .bibliotheque.json database of the watched folder. Always touch DB under LOCK.

ROOT can change at runtime: DB is refilled in place, PREV_SEEN is reassigned,
so read it as storage.PREV_SEEN.
"""
import json
import logging
import os
import threading

from . import config

log = logging.getLogger(__name__)
LOCK = threading.RLock()
DB = {}
PREV_SEEN = None  # last activity of the previous session in this folder
_last_saved = None


def load_db():
    try:
        data = json.loads(config.DB_PATH.read_text("utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def reload():
    """Load the database of the current config.ROOT (at start and after a folder change)."""
    global PREV_SEEN, _last_saved
    with LOCK:
        DB.clear()
        DB.update(load_db())
        DB.setdefault("items", {})
        DB.setdefault("removed", {})
        PREV_SEEN = DB.get("last_seen_at")
        _last_saved = None


def save_db():
    """Atomic write (.tmp then os.replace), skipped when nothing changed."""
    global _last_saved
    with LOCK:
        text = json.dumps(DB, ensure_ascii=False, indent=1)
        if text == _last_saved:
            return
        try:
            tmp = config.DB_PATH.with_name(config.DB_PATH.name + ".tmp")
            tmp.write_text(text, "utf-8")
            os.replace(tmp, config.DB_PATH)
            _last_saved = text
        except OSError as e:
            log.error("Impossible d'écrire %s : %s", config.DB_PATH, e)


reload()
