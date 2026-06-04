"""Parsing the optional SERVES: line from text recipes."""
import pytest

from meal_planner.app import _coerce_serves, _parse_text_recipe


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("4", 4),
        (" 4 ", 4),
        ("Serves 6 people", 6),
        ("0", None),
        ("", None),
        (None, None),
        ("lots", None),
    ],
)
def test_coerce_serves(raw, expected):
    assert _coerce_serves(raw) == expected


def test_parse_text_recipe_reads_serves(tmp_path):
    f = tmp_path / "chilli.txt"
    f.write_text(
        "Chilli Con Carne\n"
        "SERVES: 4\n"
        "- Onion (1)\n"
        "- Beef mince, g (500)\n",
        encoding="utf-8",
    )
    name, ingredients, url, method, serves = _parse_text_recipe(f)
    assert name == "Chilli Con Carne"
    assert serves == 4
    assert ingredients == ["Onion (1)", "Beef mince, g (500)"]


def test_parse_text_recipe_without_serves(tmp_path):
    f = tmp_path / "plain.txt"
    f.write_text("Toast\n- Bread (2)\n", encoding="utf-8")
    _, _, _, _, serves = _parse_text_recipe(f)
    assert serves is None
