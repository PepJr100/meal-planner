"""Backup export / import round-trips and validation."""
import pytest

from meal_planner import app as app_module
from meal_planner.app import export_data, import_data, set_household_size


def _seed(make_plan):
    wp = make_plan([(["Onion (1)", "Rice, g (150)"], 1, 4)])
    set_household_size(3)
    app_module.db.execute("INSERT INTO pantry_staples(normalized_name) VALUES ('salt')")
    app_module.db.commit()
    return wp


def test_export_has_all_sections(db, make_plan):
    _seed(make_plan)
    data = export_data()
    assert data["meta"]["app"] == "meal-planner"
    assert len(data["recipes"]) == 1
    assert len(data["week_plans"]) == 1
    assert len(data["week_meals"]) == 1
    assert {"normalized_name": "salt"} in data["pantry_staples"]
    assert {"key": "household_size", "value": "3"} in data["settings"]


def test_export_preserves_serves(db, make_plan):
    _seed(make_plan)
    assert export_data()["recipes"][0]["serves"] == 4


def test_round_trip_restores_everything(db, make_plan):
    _seed(make_plan)
    snapshot = export_data()

    # Wipe everything, then restore from the snapshot.
    db.executescript(
        "DELETE FROM week_meals; DELETE FROM week_plans;"
        "DELETE FROM pantry_staples; DELETE FROM settings; DELETE FROM recipes;"
    )
    db.commit()
    assert db.execute("SELECT COUNT(1) c FROM recipes").fetchone()["c"] == 0

    import_data(snapshot)

    restored = export_data()
    assert restored["recipes"] == snapshot["recipes"]
    assert restored["week_plans"] == snapshot["week_plans"]
    assert restored["week_meals"] == snapshot["week_meals"]
    assert restored["pantry_staples"] == snapshot["pantry_staples"]
    assert restored["settings"] == snapshot["settings"]


def test_import_replaces_existing_data(db, make_plan):
    _seed(make_plan)
    snapshot = export_data()
    # Add an extra recipe that should be gone after restoring the snapshot.
    app_module.upsert_recipe("Throwaway", ["Junk (1)"])
    assert db.execute("SELECT COUNT(1) c FROM recipes").fetchone()["c"] == 2

    import_data(snapshot)
    names = [r["name"] for r in db.execute("SELECT name FROM recipes")]
    assert "Throwaway" not in names
    assert len(names) == 1


def test_import_preserves_meal_foreign_keys(db, make_plan):
    _seed(make_plan)
    snapshot = export_data()
    import_data(snapshot)
    # The restored meal must still reference an existing recipe.
    row = db.execute(
        "SELECT recipe_id FROM week_meals "
        "WHERE recipe_id IN (SELECT id FROM recipes)"
    ).fetchone()
    assert row is not None


@pytest.mark.parametrize("bad", ["not a dict", 123, ["a", "b"]])
def test_import_rejects_non_object(db, bad):
    with pytest.raises(ValueError):
        import_data(bad)


def test_import_rejects_wrong_section_type(db):
    with pytest.raises(ValueError):
        import_data({"recipes": {"not": "a list"}})


def test_import_rollback_leaves_data_intact(db, make_plan):
    _seed(make_plan)
    before = export_data()
    # A recipe row missing the NOT NULL name should abort the whole import.
    bad = {"recipes": [{"id": 1, "ingredients_text": "x"}]}  # no name
    with pytest.raises(Exception):
        import_data(bad)
    after = export_data()
    assert after["recipes"] == before["recipes"]


def test_backup_routes_smoke(db, make_plan):
    _seed(make_plan)
    client = app_module.app.test_client()
    assert client.get("/backup").status_code == 200
    rj = client.get("/backup/export.json")
    assert rj.status_code == 200
    assert b"meal-planner" in rj.data
    assert client.get("/backup/export.db").status_code == 200
