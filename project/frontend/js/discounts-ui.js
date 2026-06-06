/**
 * User personal discounts / coupons panel (Milestone 8b).
 */
(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const $ = ns.$ || ((id) => document.getElementById(id));
  const apiClient = ns.api || null;
  const notify = ns.notify || null;

  /** @type {{ id: number, code: string, percent_discount: number, expires_at: string | null }[]} */
  let userDiscountCouponsCache = [];

  /** @type {Record<string, Function>} */
  let deps = {};

  function api(path, opts) {
    if (apiClient && apiClient.api) return apiClient.api(path, opts);
    throw new Error("Most nem érjük el a boltot.");
  }

  function isLoggedIn() {
    return deps.isShopUserLoggedIn ? !!deps.isShopUserLoggedIn() : false;
  }

  function escapeHtml(s) {
    if (deps.escapeHtml) return deps.escapeHtml(s);
    return String(s);
  }

  function formatCouponExpiry(expiresAt) {
    if (expiresAt == null) return "Nincs lejárat";
    try {
      return new Date(expiresAt).toLocaleString("hu-HU", {
        dateStyle: "short",
        timeStyle: "short",
      });
    } catch (_) {
      return "—";
    }
  }

  function getCouponsCache() {
    return userDiscountCouponsCache;
  }

  function resetPanel() {
    const dlist = $("userDiscountsList");
    const dst = $("userDiscountsStatus");
    if (dlist) dlist.innerHTML = "";
    if (dst) dst.textContent = "";
    userDiscountCouponsCache = [];
  }

  async function loadUserDiscountsIntoPanel() {
    const st = $("userDiscountsStatus");
    const list = $("userDiscountsList");
    if (!isLoggedIn() || !st || !list) return;
    if (deps.bindUserDiscountPicker) deps.bindUserDiscountPicker();
    st.textContent = "Betöltés…";
    list.innerHTML = "";
    try {
      const rows = await api("/users/me/coupons", { method: "GET" });
      const arr = Array.isArray(rows) ? rows : [];
      userDiscountCouponsCache = arr;
      const selected = deps.getStoredCheckoutCoupon
        ? deps.getStoredCheckoutCoupon()
        : "";
      const noneChecked = !selected ? " checked" : "";
      let html =
        '<fieldset class="user-discounts-list">' +
        '<legend class="visually-hidden">Kedvezmény választása</legend>' +
        '<label class="user-discount-option user-discount-option--none">' +
        '<input type="radio" name="userDiscountPick" value=""' +
        noneChecked +
        " />" +
        '<span class="user-discount-option__card">' +
        '<span class="user-discount-option__title">Nincs kedvezmény</span>' +
        '<span class="user-discount-option__meta">Normál árak a kosárban</span>' +
        "</span></label>";
      if (!arr.length) {
        st.textContent =
          "Nincs személyes aktív kuponod. Ha kapsz kedvezményt, itt fog megjelenni — egy kattintással alkalmazhatod a kosárban.";
        list.innerHTML = html + "</fieldset>";
        if (selected && deps.clearCheckoutCouponState)
          deps.clearCheckoutCouponState();
        return;
      }
      st.textContent =
        arr.length === 1
          ? "1 aktív kedvezményed van — válaszd ki, és a kosárban automatikusan érvényesül."
          : arr.length +
            " aktív kedvezményed van — egyszerre csak egyet válassz.";
      html += arr
        .map(function (c) {
          const code = String(c.code || "").trim();
          const pct = Number(c.percent_discount) || 0;
          const exp = formatCouponExpiry(c.expires_at);
          const checked =
            selected && code.toUpperCase() === selected.toUpperCase()
              ? " checked"
              : "";
          return (
            '<label class="user-discount-option">' +
            '<input type="radio" name="userDiscountPick" value="' +
            escapeHtml(code) +
            '"' +
            checked +
            " />" +
            '<span class="user-discount-option__card">' +
            '<span class="user-discount-option__title">−' +
            escapeHtml(String(pct)) +
            "% kedvezmény</span>" +
            '<span class="user-discount-option__meta">Kupon: ' +
            escapeHtml(code) +
            " · Lejárat: " +
            escapeHtml(exp) +
            "</span>" +
            '<span class="user-discount-option__badge">Aktív</span>' +
            "</span></label>"
          );
        })
        .join("");
      list.innerHTML = html + "</fieldset>";
      if (selected) {
        const stillValid = arr.some(function (c) {
          return String(c.code || "").toUpperCase() === selected.toUpperCase();
        });
        if (!stillValid && deps.clearCheckoutCouponState)
          deps.clearCheckoutCouponState();
        else if (deps.syncUserDiscountRadios)
          deps.syncUserDiscountRadios(selected);
      }
      if (deps.updateCheckoutCouponDisplay) deps.updateCheckoutCouponDisplay();
    } catch (e) {
      userDiscountCouponsCache = [];
      const msg = (e && e.message) || "Nem sikerült betölteni a kuponokat.";
      if (/megerősít|verified|403/i.test(msg)) {
        st.textContent =
          "A személyes kuponok a megerősített e-mail után érhetők el. Kérhetsz új megerősítő levelet a „Fiók adatok” menüpontban.";
      } else {
        st.textContent = msg;
      }
      if (notify) notify.error(st.textContent || msg);
    }
  }

  function init(injectedDeps) {
    deps = injectedDeps || {};
  }

  ns.discountsUi = {
    formatCouponExpiry,
    getCouponsCache,
    resetPanel,
    loadUserDiscountsIntoPanel,
    init,
  };
})();
