"""The version/channel badge shown in the bottom-left of every page."""
import pytest

from meal_planner import app as app_module


@pytest.mark.parametrize(
    "path", ["/", "/shopping-list", "/recipes", "/backup", "/ingredients/harmonize"]
)
def test_badge_rendered_on_every_page(db, path):
    html = app_module.app.test_client().get(path).get_data(as_text=True)
    assert 'class="app-version"' in html


def test_badge_shows_version_and_channel(db):
    html = app_module.app.test_client().get("/").get_data(as_text=True)
    assert app_module.APP_VERSION in html
    assert app_module.APP_CHANNEL in html


def test_full_git_sha_is_shortened(db, monkeypatch):
    monkeypatch.setattr(app_module, "APP_VERSION", "a" * 40)
    with app_module.app.test_request_context("/"):
        ctx = app_module.inject_app_version()
    assert ctx["app_version"] == "a" * 7


def test_normal_version_is_not_shortened(db, monkeypatch):
    monkeypatch.setattr(app_module, "APP_VERSION", "v1.10.10")
    with app_module.app.test_request_context("/"):
        ctx = app_module.inject_app_version()
    assert ctx["app_version"] == "v1.10.10"
