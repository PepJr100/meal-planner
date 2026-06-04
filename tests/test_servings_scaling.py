"""Recipe servings -> shopping-list quantity scaling."""
import pytest

from meal_planner import app as app_module
from meal_planner.app import (
    DEFAULT_HOUSEHOLD_SIZE,
    build_shopping_list_for_week,
    get_household_size,
    set_household_size,
)
from tests.conftest import find


def test_household_size_defaults(db):
    assert get_household_size() == DEFAULT_HOUSEHOLD_SIZE


def test_household_size_persists(db):
    set_household_size(3)
    assert get_household_size() == 3


def test_invalid_household_size_falls_back_to_default(db):
    app_module.set_setting("household_size", "not-a-number")
    assert get_household_size() == DEFAULT_HOUSEHOLD_SIZE


def test_recipe_without_serves_is_not_scaled(make_plan):
    wp = make_plan([(["Basmati rice, g (150)"], 1)])  # no serves
    rice = find(build_shopping_list_for_week(wp, household_size=2), "rice")
    assert rice["qty_uk"] == 150.0


def test_serves_greater_than_household_scales_down(make_plan):
    # serves 4, want 2 portions -> half.
    wp = make_plan([(["Basmati rice, g (150)"], 1, 4)])
    rice = find(build_shopping_list_for_week(wp, household_size=2), "rice")
    assert rice["qty_uk"] == pytest.approx(75.0)


def test_serves_less_than_household_scales_up(make_plan):
    # serves 2, want 4 portions -> double.
    wp = make_plan([(["Basmati rice, g (150)"], 1, 2)])
    rice = find(build_shopping_list_for_week(wp, household_size=4), "rice")
    assert rice["qty_uk"] == pytest.approx(300.0)


def test_scaling_applies_before_summation(make_plan):
    # serves 4 scheduled twice, want 2 -> (150 * 0.5) * 2 = 150.
    wp = make_plan([(["Basmati rice, g (150)"], 2, 4)])
    rice = find(build_shopping_list_for_week(wp, household_size=2), "rice")
    assert rice["qty_uk"] == pytest.approx(150.0)


def test_scaling_leaves_quantityless_items_as_none(make_plan):
    wp = make_plan([(["Gnocchi"], 1, 4)])
    gnocchi = find(build_shopping_list_for_week(wp, household_size=2), "gnocchi")
    assert gnocchi["qty_uk"] is None


def test_scaling_uses_persisted_household_when_unspecified(make_plan):
    set_household_size(2)
    wp = make_plan([(["Basmati rice, g (150)"], 1, 4)])
    rice = find(build_shopping_list_for_week(wp), "rice")  # no explicit household
    assert rice["qty_uk"] == pytest.approx(75.0)
