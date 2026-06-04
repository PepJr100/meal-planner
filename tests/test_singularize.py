"""Singularisation is what merges 'onion' and 'onions' in the shopping list."""
import pytest

from meal_planner.app import singularize


@pytest.mark.parametrize(
    "word, expected",
    [
        ("onions", "onion"),
        ("tomatoes", "tomato"),   # ...es after 'o'
        ("boxes", "box"),         # ...es after 'x'
        ("berries", "berry"),     # ...ies -> y
        ("potatoes", "potato"),
        ("glass", "glass"),       # ...ss is left alone
        ("rice", "rice"),         # no trailing 's'
        ("", ""),
    ],
)
def test_singularize(word, expected):
    assert singularize(word) == expected


def test_singularize_is_case_insensitive_and_trims():
    assert singularize("  Onions ") == "onion"
