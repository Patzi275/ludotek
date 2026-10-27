"""What the API does, independent of HTTP: the library view and the POST actions.

Each action takes (item id, request) and returns a JSON-able dict, or raises ApiError.
To add an endpoint, write the function and register it in ACTIONS.
"""
import logging
import time
from pathlib import Path

from . import config, scanner, storage
from .covers import clear_cover, fetch_image, set_cover
from .names import clean_name
from .storage import DB, LOCK, save_db
from .system import open_path, pick_folder, reveal_path

log = logging.getLogger(__name__)
OK = {"ok": True}

# Fields the UI may change, each with its cleaning rule (type + size limit).
UPDATABLE = {
    "favorite": bool,
    "status": lambda v: str(v)[:20],
    "notes": lambda v: str(v)[:5000],
    "description": lambda v: str(v)[:5000],
}


class ApiError(Exception):
    """An error message for the user (in French) and its HTTP status."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def chosen_exe(rec):
    exes = rec.get("exes") or []
    if rec.get("exe") in exes:
        return rec["exe"]
    return exes[0] if exes else None


def payload():
    """Full state for GET /api/library."""
    with LOCK:
        groups = {}
        for iid, cur in scanner.CURRENT.items():
            if cur["key"]:
                groups.setdefault(cur["key"], []).append(iid)
        items = []
        for iid, cur in scanner.CURRENT.items():
            rec = DB["items"].get(iid, {})
            items.append({
                **cur,
                "size": rec.get("size"),
                "computing": iid in scanner.PENDING,
                "favorite": bool(rec.get("favorite")),
                "status": rec.get("status", ""),
                "notes": rec.get("notes", ""),
                "description": rec.get("description", ""),
                "cover": f"/covers/{rec['cover']}?v={rec.get('cover_v', 0)}" if rec.get("cover") else None,
                "exes": rec.get("exes") or [],
                "exe": chosen_exe(rec),
                "last_launched": rec.get("last_launched"),
                "is_new": storage.PREV_SEEN is not None and rec.get("first_seen", 0) > storage.PREV_SEEN,
                "dup": len(groups.get(cur["key"], [])) > 1,
            })
        removed = sorted(
            ({"file": r.get("file"),
              "name": clean_name(Path(r.get("file", "")).stem if "." in r.get("file", "") else r.get("file", "")),
              "removed_at": r.get("removed_at")}
             for r in DB["removed"].values()),
            key=lambda r: r["removed_at"] or 0, reverse=True,
        )[:20]
    return {"root": str(config.ROOT), "scanned_at": scanner.LAST_SCAN, "items": items, "removed": removed}


def _record(iid):
    """The item's record. Call under LOCK."""
    rec = DB["items"].get(iid)
    if rec is None:
        raise ApiError(404, "élément inconnu")
    return rec


def _name(iid):
    """File name of an item, for logs."""
    with LOCK:
        return DB["items"].get(iid, {}).get("file", iid)


def _open(fn, target):
    try:
        fn(target)
    except OSError as e:
        log.error("Ouverture impossible : %s (%s)", target, e)
        raise ApiError(500, str(e))


def rescan(iid, req):
    log.info("Rescan demandé.")
    scanner.scan()
    return OK


def update(iid, req):
    body = req["json"]
    with LOCK:
        rec = _record(iid)
        for field, clean in UPDATABLE.items():
            if field in body:
                rec[field] = clean(body[field])
        # Only an executable found by the scan can be chosen.
        if "exe" in body and (body["exe"] is None or body["exe"] in (rec.get("exes") or [])):
            rec["exe"] = body["exe"]
        changed = [f for f in (*UPDATABLE, "exe") if f in body]
        log.info("Modifié : %s (%s)", rec["file"], ", ".join(changed) or "rien")
    save_db()
    return OK


def launch(iid, req):
    with LOCK:
        rec = _record(iid)
        target = config.ROOT / rec["file"]
        if target.is_dir():
            exe = chosen_exe(rec)
            if not exe:
                raise ApiError(400, "Aucun exécutable trouvé dans ce dossier.")
            target = target / exe
        log.info("Lancement : %s", target)
        _open(open_path, target)
        rec["last_launched"] = time.time()
    save_db()
    return OK


def reveal(iid, req):
    with LOCK:
        target = config.ROOT / _record(iid)["file"]
        log.info("Ouverture de l'emplacement : %s", target)
        _open(reveal_path, target)
    return OK


def cover(iid, req):
    """Body is either the image bytes or JSON {"url": ...}."""
    try:
        if req["type"].startswith("image/") or req["type"] == "application/octet-stream":
            data = req["raw"]
        elif req["json"].get("url"):
            log.info("Téléchargement de la jaquette : %s", req["json"]["url"])
            data = fetch_image(str(req["json"]["url"]))
        else:
            raise ValueError("Aucune image fournie.")
        set_cover(iid, data)
    except (ValueError, OSError) as e:
        raise ApiError(400, str(e) or "Téléchargement impossible.")
    log.info("Jaquette ajoutée : %s", _name(iid))
    return OK


def uncover(iid, req):
    try:
        clear_cover(iid)
    except ValueError as e:
        raise ApiError(404, str(e))
    log.info("Jaquette retirée : %s", _name(iid))
    return OK


def settings(iid, req):
    """Switch the watched folder and remember it for the next launch."""
    # Strip the quotes Windows adds with "Copy as path".
    raw = str(req["json"].get("root") or "").strip().strip('"').strip()
    path = Path(raw).expanduser() if raw else None
    if path is None or not path.is_absolute() or not path.is_dir():
        raise ApiError(400, "Dossier introuvable. Indique un chemin complet, par exemple D:\\Jeux.")
    log.info("Changement de dossier : %s", path)
    with LOCK:
        save_db()  # flush the previous library first
        config.set_root(path)
        storage.reload()
        scanner.reset()
        scanner.scan()
    try:
        config.save_settings({**config.load_settings(), "root": str(config.ROOT)})
    except OSError as e:
        log.warning("Réglage non enregistré dans %s : %s", config.SETTINGS_PATH, e)
        return {"ok": True, "warning": "Dossier changé, mais le réglage n'a pas pu être enregistré "
                                       "à côté de l'application : il sera perdu au prochain lancement."}
    return OK


def browse(iid, req):
    try:
        return {"path": pick_folder(config.ROOT)}
    except OSError as e:
        raise ApiError(400, str(e))


# POST /api/<action>/<id>. "quit" lives in server.py since it stops the server.
ACTIONS = {
    "rescan": rescan,
    "update": update,
    "launch": launch,
    "reveal": reveal,
    "cover": cover,
    "uncover": uncover,
    "settings": settings,
    "browse": browse,
}
