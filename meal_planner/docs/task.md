# Task: Harmonize Shopping List Ingredients

- [ ] Investigate `build_shopping_list_for_week` aggregation logic
- [ ] Determine why "Basmati rice, g (150)" fails parsing
- [x] Refinement: Make Recipe Sidebar sticky so it stays on screen
- [x] Feature 5: Ingredient Harmonization Page
  - [x] Implement clustering logic in `app.py`
  - [x] Create `ingredients_harmonize.html` template
  - [x] Add `POST` endpoint for bulk-applying harmonizations
  - [x] Add navigation link to the new tool
  - [x] Refinement: Strict clustering (Suggestions should only be naming variations for SAME amount)
  - [x] Fix: Proactively extract parenthetical quantities (e.g. Eggs (6))
  - [x] Fix: Broken 'Rename' button (missing CSS styles)
  - [x] Refinement: Update "Copy list" to "Copy Shopping list" and copy names only

# Task: Drag-and-Drop Rescheduling
- [x] Add `draggable` attributes and CSS for drag states (Slots & Recipes)
- [x] Implement JS event listeners for recipe-to-slot drop
- [x] Implement JS event listeners for slot-to-slot swap
- [x] Sync swapped values with backend via auto-save
- [x] Fix: Disappearing meals during swap (refactored to Fetch API background saves)
