/**
 * Mobile drawer nav + overlay reset safety net (Milestone 9).
 */
(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});

  function initMobileDrawerNav() {
    var mq = window.matchMedia("(max-width: 768px)");
    var toggle = document.getElementById("mobileMenuToggle");
    var rail = document.getElementById("sideRail");
    var backdrop = document.getElementById("mobileNavBackdrop");
    function isMobileNav() {
      return mq.matches;
    }
    function syncMobileNavBackdrop(open) {
      if (!backdrop) return;
      if (open && isMobileNav()) {
        backdrop.hidden = false;
        backdrop.setAttribute("aria-hidden", "false");
      } else {
        backdrop.hidden = true;
        backdrop.setAttribute("aria-hidden", "true");
      }
    }
    function blurIfInside(el) {
      try {
        var ae = document.activeElement;
        if (!ae || !el) return;
        if (ae === el || el.contains(ae)) ae.blur();
      } catch (_) {}
    }
    function setMobileNavOpen(open) {
      if (!isMobileNav()) {
        document.body.classList.remove("mobile-nav-open");
        syncMobileNavBackdrop(false);
        blurIfInside(rail);
        if (toggle) {
          toggle.setAttribute("aria-expanded", "false");
          toggle.setAttribute("aria-label", "Menü megnyitása");
          toggle.textContent = "☰";
        }
        document.body.style.overflow = "";
        return;
      }
      if (open) {
        document.body.classList.add("mobile-nav-open");
        document.body.style.overflow = "hidden";
        syncMobileNavBackdrop(true);
        if (toggle) {
          toggle.setAttribute("aria-expanded", "true");
          toggle.setAttribute("aria-label", "Menü bezárása");
          toggle.textContent = "✕";
        }
      } else {
        blurIfInside(rail);
        document.body.classList.remove("mobile-nav-open");
        syncMobileNavBackdrop(false);
        if (toggle) {
          toggle.setAttribute("aria-expanded", "false");
          toggle.setAttribute("aria-label", "Menü megnyitása");
          toggle.textContent = "☰";
          try {
            toggle.focus();
          } catch (_) {}
        }
        document.body.style.overflow = "";
      }
    }
    function closeMobileNav() {
      setMobileNavOpen(false);
    }
    window.mesencsiCloseMobileNav = closeMobileNav;
    if (toggle) {
      toggle.addEventListener("click", function () {
        if (!isMobileNav()) return;
        var next = !document.body.classList.contains("mobile-nav-open");
        setMobileNavOpen(next);
      });
    }
    if (backdrop) {
      backdrop.addEventListener("click", function (e) {
        e.preventDefault();
        if (
          !isMobileNav() ||
          !document.body.classList.contains("mobile-nav-open")
        )
          return;
        closeMobileNav();
      });
    }
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      if (typeof window.mesencsiResetOverlays === "function")
        window.mesencsiResetOverlays();
      var bootEl = document.getElementById("authBoot");
      if (
        bootEl &&
        !bootEl.hidden &&
        typeof window.mesencsiAuthBootEscape === "function"
      ) {
        window.mesencsiAuthBootEscape();
      }
    });
    if (mq.addEventListener) {
      mq.addEventListener("change", function () {
        if (!mq.matches) closeMobileNav();
      });
    } else if (mq.addListener) {
      mq.addListener(function () {
        if (!mq.matches) closeMobileNav();
      });
    }
    if (rail) {
      rail.addEventListener("click", function (e) {
        if (
          !isMobileNav() ||
          !document.body.classList.contains("mobile-nav-open")
        )
          return;
        if (e.target.closest("[data-view]")) {
          closeMobileNav();
        }
      });
    }
  }

  function initOverlaySafetyNet() {
    function resetMobileChrome() {
      try {
        var dm = document.getElementById("deactivateAccountModal");
        if (dm && !dm.hidden) {
          try {
            var ae = document.activeElement;
            if (ae && dm.contains(ae)) ae.blur();
          } catch (_) {}
          dm.hidden = true;
        }
      } catch (_) {}
      try {
        if (typeof window.mesencsiCloseMobileNav === "function")
          window.mesencsiCloseMobileNav();
        else {
          document.body.classList.remove("mobile-nav-open");
          var tg0 = document.getElementById("mobileMenuToggle");
          if (tg0) {
            tg0.setAttribute("aria-expanded", "false");
            tg0.setAttribute("aria-label", "Menü megnyitása");
            tg0.textContent = "☰";
          }
        }
        var tg = document.getElementById("mobileMenuToggle");
        if (tg && !document.body.classList.contains("mobile-nav-open")) {
          tg.setAttribute("aria-expanded", "false");
          tg.setAttribute("aria-label", "Menü megnyitása");
          tg.textContent = "☰";
        }
        document.body.style.overflow = "";
      } catch (_) {}
    }
    window.mesencsiResetOverlays = resetMobileChrome;
    window.addEventListener("pageshow", function () {
      resetMobileChrome();
    });
  }

  function init() {
    initMobileDrawerNav();
    initOverlaySafetyNet();
  }

  ns.navOverlays = { init };
  init();
})();
