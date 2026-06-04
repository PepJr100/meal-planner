# Roadmap

Prioritised plan for what's next, after the v1.0.0 release. Items were chosen by
ruthless impact-vs-effort-vs-risk evaluation for a personal/household self-hosted
app — see [Deliberately deferred](#deliberately-deferred) for what was cut and why.

## Why these, in this order

Two facts drive the priorities:

1. **There are no tests** for a ~1,100-line `app.py` whose core ingredient parsing
   and shopping-list aggregation has already shipped two silent bugs (a dropped
   quantity in aggregation; fractional amounts rounded `0.3 → 0`).
2. The **shopping list has no notion of servings or household size** — it sums
   recipe quantities exactly as written.

So tests come first (they make everything else safe to change), then the biggest
functional gap (scaling), then cheap data-safety insurance (backup), then a
high-visibility UX win (favourites + palette relayout).

## Sequence

```
#1 Tests ──┬──> #2 Servings + scaling   (edits the now-covered aggregation)
           └──> #3 Backup / export      (independent)
#4 Favourites + relayout  ── can start anytime; doesn't touch the fragile core
```

`#1` is the gate for `#2`. `#3` and `#4` are independent and can run in parallel.

---

## #1 — Test suite for parsing + aggregation

**Goal.** Lock down the fragile core so future changes can't silently regress it.

**Scope.**
- Add `pytest` as a dev dependency and a `tests/` package.
- ~20–30 tests over `parse_ingredient_line_uk`, `build_shopping_list_for_week`,
  and the `singularize` helper.
- Explicitly cover the historical bugs:
  - quantities summing across multiple lines even when an earlier line had none;
  - fractional quantities preserved (no `0.3 → 0`);
  - unit-less quantities kept as a "count" measure (e.g. `Onion (1)`);
  - plurals merging via singularisation (`spring onions` ≡ `spring onion`).
- Wire `pytest` into the CI workflow so it runs on every push/PR.

**Why.** Highest risk-reduction per hour; unblocks #2 and any future refactor.

**Acceptance.** `pytest` green locally and in CI; the four bug classes above each
have a failing-before / passing-after test.

## #2 — Recipe servings + scaling

**Goal.** Make shopping-list quantities trustworthy for the actual household.

**Scope.**
- Add a `serves` field to recipes (default sensible, e.g. 2 or 4).
- Add a target household/portion size (per plan, or a global setting).
- When aggregating, scale each recipe's ingredient quantities by
  `target / serves` before summing.
- Surface the scaling in the UI (show the factor / scaled amounts).

**Why.** The single biggest functional gap — without it the list quantities are
just the recipe's raw numbers.

**Dependencies.** Do **after #1**; it modifies `build_shopping_list_for_week`.

**Acceptance.** A recipe that "serves 4" contributes half its quantities when the
target is 2; covered by tests added in #1's suite.

## #3 — Backup / export + import

**Goal.** Protect an irreplaceable, hand-curated recipe library.

**Scope.**
- One-click **export**: download the SQLite DB and/or a JSON dump of recipes +
  plans.
- **Import**: restore from that file (with a confirmation / merge-or-replace
  choice).

**Why.** The harmonizer performs irreversible bulk rewrites behind a single
`confirm()`, and a lost Docker volume wipes everything. Cheap insurance.

**Acceptance.** Export then wipe then import round-trips the library and plans
intact.

## #4 — Favourite meals + relocate the recipe palette

**Goal.** Fix the cramped recipe palette and surface go-to meals in the planning
loop.

**Current problem.** "Available recipes" is the **last** card in the right-hand
`.sidebar` (below Add-a-meal, file upload, and URL fetch), so it's squeezed into
the bottom-right while the area under the Monday–Sunday grid sits empty.

**Scope.**
- **Data:** add an `is_favourite` flag to recipes + an idempotent migration and a
  toggle endpoint.
- **Layout:** move the `.existing-recipes` block out of `.sidebar` into the
  `.planner` column, **below `.week-grid`**, as a full-width, wrapping tray of
  draggable recipe chips that uses the empty space. Keep the `.recipes-list li`
  hook so the existing drag-to-slot JS keeps working.
- **Favourites-first:** a ★ toggle on each chip (and on the Saved Recipes page);
  order the tray with favourites at the front.
- Collapse gracefully on narrow screens (the tray already wraps).

**Why.** Improves the core weekly action (dragging recipes into slots) and removes
a real layout wart in one change. Independent of the fragile core, so low risk.

**Acceptance.** Favourited recipes appear first in a full-width tray beneath the
week grid; drag-to-slot still works; the flag persists across restarts.

---

## Deliberately deferred

Cut for poor ROI on a personal household tool (revisit if needs change):

- **Nutrition / macros** — needs an external food database; scope creep.
- **Pantry inventory** — heavy to build and keep accurate; staples cover ~80%.
- **External list integrations** (Todoist, email, ICS) — the copy buttons already
  cover "get it to my phone."
- **Auth / password protection** — only worth it if exposed beyond the LAN.
- **`app.py` blueprint refactor** — maintainability only; do it *after* #1, never
  before.

**Strongest runner-up (possible 5th):** shopping list grouped by aisle/category —
pairs naturally with the copy/export flow.

> Earlier shortlist items dropped at the user's request: an interactive check-off
> shopping list, and a "copy last week" / plan-templates feature.
