"""Shopping-list aggregation — where the historical bugs lived."""
import pytest

from meal_planner.app import build_shopping_list_for_week
from tests.conftest import find


def test_empty_plan_is_empty(make_plan):
    wp = make_plan([])
    assert build_shopping_list_for_week(wp) == []


def test_only_recipe_linked_meals_count(make_plan):
    wp = make_plan([(["Onion (1)"], 1)])
    items = build_shopping_list_for_week(wp)
    assert len(items) == 1
    assert find(items, "onion")["qty_uk"] == 1.0


def test_quantities_sum_across_meals(make_plan):
    # Same recipe scheduled on two days -> quantities add up.
    wp = make_plan([(["Basmati rice, g (150)"], 2)])
    rice = find(items := build_shopping_list_for_week(wp), "rice")
    assert rice["qty_uk"] == 300.0
    assert rice["unit_uk"] == "g"
    assert len(items) == 1


def test_quantity_after_a_quantityless_line_is_not_dropped(make_plan):
    # Regression: a quantity-less line ("Gnocchi") processed first used to pin the
    # bucket to None and swallow a later "Gnocchi (1)". It must now accumulate.
    wp = make_plan([(["Gnocchi", "Gnocchi (1)"], 1)])
    gnocchi = find(build_shopping_list_for_week(wp), "gnocchi")
    assert gnocchi is not None
    assert gnocchi["qty_uk"] == 1.0


def test_fractional_quantities_accumulate(make_plan):
    # Regression for the 0.3 -> 0 rounding: two 0.3 portions sum to 0.6.
    wp = make_plan([(["mushrooms (0.3)"], 2)])
    mushrooms = find(build_shopping_list_for_week(wp), "mushroom")
    assert mushrooms["qty_uk"] == pytest.approx(0.6)


def test_plurals_consolidate_via_singularisation(make_plan):
    # "Onion (1)" and "Onions (2)" share a bucket -> one line totalling 3.
    wp = make_plan([(["Onion (1)", "Onions (2)"], 1)])
    items = build_shopping_list_for_week(wp)
    onion = find(items, "onion")
    assert onion["qty_uk"] == 3.0
    assert onion["unit_uk"] is None
    assert len([i for i in items if "onion" in i["name"].lower()]) == 1


def test_countless_quantity_is_kept_without_unit(make_plan):
    wp = make_plan([(["Onion (1)"], 1)])
    onion = find(build_shopping_list_for_week(wp), "onion")
    assert onion["qty_uk"] == 1.0
    assert onion["unit_uk"] is None


def test_different_units_stay_separate(make_plan):
    wp = make_plan([(["Basmati rice, g (150)", "Gnocchi"], 1)])
    items = build_shopping_list_for_week(wp)
    assert find(items, "rice")["unit_uk"] == "g"
    assert find(items, "gnocchi")["qty_uk"] is None
    assert len(items) == 2


def test_results_are_sorted_by_name(make_plan):
    wp = make_plan([(["Apples (2)", "Zucchini (1)", "Mango (1)"], 1)])
    names = [i["name"].lower() for i in build_shopping_list_for_week(wp)]
    assert names == sorted(names)
