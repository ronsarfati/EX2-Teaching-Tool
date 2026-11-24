/* Manual colour theme for the lecturer pages: auto (OS setting) -> light -> dark.
   Loaded in <head> so the saved theme is applied before the first paint (no flash). */
(function () {
  var KEY = "theme";
  var ORDER = ["auto", "light", "dark"];
  var root = document.documentElement;

  function load() {
    try {
      var saved = window.localStorage.getItem(KEY);
      return ORDER.indexOf(saved) >= 0 ? saved : "auto";
    } catch (error) {
      return "auto"; /* storage blocked (private mode): keep following the OS */
    }
  }

  function save(theme) {
    try {
      window.localStorage.setItem(KEY, theme);
    } catch (error) {
      /* the choice then only lasts for this page view */
    }
  }

  function apply(theme) {
    if (theme === "auto") {
      root.removeAttribute("data-theme"); /* the CSS media query decides */
    } else {
      root.setAttribute("data-theme", theme);
    }
    var button = document.getElementById("theme-toggle");
    if (button) {
      button.textContent = theme.charAt(0).toUpperCase() + theme.slice(1);
      button.setAttribute("aria-label", "Colour theme: " + theme);
    }
  }

  var current = load();
  apply(current);
  document.addEventListener("DOMContentLoaded", function () {
    var button = document.getElementById("theme-toggle");
    apply(current);
    if (button) {
      button.addEventListener("click", function () {
        current = ORDER[(ORDER.indexOf(current) + 1) % ORDER.length];
        save(current);
        apply(current);
      });
    }
  });
})();
