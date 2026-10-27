"""What the API does, independent of HTTP: the library view and the POST actions.

Each action takes (item id, request) and returns a JSON-able dict, or raises ApiError.
To add an endpoint, write the function and register it in ACTIONS.
"""
import logging
import time
from pathlib import Path

from . import config, enrich, i18n, scanner, steam, storage
from .covers import clear_cover, fetch_image, set_cover
from .i18n import t
from .names import clean_name
from .storage import DB, LOCK, save_db
from .system import open_path, pick_folder, reveal_path

log = logging.getLogger(__name__)
OK = {"ok": True}

# Library layouts offered by the UI (app.js VIEWS must list the same values; tests check it).
VIEWS = ("grid-s", "grid-m", "grid-l", "list")
DEFAULT_VIEW = "grid-m"

# Fields the UI may change, each with its cleaning rule (type + size limit).
UPDATABLE = {
    "favorite": bool,
    "status": lambda v: str(v)[:20],
    "notes": lambda v: str(v)[:5000],
    "description": lambda v: str(v)[:5000],
}


class ApiError(Exception):
    """A message for the user (already translated, see i18n.t) and its HTTP status."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def current_view():
    """Saved library layout, or the default one."""
    view = config.load_settings().get("view")
    return view if view in VIEWS else DEFAULT_VIEW


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
                "needs_info": enrich.needs(rec, cur["kind"]),
            })
        removed = sorted(
            ({"file": r.get("file"),
              "name": clean_name(Path(r.get("file", "")).stem if "." in r.get("file", "") else r.get("file", "")),
              "removed_at": r.get("removed_at")}
             for r in DB["removed"].values()),
            key=lambda r: r["removed_at"] or 0, reverse=True,
        )[:20]
    return {"root": str(config.ROOT), "scanned_at": scanner.LAST_SCAN, "items": items, "removed": removed,
            "enrich": enrich.status()}


def _record(iid):
    """The item's record. Call under LOCK."""
    rec = DB["items"].get(iid)
    if rec is None:
        raise ApiError(404, t("error.unknown_item"))
    return rec


def _name(iid):
    """File name of an item, for logs."""
    with LOCK:
        return DB["items"].get(iid, {}).get("file", iid)


def _open(fn, target):
    try:
        fn(target)
    except OSError as e:
        log.error(t("log.open_failed", path=target, error=e))
        raise ApiError(500, str(e))


def _set_cover_source(iid, source):
    with LOCK:
        rec = DB["items"].get(iid)
        if rec is not None:
            rec["cover_source"] = source
    save_db()


def rescan(iid, req):
    log.info(t("log.rescan"))
    scanner.scan()
    return OK


def update(iid, req):
    body = req["json"]
    with LOCK:
        rec = _record(iid)
        old_description = rec.get("description", "")
        for field, clean in UPDATABLE.items():
            if field in body:
                rec[field] = clean(body[field])
        if rec.get("description", "") != old_description:
            # The user's text wins over the Steam fill; emptied on purpose means "do not refill".
            rec["description_source"] = "manual" if rec["description"] else "removed"
        # Only an executable found by the scan can be chosen.
        if "exe" in body and (body["exe"] is None or body["exe"] in (rec.get("exes") or [])):
            rec["exe"] = body["exe"]
        changed = [f for f in (*UPDATABLE, "exe") if f in body]
        log.info(t("log.updated", name=rec["file"], fields=", ".join(changed) or t("log.nothing")))
    save_db()
    return OK


def launch(iid, req):
    with LOCK:
        rec = _record(iid)
        target = config.ROOT / rec["file"]
        if target.is_dir():
            exe = chosen_exe(rec)
            if not exe:
                raise ApiError(400, t("error.no_exe"))
            target = target / exe
        log.info(t("log.launch", path=target))
        _open(open_path, target)
        rec["last_launched"] = time.time()
    save_db()
    return OK


def reveal(iid, req):
    with LOCK:
        target = config.ROOT / _record(iid)["file"]
        log.info(t("log.reveal", path=target))
        _open(reveal_path, target)
    return OK


