/*
 * Shared theme handling for every page.
 * Loaded synchronously in <head> so the saved theme is applied before first
 * paint (no flash). Light is the default; "dark" is the only stored value.
 */
(function () {
  var root = document.documentElement;

  // Apply saved theme immediately, before the page paints.
  if (localStorage.getItem("theme") === "dark") {
    root.setAttribute("data-theme", "dark");
  }

  function currentTheme() {
    return localStorage.getItem("theme") === "dark" ? "dark" : "light";
  }

  function updateLabel(theme) {
    var toggle = document.getElementById("theme-toggle");
    if (toggle) toggle.textContent = "Theme: " + theme;
  }

  // Wire up the toggle button once the DOM is ready.
  document.addEventListener("DOMContentLoaded", function () {
    updateLabel(currentTheme());
    var toggle = document.getElementById("theme-toggle");
    if (!toggle) return;
    toggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      localStorage.setItem("theme", next);
      if (next === "dark") {
        root.setAttribute("data-theme", "dark");
      } else {
        root.removeAttribute("data-theme");
      }
      updateLabel(next);
    });
  });
})();
