// Owner: Agent B. Onboarding modal, profile chip, and static profile notes (AI_RULES §9).
(function () {
  "use strict";

  var KEY = "fe_profile";
  var AGES = [["18-24", "18–24"], ["25-34", "25–34"], ["35-49", "35–49"], ["50+", "50+"]];
  var RISKS = [["low", "Low"], ["medium", "Medium"], ["high", "High"]];
  var NOTES = {
    low: "You chose low risk. Some people with this preference focus on steady, diversified investments. Every investment can lose value.",
    medium: "You chose medium risk. Some people with this preference balance growth and stability. Every investment can lose value.",
    high: "You chose high risk. Higher possible returns usually come with bigger possible losses. Every investment can lose value.",
  };

  var profile = null;
  var modal = null;
  var opener = null;

  function label(pairs, value) {
    for (var i = 0; i < pairs.length; i++) if (pairs[i][0] === value) return pairs[i][1];
    return null;
  }

  function isValid(p) {
    return !!p && label(AGES, p.age_range) !== null && label(RISKS, p.risk) !== null;
  }

  function load() {
    try {
      var stored = JSON.parse(localStorage.getItem(KEY));
      return isValid(stored) ? { age_range: stored.age_range, risk: stored.risk } : null;
    } catch (e) {
      return null;
    }
  }

  function save(p) {
    try {
      localStorage.setItem(KEY, JSON.stringify(p));
    } catch (e) { /* storage unavailable: keep the profile for this session only */ }
  }

  function renderChip() {
    var chip = document.getElementById("profile-chip");
    if (!chip) return;
    chip.textContent = profile ? label(AGES, profile.age_range) + " · " + label(RISKS, profile.risk) + " risk" : "Set your profile";
    chip.setAttribute("aria-label", "Edit your profile: " + chip.textContent);
  }

  function select(id, text, pairs, value) {
    var wrap = document.createElement("label");
    wrap.className = "field";
    wrap.htmlFor = id;
    wrap.textContent = text;
    var sel = document.createElement("select");
    sel.id = id;
    pairs.forEach(function (pair) {
      var opt = document.createElement("option");
      opt.value = pair[0];
      opt.textContent = pair[1];
      sel.appendChild(opt);
    });
    sel.value = value;
    return [wrap, sel];
  }

  function close() {
    if (!modal) return;
    modal.remove();
    modal = null;
    document.removeEventListener("keydown", onKey);
    if (opener && opener.focus) opener.focus();
  }

  function onKey(e) {
    if (e.key === "Escape" && profile) close(); // first-time onboarding must be completed
  }

  function open() {
    if (modal) return;
    opener = document.activeElement;
    var current = profile || { age_range: "25-34", risk: "medium" };

    modal = document.createElement("div");
    modal.className = "modal-backdrop";
    var box = document.createElement("form");
    box.className = "modal";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-labelledby", "profile-title");

    var title = document.createElement("h2");
    title.id = "profile-title";
    title.textContent = "Tell us a little about you";
    var age = select("profile-age", "Age range", AGES, current.age_range);
    var risk = select("profile-risk", "Risk preference", RISKS, current.risk);
    var note = document.createElement("p");
    note.className = "muted";
    note.textContent = "This only changes how things are explained. It is not advice.";

    var actions = document.createElement("div");
    actions.className = "modal-actions";
    if (profile) {
      var cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "button-secondary";
      cancel.textContent = "Cancel";
      cancel.addEventListener("click", close);
      actions.appendChild(cancel);
    }
    var submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "button-primary";
    submit.textContent = "Save";
    actions.appendChild(submit);

    [title, age[0], age[1], risk[0], risk[1], note, actions].forEach(function (n) { box.appendChild(n); });
    box.addEventListener("submit", function (e) {
      e.preventDefault();
      var next = { age_range: age[1].value, risk: risk[1].value };
      if (!isValid(next)) return;
      profile = next;
      save(profile);
      renderChip();
      close();
      document.dispatchEvent(new CustomEvent("app:profile-changed", { detail: { profile: profile } }));
    });

    modal.appendChild(box);
    document.body.appendChild(modal);
    document.addEventListener("keydown", onKey);
    age[1].focus();
  }

  window.Profile = {
    init: function () {
      profile = load();
      renderChip();
      var chip = document.getElementById("profile-chip");
      if (chip) chip.addEventListener("click", open);
      if (!profile) open();
    },
    get: function () {
      return profile ? { age_range: profile.age_range, risk: profile.risk } : null;
    },
    open: open,
    noteFor: function (risk) {
      return NOTES[risk] || null;
    },
  };
})();
