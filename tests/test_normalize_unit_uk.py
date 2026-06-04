"""Unit conversion is the deterministic foundation of the shopping list."""
import pytest

from meal_planner.app import normalize_unit_uk


def test_none_quantity_returns_all_none():
    assert normalize_unit_uk("g", None) == (None, None, None, None)


def test_no_unit_preserves_quantity_as_countless():
    assert normalize_unit_uk("", 3) == (3.0, None, 3.0, "")


@pytest.mark.parametrize(
    "unit, qty, expected_qty, expected_unit",
    [
        ("g", 250, 250.0, "g"),
        ("grams", 250, 250.0, "g"),
        ("kg", 1, 1000.0, "g"),
        ("lb", 1, 453.592, "g"),
        ("oz", 2, 56.699, "g"),
        ("ml", 100, 100.0, "ml"),
        ("l", 1, 1000.0, "ml"),
        ("cup", 1, 236.588, "ml"),
        ("tsp", 1, 5.0, "ml"),
        ("tbsp", 1, 15.0, "ml"),
    ],
)
def test_known_units_convert_to_uk(unit, qty, expected_qty, expected_unit):
    qty_uk, unit_uk, _, _ = normalize_unit_uk(unit, qty)
    assert qty_uk == pytest.approx(expected_qty)
    assert unit_uk == expected_unit


def test_unknown_unit_is_preserved_verbatim():
    qty_uk, unit_uk, _, original_unit = normalize_unit_uk("pinch", 1)
    assert (qty_uk, unit_uk) == (1.0, "pinch")
    assert original_unit == "pinch"


def test_originals_are_retained_through_conversion():
    _, _, original_qty, original_unit = normalize_unit_uk("kg", 2)
    assert (original_qty, original_unit) == (2.0, "kg")
