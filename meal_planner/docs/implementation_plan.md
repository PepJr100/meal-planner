4. Add subtle highlighting to recipes missing more than 4 ingredient amounts in the Saved Recipes list.
5. Harmonize Shopping List ingredients to merge duplicates like "Basmati rice" and "Basmati rice, g (150)".
6. **New Feature: Ingredient Harmonization Tool**
   - Create a page that lists all unique ingredient lines across all recipes.
   - Suggest harmonizations by grouping ingredients that share the same "normalized name".
   - Provide a UI to bulk-update multiple recipes to use a consistent ingredient string.

---

## Proposed Changes

### `meal_planner/app.py`
- **Singularization**: Implement a `singularize()` helper to normalize ingredient names (e.g., "spring onions" -> "spring onion").
- **Ingredient Parsing**: 
  - Update `parse_ingredient_line_uk` to proactively extract quantities from `Name (Number)` formats if the parser fails.
  - Special handling for "Eggs" and similar items where the quantity is often in parentheses.
- **Aggregation**: Use the singularized name in the shopping list aggregation key to automatically merge plurals.
- **Harmonization Grouping (Suggestions)**:
  - **Strict Clustering**: Group suggestions by `(name_singular, qty_uk, unit_uk)`.
  - Only show clusters where `variations > 1`.
  - This preserves "Parmesan cheese 50g" and "Parmesan cheese 30g" as distinct entities that don't need harmonization.
- **All Items View**: Maintain the search/bulk view grouped by name so users can see all variations of an ingredient in one place.

### `meal_planner/templates/index.html`
- **Recipe Drag Sources**: Add `draggable="true"` and `data-name="{{ r.name }}"` to the list items in the "Available recipes" section.
- **Draggable Meal Slots**: Add `draggable="true"` to `.meal-slot` containers.
- **JS Event Handlers**:
  - `dragstart`: 
    - For recipes: Store the recipe name in `dataTransfer`.
    - For meal slots: Store the slot ID/ref and its current value. Add a `dragging` class.
  - `dragover`: Allow drop, add `drop-target` class to the `.meal-slot`.
  - `dragleave`: Remove `drop-target` class.
  - `drop`:
    - If dragging from recipe: Set the target input value to the recipe name.
    - If dragging from slot: Swap values between the source and target inputs.
    - Post-drop: Trigger a `change` event on affected inputs to fire existing auto-save.
  - `dragend`: Remove `dragging` class.

### `meal_planner/static/style.css`
- **Visual Feedback**:
  - `.meal-slot.drop-target`: Highlight with a thick border or primary glow.
  - `.meal-slot.dragging`: Reduce opacity or add a "picked up" transform.
  - `.recipes-list li[draggable="true"]`: Add a `move` cursor and hover effect.

## Verification Plan

### Automated Tests
- Test the grouping logic with a script to ensure "Basmati rice" and "Basmati rice, g (150)" land in the same cluster.
- Test the string replacement logic to ensure it doesn't accidentally mangle recipes with partial matches.

### `meal_planner/templates/shopping_list.html`
- Add a `Copy ingredients` button near the list headers.
- Attach an inline JS script to parse the list DOM nodes, extract text, format into a clipboard string, and copy it using `navigator.clipboard.writeText`.
- Apply the new distinct classes to the "Mark/Unmark staple" buttons based on the `item.is_staple` boolean.

### `meal_planner/templates/recipes_list.html`
- Refactor the page layout CSS class from `layout-single` (one column) to `layout` (two columns).
- Output the recipe grid in the left column.
- Create a new sticky sidebar section (`#recipe-sidebar`) on the right side.
- Instead of using `href` standard links, the recipe cards will execute a JavaScript function `showRecipe(id)`.
- The template will render the full edit forms for each recipe hidden inside `<template>` tags. The JS function will copy the correct template into the sidebar.

---

## Verification Plan

### Automated Tests
- Validate that `app.py` passes compilation (`python -c "import meal_planner.app"`).

### Manual Verification
1. Open the UI to `/shopping-list`, click "Copy ingredients", and paste to ensure it captures the exact contents.
2. Toggle "Mark/Unmark staple" and observe the different button colors.
3. Navigate to `/recipes`, observe the two-column sidebar loading properly, click a recipe, and ensure the edit form pops open on the right instead of reloading.
4. Verify that recipes with >4 missing amount ingredients show a subtle orange highlight.
