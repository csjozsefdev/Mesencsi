(() => {
  /**
   * Global namespace for the storefront (classic scripts, hybrid migration).
   * Keeps shared utilities in one place without changing app behavior.
   */
  const ns = (window.Mesencsi = window.Mesencsi || {});

  // Element helper (kept identical to the in-app helper).
  if (!ns.$) {
    ns.$ = (id) => document.getElementById(id);
  }
})();
