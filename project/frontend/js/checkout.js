/**
 * Checkout form submit, Barion payment start/retry, return URL handling (Milestone 7).
 */
(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const $ = ns.$ || ((id) => document.getElementById(id));
  const storage = ns.storage || null;
  const apiClient = ns.api || null;
  const notify = ns.notify || null;

  /** @type {Record<string, Function>} */
  let deps = {};

  let checkoutSubmitting = false;
  let orderPaymentRetryBusy = false;

  const GUEST_CHECKOUT_TOKEN_KEY = "mesencsi_guest_checkout_token";
  const GUEST_CHECKOUT_EMAIL_KEY = "mesencsi_guest_checkout_email";
  const GUEST_CHECKOUT_TOKEN_HEADER = "X-Guest-Checkout-Token";

  /** @type {null | { kind: "success" | "pending" | "error", short: string, detail: string }} */
  let barionReturnNotice = null;

  function api(path, opts) {
    if (apiClient && apiClient.api) return apiClient.api(path, opts);
    throw new Error(
      apiClient && apiClient.friendlyBackendError
        ? apiClient.friendlyBackendError()
        : "Most nem érjük el a boltot.",
    );
  }

  async function syncCsrfToken() {
    if (apiClient && apiClient.syncCsrfToken) return apiClient.syncCsrfToken();
    return false;
  }

  async function apiFetch(path, opts) {
    if (apiClient && apiClient.apiFetch) return apiClient.apiFetch(path, opts);
    const data = await api(path, opts);
    return { data, headers: null };
  }

  function storeGuestCheckoutToken(token) {
    const t = (token || "").trim();
    if (!t) return;
    try {
      sessionStorage.setItem(GUEST_CHECKOUT_TOKEN_KEY, t);
    } catch (_) {}
  }

  function getGuestCheckoutToken() {
    try {
      return (sessionStorage.getItem(GUEST_CHECKOUT_TOKEN_KEY) || "").trim();
    } catch (_) {
      return "";
    }
  }

  function clearGuestCheckoutToken() {
    try {
      sessionStorage.removeItem(GUEST_CHECKOUT_TOKEN_KEY);
    } catch (_) {}
  }

  function storeGuestCheckoutEmail(email) {
    const e = (email || "").trim();
    if (!e) return;
    try {
      sessionStorage.setItem(GUEST_CHECKOUT_EMAIL_KEY, e);
    } catch (_) {}
  }

  function paymentAuthHeaders() {
    const h = {};
    if (!isLoggedIn()) {
      const tok = getGuestCheckoutToken();
      if (tok) h[GUEST_CHECKOUT_TOKEN_HEADER] = tok;
    }
    return h;
  }

  function syncCheckoutAuthPanel() {
    const panel = $("checkoutAuthPanel");
    const couponBox = $("checkoutCouponPicker");
    const loggedIn = isLoggedIn();
    if (panel) panel.hidden = loggedIn;
    if (couponBox) couponBox.hidden = !loggedIn;
    const emailEl = $("checkoutEmail");
    if (emailEl) {
      if (loggedIn) emailEl.setAttribute("readonly", "readonly");
      else emailEl.removeAttribute("readonly");
    }
  }

  function hidePostPurchaseAccountOffer() {
    const el = $("postPurchaseAccountOffer");
    if (el) el.hidden = true;
  }

  function showPostPurchaseAccountOffer(email) {
    const el = $("postPurchaseAccountOffer");
    if (!el) return;
    el.hidden = false;
    storeGuestCheckoutEmail(email || "");
    const regEmail = $("registerEmail");
    if (regEmail && email && !regEmail.value.trim()) regEmail.value = email;
  }

  function wireCheckoutAuthPanel() {
    const panel = $("checkoutAuthPanel");
    if (!panel || panel.dataset.checkoutWired === "1") return;
    panel.dataset.checkoutWired = "1";
    panel.querySelectorAll("[data-checkout-auth]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const action = btn.getAttribute("data-checkout-auth");
        if (action === "login" || action === "register") {
          setAuthLine(
            $("loginMsg"),
            action === "login"
              ? "Jelentkezz be a mentett adatok és tagi kedvezmények használatához."
              : "Regisztrálj a rendelési előzményekhez, mesekönyvekhez és tagi kedvezményekhez.",
            true,
          );
          window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
        }
      });
    });
    const laterBtn = $("postPurchaseAccountLater");
    if (laterBtn && !laterBtn.dataset.checkoutWired) {
      laterBtn.dataset.checkoutWired = "1";
      laterBtn.addEventListener("click", hidePostPurchaseAccountOffer);
    }
    const createBtn = $("postPurchaseAccountCreate");
    if (createBtn && !createBtn.dataset.checkoutWired) {
      createBtn.dataset.checkoutWired = "1";
      createBtn.addEventListener("click", function () {
        hidePostPurchaseAccountOffer();
        const email =
          (sessionStorage.getItem(GUEST_CHECKOUT_EMAIL_KEY) || "").trim() ||
          ($("checkoutEmail") && $("checkoutEmail").value.trim()) ||
          "";
        const regEmail = $("registerEmail");
        if (regEmail && email) regEmail.value = email;
        setAuthLine(
          $("loginMsg"),
          "Hozz létre fiókot a megvásárolt mesekönyvekhez és rendelési előzményekhez.",
          true,
        );
        window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
      });
    }
  }

  function cartFeedback(el, msg, ok) {
    if (el && msg) show(el, msg, ok);
    else if (el) hide(el);
    if (!notify || !msg) return;
    if (ok === true) notify.success(msg);
    else if (ok === false) notify.error(msg);
  }

  function show(el, msg, ok) {
    if (deps.show) return deps.show(el, msg, ok);
  }

  function hide(el) {
    if (deps.hide) return deps.hide(el);
  }

  function setAuthLine(el, text, ok) {
    if (deps.setAuthLine) return deps.setAuthLine(el, text, ok);
  }

  function isLoggedIn() {
    return deps.isShopUserLoggedIn ? !!deps.isShopUserLoggedIn() : false;
  }

  function msgPurchaseAuth() {
    return deps.MSG_PURCHASE_AUTH || "A vásárláshoz kérlek jelentkezz be.";
  }

  function cartItems() {
    return deps.cartItems ? deps.cartItems() : [];
  }

  function cartSignature() {
    return deps.cartSignature ? deps.cartSignature() : "";
  }

  function checkoutCouponCode() {
    return deps.checkoutCouponCode ? deps.checkoutCouponCode() : null;
  }

  function getStoredCheckoutCoupon() {
    return deps.getStoredCheckoutCoupon ? deps.getStoredCheckoutCoupon() : "";
  }

  function lastOrderEstimate() {
    return deps.lastOrderEstimate ? deps.lastOrderEstimate() : null;
  }

  function checkoutEstimateSig() {
    return deps.checkoutEstimateSig ? deps.checkoutEstimateSig() : "";
  }

  function finalizeCheckoutCartUi() {
    if (deps.finalizeCheckoutCartUi) return deps.finalizeCheckoutCartUi();
  }

  function friendlyBackendError() {
    if (deps.friendlyBackendError) return deps.friendlyBackendError();
    if (apiClient && apiClient.friendlyBackendError)
      return apiClient.friendlyBackendError();
    return "Most nem érjük el a boltot.";
  }

  function shopPaymentStatusHu(s) {
    if (deps.shopPaymentStatusHu) return deps.shopPaymentStatusHu(s);
    return s || "—";
  }

  function paymentReturnBannerShort(kind) {
    if (kind === "success") {
      return "Fizetés sikeres — visszaigazolást emailben küldünk.";
    }
    if (kind === "pending") {
      return "Fizetés feldolgozás alatt — részletek a Rendeléseim menüben.";
    }
    return "A fizetés nem sikerült vagy megszakadt — újrapróbálás a Rendeléseim menüben.";
  }

  function normalizePaymentReturnKind(kind) {
    return kind === "success" || kind === "pending" || kind === "error"
      ? kind
      : "error";
  }

  function hidePaymentReturnBanner() {
    const el = $("paymentReturnBanner");
    if (!el) return;
    el.hidden = true;
    el.classList.remove(
      "payment-return-banner--success",
      "payment-return-banner--pending",
      "payment-return-banner--error",
    );
    document.body.classList.remove("has-payment-return-banner");
  }

  function renderPaymentReturnBanner(shortText, kind) {
    const el = $("paymentReturnBanner");
    const textEl = $("paymentReturnBannerText");
    const actionBtn = $("paymentReturnBannerAction");
    if (!el || !textEl) return;
    const k = normalizePaymentReturnKind(kind);
    const t = (shortText || paymentReturnBannerShort(k)).trim();
    if (!t) {
      hidePaymentReturnBanner();
      return;
    }
    el.classList.remove(
      "payment-return-banner--success",
      "payment-return-banner--pending",
      "payment-return-banner--error",
    );
    el.classList.add("payment-return-banner--" + k);
    textEl.textContent = t;
    if (actionBtn) {
      const showOrders = isLoggedIn();
      actionBtn.hidden = !showOrders;
      actionBtn.setAttribute("aria-hidden", showOrders ? "false" : "true");
    }
    el.hidden = false;
    document.body.classList.add("has-payment-return-banner");
  }

  function stashBarionReturnNotice(detail, kind) {
    const k = normalizePaymentReturnKind(kind);
    const d = (detail || "").trim();
    if (!d) {
      barionReturnNotice = null;
      return;
    }
    barionReturnNotice = {
      kind: k,
      short: paymentReturnBannerShort(k),
      detail: d,
    };
  }

  function applyBarionReturnNotice() {
    if (!barionReturnNotice) return;
    renderPaymentReturnBanner(barionReturnNotice.short, barionReturnNotice.kind);
    const lo = $("authLoggedOut");
    if (lo && !lo.hidden) {
      setAuthLine(
        $("loginMsg"),
        barionReturnNotice.detail,
        barionReturnNotice.kind === "success",
      );
    }
  }

  function clearBarionReturnNotice() {
    barionReturnNotice = null;
    hidePaymentReturnBanner();
  }

  function openOrdersFromPaymentBanner() {
    hidePaymentReturnBanner();
    if (!isLoggedIn()) {
      setAuthLine(
        $("loginMsg"),
        "A rendeléseid megtekintéséhez jelentkezz be.",
        false,
      );
      try {
        if (typeof window.mesencsiCloseMobileNav === "function")
          window.mesencsiCloseMobileNav();
      } catch (_) {}
      return;
    }
    if (deps.setActiveUserSection) void deps.setActiveUserSection("orders");
  }

  function checkoutAbandonedGuidanceMsg(prefix) {
    const core =
      "A rendelés létrejött, de a fizetés még nem sikeres. A rendeléseid között ellenőrizheted az állapotot (Fiók → Rendeléseim), és a „Fizetés újrapróbálása” gombbal folytathatod a fizetést. Új kosarat is indíthatsz, ha újra szeretnéd próbálni.";
    const p = (prefix || "").trim();
    return p ? p + " " + core : core;
  }

  function barionPaymentLandingErrorMsg(prefix) {
    const parts = [];
    const p = (prefix || "").trim();
    if (p) parts.push(p);
    parts.push("A fizetés nem sikerült vagy megszakadt.");
    parts.push(
      "A rendelés létrejött, de a fizetés még nem sikeres. A rendeléseid között ellenőrizheted az állapotot (Fiók → Rendeléseim). Új kosarat is indíthatsz, ha újra szeretnéd próbálni.",
    );
    parts.push("Ha levonás történt, vedd fel velünk a kapcsolatot.");
    return parts.join(" ");
  }

  function isBarionPaymentIdUsable(pid) {
    const s = (pid || "").trim();
    if (!s || s.length < 4 || s.length > 128) return false;
    return /^[\w-]+$/.test(s);
  }

  function clearBarionPaymentQueryParams(params) {
    params.delete("payment");
    params.delete("pid");
    params.delete("result");
    params.delete("sandbox");
  }

  function stripBarionPaymentQueryFromUrl(params) {
    clearBarionPaymentQueryParams(params);
    const qs = params.toString();
    history.replaceState(
      null,
      "",
      window.location.pathname + (qs ? "?" + qs : "") + window.location.hash,
    );
  }

  function showBarionPaymentLandingNotice(detail, kind) {
    const k = normalizePaymentReturnKind(kind);
    stashBarionReturnNotice(detail, k);
    renderPaymentReturnBanner(paymentReturnBannerShort(k), k);
    const lo = $("authLoggedOut");
    if (lo && !lo.hidden) {
      setAuthLine($("loginMsg"), detail, k === "success");
    }
  }

  function orderIdsFromCreateResponse(data) {
    if (!Array.isArray(data)) return [];
    return data
      .map(function (row) {
        if (!row || typeof row !== "object") return null;
        const raw = row.id != null ? row.id : row.order_id;
        const n = Number(raw);
        return Number.isFinite(n) && n > 0 ? n : null;
      })
      .filter(function (id) {
        return id != null;
      });
  }

  function barionRedirectUrlFromStart(startPayload) {
    if (!startPayload || typeof startPayload !== "object") return "";
    const raw =
      startPayload.redirect_url != null
        ? startPayload.redirect_url
        : startPayload.gateway_url;
    return raw != null ? String(raw).trim() : "";
  }

  function stashBarionCheckoutRedirectFlag() {
    try {
      if (storage && typeof storage.setSession === "function")
        storage.setSession("mesencsi_barion_checkout_redirect", "1");
      else sessionStorage.setItem("mesencsi_barion_checkout_redirect", "1");
    } catch (_) {}
  }

  function clearBarionCheckoutRedirectFlag() {
    try {
      if (storage && typeof storage.removeSession === "function")
        storage.removeSession("mesencsi_barion_checkout_redirect");
      else sessionStorage.removeItem("mesencsi_barion_checkout_redirect");
    } catch (_) {}
  }

  async function retryBarionPaymentForOrderGroup(
    orderIds,
    minId,
    productLabel,
    triggerBtn,
  ) {
    if (orderPaymentRetryBusy) return;
    const st = $("userOrdersStatus");
    if (!isLoggedIn()) {
      const needLogin = "A fizetés újrapróbálásához jelentkezz be.";
      if (st) st.textContent = needLogin;
      if (notify) notify.warn(needLogin);
      return;
    }
    const ids = (orderIds || []).filter(function (n) {
      return Number.isFinite(n) && n > 0;
    });
    if (!ids.length) return;

    const defaultLabel = triggerBtn ? (triggerBtn.textContent || "").trim() : "";
    const desc =
      "Mesencsi rendelés újrapróbálás — #" +
      minId +
      (productLabel
        ? " — " + productLabel
        : defaultLabel
          ? " — " + defaultLabel
          : "");

    orderPaymentRetryBusy = true;
    if (triggerBtn) {
      if (!triggerBtn.dataset.retryLabelDefault) {
        triggerBtn.dataset.retryLabelDefault = (
          triggerBtn.textContent || "Fizetés újrapróbálása"
        ).trim();
      }
      triggerBtn.disabled = true;
      triggerBtn.setAttribute("aria-busy", "true");
      triggerBtn.textContent = "Fizetés indítása...";
    }
    if (st) st.textContent = "Fizetés indítása…";

    let redirecting = false;
    try {
      await syncCsrfToken();
      const payStart = await api("/payments/barion/start", {
        method: "POST",
        body: JSON.stringify({ order_ids: ids, description: desc.slice(0, 500) }),
      });
      const redirectUrl = barionRedirectUrlFromStart(payStart);
      if (redirectUrl) {
        redirecting = true;
        if (notify) notify.info("Átirányítás a Barion fizetéshez…");
        stashBarionCheckoutRedirectFlag();
        window.location.assign(redirectUrl);
        return;
      }
      const info =
        (payStart && payStart.message) ||
        "A fizetés nem indult el — nincs átirányítási cím. Próbáld újra később.";
      if (st) st.textContent = info;
      if (notify) notify.error(info);
    } catch (e) {
      const detail =
        (notify && notify.messageFromError
          ? notify.messageFromError(e, "A fizetés indítása sikertelen.")
          : (e && e.message) || "A fizetés indítása sikertelen.");
      const full =
        detail + " Ha a gond továbbra is fennáll, vedd fel velünk a kapcsolatot.";
      if (st) st.textContent = full;
      if (notify) notify.error(full);
    } finally {
      orderPaymentRetryBusy = false;
      if (!redirecting && triggerBtn) {
        triggerBtn.disabled = false;
        triggerBtn.removeAttribute("aria-busy");
        triggerBtn.textContent =
          triggerBtn.dataset.retryLabelDefault || "Fizetés újrapróbálása";
      }
    }
  }

  function initUserOrdersPaymentRetryListener() {
    const list = $("userOrdersList");
    if (!list || list.dataset.paymentRetryListener === "1") return;
    list.dataset.paymentRetryListener = "1";
    list.addEventListener("click", function (ev) {
      const btn =
        ev.target && ev.target.closest
          ? ev.target.closest("[data-order-payment-retry]")
          : null;
      if (!btn || btn.disabled) return;
      const raw = btn.getAttribute("data-order-ids") || "";
      const orderIds = raw
        .split(",")
        .map(function (x) {
          return parseInt(x, 10);
        })
        .filter(function (n) {
          return Number.isFinite(n) && n > 0;
        });
      if (!orderIds.length) return;
      const minId = parseInt(btn.getAttribute("data-order-min-id") || "", 10);
      const label = btn.getAttribute("data-order-retry-label") || "";
      void retryBarionPaymentForOrderGroup(
        orderIds,
        Number.isFinite(minId) ? minId : orderIds[0],
        label,
        btn,
      );
    });
  }

  function setCheckoutSubmitBusy(busy) {
    checkoutSubmitting = !!busy;
    const checkoutForm = document.getElementById("checkoutForm");
    if (checkoutForm) {
      if (busy) {
        checkoutForm.setAttribute("aria-busy", "true");
        checkoutForm.setAttribute("inert", "");
      } else {
        checkoutForm.removeAttribute("aria-busy");
        checkoutForm.removeAttribute("inert");
      }
    }
    const btn = checkoutForm
      ? checkoutForm.querySelector('button[type="submit"]')
      : null;
    if (!btn) return;
    if (!btn.dataset.checkoutLabelDefault) {
      btn.dataset.checkoutLabelDefault = (
        btn.textContent || "Megrendelés és fizetés indítása"
      ).trim();
    }
    if (busy) {
      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
      btn.textContent = "Fizetés indítása...";
    } else {
      btn.disabled = false;
      btn.removeAttribute("aria-busy");
      btn.textContent = btn.dataset.checkoutLabelDefault;
    }
  }

  function wireCheckoutForm() {
    const checkoutForm = document.getElementById("checkoutForm");
    if (!checkoutForm || checkoutForm.dataset.checkoutWired === "1") return;
    checkoutForm.dataset.checkoutWired = "1";
    checkoutForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (checkoutSubmitting) return;

      let checkoutRedirecting = false;
      let checkoutLoadingToast = null;
      setCheckoutSubmitBusy(true);

      const msg = $("cartMsg");
      hide(msg);

      try {
        if (!cartItems().length) {
          cartFeedback(
            msg,
            "A kosár üres — előbb válassz terméket a webshopban.",
            false,
          );
          return;
        }

        const customer_name = $("checkoutName").value.trim();

        const validatePersonNameField = deps.validatePersonNameField;
        const nameErr = validatePersonNameField
          ? validatePersonNameField(customer_name, "Név", "customer_name")
          : null;
        if (nameErr) {
          cartFeedback(msg, nameErr, false);
          return;
        }
        const validateEmailField = deps.validateEmailField;
        const emailErr = validateEmailField
          ? validateEmailField(
              $("checkoutEmail") && $("checkoutEmail").value,
            )
          : null;
        if (emailErr) {
          cartFeedback(msg, emailErr, false);
          return;
        }
        const validatePhoneOnly = deps.validatePhoneOnly;
        const phoneErr = validatePhoneOnly
          ? validatePhoneOnly($("checkoutPhone") && $("checkoutPhone").value)
          : null;
        if (phoneErr) {
          cartFeedback(msg, phoneErr, false);
          return;
        }
        const shipBuilt = deps.checkoutShippingAddressPayload
          ? deps.checkoutShippingAddressPayload()
          : { ok: false, errors: [{ message: "Szállítási cím ellenőrzés hiányzik." }] };
        if (!shipBuilt.ok) {
          cartFeedback(
            msg,
            (shipBuilt.errors[0] && shipBuilt.errors[0].message) ||
              "Érvénytelen szállítási cím.",
            false,
          );
          return;
        }
        const confirmCb = $("checkoutAddressConfirmCb");
        if (confirmCb && !confirmCb.checked) {
          cartFeedback(
            msg,
            "Kérjük, erősítsd meg, hogy a szállítási adatok helyesek.",
            false,
          );
          return;
        }
        const termsAccepted = !!(
          $("checkoutTermsAccepted") && $("checkoutTermsAccepted").checked
        );
        const privacyAcknowledged = !!(
          $("checkoutPrivacyAcknowledged") &&
          $("checkoutPrivacyAcknowledged").checked
        );
        if (!termsAccepted || !privacyAcknowledged) {
          cartFeedback(
            msg,
            "A rendeléshez el kell fogadnod az ÁSZF-et, és meg kell ismerned az adatkezelési tájékoztatót.",
            false,
          );
          return;
        }
        const body = {
          customer_name,
          items: cartItems().map(function (c) {
            return { product_id: c.id, quantity: c.quantity };
          }),
          company_website:
            ($("checkoutCompanyWebsite") && $("checkoutCompanyWebsite").value) ||
            "",
          shipping_address: shipBuilt.json,
          terms_accepted: termsAccepted,
          privacy_acknowledged: privacyAcknowledged,
        };
        if (!isLoggedIn()) {
          body.customer_email = (
            $("checkoutEmail") && $("checkoutEmail").value
          ).trim();
        }
        const notes = $("checkoutNotes").value.trim();
        const containsUnsafeMarkup = deps.containsUnsafeMarkup;
        if (notes) {
          if (
            (containsUnsafeMarkup && containsUnsafeMarkup(notes)) ||
            notes.length > 2000
          ) {
            cartFeedback(msg, "A megjegyzés érvénytelen vagy túl hosszú.", false);
            return;
          }
          body.notes = notes;
        }
        if (shipBuilt.warnings && shipBuilt.warnings.length) {
          const warnEl = $("checkoutZipCityWarn");
          if (warnEl) {
            warnEl.textContent = shipBuilt.warnings[0].message;
            warnEl.hidden = false;
          }
        }

        const cartSig = cartSignature();
        const couponForOrder =
          checkoutCouponCode() || getStoredCheckoutCoupon() || "";
        const est = lastOrderEstimate();
        const estSig = checkoutEstimateSig();
        if (
          couponForOrder &&
          isLoggedIn() &&
          est &&
          estSig === cartSig &&
          est.coupon_code &&
          String(est.coupon_code).toUpperCase() ===
            String(couponForOrder).toUpperCase()
        ) {
          body.coupon_code = est.coupon_code;
        }

        const payDescription =
          "Mesencsi rendelés — " +
          cartItems()
            .map(function (c) {
              return (c.name || "termék") + " ×" + c.quantity;
            })
            .join(", ");

        await syncCsrfToken();
        if (notify) {
          checkoutLoadingToast = notify.loading(
            "Rendelés leadása, fizetés indítása…",
          );
        }
        const orderRes = await apiFetch("/orders", {
          method: "POST",
          body: JSON.stringify(body),
        });
        const data = orderRes.data;
        if (!isLoggedIn() && orderRes.headers) {
          const guestTok =
            orderRes.headers.get(GUEST_CHECKOUT_TOKEN_HEADER) ||
            orderRes.headers.get("x-guest-checkout-token");
          if (guestTok) storeGuestCheckoutToken(guestTok);
          storeGuestCheckoutEmail(body.customer_email || "");
        }

        const orderIds = orderIdsFromCreateResponse(data);
        if (!orderIds.length) {
          if (checkoutLoadingToast) checkoutLoadingToast.dismiss();
          checkoutLoadingToast = null;
          cartFeedback(
            msg,
            "A rendelés létrejöhetett, de a fizetés nem indult el (hiányzó rendelés azonosító). A kosár megmaradt — nézd a Fiók → Rendeléseim menüt, vagy próbáld újra.",
            false,
          );
          window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
          return;
        }

        let payStart;
        try {
          payStart = await api("/payments/barion/start", {
            method: "POST",
            headers: paymentAuthHeaders(),
            body: JSON.stringify({
              order_ids: orderIds,
              description: payDescription,
            }),
          });
        } catch (payErr) {
          if (checkoutLoadingToast) checkoutLoadingToast.dismiss();
          checkoutLoadingToast = null;
          const payDetail =
            (payErr && payErr.message) ||
            "A fizetés indítása sikertelen (hálózati vagy szerverhiba).";
          cartFeedback(
            msg,
            "A rendelés létrejöhetett, de a fizetés nem indult el. A kosár megmaradt — " +
              payDetail +
              " Nézd a Fiók → Rendeléseim menüt, vagy próbáld újra a fizetést.",
            false,
          );
          window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
          return;
        }

        const redirectUrl = barionRedirectUrlFromStart(payStart);
        if (redirectUrl) {
          if (checkoutLoadingToast) checkoutLoadingToast.dismiss();
          checkoutLoadingToast = null;
          if (notify) notify.info("Átirányítás a Barion fizetéshez…");
          checkoutRedirecting = true;
          stashBarionCheckoutRedirectFlag();
          window.location.assign(redirectUrl);
          return;
        }

        if (checkoutLoadingToast) checkoutLoadingToast.dismiss();
        checkoutLoadingToast = null;
        const info =
          payStart && payStart.message
            ? String(payStart.message)
            : "A rendelés létrejöhetett, de nincs Barion átirányítás. A kosár megmaradt — nézd a Fiók → Rendeléseim menüt.";
        cartFeedback(msg, info, false);
        window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
      } catch (e) {
        if (checkoutLoadingToast) checkoutLoadingToast.dismiss();
        checkoutLoadingToast = null;
        const detail =
          notify && notify.messageFromError
            ? notify.messageFromError(
                e,
                "Nem sikerült elküldeni a rendelést. Próbáld újra.",
              )
            : e && e.message
              ? String(e.message)
              : friendlyBackendError();
        cartFeedback(
          msg,
          detail || "Nem sikerült elküldeni a rendelést. Próbáld újra.",
          false,
        );
      } finally {
        if (!checkoutRedirecting) setCheckoutSubmitBusy(false);
      }
    });
  }

  function initPaymentReturnBanner() {
    const closeBtn = $("paymentReturnBannerClose");
    if (closeBtn && !closeBtn.dataset.checkoutWired) {
      closeBtn.dataset.checkoutWired = "1";
      closeBtn.addEventListener("click", function () {
        clearBarionReturnNotice();
      });
    }
    const actionBtn = $("paymentReturnBannerAction");
    if (actionBtn && !actionBtn.dataset.checkoutWired) {
      actionBtn.dataset.checkoutWired = "1";
      actionBtn.addEventListener("click", function () {
        openOrdersFromPaymentBanner();
      });
    }
  }

  /**
   * Barion ?payment=… / ?payment=error URL params on first load (before auth bootstrap).
   * @returns {{ clearCartAfterBarionPaid: boolean }}
   */
  async function handleBarionUrlParamsOnBoot(params) {
    const paymentQ = (params.get("payment") || "").trim().toLowerCase();
    const resultQ = (params.get("result") || "").trim().toLowerCase();
    const barionReturn = paymentQ === "barion";
    const barionPaymentErrorLanding =
      paymentQ === "error" || resultQ === "error";
    let clearCartAfterBarionPaid = false;

    if (barionPaymentErrorLanding) {
      showBarionPaymentLandingNotice(barionPaymentLandingErrorMsg(), "error");
      stripBarionPaymentQueryFromUrl(params);
      clearBarionCheckoutRedirectFlag();
      return { clearCartAfterBarionPaid };
    }

    if (!barionReturn) return { clearCartAfterBarionPaid };

    const pid = (params.get("pid") || "").trim();
    let barionMsg = "";
    let barionKind = "error";
    let paymentConfirmedPaid = false;
    const barionCautiousMsg = function (prefix) {
      const pending =
        "Fizetés feldolgozása folyamatban. Visszaigazolást emailben küldünk sikeres fizetés után.";
      return checkoutAbandonedGuidanceMsg(
        ((prefix || "").trim() + " " + pending).trim(),
      );
    };

    if (!isBarionPaymentIdUsable(pid)) {
      const prefix = !isLoggedIn()
        ? "Hiányzik vagy érvénytelen a fizetés azonosítója. Lépj be ugyanazzal a fiókkal, amellyel rendeltél."
        : "Hiányzik vagy érvénytelen a fizetés azonosítója.";
      barionMsg = barionPaymentLandingErrorMsg(prefix);
      barionKind = "error";
    } else if (isLoggedIn()) {
      try {
        const st = await api(
          "/payments/barion/payment/" + encodeURIComponent(pid) + "/state",
          { method: "GET" },
        );
        const ps = st && st.payment_status ? st.payment_status : "pending";
        if (ps === "paid") {
          barionMsg =
            "Fizetés sikeresen teljesült. Visszaigazolást emailben küldünk. A rendelés állapota a Fiók → Rendeléseim menüben követhető.";
          barionKind = "success";
          paymentConfirmedPaid = true;
        } else if (ps === "failed" || ps === "cancelled") {
          barionMsg = barionPaymentLandingErrorMsg(
            "Payment: " + shopPaymentStatusHu(ps) + ".",
          );
          barionKind = "error";
        } else {
          barionMsg = barionCautiousMsg(
            "Payment: " + shopPaymentStatusHu(ps) + ".",
          );
          barionKind = "pending";
        }
      } catch (e) {
        barionMsg = barionPaymentLandingErrorMsg(
          (e && e.message) || "A fizetés állapotát most nem ellenőrizhető.",
        );
        barionKind = "error";
      }
    } else if (getGuestCheckoutToken()) {
      try {
        const st = await api(
          "/payments/barion/payment/" + encodeURIComponent(pid) + "/state",
          {
            method: "GET",
            headers: paymentAuthHeaders(),
          },
        );
        const ps = st && st.payment_status ? st.payment_status : "pending";
        if (ps === "paid") {
          barionMsg =
            "Fizetés sikeresen teljesült. Visszaigazolást emailben küldünk.";
          barionKind = "success";
          paymentConfirmedPaid = true;
          const guestEmail =
            (sessionStorage.getItem(GUEST_CHECKOUT_EMAIL_KEY) || "").trim();
          if (guestEmail) showPostPurchaseAccountOffer(guestEmail);
        } else if (ps === "failed" || ps === "cancelled") {
          barionMsg = barionPaymentLandingErrorMsg(
            "Payment: " + shopPaymentStatusHu(ps) + ".",
          );
          barionKind = "error";
        } else {
          barionMsg = barionCautiousMsg(
            "Payment: " + shopPaymentStatusHu(ps) + ".",
          );
          barionKind = "pending";
        }
      } catch (e) {
        barionMsg = barionPaymentLandingErrorMsg(
          (e && e.message) || "A fizetés állapotát most nem ellenőrizhető.",
        );
        barionKind = "error";
      }
    } else {
      barionMsg = barionPaymentLandingErrorMsg(
        "A fizetés sikerült — ellenőrizd az e-mailedet a visszaigazolásért. Fiók létrehozásával eléred a mesekönyveket és a rendelési előzményeket.",
      );
      barionKind = "success";
      paymentConfirmedPaid = true;
    }

    if (paymentConfirmedPaid && !isLoggedIn()) {
      clearGuestCheckoutToken();
    }

    clearCartAfterBarionPaid = paymentConfirmedPaid;
    stripBarionPaymentQueryFromUrl(params);
    showBarionPaymentLandingNotice(barionMsg, barionKind);
    clearBarionCheckoutRedirectFlag();
    return { clearCartAfterBarionPaid };
  }

  async function syncCheckoutEmailFromSession() {
    const el = $("checkoutEmail");
    const nm = $("checkoutName");
    syncCheckoutAuthPanel();
    if (!isLoggedIn()) {
      if (el) el.removeAttribute("readonly");
      return;
    }
    try {
      const me = await api("/auth/me", { method: "GET" });
      if (me && me.email && el) el.value = me.email;
      if (nm && me) {
        const pre =
          (me.nickname != null && String(me.nickname).trim()) ||
          (me.username && String(me.username).trim()) ||
          "";
        if (pre && !nm.value.trim()) nm.value = pre;
      }
      const cp = $("checkoutPhone");
      if (cp && me && me.phone && !cp.value.trim())
        cp.value = String(me.phone).trim();
      if (deps.wireCheckoutAddressConfirmPreview)
        deps.wireCheckoutAddressConfirmPreview();
      if (deps.updateCheckoutAddressConfirmPreview)
        deps.updateCheckoutAddressConfirmPreview();
    } catch (_) {
      /* lejárt / hibás token */
    }
  }

  function init(injectedDeps) {
    deps = injectedDeps || {};
    wireCheckoutForm();
    wireCheckoutAuthPanel();
    initPaymentReturnBanner();
    syncCheckoutAuthPanel();
  }

  ns.checkout = {
    applyBarionReturnNotice,
    clearBarionReturnNotice,
    clearBarionPaymentQueryParams,
    stripBarionPaymentQueryFromUrl,
    showBarionPaymentLandingNotice,
    stashBarionReturnNotice,
    renderPaymentReturnBanner,
    hidePaymentReturnBanner,
    openOrdersFromPaymentBanner,
    checkoutAbandonedGuidanceMsg,
    barionPaymentLandingErrorMsg,
    isBarionPaymentIdUsable,
    orderIdsFromCreateResponse,
    barionRedirectUrlFromStart,
    retryBarionPaymentForOrderGroup,
    initUserOrdersPaymentRetryListener,
    handleBarionUrlParamsOnBoot,
    syncCheckoutEmailFromSession,
    syncCheckoutAuthPanel,
    showPostPurchaseAccountOffer,
    hidePostPurchaseAccountOffer,
    init,
  };
})();
