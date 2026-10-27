"""Steam fill: matching, parsing (recorded store answers, no network) and the fill rules."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ludotek import config, enrich, scanner, steam, storage  # noqa: E402
from ludotek.names import match_score  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


def fixture(name):
    return json.loads((FIXTURES / name).read_text("utf-8"))


@pytest.fixture
def recorded(monkeypatch):
    """steam._get_json answers from tests/fixtures/ instead of the network."""
    def fake(url):
        for term, name in (("hollow", "search-hollow-knight.json"), ("hades", "search-hades.json"),
                           ("skyrim", "search-skyrim.json"), ("367520", "details-367520-fr.json"),
                           ("598190", "details-598190-en.json")):
            if term in url.lower():
                return fixture(name)
        raise steam.SteamError("no fixture for " + url)
    monkeypatch.setattr(steam, "_get_json", fake)


@pytest.mark.parametrize("name, title, accepted", [
    ("Hollow Knight", "Hollow Knight", True),
    ("Hades", "Hades II", False),  # a sequel is another game
    ("Skyrim SE", "The Elder Scrolls V: Skyrim Special Edition", True),
    ("Celeste", "Celeste Classic 2", False),
    ("notes", "Hollow Knight", False),
])
def test_match_score_is_conservative(name, title, accepted):
    assert (match_score(name, title) >= steam.AUTO_THRESHOLD) is accepted


@pytest.mark.parametrize("name, best", [
    ("Hollow Knight", "Hollow Knight"),  # exact beats Silksong and the soundtrack
    ("Hades", "Hades"),  # exact beats "Hades II", listed first by Steam
    ("Skyrim SE", "The Elder Scrolls V: Skyrim Special Edition"),
])
def test_rank_puts_the_game_first(recorded, name, best):
    ranked = steam.rank(name, steam.search(name))
    assert ranked[0]["name"] == best
    assert not any("Soundtrack" in c["name"] for c in ranked)


def test_details_cleans_the_description(recorded):
    info = steam.details(367520, "fr")
    assert info["type"] == "game" and info["name"] == "Hollow Knight"
    assert info["description"].startswith("Choisissez votre destin") and "<" not in info["description"]
    assert steam.is_steam_image(info["header"])


def test_clean_description_strips_tags_and_entities():
    assert steam.clean_description("<b>Fast</b> &amp; <i>fun</i>\n\n game") == "Fast & fun game"


def test_lookup_retries_without_edition_words(recorded, monkeypatch):
    # Steam finds nothing for "Skyrim SE": the second search uses the match key "skyrim".
    real_search, terms = steam.search, []

    def search(term):
        terms.append(term)
        return [] if term == "Skyrim SE" else real_search(term)
    monkeypatch.setattr(steam, "search", search)
    monkeypatch.setattr(steam, "details", lambda appid, lang: {"type": "game", "name": "Skyrim", "description": "", "header": None})
    assert enrich.lookup("Skyrim SE")[0] == 489830
    assert terms == ["Skyrim SE", "skyrim"]
    assert enrich.search_terms("Hades") == ["Hades"]  # no second search when nothing changes


def test_lookup_skips_what_is_not_a_game(recorded, monkeypatch):
    # Only the soundtrack is offered: details() says "music", so nothing is filled.
    monkeypatch.setattr(steam, "search", lambda name: [{"appid": 598190, "name": "Hollow Knight", "thumb": None}])
    assert enrich.lookup("Hollow Knight") is None


def test_only_steam_images_are_used():
    assert steam.cover_urls(367520, "https://evil.example/x.jpg") == [
        "https://cdn.cloudflare.steamstatic.com/steam/apps/367520/library_600x900.jpg"]
    assert not steam.is_steam_image("http://cdn.cloudflare.steamstatic.com/x.jpg")
    assert not steam.valid_appid("367520") and not steam.valid_appid(True) and steam.valid_appid(367520)


# ---- fill rules, on a temporary library (no network: lookups are replaced)

@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / ".bibliotheque.json")
    monkeypatch.setattr(config, "COVERS_DIR", tmp_path / ".bibliotheque" / "covers")
    monkeypatch.setattr(enrich, "fetch_image", lambda url: PNG)
    saved_db, saved_cur = dict(storage.DB), dict(scanner.CURRENT)
    storage.DB.clear()
    storage.DB.update(items={}, removed={})
    scanner.CURRENT.clear()
    yield
    storage.DB.clear(); storage.DB.update(saved_db)
    scanner.CURRENT.clear(); scanner.CURRENT.update(saved_cur)


def add_item(iid, name, kind="dossier", **rec):
    storage.DB["items"][iid] = {"file": name, **rec}
    scanner.CURRENT[iid] = {"name": name, "kind": kind}


def found(appid=367520, description="From Steam"):
    return lambda name: (appid, {"type": "game", "name": name, "description": description, "header": None})


def test_fill_only_touches_empty_fields(library, monkeypatch):
    monkeypatch.setattr(enrich, "lookup", found())
    add_item("a", "Empty")
    add_item("b", "Mine", cover="b.png", cover_source="manual", description="My words")
    add_item("c", "Removed", cover_source="removed", description_source="removed")
    add_item("d", "notes", kind="autre")
    enrich.run([i for i, c in scanner.CURRENT.items() if enrich.needs(storage.DB["items"][i], c["kind"])], config.ROOT)
    a, b, c = (storage.DB["items"][k] for k in "abc")
    assert a["cover_source"] == "auto" and a["description"] == "From Steam" and a["steam_appid"] == 367520
    assert b["cover"] == "b.png" and b["description"] == "My words"
    assert "cover" not in c and "description" not in c
    assert enrich.status()["covers"] == 1 and enrich.status()["descriptions"] == 1


def test_needs_ignores_files_and_done_items():
    assert enrich.needs({}, "archive")
    assert not enrich.needs({}, "autre")
    assert not enrich.needs({"cover": "x.png", "description": "d"}, "dossier")
    assert not enrich.needs({"cover_source": "removed", "description_source": "removed"}, "dossier")


def test_network_errors_count_as_missed_and_the_job_goes_on(library, monkeypatch):
    calls = []

    def flaky(name):
        calls.append(name)
        if name == "First":
            raise steam.SteamError("offline")
        return None
    monkeypatch.setattr(enrich, "lookup", flaky)
    add_item("a", "First")
    add_item("b", "Second")
    enrich.STATE.update(missed=0, covers=0, descriptions=0, done=0)
    enrich.run(["a", "b"], config.ROOT)
    assert calls == ["First", "Second"] and enrich.status()["missed"] == 2 and not enrich.status()["running"]


def test_stop_and_folder_change_end_the_job(library, monkeypatch):
    seen = []
    monkeypatch.setattr(enrich, "lookup", lambda name: seen.append(name) or enrich.stop())
    add_item("a", "First")
    add_item("b", "Second")
    enrich.STATE["stop"] = False
    enrich.run(["a", "b"], config.ROOT)
    assert seen == ["First"]
    enrich.STATE["stop"] = False
    enrich.run(["a"], Path("/another/folder"))  # root changed since the job started
    assert seen == ["First"]


def test_picked_result_replaces_the_cover_but_not_the_text(library, monkeypatch):
    monkeypatch.setattr(steam, "details", lambda appid, lang: {"type": "game", "name": "Hollow Knight",
                                                                "description": "From Steam", "header": None})
    add_item("a", "HK", cover="a.png", cover_source="manual", description="My words")
    (cover_set, desc_set), title = enrich.apply_choice("a", 367520)
    rec = storage.DB["items"]["a"]
    assert cover_set and not desc_set and title == "Hollow Knight"
    assert rec["cover_source"] == "auto" and rec["description"] == "My words"
