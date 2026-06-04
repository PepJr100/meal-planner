"""End-to-end parsing of a single ingredient line (uses the real NLP parser)."""
import pytest

from meal_planner.app import parse_ingredient_line_uk


def test_parenthetical_count_has_no_unit():
    r = parse_ingredient_line_uk("Onion (1)")
    assert r["qty_uk"] == 1.0
    assert r["unit_uk"] is None
    assert r["name_singular"] == "onion"


def test_fractional_quantity_is_preserved():
    # Regression: fractional amounts must not collapse to 0 (the 0.3 -> 0 bug).
    r = parse_ingredient_line_uk("mushrooms (0.3)")
    assert r["qty_uk"] == pytest.approx(0.3)
    assert r["unit_uk"] is None
    assert r["name_singular"] == "mushroom"


def test_parenthetical_quantity_is_stripped_from_name():
    r = parse_ingredient_line_uk("Onion (1)")
    assert "(1)" not in r["normalized_name"]


def test_split_name_unit_quantity_is_stitched():
    # "Name, <unit> (<qty>)" — the parser splits these; we re-stitch them.
    r = parse_ingredient_line_uk("Basmati rice, g (150)")
    assert r["qty_uk"] == 150.0
    assert r["unit_uk"] == "g"


def test_grams_with_plural_name():
    r = parse_ingredient_line_uk("Kidney Beans, g (400)")
    assert r["qty_uk"] == 400.0
    assert r["unit_uk"] == "g"
    assert r["name_singular"] == "kidney bean"


def test_natural_language_quantity():
    r = parse_ingredient_line_uk("2 onions")
    assert r["qty_uk"] == 2.0
    assert r["unit_uk"] is None
    assert r["name_singular"] == "onion"


def test_natural_language_weight():
    r = parse_ingredient_line_uk("150 g basmati rice")
    assert r["qty_uk"] == 150.0
    assert r["unit_uk"] == "g"


def test_line_without_quantity():
    r = parse_ingredient_line_uk("Gnocchi")
    assert r["qty_uk"] is None
    assert r["unit_uk"] is None
    assert r["name_singular"] == "gnocchi"


def test_multiword_name_singularises_last_word_only():
    r = parse_ingredient_line_uk("Spring Onions (2)")
    assert r["qty_uk"] == 2.0
    assert r["name_singular"] == "spring onion"


def test_original_text_is_retained():
    r = parse_ingredient_line_uk("  Onion (1)  ")
    assert r["original_text"] == "Onion (1)"
