/**
 * Shop auth session + login/register/logout UI (Milestone 5).
 * Cookie session + CSRF via Mesencsi.api; profile cache in Mesencsi.storage.
 */
(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const $ = ns.$ || ((id) => document.getElementById(id));
  const storage = ns.storage || null;
  const apiClient = ns.api || null;
  const notify = ns.notify || null;

  const SHOP_USER_ACCESS_TOKEN_KEY = "mesencsi_user_access_token";
  const SHOP_USER_PROFILE_KEY = "mesencsi_user_profile_json";

  const REGISTER_SUCCESS_MSG =
    "Sikeres regisztráció! Kérlek ellenőrizd az emailed a megerősítéshez.";
  const REGISTER_EMAIL_WARN_FALLBACK =
    "A regisztráció sikeres. A megerősítő link a szerver termináljában van (fejlesztői mód: LOCAL DEV AUTH EMAIL). " +
    "Bejelentkezés után kérhetsz új megerősítő levelet is.";
  const REGISTER_REDIRECT_MS = 2800;

  /** @type {Record<string, Function>} */
  let deps = {};
  let registerRedirectTimer = null;

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

  function apiBaseFallbacks() {
    if (apiClient && apiClient.apiBaseFallbacks)
      return apiClient.apiBaseFallbacks();
    return [window.location.origin];
  }

  function friendlyBackendError() {
    if (apiClient && apiClient.friendlyBackendError)
      return apiClient.friendlyBackendError();
    return "Most nem érjük el a boltot.";
  }

  function humanizeServerError(status, data, rawText) {
    if (apiClient && apiClient.humanizeServerError)
      return apiClient.humanizeServerError(status, data, rawText);
    return friendlyBackendError();
  }

  function saveAuthSession(_token, profile) {
    try {
      if (profile) {
        if (storage && typeof storage.setJsonLocal === "function")
          storage.setJsonLocal(SHOP_USER_PROFILE_KEY, profile);
        else localStorage.setItem(SHOP_USER_PROFILE_KEY, JSON.stringify(profile));
      }
    } catch (_) {}
  }

  function clearAuthSession() {
    try {
      if (storage && typeof storage.removeLocal === "function") {
        storage.removeLocal(SHOP_USER_ACCESS_TOKEN_KEY);
        storage.removeLocal(SHOP_USER_PROFILE_KEY);
      } else {
        localStorage.removeItem(SHOP_USER_ACCESS_TOKEN_KEY);
        localStorage.removeItem(SHOP_USER_PROFILE_KEY);
      }
      try {
        delete window.__MESENCSI_CSRF_TOKEN;
      } catch (_) {}
    } catch (_) {}
  }

  function shopUserProfile() {
    if (storage && typeof storage.getJsonLocal === "function") {
      return storage.getJsonLocal(SHOP_USER_PROFILE_KEY);
    }
    try {
      const raw = localStorage.getItem(SHOP_USER_PROFILE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_) {
      return null;
    }
  }

  function shopUserAccessToken() {
    return "";
  }

  function isShopUserLoggedIn() {
    const p = shopUserProfile();
    return !!(p && p.id != null);
  }

  async function ensureShopUserSessionForWrite() {
    if (isShopUserLoggedIn()) return true;
    try {
      const me = await api("/auth/me", { method: "GET" });
      if (me && me.id != null) {
        saveAuthSession(null, me);
        return true;
      }
    } catch (_) {}
    return false;
  }

  function setAuthLine(el, text, ok) {
    if (!el) return;
    el.textContent = text || "";
    let cls = "auth-msg";
    if (ok === true) cls += " ok";
    else if (ok === "warn") cls += " warn";
    else if (ok === false) cls += " err";
    el.className = cls;
  }

  function authFeedback(el, text, ok, withToast) {
    setAuthLine(el, text, ok);
    if (!withToast || !notify || !text) return;
    if (ok === true) notify.success(text);
    else if (ok === "warn") notify.warn(text);
    else if (ok === false) notify.error(text);
  }

  function hideAuthBoot() {
    const boot = $("authBoot");
    if (boot) boot.hidden = true;
  }

  function showAuthBoot() {
    if (deps.closeUserAccountPanelsOnly) deps.closeUserAccountPanelsOnly();
    const boot = $("authBoot");
    const lo = $("authLoggedOut");
    const reg = $("authRegister");
    const li = $("authLoggedIn");
    if (boot) boot.hidden = false;
    if (lo) lo.hidden = true;
    if (reg) reg.hidden = true;
    if (li) li.hidden = true;
  }

  function setAuthPanelsLoggedOut() {
    const lo = $("authLoggedOut");
    const reg = $("authRegister");
    const li = $("authLoggedIn");
    if (lo) lo.hidden = false;
    if (reg) reg.hidden = true;
    if (li) li.hidden = true;
  }

  function setAuthPanelsRegister() {
    const lo = $("authLoggedOut");
    const reg = $("authRegister");
    const li = $("authLoggedIn");
    if (lo) lo.hidden = true;
    if (reg) reg.hidden = false;
    if (li) li.hidden = true;
  }

  function setAuthPanelsLoggedIn() {
    const lo = $("authLoggedOut");
    const reg = $("authRegister");
    const li = $("authLoggedIn");
    if (lo) lo.hidden = true;
    if (reg) reg.hidden = true;
    if (li) li.hidden = false;
  }

  function userIsEmailVerified(me) {
    if (!me) return false;
    if (me.is_verified === true) return true;
    return (
      me.email_verified_at != null && String(me.email_verified_at).length > 0
    );
  }

  function fillUserPanel(me) {
    const display = $("userPanelDisplayName");
    const loginId = $("userPanelLoginId");
    const em = $("userPanelEmail");
    const shortBio = $("userPanelShortBio");
    const famWrap = $("userPanelFamilyWrap");
    const famText = $("userPanelFamilyText");

    const nick =
      me && me.nickname != null && String(me.nickname).trim()
        ? String(me.nickname).trim()
        : "";
    const username = (me && me.username && String(me.username).trim()) || "";

    if (display) display.textContent = nick || username || "";
    if (loginId) {
      if (username) {
        loginId.textContent = "Felhasználónév: " + username;
        loginId.hidden = false;
      } else {
        loginId.textContent = "";
        loginId.hidden = true;
      }
    }
    if (em) {
      const mail = me && me.email ? String(me.email) : "";
      em.textContent = mail;
      em.title = mail;
    }

    const shortBioText = me && me.short_bio && String(me.short_bio).trim();
    if (shortBio) {
      if (shortBioText) {
        shortBio.textContent = shortBioText;
        shortBio.hidden = false;
      } else {
        shortBio.textContent = "";
        shortBio.hidden = true;
      }
    }
    const fn = me && me.family_note && String(me.family_note).trim();
    if (famWrap && famText) {
      if (fn) {
        famText.textContent = fn;
        famWrap.hidden = false;
      } else {
        famText.textContent = "";
        famWrap.hidden = true;
      }
    }
    if (deps.syncAvatarElements && deps.avatarDisplayNameFromUser) {
      deps.syncAvatarElements(
        $("userPanelAvatar"),
        $("userPanelAvatarPh"),
        me && me.profile_image_url,
        me,
        deps.avatarDisplayNameFromUser(me) || "Profilkép",
      );
    }
    const ban = $("userEmailVerifyBanner");
    const rmsg = $("resendVerificationMsg");
    if (rmsg) {
      rmsg.textContent = "";
      rmsg.className = "auth-msg";
    }
    if (ban) {
      ban.hidden = userIsEmailVerified(me);
    }
  }

  function showAuthGuest() {
    if (deps.closeUserAccountPanelsOnly) deps.closeUserAccountPanelsOnly();
    hideAuthBoot();
    if (deps.clearCheckoutCouponState) deps.clearCheckoutCouponState();
    setAuthPanelsLoggedOut();
    if (deps.resetUserOrdersPanel) deps.resetUserOrdersPanel();
    if (deps.applyPurchaseGates) deps.applyPurchaseGates();
    if (deps.refreshAllNewsCommentsOnHome) deps.refreshAllNewsCommentsOnHome();
    if (deps.mesencsiResetOverlays) deps.mesencsiResetOverlays();
  }

  function showAuthRegister() {
    hideAuthBoot();
    setAuthPanelsRegister();
    if (deps.clearBarionReturnNotice) deps.clearBarionReturnNotice();
    clearRegisterRedirectTimer();
    setRegisterFormBusy(false);
    setAuthLine($("loginMsg"), "", null);
    setAuthLine($("registerMsg"), "", null);
  }

  function showAuthUser(me) {
    if (deps.closeUserAccountPanelsOnly) deps.closeUserAccountPanelsOnly();
    hideAuthBoot();
    setAuthPanelsLoggedIn();
    if (deps.resetUserOrdersPanel) deps.resetUserOrdersPanel();
    fillUserPanel(me);
    setAuthLine($("loginMsg"), "", null);
    setAuthLine($("registerMsg"), "", null);
    setAuthLine($("profileMsg"), "", null);
    if (deps.applyBarionReturnNotice) deps.applyBarionReturnNotice();
    if (deps.applyPurchaseGates) deps.applyPurchaseGates();
    const ps = $("pageStack");
    if (ps && ps.getAttribute("data-current-view") === "stories") {
      if (deps.ensureProductsCatalog) deps.ensureProductsCatalog();
    }
    if (deps.refreshAllNewsCommentsOnHome) deps.refreshAllNewsCommentsOnHome();
    if (deps.mesencsiResetOverlays) deps.mesencsiResetOverlays();
    if (deps.restoreStoredCheckoutCoupon) deps.restoreStoredCheckoutCoupon();
  }

  async function refreshShopUser() {
    try {
      const me = await api("/auth/me", { method: "GET" });
      saveAuthSession("", me);
      showAuthUser(me);
      if (deps.syncCheckoutEmailFromSession) deps.syncCheckoutEmailFromSession();
    } catch (_) {
      clearAuthSession();
      showAuthGuest();
    }
  }

  async function bootstrapAuthUiAsync() {
    showAuthBoot();
    try {
      await refreshShopUser();
    } finally {
      hideAuthBoot();
    }
  }

  function clearRegisterRedirectTimer() {
    if (registerRedirectTimer) {
      clearTimeout(registerRedirectTimer);
      registerRedirectTimer = null;
    }
  }

  function setRegisterFormBusy(busy) {
    const form = $("registerForm");
    const submitBtn = $("registerSubmitBtn");
    const label = $("registerSubmitLabel");
    const backBtn = $("backToLoginBtn");
    const fields = form
      ? form.querySelectorAll("input:not([type='hidden']), button[type='button']")
      : [];
    if (submitBtn) {
      submitBtn.disabled = !!busy;
      submitBtn.setAttribute("aria-busy", busy ? "true" : "false");
    }
    if (label) {
      label.textContent = busy ? "Regisztráció…" : "Regisztráció";
    }
    if (backBtn) backBtn.disabled = !!busy;
    for (let i = 0; i < fields.length; i++) {
      const el = fields[i];
      if (el && el.id !== "backToLoginBtn") el.disabled = !!busy;
    }
  }

  function registrationDetailString(data) {
    if (!data) return "";
    if (typeof data.detail === "string") return data.detail;
    if (data.detail != null && !Array.isArray(data.detail))
      return String(data.detail);
    return "";
  }

  function isRegisterAccountCreatedWarning(status, detailStr) {
    return status === 503 && /regisztráció.*mentve/i.test(detailStr || "");
  }

  function registerOutcomeMessage(regData) {
    if (regData && regData.verification_email_sent === false) {
      return (
        (regData.message && String(regData.message).trim()) ||
        REGISTER_EMAIL_WARN_FALLBACK
      );
    }
    return REGISTER_SUCCESS_MSG;
  }

  function registerOutcomeKind(regData) {
    if (regData && regData.verification_email_sent === false) return "warn";
    return "ok";
  }

  async function postRegister(payload) {
    const bases = apiBaseFallbacks();
    let res = null;
    for (let i = 0; i < bases.length; i++) {
      const url = bases[i] + "/auth/register";
      try {
        res = await fetch(url, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });
        break;
      } catch (_) {
        res = null;
      }
    }
    if (!res) {
      throw new Error(friendlyBackendError());
    }
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }
    return { status: res.status, data, text };
  }

  function goToLoginAfterRegister(email, message, kind) {
    clearRegisterRedirectTimer();
    setRegisterFormBusy(false);
    if ($("loginEmail")) $("loginEmail").value = email;
    showAuthGuest();
    setAuthLine($("loginMsg"), message, kind);
    setAuthLine($("registerMsg"), "", null);
    if ($("loginPassword")) $("loginPassword").focus();
  }

  function scheduleRegisterRedirectToLogin(email, message, kind) {
    clearRegisterRedirectTimer();
    registerRedirectTimer = setTimeout(function () {
      registerRedirectTimer = null;
      goToLoginAfterRegister(email, message, kind);
    }, REGISTER_REDIRECT_MS);
  }

  function wireAuthForms() {
    const loginForm = $("loginForm");
    if (loginForm && !loginForm.dataset.authUiWired) {
      loginForm.dataset.authUiWired = "1";
      loginForm.addEventListener("submit", async function (e) {
        e.preventDefault();
        if (deps.clearBarionReturnNotice) deps.clearBarionReturnNotice();
        const loginMsg = $("loginMsg");
        setAuthLine(loginMsg, "", null);
        const email = ($("loginEmail") && $("loginEmail").value.trim()) || "";
        const password = ($("loginPassword") && $("loginPassword").value) || "";
        if (!email || !password) {
          authFeedback(
            loginMsg,
            "Add meg az e-mail címet és a jelszót.",
            false,
            true,
          );
          return;
        }
        const loginEmailEl = $("loginEmail");
        if (loginEmailEl && !loginEmailEl.checkValidity()) {
          try {
            loginEmailEl.reportValidity();
          } catch (_) {}
          return;
        }
        const submitBtn = loginForm.querySelector('button[type="submit"]');
        const runLogin = async function () {
          const data = await api("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email, password }),
          });
          if (!data || !data.user) {
            throw new Error("Váratlan válasz a szervertől.");
          }
          saveAuthSession(data.access_token || "", data.user);
          await syncCsrfToken();
          if ($("loginPassword")) $("loginPassword").value = "";
          if (deps.clearBarionReturnNotice) deps.clearBarionReturnNotice();
          showAuthUser(data.user);
          if (deps.syncCheckoutEmailFromSession)
            deps.syncCheckoutEmailFromSession();
          return data;
        };
        try {
          if (notify && notify.run) {
            await notify.run({
              button: submitBtn,
              inlineEl: loginMsg,
              loadingText: "Belépés…",
              loadingInline: "Belépés…",
              success: "Sikeres belépés.",
              errorFallback: "Belépés sikertelen.",
              fn: runLogin,
            });
          } else {
            const data = await runLogin();
            authFeedback(loginMsg, "Sikeres belépés.", true, true);
            void data;
          }
        } catch (_) {}
      });
    }

    const showReg = $("showRegisterBtn");
    if (showReg && !showReg.dataset.authUiWired) {
      showReg.dataset.authUiWired = "1";
      showReg.addEventListener("click", showAuthRegister);
    }

    const backLogin = $("backToLoginBtn");
    if (backLogin && !backLogin.dataset.authUiWired) {
      backLogin.dataset.authUiWired = "1";
      backLogin.addEventListener("click", function () {
        clearRegisterRedirectTimer();
        setRegisterFormBusy(false);
        showAuthGuest();
        setAuthLine($("registerMsg"), "", null);
      });
    }

    const registerForm = $("registerForm");
    if (registerForm && !registerForm.dataset.authUiWired) {
      registerForm.dataset.authUiWired = "1";
      registerForm.addEventListener("submit", async function (e) {
        e.preventDefault();
        clearRegisterRedirectTimer();
        setAuthLine($("registerMsg"), "", null);
        const submitBtn = $("registerSubmitBtn");
        if (submitBtn && submitBtn.disabled) return;

        const email = ($("regEmail") && $("regEmail").value.trim()) || "";
        const password = ($("regPassword") && $("regPassword").value) || "";
        const password2 = ($("regPassword2") && $("regPassword2").value) || "";
        if (!email || !password) {
          authFeedback(
            $("registerMsg"),
            "Az e-mail és a jelszó kötelező.",
            false,
            true,
          );
          return;
        }
        if (password.length < 8) {
          authFeedback(
            $("registerMsg"),
            "A jelszónak legalább 8 karakter hosszúnak kell lennie.",
            false,
            true,
          );
          return;
        }
        if (password !== password2) {
          authFeedback(
            $("registerMsg"),
            "A két jelszó nem egyezik.",
            false,
            true,
          );
          return;
        }
        const regEmailEl = $("regEmail");
        if (regEmailEl && !regEmailEl.checkValidity()) {
          try {
            regEmailEl.reportValidity();
          } catch (_) {}
          return;
        }
        const payload = {
          email,
          password,
          password_confirm: password2,
          company_website:
            ($("regCompanyWebsite") && $("regCompanyWebsite").value) || "",
        };

        setRegisterFormBusy(true);
        try {
          const { status, data, text } = await postRegister(payload);
          const detailStr = registrationDetailString(data);

          if (status === 201) {
            const kind = registerOutcomeKind(data);
            const message = registerOutcomeMessage(data);
            registerForm.reset();
            const full = message + " Átirányítás a bejelentkezéshez…";
            authFeedback($("registerMsg"), full, kind, true);
            scheduleRegisterRedirectToLogin(email, message, kind);
            return;
          }

          if (isRegisterAccountCreatedWarning(status, detailStr)) {
            const message = detailStr || REGISTER_EMAIL_WARN_FALLBACK;
            registerForm.reset();
            const full = message + " Átirányítás a bejelentkezéshez…";
            authFeedback($("registerMsg"), full, "warn", true);
            scheduleRegisterRedirectToLogin(email, message, "warn");
            return;
          }

          const hu = humanizeServerError(status, data, text);
          authFeedback($("registerMsg"), hu, false, true);
          setRegisterFormBusy(false);
        } catch (err) {
          const em =
            (notify && notify.messageFromError
              ? notify.messageFromError(err, "Regisztráció sikertelen.")
              : (err && err.message) || "Regisztráció sikertelen.");
          authFeedback($("registerMsg"), em, false, true);
          setRegisterFormBusy(false);
        }
      });
    }

    const logoutBtn = $("logoutBtn");
    if (logoutBtn && !logoutBtn.dataset.authUiWired) {
      logoutBtn.dataset.authUiWired = "1";
      logoutBtn.addEventListener("click", function () {
        if (deps.clearBarionReturnNotice) deps.clearBarionReturnNotice();
        setAuthLine($("loginMsg"), "", null);
        logoutBtn.disabled = true;
        const done = function () {
          logoutBtn.disabled = false;
          if (deps.setCartEmpty) deps.setCartEmpty();
          clearAuthSession();
          showAuthGuest();
          const em = $("checkoutEmail");
          if (em) em.value = "";
          const cn = $("checkoutName");
          if (cn) cn.value = "";
          if (deps.clearCheckoutShippingFields) deps.clearCheckoutShippingFields();
          authFeedback(
            $("loginMsg"),
            "Kijelentkeztél.",
            true,
            true,
          );
          try {
            if (typeof window.mesencsiCloseMobileNav === "function")
              window.mesencsiCloseMobileNav();
          } catch (_) {}
        };
        if (deps.flushCartToServer) {
          void deps
            .flushCartToServer()
            .catch(function () {
              if (notify)
                notify.warn(
                  "A kosár szinkronizálása nem sikerült — a helyi kosár megmaradt.",
                );
            })
            .finally(done);
        } else {
          done();
        }
      });
    }
  }

  function init(injectedDeps) {
    deps = injectedDeps || {};
    wireAuthForms();
    window.mesencsiAuthBootEscape = function () {
      const boot = $("authBoot");
      if (!boot || boot.hidden) return;
      hideAuthBoot();
      if (isShopUserLoggedIn()) {
        void refreshShopUser();
      } else {
        showAuthGuest();
      }
    };
  }

  ns.authUi = {
    SHOP_USER_ACCESS_TOKEN_KEY,
    SHOP_USER_PROFILE_KEY,
    REGISTER_EMAIL_WARN_FALLBACK,
    saveAuthSession,
    clearAuthSession,
    shopUserProfile,
    shopUserAccessToken,
    isShopUserLoggedIn,
    ensureShopUserSessionForWrite,
    setAuthLine,
    hideAuthBoot,
    showAuthBoot,
    showAuthGuest,
    showAuthRegister,
    showAuthUser,
    fillUserPanel,
    userIsEmailVerified,
    refreshShopUser,
    bootstrapAuthUiAsync,
    init,
  };
})();
