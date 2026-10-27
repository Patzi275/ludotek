"""Watching the games folder: top-level scan, then folder sizes and executables in the background."""
import logging
import os
import queue
import re
import time
from pathlib import Path

from . import config
from .config import ARCHIVE_EXT, EXECUTABLE_EXT, IGNORED, IS_WIN, RESCAN_EVERY
from .names import clean_name, detect_source, item_id, match_key
from .storage import DB, LOCK, save_db

# Executables and folders that are never the game itself.
EXE_BLACKLIST = re.compile(
    r"unins|setup|redist|vc_?redist|dxsetup|directx|crash|report|install|dotnet|"
    r"prereq|helper|quicksfv|unrar|7z|cleanup|touchup|activation",
    re.I,
)
SKIP_DIRS = {"_commonredist", "redist", "redistributables", "directx", "vcredist",
             "__installer", "_redist", "support"}

log = logging.getLogger(__name__)
MAX_LISTED = 10  # beyond this, a scan logs a count instead of every name

CURRENT = {}          # id -> entry info as seen in the last scan
PENDING = set()       # folders being analysed (size + executables)
WORK = queue.Queue()
LAST_SCAN = 0.0
_last_error = None  # logged once, not on every rescan


def entry_kind(is_dir, ext):
    # These values are sent to the UI, which matches on them.
    if is_dir:
        return "dossier"
    if ext in ARCHIVE_EXT:
        return "archive"
    if ext in EXECUTABLE_EXT:
        return "executable"
    return "autre"


def scan():
    global LAST_SCAN, _last_error
    root = config.ROOT
    try:
        entries = list(os.scandir(root))
    except OSError as e:
        if str(e) != _last_error:
            log.error("Lecture du dossier impossible : %s", e)
            _last_error = str(e)
        return
    _last_error = None
    now = time.time()
    found = {}
    first = not CURRENT
    added, back_again, gone = [], [], []
    with LOCK:
        if root != config.ROOT:
            return  # the folder was changed while we were listing it
        for e in entries:
            n = e.name
            if n.startswith(".") or n.lower() in IGNORED:
                continue
            try:
                st = e.stat()
                is_dir = e.is_dir()
            except OSError:
                continue
            ext = "" if is_dir else Path(n).suffix.lower()

            iid = item_id(n)
            rec = DB["items"].get(iid)
            if rec is None:
                back = DB["removed"].pop(iid, None)  # came back after being removed
                if back:
                    back.pop("removed_at", None)
                    rec = back
                    back_again.append(n)
                else:
                    rec = {"file": n, "first_seen": now, "favorite": False,
                           "status": "", "notes": "", "exe": None}
                    added.append(n)
                DB["items"][iid] = rec
            rec["file"] = n

            if is_dir:
                if rec.get("size_mtime") != st.st_mtime and iid not in PENDING:
                    PENDING.add(iid)
                    WORK.put(iid)
            else:
                rec["size"] = st.st_size
                rec["size_mtime"] = st.st_mtime

            name = clean_name(n if is_dir else Path(n).stem)
            found[iid] = {
                "id": iid,
                "file": n,
                "name": name,
                "key": match_key(name),
                "kind": entry_kind(is_dir, ext),
                "ext": ext,
                "source": detect_source(n),
                "added": st.st_ctime if IS_WIN else st.st_mtime,
            }

        for iid in [i for i in DB["items"] if i not in found]:
            rec = DB["items"].pop(iid)
            rec["removed_at"] = now
            DB["removed"][iid] = rec
            gone.append(rec.get("file", iid))

        CURRENT.clear()
        CURRENT.update(found)
        DB["last_seen_at"] = now
        LAST_SCAN = now
    if first:
        log.info("Dossier scanné : %d élément(s), %d dossier(s) à analyser.", len(found), len(PENDING))
    _log_changes("Nouveau", added)
    _log_changes("Revenu", back_again)
    _log_changes("Disparu", gone)
    save_db()


def _log_changes(label, names):
    if len(names) > MAX_LISTED:
        log.info("%s : %d éléments.", label, len(names))
    else:
        for n in names:
            log.info("%s : %s", label, n)


def measure_dir(path, exe_depth=3):
    """Total size + plausible executables (shallowest first, then largest)."""
    total = 0
    exes = []
    base = len(path.parts)
    for dirpath, dirnames, filenames in os.walk(path, onerror=lambda err: None):
        rel_parts = Path(dirpath).parts[base:]
        depth = len(rel_parts)
        in_skip = any(p.lower() in SKIP_DIRS for p in rel_parts)
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                sz = os.path.getsize(fp)
            except OSError:
                continue
            total += sz
            if (depth <= exe_depth and not in_skip and f.lower().endswith(".exe")
                    and not EXE_BLACKLIST.search(f)):
                exes.append((depth, -sz, os.path.relpath(fp, path)))
    exes.sort()
    return total, [e[2] for e in exes[:12]]


def worker():
    """Background thread: measures the folders queued by scan()."""
    while True:
        iid = WORK.get()
        with LOCK:
            root = config.ROOT
            rec = DB["items"].get(iid)
            path = root / rec["file"] if rec else None
        if path is None:
            with LOCK:
                PENDING.discard(iid)
            continue
        t0 = time.time()
        size, exes = measure_dir(path)
        log.info("Analysé : %s (%s Mo, %d exécutable(s), %s s)", path.name,
                 f"{size / 1048576:.1f}".replace(".", ","), len(exes), f"{time.time() - t0:.1f}".replace(".", ","))
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = None
        with LOCK:
            rec = DB["items"].get(iid)
            if rec and root == config.ROOT:  # skip results from a previous folder
                rec.update(size=size, exes=exes, size_mtime=mtime)
            PENDING.discard(iid)
            done = not PENDING
        if done:
            log.info("Analyse des dossiers terminée.")
        save_db()


def reset():
    """Forget the previous folder's scan. Call under LOCK, after storage.reload()."""
    CURRENT.clear()
    PENDING.clear()


def rescan_loop():
    while True:
        time.sleep(RESCAN_EVERY)
        scan()
