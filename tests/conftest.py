"""Shared pytest fixtures.

The app opens its SQLite connection at *import time* from the ``MEAL_PLANNER_DB``
environment variable (see ``meal_planner/app.py``), so we point it at a throwaway
database **before** importing the module.
"""
from __future__ import annotations

import os
import tempfile
from datetime import date

import pytest

_TMP_DIR = tempfile.mkdtemp(prefix="meal-planner-tests-")
os.environ["MEAL_PLANNER_DB"] = os.path.join(_TMP_DIR, "test.db")

from meal_planner import app as app_module  # noqa: E402  (must follow env setup above)


@pytest.fixture()
def db():
    """Reset the schema on the app's module-level connection for each test."""
    conn = app_module.db
    conn.executescript(
        "DROP TABLE IF EXISTS week_meals;"
        "DROP TABLE IF EXISTS week_plans;"
        "DROP TABLE IF EXISTS recipes;"
        "DROP TABLE IF EXISTS pantry_staples;"
        "DROP TABLE IF EXISTS settings;"
    )
    conn.commit()
    app_module.init_db()
    yield conn


@pytest.fixture()
def make_plan(db):
    """Factory that builds a week plan from recipes and returns its week_plan_id.

    Pass a list of ``(ingredient_lines, times)`` or ``(ingredient_lines, times,
    serves)`` tuples; each recipe is created and scheduled into ``times`` separate
    dinner slots. Recipes are inserted in the given order, so tests can rely on
    ingredient processing order.
    """
    counter = {"n": 0}

    def _make(recipes):
        week_plan_id = app_module.get_or_create_week_plan_id(date(2026, 6, 1))
        day = 0
        for spec in recipes:
            ingredient_lines, times = spec[0], spec[1]
            serves = spec[2] if len(spec) > 2 else None
            counter["n"] += 1
            name = "R%d" % counter["n"]
            rid = app_module.upsert_recipe(name, ingredient_lines, serves=serves)
            for _ in range(times):
                db.execute(
                    "INSERT INTO week_meals"
                    "(week_plan_id, day_date, meal_type, recipe_id, meal_name) "
                    "VALUES (?,?,?,?,?)",
                    (week_plan_id, "2026-06-%02d" % (1 + day), "Dinner", rid, name),
                )
                day += 1
        db.commit()
        return week_plan_id

    return _make


def find(items, name_contains):
    """Return the first shopping-list item whose name contains the substring."""
    needle = name_contains.lower()
    for it in items:
        if needle in it["name"].lower():
            return it
    return None
