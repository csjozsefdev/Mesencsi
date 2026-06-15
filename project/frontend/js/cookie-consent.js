(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const CONSENT_KEY = "mesencsi_cookie_consent_v1";
  const POLICY_VERSION = "2026-06-14";
  const OPTIONAL_EXACT_KEYS = new Set([
    "mesencsi_user_profile_json",
    "mesencsi_selected_coupon",
    "admin_role",
    "admin_username",
    "debugStorybookV2",
  ]);
  const OPTIONAL_PREFIXES = ["mesencsi_cart_"];

  function readConsent() {
    try {
      const parsed = JSON.parse(localStorage.getItem(CONSENT_KEY) || "null");
      if (!parsed || parsed.version !== POLICY_VERSION) return null;
      return parsed;
    } catch (_) {
      return null;
    }
  }

  function functionalAllowed() {
    const consent = readConsent();
    return !!(consent && consent.functional === true);
  }

  function isOptionalKey(key) {
    const value = String(key || "");
    return (
      OPTIONAL_EXACT_KEYS.has(value) ||
      OPTIONAL_PREFIXES.some((prefix) => value.startsWith(prefix))
    );
  }

  function storageAllowed(key) {
    if (String(key || "") === CONSENT_KEY) return true;
    if (!isOptionalKey(key)) return true;
    return functionalAllowed();
  }

  function clearOptionalStorage() {
    try {
      const keys = [];
      for (let i = 0; i < localStorage.length; i += 1) {
        const key = localStorage.key(i);
        if (key && isOptionalKey(key)) keys.push(key);
      }
      keys.forEach((key) => localStorage.removeItem(key));
    } catch (_) {}
  }

  function saveConsent(functional) {
    const value = {
      version: POLICY_VERSION,
      necessary: true,
      functional: !!functional,
      decided_at: new Date().toISOString(),
    };
    try {
      localStorage.setItem(CONSENT_KEY, JSON.stringify(value));
    } catch (_) {}
    if (!value.functional) clearOptionalStorage();
    render();
    return value;
  }

  function byId(id) {
    return document.getElementById(id);
  }

  function openPreferences() {
    const panel = byId("cookiePreferences");
    const functional = byId("cookieFunctionalConsent");
    if (functional) functional.checked = functionalAllowed();
    if (panel) panel.hidden = false;
  }

  function closePreferences() {
    const panel = byId("cookiePreferences");
    if (panel) panel.hidden = true;
  }

  function render() {
    const banner = byId("cookieBanner");
    if (banner) banner.hidden = readConsent() !== null;
    closePreferences();
  }

  function wire() {
    const actions = {
      cookieAcceptAll: () => saveConsent(true),
      cookieNecessaryOnly: () => saveConsent(false),
      cookiePreferencesOpen: openPreferences,
      cookieSettingsOpen: openPreferences,
      cookiePreferencesSave: () => {
        const functional = byId("cookieFunctionalConsent");
        saveConsent(!!(functional && functional.checked));
      },
      cookieWithdraw: () => saveConsent(false),
      cookiePreferencesClose: closePreferences,
    };
    Object.keys(actions).forEach((id) => {
      const element = byId(id);
      if (element) element.addEventListener("click", actions[id]);
    });
    render();
  }

  ns.cookieConsent = {
    CONSENT_KEY,
    POLICY_VERSION,
    readConsent,
    functionalAllowed,
    storageAllowed,
    saveConsent,
    openPreferences,
    clearOptionalStorage,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire, { once: true });
  } else {
    wire();
  }
})();