def cover(iid, req):
    """Body is either the image bytes or JSON {"url": ...}."""
    try:
        if req["type"].startswith("image/") or req["type"] == "application/octet-stream":
            data = req["raw"]
        elif req["json"].get("url"):
            log.info(t("log.cover_download", url=req["json"]["url"]))
            data = fetch_image(str(req["json"]["url"]))
        else:
            raise ValueError(t("error.no_image"))
        set_cover(iid, data)
    except (ValueError, OSError) as e:
        raise ApiError(400, str(e) or t("error.download_failed"))
    _set_cover_source(iid, "manual")
    log.info(t("log.cover_added", name=_name(iid)))
    return OK


def uncover(iid, req):
    try:
        clear_cover(iid)
    except ValueError as e:
        raise ApiError(404, str(e))
    _set_cover_source(iid, "removed")  # the Steam fill will not bring it back
    log.info(t("log.cover_removed", name=_name(iid)))
    return OK


def settings(iid, req):
    """Change the watched folder, the language and/or the layout, and remember them for the next launch.

    Both fields are optional and validated before anything is applied.
    """
    body = req["json"]
    path = lang = None
    if "root" in body:
        # Strip the quotes Windows adds with "Copy as path".
        raw = str(body["root"] or "").strip().strip('"').strip()
        path = Path(raw).expanduser() if raw else None
        if path is None or not path.is_absolute() or not path.is_dir():
            raise ApiError(400, t("error.bad_folder"))
    if "language" in body:
        lang = str(body["language"])
        if lang not in i18n.LANGUAGES:
            raise ApiError(400, t("error.bad_language", language=lang))
    if "view" in body and body["view"] not in VIEWS:
        raise ApiError(400, t("error.bad_view", view=str(body["view"])[:20]))

    saved = {"view": body["view"]} if "view" in body else {}
    if lang:
        config.LANGUAGE = lang
        saved["language"] = lang
        log.info(t("log.language_change", language=lang))
    if path:
        log.info(t("log.folder_change", path=path))
        with LOCK:
            save_db()  # flush the previous library first
            config.set_root(path)
            storage.reload()
            scanner.reset()
            scanner.scan()
        saved["root"] = str(config.ROOT)
    if not saved:
        return OK
    try:
        config.save_settings({**config.load_settings(), **saved})
    except OSError as e:
        log.warning(t("log.settings_not_saved", path=config.SETTINGS_PATH, error=e))
        return {"ok": True, "warning": t("error.settings_not_saved")}
    return OK


def browse(iid, req):
    try:
        return {"path": pick_folder(config.ROOT)}
    except OSError as e:
        raise ApiError(400, str(e))


def fill(iid, req):
    """Start (or with {"stop": true}, stop) the Steam fill of every game missing a cover or a description."""
    if req["json"].get("stop"):
        enrich.stop()
        return OK
    total = enrich.start()
    if total is None:
        raise ApiError(409, t("error.enrich_busy"))
    return {"ok": True, "total": total}


def steam_search(iid, req):
    """Top Steam results for one game. Blocks the request for a second or two (tolerated)."""
    with LOCK:
        _record(iid)
    try:
        return {"candidates": enrich.candidates(iid)}
    except steam.SteamError:
        raise ApiError(502, t("error.steam_unavailable"))


def steam_apply(iid, req):
    """Fill one game from the store page the user picked."""
    appid = req["json"].get("appid")
    if not steam.valid_appid(appid):
        raise ApiError(400, t("error.bad_appid"))
    with LOCK:
        name = _record(iid)["file"]
    try:
        (cover_set, desc_set), title = enrich.apply_choice(iid, appid)
    except steam.SteamError:
        raise ApiError(502, t("error.steam_unavailable"))
    log.info(t("log.steam_applied", name=name, title=title))
    return {"ok": True, "cover": cover_set, "description": desc_set}


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
    "enrich": fill,
    "steam_search": steam_search,
    "steam_apply": steam_apply,
}
