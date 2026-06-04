from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, TypedDict

from flask import Flask, jsonify, redirect, render_template, request, url_for  # type: ignore
from werkzeug.utils import secure_filename  # type: ignore

from ingredient_parser import parse_ingredient  # type: ignore


BASE_DIR = Path(__file__).resolve().parent
RECIPES_DIR = BASE_DIR / "recipes"
DEFAULT_DB_PATH = BASE_DIR / "meal_planner.db"


app = Flask(__name__, template_folder="templates", static_folder="static")

MEAL_TYPES = ["Breakfast", "Lunch", "Dinner", "Snack"]


def _db_path() -> str:
    return os.environ.get("MEAL_PLANNER_DB") or str(DEFAULT_DB_PATH)


def _connect_db() -> sqlite3.Connection:
    db_file = _db_path()
    parent = os.path.dirname(db_file)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_file, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


db = _connect_db()


def init_db() -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS recipes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          url TEXT,
          ingredients_text TEXT NOT NULL,
          method_text TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS week_plans (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          week_start_date TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS week_meals (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          week_plan_id INTEGER NOT NULL REFERENCES week_plans(id) ON DELETE CASCADE,
          day_date TEXT NOT NULL,
          meal_type TEXT NOT NULL,
          recipe_id INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
          meal_name TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_week_meals_week_day ON week_meals(week_plan_id, day_date);

        CREATE TABLE IF NOT EXISTS pantry_staples (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          normalized_name TEXT NOT NULL UNIQUE
        );
        """
    )
    db.commit()


def ensure_recipes_dir() -> None:
    """
    Ensure the legacy filesystem recipes directory exists.
    Used for one-time import and optional backup of uploaded files.
    """
    RECIPES_DIR.mkdir(parents=True, exist_ok=True)


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_days(week_start: date) -> List[str]:
    return [(week_start + timedelta(days=i)).isoformat() for i in range(7)]


def get_or_create_week_plan_id(week_start: date) -> int:
    ws = week_start.isoformat()
    row = db.execute("SELECT id FROM week_plans WHERE week_start_date = ?", (ws,)).fetchone()
    if row:
        return int(row["id"])
    cur = db.execute("INSERT INTO week_plans(week_start_date) VALUES (?)", (ws,))
    db.commit()
    return int(cur.lastrowid or 0)


def upsert_recipe(name: str, ingredients: List[str], url: str | None = None, method: str | None = None) -> int:
    now = datetime.now(timezone.utc).isoformat()
    ingredients_text = "\n".join([i.strip() for i in ingredients if i and i.strip()])
    cur = db.execute(
        "INSERT INTO recipes(name, url, ingredients_text, method_text, created_at, updated_at) VALUES (?,?,?,?,?,?)",
        (name.strip(), (url or None), ingredients_text, (method or None), now, now),
    )
    db.commit()
    return int(cur.lastrowid or 0)


def update_recipe(recipe_id: int, name: str, url: str | None, ingredients_text: str, method: str | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "UPDATE recipes SET name=?, url=?, ingredients_text=?, method_text=?, updated_at=? WHERE id=?",
        (name.strip(), (url or None), ingredients_text.strip(), (method or None), now, recipe_id),
    )
    db.commit()


def get_recipes() -> List["Recipe"]:
    rows = db.execute("SELECT id, name, url, ingredients_text, method_text FROM recipes ORDER BY lower(name) ASC").fetchall()
    out: List[Recipe] = []
    for r in rows:
        ingredients = [ln.strip() for ln in (r["ingredients_text"] or "").splitlines() if ln.strip()]
        out.append(
            Recipe(
                id=int(r["id"]),
                name=str(r["name"]),
                ingredients=ingredients,
                source_path=None,
                url=(str(r["url"]) if r["url"] else None),
                method=(str(r["method_text"]) if r["method_text"] else None),
            )
        )
    return out


def get_recipe(recipe_id: int) -> Optional["Recipe"]:
    r = db.execute(
        "SELECT id, name, url, ingredients_text, method_text FROM recipes WHERE id = ?",
        (recipe_id,),
    ).fetchone()
    if not r:
        return None
    ingredients = [ln.strip() for ln in (r["ingredients_text"] or "").splitlines() if ln.strip()]
    return Recipe(
        id=int(r["id"]),
        name=str(r["name"]),
        ingredients=ingredients,
        source_path=None,
        url=(str(r["url"]) if r["url"] else None),
        method=(str(r["method_text"]) if r["method_text"] else None),
    )


def import_filesystem_recipes_if_empty() -> None:
    """
    One-time import: if DB has no recipes, import from meal_planner/recipes/*.{txt,md,csv}.
    """
    row = db.execute("SELECT COUNT(1) AS c FROM recipes").fetchone()
    if row and int(row["c"]) > 0:
        return

    ensure_recipes_dir()
    for entry in sorted(RECIPES_DIR.iterdir()):
        if not entry.is_file():
            continue
        suffix = entry.suffix.lower()
        if suffix in {".txt", ".md"}:
            name, ingredients, url, method = _parse_text_recipe(entry)
            if name:
                upsert_recipe(name=name, ingredients=ingredients, url=url, method=method)
        elif suffix == ".csv":
            for name, ingredients in _parse_csv_recipes(entry):
                if name:
                    upsert_recipe(name=name, ingredients=ingredients, url=None, method=None)


def normalize_unit_uk(unit: Optional[str], quantity: Optional[float]) -> Tuple[Optional[float], Optional[str], Optional[float], Optional[str]]:
    """
    Map various units to UK-friendly ones (g, kg, ml, l, tsp, tbsp).
    Always treat 'cup'/'cups' as US cup (236.588 ml).
    Returns (qty_uk, unit_uk, original_qty, original_unit).
    """
    if quantity is None:
        return None, None, None, None

    u = str(unit or "").lower().strip()
    q = float(quantity)
    original_qty = q
    original_unit = unit

    if not u:
        return q, None, original_qty, original_unit

    # weight
    if u in {"g", "gram", "grams"}:
        return q, "g", original_qty, original_unit
    if u in {"kg", "kilogram", "kilograms"}:
        return q * 1000.0, "g", original_qty, original_unit
    if u in {"lb", "lbs", "pound", "pounds"}:
        return q * 453.592, "g", original_qty, original_unit
    if u in {"oz", "ounce", "ounces"}:
        return q * 28.3495, "g", original_qty, original_unit

    # volume
    if u in {"ml", "millilitre", "millilitres", "milliliter", "milliliters"}:
        return q, "ml", original_qty, original_unit
    if u in {"l", "litre", "litres", "liter", "liters"}:
        return q * 1000.0, "ml", original_qty, original_unit
    if u in {"cup", "cups"}:
        # Assume US cups
        return q * 236.588, "ml", original_qty, original_unit
    if u in {"tsp", "teaspoon", "teaspoons"}:
        return q * 5.0, "ml", original_qty, original_unit
    if u in {"tbsp", "tablespoon", "tablespoons"}:
        return q * 15.0, "ml", original_qty, original_unit

    # If unknown unit, preserve the quantity and original unit
    return q, unit, original_qty, original_unit


def singularize(word: str) -> str:
    """Simple heuristic to singularize common English nouns for ingredient name matching."""
    word = word.strip().lower()
    if not word:
        return ""
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 2 and word[-3] in "oxshz":
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 1:
        return word[:-1]
    return word


def parse_ingredient_line_uk(line: str) -> Dict[str, Any]:
    """
    Use ingredient_parser to extract a UK-normalized representation while preserving originals.
    """
    parsed = parse_ingredient(line)
    
    # Extract name and clean it up (parser sometimes leaves trailing commas/junk)
    name_texts = [t.text for t in (parsed.name or []) if getattr(t, "text", "").strip()]
    normalized_name = ", ".join(name_texts).strip() or line.strip()
    # Strip parenthetical numbers or trailing numbers if parser missed them but they look like amounts
    normalized_name = re.sub(r'\s*\(\d+(\.\d+)?\)\s*$', '', normalized_name)
    normalized_name = re.sub(r'[,.\s]+$', '', normalized_name)

    qty_uk: Optional[float] = None
    unit_uk: Optional[str] = None
    original_qty: Optional[float] = None
    original_unit: Optional[str] = None

    # Logic to stitch together quantity/unit if parser splits them (e.g. "Basmati rice, g (150)")
    q_raw: Optional[str] = None
    u_raw: Optional[str] = None
    
    if parsed.amount:
        # Pass 1: Find any valid quantity
        for amt in parsed.amount:
            val = str(getattr(amt, "quantity", "") or "").strip()
            if val and not q_raw:
                q_raw = val
            unit = str(getattr(amt, "unit", "") or "").strip()
            if unit and not u_raw:
                u_raw = unit
    
    # PROACTIVE CATCH: If parser failed to find a clear quantity, look for trailing numbers
    # This catches "Item (1)", "Item (0.5)", "Item 1", "Item, 1"
    if not q_raw:
        # Regex explanation:
        # [^\w.] matches anything not a letter, digit, or dot (like space, comma, paren)
        # (\d+(?:\.\d+)?) matches the number
        # [)\s]*$ matches optional closing paren/spaces at end
        match = re.search(r'[^\w.]+(\d+(?:\.\d+)?)[)\s]*$', line.strip())
        if match:
            q_raw = match.group(1)
            # Ensure u_raw remains None for unit-less numbers
                
    # Conversion
    if q_raw:
        try:
            # Handle fractions safely
            q_val = float(Fraction(q_raw))
            qty_uk, unit_uk, original_qty, original_unit = normalize_unit_uk(u_raw, q_val)
        except Exception:
            # Fallback to direct float if Fraction fails
            try:
                q_val = float(q_raw)
                qty_uk, unit_uk, original_qty, original_unit = normalize_unit_uk(u_raw, q_val)
            except Exception:
                pass

    return {
        "normalized_name": normalized_name,
        "name_singular": singularize(normalized_name),
        "qty_uk": qty_uk,
        "unit_uk": unit_uk,
        "original_qty": original_qty,
        "original_unit": original_unit,
        "original_text": line.strip(),
    }


class Bucket(TypedDict):
    name: str
    unit_uk: Optional[str]
    qty_uk: Optional[float]
    originals: List[Dict[str, Any]]


def build_shopping_list_for_week(week_plan_id: int) -> List[Dict[str, Any]]:
    """
    Build a structured shopping list for a given week, using Ingredient Parser and UK units.
    Aggregates by (normalized_name, unit_uk) when available; otherwise by original_text.
    """
    # Map recipe_id -> ingredients_text
    recipes_map: Dict[int, Dict[str, Any]] = {}
    for r in db.execute("SELECT id, name, ingredients_text FROM recipes"):
        recipes_map[int(r["id"])] = {
            "name": str(r["name"]),
            "ingredients": [ln.strip() for ln in (r["ingredients_text"] or "").splitlines() if ln.strip()],
        }

    # Collect ingredient lines
    rows = db.execute(
        "SELECT recipe_id FROM week_meals WHERE week_plan_id = ? AND recipe_id IS NOT NULL",
        (week_plan_id,),
    ).fetchall()

    parsed_items: List[Dict[str, Any]] = []
    for r in rows:
        rid = int(r["recipe_id"])
        recipe = recipes_map.get(rid)
        if not recipe:
            continue
        for line in recipe["ingredients"]:
            try:
                parsed_items.append(parse_ingredient_line_uk(line))
            except Exception:
                parsed_items.append(
                    {
                        "normalized_name": line.strip(),
                        "qty_uk": None,
                        "unit_uk": None,
                        "original_qty": None,
                        "original_unit": None,
                        "original_text": line.strip(),
                    }
                )

    # Aggregate
    totals: Dict[Tuple[str, Optional[str]], Bucket] = {}
    for item in parsed_items:
        # Use singularized name for the key to consolidate "onion" and "onions"
        key = (
            item["name_singular"].lower(),
            item["unit_uk"],
        )
        bucket = totals.get(key)
        if not bucket:
            bucket = Bucket(  # type: ignore
                name=str(item["normalized_name"]),
                unit_uk=item["unit_uk"],
                qty_uk=None,
                originals=[],
            )
            totals[key] = bucket
        # Accumulate any quantity we find. The first quantity seeds the sum, so a
        # bucket stays None only when no line in it ever carried a quantity. This
        # avoids the order-dependent bug where a quantity-less line (e.g. "Gnocchi")
        # processed first pinned the bucket to None and swallowed later "Gnocchi (1)".
        if item["qty_uk"] is not None:
            bucket["qty_uk"] = (bucket["qty_uk"] or 0.0) + item["qty_uk"]  # type: ignore
        bucket["originals"].append(
            {
                "original_qty": item["original_qty"],
                "original_unit": item["original_unit"],
                "original_text": item["original_text"],
            }
        )

    result: List[Dict[str, Any]] = []
    for (_norm, unit_uk), data in totals.items():
        result.append(
            {
                "name": data["name"],
                "unit_uk": unit_uk,
                "qty_uk": data["qty_uk"],
                "originals": data["originals"],
            }
        )

    # Sort by name
    result.sort(key=lambda x: x["name"].lower())
    return result

def get_day_meals_by_type(week_plan_id: int) -> Dict[str, Dict[str, str]]:
    """
    Return day_date -> { meal_type: meal_name } for a given week.
    """
    rows = db.execute(
        "SELECT day_date, meal_type, meal_name FROM week_meals WHERE week_plan_id = ?",
        (week_plan_id,),
    ).fetchall()
    out: Dict[str, Dict[str, str]] = {}
    for r in rows:
        day = str(r["day_date"])
        out.setdefault(day, {})[str(r["meal_type"])] = str(r["meal_name"])
    return out


def replace_day_meals(week_plan_id: int, day_date: str, name_by_type: Dict[str, str], recipes: List["Recipe"]) -> None:
    by_name = {r.name.strip(): r.id for r in recipes}
    db.execute("DELETE FROM week_meals WHERE week_plan_id = ? AND day_date = ?", (week_plan_id, day_date))
    for meal_type, name in name_by_type.items():
        name = (name or "").strip()
        if not name:
            continue
        recipe_id = by_name.get(name)
        db.execute(
            "INSERT INTO week_meals(week_plan_id, day_date, meal_type, recipe_id, meal_name) VALUES (?,?,?,?,?)",
            (week_plan_id, day_date, meal_type, recipe_id, name),
        )
    db.commit()


def set_day_meal_slot(week_plan_id: int, day_date: str, meal_type: str, name: str, recipes: List["Recipe"]) -> None:
    by_name = {r.name.strip(): r.id for r in recipes}
    name = (name or "").strip()
    if not name:
        db.execute(
            "DELETE FROM week_meals WHERE week_plan_id = ? AND day_date = ? AND meal_type = ?",
            (week_plan_id, day_date, meal_type),
        )
        db.commit()
        return

    recipe_id = by_name.get(name)
    # replace existing slot
    db.execute(
        "DELETE FROM week_meals WHERE week_plan_id = ? AND day_date = ? AND meal_type = ?",
        (week_plan_id, day_date, meal_type),
    )
    db.execute(
        "INSERT INTO week_meals(week_plan_id, day_date, meal_type, recipe_id, meal_name) VALUES (?,?,?,?,?)",
        (week_plan_id, day_date, meal_type, recipe_id, name),
    )
    db.commit()


@dataclass
class Recipe:
    id: int
    name: str
    ingredients: List[str]
    source_path: Optional[Path] = None
    url: Optional[str] = None
    method: Optional[str] = None

    @property
    def is_missing_amounts(self) -> bool:
        """
        Fast heuristic to determine if more than 4 ingredients are missing quantities.
        Looks for digits or common amount words in the ingredient string.
        """
        if not self.ingredients:
            return False
            
        amount_pattern = re.compile(r'\d|one|two|three|four|five|half|quarter|pinch|handful|dash|some|few|tbsp|tsp|cup|ml|g|oz|lb', re.IGNORECASE)
        missing_count = 0
        
        for ing in self.ingredients:
            if not amount_pattern.search(ing):
                missing_count += 1  # type: ignore
                
        return missing_count > 4


@dataclass
class Meal:
    day: str
    meal_type: str
    name: str
    notes: str = ""
    recipe_id: Optional[int] = None


@dataclass
class Plan:
    start_date: date
    days: List[str] = field(default_factory=list)
    meals: Dict[str, List[Meal]] = field(default_factory=dict)

    @classmethod
    def for_week(cls, start: date | None = None) -> "Plan":
        if start is None:
            today = date.today()
            # start the plan on the current week's Monday
            start = today - timedelta(days=today.weekday())

        days: List[str] = []
        meals: Dict[str, List[Meal]] = {}
        for offset in range(7):
            d = start + timedelta(days=offset)
            key = d.isoformat()
            days.append(key)
            meals[key] = []

        return cls(start_date=start, days=days, meals=meals)





def _parse_text_recipe(path: Path) -> Tuple[Optional[str], List[str], Optional[str], Optional[str]]:
    """
    Very simple parser for .txt/.md recipe files.

    Convention:
      - first non-empty line: recipe name
      - an optional line starting with 'URL:' is treated as a source URL
      - lines starting with '-', '*', '•' are ingredients
      - optional 'METHOD:' section: following lines are method text
    """
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None, [], None, None

    lines = [ln.rstrip() for ln in text.splitlines()]
    name: Optional[str] = None
    url: Optional[str] = None
    ingredients: List[str] = []
    method: Optional[str] = None
    in_method = False
    method_lines: List[str] = []

    for raw in lines:
        if in_method:
            method_lines.append(raw)
            continue
        stripped = raw.strip()
        if not stripped:
            continue

        if stripped.lower().startswith("method:"):
            in_method = True
            rest = stripped.split(":", 1)[1].strip()
            if rest:
                method_lines.append(rest)
            continue

        if name is None and not stripped.lower().startswith("url:"):
            name = stripped
            continue

        if stripped.lower().startswith("url:"):
            url = stripped.split(":", 1)[1].strip() or None
            continue

        ingredient = stripped.lstrip("-*•").strip()
        if ingredient:
            ingredients.append(ingredient)

    if method_lines:
        method = "\n".join(method_lines).strip() or None
    return name, ingredients, url, method


def _parse_csv_recipes(path: Path) -> List[Tuple[str, List[str]]]:
    """
    Parse .csv recipes of the form:
      name,ingredients
      "Pasta","spaghetti; tomato sauce; basil"
    """
    recipes: List[Tuple[str, List[str]]] = []
    try:
        with path.open(newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get("name") or "").strip()
                raw_ing = (row.get("ingredients") or "").strip()
                if not name:
                    continue
                ing: List[str] = []
                if raw_ing:
                    parts = [p.strip() for p in raw_ing.replace(";", ",").split(",")]
                    ing = [p for p in parts if p]
                recipes.append((name, ing))
    except OSError:
        return []

    return recipes


def load_recipes() -> List[Recipe]:
    ensure_recipes_dir()
    recipes: List[Recipe] = []
    current_id: int = 1

    for entry in sorted(RECIPES_DIR.iterdir()):
        if not entry.is_file():
            continue

        suffix = entry.suffix.lower()
        if suffix in {".txt", ".md"}:
            name, ingredients, url, method = _parse_text_recipe(entry)
            if not name:
                continue
            recipes.append(
                Recipe(
                    id=current_id,
                    name=name,
                    ingredients=ingredients,
                    source_path=entry,
                    url=url,
                    method=method,
                )
            )
            current_id = current_id + 1  # type: ignore
        elif suffix == ".csv":
            for name, ingredients in _parse_csv_recipes(entry):
                recipes.append(
                    Recipe(
                        id=current_id,
                        name=name,
                        ingredients=ingredients,
                        source_path=entry,
                    )
                )
                current_id = current_id + 1  # type: ignore
        else:
            # unsupported type for now
            continue

    return recipes


# Initialize DB after parser helpers exist (Gunicorn imports this module)
init_db()
import_filesystem_recipes_if_empty()


@app.route("/", methods=["GET"])
def index():
    week_q = (request.args.get("week") or "").strip()
    today = date.today()
    week_start = monday_of(date.fromisoformat(week_q)) if week_q else monday_of(today)
    week_plan_id = get_or_create_week_plan_id(week_start)

    days = week_days(week_start)
    day_labels: List[Tuple[str, str, str]] = []
    for d in days:
        dt = date.fromisoformat(d)
        day_labels.append((d, dt.strftime("%A"), dt.strftime("%d %b")))

    recipes = get_recipes()
    day_meals = get_day_meals_by_type(week_plan_id)
    # Ensure all days exist in dict for template lookups
    for d in days:
        day_meals.setdefault(d, {})

    return render_template(
        "index.html",
        week_start=week_start.isoformat(),
        this_week=monday_of(today).isoformat(),
        next_week=(monday_of(today) + timedelta(days=7)).isoformat(),
        recipes=recipes,
        meal_types=MEAL_TYPES,
        day_labels=day_labels,
        day_meals=day_meals,
    )


@app.route("/add", methods=["POST"])
def add_meal():
    day = (request.form.get("day") or "").strip()
    meal_type = request.form.get("meal_type") or ""
    name = (request.form.get("name") or "").strip()
    notes = (request.form.get("notes") or "").strip()
    recipe_id_raw = request.form.get("recipe_id") or ""
    week_start_raw = (request.form.get("week_start") or "").strip()

    week_start = monday_of(date.fromisoformat(week_start_raw)) if week_start_raw else monday_of(date.today())
    week_plan_id = get_or_create_week_plan_id(week_start)

    recipe_id: Optional[int] = None
    if recipe_id_raw.isdigit():
        recipe_id = int(recipe_id_raw)

    recipes = get_recipes()
    selected_recipe = next((r for r in recipes if r.id == recipe_id), None) if recipe_id else None
    if selected_recipe and not name:
        name = selected_recipe.name

    if day and name and meal_type:
        set_day_meal_slot(week_plan_id=week_plan_id, day_date=day, meal_type=meal_type, name=name, recipes=recipes)

    return redirect(url_for("index", week=week_start.isoformat()))


@app.route("/day/<date_iso>/meals", methods=["POST"])
def update_day_meals(date_iso: str):
    """Replace one day's meals with four slots: breakfast, lunch, dinner, snack."""
    week_start_raw = (request.form.get("week_start") or "").strip()
    week_start = monday_of(date.fromisoformat(week_start_raw)) if week_start_raw else monday_of(date.today())
    week_plan_id = get_or_create_week_plan_id(week_start)

    name_by_type = {
        "Breakfast": (request.form.get("breakfast") or "").strip(),
        "Lunch": (request.form.get("lunch") or "").strip(),
        "Dinner": (request.form.get("dinner") or "").strip(),
        "Snack": (request.form.get("snack") or "").strip(),
    }

    recipes = get_recipes()
    replace_day_meals(week_plan_id=week_plan_id, day_date=date_iso, name_by_type=name_by_type, recipes=recipes)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"status": "success", "date": date_iso})
        
    return redirect(url_for("index", week=week_start.isoformat()))


@app.route("/clear", methods=["POST"])
def clear_plan():
    week_q = (request.args.get("week") or request.form.get("week_start") or "").strip()
    week_start = monday_of(date.fromisoformat(week_q)) if week_q else monday_of(date.today())
    week_plan_id = get_or_create_week_plan_id(week_start)
    db.execute("DELETE FROM week_meals WHERE week_plan_id = ?", (week_plan_id,))
    db.commit()
    return redirect(url_for("index", week=week_start.isoformat()))


@app.route("/recipes/upload", methods=["POST"])
def upload_recipes():
    """
    Accept one or more dropped/selected files and import recipes into SQLite.
    (We also save the original files into meal_planner/recipes as an optional library backup.)
    """
    ensure_recipes_dir()

    files = request.files.getlist("files")
    for f in files:
        if not f or not f.filename:
            continue
        filename = secure_filename(f.filename)
        if not filename:
            continue
        target = RECIPES_DIR / filename
        try:
            f.save(target)
        except OSError:
            continue
        suffix = target.suffix.lower()
        if suffix in {".txt", ".md"}:
            name, ingredients, url, method = _parse_text_recipe(target)
            if name:
                upsert_recipe(name=name, ingredients=ingredients, url=url, method=method)
        elif suffix == ".csv":
            for name, ingredients in _parse_csv_recipes(target):
                if name:
                    upsert_recipe(name=name, ingredients=ingredients, url=None, method=None)

    week_q = (request.args.get("week") or "").strip()
    return redirect(url_for("index", week=week_q) if week_q else url_for("index"))


def _parse_recipe_from_html(html: str, source_url: str) -> Dict[str, Any]:
    """Extract recipe name, ingredients, and method from HTML (JSON-LD or heuristics)."""
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        return {"name": "", "ingredients": [], "method": "", "url": source_url}

    soup = BeautifulSoup(html, "html.parser")
    name = ""
    ingredients: List[str] = []
    method = ""

    # JSON-LD Recipe
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
            if isinstance(data, dict) and data.get("@type") == "Recipe":
                name = (data.get("name") or "").strip()
                for ing in data.get("recipeIngredient") or []:
                    if isinstance(ing, str) and ing.strip():
                        ingredients.append(ing.strip())
                for step in data.get("recipeInstructions") or []:
                    if isinstance(step, dict) and step.get("text"):
                        method += str(step["text"]).strip() + "\n"  # type: ignore
                    elif isinstance(step, str) and step.strip():
                        method += (step.strip() + "\n")
                if name or ingredients:
                    break
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "Recipe":
                        name = (item.get("name") or "").strip()
                        for ing in item.get("recipeIngredient") or []:
                            if isinstance(ing, str) and ing.strip():
                                ingredients.append(ing.strip())
                        for step in item.get("recipeInstructions") or []:
                            if isinstance(step, dict) and step.get("text"):
                                method += str(step["text"]).strip() + "\n"  # type: ignore
                            elif isinstance(step, str) and step.strip():
                                method += (step.strip() + "\n")
                        if name or ingredients:
                            break
                if name or ingredients:
                    break
        except (json.JSONDecodeError, TypeError):
            continue

    # Fallback: common class/id patterns
    if not name:
        title = soup.find("h1") or soup.find(class_=re.compile(r"recipe[- ]?title", re.I)) or soup.find("title")
        if title and title.get_text():
            name = title.get_text(strip=True)[:200]
    if not ingredients:
        for sel in ["[itemprop='recipeIngredient']", ".recipe-ingredients li", ".ingredients li", ".wprm-recipe-ingredient"]:
            for el in soup.select(sel):
                t = el.get_text(strip=True)
                if t and len(t) > 1:
                    ingredients.append(t)
        if not ingredients and soup.find(class_=re.compile(r"ingredient", re.I)):
            div = soup.find(class_=re.compile(r"ingredient", re.I))
            if div:
                for li in div.find_all("li") or [div]:
                    t = li.get_text(strip=True)
                    if t:
                        ingredients.append(t)
    if not method:
        for sel in ["[itemprop='recipeInstructions']", ".recipe-instructions li", ".instructions li", ".wprm-recipe-instruction"]:
            for el in soup.select(sel):
                t = el.get_text(strip=True)
                if t:
                    method += str(t) + "\n"  # type: ignore

    return {"name": name or "Imported recipe", "ingredients": ingredients[:200], "method": method.strip(), "url": source_url}  # type: ignore


@app.route("/recipes/parse-url", methods=["GET", "POST"])
def parse_recipe_url():
    """Fetch URL and return extracted recipe as JSON for confirmation dialog."""
    url_value = (request.args.get("url") or request.form.get("url") or "").strip()
    if not url_value or not url_value.startswith(("http://", "https://")):
        return jsonify({"error": "Invalid URL"}), 400
    try:
        import requests  # type: ignore
        r = requests.get(
            url_value,
            timeout=(5, 10),
            headers={"User-Agent": "MealPlanner/1.0"},
            stream=True,
        )
        # limit response size to ~1MB
        content = b""
        for chunk in r.iter_content(chunk_size=65536):
            if not chunk:
                break
            content += chunk
            if len(content) > 1_000_000:
                break
        text = content.decode(r.encoding or "utf-8", errors="ignore")
        r.raise_for_status()
        out = _parse_recipe_from_html(text, url_value)
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/recipes/add-from-parsed", methods=["POST"])
def add_recipe_from_parsed():
    """Save recipe from confirmation dialog (name, ingredients, method, url)."""
    name = (request.form.get("name") or "").strip()
    url_value = (request.form.get("url") or "").strip()
    raw_ingredients = (request.form.get("ingredients") or "").strip()
    method = (request.form.get("method") or "").strip()

    if not name:
        return redirect(url_for("index"))
    ingredients = [ln.strip() for ln in raw_ingredients.splitlines() if ln.strip()]
    upsert_recipe(name=name, ingredients=ingredients, url=(url_value or None), method=(method or None))
    return redirect(url_for("recipes_list"))


@app.route("/recipes/add-url", methods=["POST"])
def add_recipe_from_url():
    """
    Create a simple text recipe file from a URL + ingredients entered in the UI.
    """
    name = (request.form.get("name") or "").strip()
    url_value = (request.form.get("url") or "").strip()
    raw_ingredients = (request.form.get("ingredients") or "").strip()

    if not name:
        return redirect(url_for("index"))
    ingredients = [ln.strip() for ln in raw_ingredients.splitlines() if ln.strip()]
    upsert_recipe(name=name, ingredients=ingredients, url=(url_value or None), method=None)
    return redirect(url_for("recipes_list"))


@app.route("/shopping-list", methods=["GET"])
def shopping_list():
    # Determine week (defaults to current week)
    week_q = (request.args.get("week") or "").strip()
    today = date.today()
    week_start = monday_of(date.fromisoformat(week_q)) if week_q else monday_of(today)
    week_plan_id = get_or_create_week_plan_id(week_start)

    # Pantry staples
    staple_names = {
        str(r["normalized_name"]).lower()
        for r in db.execute("SELECT normalized_name FROM pantry_staples")
    }
    items = build_shopping_list_for_week(week_plan_id)
    for it in items:
        it["is_staple"] = it["name"].lower() in staple_names

    # Order staples based on toggle
    pin_mode = (request.args.get("staples") or "bottom").lower()  # "top" or "bottom"
    if pin_mode == "top":
        items.sort(key=lambda x: (not x["is_staple"], x["name"].lower()))
    else:
        items.sort(key=lambda x: (x["is_staple"], x["name"].lower()))

    return render_template(
        "shopping_list.html",
        items=items,
        week_start=week_start.isoformat(),
        staples_mode=pin_mode,
    )


@app.route("/shopping-list/staple", methods=["POST"])
def toggle_staple():
    """
    Mark or unmark an item as pantry staple.
    """
    name = (request.form.get("name") or "").strip()
    week_start = (request.form.get("week_start") or "").strip()
    staples_mode = (request.form.get("staples_mode") or "bottom").strip()
    if not name:
        return redirect(url_for("shopping_list", week=week_start, staples=staples_mode))
    norm = name.lower()
    row = db.execute("SELECT id FROM pantry_staples WHERE normalized_name = ?", (norm,)).fetchone()
    if row:
        db.execute("DELETE FROM pantry_staples WHERE id = ?", (row["id"],))
    else:
        db.execute("INSERT INTO pantry_staples(normalized_name) VALUES (?)", (norm,))
    db.commit()
    return redirect(url_for("shopping_list", week=week_start, staples=staples_mode))


@app.route("/recipes", methods=["GET"])
def recipes_list():
    """List all saved recipes with links to edit."""
    return render_template("recipes_list.html", recipes=get_recipes())


@app.route("/recipes/edit/<int:recipe_id>", methods=["GET", "POST"])
def recipe_edit(recipe_id: int):
    """View or save edits for one recipe."""
    recipe = get_recipe(recipe_id)
    if not recipe:
        return redirect(url_for("recipes_list"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        url_value = (request.form.get("url") or "").strip()
        ingredients_text = (request.form.get("ingredients") or "").strip()
        method = (request.form.get("method") or "").strip()
        if not name:
            return redirect(url_for("recipe_edit", recipe_id=recipe_id))
        update_recipe(recipe_id=recipe_id, name=name, url=(url_value or None), ingredients_text=ingredients_text, method=(method or None))
        return redirect(url_for("recipes_list"))

    return render_template(
        "recipe_edit.html",
        recipe=recipe,
        ingredients_text="\n".join(recipe.ingredients),
        can_edit=True,
    )


@app.route("/ingredients/harmonize", methods=["GET"])
def harmonize_ingredients():
    """Find ingredients that share the same normalized name but have different raw text."""
    recipes = get_recipes()
    clusters_map = {}
    
    for r in recipes:
        for line in r.ingredients:
            try:
                p = parse_ingredient_line_uk(line)
                # Group by singularized name
                key_name = p["name_singular"].lower()
                if not key_name:
                    continue
                
                # Group SUGGESTIONS strictly by (singular_name, qty_uk, unit_uk)
                # This ensures we don't suggest replacing "50g Parmesan" with "100g Parmesan"
                cluster_key = (key_name, p["qty_uk"], p["unit_uk"])
                
                if cluster_key not in clusters_map:
                    clusters_map[cluster_key] = {
                        "name": p["normalized_name"], 
                        "qty": p["qty_uk"],
                        "unit": p["unit_uk"],
                        "variations": {}
                    }
                
                v_map = clusters_map[cluster_key]["variations"]
                # Store extra info about each variation for the UI
                if line not in v_map:
                    v_map[line] = {
                        "qty": p["qty_uk"],
                        "unit": p["unit_uk"],
                        "recipes": []
                    }
                v_map[line]["recipes"].append(r.name)
            except Exception:
                continue

    # Filter to clusters with > 1 variation (actual naming inconsistencies for SAME amount)
    suggestions = [c for c in clusters_map.values() if len(c["variations"]) > 1]
    suggestions.sort(key=lambda x: len(x["variations"]), reverse=True)
    
    # All unique ingredients for the "full list" view (Grouped by name only for searching)
    all_raw_items = []
    # We rebuild a name-only map for the table to keep it easy to browse
    name_only_map = {}
    for cluster_data in clusters_map.values():
        name = cluster_data["name"]
        if name not in name_only_map:
            name_only_map[name] = []
        for raw_text, var_data in cluster_data["variations"].items():
            name_only_map[name].append({
                "raw": raw_text,
                "recipes": var_data["recipes"],
                "qty": var_data["qty"],
                "unit": var_data["unit"]
            })
    
    table_items = []
    for name in sorted(name_only_map.keys(), key=lambda x: x.lower()):
        for item in name_only_map[name]:
            table_items.append({
                "raw": item["raw"],
                "norm": name,
                "recipes": item["recipes"],
                "qty": item["qty"],
                "unit": item["unit"]
            })

    return render_template("ingredients_harmonize.html", suggestions=suggestions, all_items=table_items)


@app.route("/ingredients/harmonize/apply", methods=["POST"])
def harmonize_apply():
    """Bulk replace one or more ingredient strings with a single target across all recipes.

    Accepts multiple `old_text` values (e.g. all variations in a group) and one
    `new_text` target, which may be an existing variation or a custom-typed string.
    """
    old_texts = {t.strip() for t in request.form.getlist("old_text") if t.strip()}
    new_text = (request.form.get("new_text") or "").strip()

    # Don't replace the target with itself (the chosen variation may be in the list).
    old_texts.discard(new_text)

    if not old_texts or not new_text:
        return redirect(url_for("harmonize_ingredients"))

    rows = db.execute("SELECT id, ingredients_text FROM recipes").fetchall()
    for row in rows:
        text = row["ingredients_text"] or ""
        lines = text.splitlines()
        new_lines = []
        changed = False
        for ln in lines:
            if ln.strip() in old_texts:
                new_lines.append(new_text)
                changed = True
            else:
                new_lines.append(ln)

        if changed:
            db.execute("UPDATE recipes SET ingredients_text = ? WHERE id = ?", ("\n".join(new_lines), row["id"]))
            
    db.commit()
    return redirect(url_for("harmonize_ingredients"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8717, debug=True)

