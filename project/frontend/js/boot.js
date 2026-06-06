/**
 * Shop boot: API origin, admin FAB, post-load init sequence (Milestone 9).
 */
(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const $ = ns.$ || ((id) => document.getElementById(id));
  const storage = ns.storage || null;
  const apiClient = ns.api || null;

  function resolveBackendOrigin() {
    var el = document.getElementById("apiBase");
    var raw = (el && el.value ? String(el.value) : "")
      .replace(/\/$/, "")
      .trim();
    if (raw) return raw;
    var loc = window.location;
    if (loc.port === "5500") return loc.protocol + "//127.0.0.1:8000";
    return loc.origin;
  }

  window.__MESENCsi_API_ORIGIN = resolveBackendOrigin();
  var fabEarly = document.getElementById("adminFab");
  if (fabEarly)
    fabEarly.setAttribute(
      "href",
      window.__MESENCsi_API_ORIGIN + "/admin/login",
    );

  function api(path, opts) {
    if (apiClient && apiClient.api) return apiClient.api(path, opts);
    throw new Error("Most nem érjük el a boltot.");
  }

  async function syncCsrfToken() {
    if (apiClient && apiClient.syncCsrfToken) return apiClient.syncCsrfToken();
    return false;
  }

  function apiBase() {
    if (apiClient && apiClient.apiBase) return apiClient.apiBase();
    if (window.__MESENCsi_API_ORIGIN) return window.__MESENCsi_API_ORIGIN;
    return resolveBackendOrigin();
  }

  function refreshAdminFab() {
    const fab = document.getElementById("adminFab");
    if (!fab) return;
    let token = "";
    try {
      token =
        storage && typeof storage.getLocal === "function"
          ? storage.getLocal("token") || ""
          : localStorage.getItem("token") || "";
    } catch (_) {
      token = "";
    }
    const base = apiBase().replace(/\/$/, "");
    fab.href = base + (token ? "/admin" : "/admin/login");
  }

  /**
   * @param {Record<string, Function>} deps
   */
  async function start(deps) {
    deps = deps || {};
    if (typeof window.mesencsiResetOverlays === "function")
      window.mesencsiResetOverlays();

    let clearCartAfterBarionPaid = false;
    try {
      const params = new URLSearchParams(window.location.search);
      const vtok = params.get("email_verify_token");
      if (vtok) {
        try {
          await api("/auth/verify-email?token=" + encodeURIComponent(vtok));
          params.delete("email_verify_token");
          const qs = params.toString();
          history.replaceState(
            null,
            "",
            window.location.pathname +
              (qs ? "?" + qs : "") +
              window.location.hash,
          );
          const okMsg = "E-mail cím megerősítve — most már beléphetsz.";
          if (deps.setAuthLine)
            deps.setAuthLine($("loginMsg"), okMsg, true);
          const notify = ns.notify;
          if (notify) notify.success(okMsg);
        } catch (e) {
          const errMsg =
            (e && e.message) ||
            "A megerősítés nem sikerült (lejárt vagy hibás link).";
          if (deps.setAuthLine)
            deps.setAuthLine($("loginMsg"), errMsg, false);
          const notify = ns.notify;
          if (notify) notify.error(errMsg);
        }
      }
      const checkoutMod = ns.checkout;
      if (checkoutMod && checkoutMod.handleBarionUrlParamsOnBoot) {
        const barionBoot =
          await checkoutMod.handleBarionUrlParamsOnBoot(params);
        clearCartAfterBarionPaid = !!barionBoot.clearCartAfterBarionPaid;
      }
    } catch (_) {}

    await syncCsrfToken();
    if (deps.bootstrapAuthUiAsync) await deps.bootstrapAuthUiAsync();
    if (deps.applyBarionReturnNotice) deps.applyBarionReturnNotice();
    if (deps.loadCartFromStorage) deps.loadCartFromStorage();
    if (
      clearCartAfterBarionPaid &&
      deps.cartItems &&
      deps.cartItems().length &&
      deps.finalizeCheckoutCartUi
    ) {
      deps.finalizeCheckoutCartUi();
    }
    if (deps.applyPurchaseGates) deps.applyPurchaseGates();
    if (deps.updateCartUI) deps.updateCartUI();
    if (deps.loadHomeNews) void deps.loadHomeNews();
    refreshAdminFab();
    if (deps.showView && deps.viewFromPathname)
      deps.showView(deps.viewFromPathname(window.location.pathname));
  }

  ns.boot = {
    resolveBackendOrigin,
    refreshAdminFab,
    start,
  };
})();
