/**
 * SPA view switching and history navigation (Milestone 9).
 */
(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const $ = ns.$ || ((id) => document.getElementById(id));

  const VIEWS = [
    "webshop",
    "gallery",
    "stories",
    "storybooks",
    "cart",
    "aszf",
    "adatkezeles",
    "impresszum",
    "elallas",
    "szallitas",
    "fizetes",
    "panaszkezeles",
    "sutik",
  ];

  /** @type {Record<string, Function>} */
  let deps = {};

  function isLoggedIn() {
    return deps.isShopUserLoggedIn ? !!deps.isShopUserLoggedIn() : false;
  }

  function setAuthLine(el, text, ok) {
    if (deps.setAuthLine) return deps.setAuthLine(el, text, ok);
  }

  function hide(el) {
    if (deps.hide) return deps.hide(el);
  }

  function showView(name) {
    if (deps.closeUserAccountPanelsOnly) deps.closeUserAccountPanelsOnly();
    if (
      (name === "webshop" || name === "cart" || name === "storybooks") &&
      !isLoggedIn()
    ) {
      const msg =
        name === "webshop"
          ? deps.MSG_WEBSHOP_AUTH
          : name === "cart"
            ? deps.MSG_PURCHASE_AUTH
            : deps.MSG_STORYBOOKS_AUTH;
      setAuthLine($("loginMsg"), msg, false);
      showView("home");
      return;
    }

    if (name !== "home") {
      try {
        if (typeof window.mesencsiCloseMobileNav === "function")
          window.mesencsiCloseMobileNav();
      } catch (_) {}
    }

    const stack = $("pageStack");
    const prevView = stack
      ? stack.getAttribute("data-current-view") || "home"
      : "home";
    const homeIntro = $("homeIntro");
    const cartMsg = $("cartMsg");
    if (cartMsg) hide(cartMsg);

    if (name !== "webshop") {
      const hint = $("webshopCartHint");
      if (hint) hint.hidden = true;
    }

    VIEWS.forEach((v) => {
      const el = $("view-" + v);
      if (!el) return;
      el.classList.remove("is-active");
      el.hidden = true;
    });

    if (name === "home") {
      stack.setAttribute("data-current-view", "home");
      homeIntro.hidden = false;
      if (deps.syncHomeNewsChrome) deps.syncHomeNewsChrome("home");
      VIEWS.forEach((v) => {
        const el = $("view-" + v);
        if (!el) return;
        el.classList.remove("is-active");
        el.hidden = true;
      });
      window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
      if (deps.syncCartFabVisibility) deps.syncCartFabVisibility();
      return;
    }

    if (!VIEWS.includes(name)) {
      showView("home");
      return;
    }

    stack.setAttribute("data-current-view", name);
    homeIntro.hidden = true;
    if (deps.syncHomeNewsChrome) deps.syncHomeNewsChrome(name);
    const target = $("view-" + name);
    target.hidden = false;
    target.classList.add("is-active");
    window.scrollTo({ top: 0, left: 0, behavior: "smooth" });

    if (name === "webshop" && deps.ensureCatalog) deps.ensureCatalog();
    if (name === "cart") {
      if (deps.updateCartUI) deps.updateCartUI();
      if (deps.syncCheckoutEmailFromSession) deps.syncCheckoutEmailFromSession();
      if (deps.wireCheckoutAddressConfirmPreview)
        deps.wireCheckoutAddressConfirmPreview();
      if (deps.updateCheckoutCouponDisplay) deps.updateCheckoutCouponDisplay();
      if (isLoggedIn()) {
        if (deps.cartItems && deps.cartItems().length && deps.scheduleCartPricingEstimate)
          deps.scheduleCartPricingEstimate();
        else if (deps.restoreStoredCheckoutCoupon)
          void deps.restoreStoredCheckoutCoupon();
      }
    }
    if (name === "gallery" && prevView !== "gallery" && deps.ensureGallery)
      void deps.ensureGallery();
    if (name === "stories" && deps.ensureProductsCatalog)
      deps.ensureProductsCatalog();
    if (name === "storybooks" && deps.ensureStorybooksCatalog)
      deps.ensureStorybooksCatalog();
    if (deps.syncCartFabVisibility) deps.syncCartFabVisibility();
  }

  function navigateTo(path, viewName) {
    try {
      history.pushState({ view: viewName }, "", path);
    } catch (_) {}
    showView(viewName);
  }

  function viewFromPathname(pathname) {
    if (pathname === "/aszf") return "aszf";
    if (pathname === "/adatkezeles") return "adatkezeles";
    if (pathname === "/impresszum") return "impresszum";
    if (pathname === "/elallas") return "elallas";
    if (pathname === "/szallitas") return "szallitas";
    if (pathname === "/fizetes") return "fizetes";
    if (pathname === "/panaszkezeles") return "panaszkezeles";
    if (pathname === "/sutik") return "sutik";
    return "home";
  }

  function wireNavigation() {
    document.querySelectorAll("[data-view]").forEach((el) => {
      if (el.dataset.routerViewWired === "1") return;
      el.dataset.routerViewWired = "1";
      el.addEventListener("click", () => {
        const v = el.getAttribute("data-view");
        if (!v) return;
        if (
          (v === "webshop" || v === "cart" || v === "storybooks") &&
          !isLoggedIn()
        ) {
          const msg =
            v === "webshop"
              ? deps.MSG_WEBSHOP_AUTH
              : v === "cart"
                ? deps.MSG_PURCHASE_AUTH
                : deps.MSG_STORYBOOKS_AUTH;
          setAuthLine($("loginMsg"), msg, false);
          try {
            const le = $("loginEmail");
            if (le) le.focus();
          } catch (_) {}
          return;
        }
        try {
          history.pushState({ view: v }, "", "/");
        } catch (_) {}
        showView(v);
      });
    });

    document.querySelectorAll("[data-route]").forEach((el) => {
      if (el.dataset.routerRouteWired === "1") return;
      el.dataset.routerRouteWired = "1";
      el.addEventListener("click", (e) => {
        const path = el.getAttribute("data-route");
        if (!path) return;
        e.preventDefault();
        const view = viewFromPathname(path);
        if (view === "home") {
          navigateTo("/", "home");
        } else {
          navigateTo(path, view);
        }
      });
    });

    if (!window.__mesencsiPopstateWired) {
      window.__mesencsiPopstateWired = true;
      window.addEventListener("popstate", () => {
        showView(viewFromPathname(window.location.pathname));
      });
    }

    const cartFab = $("cartFab");
    if (cartFab && !cartFab.dataset.routerFabWired) {
      cartFab.dataset.routerFabWired = "1";
      cartFab.addEventListener("click", () => {
        if (!isLoggedIn()) {
          setAuthLine($("loginMsg"), deps.MSG_PURCHASE_AUTH, false);
          return;
        }
        try {
          history.pushState({ view: "cart" }, "", "/");
        } catch (_) {}
        showView("cart");
      });
    }
  }

  function init(injectedDeps) {
    deps = injectedDeps || {};
    wireNavigation();
  }

  ns.router = {
    VIEWS,
    showView,
    navigateTo,
    viewFromPathname,
    init,
  };
})();
