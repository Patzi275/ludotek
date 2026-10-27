"""Translations. One flat JSON catalog per language in web/i18n/, shared with the UI.

Keys are dotted ("settings.title"), placeholders are named ("{name}"), plurals use
"key.one" / "key.other". A missing key falls back to English, then to the key itself.
Adding a language = adding web/i18n/<code>.json with the same keys (tests check it).
"""
import json
import os
import sys

from . import config

DIR = config.WEB_DIR / "i18n"
LANGUAGES = sorted(p.stem for p in DIR.glob("*.json"))
FALLBACK = "en"
# Windows primary language ids (LANGID & 0x3FF) -> ISO 639-1, for the languages likely to come.
_WIN_LANGS = {0x07: "de", 0x09: "en", 0x0A: "es", 0x0C: "fr", 0x10: "it", 0x16: "pt"}
_cache = {}


def catalog(lang):
    if lang not in _cache:
        try:
            data = json.loads((DIR / f"{lang}.json").read_text("utf-8"))
        except (OSError, ValueError):
            data = {}
        _cache[lang] = data if isinstance(data, dict) else {}
    return _cache[lang]


def _message(lang, key):
    return catalog(lang).get(key) or catalog(FALLBACK).get(key) or key


def plural_key(lang, key, n):
    zero_is_one = _message(lang, "plural.zero_is_one") == "yes"
    one = n <= 1 if zero_is_one else n == 1
    return f"{key}.{'one' if one else 'other'}"


def t(key, **params):
    """Translated message in the current language. "n" is an ordinary placeholder here."""
    msg = _message(config.LANGUAGE, key)
    try:
        return msg.format(**params)
    except (KeyError, IndexError, ValueError):
        return msg  # a broken translation must never crash the app


def tn(key, n, **params):
    """Plural message: picks "key.one" or "key.other" for n (same rule as tn() in app.js)."""
    return t(plural_key(config.LANGUAGE, key, n), n=n, **params)


def number(x, digits=1):
    """Decimal number with the separator of the current language."""
    return f"{x:.{digits}f}".replace(".", t("number.decimal"))


def system_language():
    """ISO 639-1 code of the user's system language, or None."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            return _WIN_LANGS.get(ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF)
        except Exception:
            return None
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        code = value.split(":")[0].split("_")[0].split(".")[0].lower()
        if code and code not in ("c", "posix"):
            return code
    return None


def resolve(saved):
    """Saved setting, else system language, else English: the first one we have a catalog for."""
    for lang in (saved, system_language(), FALLBACK):
        if lang in LANGUAGES:
            return lang
    return FALLBACK


def languages():
    """[{code, name}] for the language selector, each name in its own language."""
    return [{"code": c, "name": catalog(c).get("language.name", c)} for c in LANGUAGES]


def page_data():
    """What the UI needs, injected into index.html: current catalog, fallback and choices."""
    return {"lang": config.LANGUAGE, "messages": catalog(config.LANGUAGE),
            "fallback": catalog(FALLBACK), "languages": languages()}


config.LANGUAGE = resolve(config.load_settings().get("language"))
