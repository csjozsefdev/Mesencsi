const $ = (id) => document.getElementById(id);
const Mesencsi = (window.Mesencsi = window.Mesencsi || {});
Mesencsi.$ = Mesencsi.$ || $;
const storage = (Mesencsi.storage = Mesencsi.storage || null);
const dom = (Mesencsi.dom = Mesencsi.dom || null);
const apiClient = (Mesencsi.api = Mesencsi.api || null);
const address = (Mesencsi.address = Mesencsi.address || null);
const authUi = (Mesencsi.authUi = Mesencsi.authUi || null);
const cartMod = (Mesencsi.cart = Mesencsi.cart || null);
const checkoutMod = (Mesencsi.checkout = Mesencsi.checkout || null);
const ordersUi = (Mesencsi.ordersUi = Mesencsi.ordersUi || null);
const discountsUi = (Mesencsi.discountsUi = Mesencsi.discountsUi || null);
const newsMod = (Mesencsi.news = Mesencsi.news || null);
const galleryMod = (Mesencsi.gallery = Mesencsi.gallery || null);
const storybooksMod = (Mesencsi.storybooks = Mesencsi.storybooks || null);
const productsMod = (Mesencsi.products = Mesencsi.products || null);
const routerMod = (Mesencsi.router = Mesencsi.router || null);
const bootMod = (Mesencsi.boot = Mesencsi.boot || null);
const notify = Mesencsi.notify || null;

const VIEWS = (routerMod && routerMod.VIEWS) || [];

/** Visszatéréskor: melyik nézet volt a fiók panel megnyitása előtt (SPA). */
var __mesencsiViewBeforeUserAccount = null;
/** @type {null | "profile" | "orders" | "discounts" | "account"} */
var activeUserSection = null;
function hideAllUserSectionShells() {
  ["Account", "Profile", "Orders", "Discounts"].forEach(function (suf) {
    const el = $("userSection" + suf);
    if (el) el.hidden = true;
  });
}

function syncUserNavActiveClasses() {
  const nav = $("userPanelNav");
  if (!nav) return;
  nav.querySelectorAll("[data-user-section]").forEach(function (btn) {
    const sec = btn.getAttribute("data-user-section");
    if (sec && activeUserSection === sec) {
      btn.classList.add("user-panel__nav-btn--active");
      btn.setAttribute("aria-current", "page");
    } else {
      btn.classList.remove("user-panel__nav-btn--active");
      btn.removeAttribute("aria-current");
    }
  });
}

function closeUserAccountPanelsOnly() {
  __mesencsiViewBeforeUserAccount = null;
  activeUserSection = null;
  hideAllUserSectionShells();
  const dock = $("userAccountDock");
  if (dock) dock.hidden = true;
  const stack = $("pageStack");
  if (stack) {
    stack.removeAttribute("data-user-account-open");
    stack.removeAttribute("data-active-user-section");
  }
  syncUserNavActiveClasses();
}

function rememberViewBeforeUserAccount() {
  if (__mesencsiViewBeforeUserAccount != null) return;
  const stack = $("pageStack");
  __mesencsiViewBeforeUserAccount =
    (stack && stack.getAttribute("data-current-view")) || "home";
}

function openUserAccountContent() {
  rememberViewBeforeUserAccount();
  const stack = $("pageStack");
  if (stack) stack.setAttribute("data-user-account-open", "1");
  const dock = $("userAccountDock");
  if (dock) dock.hidden = false;
  VIEWS.forEach(function (v) {
    const el = $("view-" + v);
    if (!el) return;
    el.classList.remove("is-active");
    el.hidden = true;
  });
  const homeIntro = $("homeIntro");
  if (homeIntro) homeIntro.hidden = true;
  const heroBand = $("heroBand");
  if (heroBand) heroBand.hidden = true;
  const archive = $("homeNewsArchive");
  if (archive) archive.hidden = true;
  document
    .querySelectorAll("[data-news-post-comments]")
    .forEach(function (block) {
      block.hidden = true;
    });
  try {
    if (typeof window.mesencsiCloseMobileNav === "function")
      window.mesencsiCloseMobileNav();
  } catch (_) {}
  window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
}

function userAccountDockBack() {
  const saved = __mesencsiViewBeforeUserAccount;
  __mesencsiViewBeforeUserAccount = null;
  activeUserSection = null;
  hideAllUserSectionShells();
  const dock = $("userAccountDock");
  if (dock) dock.hidden = true;
  const stack = $("pageStack");
  if (stack) {
    stack.removeAttribute("data-user-account-open");
    stack.removeAttribute("data-active-user-section");
  }
  syncUserNavActiveClasses();
  showView(saved || "home");
}


function emptyProfileAddressParts() {
  return address.emptyProfileAddressParts();
}
function containsUnsafeMarkup(value) {
  return address.containsUnsafeMarkup(value);
}
function zipCityMismatchWarningHu(postalCode, city) {
  return address.zipCityMismatchWarningHu(postalCode, city);
}
function validatePersonNameField(value, label, field) {
  return address.validatePersonNameField(value, label, field);
}
function validateEmailField(value) {
  return address.validateEmailField(value);
}
function buildValidatedShippingJson(parts, phoneOverride) {
  return address.buildValidatedShippingJson(parts, phoneOverride);
}
function buildOptionalProfileAddressJson(parts, phoneOverride) {
  if (!address || !address.buildOptionalProfileAddressJson) {
    return {
      ok: false,
      errors: [
        {
          field: null,
          message:
            "A címellenőrzés nem töltődött be — frissítsd az oldalt (Ctrl+F5).",
        },
      ],
      warnings: [],
    };
  }
  return address.buildOptionalProfileAddressJson(parts, phoneOverride);
}
function formatShippingAddressPlainFromParts(parts) {
  return address.formatShippingAddressPlainFromParts(parts);
}
function formatShippingAddressPlainFromRaw(raw) {
  return address.formatShippingAddressPlainFromRaw(raw);
}
function parseProfileAddressRaw(raw) {
  return address.parseProfileAddressRaw(raw);
}
function validatePhoneOnly(raw) {
  return address.validatePhoneOnly(raw);
}
function profileAddressPartsFromInputs(prefix) {
  function gv(id) {
    const el = $(id);
    return el && el.value != null ? String(el.value).trim() : "";
  }
  let phone = "";
  if (prefix === "checkoutShip") {
    const cp = $("checkoutPhone");
    phone = cp && cp.value != null ? String(cp.value).trim() : "";
  } else if (prefix === "profShip") {
    const pp = $("profPhone");
    phone = pp && pp.value != null ? String(pp.value).trim() : "";
  } else {
    phone = gv(prefix + "Phone");
  }
  return {
    recipient_name: gv(prefix + "Name"),
    phone: phone,
    postal_code: gv(prefix + "Zip"),
    city: gv(prefix + "City"),
    street: gv(prefix + "Street"),
    house_number: gv(prefix + "House"),
    line2: gv(prefix + "Line2"),
    country: gv(prefix + "Country"),
  };
}

function applyProfileAddressPartsToInputs(prefix, parts) {
  const map = {
    recipient_name: prefix + "Name",
    postal_code: prefix + "Zip",
    city: prefix + "City",
    street: prefix + "Street",
    house_number: prefix + "House",
    line2: prefix + "Line2",
    country: prefix + "Country",
  };
  Object.keys(map).forEach(function (k) {
    const el = $(map[k]);
    if (el) el.value = parts[k] != null ? String(parts[k]) : "";
  });
  if (parts.phone != null) {
    if (prefix === "checkoutShip") {
      const cp = $("checkoutPhone");
      if (cp) cp.value = String(parts.phone);
    } else if (prefix === "profShip") {
      const pp = $("profPhone");
      if (pp && !pp.value.trim()) pp.value = String(parts.phone);
    } else {
      const el = $(prefix + "Phone");
      if (el) el.value = String(parts.phone);
    }
  }
}

