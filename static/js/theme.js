// Theme: follows the system unless the visitor picks Light or Dark. Loaded in <head> (not deferred) so the chosen
// theme applies before the first paint. The choice is a per-browser convenience in localStorage.
(function () {
  "use strict";

  var KEY = "theme";
  var ORDER = ["system", "light", "dark"];
  var LABELS = { system: "System", light: "Light", dark: "Dark" };

  function read() {
    try {
      var v = window.localStorage.getItem(KEY);
      return v === "light" || v === "dark" ? v : "system";
    } catch (e) {
      return "system";
    }
  }

  function apply(mode) {
    if (mode === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", mode);
  }

  function save(mode) {
    try {
      if (mode === "system") window.localStorage.removeItem(KEY);
      else window.localStorage.setItem(KEY, mode);
    } catch (e) { /* storage unavailable: the choice lasts for this page only */ }
  }

  apply(read());

  document.addEventListener("DOMContentLoaded", function () {
    var button = document.getElementById("theme-toggle");
    if (!button) return;
    function label(mode) {
      button.textContent = "Theme: " + LABELS[mode];
      button.setAttribute("aria-label", "Theme: " + LABELS[mode] + ". Activate to change.");
    }
    label(read());
    button.addEventListener("click", function () {
      var next = ORDER[(ORDER.indexOf(read()) + 1) % ORDER.length];
      save(next);
      apply(next);
      label(next);
    });
  });
})();
