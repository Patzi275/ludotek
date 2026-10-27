"""Fill missing covers and descriptions from the Steam store.

Two entry points:
- start() / stop(): background job over every game that misses a cover or a description;
- candidates() / apply_choice(): per-game search where the user picks the right result.

Only empty fields are filled, and what the user did wins: a removed cover or an emptied
description is marked "removed" (see api.uncover / api.update) and never filled again.
"""
import logging
import threading
import time

from . import config, scanner, steam
from .covers import fetch_image, set_cover
from .i18n import t
from .names import match_key
from .storage import DB, LOCK, save_db

log = logging.getLogger(__name__)
GAME_KINDS = ("dossier", "archive", "executable")  # "autre" (notes.txt…) is never looked up
RATE_LIMIT_PAUSE = 60  # seconds to wait once after an HTTP 429

STATE = {"running": False, "stop": False, "done": 0, "total": 0, "covers": 0, "descriptions": 0, "missed": 0}


def needs_cover(rec):
    return not rec.get("cover") and rec.get("cover_source") != "removed"


def needs_description(rec):
    return not rec.get("description") and rec.get("description_source") != "removed"


def needs(rec, kind):
    """True when the automatic fill has something to do for this item."""
    return kind in GAME_KINDS and (needs_cover(rec) or needs_description(rec))


def status():
    """Progress of the background job, for api.payload()."""
    with LOCK:
        return {k: v for k, v in STATE.items() if k != "stop"}


def start():
    """Start the background job. Returns the number of games, or None if one is already running."""
    with LOCK:
        if STATE["running"]:
            return None
        ids = [iid for iid, cur in scanner.CURRENT.items() if needs(DB["items"].get(iid, {}), cur["kind"])]
        STATE.update(running=bool(ids), stop=False, done=0, total=len(ids), covers=0, descriptions=0, missed=0)
        root = config.ROOT
    if ids:
        log.info(t("log.enrich_start", n=len(ids)))
        threading.Thread(target=run, args=(ids, root), daemon=True).start()
    return len(ids)


def stop():
    with LOCK:
        STATE["stop"] = True


def run(ids, root):
    """The job itself (runs in its own thread). Stops on request or when the folder changes."""
    stopped = False
    try:
        for iid in ids:
            with LOCK:
                if STATE["stop"] or config.ROOT != root:
                    stopped = True
                    break
                cur = scanner.CURRENT.get(iid)
            if cur:
                _fill_one(iid, cur["name"])
            with LOCK:
                STATE["done"] += 1
    finally:
        with LOCK:
            STATE["running"] = False
            summary = dict(STATE)
        log.info(t("log.enrich_stopped") if stopped else
                 t("log.enrich_done", covers=summary["covers"], descriptions=summary["descriptions"],
                   missed=summary["missed"]))


def search_terms(name):
    """The name, then its match key ("Skyrim SE" -> "skyrim"): Steam's search finds
    nothing for some edition names, and the key drops the edition words."""
    key = match_key(name)
    return [name] if not key or key == name.lower() else [name, key]


def lookup(name):
    """(appid, details) of the store page that is surely this game, or None."""
    for term in search_terms(name):
        for cand in steam.rank(name, steam.search(term))[:2]:
            if cand["score"] < steam.AUTO_THRESHOLD:
                break
            info = steam.details(cand["appid"], config.LANGUAGE)
            if info["type"] == "game":  # not a DLC, a soundtrack or a demo
                return cand["appid"], info
    return None


def _fill_one(iid, name):
    try:
        try:
            match = lookup(name)
        except steam.RateLimited:
            log.warning(t("log.enrich_rate_limited"))
            time.sleep(RATE_LIMIT_PAUSE)
            match = lookup(name)
    except steam.RateLimited as e:
        stop()  # still limited after the pause: give up rather than hammer Steam
        _count(missed=1)
        log.warning(t("log.enrich_error", name=name, error=e))
        return
    except steam.SteamError as e:
        _count(missed=1)
        log.warning(t("log.enrich_error", name=name, error=e))
        return
    if not match:
        _count(missed=1)
        log.info(t("log.enrich_missed", name=name))
        return
    appid, info = match
    cover_set, desc_set = apply(iid, appid, info)
    _count(covers=int(cover_set), descriptions=int(desc_set))
    log.info(t("log.enrich_found", name=name, title=info["name"]))


def _count(**deltas):
    with LOCK:
        for key, n in deltas.items():
            STATE[key] += n


def apply(iid, appid, info, replace_cover=False):
    """Fill the item from a store page; returns (cover set, description set).

    Fields are checked again under LOCK just before writing: the user may have
    edited the item while Steam was answering.
    """
    with LOCK:
        rec = DB["items"].get(iid)
        if rec is None:
            return False, False
        want_cover = replace_cover or needs_cover(rec)
    cover_set = False
    if want_cover:
        for url in steam.cover_urls(appid, info.get("header")):
            try:
                data = fetch_image(url)  # http(s) only, MAX_IMAGE
            except (OSError, ValueError):
                continue  # e.g. no portrait cover for old games: try the header
            with LOCK:
                rec = DB["items"].get(iid)
                if rec is None or not (replace_cover or needs_cover(rec)):
                    break
                try:
                    set_cover(iid, data)  # checks the bytes really are an image
                except ValueError:
                    continue
                rec["cover_source"] = "auto"
                cover_set = True
            break
    with LOCK:
        rec = DB["items"].get(iid)
        if rec is None:
            return cover_set, False
        desc_set = bool(info.get("description")) and needs_description(rec)
        if desc_set:
            rec["description"] = info["description"]
            rec["description_source"] = "auto"
        rec["steam_appid"] = appid
    save_db()
    return cover_set, desc_set


def candidates(iid):
    """Top 5 store results for the details dialog, with no threshold: the user decides."""
    with LOCK:
        cur = scanner.CURRENT.get(iid)
    if cur is None:
        return []
    for term in search_terms(cur["name"]):
        ranked = steam.rank(cur["name"], steam.search(term))[:5]
        if ranked:
            return [{"appid": c["appid"], "name": c["name"], "image": steam.cover_urls(c["appid"])[0],
                     "fallback": c["thumb"]} for c in ranked]
    return []


def apply_choice(iid, appid):
    """The user picked this store page: replace the cover, fill the description if empty."""
    info = steam.details(appid, config.LANGUAGE)
    return apply(iid, appid, info, replace_cover=True), info["name"]
