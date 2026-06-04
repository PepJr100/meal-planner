"""Favourite recipes: flag, ordering, and persistence."""
from meal_planner import app as app_module
from meal_planner.app import export_data, get_recipes, import_data


def _add(name, favourite=False):
    rid = app_module.upsert_recipe(name, ["Onion (1)"])
    if favourite:
        app_module.db.execute("UPDATE recipes SET is_favourite = 1 WHERE id = ?", (rid,))
        app_module.db.commit()
    return rid


def test_new_recipe_is_not_favourite(db):
    rid = _add("Risotto")
    assert app_module.get_recipe(rid).is_favourite is False


def test_favourites_sort_to_the_top(db):
    _add("Zebra Stew", favourite=True)
    _add("Apple Bake")
    _add("Mango Salad")
    names = [r.name for r in get_recipes()]
    # Favourite first, then the rest alphabetically.
    assert names[0] == "Zebra Stew"
    assert names[1:] == ["Apple Bake", "Mango Salad"]


def test_toggle_route_flips_flag(db):
    rid = _add("Toastie")
    client = app_module.app.test_client()

    r = client.post("/recipes/favourite", data={"recipe_id": rid}, follow_redirects=False)
    assert r.status_code in (301, 302)
    assert app_module.get_recipe(rid).is_favourite is True

    client.post("/recipes/favourite", data={"recipe_id": rid})
    assert app_module.get_recipe(rid).is_favourite is False


def test_toggle_route_ignores_bad_id(db):
    client = app_module.app.test_client()
    assert client.post("/recipes/favourite", data={"recipe_id": "nope"}).status_code in (301, 302)


def test_favourite_survives_backup_round_trip(db):
    rid = _add("Curry", favourite=True)
    snapshot = export_data()
    assert snapshot["recipes"][0]["is_favourite"] == 1

    db.executescript("DELETE FROM week_meals; DELETE FROM recipes;")
    db.commit()
    import_data(snapshot)
    assert app_module.get_recipe(rid).is_favourite is True
