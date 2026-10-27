"""Translation catalogs: complete, consistent, and every key used by the code exists."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ludotek import config, i18n  # noqa: E402

CATALOG_DIR = ROOT / "ludotek" / "web" / "i18n"
CATALOGS = {p.stem: json.loads(p.read_text("utf-8")) for p in sorted(CATALOG_DIR.glob("*.json"))}
PLACEHOLDER = re.compile(r"\{(\w+)\}")
HTML = (ROOT / "ludotek" / "web" / "index.html").read_text("utf-8")
JS = (ROOT / "ludotek" / "web" / "app.js").read_text("utf-8")
PY = "\n".join(p.read_text("utf-8") for p in (ROOT / "ludotek").glob("*.py"))
SOURCES = HTML + JS + PY


def used_keys():
    """Keys referenced literally: data-i18n* attributes, t("...") and tn("...") calls."""
    keys = set(re.findall(r'data-i18n(?:-[a-z-]+)?="([^"]+)"', HTML))
    keys |= set(re.findall(r'\bt\("([^"]+)"', JS + PY))
    for base in re.findall(r'\btn\("([^"]+)"', JS + PY):  # plural: both forms must exist
        keys |= {base + ".one", base + ".other"}
    return keys


def test_french_and_english_exist():
    assert {"en", "fr"} <= set(CATALOGS)


@pytest.mark.parametrize("lang", sorted(CATALOGS))
def test_same_keys_as_english(lang):
    assert set(CATALOGS[lang]) == set(CATALOGS["en"])


@pytest.mark.parametrize("lang", sorted(CATALOGS))
def test_same_placeholders_as_english(lang):
    for key, en in CATALOGS["en"].items():
        assert set(PLACEHOLDER.findall(CATALOGS[lang][key])) == set(PLACEHOLDER.findall(en)), key


@pytest.mark.parametrize("lang", sorted(CATALOGS))
def test_values_are_non_empty_strings(lang):
    for key, value in CATALOGS[lang].items():
        assert isinstance(value, str) and value.strip(), key


def test_every_used_key_exists():
    assert used_keys() - set(CATALOGS["en"]) == set()


def test_every_key_is_used():
    # A key counts as used when it appears quoted in the code (plural forms through their base).
    unused = []
    for key in CATALOGS["en"]:
        base = re.sub(r"\.(one|other)$", "", key)
        if f'"{key}"' not in SOURCES and f'"{base}"' not in SOURCES:
            unused.append(key)
    assert unused == []


@pytest.fixture
def fake_catalogs(monkeypatch):
    monkeypatch.setattr(i18n, "_cache", {
        "fr": {"plural.zero_is_one": "yes", "n.one": "{n} jeu", "n.other": "{n} jeux", "hello": "Salut {name}",
               "number.decimal": ","},
        "en": {"plural.zero_is_one": "no", "n.one": "{n} game", "n.other": "{n} games", "hello": "Hi {name}",
               "only.en": "English only", "broken": "Bad {missing}", "number.decimal": "."},
    })


def test_plurals_follow_the_language(fake_catalogs, monkeypatch):
    monkeypatch.setattr(config, "LANGUAGE", "fr")
    assert [i18n.tn("n", k) for k in (0, 1, 2)] == ["0 jeu", "1 jeu", "2 jeux"]
    monkeypatch.setattr(config, "LANGUAGE", "en")
    assert [i18n.tn("n", k) for k in (0, 1, 2)] == ["0 games", "1 game", "2 games"]


def test_n_is_an_ordinary_placeholder_in_t(fake_catalogs, monkeypatch):
    # Regression: t(key, n=…) used to look up "key.one"/"key.other" and print the raw key.
    monkeypatch.setattr(i18n, "_cache", {"en": {"many": "New: {n} items."}, "fr": {}})
    monkeypatch.setattr(config, "LANGUAGE", "en")
    assert i18n.t("many", n=12) == "New: 12 items."


def test_fallback_to_english_then_to_the_key(fake_catalogs, monkeypatch):
    monkeypatch.setattr(config, "LANGUAGE", "fr")
    assert i18n.t("hello", name="Ada") == "Salut Ada"
    assert i18n.t("only.en") == "English only"
    assert i18n.t("no.such.key") == "no.such.key"


def test_broken_translation_does_not_crash(fake_catalogs, monkeypatch):
    monkeypatch.setattr(config, "LANGUAGE", "en")
    assert i18n.t("broken") == "Bad {missing}"


def test_number_uses_the_language_separator(fake_catalogs, monkeypatch):
    monkeypatch.setattr(config, "LANGUAGE", "fr")
    assert i18n.number(1.25, 1) == "1,2"
    monkeypatch.setattr(config, "LANGUAGE", "en")
    assert i18n.number(3, 1) == "3.0"


@pytest.mark.parametrize("env, expected", [
    ({"LANG": "fr_FR.UTF-8"}, "fr"),
    ({"LANGUAGE": "de:en", "LANG": "fr_FR.UTF-8"}, "de"),
    ({"LC_ALL": "C", "LANG": "en_US.UTF-8"}, "en"),
    ({}, None),
])
def test_system_language_from_environment(monkeypatch, env, expected):
    monkeypatch.setattr(sys, "platform", "linux")
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    for var, value in env.items():
        monkeypatch.setenv(var, value)
    assert i18n.system_language() == expected


def test_resolve_prefers_saved_then_system_then_english(monkeypatch):
    monkeypatch.setattr(i18n, "system_language", lambda: "fr")
    assert i18n.resolve("en") == "en"
    assert i18n.resolve("xx") == "fr"
    monkeypatch.setattr(i18n, "system_language", lambda: "de")
    assert i18n.resolve(None) == "en"
