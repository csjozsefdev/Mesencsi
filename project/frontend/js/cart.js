/**
 * Shop cart: local/server sync, coupon estimate, cart UI (Milestone 6).
 */
(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const $ = ns.$ || ((id) => document.getElementById(id));
  const storage = ns.storage || null;
  const apiClient = ns.api || null;
  const notify = ns.notify || null;

  const CART_STORAGE_KEY = "mesencsi_cart_v1";
  const CHECKOUT_COUPON_STORAGE_KEY = "mesencsi_selected_coupon";

  /** @type {{ id: number, name: string, price: number, description: string, quantity: number }[]} */
  let _cart = [];
  let _checkoutCouponCode = null;
  let _checkoutEstimateSig = "";
  let _lastOrderEstimate = null;
  let _cartEstimateTimer = null;
  let _cartServerSyncTimer = null;
  let _userDiscountPickerBound = false;
  let cartQtyToastTimer = null;

  /** @type {Record<string, Function>} */
  let deps = {};

  function api(path, opts) {
    if (apiClient && apiClient.api) return apiClient.api(path, opts);
    throw new Error(
      apiClient && apiClient.friendlyBackendError
        ? apiClient.friendlyBackendError()
        : "Most nem érjük el a boltot.",
    );
  }

  function isLoggedIn() {
    return deps.isShopUserLoggedIn ? !!deps.isShopUserLoggedIn() : false;
  }

  function shopProfile() {
    return deps.shopUserProfile ? deps.shopUserProfile() : null;
  }

  function show(el, msg, ok) {
    if (deps.show) return deps.show(el, msg, ok);
  }

  function hide(el) {
    if (deps.hide) return deps.hide(el);
  }

  function formatPrice(n) {
    if (deps.formatPrice) return deps.formatPrice(n);
    return String(n);
  }

  function escapeHtml(s) {
    if (deps.escapeHtml) return deps.escapeHtml(s);
    return String(s);
  }

  function setAuthLine(el, text, ok) {
    if (deps.setAuthLine) return deps.setAuthLine(el, text, ok);
  }

  function msgPurchaseAuth() {
    return deps.MSG_PURCHASE_AUTH || "A vásárláshoz kérlek jelentkezz be.";
  }

  function userDiscountCouponsCache() {
    return deps.getUserDiscountCouponsCache
      ? deps.getUserDiscountCouponsCache()
      : [];
  }

  function cartStorageKey() {
    const p = shopProfile();
    if (p && p.id != null) return CART_STORAGE_KEY + "_u" + String(p.id);
    return CART_STORAGE_KEY;
  }

  function cartRowsFromPayload(rows) {
    const next = [];
    if (!Array.isArray(rows)) return next;
    for (const row of rows) {
      if (!row || row.product_id == null) continue;
      const id = Number(row.product_id != null ? row.product_id : row.id);
      const price = Number(row.price);
      let q = Math.floor(Number(row.quantity));
      if (
        !Number.isFinite(id) ||
        !Number.isFinite(price) ||
        !Number.isFinite(q) ||
        q < 1
      )
        continue;
      next.push({
        id,
        name: String(row.name || ""),
        price,
        description: typeof row.description === "string" ? row.description : "",
        quantity: q,
      });
    }
    return next;
  }

  function getItems() {
    return _cart;
  }

  function setItems(items) {
    _cart = Array.isArray(items) ? items : [];
  }

  function clear() {
    _cart = [];
  }

  function getCheckoutCouponCode() {
    return _checkoutCouponCode;
  }

  function getLastOrderEstimate() {
    return _lastOrderEstimate;
  }

  function getCheckoutEstimateSig() {
    return _checkoutEstimateSig;
  }

  function cartSignature() {
    return _cart
      .map(function (c) {
        return String(c.id) + ":" + String(Math.floor(Number(c.quantity)) || 0);
      })
      .join("|");
  }

  function getStoredCheckoutCoupon() {
    try {
      const v =
        storage && typeof storage.getLocal === "function"
          ? storage.getLocal(CHECKOUT_COUPON_STORAGE_KEY)
          : localStorage.getItem(CHECKOUT_COUPON_STORAGE_KEY);
      return v && String(v).trim() ? String(v).trim() : "";
    } catch (_) {
      return "";
    }
  }

  function setStoredCheckoutCoupon(code) {
    try {
      const c = code && String(code).trim() ? String(code).trim() : "";
      if (
        storage &&
        typeof storage.setLocal === "function" &&
        typeof storage.removeLocal === "function"
      ) {
        if (c) storage.setLocal(CHECKOUT_COUPON_STORAGE_KEY, c);
        else storage.removeLocal(CHECKOUT_COUPON_STORAGE_KEY);
      } else {
        if (c) localStorage.setItem(CHECKOUT_COUPON_STORAGE_KEY, c);
        else localStorage.removeItem(CHECKOUT_COUPON_STORAGE_KEY);
      }
    } catch (_) {}
  }

  function syncUserDiscountRadios(selectedCode) {
    const list = $("userDiscountsList");
    if (!list) return;
    const val =
      selectedCode != null
        ? String(selectedCode)
        : getStoredCheckoutCoupon() || "";
    const norm = val.toUpperCase();
    list
      .querySelectorAll('input[name="userDiscountPick"]')
      .forEach(function (inp) {
        const iv = inp.value || "";
        inp.checked = norm ? iv.toUpperCase() === norm : iv === "";
      });
  }

  function updateCheckoutCouponDisplay() {
    const active = $("checkoutCouponActive");
    const hint = $("checkoutCouponHint");
    const clr = $("btnCouponClear");
    const code = _checkoutCouponCode || getStoredCheckoutCoupon() || "";
    const cache = userDiscountCouponsCache();
    if (active) {
      if (code) {
        active.hidden = false;
        let label = "Aktív kedvezmény: " + code;
        if (
          _lastOrderEstimate &&
          _lastOrderEstimate.coupon_code &&
          _lastOrderEstimate.discount_percent != null
        ) {
          label += " (−" + String(_lastOrderEstimate.discount_percent) + "%)";
        } else {
          const row = cache.find(function (c) {
            return (
              String(c.code || "").toUpperCase() === String(code).toUpperCase()
            );
          });
          if (row && row.percent_discount != null) {
            label += " (−" + String(row.percent_discount) + "%)";
          }
        }
        if (
          _lastOrderEstimate &&
          _lastOrderEstimate.bundle_rule_name &&
          !_lastOrderEstimate.coupon_code
        ) {
          label +=
            " — a kosárra kombó kedvezmény érvényes; a személyes kupon ebben az esetben nem került felhasználásra.";
        }
        active.textContent = label;
      } else {
        active.hidden = true;
        active.textContent = "";
      }
    }
    if (hint) hint.hidden = !!code;
    if (clr) clr.hidden = !code;
  }

  function clearCheckoutCouponState() {
    _checkoutCouponCode = null;
    _checkoutEstimateSig = "";
    _lastOrderEstimate = null;
    setStoredCheckoutCoupon("");
    syncUserDiscountRadios("");
    updateCheckoutCouponDisplay();
    const sum = $("couponSummaryLine");
    if (sum) {
      sum.hidden = true;
      sum.textContent = "";
    }
  }

  function formatOrderEstimateSummary(est) {
    if (!est) return "";
    const parts = [];
    parts.push("Részösszeg: " + formatPrice(est.grand_original));
    if (est.bundle_rule_name) {
      parts.push('Kombó: "' + String(est.bundle_rule_name) + '"');
      parts.push(
        "Kedvezmény (−" +
          String(est.bundle_percent != null ? est.bundle_percent : 0) +
          "%): −" +
          formatPrice(est.grand_discount),
      );
    } else if (est.grand_discount > 0 && est.discount_percent != null) {
      parts.push(
        "Kupon (−" +
          String(est.discount_percent) +
          "%): −" +
          formatPrice(est.grand_discount),
      );
    } else if (est.grand_discount > 0) {
      parts.push("Kedvezmény: −" + formatPrice(est.grand_discount));
    }
    parts.push("Fizetendő: " + formatPrice(est.grand_final));
    return parts.join(" · ");
  }

  function updateCartFabBadge() {
    const badge = $("cartFabBadge");
    const fab = $("cartFab");
    if (!fab) return;
    const n = _cart.reduce(function (sum, item) {
      return sum + item.quantity;
    }, 0);
    if (badge) {
      if (n > 0) {
        badge.hidden = false;
        badge.textContent = n > 99 ? "99+" : String(n);
      } else {
        badge.hidden = true;
        badge.textContent = "";
      }
    }
    fab.setAttribute(
      "aria-label",
      n > 0
        ? "Kosár megnyitása, " + n + " db tétel összesen"
        : "Kosár megnyitása",
    );
  }

  function loadCartFromStorage() {
    try {
      if (!isLoggedIn()) {
        _cart = [];
        return;
      }
      const raw =
        storage && typeof storage.getLocal === "function"
          ? storage.getLocal(cartStorageKey())
          : localStorage.getItem(cartStorageKey());
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return;
      const next = [];
      for (const row of parsed) {
        if (!row || row.id == null) continue;
        const id = Number(row.id);
        const price = Number(row.price);
        let q = Math.floor(Number(row.quantity));
        if (
          !Number.isFinite(id) ||
          !Number.isFinite(price) ||
          !Number.isFinite(q) ||
          q < 1
        )
          continue;
        next.push({
          id,
          name: String(row.name || ""),
          price,
          description:
            typeof row.description === "string" ? row.description : "",
          quantity: q,
        });
      }
      _cart = next;
    } catch (_) {
      _cart = [];
    }
  }

  async function flushCartToServer(opts) {
    const silent = opts && opts.silent;
    try {
      await api("/cart", {
        method: "PUT",
        body: JSON.stringify({
          items: _cart.map(function (c) {
            return { product_id: c.id, quantity: c.quantity };
          }),
        }),
      });
    } catch (e) {
      if (!silent && notify) {
        notify.warn(
          (e && e.message) ||
            "A kosár szinkronizálása nem sikerült — a helyi kosár megmaradt.",
        );
      }
      throw e;
    }
  }

  function scheduleCartServerSync() {
    if (!isLoggedIn()) return;
    if (_cartServerSyncTimer) clearTimeout(_cartServerSyncTimer);
    _cartServerSyncTimer = setTimeout(function () {
      _cartServerSyncTimer = null;
      void flushCartToServer({ silent: true });
    }, 450);
  }

  function persistCart() {
    if (!isLoggedIn()) return;
    try {
      const key = cartStorageKey();
      const raw = JSON.stringify(_cart);
      if (storage && typeof storage.setLocal === "function")
        storage.setLocal(key, raw);
      else localStorage.setItem(key, raw);
      scheduleCartServerSync();
    } catch (_) {}
  }

  async function hydrateCartForLoggedInUser() {
    try {
      const data = await api("/cart", { method: "GET" });
      const fromServer = cartRowsFromPayload(data);
      if (fromServer.length) {
        _cart = fromServer;
      } else {
        loadCartFromStorage();
        if (_cart.length) await flushCartToServer();
      }
    } catch (_) {
      loadCartFromStorage();
    }
    updateCartUI();
    if (_cart.length) scheduleCartPricingEstimate();
  }

  function scheduleCartPricingEstimate() {
    if (_cartEstimateTimer) clearTimeout(_cartEstimateTimer);
    _cartEstimateTimer = setTimeout(async function () {
      _cartEstimateTimer = null;
      if (!isLoggedIn() || !_cart.length) return;
      try {
        const sigBefore = cartSignature();
        const est = await api("/orders/estimate", {
          method: "POST",
          body: JSON.stringify({
            items: _cart.map(function (c) {
              return { product_id: c.id, quantity: c.quantity };
            }),
            coupon_code: _checkoutCouponCode || null,
          }),
        });
        if (sigBefore !== cartSignature()) return;
        _lastOrderEstimate = est;
        _checkoutEstimateSig = cartSignature();
        _checkoutCouponCode = (est && est.coupon_code) || null;
        if (_checkoutCouponCode) setStoredCheckoutCoupon(_checkoutCouponCode);
        updateCartUI();
        updateCheckoutCouponDisplay();
      } catch (e) {
        if (notify) {
          notify.error(
            (e && e.message) ||
              "Nem sikerült frissíteni a kosár árát. Próbáld újra.",
          );
        }
      }
    }, 400);
  }

  function updateCartUI() {
    const emptyEl = $("cartEmpty");
    const wrap = $("cartWithItems");
    const lines = $("cartLines");
    const totalEl = $("cartGrandTotal");
    const coupLine = $("couponSummaryLine");
    if (!emptyEl || !wrap || !lines || !totalEl) {
      updateCartFabBadge();
      return;
    }

    try {
      if (!_cart.length) {
        clearCheckoutCouponState();
        emptyEl.hidden = false;
        wrap.hidden = true;
        lines.innerHTML = "";
        totalEl.textContent = formatPrice(0);
        return;
      }

      const sig = cartSignature();
      if (_checkoutEstimateSig && sig !== _checkoutEstimateSig) {
        _lastOrderEstimate = null;
        _checkoutEstimateSig = "";
        const keepCoupon = getStoredCheckoutCoupon() || _checkoutCouponCode;
        if (keepCoupon) {
          _checkoutCouponCode = keepCoupon;
          scheduleCartPricingEstimate();
        }
      }

      emptyEl.hidden = true;
      wrap.hidden = false;

      let grand = 0;
      lines.innerHTML = _cart
        .map(function (item, idx) {
          const lineTotal = item.price * item.quantity;
          grand += lineTotal;
          return (
            '<div class="cart-line">' +
            "<div>" +
            '<div class="cart-line__title">' +
            escapeHtml(item.name) +
            "</div>" +
            '<div class="cart-line__meta">' +
            escapeHtml(formatPrice(item.price)) +
            " / db</div>" +
            "</div>" +
            '<input type="number" min="1" step="1" data-cart-qty="' +
            idx +
            '" value="' +
            item.quantity +
            '" aria-label="Darabszám: ' +
            escapeHtml(item.name) +
            '" />' +
            '<div class="cart-line__meta">' +
            escapeHtml(formatPrice(lineTotal)) +
            "</div>" +
            '<button type="button" class="btn-cart-remove" data-cart-remove="' +
            idx +
            '">Eltávolítás</button>' +
            "</div>"
          );
        })
        .join("");

      const sig2 = cartSignature();
      if (_lastOrderEstimate && _checkoutEstimateSig === sig2) {
        totalEl.textContent = formatPrice(_lastOrderEstimate.grand_final);
        if (coupLine) {
          coupLine.hidden = false;
          coupLine.textContent = formatOrderEstimateSummary(_lastOrderEstimate);
        }
      } else {
        totalEl.textContent = formatPrice(grand);
        if (coupLine) {
          coupLine.hidden = true;
          coupLine.textContent = "";
        }
      }
    } finally {
      persistCart();
      updateCartFabBadge();
      updateCheckoutCouponDisplay();
    }
  }

  function cartFeedback(msgEl, text, ok) {
    if (msgEl && text) show(msgEl, text, ok);
    else if (msgEl) hide(msgEl);
    if (!notify || !text) return;
    if (ok === true) notify.success(text);
    else if (ok === false) notify.error(text);
  }

  function addToCart(product) {
    if (!isLoggedIn()) {
      const loginMsg = $("loginMsg");
      setAuthLine(loginMsg, msgPurchaseAuth(), false);
      if (notify) notify.warn(msgPurchaseAuth());
      return;
    }
    const existing = _cart.find(function (item) {
      return item.id === product.id;
    });
    if (existing) {
      existing.quantity += 1;
    } else {
      _cart.push({
        id: product.id,
        name: product.name,
        price: product.price,
        description: product.description,
        quantity: 1,
      });
    }
    updateCartUI();
    if (isLoggedIn() && _cart.length) scheduleCartPricingEstimate();
    const hint = $("webshopCartHint");
    if (hint) hint.hidden = false;
    if (notify) {
      const label = product && product.name ? String(product.name) : "Termék";
      notify.success("Hozzáadva a kosárhoz: " + label);
    }
  }

  async function applyCouponViaEstimate(rawCode, opts) {
    const optsSafe = opts || {};
    const msg = optsSafe.cartMsgEl || $("cartMsg");
    const code = rawCode && String(rawCode).trim();
    if (!code) {
      clearCheckoutCouponState();
      updateCartUI();
      if (_cart.length && isLoggedIn()) scheduleCartPricingEstimate();
      return false;
    }
    if (!isLoggedIn()) {
      if (msg && !optsSafe.silent) cartFeedback(msg, msgPurchaseAuth(), false);
      return false;
    }
    if (!_cart.length) {
      _checkoutCouponCode = code;
      setStoredCheckoutCoupon(code);
      syncUserDiscountRadios(code);
      updateCheckoutCouponDisplay();
      return true;
    }
    try {
      const est = await api("/orders/estimate", {
        method: "POST",
        body: JSON.stringify({
          items: _cart.map(function (c) {
            return { product_id: c.id, quantity: c.quantity };
          }),
          coupon_code: code,
        }),
      });
      _lastOrderEstimate = est;
      _checkoutEstimateSig = cartSignature();
      _checkoutCouponCode = (est && est.coupon_code) || code;
      setStoredCheckoutCoupon(_checkoutCouponCode);
      syncUserDiscountRadios(_checkoutCouponCode);
      updateCartUI();
      updateCheckoutCouponDisplay();
      if (msg && !optsSafe.silent) {
        if (est && est.bundle_rule_name && !est.coupon_code) {
          cartFeedback(
            msg,
            "A kosárra kombó kedvezmény érvényesült — a személyes kupon ebben az esetben nem került felhasználásra.",
            true,
          );
        } else {
          cartFeedback(
            msg,
            "Kedvezmény alkalmazva — a fizetendő összeget a szerver számolta.",
            true,
          );
        }
      }
      return true;
    } catch (e) {
      if (getStoredCheckoutCoupon().toUpperCase() === code.toUpperCase()) {
        clearCheckoutCouponState();
      }
      updateCartUI();
      const em = (e && e.message) || "Érvénytelen vagy nem használható kupon.";
      if (msg && !optsSafe.silent) {
        if (/megerősít|verified|403/i.test(em)) {
          cartFeedback(
            msg,
            "A kuponhoz előbb erősítsd meg az e-mail címed („Fiók adatok” → „Új megerősítő e-mail”).",
            false,
          );
        } else if (msg) {
          cartFeedback(msg, em, false);
        }
      }
      return false;
    }
  }

  async function restoreStoredCheckoutCoupon() {
    const stored = getStoredCheckoutCoupon();
    if (!stored || !isLoggedIn()) {
      updateCheckoutCouponDisplay();
      return;
    }
    if (_cart.length) {
      await applyCouponViaEstimate(stored, { silent: true });
    } else {
      _checkoutCouponCode = stored;
      syncUserDiscountRadios(stored);
      updateCheckoutCouponDisplay();
    }
  }

  function bindUserDiscountPicker() {
    if (_userDiscountPickerBound) return;
    const list = $("userDiscountsList");
    if (!list) return;
    _userDiscountPickerBound = true;
    list.addEventListener("change", function (e) {
      const inp = e.target;
      if (!inp || inp.name !== "userDiscountPick") return;
      const val = inp.value || "";
      if (!val) {
        clearCheckoutCouponState();
        updateCartUI();
        if (_cart.length) scheduleCartPricingEstimate();
        const cartMsg = $("cartMsg");
        if (cartMsg) hide(cartMsg);
        return;
      }
      void applyCouponViaEstimate(val, { silent: false });
    });
  }

  function finalizeCheckoutCartUi() {
    _cart = [];
    clearCheckoutCouponState();
    updateCartUI();
    persistCart();
    const checkoutFormEl = $("checkoutForm");
    if (checkoutFormEl) checkoutFormEl.reset();
  }

  function syncCartFabVisibility() {
    const fab = $("cartFab");
    if (!fab) return;
    const onCartView = deps.getCurrentView
      ? deps.getCurrentView() === "cart"
      : false;
    const showFab = isLoggedIn() && !onCartView;
    fab.hidden = !showFab;
    fab.setAttribute("aria-hidden", showFab ? "false" : "true");
  }

  function wireCartUi() {
    const cartWithItems = $("cartWithItems");
    if (cartWithItems && !cartWithItems.dataset.cartUiWired) {
      cartWithItems.dataset.cartUiWired = "1";
      cartWithItems.addEventListener("click", function (e) {
        if (!isLoggedIn()) return;
        const rm = e.target.closest("[data-cart-remove]");
        if (!rm) return;
        const i = parseInt(rm.getAttribute("data-cart-remove"), 10);
        if (Number.isNaN(i)) return;
        _cart.splice(i, 1);
        updateCartUI();
        if (isLoggedIn() && _cart.length) scheduleCartPricingEstimate();
      });
      cartWithItems.addEventListener("change", function (e) {
        if (!isLoggedIn()) return;
        const t = e.target;
        if (
          !(t instanceof HTMLInputElement) ||
          !t.matches("input[data-cart-qty]")
        )
          return;
        const i = parseInt(t.getAttribute("data-cart-qty"), 10);
        if (Number.isNaN(i) || !_cart[i]) return;
        let q = parseInt(t.value, 10);
        if (!Number.isFinite(q) || q < 1) q = 1;
        _cart[i].quantity = q;
        updateCartUI();
        if (isLoggedIn() && _cart.length) scheduleCartPricingEstimate();
        if (notify) {
          if (!cartQtyToastTimer) {
            cartQtyToastTimer = setTimeout(function () {
              cartQtyToastTimer = null;
              notify.success("Kosár frissítve.", { durationMs: 2400 });
            }, 600);
          }
        }
      });
    }

    const btnCouponClear = $("btnCouponClear");
    if (btnCouponClear && !btnCouponClear.dataset.cartUiWired) {
      btnCouponClear.dataset.cartUiWired = "1";
      btnCouponClear.addEventListener("click", function () {
        clearCheckoutCouponState();
        updateCartUI();
        if (_cart.length) scheduleCartPricingEstimate();
        const msg = $("cartMsg");
        if (msg) hide(msg);
        if (notify) notify.info("Kupon eltávolítva.", { durationMs: 2800 });
      });
    }
  }

  function init(injectedDeps) {
    deps = injectedDeps || {};
    wireCartUi();
  }

  ns.cart = {
    CART_STORAGE_KEY,
    CHECKOUT_COUPON_STORAGE_KEY,
    getItems,
    setItems,
    clear,
    getCheckoutCouponCode,
    getLastOrderEstimate,
    getCheckoutEstimateSig,
    cartSignature,
    cartRowsFromPayload,
    loadCartFromStorage,
    flushCartToServer,
    persistCart,
    hydrateCartForLoggedInUser,
    addToCart,
    updateCartUI,
    updateCartFabBadge,
    syncCartFabVisibility,
    scheduleCartPricingEstimate,
    applyCouponViaEstimate,
    restoreStoredCheckoutCoupon,
    clearCheckoutCouponState,
    updateCheckoutCouponDisplay,
    bindUserDiscountPicker,
    finalizeCheckoutCartUi,
    getStoredCheckoutCoupon,
    syncUserDiscountRadios,
    init,
  };
})();
