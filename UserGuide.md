# Meal Planner — User Guide

A walkthrough of everything Meal Planner can do, page by page. For installation and
hosting, see the [README](README.md).

## Contents

- [Getting started](#getting-started)
- [The weekly planner](#the-weekly-planner)
- [The shopping list](#the-shopping-list)
  - [Servings & scaling](#servings--scaling)
- [The recipe library](#the-recipe-library)
- [Importing a recipe from a URL](#importing-a-recipe-from-a-url)
- [The ingredient harmonizer](#the-ingredient-harmonizer)
- [Backup & restore](#backup--restore)
- [Themes](#themes)
- [Tips & FAQ](#tips--faq)

---

## Getting started

Open the app in your browser (by default <http://localhost:8717>). You land on the
**weekly planner**. The top bar links the four main pages — **Planner**,
**Saved recipes**, **Shopping list**, **Harmonizer** — and a **Theme** toggle.

On first launch the app seeds its recipe library from the bundled recipe files, so
you'll have something to plan with straight away.

---

## The weekly planner

![Weekly planner](screenshots/planner.png)

The planner is a Monday–Sunday grid. Each day has four slots: **Breakfast**,
**Lunch**, **Dinner**, and **Snack**.

**Add a meal by dragging.** Drag a recipe from the sidebar on the left into any
slot and it drops straight in.

**Rearrange by dragging.** Drag one filled slot onto another to swap the two meals.

**Type directly.** You can also click a slot and type a meal name by hand — handy
for one-offs that aren't in your recipe library.

**Everything auto-saves.** Changes are saved in the background as you make them —
there are no Save buttons and no page reloads, so the grid never flickers or loses
a meal mid-swap.

**Switching weeks.** The planner shows one week at a time; use the week navigation
to move between weeks. Each week keeps its own plan.

---

## The shopping list

![Weekly shopping list](screenshots/shopping-list.png)

The shopping list reads every meal in the current week's plan, looks up each
recipe's ingredients, and combines them into one consolidated list.

**Smart combining.** Quantities for the same ingredient are added together across
all the meals in the week, and units are normalised to UK conventions (g, kg, ml,
l, tsp, tbsp; `cup` is treated as US). Fractional amounts are shown as-is
(e.g. `0.3`), not rounded away.

### Servings & scaling

A recipe can record how many portions it makes (its **Serves** value). On the
shopping list, set **Servings per meal** to your household size and any recipe with
a Serves value is scaled to match — a "serves 4" recipe contributes half its
quantities when you want 2 portions. Recipes without a Serves value are left exactly
as written, so this is entirely opt-in. The setting is remembered between visits.

**Pantry staples.** Use **Mark as staple** on items you usually keep at home (salt,
oil, etc.). Staples are grouped together and can be pinned to the **top** or
**bottom** of the list with the **Pin top / Pin bottom** control, so they don't
clutter the things you actually need to buy. **Unmark staple** moves an item back.

**Copying the list.** Two buttons copy the list to your clipboard:

- **Copy Shopping list** — item names only. Best for pasting into a grocer's bulk
  search, where quantities can interfere with matching.
- **Copy Shopping list (With quantities)** — each item with its combined amount,
  e.g. `Arborio rice — 150 g`.

Both work even when the app is served over plain HTTP on your home network.

---

## The recipe library

![Saved recipes](screenshots/harmonizer.png)

The **Saved recipes** page is your recipe database. It opens with a two-column
layout: the recipe grid on the left and a details/edit panel on the right.

- **Click a recipe** to open it in the side panel without leaving the page.
- **Edit** a recipe's name, ingredients, and method, then save.
- **Add** a new recipe from scratch, or **upload** recipe files.
- Recipes imported from CSV open in a read-only view.

### Recipe text format

When adding or editing a recipe by hand, ingredients follow a simple convention:

```
Chilli Con Carne
URL: https://example.com/chilli        (optional)
SERVES: 4                              (optional)

- Onion (1)
- Kidney Beans, g (400)
- Beef mince, g (500)
- Sour Cream, pot (1)

METHOD:                                 (optional)
Brown the mince, add everything else, simmer 30 min.
```

- The first non-empty line is the **recipe name**.
- An optional `SERVES:` line says how many portions the recipe makes — the shopping
  list uses it to scale quantities (see [Servings & scaling](#servings--scaling)).
  In the editor it's the **Serves** field.
- Lines starting with `-`, `*`, or `•` are **ingredients**, written as
  `Name, <unit> (<quantity>)`. The unit and comma are optional, so
  `Bananas (5)` and `Cheddar Cheese, g (250)` are both fine.
- An optional `METHOD:` line begins the method section.

---

## Importing a recipe from a URL

Paste a recipe page's web address and the app fetches it and extracts the name,
ingredients, and method automatically (from structured recipe data or common page
patterns). You get a **confirmation step** to review and tweak what it found before
saving, so a messy source page never silently pollutes your library.

---

## The ingredient harmonizer

![Ingredient harmonizer](screenshots/harmonizer.png)

Over time the same ingredient creeps into your recipes under slightly different
names — `Parmesan` vs `parmesan cheese`, `spring onions` vs `spring onion`. The
**Harmonizer** finds these and lets you standardise them in bulk.

### Suggested harmonizations

The top section groups ingredients that share a base name **and the same amount**
(so it never suggests merging `50 g Parmesan` with `100 g Parmesan` — those are
genuinely different). Each card lists the variations it found and where they're
used.

To clean up a group:

1. Open the **Harmonize all to…** dropdown for that group.
2. Pick the spelling you want to keep — either one of the existing variations, or
   choose **Other (type your own)…** to type a custom replacement that isn't in the
   list yet.
3. Click **Harmonize group** and confirm.

Every matching ingredient line across all your recipes is rewritten to the chosen
text in one go.

### All unique ingredients

Below the suggestions is a searchable table of every distinct ingredient string in
your library, with a **Rename** button on each. Renaming replaces that exact string
everywhere it appears — useful for one-off fixes the suggestion grouping didn't
surface.

---

## Backup & restore

The **Backup** link in the top bar opens a page where you can safeguard your data.

- **Export** — download everything (recipes, week plans, planned meals, staples, and
  settings) as a single **JSON backup** file, or grab a raw copy of the **`.db`**
  database. Do this periodically, and especially before a big tidy-up in the
  Harmonizer (whose bulk renames can't be undone).
- **Restore** — upload a JSON backup to bring your data back. Importing **replaces**
  everything currently in the app with the file's contents, after a confirmation
  prompt, so it also works for moving your library to another machine.

## Themes

![Dark mode](screenshots/planner-dark.png)

Use the **Theme** button in the top bar to switch between a warm light palette and
an earthy dark mode. Your choice is remembered as you move between pages. Light is
the default.

---

## Tips & FAQ

**My shopping list is empty.** It's built from the meals planned for the current
week. Add some recipes to the planner grid first, then revisit the shopping list.

**An ingredient shows no quantity.** If none of the recipes for that week gave the
ingredient an amount, it appears without one — add a quantity in the recipe to have
it counted and summed.

**Where is my data stored?** Everything lives in a single SQLite database file. When
running in Docker, mount a volume so it persists across restarts (see the README).

**Two recipes use different names for the same thing.** Run the **Harmonizer** to
merge them, then your shopping list will combine their quantities automatically.
