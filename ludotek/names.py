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


SEQUEL_RE = re.compile(r"^(\d+|i{2,3}|iv|vi{0,3}|ix|x)$")  # "2", "ii", "iv"… mark another game


def match_score(name, candidate):
    """How surely `candidate` (a store title) is the same game as `name`, from 0 to 1.

    Conservative on purpose (a wrong cover is worse than none): 1.0 for the same key,
    0.8 when every word of `name` is in `candidate` and the extra words are not a sequel
    number ("Skyrim" -> "The Elder Scrolls V: Skyrim"), else the word overlap (Jaccard).
    """
    a, b = match_key(name).split(), match_key(candidate).split()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    sa, sb = set(a), set(b)
    if sa <= sb and not any(SEQUEL_RE.match(w) for w in sb - sa):
        return 0.8
    return len(sa & sb) / len(sa | sb)


def detect_source(filename):
    for label, rx in SOURCES:
        if rx.search(filename):
            return label
    return None


def item_id(filename):
    return hashlib.sha1(filename.encode("utf-8")).hexdigest()[:12]
