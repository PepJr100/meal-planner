# Development history

Developer-facing notes on how Meal Planner's features were built. This is a
historical record — for current behaviour, see the [User Guide](../UserGuide.md)
and the code itself. (Consolidated from the earlier `task.md`, `walkthrough.md`,
and `implementation_plan.md`.)

---

## Shopping-list aggregation

- **Quantity aggregation bug.** `build_shopping_list_for_week` seeded a bucket's
  `qty_uk` from the first line only, so a quantity-less line processed first (e.g.
  "Gnocchi") pinned the bucket to `None`, and the `qty_uk is not None` guard then
  dropped every later quantity in that bucket. Fixed by accumulating lazily — the
  first quantity seeds the sum, so a bucket is `None` only when no line ever carried
  a quantity.
- **`Basmati rice, g (150)` "missing quantity".** Not actually a parse failure (the
  NLP parser plus a proactive parenthetical catch handles it); it was the
  aggregation bug above surfacing on the list.
- **Unit-less quantities** (e.g. `Onion (1)`) were being discarded by the unit
  normaliser; they're now preserved as a "count" measure.
- Singularised ingredient names are used as the aggregation key so plurals merge
  automatically (e.g. `spring onions` → `spring onion`).

## Ingredient harmonizer

- **Clustering.** Ingredients are grouped by singularised base name. Suggestions use
  *strict* clustering on `(name_singular, qty_uk, unit_uk)` and only show groups with
  more than one variation, so `Parmesan 50g` and `Parmesan 30g` stay distinct.
- **Parsing.** `parse_ingredient_line_uk` proactively extracts quantities from
  `Name (Number)` forms when the parser otherwise misses them (e.g. `Eggs (6)`), and
  parenthetical numbers like `(1)` are stripped from names during clustering.
- **Bulk apply.** A `POST` endpoint rewrites a matching ingredient string to a chosen
  target across every recipe. The UI later moved from a per-variation dropdown to a
  single **per-group** dropdown with an **"Other"** free-text option for a custom
  replacement.
- The **"All unique ingredients"** table offers a per-string Rename for one-off fixes.
- *Superseded:* an earlier per-item `confirm()` measure-mismatch guard was removed
  once suggestion groups were constrained to a single measure, making it dead code.

## Drag-and-drop rescheduling

- `draggable` attributes + CSS drag states on recipe sources and meal slots.
- Recipe-to-slot drop populates a slot; slot-to-slot drop swaps two slots' values.
- Auto-save was refactored onto the Fetch API for background saves — this removed
  page flicker and fixed a bug where competing reloads could make meals "disappear"
  during a swap.
- Polish: smooth transitions, ghosting on the dragged item, drop-target highlighting.

## Recipe library UI

- The Saved Recipes page uses a two-column layout: a recipe grid plus a sticky side
  panel. Clicking a recipe opens its details/edit form on the right instead of
  navigating away. Normal recipes are editable; CSV-sourced recipes open read-only.
- Recipes missing more than four ingredient amounts get a subtle highlight and a
  "Missing amounts" tag, via a fast regex heuristic at render time.

## Shopping-list UI

- A copy-to-clipboard control (later split into names-only and with-quantities
  buttons, with an `execCommand` fallback for non-secure/LAN contexts).
- Distinct styles for **Mark as staple** (plain) vs **Unmark staple** (soft tint).