function serializeProfileAddressFromParts(parts) {
  const p = normalizeProfileAddressObject(parts);
  const any =
    p.recipient_name ||
    p.phone ||
    p.postal_code ||
    p.city ||
    p.street ||
    p.house_number ||
    p.line2 ||
    (p.country && p.country !== "Magyarország");
  if (!any) return null;
  return JSON.stringify({
    v: PROFILE_ADDRESS_JSON_V,
    recipient_name: p.recipient_name || null,
    phone: p.phone || null,
    postal_code: p.postal_code || null,
    city: p.city || null,
    street: p.street || null,
    house_number: p.house_number || null,
    line2: p.line2 || null,
    country: p.country || null,
  });
}

function clearCheckoutShippingFields() {
  applyProfileAddressPartsToInputs("checkoutShip", emptyProfileAddressParts());
  const ph = $("checkoutPhone");
  if (ph) ph.value = "";
  const warn = $("checkoutZipCityWarn");
  if (warn) {
    warn.textContent = "";
    warn.hidden = true;
  }
  updateCheckoutAddressConfirmPreview();
}

function checkoutShippingAddressPayload() {
  const parts = profileAddressPartsFromInputs("checkoutShip");
  const phoneEl = $("checkoutPhone");
  const phoneOverride = phoneEl && phoneEl.value != null ? phoneEl.value : "";
  return buildValidatedShippingJson(parts, phoneOverride);
}

function updateCheckoutAddressConfirmPreview() {
  const box = $("checkoutAddressConfirmBody");
  const wrap = $("checkoutAddressConfirm");
  if (!box || !wrap) return;
  const parts = profileAddressPartsFromInputs("checkoutShip");
  const phoneEl = $("checkoutPhone");
  if (phoneEl) parts.phone = phoneEl.value.trim();
  const plain = formatShippingAddressPlainFromParts(parts);
  const name = $("checkoutName") && $("checkoutName").value.trim();
  const email = $("checkoutEmail") && $("checkoutEmail").value.trim();
  const lines = [];
  if (name) lines.push("Megrendelő: " + name);
  if (email) lines.push("E-mail: " + email);
  if (plain) lines.push(plain);
  box.textContent = lines.length
    ? lines.join("\n")
    : "Töltsd ki a szállítási mezőket.";
  wrap.hidden = false;
}

function wireCheckoutAddressConfirmPreview() {
  const ids = [
    "checkoutName",
    "checkoutEmail",
    "checkoutPhone",
    "checkoutShipName",
    "checkoutShipZip",
    "checkoutShipCity",
    "checkoutShipStreet",
    "checkoutShipHouse",
    "checkoutShipLine2",
    "checkoutShipCountry",
  ];
  ids.forEach(function (id) {
    const el = $(id);
    if (!el || el.dataset.confirmPreviewWired) return;
    el.dataset.confirmPreviewWired = "1";
    el.addEventListener("input", function () {
      const zip = $("checkoutShipZip");
      const city = $("checkoutShipCity");
      const warn = $("checkoutZipCityWarn");
      if (warn && zip && city) {
        const w = zipCityMismatchWarningHu(zip.value, city.value);
        if (w) {
          warn.textContent = w;
          warn.hidden = false;
        } else {
          warn.textContent = "";
          warn.hidden = true;
        }
      }
      updateCheckoutAddressConfirmPreview();
    });
  });
}

async function importCheckoutShippingFromProfile() {
  const msg = $("cartMsg");
  if (!isShopUserLoggedIn()) {
    if (msg) show(msg, MSG_PURCHASE_AUTH, false);
    return;
  }
  try {
    const me = await api("/auth/me", { method: "GET" });
    const parsed = parseProfileAddressRaw(me && me.shipping_address);
    const p = parsed.parts;
    const hasAny =
      p.recipient_name ||
      p.postal_code ||
      p.city ||
      p.street ||
      p.line2 ||
      p.country;
    if (!hasAny) {
      if (msg) {
        show(
          msg,
          "A profilodban még nincs mentett szállítási cím — add meg a Fiók → Profil menüben, vagy írd be kézzel.",
          false,
        );
      }
      return;
    }
    applyProfileAddressPartsToInputs("checkoutShip", p);
    if (me && me.phone) {
      const cp = $("checkoutPhone");
      if (cp && !cp.value.trim()) cp.value = String(me.phone).trim();
    }
    const nm = $("checkoutName");
    if (nm && !nm.value.trim() && p.recipient_name) nm.value = p.recipient_name;
    updateCheckoutAddressConfirmPreview();
    if (msg) hide(msg);
  } catch (err) {
    if (msg)
      show(
        msg,
        (err && err.message) || "Nem sikerült betölteni a profil címét.",
        false,
      );
  }
}

function syncProfileBillingBlockVisibility() {
  const same = $("profBillSame");
  const block = $("profBillingBlock");
  if (!block) return;
  block.hidden = !!(same && same.checked);
}

function avatarDisplayNameFromUser(me) {
  if (!me) return "";
  const nick = me.nickname != null ? String(me.nickname).trim() : "";
  if (nick) return nick;
  const user = me.username != null ? String(me.username).trim() : "";
  if (user) return user;
  const mail = me.email != null ? String(me.email).trim() : "";
  if (mail && mail.indexOf("@") > 0) return mail.split("@")[0];
  return mail;
}

function avatarInitialsFromDisplayName(name) {
  const raw = String(name || "").trim();
  if (!raw) return "";
  const parts = raw.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (
      parts[0].charAt(0) + parts[parts.length - 1].charAt(0)
    ).toUpperCase();
  }
  if (parts[0].length >= 2) return parts[0].slice(0, 2).toUpperCase();
  return parts[0].charAt(0).toUpperCase();
}

/** Warm Mesencsi palette — deterministic from display name (no gender field in profile). */
function avatarPlaceholderColors(name) {
  const raw = String(name || "")
    .trim()
    .toLowerCase();
  const palettes = [
    ["#fff8eb", "#d4af5f"],
    ["#f5ebe3", "#b88862"],
    ["#eef3f8", "#7a9ab8"],
    ["#edf5ee", "#6f9474"],
    ["#f3ecf8", "#9a7fad"],
  ];
  if (!raw) return palettes[0];
  let h = 0;
  for (let i = 0; i < raw.length; i++) h = (h * 31 + raw.charCodeAt(i)) | 0;
  return palettes[Math.abs(h) % palettes.length];
}

function applyAvatarPlaceholder(el, meOrName) {
  if (!el) return;
  const name =
    typeof meOrName === "string"
      ? meOrName.trim()
      : avatarDisplayNameFromUser(meOrName);
  const initials = avatarInitialsFromDisplayName(name);
  el.textContent = "";
  el.classList.remove("avatar-ph--icon", "avatar-ph--initials");
  el.style.removeProperty("--avatar-ph-top");
  el.style.removeProperty("--avatar-ph-bottom");
  if (initials) {
    const colors = avatarPlaceholderColors(name);
    el.textContent = initials;
    el.classList.add("avatar-ph--initials");
    el.style.setProperty("--avatar-ph-top", colors[0]);
    el.style.setProperty("--avatar-ph-bottom", colors[1]);
    el.setAttribute("aria-label", "Profilkép: " + name);
  } else {
    el.classList.add("avatar-ph--icon");
    el.setAttribute("aria-label", "Alapértelmezett profilkép");
  }
}

