/**
 * Password visibility toggle — attach to inputs via data-password-toggle-for="inputId"
 * or wrap input in .password-field-wrap with a sibling button[data-password-toggle].
 */
(function () {
  function labelForHidden(isHidden) {
    return isHidden ? "Jelszó megjelenítése" : "Jelszó elrejtése";
  }

  function bindToggle(btn, input) {
    if (!btn || !input || btn.dataset.pwToggleBound === "1") return;
    btn.dataset.pwToggleBound = "1";
    btn.type = "button";
    btn.setAttribute("aria-pressed", "false");
    if (!btn.getAttribute("aria-label")) btn.setAttribute("aria-label", labelForHidden(true));
    btn.addEventListener("click", function () {
      const hidden = input.type === "password";
      input.type = hidden ? "text" : "password";
      btn.setAttribute("aria-pressed", hidden ? "true" : "false");
      btn.setAttribute("aria-label", labelForHidden(!hidden));
    });
  }

  function initPasswordToggles(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll("[data-password-toggle-for]").forEach(function (btn) {
      const id = btn.getAttribute("data-password-toggle-for");
      const input = id ? document.getElementById(id) : null;
      bindToggle(btn, input);
    });
    scope.querySelectorAll(".password-field-wrap").forEach(function (wrap) {
      const input = wrap.querySelector('input[type="password"], input[type="text"][data-password-field]');
      const btn = wrap.querySelector("[data-password-toggle]");
      if (input && !input.hasAttribute("data-password-field")) input.setAttribute("data-password-field", "1");
      bindToggle(btn, input);
    });
  }

  window.MesencsiPasswordToggle = { init: initPasswordToggles };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initPasswordToggles(document);
    });
  } else {
    initPasswordToggles(document);
  }
})();
