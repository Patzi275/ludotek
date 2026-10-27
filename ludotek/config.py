"""Settings shared by every module: paths, network, limits and file types."""
import json
import os
import re
import secrets
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
# Folder holding the .exe (frozen build) or the repo root, parent of the ludotek/ package (dev).
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
# Which folder to watch. The only file stored outside the watched folder: it sits next to the app.
SETTINGS_PATH = APP_DIR / ".ludotek.json"
WEB_DIR = Path(__file__).resolve().parent / "web"

# Our own files, in case the app sits inside the games folder.
IGNORED = {"ludotek", "bibliotheque.py", "bibliotheque.exe", "ludotek.exe", "desktop.ini", "thumbs.db"}
if FROZEN:
    IGNORED.add(Path(sys.executable).name.lower())

PORT = 8765
TOKEN = secrets.token_urlsafe(16)
RESCAN_EVERY = 15  # seconds
IS_WIN = sys.platform.startswith("win")

MAX_IMAGE = 15 * 1024 * 1024
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
COVER_NAME_RE = re.compile(r"^[0-9a-f]{12}\.(png|jpg|gif|webp)$")



def load_settings():
    try:
        data = json.loads(SETTINGS_PATH.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(data):
    tmp = SETTINGS_PATH.with_name(SETTINGS_PATH.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, SETTINGS_PATH)


def set_root(path):
    """Point every data path at another watched folder. Callers hold storage.LOCK."""
    global ROOT, DB_PATH, COVERS_DIR
    ROOT = Path(path).resolve()
    # Data file and folder names are kept as-is: existing libraries depend on them.
    DB_PATH = ROOT / ".bibliotheque.json"
    COVERS_DIR = ROOT / ".bibliotheque" / "covers"


def _initial_root():
    # Command line, then saved setting (if the folder still exists), then the app's folder.
    if ARGS:
        return ARGS[0]
    saved = load_settings().get("root")
    if isinstance(saved, str) and Path(saved).is_dir():
        return saved
    return APP_DIR


ROOT = DB_PATH = COVERS_DIR = None
set_root(_initial_root())

LANGUAGE = "en"  # set by i18n at import: saved setting, else system language, else English

ARCHIVE_EXT = {".rar", ".zip", ".7z", ".iso", ".tar", ".gz"}
EXECUTABLE_EXT = {".exe", ".msi"}