function isProfileImageUrlOk(u) {
  const s = u != null ? String(u).trim() : "";
  if (!s || s.indexOf("..") >= 0) return false;
  if (
    /^\s*javascript\s*:/i.test(s) ||
    /^\s*data\s*:/i.test(s) ||
    /^\s*\/\//.test(s)
  )
    return false;
  if (/^https?:\/\//i.test(s)) return false;
  if (s.startsWith("/media/uploads/avatars/")) return true;
  return /^\/images\/avatars\/presets\/preset-[1-4]\.svg$/i.test(s);
}

function resolveAvatarDisplayContext(meOrName, profileImageUrl) {
  const display =
    meOrName ||
    (function () {
      const nick = $("profNickname") && $("profNickname").value.trim();
      if (nick) return { nickname: nick };
      return shopUserProfile();
    })();
  const url =
    profileImageUrl != null
      ? String(profileImageUrl).trim()
      : display && display.profile_image_url != null
        ? String(display.profile_image_url).trim()
        : "";
  const label = avatarDisplayNameFromUser(display) || "Profilkép";
  return {
    display: display,
    url: url,
    label: label,
    ok: isProfileImageUrlOk(url),
  };
}

function wireAvatarImgFallback(img, ph, meOrName) {
  if (!img || !ph) return;
  img.onerror = function () {
    img.removeAttribute("src");
    img.hidden = true;
    ph.hidden = false;
    applyAvatarPlaceholder(ph, meOrName);
  };
}

/** Shared avatar sync for user menu + profile preview (image, initials, or neutral icon). */
function syncAvatarElements(img, ph, profileImageUrl, meOrName, altText) {
  if (!ph) return;
  const ctx = resolveAvatarDisplayContext(meOrName, profileImageUrl);
  if (img) {
    img.onerror = null;
    if (ctx.ok) {
      wireAvatarImgFallback(img, ph, ctx.display);
      img.src = ctx.url;
      img.alt = altText || ctx.label;
      img.hidden = false;
      ph.hidden = true;
      return;
    }
    img.removeAttribute("src");
    img.hidden = true;
  }
  ph.hidden = false;
  applyAvatarPlaceholder(ph, ctx.display);
}

function applyProfileAvatarPreview(url, meOrName) {
  const hidden = $("profProfileImageUrl");
  const u = url != null ? String(url).trim() : "";
  if (hidden) hidden.value = u;
  syncAvatarElements(
    $("profAvatarPreviewImg"),
    $("profAvatarPreviewPh"),
    u,
    meOrName,
    "Profilkép előnézet",
  );
}

function initProfileAvatarPresetsOnce() {
  const wrap = $("profAvatarPresets");
  if (!wrap || wrap.dataset.wired) return;
  wrap.dataset.wired = "1";
  const paths = [
    "/images/avatars/presets/preset-1.svg",
    "/images/avatars/presets/preset-2.svg",
    "/images/avatars/presets/preset-3.svg",
    "/images/avatars/presets/preset-4.svg",
  ];
  paths.forEach(function (src, idx) {
    const b = document.createElement("button");
    b.type = "button";
    b.title = "Előre beállított profilkép " + (idx + 1);
    const im = document.createElement("img");
    im.src = src;
    im.alt = "";
    b.appendChild(im);
    b.addEventListener("click", async function () {
      if (!(await ensureShopUserSessionForWrite())) return;
      applyProfileAvatarPreview(src);
      setAuthLine($("profileMsg"), "", null);
      try {
        b.disabled = true;
        await syncCsrfToken();
        const updated = await api("/users/me", {
          method: "PATCH",
          body: JSON.stringify({ profile_image_url: src }),
        });
        applyProfileSaveSuccess(updated);
        const okText = "Profilkép kiválasztva és elmentve.";
        setAuthLine($("profileMsg"), okText, true);
        if (notify) notify.success(okText);
      } catch (err) {
        const errText =
          (notify && notify.messageFromError
            ? notify.messageFromError(err, "Mentés sikertelen.")
            : (err && err.message) || "Mentés sikertelen.");
        setAuthLine($("profileMsg"), errText, false);
        if (notify) notify.error(errText);
      } finally {
        b.disabled = false;
      }
    });
    wrap.appendChild(b);
  });
}

async function populateProfileFormFromServer() {
  if (!isShopUserLoggedIn()) return;
  setAuthLine($("profileMsg"), "", null);
  initProfileAvatarPresetsOnce();
  let me;
  try {
    me = await api("/auth/me", { method: "GET" });
  } catch (err) {
    setAuthLine(
      $("profileMsg"),
      (err && err.message) || "Nem sikerült betölteni a profilt.",
      false,
    );
    return;
  }
  if ($("profNickname"))
    $("profNickname").value = me.nickname != null ? String(me.nickname) : "";
  if ($("profEmail")) $("profEmail").value = me.email || "";
  if ($("profPhone"))
    $("profPhone").value = me.phone != null ? String(me.phone) : "";

  const shipParsed = parseProfileAddressRaw(me.shipping_address);
  applyProfileAddressPartsToInputs("profShip", shipParsed.parts);

  const billRaw =
    me.billing_address != null ? String(me.billing_address).trim() : "";
  const billSame = $("profBillSame");
  if (billSame) billSame.checked = !billRaw;
  syncProfileBillingBlockVisibility();
  if (billRaw) {
    const billParsed = parseProfileAddressRaw(billRaw);
    applyProfileAddressPartsToInputs("profBill", billParsed.parts);
  } else {
    applyProfileAddressPartsToInputs("profBill", emptyProfileAddressParts());
  }

  if ($("profShortBio")) $("profShortBio").value = me.short_bio || "";
  if ($("profFamilyNote")) $("profFamilyNote").value = me.family_note || "";
  applyProfileAvatarPreview(me.profile_image_url || "", me);

  const pvh = $("profVerifyHint");
  if (pvh) {
    pvh.textContent = userIsEmailVerified(me)
      ? "E-mail cím: megerősítve."
      : "E-mail cím: még nincs megerősítve — a „Fiók adatok” menüben kérhetsz új megerősítő e-mailt.";
  }
}

async function loadUserSectionContent(section) {
  if (section === "profile") {
    await populateProfileFormFromServer();
    return;
  }
  if (section === "orders") {
    await loadUserOrdersIntoPanel();
    return;
  }
  if (section === "discounts") {
    await loadUserDiscountsIntoPanel();
    return;
  }
  if (section === "account") {
    if (!isShopUserLoggedIn()) return;
    try {
      const me = await api("/auth/me", { method: "GET" });
      saveAuthSession("", me);
      fillUserPanel(me);
    } catch (_) {}
    return;
  }
}

async function setActiveUserSection(section) {
  if (!section) {
    userAccountDockBack();
    return;
  }
  if (!isShopUserLoggedIn()) return;
  openUserAccountContent();
  hideAllUserSectionShells();
  activeUserSection = section;
  const map = {
    profile: "Profile",
    orders: "Orders",
    discounts: "Discounts",
    account: "Account",
  };
  const wrap = $("userSection" + map[section]);
  if (wrap) wrap.hidden = false;
  const ps = $("pageStack");
  if (ps && section) ps.setAttribute("data-active-user-section", section);
  syncUserNavActiveClasses();
  try {
    if (typeof window.mesencsiCloseMobileNav === "function")
      window.mesencsiCloseMobileNav();
  } catch (_) {}
  await loadUserSectionContent(section);
}

function shopUserProfile() {
  if (authUi && authUi.shopUserProfile) return authUi.shopUserProfile();
  return null;
}

function shopUserAccessToken() {
  if (authUi && authUi.shopUserAccessToken) return authUi.shopUserAccessToken();
  return "";
}

function isShopUserLoggedIn() {
  if (authUi && authUi.isShopUserLoggedIn) return authUi.isShopUserLoggedIn();
  return false;
}

async function ensureShopUserSessionForWrite() {
  if (authUi && authUi.ensureShopUserSessionForWrite)
    return authUi.ensureShopUserSessionForWrite();
  return false;
}

function applyProfileSaveSuccess(updated) {
  saveAuthSession(null, updated);
  fillUserPanel(updated);
  if ($("profNickname"))
    $("profNickname").value =
      updated.nickname != null ? String(updated.nickname) : "";
  if ($("profEmail")) $("profEmail").value = updated.email || "";
  if ($("profPhone"))
    $("profPhone").value = updated.phone != null ? String(updated.phone) : "";
  const shipParsed = parseProfileAddressRaw(updated.shipping_address);
  applyProfileAddressPartsToInputs("profShip", shipParsed.parts);
  const billRaw =
    updated.billing_address != null
      ? String(updated.billing_address).trim()
      : "";
  const billSame = $("profBillSame");
  if (billSame) billSame.checked = !billRaw;
  syncProfileBillingBlockVisibility();
  if (billRaw) {
    const billParsed = parseProfileAddressRaw(updated.billing_address);
    applyProfileAddressPartsToInputs("profBill", billParsed.parts);
  }
  if ($("profShortBio")) $("profShortBio").value = updated.short_bio || "";
  if ($("profFamilyNote")) $("profFamilyNote").value = updated.family_note || "";
  applyProfileAvatarPreview(updated.profile_image_url || "", updated);
  const pvh = $("profVerifyHint");
  if (pvh) {
    pvh.textContent = userIsEmailVerified(updated)
      ? "E-mail cím: megerősítve."
      : "E-mail cím: még nincs megerősítve — a „Fiók adatok” menüben kérhetsz új megerősítő e-mailt.";
  }
  applyPurchaseGates();
  syncCheckoutEmailFromSession();
}

/* ----- Kosár: Mesencsi.cart (js/cart.js) — thin delegators ----- */
function cartItems() {
  return cartMod && cartMod.getItems ? cartMod.getItems() : [];
}
function cartSet(items) {
  if (cartMod && cartMod.setItems) cartMod.setItems(items);
}
function cartClear() {
  if (cartMod && cartMod.clear) cartMod.clear();
}
function cartSignature() {
  if (cartMod && cartMod.cartSignature) return cartMod.cartSignature();
  return "";
}
function checkoutCouponCode() {
  return cartMod && cartMod.getCheckoutCouponCode
    ? cartMod.getCheckoutCouponCode()
    : null;
}
function lastOrderEstimate() {
  return cartMod && cartMod.getLastOrderEstimate
    ? cartMod.getLastOrderEstimate()
    : null;
}
function checkoutEstimateSig() {
  return cartMod && cartMod.getCheckoutEstimateSig
    ? cartMod.getCheckoutEstimateSig()
    : "";
}
function cartRowsFromPayload(rows) {
  if (cartMod && cartMod.cartRowsFromPayload)
    return cartMod.cartRowsFromPayload(rows);
  return [];
}
function loadCartFromStorage() {
  if (cartMod && cartMod.loadCartFromStorage) return cartMod.loadCartFromStorage();
}
async function flushCartToServer() {
  if (cartMod && cartMod.flushCartToServer) return cartMod.flushCartToServer();
}
function persistCart() {
  if (cartMod && cartMod.persistCart) return cartMod.persistCart();
}
async function hydrateCartForLoggedInUser() {
  if (cartMod && cartMod.hydrateCartForLoggedInUser)
    return cartMod.hydrateCartForLoggedInUser();
}
function addToCart(product) {
  if (cartMod && cartMod.addToCart) return cartMod.addToCart(product);
}
function updateCartUI() {
  if (cartMod && cartMod.updateCartUI) return cartMod.updateCartUI();
}
function updateCartFabBadge() {
  if (cartMod && cartMod.updateCartFabBadge) return cartMod.updateCartFabBadge();
}
function scheduleCartPricingEstimate() {
  if (cartMod && cartMod.scheduleCartPricingEstimate)
    return cartMod.scheduleCartPricingEstimate();
}
async function applyCouponViaEstimate(rawCode, opts) {
  if (cartMod && cartMod.applyCouponViaEstimate)
    return cartMod.applyCouponViaEstimate(rawCode, opts);
}
async function restoreStoredCheckoutCoupon() {
  if (cartMod && cartMod.restoreStoredCheckoutCoupon)
    return cartMod.restoreStoredCheckoutCoupon();
}
function clearCheckoutCouponState() {
  if (cartMod && cartMod.clearCheckoutCouponState)
    return cartMod.clearCheckoutCouponState();
}
function updateCheckoutCouponDisplay() {
  if (cartMod && cartMod.updateCheckoutCouponDisplay)
    return cartMod.updateCheckoutCouponDisplay();
}
function bindUserDiscountPicker() {
  if (cartMod && cartMod.bindUserDiscountPicker)
    return cartMod.bindUserDiscountPicker();
}
function finalizeCheckoutCartUi() {
  if (cartMod && cartMod.finalizeCheckoutCartUi)
    return cartMod.finalizeCheckoutCartUi();
}
function getStoredCheckoutCoupon() {
  if (cartMod && cartMod.getStoredCheckoutCoupon)
    return cartMod.getStoredCheckoutCoupon();
  return "";
}

const MSG_WEBSHOP_AUTH = "A webshop használatához kérlek jelentkezz be.";
const MSG_PURCHASE_AUTH = "A vásárláshoz kérlek jelentkezz be.";
const MSG_STORYBOOKS_AUTH =
  "A mesekönyvek megtekintéséhez kérlek jelentkezz be.";
const MSG_EMPTY_PUBLIC = "Jelenleg nincs megjeleníthető tartalom.";

/** Lebegő kosár FAB: rejtve a kosár/checkout nézetben (checkout a view-cart alatt van). */
function syncCartFabVisibility() {
  if (cartMod && cartMod.syncCartFabVisibility)
    return cartMod.syncCartFabVisibility();
}

/**
 * Purchase gates: storybooks require login; webshop/cart are public.
 */
function applyPurchaseGates() {
  const ok = isShopUserLoggedIn();
  const nav = document.querySelector("nav.side-menu.wood-menu.side-rail-nav");
  if (nav) {
    nav
      .querySelectorAll('button[data-view="webshop"], button[data-view="cart"]')
      .forEach(function (btn) {
        btn.hidden = false;
        btn.setAttribute("aria-hidden", "false");
      });
    nav
      .querySelectorAll('button[data-view="storybooks"]')
      .forEach(function (btn) {
        btn.hidden = !ok;
        btn.setAttribute("aria-hidden", ok ? "false" : "true");
      });
    const storiesBtn = nav.querySelector('button[data-view="stories"]');
    if (storiesBtn) {
      storiesBtn.hidden = ok;
      storiesBtn.setAttribute("aria-hidden", ok ? "true" : "false");
    }
  }
  document
    .querySelectorAll(
      '.glass-card button[data-view="webshop"], .glass-card button[data-view="cart"]',
    )
    .forEach(function (el) {
      el.hidden = false;
      el.setAttribute("aria-hidden", "false");
    });
  if (ok) {
    void hydrateCartForLoggedInUser();
    const hint = $("webshopCartHint");
    if (hint) hint.hidden = true;
    syncCartFabVisibility();
    if (checkoutMod && checkoutMod.syncCheckoutAuthPanel) checkoutMod.syncCheckoutAuthPanel();
    return;
  }
  loadCartFromStorage();
  updateCartUI();
  const stack = $("pageStack");
  const cur = stack && stack.getAttribute("data-current-view");
  if (cur === "storybooks") {
    showView("home");
  }
  syncCartFabVisibility();
  if (checkoutMod && checkoutMod.syncCheckoutAuthPanel) checkoutMod.syncCheckoutAuthPanel();
}

function apiBase() {
  if (apiClient && apiClient.apiBase) return apiClient.apiBase();
  if (window.__MESENCsi_API_ORIGIN) return window.__MESENCsi_API_ORIGIN;
  const raw = ($("apiBase").value || "").replace(/\/$/, "").trim();
  if (raw) return raw;
  const loc = window.location;
  if (loc.port === "5500") return `${loc.protocol}//127.0.0.1:8000`;
  return loc.origin;
}

function apiBaseFallbacks() {
  if (apiClient && apiClient.apiBaseFallbacks) return apiClient.apiBaseFallbacks();
  const base = apiBase();
  const fallbacks = [base];
  if (base !== "http://127.0.0.1:8000") fallbacks.push("http://127.0.0.1:8000");
  if (base !== "http://localhost:8000") fallbacks.push("http://localhost:8000");
  return fallbacks;
}

async function api(path, opts = {}) {
  if (apiClient && apiClient.api) return apiClient.api(path, opts);
  throw new Error(friendlyBackendError());
}

/** Sync X-CSRF-Token with mesencsi_csrf cookie (required after login sets a new cookie). */
async function syncCsrfToken() {
  if (apiClient && apiClient.syncCsrfToken) return apiClient.syncCsrfToken();
  return false;
}

async function apiMultipart(path, formData, bearerToken) {
  if (apiClient && apiClient.apiMultipart)
    return apiClient.apiMultipart(path, formData, bearerToken);
  throw new Error(friendlyBackendError());
}

/* ----- Vásárlói auth: Mesencsi.authUi (js/auth-ui.js) — thin delegators ----- */
function saveAuthSession(token, profile) {
  if (authUi && authUi.saveAuthSession) return authUi.saveAuthSession(token, profile);
}

function clearAuthSession() {
  if (authUi && authUi.clearAuthSession) return authUi.clearAuthSession();
}

function setAuthLine(el, text, ok) {
  if (authUi && authUi.setAuthLine) return authUi.setAuthLine(el, text, ok);
}

/* ----- Checkout / Barion: Mesencsi.checkout (js/checkout.js) — thin delegators ----- */
function applyBarionReturnNotice() {
  if (checkoutMod && checkoutMod.applyBarionReturnNotice)
    return checkoutMod.applyBarionReturnNotice();
}
function clearBarionReturnNotice() {
  if (checkoutMod && checkoutMod.clearBarionReturnNotice)
    return checkoutMod.clearBarionReturnNotice();
}
function showBarionPaymentLandingNotice(detail, kind) {
  if (checkoutMod && checkoutMod.showBarionPaymentLandingNotice)
    return checkoutMod.showBarionPaymentLandingNotice(detail, kind);
}
function checkoutAbandonedGuidanceMsg(prefix) {
  if (checkoutMod && checkoutMod.checkoutAbandonedGuidanceMsg)
    return checkoutMod.checkoutAbandonedGuidanceMsg(prefix);
  return prefix || "";
}
function barionPaymentLandingErrorMsg(prefix) {
  if (checkoutMod && checkoutMod.barionPaymentLandingErrorMsg)
    return checkoutMod.barionPaymentLandingErrorMsg(prefix);
  return prefix || "";
}
function orderIdsFromCreateResponse(data) {
  if (checkoutMod && checkoutMod.orderIdsFromCreateResponse)
    return checkoutMod.orderIdsFromCreateResponse(data);
  return [];
}
function barionRedirectUrlFromStart(startPayload) {
  if (checkoutMod && checkoutMod.barionRedirectUrlFromStart)
    return checkoutMod.barionRedirectUrlFromStart(startPayload);
  return "";
}
async function retryBarionPaymentForOrderGroup(
  orderIds,
  minId,
  productLabel,
  triggerBtn,
) {
  if (checkoutMod && checkoutMod.retryBarionPaymentForOrderGroup)
    return checkoutMod.retryBarionPaymentForOrderGroup(
      orderIds,
      minId,
      productLabel,
      triggerBtn,
    );
}
function initUserOrdersPaymentRetryListener() {
  if (checkoutMod && checkoutMod.initUserOrdersPaymentRetryListener)
    return checkoutMod.initUserOrdersPaymentRetryListener();
}
async function syncCheckoutEmailFromSession() {
  if (checkoutMod && checkoutMod.syncCheckoutEmailFromSession)
    return checkoutMod.syncCheckoutEmailFromSession();
}

function hideAuthBoot() {
  if (authUi && authUi.hideAuthBoot) return authUi.hideAuthBoot();
}

function showAuthBoot() {
  if (authUi && authUi.showAuthBoot) return authUi.showAuthBoot();
}

function showAuthGuest() {
  if (authUi && authUi.showAuthGuest) return authUi.showAuthGuest();
}

function showAuthRegister() {
  if (authUi && authUi.showAuthRegister) return authUi.showAuthRegister();
}

function resetUserOrdersPanel() {
  if (ordersUi && ordersUi.resetPanel) ordersUi.resetPanel();
  if (discountsUi && discountsUi.resetPanel) discountsUi.resetPanel();
}

function shopPaymentStatusHu(s) {
  if (ordersUi && ordersUi.shopPaymentStatusHu)
    return ordersUi.shopPaymentStatusHu(s);
  return s || "—";
}

async function loadUserOrdersIntoPanel() {
  if (ordersUi && ordersUi.loadUserOrdersIntoPanel)
    return ordersUi.loadUserOrdersIntoPanel();
}

async function loadUserDiscountsIntoPanel() {
  if (discountsUi && discountsUi.loadUserDiscountsIntoPanel)
    return discountsUi.loadUserDiscountsIntoPanel();
}

function formatCouponExpiry(expiresAt) {
  if (discountsUi && discountsUi.formatCouponExpiry)
    return discountsUi.formatCouponExpiry(expiresAt);
  return "—";
}

function userIsEmailVerified(me) {
  if (authUi && authUi.userIsEmailVerified) return authUi.userIsEmailVerified(me);
  return false;
}

function fillUserPanel(me) {
  if (authUi && authUi.fillUserPanel) return authUi.fillUserPanel(me);
}

function showAuthUser(me) {
  if (authUi && authUi.showAuthUser) return authUi.showAuthUser(me);
}

async function refreshShopUser() {
  if (authUi && authUi.refreshShopUser) return authUi.refreshShopUser();
}

function show(el, msg, ok) {
  if (dom && dom.show) return dom.show(el, msg, ok);
  el.style.display = "block";
  el.className = "status " + (ok ? "ok" : "err");
  el.textContent = msg;
}

function hide(el) {
  if (dom && dom.hide) return dom.hide(el);
  el.style.display = "none";
  el.textContent = "";
}

function friendlyBackendError() {
  if (apiClient && apiClient.friendlyBackendError)
    return apiClient.friendlyBackendError();
  return "Most nem érjük el a boltot. Nézd meg az internetet, vagy próbáld újra egy kicsit később.";
}

/** Szerverválaszból érthető magyar szöveg (nem szakzsargon). */
function humanizeServerError(status, data, rawText) {
  if (apiClient && apiClient.humanizeServerError)
    return apiClient.humanizeServerError(status, data, rawText);
  return friendlyBackendError();
}

function formatPrice(n) {
  if (dom && dom.formatPrice) return dom.formatPrice(n);
  try {
    return new Intl.NumberFormat("hu-HU").format(n) + " Ft";
  } catch {
    return String(n) + " Ft";
  }
}

function escapeHtml(s) {
  if (dom && dom.escapeHtml) return dom.escapeHtml(s);
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* ----- News: Mesencsi.news (js/news.js) — thin delegators ----- */
async function loadHomeNews() {
  if (newsMod && newsMod.loadHomeNews) return newsMod.loadHomeNews();
}
function syncHomeNewsChrome(viewName) {
  if (newsMod && newsMod.syncHomeNewsChrome)
    return newsMod.syncHomeNewsChrome(viewName);
}
async function refreshAllNewsCommentsOnHome() {
  if (newsMod && newsMod.refreshAllNewsCommentsOnHome)
    return newsMod.refreshAllNewsCommentsOnHome();
}

/* ----- Gallery: Mesencsi.gallery (js/gallery.js) ----- */
async function ensureGallery() {
  if (galleryMod && galleryMod.ensureGallery) return galleryMod.ensureGallery();
}

/* ----- Storybooks: Mesencsi.storybooks (js/storybooks.js) ----- */
async function ensureStorybooksCatalog() {
  if (storybooksMod && storybooksMod.ensureStorybooksCatalog)
    return storybooksMod.ensureStorybooksCatalog();
}

/* ----- Products: Mesencsi.products (js/products.js) ----- */
async function ensureCatalog() {
  if (productsMod && productsMod.ensureCatalog) return productsMod.ensureCatalog();
}
async function ensureProductsCatalog() {
  if (productsMod && productsMod.ensureProductsCatalog)
    return productsMod.ensureProductsCatalog();
}

/* ----- Router: Mesencsi.router (js/router.js) ----- */
function showView(name) {
  if (routerMod && routerMod.showView) return routerMod.showView(name);
}
function navigateTo(path, viewName) {
  if (routerMod && routerMod.navigateTo) return routerMod.navigateTo(path, viewName);
}
function viewFromPathname(pathname) {
  if (routerMod && routerMod.viewFromPathname)
    return routerMod.viewFromPathname(pathname);
  return "home";
}



const btnCheckoutImportProfileAddress = $("btnCheckoutImportProfileAddress");
if (btnCheckoutImportProfileAddress) {
  btnCheckoutImportProfileAddress.addEventListener("click", function () {
    void importCheckoutShippingFromProfile();
  });
}

const btnCheckoutClearShippingAddress = $("btnCheckoutClearShippingAddress");
if (btnCheckoutClearShippingAddress) {
  btnCheckoutClearShippingAddress.addEventListener("click", function () {
    clearCheckoutShippingFields();
    const msg = $("cartMsg");
    if (msg) hide(msg);
  });
}

const userPanelNav = $("userPanelNav");
if (userPanelNav) {
  userPanelNav.addEventListener("click", function (ev) {
    const btn =
      ev.target && ev.target.closest
        ? ev.target.closest("[data-user-section]")
        : null;
    if (!btn) return;
    const sec = btn.getAttribute("data-user-section");
    if (!sec) return;
    ev.preventDefault();
    void setActiveUserSection(sec);
  });
}

const changePasswordForm = $("changePasswordForm");
if (changePasswordForm) {
  changePasswordForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    const msgEl = $("changePasswordMsg");
    const submitBtn = $("changePasswordSubmit");
    if (!isShopUserLoggedIn()) {
      setAuthLine(msgEl, "Előbb jelentkezz be.", false);
      return;
    }
    const current = ($("changePasswordCurrent") && $("changePasswordCurrent").value) || "";
    const password = ($("changePasswordNew") && $("changePasswordNew").value) || "";
    const passwordConfirm =
      ($("changePasswordConfirm") && $("changePasswordConfirm").value) || "";
    if (!current || !password || !passwordConfirm) {
      setAuthLine(msgEl, "Töltsd ki mindhárom mezőt.", false);
      return;
    }
    if (password.length < 8) {
      setAuthLine(msgEl, "Az új jelszónak legalább 8 karakter hosszúnak kell lennie.", false);
      return;
    }
    if (password !== passwordConfirm) {
      setAuthLine(msgEl, "Az új jelszó és a megerősítés nem egyezik.", false);
      return;
    }
    try {
      if (submitBtn) submitBtn.disabled = true;
      setAuthLine(msgEl, "Mentés…", null);
      await syncCsrfToken();
      const data = await api("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: current,
          password,
          password_confirm: passwordConfirm,
        }),
      });
      const okText =
        (data && data.message && String(data.message).trim()) || "A jelszó frissítve.";
      setAuthLine(msgEl, okText, true);
      if (notify) notify.success(okText);
      changePasswordForm.reset();
      const detailsEl = changePasswordForm.closest("details");
      if (detailsEl) detailsEl.open = false;
    } catch (err) {
      const errText =
        (notify && notify.messageFromError
          ? notify.messageFromError(err, "A jelszó mentése sikertelen.")
          : (err && err.message) || "A jelszó mentése sikertelen.");
      setAuthLine(msgEl, errText, false);
      if (notify) notify.error(errText);
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

const resendVerificationBtn = $("resendVerificationBtn");
if (resendVerificationBtn) {
  resendVerificationBtn.addEventListener("click", async function () {
    const rmsg = $("resendVerificationMsg");
    if (!isShopUserLoggedIn()) {
      setAuthLine(rmsg, "Előbb jelentkezz be.", false);
      if (notify) notify.warn("Előbb jelentkezz be.");
      return;
    }
    const sendResend = async function () {
      await syncCsrfToken();
      const data = await api("/auth/resend-verification", {
        method: "POST",
        body: "{}",
      });
      if (data && data.verification_email_sent === false) {
        const warnText =
          (data.message && String(data.message).trim()) ||
          (authUi && authUi.REGISTER_EMAIL_WARN_FALLBACK) ||
          "A megerősítő link a szerver naplójában lehet (fejlesztői mód).";
        setAuthLine(rmsg, warnText, "warn");
        if (notify) notify.warn(warnText);
        return;
      }
      const okText =
        "Ha van aktív SMTP, a levél úton van. (Fejlesztői módban nézd a szerver naplót.)";
      setAuthLine(rmsg, okText, true);
      if (notify) notify.success(okText);
    };
    try {
      if (notify && notify.run) {
        await notify.run({
          button: resendVerificationBtn,
          loadingText: "Küldés…",
          loadingInline: "Küldés…",
          inlineEl: rmsg,
          errorFallback: "Nem sikerült elkérni az új levelet.",
          fn: sendResend,
          toastOnly: true,
        });
      } else {
        setAuthLine(rmsg, "Küldés…", null);
        resendVerificationBtn.disabled = true;
        try {
          await sendResend();
        } finally {
          resendVerificationBtn.disabled = false;
        }
      }
    } catch (_) {}
  });
}

document.addEventListener("click", function (ev) {
  const link =
    ev.target && ev.target.closest
      ? ev.target.closest("[data-open-user-discounts]")
      : null;
  if (!link) return;
  ev.preventDefault();
  if (!isShopUserLoggedIn()) {
    setAuthLine($("loginMsg"), MSG_PURCHASE_AUTH, false);
    return;
  }
  void setActiveUserSection("discounts");
});

const cancelProfileBtn = $("cancelProfileBtn");
if (cancelProfileBtn) {
  cancelProfileBtn.addEventListener("click", function () {
    setAuthLine($("profileMsg"), "", null);
    userAccountDockBack();
  });
}

const userAccountDockBackBtn = $("userAccountDockBack");
if (userAccountDockBackBtn) {
  userAccountDockBackBtn.addEventListener("click", function () {
    userAccountDockBack();
  });
}


async function submitProfileFormAsync() {
  const msgEl = $("profileMsg");
  const formEl = $("profileForm");
  const submitBtn =
    formEl && formEl.querySelector('button[type="submit"]');
  if (!(await ensureShopUserSessionForWrite())) {
    setAuthLine(msgEl, "Előbb jelentkezz be.", false);
    return;
  }
  setAuthLine(msgEl, "Mentés…", null);
  if (submitBtn) submitBtn.disabled = true;
  try {
    const billSameEl = $("profBillSame");
    const sameBilling = !!(billSameEl && billSameEl.checked);
    const profPhoneVal = ($("profPhone") && $("profPhone").value.trim()) || "";
    const phoneErrProf = profPhoneVal ? validatePhoneOnly(profPhoneVal) : null;
    if (phoneErrProf) {
      setAuthLine(msgEl, phoneErrProf, false);
      return;
    }
    const shipBuilt = buildOptionalProfileAddressJson(
      profileAddressPartsFromInputs("profShip"),
      profPhoneVal,
    );
    if (!shipBuilt.ok) {
      setAuthLine(
        msgEl,
        (shipBuilt.errors[0] && shipBuilt.errors[0].message) ||
          "Érvénytelen szállítási cím.",
        false,
      );
      return;
    }
    let billBuilt = { ok: true, json: null };
    if (!sameBilling) {
      billBuilt = buildOptionalProfileAddressJson(
        profileAddressPartsFromInputs("profBill"),
        null,
      );
      if (!billBuilt.ok) {
        setAuthLine(
          msgEl,
          (billBuilt.errors[0] && billBuilt.errors[0].message) ||
            "Érvénytelen számlázási cím.",
          false,
        );
        return;
      }
    }
    const imgHidden = $("profProfileImageUrl");
    const profileImg =
      imgHidden && imgHidden.value != null
        ? String(imgHidden.value).trim()
        : "";
    const body = {
      nickname: ($("profNickname") && $("profNickname").value.trim()) || null,
      email: ($("profEmail") && $("profEmail").value.trim()) || "",
      phone: profPhoneVal || null,
      shipping_address: shipBuilt.json,
      billing_address: billBuilt.json,
      short_bio: ($("profShortBio") && $("profShortBio").value.trim()) || null,
      family_note:
        ($("profFamilyNote") && $("profFamilyNote").value.trim()) || null,
      profile_image_url: profileImg || null,
    };
    const profEmailErr = validateEmailField(body.email);
    if (profEmailErr) {
      setAuthLine(msgEl, profEmailErr, false);
      return;
    }
    await syncCsrfToken();
    const updated = await api("/users/me", {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    applyProfileSaveSuccess(updated);
    const okText =
      "Profil és címek mentve. A „Mégse” gombbal zárhatod.";
    setAuthLine(msgEl, okText, true);
    if (notify) notify.success(okText);
  } catch (err) {
    const errText =
      (notify && notify.messageFromError
        ? notify.messageFromError(err, "Mentés sikertelen.")
        : (err && err.message) || "Mentés sikertelen.");
    setAuthLine(msgEl, errText, false);
    if (notify) notify.error(errText);
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

const profileForm = $("profileForm");
if (profileForm) {
  profileForm.addEventListener("submit", function (e) {
    e.preventDefault();
    void submitProfileFormAsync();
  });
}

const profNicknameInput = $("profNickname");
if (profNicknameInput) {
  profNicknameInput.addEventListener("input", function () {
    const img = $("profAvatarPreviewImg");
    if (img && !img.hidden) return;
    const hidden = $("profProfileImageUrl");
    const url =
      hidden && hidden.value != null ? String(hidden.value).trim() : "";
    if (isProfileImageUrlOk(url)) return;
    applyProfileAvatarPreview("", { nickname: profNicknameInput.value });
  });
}

const profBillSame = $("profBillSame");
if (profBillSame) {
  profBillSame.addEventListener("change", function () {
    syncProfileBillingBlockVisibility();
    setAuthLine($("profileMsg"), "", null);
  });
}

const profAvatarUploadBtn = $("profAvatarUploadBtn");
if (profAvatarUploadBtn) {
  profAvatarUploadBtn.addEventListener("click", async function () {
    if (!isShopUserLoggedIn()) {
      setAuthLine($("profileMsg"), "Előbb jelentkezz be.", false);
      return;
    }
    const inp = $("profAvatarFile");
    setAuthLine($("profileMsg"), "", null);
    if (!inp || !inp.files || !inp.files[0]) {
      setAuthLine($("profileMsg"), "Előbb válassz ki egy képfájlt.", false);
      return;
    }
    const fd = new FormData();
    fd.append("file", inp.files[0]);
    try {
      profAvatarUploadBtn.disabled = true;
      await syncCsrfToken();
      const updated = await apiMultipart("/users/me/avatar", fd);
      applyProfileSaveSuccess(updated);
      try {
        inp.value = "";
      } catch (_) {}
      const okText = "Profilkép feltöltve és elmentve.";
      setAuthLine($("profileMsg"), okText, true);
      if (notify) notify.success(okText);
    } catch (err) {
      const errText =
        (notify && notify.messageFromError
          ? notify.messageFromError(err, "Feltöltés sikertelen.")
          : (err && err.message) || "Feltöltés sikertelen.");
      setAuthLine($("profileMsg"), errText, false);
      if (notify) notify.error(errText);
    } finally {
      profAvatarUploadBtn.disabled = false;
    }
  });
}

const profAvatarClearBtn = $("profAvatarClearBtn");
if (profAvatarClearBtn) {
  profAvatarClearBtn.addEventListener("click", async function () {
    if (!isShopUserLoggedIn()) {
      setAuthLine($("profileMsg"), "Előbb jelentkezz be.", false);
      return;
    }
    setAuthLine($("profileMsg"), "", null);
    try {
      profAvatarClearBtn.disabled = true;
      await syncCsrfToken();
      const updated = await api("/users/me", {
        method: "PATCH",
        body: JSON.stringify({ profile_image_url: null }),
      });
      applyProfileSaveSuccess(updated);
      const okText = "Profilkép eltávolítva.";
      setAuthLine($("profileMsg"), okText, true);
      if (notify) notify.success(okText);
    } catch (err) {
      const errText =
        (notify && notify.messageFromError
          ? notify.messageFromError(err, "Nem sikerült eltávolítani.")
          : (err && err.message) || "Nem sikerült eltávolítani.");
      setAuthLine($("profileMsg"), errText, false);
      if (notify) notify.error(errText);
    } finally {
      profAvatarClearBtn.disabled = false;
    }
  });
}

const deactivateAccountModal = $("deactivateAccountModal");
const deactivateAccountModalBackdrop = $("deactivateAccountModalBackdrop");
const deactivateAccountModalCancel = $("deactivateAccountModalCancel");
const deactivateAccountModalConfirm = $("deactivateAccountModalConfirm");
const deactivateAccountModalError = $("deactivateAccountModalError");

function closeDeactivateAccountModal() {
  if (deactivateAccountModal) deactivateAccountModal.hidden = true;
  if (deactivateAccountModalConfirm) {
    deactivateAccountModalConfirm.disabled = false;
    deactivateAccountModalConfirm.textContent = "Igen, deaktiválom";
  }
  if (deactivateAccountModalCancel)
    deactivateAccountModalCancel.disabled = false;
  if (deactivateAccountModalError) {
    deactivateAccountModalError.textContent = "";
    deactivateAccountModalError.hidden = true;
  }
}

function openDeactivateAccountModal() {
  if (!deactivateAccountModal) return;
  if (deactivateAccountModalError) {
    deactivateAccountModalError.textContent = "";
    deactivateAccountModalError.hidden = true;
  }
  if (deactivateAccountModalConfirm) {
    deactivateAccountModalConfirm.disabled = false;
    deactivateAccountModalConfirm.textContent = "Igen, deaktiválom";
  }
  if (deactivateAccountModalCancel)
    deactivateAccountModalCancel.disabled = false;
  deactivateAccountModal.hidden = false;
  try {
    if (deactivateAccountModalCancel) deactivateAccountModalCancel.focus();
  } catch (_) {}
}

document.addEventListener("keydown", function (ev) {
  const m = $("deactivateAccountModal");
  if (!m || m.hidden) return;
  if (ev.key === "Escape") {
    ev.preventDefault();
    closeDeactivateAccountModal();
  }
});

const deactivateAccountBtn = $("deactivateAccountBtn");
if (deactivateAccountBtn) {
  deactivateAccountBtn.addEventListener("click", function () {
    openDeactivateAccountModal();
  });
}
if (deactivateAccountModalBackdrop) {
  deactivateAccountModalBackdrop.addEventListener("click", function () {
    closeDeactivateAccountModal();
  });
}
if (deactivateAccountModalCancel) {
  deactivateAccountModalCancel.addEventListener("click", function () {
    closeDeactivateAccountModal();
  });
}
if (deactivateAccountModalConfirm) {
  deactivateAccountModalConfirm.addEventListener("click", async function () {
    if (!isShopUserLoggedIn()) {
      closeDeactivateAccountModal();
      return;
    }
    if (deactivateAccountModalError) {
      deactivateAccountModalError.textContent = "";
      deactivateAccountModalError.hidden = true;
    }
    deactivateAccountModalConfirm.disabled = true;
    if (deactivateAccountModalCancel)
      deactivateAccountModalCancel.disabled = true;
    deactivateAccountModalConfirm.textContent = "Deaktiválás…";
    try {
      await syncCsrfToken();
      await api("/users/me", { method: "DELETE" });
      closeDeactivateAccountModal();
      clearAuthSession();
      showAuthGuest();
      const em = $("checkoutEmail");
      if (em) em.value = "";
      const cn = $("checkoutName");
      if (cn) cn.value = "";
      clearCheckoutShippingFields();
      try {
        if (typeof window.mesencsiCloseMobileNav === "function")
          window.mesencsiCloseMobileNav();
      } catch (_) {}
      const okText =
        "A fiókod inaktiválva lett. Most kijelentkeztettünk — új regisztrációval tudsz majd belépni.";
      setAuthLine($("loginMsg"), okText, true);
      if (notify) notify.success(okText);
    } catch (err) {
      const msg =
        (notify && notify.messageFromError
          ? notify.messageFromError(
              err,
              "A deaktiválás nem sikerült. Próbáld újra később.",
            )
          : (err && err.message) ||
            "A deaktiválás nem sikerült. Próbáld újra később.");
      if (deactivateAccountModalError) {
        deactivateAccountModalError.textContent = msg;
        deactivateAccountModalError.hidden = false;
      }
      if (notify) notify.error(msg);
      deactivateAccountModalConfirm.disabled = false;
      if (deactivateAccountModalCancel)
        deactivateAccountModalCancel.disabled = false;
      deactivateAccountModalConfirm.textContent = "Igen, deaktiválom";
    }
  });
}

async function bootstrapAuthUiAsync() {
  if (authUi && authUi.bootstrapAuthUiAsync) return authUi.bootstrapAuthUiAsync();
  showAuthBoot();
  try {
    await refreshShopUser();
  } finally {
    hideAuthBoot();
  }
}

function initShopOrdersUiModule() {
  if (!ordersUi || !ordersUi.init) return;
  ordersUi.init({
    isShopUserLoggedIn: isShopUserLoggedIn,
    initUserOrdersPaymentRetryListener: initUserOrdersPaymentRetryListener,
    formatShippingAddressPlainFromRaw: formatShippingAddressPlainFromRaw,
  });
}

function initShopDiscountsUiModule() {
  if (!discountsUi || !discountsUi.init) return;
  discountsUi.init({
    isShopUserLoggedIn: isShopUserLoggedIn,
    escapeHtml: escapeHtml,
    bindUserDiscountPicker: bindUserDiscountPicker,
    getStoredCheckoutCoupon: getStoredCheckoutCoupon,
    clearCheckoutCouponState: clearCheckoutCouponState,
    updateCheckoutCouponDisplay: updateCheckoutCouponDisplay,
    syncUserDiscountRadios: function (code) {
      if (cartMod && cartMod.syncUserDiscountRadios)
        return cartMod.syncUserDiscountRadios(code);
    },
  });
}

function initShopNewsModule() {
  if (!newsMod || !newsMod.init) return;
  newsMod.init({
    isShopUserLoggedIn: isShopUserLoggedIn,
    shopUserProfile: shopUserProfile,
    userIsEmailVerified: userIsEmailVerified,
    setAuthLine: setAuthLine,
    escapeHtml: escapeHtml,
  });
}

function initShopGalleryModule() {
  if (!galleryMod || !galleryMod.init) return;
  galleryMod.init({
    escapeHtml: escapeHtml,
    friendlyBackendError: friendlyBackendError,
  });
}

function initShopStorybooksModule() {
  if (!storybooksMod || !storybooksMod.init) return;
  storybooksMod.init({
    escapeHtml: escapeHtml,
  });
}

function initShopProductsModule() {
  if (!productsMod || !productsMod.init) return;
  productsMod.init({
    isShopUserLoggedIn: isShopUserLoggedIn,
    escapeHtml: escapeHtml,
    formatPrice: formatPrice,
    MSG_WEBSHOP_AUTH: MSG_WEBSHOP_AUTH,
    MSG_PURCHASE_AUTH: MSG_PURCHASE_AUTH,
    MSG_EMPTY_PUBLIC: MSG_EMPTY_PUBLIC,
    friendlyBackendError: friendlyBackendError,
    addToCart: addToCart,
  });
}

function initShopRouterModule() {
  if (!routerMod || !routerMod.init) return;
  routerMod.init({
    isShopUserLoggedIn: isShopUserLoggedIn,
    setAuthLine: setAuthLine,
    hide: hide,
    MSG_WEBSHOP_AUTH: MSG_WEBSHOP_AUTH,
    MSG_PURCHASE_AUTH: MSG_PURCHASE_AUTH,
    MSG_STORYBOOKS_AUTH: MSG_STORYBOOKS_AUTH,
    closeUserAccountPanelsOnly: closeUserAccountPanelsOnly,
    syncHomeNewsChrome: syncHomeNewsChrome,
    syncCartFabVisibility: syncCartFabVisibility,
    ensureCatalog: ensureCatalog,
    updateCartUI: updateCartUI,
    syncCheckoutEmailFromSession: syncCheckoutEmailFromSession,
    wireCheckoutAddressConfirmPreview: wireCheckoutAddressConfirmPreview,
    updateCheckoutCouponDisplay: updateCheckoutCouponDisplay,
    cartItems: cartItems,
    scheduleCartPricingEstimate: scheduleCartPricingEstimate,
    restoreStoredCheckoutCoupon: restoreStoredCheckoutCoupon,
    ensureGallery: ensureGallery,
    ensureProductsCatalog: ensureProductsCatalog,
    ensureStorybooksCatalog: ensureStorybooksCatalog,
  });
}

function initShopCartModule() {
  if (!cartMod || !cartMod.init) return;
  cartMod.init({
    isShopUserLoggedIn: isShopUserLoggedIn,
    shopUserProfile: shopUserProfile,
    show: show,
    hide: hide,
    formatPrice: formatPrice,
    escapeHtml: escapeHtml,
    setAuthLine: setAuthLine,
    MSG_PURCHASE_AUTH: MSG_PURCHASE_AUTH,
    getUserDiscountCouponsCache: function () {
      if (discountsUi && discountsUi.getCouponsCache)
        return discountsUi.getCouponsCache();
      return [];
    },
    getCurrentView: function () {
      const stack = $("pageStack");
      return stack ? stack.getAttribute("data-current-view") : "";
    },
  });
}

function initShopCheckoutModule() {
  if (!checkoutMod || !checkoutMod.init) return;
  checkoutMod.init({
    isShopUserLoggedIn: isShopUserLoggedIn,
    show: show,
    hide: hide,
    setAuthLine: setAuthLine,
    MSG_PURCHASE_AUTH: MSG_PURCHASE_AUTH,
    cartItems: cartItems,
    cartSignature: cartSignature,
    checkoutCouponCode: checkoutCouponCode,
    getStoredCheckoutCoupon: getStoredCheckoutCoupon,
    lastOrderEstimate: lastOrderEstimate,
    checkoutEstimateSig: checkoutEstimateSig,
    finalizeCheckoutCartUi: finalizeCheckoutCartUi,
    validatePersonNameField: validatePersonNameField,
    validateEmailField: validateEmailField,
    validatePhoneOnly: validatePhoneOnly,
    checkoutShippingAddressPayload: checkoutShippingAddressPayload,
    containsUnsafeMarkup: containsUnsafeMarkup,
    friendlyBackendError: friendlyBackendError,
    shopPaymentStatusHu: shopPaymentStatusHu,
    setActiveUserSection: setActiveUserSection,
    wireCheckoutAddressConfirmPreview: wireCheckoutAddressConfirmPreview,
    updateCheckoutAddressConfirmPreview: updateCheckoutAddressConfirmPreview,
  });
}

function initShopAuthUiModule() {
  if (!authUi || !authUi.init) return;
  authUi.init({
    closeUserAccountPanelsOnly: closeUserAccountPanelsOnly,
    clearCheckoutCouponState: clearCheckoutCouponState,
    applyPurchaseGates: applyPurchaseGates,
    resetUserOrdersPanel: resetUserOrdersPanel,
    refreshAllNewsCommentsOnHome: refreshAllNewsCommentsOnHome,
    ensureProductsCatalog: ensureProductsCatalog,
    restoreStoredCheckoutCoupon: restoreStoredCheckoutCoupon,
    clearBarionReturnNotice: clearBarionReturnNotice,
    flushCartToServer: flushCartToServer,
    clearCheckoutShippingFields: clearCheckoutShippingFields,
    syncCheckoutEmailFromSession: syncCheckoutEmailFromSession,
    syncAvatarElements: syncAvatarElements,
    avatarDisplayNameFromUser: avatarDisplayNameFromUser,
    applyBarionReturnNotice: applyBarionReturnNotice,
    mesencsiResetOverlays: function () {
      if (typeof window.mesencsiResetOverlays === "function")
        window.mesencsiResetOverlays();
    },
    setCartEmpty: cartClear,
  });
}
function initMesencsiShop() {
  initShopOrdersUiModule();
  initShopDiscountsUiModule();
  initShopCartModule();
  initShopCheckoutModule();
  initShopAuthUiModule();
  initShopNewsModule();
  initShopGalleryModule();
  initShopStorybooksModule();
  initShopProductsModule();
  initShopRouterModule();
  if (bootMod && bootMod.start) {
    void bootMod.start({
      setAuthLine: setAuthLine,
      bootstrapAuthUiAsync: bootstrapAuthUiAsync,
      applyBarionReturnNotice: applyBarionReturnNotice,
      loadCartFromStorage: loadCartFromStorage,
      cartItems: cartItems,
      finalizeCheckoutCartUi: finalizeCheckoutCartUi,
      applyPurchaseGates: applyPurchaseGates,
      updateCartUI: updateCartUI,
      loadHomeNews: loadHomeNews,
      showView: showView,
      viewFromPathname: viewFromPathname,
    });
  }
}

initMesencsiShop();
