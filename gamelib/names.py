"""Turning raw file names into titles, duplicate keys, sources and ids."""
import hashlib
import re

SOURCES = [
    ("FitGirl", re.compile(r"fit\s*girl", re.I)),
    ("SteamRIP", re.compile(r"steam\s*rip", re.I)),
    ("AnkerGames", re.compile(r"anker\s*games", re.I)),
    ("Telegram", re.compile(r"telegram", re.I)),
]
TAG_RE = re.compile(
    r"[\s_.\-]*(?:steam\s*rip(?:\.com)?|anker\s*games|fit\s*girl(?:[\s_\-]*repack)?)", re.I
)
BRACKETS_RE = re.compile(r"\[[^\]]*\]|\([^)]*\)")
EDITION_WORDS = {
    "the", "special", "edition", "anniversary", "complete", "definitive", "goty",
    "deluxe", "ultimate", "remastered", "ae", "se", "de", "repack",
}


def clean_name(stem):
    """'Hollow-Knight-SteamRIP.com' -> 'Hollow Knight'."""
    s = BRACKETS_RE.sub(" ", stem)
    s = TAG_RE.sub(" ", s)
    s = s.replace("_", " ")
    s = re.sub(r"(?<=\w)-(?=\w)", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -.")
    return s or stem


def match_key(name):
    """Matching key used to spot duplicates (Skyrim SE vs Skyrim AE...)."""
    toks = [
        t for t in re.findall(r"[a-z0-9]+", name.lower())
        if t not in EDITION_WORDS and not (len(t) == 1 and t.isalpha())
    ]
    return " ".join(toks)


def detect_source(filename):
    for label, rx in SOURCES:
        if rx.search(filename):
            return label
    return None


def item_id(filename):
    return hashlib.sha1(filename.encode("utf-8")).hexdigest()[:12]
