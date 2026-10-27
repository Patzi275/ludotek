"""Settings saved in .ludotek.json: library layout validation and persistence."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ludotek import api, config  # noqa: E402


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    path = tmp_path / ".ludotek.json"
    monkeypatch.setattr(config, "SETTINGS_PATH", path)
    return path


def post_settings(body):
    return api.settings(None, {"raw": b"", "type": "application/json", "json": body})


def test_ui_lists_the_same_views_as_the_api():
    js = (ROOT / "ludotek" / "web" / "app.js").read_text("utf-8")
    js_views = re.search(r"const VIEWS = \[([^\]]*)\]", js).group(1)
    assert tuple(re.findall(r'"([^"]+)"', js_views)) == api.VIEWS


def test_view_is_saved_and_other_settings_are_kept(settings_file):
    settings_file.write_text(json.dumps({"root": "D:\\Jeux", "keep_me": 1}), "utf-8")
    assert post_settings({"view": "list"}) == api.OK
    assert json.loads(settings_file.read_text("utf-8")) == {"root": "D:\\Jeux", "keep_me": 1, "view": "list"}
    assert api.current_view() == "list"


def test_unknown_view_is_refused_and_nothing_is_saved(settings_file):
    with pytest.raises(api.ApiError) as err:
        post_settings({"view": "mosaic"})
    assert err.value.status == 400
    assert not settings_file.exists()


def test_default_view_when_nothing_or_garbage_is_saved(settings_file):
    assert api.current_view() == api.DEFAULT_VIEW
    settings_file.write_text(json.dumps({"view": "<script>"}), "utf-8")
    assert api.current_view() == api.DEFAULT_VIEW
