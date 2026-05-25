    (function () {
      function resolveBackendOrigin() {
        var el = document.getElementById("apiBase");
        var raw = (el && el.value ? String(el.value) : "").replace(/\/$/, "").trim();
        if (raw) return raw;
        var loc = window.location;
        if (loc.port === "5500") return loc.protocol + "//127.0.0.1:8000";
        return loc.origin;
      }
      window.__MESENCsi_API_ORIGIN = resolveBackendOrigin();
      var fab = document.getElementById("adminFab");
      if (fab) fab.setAttribute("href", window.__MESENCsi_API_ORIGIN + "/admin/login");
    })();

    const $ = (id) => document.getElementById(id);
    const SBR = window.MesencsiStorybookReader;

    const VIEWS = ["webshop", "gallery", "stories", "storybooks", "cart", "aszf", "adatkezeles", "impresszum"];

    /** Visszatéréskor: melyik nézet volt a fiók panel megnyitása előtt (SPA). */
    var __mesencsiViewBeforeUserAccount = null;
    /** @type {null | "profile" | "orders" | "discounts" | "account"} */
    var activeUserSection = null;
    function storybookEls() {
      return {
        catalogOut: $("storybooksCatalogOut"),
        publicList: $("storybooksPublicList"),
        publicReader: $("storybooksPublicReader"),
        readerOut: $("storybooksReaderOut"),
      };
    }

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
      __mesencsiViewBeforeUserAccount = (stack && stack.getAttribute("data-current-view")) || "home";
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
      document.querySelectorAll("[data-news-post-comments]").forEach(function (block) {
        block.hidden = true;
      });
      try {
        if (typeof window.mesencsiCloseMobileNav === "function") window.mesencsiCloseMobileNav();
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

    const PROFILE_ADDRESS_JSON_V = 2;

    const _UNSAFE_MARKUP_RE = /[<>]|javascript\s*:|data\s*:|vbscript\s*:|on\w+\s*=/i;
    const _HU_ZIP_RE = /^\d{4}$/;
    const _EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const _NAME_RE = /^[\w .'\-\u00c0-\u024f]{2,128}$/u;
    const _CITY_RE = /^[\w .'\-\u00c0-\u024f]{2,128}$/u;
    const _STREET_RE = /^[\w .'\-\u00c0-\u024f0-9]{2,256}$/u;
    const _HOUSE_RE = /^[\w .'\-\/\u00c0-\u024f0-9]{1,32}$/u;
    const _LINE2_RE = /^[\w .'\-\u00c0-\u024f0-9]{0,256}$/u;
    const _COUNTRY_RE = /^[\w .'\-\u00c0-\u024f]{2,128}$/u;

    function emptyProfileAddressParts() {
      return {
        recipient_name: "",
        phone: "",
        postal_code: "",
        city: "",
        street: "",
        house_number: "",
        line2: "",
        country: "Magyarország",
      };
    }

    function containsUnsafeMarkup(value) {
      return _UNSAFE_MARKUP_RE.test(String(value || ""));
    }

    function normalizeProfileAddressObject(o) {
      const p = emptyProfileAddressParts();
      if (!o || typeof o !== "object") return p;
      p.recipient_name = o.recipient_name != null ? String(o.recipient_name).trim() : "";
      p.phone = o.phone != null ? String(o.phone).trim() : "";
      p.postal_code = o.postal_code != null ? String(o.postal_code).trim() : "";
      p.city = o.city != null ? String(o.city).trim() : "";
      p.street = o.street != null ? String(o.street).trim() : "";
      p.house_number = o.house_number != null ? String(o.house_number).trim() : "";
      p.line2 = o.line2 != null ? String(o.line2).trim() : "";
      p.country = o.country != null ? String(o.country).trim() : "";
      if (!p.country) p.country = "Magyarország";
      return p;
    }

    function normalizeHuPhoneDigits(raw) {
      let digits = String(raw || "").replace(/\D/g, "");
      if (digits.indexOf("36") === 0 && digits.length >= 10) digits = digits.slice(2);
      if (digits.indexOf("06") === 0) digits = digits.slice(2);
      return digits;
    }

    function zipCityMismatchWarningHu(postalCode, city) {
      const z = String(postalCode || "").trim();
      const c = String(city || "")
        .trim()
        .toLowerCase();
      if (!z || !c || !/^\d{4}$/.test(z)) return null;
      const znum = parseInt(z, 10);
      if (znum >= 1000 && znum <= 1999 && c.indexOf("budapest") < 0) {
        return "Az irányítószám Budapesthez tartozhat — ellenőrizd a várost.";
      }
      if (znum >= 4000 && znum <= 4999 && c.indexOf("debrecen") < 0) {
        return "Az irányítószám Debrecenhez tartozhat — ellenőrizd a várost.";
      }
      if (znum >= 6000 && znum <= 6999 && c.indexOf("szeged") < 0) {
        return "Az irányítószám Szegedhez tartozhat — ellenőrizd a várost.";
      }
      return null;
    }

    function validateShippingAddressParts(parts, opts) {
      const requireAll = !opts || opts.requireAll !== false;
      const errors = [];
      const warnings = [];
      const p = normalizeProfileAddressObject(parts);

      function pushError(field, message) {
        errors.push({ field: field, message: message });
      }

      function requireField(field, label, value, minLen, maxLen, pattern, patternMsg) {
        const s = value != null ? String(value).trim() : "";
        if (!s) {
          if (requireAll) pushError(field, "A(z) " + label + " megadása kötelező.");
          return "";
        }
        if (s.length < minLen) {
          pushError(field, "A(z) " + label + " túl rövid.");
          return s;
        }
        if (s.length > maxLen) {
          pushError(field, "A(z) " + label + " legfeljebb " + maxLen + " karakter lehet.");
          return s;
        }
        if (containsUnsafeMarkup(s)) {
          pushError(field, "A(z) " + label + " nem tartalmazhat HTML-t vagy szkriptet.");
          return s;
        }
        if (pattern && !pattern.test(s)) {
          pushError(field, patternMsg || "A(z) " + label + " formátuma érvénytelen.");
        }
        return s;
      }

      if (!requireAll) {
        const any =
          p.recipient_name ||
          p.phone ||
          p.postal_code ||
          p.city ||
          p.street ||
          p.house_number ||
          p.line2 ||
          (p.country && p.country !== "Magyarország");
        if (!any) {
          return { ok: true, errors: [], warnings: [], normalized: emptyProfileAddressParts() };
        }
      }

      const recipient_name = requireField(
        "recipient_name",
        "átvevő neve",
        p.recipient_name,
        2,
        128,
        _NAME_RE,
        "Az átvevő neve csak betűket és szóközt tartalmazhat."
      );
      const phoneRaw = requireField("phone", "telefonszám", p.phone, 8, 32, null, null);
      if (phoneRaw && !errors.some(function (e) {
        return e.field === "phone";
      })) {
        const digits = normalizeHuPhoneDigits(phoneRaw);
        if (digits.length < 8 || digits.length > 9 || digits.charAt(0) === "0") {
          pushError("phone", "Érvénytelen magyar telefonszám (pl. 06 30 123 4567).");
        }
      }
      const postal_code = requireField(
        "postal_code",
        "irányítószám",
        p.postal_code,
        4,
        4,
        _HU_ZIP_RE,
        "Az irányítószám pontosan 4 számjegy legyen."
      );
      const city = requireField("city", "város", p.city, 2, 128, _CITY_RE, "A város formátuma érvénytelen.");
      const street = requireField("street", "utca", p.street, 2, 256, _STREET_RE, "Az utca formátuma érvénytelen.");
      const house_number = requireField(
        "house_number",
        "házszám",
        p.house_number,
        1,
        32,
        _HOUSE_RE,
        "A házszám formátuma érvénytelen."
      );
      let line2 = p.line2 != null ? String(p.line2).trim() : "";
      if (line2) {
        if (line2.length > 256) pushError("line2", "Az emelet/ajtó legfeljebb 256 karakter lehet.");
        else if (containsUnsafeMarkup(line2) || !_LINE2_RE.test(line2)) {
          pushError("line2", "Az emelet/ajtó formátuma érvénytelen.");
        }
      } else {
        line2 = "";
      }
      const country = requireField(
        "country",
        "ország",
        p.country || "Magyarország",
        2,
        128,
        _COUNTRY_RE,
        "Az ország formátuma érvénytelen."
      );

      if (postal_code && city && !errors.length) {
        const w = zipCityMismatchWarningHu(postal_code, city);
        if (w) warnings.push({ field: "city", message: w });
      }

      return {
        ok: errors.length === 0,
        errors: errors,
        warnings: warnings,
        normalized: {
          recipient_name: recipient_name,
          phone: phoneRaw,
          postal_code: postal_code,
          city: city,
          street: street,
          house_number: house_number,
          line2: line2,
          country: country || "Magyarország",
        },
      };
    }

    function validatePersonNameField(value, label, field) {
      const s = value != null ? String(value).trim() : "";
      if (!s) return label + " megadása kötelező.";
      if (s.length < 2 || s.length > 128) return label + " 2–128 karakter legyen.";
      if (containsUnsafeMarkup(s) || !_NAME_RE.test(s)) {
        return label + " formátuma érvénytelen.";
      }
      return null;
    }

    function validateEmailField(value) {
      const s = value != null ? String(value).trim() : "";
      if (!s) return "Az e-mail megadása kötelező.";
      if (s.length > 320) return "Az e-mail túl hosszú.";
      if (containsUnsafeMarkup(s) || !_EMAIL_RE.test(s)) return "Érvénytelen e-mail cím.";
      return null;
    }

    function buildValidatedShippingJson(parts, phoneOverride) {
      const merged = normalizeProfileAddressObject(parts);
      if (phoneOverride != null) merged.phone = String(phoneOverride).trim();
      const v = validateShippingAddressParts(merged, { requireAll: true });
      if (!v.ok) {
        return { ok: false, errors: v.errors, warnings: v.warnings };
      }
      const json = serializeProfileAddressFromParts(v.normalized);
      if (!json) {
        return {
          ok: false,
          errors: [{ field: null, message: "A szállítási cím megadása kötelező." }],
          warnings: [],
        };
      }
      return { ok: true, json: json, warnings: v.warnings, normalized: v.normalized };
    }

    function buildOptionalProfileAddressJson(parts, phoneOverride) {
      const merged = normalizeProfileAddressObject(parts);
      if (phoneOverride != null) merged.phone = String(phoneOverride).trim();
      const any =
        merged.recipient_name ||
        merged.phone ||
        merged.postal_code ||
        merged.city ||
        merged.street ||
        merged.house_number ||
        merged.line2 ||
        (merged.country && merged.country !== "Magyarország");
      if (!any) return { ok: true, json: null, warnings: [] };
      const v = validateShippingAddressParts(merged, { requireAll: true });
      if (!v.ok) return { ok: false, errors: v.errors, warnings: v.warnings };
      return {
        ok: true,
        json: serializeProfileAddressFromParts(v.normalized),
        warnings: v.warnings,
      };
    }

    function formatShippingAddressPlainFromParts(parts) {
      const p = normalizeProfileAddressObject(parts);
      const lines = [
        p.recipient_name,
        p.phone,
        [p.postal_code, p.city].filter(Boolean).join(" "),
        [p.street, p.house_number].filter(Boolean).join(" ").trim(),
      ];
      if (p.line2) lines.push(p.line2);
      if (p.country) lines.push(p.country);
      return lines.filter(Boolean).join("\n");
    }

    function formatShippingAddressPlainFromRaw(raw) {
      const parsed = parseProfileAddressRaw(raw);
      if (parsed.mode === "legacy") return parsed.parts.street || String(raw || "").trim();
      if (parsed.mode === "empty") return "";
      return formatShippingAddressPlainFromParts(parsed.parts);
    }

    function parseProfileAddressRaw(raw) {
      if (raw == null) return { mode: "empty", parts: emptyProfileAddressParts() };
      const s = String(raw).trim();
      if (!s) return { mode: "empty", parts: emptyProfileAddressParts() };
      if (s.startsWith("{")) {
        try {
          const o = JSON.parse(s);
          if (o && typeof o === "object" && (o.v === PROFILE_ADDRESS_JSON_V || o.street != null || o.postal_code != null)) {
            return { mode: "json", parts: normalizeProfileAddressObject(o) };
          }
        } catch (_) {}
      }
      return { mode: "legacy", parts: Object.assign(emptyProfileAddressParts(), { street: s }) };
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

    function validatePhoneOnly(raw) {
      const s = raw != null ? String(raw).trim() : "";
      if (!s) return "A telefonszám megadása kötelező.";
      if (s.length > 32) return "A telefonszám legfeljebb 32 karakter lehet.";
      if (containsUnsafeMarkup(s)) return "A telefonszám nem tartalmazhat HTML-t vagy szkriptet.";
      const digits = normalizeHuPhoneDigits(s);
      if (digits.length < 8 || digits.length > 9 || digits.charAt(0) === "0") {
        return "Érvénytelen magyar telefonszám (pl. 06 30 123 4567).";
      }
      return null;
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
      box.textContent = lines.length ? lines.join("\n") : "Töltsd ki a szállítási mezőket.";
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
      const t = shopUserAccessToken();
      if (!t) {
        if (msg) show(msg, MSG_PURCHASE_AUTH, false);
        return;
      }
      try {
        const me = await api("/auth/me", {
          method: "GET",
          headers: { Authorization: "Bearer " + t },
        });
        const parsed = parseProfileAddressRaw(me && me.shipping_address);
        const p = parsed.parts;
        const hasAny =
          p.recipient_name || p.postal_code || p.city || p.street || p.line2 || p.country;
        if (!hasAny) {
          if (msg) {
            show(
              msg,
              "A profilodban még nincs mentett szállítási cím — add meg a Fiók → Profil menüben, vagy írd be kézzel.",
              false
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
        if (msg) show(msg, (err && err.message) || "Nem sikerült betölteni a profil címét.", false);
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
        return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
      }
      if (parts[0].length >= 2) return parts[0].slice(0, 2).toUpperCase();
      return parts[0].charAt(0).toUpperCase();
    }

    /** Warm Mesencsi palette — deterministic from display name (no gender field in profile). */
    function avatarPlaceholderColors(name) {
      const raw = String(name || "").trim().toLowerCase();
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
      if (/^\s*javascript\s*:/i.test(s) || /^\s*data\s*:/i.test(s) || /^\s*\/\//.test(s)) return false;
      if (/^https?:\/\//i.test(s)) return false;
      return s.startsWith("/media/uploads/avatars/");
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
      return { display: display, url: url, label: label, ok: isProfileImageUrlOk(url) };
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
        "Profilkép előnézet"
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
          const t = shopUserAccessToken();
          if (!t) return;
          applyProfileAvatarPreview(src);
          setAuthLine($("profileMsg"), "", null);
          try {
            b.disabled = true;
            const updated = await api("/users/me", {
              method: "PATCH",
              headers: { Authorization: "Bearer " + t },
              body: JSON.stringify({ profile_image_url: src }),
            });
            saveAuthSession(t, updated);
            showAuthUser(updated);
            setAuthLine($("profileMsg"), "Profilkép kiválasztva és elmentve.", true);
          } catch (err) {
            setAuthLine($("profileMsg"), (err && err.message) || "Mentés sikertelen.", false);
          } finally {
            b.disabled = false;
          }
        });
        wrap.appendChild(b);
      });
    }

    async function populateProfileFormFromServer() {
      const t = shopUserAccessToken();
      if (!t) return;
      setAuthLine($("profileMsg"), "", null);
      initProfileAvatarPresetsOnce();
      let me;
      try {
        me = await api("/auth/me", { method: "GET", headers: { Authorization: "Bearer " + t } });
      } catch (err) {
        setAuthLine($("profileMsg"), (err && err.message) || "Nem sikerült betölteni a profilt.", false);
        return;
      }
      if ($("profNickname")) $("profNickname").value = me.nickname != null ? String(me.nickname) : "";
      if ($("profEmail")) $("profEmail").value = me.email || "";
      if ($("profPhone")) $("profPhone").value = me.phone != null ? String(me.phone) : "";

      const shipParsed = parseProfileAddressRaw(me.shipping_address);
      applyProfileAddressPartsToInputs("profShip", shipParsed.parts);

      const billRaw = me.billing_address != null ? String(me.billing_address).trim() : "";
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
        const t = shopUserAccessToken();
        if (!t) return;
        try {
          const me = await api("/auth/me", { method: "GET", headers: { Authorization: "Bearer " + t } });
          saveAuthSession(t, me);
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
      const map = { profile: "Profile", orders: "Orders", discounts: "Discounts", account: "Account" };
      const wrap = $("userSection" + map[section]);
      if (wrap) wrap.hidden = false;
      const ps = $("pageStack");
      if (ps && section) ps.setAttribute("data-active-user-section", section);
      syncUserNavActiveClasses();
      try {
        if (typeof window.mesencsiCloseMobileNav === "function") window.mesencsiCloseMobileNav();
      } catch (_) {}
      await loadUserSectionContent(section);
    }

    /** @type {{ id: number, name: string, price: number, description: string, quantity: number }[]} */
    let cart = [];
    /** Selected coupon for checkout (validated server-side via POST /orders/estimate). */
    let checkoutCouponCode = null;
    let checkoutEstimateSig = "";
    const CHECKOUT_COUPON_STORAGE_KEY = "mesencsi_selected_coupon";
    /** @type {{ id: number, code: string, percent_discount: number, expires_at: string | null }[]} */
    let userDiscountCouponsCache = [];
    let userDiscountPickerBound = false;
    /** @type {null | { discount_percent: number | null, coupon_code: string | null, bundle_rule_name: string | null, bundle_discount_total: number, bundle_percent: number | null, grand_original: number, grand_discount: number, grand_final: number }} */
    let lastOrderEstimate = null;
    let cartEstimateTimer = null;
    /** Kiállított hero-hír `id` — hozzászólások zónája ehhez a közzétett hírhez kötődik. */
    const newsCommentsSubmitting = new Set();
    /** Barion return boot: globális banner + opcionális loginMsg vendégnek. */
    /** @type {null | { kind: "success" | "pending" | "error", short: string, detail: string }} */
    let barionReturnNotice = null;

    const CART_STORAGE_KEY = "mesencsi_cart_v1";
    let cartServerSyncTimer = null;
    /** POST /orders Bearer: login válasz ``access_token`` — fejlesztői / későbbi UI-hoz. */
    const SHOP_USER_ACCESS_TOKEN_KEY = "mesencsi_user_access_token";
    /** Gyors UI frissítés; a forrás igazság a GET /auth/me. */
    const SHOP_USER_PROFILE_KEY = "mesencsi_user_profile_json";

    function shopUserProfile() {
      try {
        const raw = localStorage.getItem(SHOP_USER_PROFILE_KEY);
        if (!raw) return null;
        return JSON.parse(raw);
      } catch (_) {
        return null;
      }
    }

    function shopUserAccessToken() {
      try {
        return (localStorage.getItem(SHOP_USER_ACCESS_TOKEN_KEY) || "").trim();
      } catch {
        return "";
      }
    }

    function isShopUserLoggedIn() {
      return !!shopUserAccessToken();
    }

    function cartStorageKey() {
      const p = shopUserProfile();
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
        if (!Number.isFinite(id) || !Number.isFinite(price) || !Number.isFinite(q) || q < 1) continue;
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

    const MSG_WEBSHOP_AUTH = "A webshop használatához kérlek jelentkezz be.";
    const MSG_PURCHASE_AUTH = "A vásárláshoz kérlek jelentkezz be.";
    const MSG_STORYBOOKS_AUTH = "A mesekönyvek megtekintéséhez kérlek jelentkezz be.";
    const MSG_EMPTY_PUBLIC = "Jelenleg nincs megjeleníthető tartalom.";

    /** Lebegő kosár FAB: rejtve a kosár/checkout nézetben (checkout a view-cart alatt van). */
    function syncCartFabVisibility() {
      const fab = $("cartFab");
      if (!fab) return;
      const stack = $("pageStack");
      const cur = stack && stack.getAttribute("data-current-view");
      const onCartView = cur === "cart";
      const show = isShopUserLoggedIn() && !onCartView;
      fab.hidden = !show;
      fab.setAttribute("aria-hidden", show ? "false" : "true");
    }

    /**
     * Webshop / kosár / Mesekönyvek menü csak bejelentkezett vásárlónak:
     * - fa menü (desktop + mobil hamburger): Webshop + Kosár + Mesekönyvek rejtése kijelentkezve
     * - nézeten belüli CTA-k (.glass-card): „Megnyitom a webshopot” / kosár link szintén
     * - lebegő kosár FAB
     * Kosár ürítése kijelentkezve.
     */
    function applyPurchaseGates() {
      const ok = isShopUserLoggedIn();
      const nav = document.querySelector("nav.side-menu.wood-menu.side-rail-nav");
      if (nav) {
        nav.querySelectorAll(
          'button[data-view="webshop"], button[data-view="cart"], button[data-view="storybooks"]'
        ).forEach(function (btn) {
          btn.hidden = !ok;
          btn.setAttribute("aria-hidden", ok ? "false" : "true");
        });
        /* Belépett usernél a "Termékek" (stories) gomb felesleges — a Webshop lefedi.
           Kijelentkezve viszont láthatónak kell maradnia. */
        const storiesBtn = nav.querySelector('button[data-view="stories"]');
        if (storiesBtn) {
          storiesBtn.hidden = ok;
          storiesBtn.setAttribute("aria-hidden", ok ? "true" : "false");
        }
      }
      document.querySelectorAll('.glass-card button[data-view="webshop"], .glass-card button[data-view="cart"]').forEach(function (el) {
        el.hidden = !ok;
        el.setAttribute("aria-hidden", ok ? "false" : "true");
      });
      if (ok) {
        void hydrateCartForLoggedInUser();
        const hint = $("webshopCartHint");
        if (hint) hint.hidden = true;
        syncCartFabVisibility();
        return;
      }
      cart = [];
      updateCartUI();
      const stack = $("pageStack");
      const cur = stack && stack.getAttribute("data-current-view");
      if (cur === "webshop" || cur === "cart" || cur === "storybooks") {
        showView("home");
      }
      syncCartFabVisibility();
    }

    function apiBase() {
      if (window.__MESENCsi_API_ORIGIN) return window.__MESENCsi_API_ORIGIN;
      const raw = ($("apiBase").value || "").replace(/\/$/, "").trim();
      if (raw) return raw;
      const loc = window.location;
      if (loc.port === "5500") return `${loc.protocol}//127.0.0.1:8000`;
      return loc.origin;
    }

    function apiBaseFallbacks() {
      const base = apiBase();
      const fallbacks = [base];
      if (base !== "http://127.0.0.1:8000") fallbacks.push("http://127.0.0.1:8000");
      if (base !== "http://localhost:8000") fallbacks.push("http://localhost:8000");
      return fallbacks;
    }

    function loadCartFromStorage() {
      try {
        if (!isShopUserLoggedIn()) {
          cart = [];
          return;
        }
        const raw = localStorage.getItem(cartStorageKey());
        if (!raw) return;
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return;
        const next = [];
        for (const row of parsed) {
          if (!row || row.id == null) continue;
          const id = Number(row.id);
          const price = Number(row.price);
          let q = Math.floor(Number(row.quantity));
          if (!Number.isFinite(id) || !Number.isFinite(price) || !Number.isFinite(q) || q < 1) continue;
          next.push({
            id,
            name: String(row.name || ""),
            price,
            description: typeof row.description === "string" ? row.description : "",
            quantity: q,
          });
        }
        cart = next;
      } catch {
        cart = [];
      }
    }

    async function flushCartToServer() {
      const token = shopUserAccessToken();
      if (!token) return;
      try {
        await api("/cart", {
          method: "PUT",
          headers: { Authorization: "Bearer " + token },
          body: JSON.stringify({
            items: cart.map(function (c) {
              return { product_id: c.id, quantity: c.quantity };
            }),
          }),
        });
      } catch (_) {}
    }

    function scheduleCartServerSync() {
      if (!isShopUserLoggedIn()) return;
      if (cartServerSyncTimer) clearTimeout(cartServerSyncTimer);
      cartServerSyncTimer = setTimeout(function () {
        cartServerSyncTimer = null;
        void flushCartToServer();
      }, 450);
    }

    function persistCart() {
      if (!isShopUserLoggedIn()) return;
      try {
        localStorage.setItem(cartStorageKey(), JSON.stringify(cart));
        scheduleCartServerSync();
      } catch (_) {}
    }

    async function hydrateCartForLoggedInUser() {
      const token = shopUserAccessToken();
      if (!token) {
        loadCartFromStorage();
        updateCartUI();
        return;
      }
      try {
        const data = await api("/cart", { method: "GET", headers: { Authorization: "Bearer " + token } });
        const fromServer = cartRowsFromPayload(data);
        if (fromServer.length) {
          cart = fromServer;
        } else {
          loadCartFromStorage();
          if (cart.length) await flushCartToServer();
        }
      } catch (_) {
        loadCartFromStorage();
      }
      updateCartUI();
      if (cart.length) scheduleCartPricingEstimate();
    }

    async function api(path, opts = {}) {
      const bases = apiBaseFallbacks();
      let res = null;
      let lastErr = null;
      let url = "";
      for (let i = 0; i < bases.length; i++) {
        url = bases[i] + path;
        try {
          res = await fetch(url, {
            ...opts,
            headers: {
              Accept: "application/json",
              "Content-Type": "application/json",
              ...(opts.headers || {}),
            },
          });
          break;
        } catch (e) {
          lastErr = e;
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
      if (!res.ok) {
        const hu = humanizeServerError(res.status, data, text);
        throw new Error(hu);
      }
      return data;
    }

    async function apiMultipart(path, formData, bearerToken) {
      const bases = apiBaseFallbacks();
      let res = null;
      let lastErr = null;
      let url = "";
      const headers = { Accept: "application/json" };
      if (bearerToken) headers.Authorization = "Bearer " + bearerToken;
      for (let i = 0; i < bases.length; i++) {
        url = bases[i] + path;
        try {
          res = await fetch(url, { method: "POST", headers: headers, body: formData });
          break;
        } catch (e) {
          lastErr = e;
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
      if (!res.ok) {
        const hu = humanizeServerError(res.status, data, text);
        throw new Error(hu);
      }
      return data;
    }

    /* ----- Vásárlói auth UI (MVP): POST /auth/register, /auth/login, GET /auth/me, PATCH /users/me, DELETE /users/me ----- */
    function saveAuthSession(token, profile) {
      try {
        localStorage.setItem(SHOP_USER_ACCESS_TOKEN_KEY, token);
        if (profile) localStorage.setItem(SHOP_USER_PROFILE_KEY, JSON.stringify(profile));
      } catch (_) {}
    }

    function clearAuthSession() {
      try {
        localStorage.removeItem(SHOP_USER_ACCESS_TOKEN_KEY);
        localStorage.removeItem(SHOP_USER_PROFILE_KEY);
      } catch (_) {}
    }

    function setAuthLine(el, text, ok) {
      if (!el) return;
      el.textContent = text || "";
      el.className = "auth-msg" + (ok === true ? " ok" : ok === false ? " err" : "");
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
      return kind === "success" || kind === "pending" || kind === "error" ? kind : "error";
    }

    function hidePaymentReturnBanner() {
      const el = $("paymentReturnBanner");
      if (!el) return;
      el.hidden = true;
      el.classList.remove(
        "payment-return-banner--success",
        "payment-return-banner--pending",
        "payment-return-banner--error"
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
        "payment-return-banner--error"
      );
      el.classList.add("payment-return-banner--" + k);
      textEl.textContent = t;
      if (actionBtn) {
        const showOrders = isShopUserLoggedIn();
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
      barionReturnNotice = { kind: k, short: paymentReturnBannerShort(k), detail: d };
    }

    function applyBarionReturnNotice() {
      if (!barionReturnNotice) return;
      renderPaymentReturnBanner(barionReturnNotice.short, barionReturnNotice.kind);
      const lo = $("authLoggedOut");
      if (lo && !lo.hidden) {
        setAuthLine($("loginMsg"), barionReturnNotice.detail, barionReturnNotice.kind === "success");
      }
    }

    function clearBarionReturnNotice() {
      barionReturnNotice = null;
      hidePaymentReturnBanner();
    }

    function openOrdersFromPaymentBanner() {
      hidePaymentReturnBanner();
      if (!isShopUserLoggedIn()) {
        setAuthLine($("loginMsg"), "A rendeléseid megtekintéséhez jelentkezz be.", false);
        try {
          if (typeof window.mesencsiCloseMobileNav === "function") window.mesencsiCloseMobileNav();
        } catch (_) {}
        return;
      }
      void setActiveUserSection("orders");
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
        "A rendelés létrejött, de a fizetés még nem sikeres. A rendeléseid között ellenőrizheted az állapotot (Fiók → Rendeléseim). Új kosarat is indíthatsz, ha újra szeretnéd próbálni."
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
      history.replaceState(null, "", window.location.pathname + (qs ? "?" + qs : "") + window.location.hash);
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

    function hideAuthBoot() {
      const boot = $("authBoot");
      if (boot) boot.hidden = true;
    }

    function showAuthBoot() {
      closeUserAccountPanelsOnly();
      const boot = $("authBoot");
      const lo = $("authLoggedOut");
      const reg = $("authRegister");
      const li = $("authLoggedIn");
      if (boot) boot.hidden = false;
      if (lo) lo.hidden = true;
      if (reg) reg.hidden = true;
      if (li) li.hidden = true;
    }

    function showAuthGuest() {
      closeUserAccountPanelsOnly();
      hideAuthBoot();
      clearCheckoutCouponState();
      const lo = $("authLoggedOut");
      const reg = $("authRegister");
      const li = $("authLoggedIn");
      if (lo) lo.hidden = false;
      if (reg) reg.hidden = true;
      if (li) li.hidden = true;
      resetUserOrdersPanel();
      applyPurchaseGates();
      void refreshAllNewsCommentsOnHome();
      if (typeof window.mesencsiResetOverlays === "function") window.mesencsiResetOverlays();
    }

    function showAuthRegister() {
      hideAuthBoot();
      const lo = $("authLoggedOut");
      const reg = $("authRegister");
      const li = $("authLoggedIn");
      if (lo) lo.hidden = true;
      if (reg) reg.hidden = false;
      if (li) li.hidden = true;
      clearBarionReturnNotice();
      setAuthLine($("loginMsg"), "", null);
      setAuthLine($("registerMsg"), "", null);
    }

    function applyUserPanelAvatar(me) {
      syncAvatarElements(
        $("userPanelAvatar"),
        $("userPanelAvatarPh"),
        me && me.profile_image_url,
        me,
        avatarDisplayNameFromUser(me) || "Profilkép"
      );
    }

    function resetUserOrdersPanel() {
      const list = $("userOrdersList");
      const st = $("userOrdersStatus");
      if (list) list.innerHTML = "";
      if (st) st.textContent = "";
      const dlist = $("userDiscountsList");
      const dst = $("userDiscountsStatus");
      if (dlist) dlist.innerHTML = "";
      if (dst) dst.textContent = "";
      userDiscountCouponsCache = [];
    }

    function shopOrderStatusHu(s) {
      const m = {
        new: "Új",
        processing: "Feldolgozás alatt",
        completed: "Teljesítve",
        cancelled: "Lemondva",
      };
      return m[s] || s || "—";
    }

    function shopPaymentStatusHu(s) {
      const m = {
        pending: "Fizetés függőben",
        paid: "Fizetve",
        failed: "Fizetés sikertelen",
        cancelled: "Fizetés lemondva",
      };
      return m[s] || s || "—";
    }

    function normalizeShopPaymentStatus(raw) {
      const s = (raw || "pending").trim().toLowerCase();
      return s === "paid" || s === "failed" || s === "cancelled" || s === "pending" ? s : "pending";
    }

    function orderGroupAllowsPaymentRetry(paymentStatus) {
      const ps = normalizeShopPaymentStatus(paymentStatus);
      return ps === "pending" || ps === "failed" || ps === "cancelled";
    }

    function userIsEmailVerified(me) {
      if (!me) return false;
      if (me.is_verified === true) return true;
      return me.email_verified_at != null && String(me.email_verified_at).length > 0;
    }

    function groupShopOrderLines(lines) {
      if (!lines || !lines.length) return [];
      const map = new Map();
      for (let i = 0; i < lines.length; i++) {
        const row = lines[i];
        const ts = row.placed_at || "";
        const key = row.checkout_group_id
          ? String(row.checkout_group_id)
          : ts +
            "\0" +
            String(row.customer_name || "") +
            "\0" +
            String(row.shipping_address || "") +
            "\0" +
            String(row.notes || "");
        if (!map.has(key)) map.set(key, []);
        map.get(key).push(row);
      }
      const groups = Array.from(map.values());
      groups.sort(function (a, b) {
        const ta = new Date(a[0].placed_at).getTime() || 0;
        const tb = new Date(b[0].placed_at).getTime() || 0;
        return tb - ta;
      });
      return groups.map(function (rows) {
        const ids = rows.map(function (r) {
          return r.id;
        });
        return {
          rows: rows,
          orderIds: ids,
          minId: Math.min.apply(null, ids),
          placed_at: rows[0].placed_at,
          status: rows[0].status,
          payment_status: normalizeShopPaymentStatus(rows[0].payment_status),
          checkout_group_id: rows[0].checkout_group_id || null,
          barion_payment_id: rows[0].barion_payment_id || null,
          total: rows.reduce(function (sum, r) {
            return sum + (Number(r.total_price) || 0);
          }, 0),
        };
      });
    }

    let orderPaymentRetryBusy = false;

    function initUserOrdersPaymentRetryListener() {
      const list = $("userOrdersList");
      if (!list || list.dataset.paymentRetryListener === "1") return;
      list.dataset.paymentRetryListener = "1";
      list.addEventListener("click", function (ev) {
        const btn = ev.target && ev.target.closest ? ev.target.closest("[data-order-payment-retry]") : null;
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
        void retryBarionPaymentForOrderGroup(orderIds, Number.isFinite(minId) ? minId : orderIds[0], label, btn);
      });
    }

    function renderUserOrders(groups) {
      const list = $("userOrdersList");
      const st = $("userOrdersStatus");
      if (!list || !st) return;
      list.innerHTML = "";
      if (!groups.length) {
        st.textContent = "Még nincs rendelésed.";
        return;
      }
      st.textContent = groups.length === 1 ? "1 rendelés." : groups.length + " rendelés.";
      for (let i = 0; i < groups.length; i++) {
        const g = groups[i];
        const card = document.createElement("div");
        card.className = "user-order-card";
        const d = g.placed_at ? new Date(g.placed_at) : null;
        const dateStr =
          d && !isNaN(d.getTime())
            ? d.toLocaleString("hu-HU", { dateStyle: "short", timeStyle: "short" })
            : "—";
        const head = document.createElement("div");
        head.className = "user-order-card__head";
        head.textContent =
          "#" +
          g.minId +
          " · " +
          shopOrderStatusHu(g.status) +
          " · " +
          shopPaymentStatusHu(g.payment_status);
        const meta = document.createElement("div");
        meta.className = "user-order-card__meta";
        meta.textContent =
          dateStr + " · összesen " + (g.total || 0).toLocaleString("hu-HU") + " Ft";
        const linesEl = document.createElement("div");
        linesEl.className = "user-order-card__lines";
        linesEl.textContent = g.rows
          .map(function (r) {
            return (r.product_name || "Tétel") + " ×" + (r.quantity || 0);
          })
          .join(", ");
        card.appendChild(head);
        card.appendChild(meta);
        card.appendChild(linesEl);
        if (orderGroupAllowsPaymentRetry(g.payment_status)) {
          const actions = document.createElement("div");
          actions.className = "user-order-card__actions";
          const retryBtn = document.createElement("button");
          retryBtn.type = "button";
          retryBtn.className = "btn-outline-ghost user-order-card__retry-btn";
          retryBtn.setAttribute("data-order-payment-retry", "1");
          retryBtn.setAttribute("data-order-ids", g.orderIds.join(","));
          retryBtn.setAttribute("data-order-min-id", String(g.minId));
          const retryLabel = g.rows
            .map(function (r) {
              return (r.product_name || "termék") + " ×" + (r.quantity || 0);
            })
            .join(", ");
          retryBtn.setAttribute("data-order-retry-label", retryLabel);
          retryBtn.textContent = "Fizetés újrapróbálása";
          actions.appendChild(retryBtn);
          card.appendChild(actions);
        }
        list.appendChild(card);
      }
      initUserOrdersPaymentRetryListener();
    }

    async function loadUserOrdersIntoPanel() {
      const t = shopUserAccessToken();
      const st = $("userOrdersStatus");
      const list = $("userOrdersList");
      if (!t || !st || !list) return;
      st.textContent = "Betöltés…";
      list.innerHTML = "";
      try {
        const lines = await api("/orders", {
          method: "GET",
          headers: { Authorization: "Bearer " + t },
        });
        const arr = Array.isArray(lines) ? lines : [];
        renderUserOrders(groupShopOrderLines(arr));
      } catch (e) {
        const msg = (e && e.message) || "Nem sikerült betölteni a rendeléseket.";
        if (/megerősít|verified|403/i.test(msg)) {
          st.textContent =
            "A rendelések megtekintéséhez erősítsd meg az e-mail címed („Fiók adatok” → „Új megerősítő e-mail”).";
        } else {
          st.textContent = msg;
        }
      }
    }

    async function loadUserDiscountsIntoPanel() {
      const t = shopUserAccessToken();
      const st = $("userDiscountsStatus");
      const list = $("userDiscountsList");
      if (!t || !st || !list) return;
      bindUserDiscountPicker();
      st.textContent = "Betöltés…";
      list.innerHTML = "";
      try {
        const rows = await api("/users/me/coupons", {
          method: "GET",
          headers: { Authorization: "Bearer " + t },
        });
        const arr = Array.isArray(rows) ? rows : [];
        userDiscountCouponsCache = arr;
        const selected = getStoredCheckoutCoupon();
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
          if (selected) clearCheckoutCouponState();
          return;
        }
        st.textContent =
          arr.length === 1
            ? "1 aktív kedvezményed van — válaszd ki, és a kosárban automatikusan érvényesül."
            : arr.length + " aktív kedvezményed van — egyszerre csak egyet válassz.";
        html += arr
          .map(function (c) {
            const code = String(c.code || "").trim();
            const pct = Number(c.percent_discount) || 0;
            const exp = formatCouponExpiry(c.expires_at);
            const checked =
              selected && code.toUpperCase() === selected.toUpperCase() ? " checked" : "";
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
          if (!stillValid) clearCheckoutCouponState();
          else syncUserDiscountRadios(selected);
        }
        updateCheckoutCouponDisplay();
      } catch (e) {
        userDiscountCouponsCache = [];
        const msg = (e && e.message) || "Nem sikerült betölteni a kuponokat.";
        if (/megerősít|verified|403/i.test(msg)) {
          st.textContent =
            "A személyes kuponok a megerősített e-mail után érhetők el. Kérhetsz új megerősítő levelet a „Fiók adatok” menüpontban.";
        } else {
          st.textContent = msg;
        }
      }
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

      const sb = me && me.short_bio && String(me.short_bio).trim();
      if (shortBio) {
        if (sb) {
          shortBio.textContent = sb;
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
      applyUserPanelAvatar(me);
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

    function showAuthUser(me) {
      closeUserAccountPanelsOnly();
      hideAuthBoot();
      const lo = $("authLoggedOut");
      const reg = $("authRegister");
      const li = $("authLoggedIn");
      if (lo) lo.hidden = true;
      if (reg) reg.hidden = true;
      if (li) li.hidden = false;
      resetUserOrdersPanel();
      fillUserPanel(me);
      setAuthLine($("loginMsg"), "", null);
      setAuthLine($("registerMsg"), "", null);
      setAuthLine($("profileMsg"), "", null);
      applyBarionReturnNotice();
      applyPurchaseGates();
      const ps = $("pageStack");
      if (ps && ps.getAttribute("data-current-view") === "stories") {
        ensureProductsCatalog();
      }
      void refreshAllNewsCommentsOnHome();
      if (typeof window.mesencsiResetOverlays === "function") window.mesencsiResetOverlays();
      void restoreStoredCheckoutCoupon();
    }

    async function refreshShopUser() {
      const t = shopUserAccessToken();
      if (!t) {
        showAuthGuest();
        return;
      }
      try {
        const me = await api("/auth/me", { method: "GET", headers: { Authorization: "Bearer " + t } });
        saveAuthSession(t, me);
        showAuthUser(me);
        syncCheckoutEmailFromSession();
      } catch (_) {
        clearAuthSession();
        showAuthGuest();
      }
    }

    window.mesencsiAuthBootEscape = function () {
      const boot = $("authBoot");
      if (!boot || boot.hidden) return;
      hideAuthBoot();
      if (shopUserAccessToken()) {
        void refreshShopUser();
      } else {
        showAuthGuest();
      }
    };

    async function syncCheckoutEmailFromSession() {
      const t = shopUserAccessToken();
      const el = $("checkoutEmail");
      const nm = $("checkoutName");
      if (!t) return;
      try {
        const me = await api("/auth/me", {
          method: "GET",
          headers: { Authorization: "Bearer " + t },
        });
        if (me && me.email && el) el.value = me.email;
        if (nm && me) {
          const pre =
            (me.nickname != null && String(me.nickname).trim()) ||
            (me.username && String(me.username).trim()) ||
            "";
          if (pre && !nm.value.trim()) nm.value = pre;
        }
        const cp = $("checkoutPhone");
        if (cp && me && me.phone && !cp.value.trim()) cp.value = String(me.phone).trim();
        wireCheckoutAddressConfirmPreview();
        updateCheckoutAddressConfirmPreview();
      } catch (_) {
        /* lejárt / hibás token */
      }
    }

    function show(el, msg, ok) {
      el.style.display = "block";
      el.className = "status " + (ok ? "ok" : "err");
      el.textContent = msg;
    }

    function hide(el) {
      el.style.display = "none";
      el.textContent = "";
    }

    function friendlyBackendError() {
      return "Most nem érjük el a boltot. Nézd meg az internetet, vagy próbáld újra egy kicsit később.";
    }

    /** Szerverválaszból érthető magyar szöveg (nem szakzsargon). */
    function humanizeServerError(status, data, rawText) {
      const t = (rawText || "").toLowerCase();
      const detailStr =
        data && typeof data.detail === "string"
          ? data.detail
          : data && data.detail != null && !Array.isArray(data.detail)
            ? String(data.detail)
            : "";
      const detailIsList = Array.isArray(data && data.detail);

      if (status >= 500) {
        return "A bolt éppen nem tud válaszolni. Próbáld újra néhány perc múlva.";
      }

      if (detailStr && detailStr.length > 0 && detailStr.length < 400 && !detailIsList) {
        return detailStr;
      }

      if (status === 404) {
        if (/termék|product/i.test(detailStr + t)) return "Nincs ilyen termék, vagy már nem kapható.";
        if (/rendelés|order/i.test(detailStr + t)) return "Nincs ilyen rendelés.";
        if (/galéria|gallery/i.test(detailStr + t)) return "Nincs ilyen galériakép.";
        return "Nem találjuk, amit kértél — lehet, hogy már nem elérhető.";
      }
      if (status === 401 || status === 403) {
        if (detailStr && detailStr.length > 0 && detailStr.length < 400) return detailStr;
        return "Be kell jelentkezned, vagy lejárt a belépésed — jelentkezz be újra.";
      }
      if (status === 429) {
        if (detailStr && detailStr.length > 0 && detailStr.length < 400) return detailStr;
        return "Túl gyorsan próbálkozol — várj egy kicsit, és próbáld újra.";
      }
      if (status === 422) {
        if (Array.isArray(data && data.detail)) {
          for (const err of data.detail) {
            const loc = (err.loc || []).join(" ").toLowerCase();
            const msg = String(err.msg || "").toLowerCase();
            if (loc.includes("email") || msg.includes("email")) {
              return "Adj meg egy érvényes e-mail címet (pl. nev@pelda.hu).";
            }
            if (loc.includes("customer_name") || loc.includes("name")) {
              return "Add meg a neved a rendeléshez.";
            }
            if (loc.includes("items") && (msg.includes("least") || msg.includes("min"))) {
              return "Legalább egy termék kell a rendeléshez. Frissítsd az oldalt, és próbáld újra.";
            }
            if (loc.includes("quantity")) {
              return "A darabszámnak legalább 1-nek kell lennie.";
            }
          }
          return "Valamelyik mező hiányzik vagy hibás — nézd át az űrlapot.";
        }
        if (detailStr) {
          if (/page|oldal|galéri/i.test(detailStr)) return "Érvénytelen oldalszám a galériánál. Nyisd meg újra a galériát.";
          return detailStr.length < 220 ? detailStr : "A megadott adatok nem megfelelőek. Ellenőrizd a mezőket.";
        }
        return "A megadott adatok nem megfelelőek. Ellenőrizd a mezőket.";
      }
      if (status === 409) {
        if (detailStr && detailStr.length < 400) return detailStr;
        return "Ez most nem végezhető el — valami ütközik (pl. már van rá hivatkozás).";
      }
      if (status === 400) return "A kérés nem sikerült. Frissítsd az oldalt, és próbáld újra.";
      if (detailStr && detailStr.length < 220) return detailStr;
      return friendlyBackendError();
    }

    function formatPrice(n) {
      try {
        return new Intl.NumberFormat("hu-HU").format(n) + " Ft";
      } catch {
        return String(n) + " Ft";
      }
    }

    function escapeHtml(s) {
      return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function newsCommentCanPost() {
      if (!isShopUserLoggedIn()) return false;
      return userIsEmailVerified(shopUserProfile());
    }

    function isHomeNewsVisible() {
      const stack = $("pageStack");
      if (!stack || stack.getAttribute("data-current-view") !== "home") return false;
      if (stack.getAttribute("data-user-account-open") === "1") return false;
      return true;
    }

    function renderNewsBodyHtml(news) {
      const nf = window.MesencsiNewsFormat;
      const rawBody = String((news && news.body) || "");
      const rawSummary = String((news && news.summary) || "");
      if (nf && typeof nf.renderNewsHtml === "function") {
        return nf.renderNewsHtml(rawBody || rawSummary);
      }
      const paras = rawBody
        .split(/\n\s*\n/)
        .map(function (x) {
          return x.trim();
        })
        .filter(Boolean);
      return paras.length
        ? paras
            .map(function (p) {
              return "<p>" + escapeHtml(p).replace(/\n/g, "<br/>") + "</p>";
            })
            .join("")
        : "<p>" + escapeHtml(rawSummary) + "</p>";
    }

    function renderNewsImageHtml(imageUrl) {
      const raw = imageUrl != null ? String(imageUrl).trim() : "";
      if (!raw) return "";
      const u = /^https?:\/\//i.test(raw) ? raw : raw.startsWith("/") ? raw : "/" + raw;
      return (
        '<div class="hero-news-thumb"><img src="' +
        escapeHtml(u) +
        '" alt="" loading="lazy" decoding="async" /></div>'
      );
    }

    function formatNewsCommentCount(n) {
      const c = Number(n) || 0;
      if (c === 0) return "";
      if (c === 1) return "1 hozzászólás";
      return c + " hozzászólás";
    }

    function createNewsCommentsBlock(news) {
      const tpl = $("newsCommentsBlockTpl");
      if (!tpl || !tpl.content || !news || news.id == null) return null;
      const node = tpl.content.cloneNode(true);
      const block = node.querySelector("[data-news-post-comments]");
      if (!block) return null;
      const newsId = Number(news.id);
      if (!Number.isFinite(newsId)) return null;
      block.setAttribute("data-news-id", String(newsId));
      const title = String(news.title || "Hír").trim() || "Hír";
      const titleEl = block.querySelector("[data-comment-title]");
      if (titleEl) titleEl.textContent = "Hozzászólások — " + title;
      const countEl = block.querySelector("[data-comment-count]");
      const countLabel = formatNewsCommentCount(news.comment_count);
      if (countEl) {
        if (countLabel) {
          countEl.textContent = countLabel;
          countEl.hidden = false;
        } else {
          countEl.textContent = "";
          countEl.hidden = true;
        }
      }
      const label = block.querySelector("[data-comment-label]");
      if (label) label.setAttribute("for", "newsCommentBody-" + newsId);
      const bodyInput = block.querySelector("[data-comment-body]");
      if (bodyInput) bodyInput.id = "newsCommentBody-" + newsId;
      return block;
    }

    function renderNewsCommentsListHtml(items) {
      return items
        .map(function (it) {
          const dateStr = it.created_at
            ? new Date(it.created_at).toLocaleString("hu-HU", { dateStyle: "short", timeStyle: "short" })
            : "";
          const name = escapeHtml(it.author_display_name || "Vásárló");
          const body = escapeHtml(it.content || "");
          let av = '<div class="news-comment-card__avatar--ph" aria-hidden="true">💬</div>';
          if (it.author_avatar_url) {
            let u = String(it.author_avatar_url).trim();
            if (u && !/^https?:\/\//i.test(u) && !u.startsWith("/")) u = "/" + u;
            if (/^https?:\/\//i.test(u) || u.startsWith("/")) {
              av =
                '<img class="news-comment-card__avatar" src="' +
                escapeHtml(u) +
                '" alt="" loading="lazy" decoding="async" />';
            }
          }
          return (
            '<article class="news-comment-card">' +
            av +
            '<div><div class="news-comment-card__meta">' +
            name +
            " · " +
            escapeHtml(dateStr) +
            "</div>" +
            '<div class="news-comment-card__body">' +
            body +
            "</div></div></article>"
          );
        })
        .join("");
    }

    async function refreshNewsCommentsBlock(blockEl) {
      if (!blockEl || !isHomeNewsVisible()) return;
      const newsId = parseInt(blockEl.getAttribute("data-news-id") || "", 10);
      if (!Number.isFinite(newsId)) return;
      blockEl.hidden = false;
      const hint = blockEl.querySelector("[data-login-hint]");
      const publishNote = blockEl.querySelector("[data-publish-note]");
      const form = blockEl.querySelector("[data-news-comment-form]");
      const logged = isShopUserLoggedIn();
      const verified = newsCommentCanPost();
      if (hint) {
        if (!logged) {
          hint.hidden = false;
          hint.textContent = "Kommenteléshez kérlek jelentkezz be.";
        } else if (!verified) {
          hint.hidden = false;
          hint.textContent =
            "Kommenteléshez erősítsd meg az e-mail címed — a Fiók → Fiók adatok menüben kérhetsz új megerősítő linket.";
        } else {
          hint.hidden = true;
          hint.textContent = "";
        }
      }
      if (form) form.hidden = !verified;
      if (publishNote) publishNote.hidden = !verified;
      const list = blockEl.querySelector("[data-comment-list]");
      const empty = blockEl.querySelector("[data-comment-empty]");
      const st = blockEl.querySelector("[data-comment-status]");
      if (st) {
        st.hidden = false;
        st.textContent = "Betöltés…";
      }
      if (list) list.innerHTML = "";
      if (empty) empty.hidden = true;
      try {
        const page = await api("/news/" + newsId + "/comments?page=1&page_size=40");
        if (st) st.hidden = true;
        const items = page && Array.isArray(page.items) ? page.items : [];
        const countEl = blockEl.querySelector("[data-comment-count]");
        const total = page && page.total != null ? Number(page.total) : items.length;
        const countLabel = formatNewsCommentCount(total);
        if (countEl) {
          if (countLabel) {
            countEl.textContent = countLabel;
            countEl.hidden = false;
          } else {
            countEl.hidden = true;
          }
        }
        if (!items.length) {
          if (empty) empty.hidden = false;
          return;
        }
        if (empty) empty.hidden = true;
        if (list) list.innerHTML = renderNewsCommentsListHtml(items);
      } catch (e) {
        if (st) {
          st.hidden = false;
          st.textContent = (e && e.message) || "A hozzászólások nem tölthetők be.";
        }
      }
    }

    async function refreshAllNewsCommentsOnHome() {
      if (!isHomeNewsVisible()) return;
      document.querySelectorAll("[data-news-post-comments]").forEach(function (block) {
        void refreshNewsCommentsBlock(block);
      });
    }

    function mountNewsArticleWithComments(container, news, opts) {
      if (!container || !news) return;
      const title = escapeHtml(String(news.title || ""));
      const bodyHtml = renderNewsBodyHtml(news);
      const img = renderNewsImageHtml(news.image_url);
      const articleClass = opts && opts.featured ? "home-news-article home-news-article--featured" : "home-news-article";
      container.innerHTML =
        '<article class="' +
        articleClass +
        '" data-news-article data-news-id="' +
        escapeHtml(String(news.id)) +
        '">' +
        img +
        '<h3 class="home-news-article__title">' +
        title +
        "</h3>" +
        '<div class="home-news-article__body hero-body">' +
        bodyHtml +
        "</div></article>";
      const article = container.querySelector("[data-news-article]");
      const comments = createNewsCommentsBlock(news);
      if (article && comments) article.appendChild(comments);
    }

    function renderHomeNewsArchiveItem(news) {
      const wrap = document.createElement("article");
      wrap.className = "home-news-card";
      wrap.setAttribute("data-news-id", String(news.id));
      const title = escapeHtml(String(news.title || ""));
      const summary = escapeHtml(String(news.summary || "").trim());
      const img = renderNewsImageHtml(news.image_url);
      wrap.innerHTML =
        img +
        '<h3 class="home-news-card__title">' +
        title +
        "</h3>" +
        (summary ? '<p class="home-news-card__summary">' + summary + "</p>" : "");
      const comments = createNewsCommentsBlock(news);
      if (comments) wrap.appendChild(comments);
      return wrap;
    }

    /**
     * Home: featured hír a hero-ban + további hírek listája, mindegyikhez saját komment blokk.
     */
    async function loadHomeNews() {
      const glass = $("heroGlass");
      const archive = $("homeNewsArchive");
      const archiveList = $("homeNewsArchiveList");
      if (!glass) return;
      const fallbackHook = "Hamarosan új hírekkel érkezünk.";
      try {
        const featured = await api("/news/featured");
        if (!featured) {
          glass.innerHTML =
            '<p class="hero-hook">' +
            escapeHtml(fallbackHook) +
            '</p><div class="hero-body"><p>Egyelőre nincs megjeleníthető hír.</p></div>';
          if (archive) archive.hidden = true;
          if (archiveList) archiveList.innerHTML = "";
          syncHomeNewsChrome("home");
          return;
        }
        mountNewsArticleWithComments(glass, featured, { featured: true });
        const featuredId = Number(featured.id);
        let others = [];
        try {
          const page = await api("/news?page=1&page_size=20");
          others = page && Array.isArray(page.items) ? page.items : [];
        } catch (_) {
          others = [];
        }
        if (archive && archiveList) {
          archiveList.innerHTML = "";
          const more = others.filter(function (n) {
            return Number(n.id) !== featuredId;
          });
          if (more.length) {
            more.forEach(function (n) {
              archiveList.appendChild(renderHomeNewsArchiveItem(n));
            });
            archive.hidden = !isHomeNewsVisible();
          } else {
            archive.hidden = true;
          }
        }
        syncHomeNewsChrome("home");
        void refreshAllNewsCommentsOnHome();
      } catch (_) {
        glass.innerHTML =
          '<p class="hero-hook">' +
          escapeHtml(fallbackHook) +
          '</p><div class="hero-body"><p>A hírek betöltése nem sikerült.</p></div>';
        if (archive) archive.hidden = true;
      }
    }

    function updateCartFabBadge() {
      const badge = $("cartFabBadge");
      const fab = $("cartFab");
      if (!fab) return;
      const n = cart.reduce((sum, item) => sum + item.quantity, 0);
      if (badge) {
        if (n > 0) {
          badge.hidden = false;
          badge.textContent = n > 99 ? "99+" : String(n);
        } else {
          badge.hidden = true;
          badge.textContent = "";
        }
      }
      fab.setAttribute("aria-label", n > 0 ? "Kosár megnyitása, " + n + " db tétel összesen" : "Kosár megnyitása");
    }

    function addToCart(product) {
      if (!isShopUserLoggedIn()) {
        setAuthLine($("loginMsg"), MSG_PURCHASE_AUTH, false);
        return;
      }
      const existing = cart.find((item) => item.id === product.id);
      if (existing) {
        existing.quantity += 1;
      } else {
        cart.push({
          id: product.id,
          name: product.name,
          price: product.price,
          description: product.description,
          quantity: 1,
        });
      }
      updateCartUI();
      if (isShopUserLoggedIn() && cart.length) scheduleCartPricingEstimate();
      const hint = $("webshopCartHint");
      if (hint) hint.hidden = false;
    }

    function cartSignature() {
      return cart
        .map(function (c) {
          return String(c.id) + ":" + String(Math.floor(Number(c.quantity)) || 0);
        })
        .join("|");
    }

    function getStoredCheckoutCoupon() {
      try {
        const v = localStorage.getItem(CHECKOUT_COUPON_STORAGE_KEY);
        return v && String(v).trim() ? String(v).trim() : "";
      } catch (_) {
        return "";
      }
    }

    function setStoredCheckoutCoupon(code) {
      try {
        const c = code && String(code).trim() ? String(code).trim() : "";
        if (c) localStorage.setItem(CHECKOUT_COUPON_STORAGE_KEY, c);
        else localStorage.removeItem(CHECKOUT_COUPON_STORAGE_KEY);
      } catch (_) {}
    }

    function formatCouponExpiry(expiresAt) {
      if (expiresAt == null) return "Nincs lejárat";
      try {
        return new Date(expiresAt).toLocaleString("hu-HU", { dateStyle: "short", timeStyle: "short" });
      } catch (_) {
        return "—";
      }
    }

    function syncUserDiscountRadios(selectedCode) {
      const list = $("userDiscountsList");
      if (!list) return;
      const val = selectedCode != null ? String(selectedCode) : getStoredCheckoutCoupon() || "";
      const norm = val.toUpperCase();
      list.querySelectorAll('input[name="userDiscountPick"]').forEach(function (inp) {
        const iv = inp.value || "";
        inp.checked = norm ? iv.toUpperCase() === norm : iv === "";
      });
    }

    function updateCheckoutCouponDisplay() {
      const active = $("checkoutCouponActive");
      const hint = $("checkoutCouponHint");
      const clr = $("btnCouponClear");
      const code = checkoutCouponCode || getStoredCheckoutCoupon() || "";
      if (active) {
        if (code) {
          active.hidden = false;
          let label = "Aktív kedvezmény: " + code;
          if (lastOrderEstimate && lastOrderEstimate.coupon_code && lastOrderEstimate.discount_percent != null) {
            label += " (−" + String(lastOrderEstimate.discount_percent) + "%)";
          } else {
            const row = userDiscountCouponsCache.find(function (c) {
              return String(c.code || "").toUpperCase() === String(code).toUpperCase();
            });
            if (row && row.percent_discount != null) {
              label += " (−" + String(row.percent_discount) + "%)";
            }
          }
          if (lastOrderEstimate && lastOrderEstimate.bundle_rule_name && !lastOrderEstimate.coupon_code) {
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
      checkoutCouponCode = null;
      checkoutEstimateSig = "";
      lastOrderEstimate = null;
      setStoredCheckoutCoupon("");
      syncUserDiscountRadios("");
      updateCheckoutCouponDisplay();
      const sum = $("couponSummaryLine");
      if (sum) {
        sum.hidden = true;
        sum.textContent = "";
      }
    }

    async function applyCouponViaEstimate(rawCode, opts) {
      const optsSafe = opts || {};
      const msg = optsSafe.cartMsgEl || $("cartMsg");
      const code = rawCode && String(rawCode).trim();
      if (!code) {
        clearCheckoutCouponState();
        updateCartUI();
        if (cart.length && isShopUserLoggedIn()) scheduleCartPricingEstimate();
        return false;
      }
      if (!isShopUserLoggedIn()) {
        if (msg && !optsSafe.silent) show(msg, MSG_PURCHASE_AUTH, false);
        return false;
      }
      const token = shopUserAccessToken();
      if (!token) {
        if (msg && !optsSafe.silent) show(msg, MSG_PURCHASE_AUTH, false);
        return false;
      }
      if (!cart.length) {
        checkoutCouponCode = code;
        setStoredCheckoutCoupon(code);
        syncUserDiscountRadios(code);
        updateCheckoutCouponDisplay();
        return true;
      }
      try {
        const est = await api("/orders/estimate", {
          method: "POST",
          headers: { Authorization: "Bearer " + token },
          body: JSON.stringify({
            items: cart.map((c) => ({ product_id: c.id, quantity: c.quantity })),
            coupon_code: code,
          }),
        });
        lastOrderEstimate = est;
        checkoutEstimateSig = cartSignature();
        checkoutCouponCode = (est && est.coupon_code) || code;
        setStoredCheckoutCoupon(checkoutCouponCode);
        syncUserDiscountRadios(checkoutCouponCode);
        updateCartUI();
        updateCheckoutCouponDisplay();
        if (msg && !optsSafe.silent) {
          if (est && est.bundle_rule_name && !est.coupon_code) {
            show(
              msg,
              "A kosárra kombó kedvezmény érvényesült — a személyes kupon ebben az esetben nem került felhasználásra.",
              true
            );
          } else {
            show(msg, "Kedvezmény alkalmazva — a fizetendő összeget a szerver számolta.", true);
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
            show(
              msg,
              "A kuponhoz előbb erősítsd meg az e-mail címed („Fiók adatok” → „Új megerősítő e-mail”).",
              false
            );
          } else if (msg) {
            show(msg, em, false);
          }
        }
        return false;
      }
    }

    async function restoreStoredCheckoutCoupon() {
      const stored = getStoredCheckoutCoupon();
      if (!stored || !isShopUserLoggedIn()) {
        updateCheckoutCouponDisplay();
        return;
      }
      if (cart.length) {
        await applyCouponViaEstimate(stored, { silent: true });
      } else {
        checkoutCouponCode = stored;
        syncUserDiscountRadios(stored);
        updateCheckoutCouponDisplay();
      }
    }

    function bindUserDiscountPicker() {
      if (userDiscountPickerBound) return;
      const list = $("userDiscountsList");
      if (!list) return;
      userDiscountPickerBound = true;
      list.addEventListener("change", function (e) {
        const inp = e.target;
        if (!inp || inp.name !== "userDiscountPick") return;
        const val = inp.value || "";
        if (!val) {
          clearCheckoutCouponState();
          updateCartUI();
          if (cart.length) scheduleCartPricingEstimate();
          const cartMsg = $("cartMsg");
          if (cartMsg) hide(cartMsg);
          return;
        }
        void applyCouponViaEstimate(val, { silent: false });
      });
    }

    function formatOrderEstimateSummary(est) {
      if (!est) return "";
      const parts = [];
      parts.push("Részösszeg: " + formatPrice(est.grand_original));
      if (est.bundle_rule_name) {
        parts.push('Kombó: "' + String(est.bundle_rule_name) + '"');
        parts.push(
          "Kedvezmény (−" + String(est.bundle_percent != null ? est.bundle_percent : 0) + "%): −" + formatPrice(est.grand_discount)
        );
      } else if (est.grand_discount > 0 && est.discount_percent != null) {
        parts.push("Kupon (−" + String(est.discount_percent) + "%): −" + formatPrice(est.grand_discount));
      } else if (est.grand_discount > 0) {
        parts.push("Kedvezmény: −" + formatPrice(est.grand_discount));
      }
      parts.push("Fizetendő: " + formatPrice(est.grand_final));
      return parts.join(" · ");
    }

    function scheduleCartPricingEstimate() {
      if (cartEstimateTimer) clearTimeout(cartEstimateTimer);
      cartEstimateTimer = setTimeout(async function () {
        cartEstimateTimer = null;
        if (!isShopUserLoggedIn() || !cart.length) return;
        const token = shopUserAccessToken();
        if (!token) return;
        try {
          const sigBefore = cartSignature();
          const est = await api("/orders/estimate", {
            method: "POST",
            headers: { Authorization: "Bearer " + token },
            body: JSON.stringify({
              items: cart.map((c) => ({ product_id: c.id, quantity: c.quantity })),
              coupon_code: checkoutCouponCode || null,
            }),
          });
          if (sigBefore !== cartSignature()) return;
          lastOrderEstimate = est;
          checkoutEstimateSig = cartSignature();
          checkoutCouponCode = (est && est.coupon_code) || null;
          if (checkoutCouponCode) setStoredCheckoutCoupon(checkoutCouponCode);
          updateCartUI();
          updateCheckoutCouponDisplay();
        } catch (_) {
          /* pl. kupon 403 — a szinkron estimate opcionális; a kosár alapár megmarad */
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
        if (!cart.length) {
          clearCheckoutCouponState();
          emptyEl.hidden = false;
          wrap.hidden = true;
          lines.innerHTML = "";
          totalEl.textContent = formatPrice(0);
          return;
        }

        const sig = cartSignature();
        if (checkoutEstimateSig && sig !== checkoutEstimateSig) {
          lastOrderEstimate = null;
          checkoutEstimateSig = "";
          const keepCoupon = getStoredCheckoutCoupon() || checkoutCouponCode;
          if (keepCoupon) {
            checkoutCouponCode = keepCoupon;
            scheduleCartPricingEstimate();
          }
        }

        emptyEl.hidden = true;
        wrap.hidden = false;

        let grand = 0;
        lines.innerHTML = cart
          .map((item, idx) => {
            const lineTotal = item.price * item.quantity;
            grand += lineTotal;
            return `
        <div class="cart-line">
          <div>
            <div class="cart-line__title">${escapeHtml(item.name)}</div>
            <div class="cart-line__meta">${escapeHtml(formatPrice(item.price))} / db</div>
          </div>
          <input type="number" min="1" step="1" data-cart-qty="${idx}" value="${item.quantity}" aria-label="Darabszám: ${escapeHtml(item.name)}" />
          <div class="cart-line__meta">${escapeHtml(formatPrice(lineTotal))}</div>
          <button type="button" class="btn-cart-remove" data-cart-remove="${idx}">Eltávolítás</button>
        </div>`;
          })
          .join("");

        const sig2 = cartSignature();
        if (lastOrderEstimate && checkoutEstimateSig === sig2) {
          totalEl.textContent = formatPrice(lastOrderEstimate.grand_final);
          if (coupLine) {
            coupLine.hidden = false;
            coupLine.textContent = formatOrderEstimateSummary(lastOrderEstimate);
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

    function safeProductImageUrl(p) {
      if (p && typeof p.image_url === "string") {
        const t = p.image_url.trim();
        if (t && !/^https?:\/\//i.test(t) && t.startsWith("/")) return t;
      }
      return "";
    }

    /**
     * Közös termékkártya: FastAPI `GET /products` — Webshop: shop=true (Kosárba); Termékek nézet: shop=false (csak böngészés).
     */
    function buildProductCardMarkup(p, shop) {
      const imgUrl = safeProductImageUrl(p);
      const thumb = imgUrl
        ? `<div class="product-card__thumb"><img src="${escapeHtml(imgUrl)}" alt="" loading="lazy" decoding="async" /></div>`
        : `<div class="product-card__thumb" aria-hidden="true">📦</div>`;
      const desc = (p.description && String(p.description).trim()) || "";
      const descBlock = desc ? `<p class="desc">${escapeHtml(desc)}</p>` : "";
      const extraClass = shop ? "" : " product-card--catalog";
      const browseNote = isShopUserLoggedIn()
        ? "Megrendeléshez használd a Webshop menüt."
        : MSG_PURCHASE_AUTH;
      const footer = shop
        ? `<button type="button" class="btn-card btn-add-cart" data-id="${escapeHtml(String(p.id))}" data-name="${escapeHtml(p.name)}" data-price="${escapeHtml(String(p.price))}" data-description="${escapeHtml(desc)}">
            Kosárba
          </button>`
        : `<p class="product-card__browse-note">${browseNote}</p>`;
      return `
        <article class="product-card${extraClass}" data-product-id="${escapeHtml(String(p.id))}">
          ${thumb}
          <h3>${escapeHtml(p.name)}</h3>
          <p class="price">${escapeHtml(formatPrice(p.price))}</p>
          ${descBlock}
          ${footer}
        </article>`;
    }

    /**
     * Webshop: FastAPI `GET /products` → [{ id, name, price, description }, ...] (models.Product)
     */
    async function loadProducts() {
      const out = $("productsOut");
      if (!out) return;
      if (!isShopUserLoggedIn()) {
        out.innerHTML = '<p class="empty">' + MSG_WEBSHOP_AUTH + "</p>";
        return;
      }
      out.innerHTML = '<p class="empty">Betöltés…</p>';

      const list = await api("/products");
      if (!Array.isArray(list)) {
        throw new Error("Nem sikerült betölteni a termékeket. Próbáld újra.");
      }
      if (!list.length) {
        out.innerHTML =
          '<p class="empty" role="status">' +
          MSG_EMPTY_PUBLIC +
          " A polcok hamarosan feltöltődnek.</p>";
        return;
      }
      out.innerHTML = list.map((p) => buildProductCardMarkup(p, true)).join("");

      out.querySelectorAll(".btn-add-cart").forEach((btn) => {
        btn.addEventListener("click", () => {
          const price = Number(btn.getAttribute("data-price"));
          const id = parseInt(btn.getAttribute("data-id"), 10);
          if (!Number.isFinite(price) || !Number.isFinite(id)) return;
          addToCart({
            id,
            name: btn.getAttribute("data-name") || "",
            price,
            description: btn.getAttribute("data-description") || "",
          });
        });
      });
    }

    async function ensureCatalog() {
      try {
        await loadProducts();
      } catch (e) {
        const msg = e && e.message ? String(e.message) : friendlyBackendError();
        const el = $("productsOut");
        if (el) el.innerHTML = '<p class="empty" role="alert">' + escapeHtml(msg) + "</p>";
      }
    }

    /** Termékek nézet (view-stories): ugyanaz a `GET /products`, kosár gomb nélkül. */
    async function loadProductsCatalogReadOnly() {
      const out = $("productsCatalogOut");
      if (!out) return;
      out.innerHTML = '<p class="empty">Betöltés…</p>';
      const list = await api("/products");
      if (!Array.isArray(list)) {
        throw new Error("Nem sikerült betölteni a termékeket. Próbáld újra.");
      }
      if (!list.length) {
        out.innerHTML =
          '<p class="empty" role="status">' +
          MSG_EMPTY_PUBLIC +
          " A polcok hamarosan feltöltődnek.</p>";
        return;
      }
      out.innerHTML = list.map((p) => buildProductCardMarkup(p, false)).join("");
    }

    async function ensureProductsCatalog() {
      try {
        await loadProductsCatalogReadOnly();
      } catch (e) {
        const msg = e && e.message ? String(e.message) : friendlyBackendError();
        const el = $("productsCatalogOut");
        if (el) el.innerHTML = '<p class="empty" role="alert">' + escapeHtml(msg) + "</p>";
      }
    }

    function publicMediaUrl(u) {
      if (!u) return "";
      const s = String(u).trim();
      if (/^https?:\/\//i.test(s)) return s;
      return s.startsWith("/") ? s : "/" + s;
    }

    function galleryHasDisplayImage(it) {
      return !!(it && it.image_url && String(it.image_url).trim());
    }

    function buildGalleryPublicCardMarkup(it, indexInPage) {
      const imgUrl = publicMediaUrl(it && it.image_url);
      if (!imgUrl) return "";
      const titleRaw = (it && it.title) || "";
      const title = escapeHtml(titleRaw);
      const descRaw = it && it.description && String(it.description).trim() ? String(it.description).trim() : "";
      const desc = descRaw ? '<p class="gallery-public-card__desc">' + escapeHtml(descRaw) + "</p>" : "";
      const imgBlock =
        '<div class="gallery-public-card__img-wrap"><img class="gallery-public-card__img" src="' +
        escapeHtml(imgUrl) +
        '" alt="" loading="lazy" decoding="async" onerror="var c=this.closest(\'article.gallery-public-card\');if(c)c.remove();" /></div>';
      const idxAttr =
        indexInPage != null && Number.isFinite(Number(indexInPage)) ? ' data-gallery-index="' + Math.floor(Number(indexInPage)) + '"' : "";
      const clickable =
        ' class="gallery-public-card gallery-public-card--clickable" role="button" tabindex="0" data-gallery-img="' +
        escapeHtml(imgUrl) +
        '" data-gallery-title="' +
        escapeHtml(titleRaw) +
        '" data-gallery-desc="' +
        escapeHtml(descRaw) +
        '"' +
        idxAttr;
      return "<article" + clickable + ">" + imgBlock + '<h3 class="gallery-public-card__title">' + title + "</h3>" + desc + "</article>";
    }

    const GALLERY_PAGE_SIZE = 12;
    let galleryPublicPage = 1;
    let galleryLoadSeq = 0;
    /** In-memory gallery page for list view + lightbox edge navigation. */
    let galleryLightboxState = { items: [], index: 0, page: 1, pages: 0, total: 0 };
    let galleryLightboxNavBusy = false;
    let galleryLightboxLastFocus = null;

    function syncGalleryLightboxClosed() {
      const lb = $("galleryLightbox");
      if (!lb) return;
      lb.hidden = true;
      lb.classList.remove("is-open");
      lb.setAttribute("aria-hidden", "true");
    }

    function galleryLightboxGlobalPosition() {
      const st = galleryLightboxState;
      if (!st.total) return 0;
      return (st.page - 1) * GALLERY_PAGE_SIZE + st.index + 1;
    }

    function updateGalleryLightboxNavUi() {
      const st = galleryLightboxState;
      const prev = $("galleryLightboxPrev");
      const next = $("galleryLightboxNext");
      const counter = $("galleryLightboxCounter");
      const canPrev = st.index > 0 || st.page > 1;
      const canNext = st.index < st.items.length - 1 || st.page < st.pages;
      if (prev) {
        prev.disabled = galleryLightboxNavBusy || !canPrev;
        prev.classList.toggle("is-disabled", prev.disabled);
      }
      if (next) {
        next.disabled = galleryLightboxNavBusy || !canNext;
        next.classList.toggle("is-disabled", next.disabled);
      }
      if (counter) {
        const pos = galleryLightboxGlobalPosition();
        counter.textContent = st.total > 0 && pos > 0 ? pos + " / " + st.total : "";
        counter.hidden = !(st.total > 0 && pos > 0);
      }
    }

    function showLightboxItem(it) {
      const lb = $("galleryLightbox");
      const img = $("galleryLightboxImg");
      if (!lb || !img || !it) return;
      const imgUrl = publicMediaUrl(it.image_url);
      if (!imgUrl) return;
      const titleRaw = (it && it.title) || "";
      const descRaw = it && it.description && String(it.description).trim() ? String(it.description).trim() : "";
      img.src = imgUrl;
      img.alt = titleRaw || "Galéria kép";
      const cap = $("galleryLightboxCaption");
      if (cap) {
        const parts = [];
        if (titleRaw) parts.push(titleRaw);
        if (descRaw) parts.push(descRaw);
        cap.textContent = parts.join(" — ");
        cap.hidden = !parts.length;
      }
      lb.hidden = false;
      lb.classList.add("is-open");
      lb.setAttribute("aria-hidden", "false");
      document.body.classList.add("gallery-lightbox-open");
      updateGalleryLightboxNavUi();
    }

    function openGalleryLightboxAtIndex(index, opts) {
      const st = galleryLightboxState;
      const idx = Math.max(0, Math.min(st.items.length - 1, Math.floor(Number(index)) || 0));
      if (!st.items.length || !st.items[idx]) return;
      const fromNav = !!(opts && opts.fromNav);
      if (!fromNav) {
        galleryLightboxLastFocus = document.activeElement;
      }
      st.index = idx;
      showLightboxItem(st.items[idx]);
      if (!fromNav) {
        const closeBtn = $("galleryLightboxClose");
        if (closeBtn) closeBtn.focus();
      }
    }

    function closeGalleryLightbox() {
      const lb = $("galleryLightbox");
      if (!lb) return;
      lb.hidden = true;
      lb.classList.remove("is-open");
      lb.setAttribute("aria-hidden", "true");
      document.body.classList.remove("gallery-lightbox-open");
      const img = $("galleryLightboxImg");
      if (img) {
        img.removeAttribute("src");
        img.alt = "";
      }
      const cap = $("galleryLightboxCaption");
      if (cap) cap.textContent = "";
      if (galleryLightboxLastFocus && typeof galleryLightboxLastFocus.focus === "function") {
        try {
          galleryLightboxLastFocus.focus();
        } catch (_) {}
      }
      galleryLightboxLastFocus = null;
      galleryLightboxNavBusy = false;
    }

    async function fetchGalleryPageData(pageNum) {
      const reqPage =
        pageNum != null && Number.isFinite(Number(pageNum)) && Number(pageNum) >= 1
          ? Math.floor(Number(pageNum))
          : galleryPublicPage;
      const data = await api("/gallery?page=" + reqPage + "&page_size=" + GALLERY_PAGE_SIZE);
      const items = data && Array.isArray(data.items) ? data.items.filter(galleryHasDisplayImage) : [];
      const total = data && data.total != null ? Number(data.total) : 0;
      let pages = data && data.pages != null ? Number(data.pages) : 0;
      if (!pages && total > 0) pages = Math.max(1, Math.ceil(total / GALLERY_PAGE_SIZE));
      const page = data && data.page != null ? Number(data.page) : reqPage;
      return { items: items, page: page, pages: pages, total: total };
    }

    function applyGalleryPageToDom(pageData) {
      const out = $("galleryPublicOut");
      if (!out || !pageData) return;
      const items = pageData.items || [];
      const total = pageData.total || 0;
      const current = pageData.page || 1;
      const pages = pageData.pages || 0;
      if (!items.length && total === 0) {
        out.innerHTML =
          '<p class="empty" role="status">Még nincs megjeleníthető galériakép — hamarosan új illusztrációk érkeznek.</p>';
        return;
      }
      const pagerMeta = { total: total, page: current, pages: pages };
      const cardsHtml = items
        .map(function (it, i) {
          return buildGalleryPublicCardMarkup(it, i);
        })
        .filter(Boolean)
        .join("");
      const listBody = cardsHtml
        ? '<div class="gallery-public-list" role="list">' + cardsHtml + "</div>"
        : '<p class="empty" role="status">Ezen az oldalon nincs megjeleníthető kép (hiányzó fájl). Próbáld a másik oldalt.</p>';
      out.innerHTML = listBody + galleryPaginationMarkup(pagerMeta);
    }

    function syncGalleryLightboxState(pageData) {
      galleryLightboxState.items = pageData.items || [];
      galleryLightboxState.page = pageData.page || 1;
      galleryLightboxState.pages = pageData.pages || 0;
      galleryLightboxState.total = pageData.total || 0;
      galleryPublicPage = galleryLightboxState.page;
    }

    async function galleryLightboxStep(delta) {
      const st = galleryLightboxState;
      const dir = delta > 0 ? 1 : -1;
      if (galleryLightboxNavBusy) return;
      const nextIndex = st.index + dir;
      if (nextIndex >= 0 && nextIndex < st.items.length) {
        openGalleryLightboxAtIndex(nextIndex, { fromNav: true });
        return;
      }
      if (dir > 0 && st.page < st.pages) {
        galleryLightboxNavBusy = true;
        updateGalleryLightboxNavUi();
        try {
          const pageData = await fetchGalleryPageData(st.page + 1);
          if (!pageData.items.length) return;
          syncGalleryLightboxState(pageData);
          applyGalleryPageToDom(pageData);
          openGalleryLightboxAtIndex(0, { fromNav: true });
        } finally {
          galleryLightboxNavBusy = false;
          updateGalleryLightboxNavUi();
        }
        return;
      }
      if (dir < 0 && st.page > 1) {
        galleryLightboxNavBusy = true;
        updateGalleryLightboxNavUi();
        try {
          const pageData = await fetchGalleryPageData(st.page - 1);
          if (!pageData.items.length) return;
          syncGalleryLightboxState(pageData);
          applyGalleryPageToDom(pageData);
          openGalleryLightboxAtIndex(pageData.items.length - 1, { fromNav: true });
        } finally {
          galleryLightboxNavBusy = false;
          updateGalleryLightboxNavUi();
        }
      }
    }

    function bindGalleryLightboxNav() {
      const lb = $("galleryLightbox");
      if (!lb || lb.dataset.galleryNavBound === "1") return;
      lb.dataset.galleryNavBound = "1";
      const prev = $("galleryLightboxPrev");
      const next = $("galleryLightboxNext");
      const figure = lb.querySelector(".gallery-lightbox__figure");
      if (figure) {
        figure.addEventListener("click", function (ev) {
          ev.stopPropagation();
        });
      }
      if (prev) {
        prev.addEventListener("click", function (ev) {
          ev.preventDefault();
          ev.stopPropagation();
          void galleryLightboxStep(-1);
        });
      }
      if (next) {
        next.addEventListener("click", function (ev) {
          ev.preventDefault();
          ev.stopPropagation();
          void galleryLightboxStep(1);
        });
      }
    }

    function bindGalleryLightboxUi() {
      syncGalleryLightboxClosed();
      bindGalleryLightboxNav();
      const out = $("galleryPublicOut");
      if (!out || out.dataset.galleryLbBound === "1") return;
      out.dataset.galleryLbBound = "1";
      out.addEventListener("click", function (ev) {
        const pageBtn = ev.target && ev.target.closest ? ev.target.closest("[data-gallery-page]") : null;
        if (pageBtn && !pageBtn.disabled) {
          const p = parseInt(pageBtn.getAttribute("data-gallery-page"), 10);
          if (Number.isFinite(p) && p >= 1) {
            ev.preventDefault();
            ev.stopPropagation();
            void loadGalleryPublic(p, { fromPager: true });
          }
          return;
        }
        const card = ev.target && ev.target.closest ? ev.target.closest(".gallery-public-card--clickable") : null;
        if (!card) return;
        const idx = parseInt(card.getAttribute("data-gallery-index"), 10);
        openGalleryLightboxAtIndex(Number.isFinite(idx) ? idx : 0);
      });
      out.addEventListener("keydown", function (ev) {
        if (ev.key !== "Enter" && ev.key !== " ") return;
        const card = ev.target && ev.target.closest ? ev.target.closest(".gallery-public-card--clickable") : null;
        if (!card) return;
        ev.preventDefault();
        const idx = parseInt(card.getAttribute("data-gallery-index"), 10);
        openGalleryLightboxAtIndex(Number.isFinite(idx) ? idx : 0);
      });
      const closeBtn = $("galleryLightboxClose");
      const backdrop = $("galleryLightboxBackdrop");
      if (closeBtn) closeBtn.addEventListener("click", closeGalleryLightbox);
      if (backdrop) backdrop.addEventListener("click", closeGalleryLightbox);
      document.addEventListener("keydown", function (ev) {
        const lb = $("galleryLightbox");
        if (!lb || !lb.classList.contains("is-open") || lb.hidden) return;
        if (ev.key === "Escape") {
          closeGalleryLightbox();
          return;
        }
        if (ev.key === "ArrowLeft") {
          ev.preventDefault();
          void galleryLightboxStep(-1);
          return;
        }
        if (ev.key === "ArrowRight") {
          ev.preventDefault();
          void galleryLightboxStep(1);
        }
      });
    }

    function galleryPaginationMarkup(meta) {
      const total = meta && meta.total != null ? Number(meta.total) : 0;
      const page = meta && meta.page != null ? Number(meta.page) : 1;
      let pages = meta && meta.pages != null ? Number(meta.pages) : 0;
      if (!pages && total > 0) {
        pages = Math.max(1, Math.ceil(total / GALLERY_PAGE_SIZE));
      }
      if (!pages || pages <= 1) return "";
      const prevDisabled = page <= 1;
      const nextDisabled = page >= pages;
      return (
        '<nav class="gallery-pagination" aria-label="Galéria lapozás">' +
        '<div class="gallery-pagination__inner">' +
        '<button type="button" class="btn-outline-ghost gallery-pagination__btn" data-gallery-page="' +
        (page - 1) +
        '"' +
        (prevDisabled ? " disabled" : "") +
        ">Előző</button>" +
        '<span class="gallery-pagination__info" role="status">Oldal ' +
        page +
        " / " +
        pages +
        " · " +
        total +
        " kép</span>" +
        '<button type="button" class="btn-outline-ghost gallery-pagination__btn" data-gallery-page="' +
        (page + 1) +
        '"' +
        (nextDisabled ? " disabled" : "") +
        ">Következő</button>" +
        "</div></nav>"
      );
    }

    async function loadGalleryPublic(pageNum, opts) {
      const out = $("galleryPublicOut");
      if (!out) return;
      const fromPager = !!(opts && opts.fromPager);
      const reqPage =
        pageNum != null && Number.isFinite(Number(pageNum)) && Number(pageNum) >= 1
          ? Math.floor(Number(pageNum))
          : galleryPublicPage;
      const loadSeq = ++galleryLoadSeq;
      galleryPublicPage = reqPage;
      if (!fromPager) {
        out.innerHTML = '<p class="empty" role="status">Betöltés…</p>';
      } else {
        out.setAttribute("aria-busy", "true");
        out.querySelectorAll("[data-gallery-page]").forEach(function (btn) {
          btn.disabled = true;
        });
      }
      try {
        const pageData = await fetchGalleryPageData(reqPage);
        if (loadSeq !== galleryLoadSeq) return;
        syncGalleryLightboxState(pageData);
        applyGalleryPageToDom(pageData);
        out.removeAttribute("aria-busy");
      } catch (e) {
        if (loadSeq !== galleryLoadSeq) return;
        const msg = e && e.message ? String(e.message) : friendlyBackendError();
        out.innerHTML = '<p class="empty" role="alert">' + escapeHtml(msg) + "</p>";
        out.removeAttribute("aria-busy");
        throw e;
      }
    }

    async function ensureGallery() {
      bindGalleryLightboxUi();
      try {
        await loadGalleryPublic(galleryPublicPage);
      } catch (_) {
        /* loadGalleryPublic sets error UI */
      }
    }

    let storybooksCatalogLoaded = false;
    let storybookReaderState = { title: "", description: "", cover_url: "", pages: [], idx: 0 };

    function storybookAssetUrl(u) {
      if (!u) return "";
      const s = String(u).trim();
      if (/^https?:\/\//i.test(s)) return "";
      return s.startsWith("/") ? s : "/" + s;
    }

    let storybookReaderTransitioning = false;

    function storybookBuildPublicHeaderHtml(st, i, pages) {
      const showBookHeader = i === 0;
      let coverBlock = "";
      if (showBookHeader && st.cover_url) {
        const u = storybookAssetUrl(st.cover_url);
        coverBlock =
          '<div style="text-align:center;margin-bottom:1rem"><img src="' +
          escapeHtml(u) +
          '" alt="" style="max-width:100%;max-height:200px;border-radius:12px;object-fit:contain" loading="lazy" onerror="this.style.display=\'none\'"/></div>';
      }
      const bookTitle = showBookHeader ? '<h2 class="section__title">' + escapeHtml(st.title || "") + "</h2>" : "";
      const bookDesc = showBookHeader && st.description ? '<p class="section__lead">' + escapeHtml(st.description) + "</p>" : "";
      return { header: bookTitle + coverBlock + bookDesc, pageInd: "Oldal " + (i + 1) + " / " + pages.length };
    }

    function syncStorybookReaderNavButtons() {
      const out = storybookEls().readerOut;
      if (!out) return;
      const st = storybookReaderState;
      const pages = st.pages || [];
      const i = st.idx;
      const n = pages.length;
      const prevB = out.querySelector('[data-sb-nav="prev"]');
      const nextB = out.querySelector('[data-sb-nav="next"]');
      const busy = storybookReaderTransitioning;
      if (prevB) prevB.disabled = i <= 0 || busy;
      if (nextB) nextB.disabled = n === 0 || i >= n - 1 || busy;
    }

    function wireStorybookReaderNav(out) {
      if (!out || out.dataset.sbNavWired === "1") return;
      out.dataset.sbNavWired = "1";
      out.addEventListener("click", function (e) {
        const btn = e.target && e.target.closest ? e.target.closest("[data-sb-nav]") : null;
        if (!btn || storybookReaderTransitioning) return;
        const dir = btn.getAttribute("data-sb-nav");
        if (dir === "prev") {
          if (storybookReaderState.idx > 0) {
            const oldIndex = storybookReaderState.idx;
            const newIndex = oldIndex - 1;
            renderStorybookReader({ direction: "prev", oldIndex: oldIndex, newIndex: newIndex });
          }
        } else if (dir === "next") {
          const n = (storybookReaderState.pages || []).length;
          if (storybookReaderState.idx < n - 1) {
            const oldIndex = storybookReaderState.idx;
            const newIndex = oldIndex + 1;
            renderStorybookReader({ direction: "next", oldIndex: oldIndex, newIndex: newIndex });
          }
        }
      });
    }

    function renderStorybookReader(opts) {
      opts = opts || {};
      const out = storybookEls().readerOut;
      if (!out || !SBR) return;
      wireStorybookReaderNav(out);
      const st = storybookReaderState;
      const pages = st.pages || [];
      const i = st.idx;
      const p = pages[i];
      const builtEmpty = storybookBuildPublicHeaderHtml(st, i, pages);

      if (!p || !pages.length) {
        out.innerHTML = builtEmpty.header + '<p class="empty" role="status">Nincs megjeleníthető oldal.</p>';
        return;
      }

      let panel = out.querySelector(".sb-read-page-panel");
      if (!panel || !out.querySelector(".sb-public-reader-inner")) {
        out.innerHTML = SBR.buildPublicReaderShellHtml({});
        panel = out.querySelector(".sb-read-page-panel");
      }
      if (!panel) return;
      if (!panel.classList.contains("storybook-page")) panel.classList.add("storybook-page");

      const hdr = out.querySelector(".sb-read-dynamic-header");
      const indEl = out.querySelector(".sb-public-read-pageind");
      const prevB = out.querySelector('[data-sb-nav="prev"]');
      const nextB = out.querySelector('[data-sb-nav="next"]');
      const built = storybookBuildPublicHeaderHtml(st, i, pages);
      if (hdr) hdr.innerHTML = built.header;
      if (indEl) indEl.textContent = built.pageInd;

      function applyPanel() {
        if (typeof opts.newIndex === "number") storybookReaderState.idx = opts.newIndex;
        const pLive = pages[storybookReaderState.idx];
        if (!panel || !pLive) return;
        const builtLive = storybookBuildPublicHeaderHtml(st, storybookReaderState.idx, pages);
        if (hdr) hdr.innerHTML = builtLive.header;
        if (indEl) indEl.textContent = builtLive.pageInd;
        panel.innerHTML = SBR.buildPanelHtml(pLive, {
          escapeHtml: escapeHtml,
          assetUrl: storybookAssetUrl,
          layout: "mesencsi",
        });
      }

      const wantAnim = !!(
        opts.direction &&
        typeof opts.oldIndex === "number" &&
        typeof opts.newIndex === "number"
      );

      if (!wantAnim) {
        panel.classList.remove(
          "sb-read-panel--enter-next",
          "sb-read-panel--enter-prev",
          "sb-read-panel--exit-next",
          "sb-read-panel--exit-prev",
          "page-exit",
          "page-exit--next",
          "page-exit--prev",
          "page-enter-prep",
          "page-enter-prep--next",
          "page-enter-prep--prev",
          "page-enter",
          "sb-page-rm-fade-out",
          "sb-page-rm-fade-in-prep",
          "sb-page-rm-fade-in",
          "page-transition-out",
          "page-transition-out--next",
          "page-transition-out--prev",
          "page-transition-in-prep",
          "page-transition-in"
        );
        applyPanel();
        SBR.preloadAdjacentImages(pages, storybookReaderState.idx, storybookAssetUrl);
        syncStorybookReaderNavButtons();
        return;
      }

      SBR.runPanelTransition(panel, opts.direction, applyPanel, {
        getAnimating: () => storybookReaderTransitioning,
        setAnimating: (v) => {
          storybookReaderTransitioning = v;
        },
        oldIndex: opts.oldIndex,
        newIndex: opts.newIndex,
        preloadAdjacent: () => SBR.preloadAdjacentImages(st.pages || [], st.idx, storybookAssetUrl),
        onDone: syncStorybookReaderNavButtons,
      });
      syncStorybookReaderNavButtons();
    }

    function showStorybookCatalogErrorPanel(els, message) {
      const el = els.catalogOut;
      const list = els.publicList;
      const reader = els.publicReader;
      const ro = els.readerOut;
      if (!el || !list || !reader) return;
      list.hidden = false;
      reader.hidden = true;
      if (ro) {
        ro.innerHTML = "";
        try {
          ro.removeAttribute("data-sb-nav-wired");
        } catch (_) {}
      }
      const safeMsg =
        message && String(message).trim()
          ? String(message).trim()
          : "A mesekönyv jelenleg nem tölthető be.";
      el.innerHTML =
        '<div class="storybook-catalog-error">' +
        '<p class="empty" role="alert">' +
        escapeHtml(safeMsg) +
        "</p>" +
        '<p style="margin-top:0.75rem"><button type="button" class="btn-outline-ghost" data-storybook-error-back>Vissza a listához</button></p>' +
        "</div>";
      const btn = el.querySelector("[data-storybook-error-back]");
      if (btn) {
        btn.addEventListener("click", function () {
          void ensureStorybooksCatalog();
        });
      }
    }

    async function openStorybookReader(slugInput, pageIndexOpt) {
      const els = storybookEls();
      const list = els.publicList;
      const reader = els.publicReader;
      if (!list || !reader) return;
      let slugPart = slugInput != null ? String(slugInput).trim() : "";
      let pageIndex = 1;
      if (pageIndexOpt != null && Number.isFinite(Number(pageIndexOpt))) {
        pageIndex = Math.max(1, Math.floor(Number(pageIndexOpt)));
      }
      const legacy = /^(\d+):(\d+)$/.exec(slugPart);
      if (legacy) {
        const legacyBookId = parseInt(legacy[1], 10);
        pageIndex = Math.max(1, parseInt(legacy[2], 10));
        try {
          const rows = await api("/storybooks");
          const row = Array.isArray(rows) ? rows.find((b) => b.id === legacyBookId) : null;
          if (!row || !String(row.slug || "").trim()) {
            throw new Error("legacy_resolve");
          }
          slugPart = String(row.slug).trim();
        } catch (e) {
          showStorybookCatalogErrorPanel(els, "A mesekönyv jelenleg nem tölthető be.");
          return;
        }
      }
      if (!slugPart) {
        list.hidden = false;
        reader.hidden = true;
        const el = els.catalogOut;
        if (el) {
          el.innerHTML =
            '<p class="empty" role="alert">Hiányzik a mesekönyv azonosítója.</p>' +
            '<p style="margin-top:0.75rem"><button type="button" class="btn-outline-ghost" data-storybook-error-back>Vissza a listához</button></p>';
          const b = el.querySelector("[data-storybook-error-back]");
          if (b)
            b.addEventListener("click", function () {
              void ensureStorybooksCatalog();
            });
        }
        return;
      }
      try {
        const book = await api("/storybooks/" + encodeURIComponent(slugPart));
        const pages = (book.pages || []).slice().sort((a, b) => (a.page_index || 0) - (b.page_index || 0));
        const idx = pages.length ? Math.max(0, Math.min(pageIndex - 1, pages.length - 1)) : 0;
        storybookReaderState = {
          title: book.title || "",
          description: (book.description || "").trim(),
          cover_url: book.cover_image_url || "",
          pages,
          idx,
        };
        list.hidden = true;
        reader.hidden = false;
        storybookReaderTransitioning = false;
        renderStorybookReader();
      } catch (e) {
        showStorybookCatalogErrorPanel(els, "A mesekönyv jelenleg nem tölthető be.");
      }
    }

    async function ensureStorybooksCatalog() {
      const els = storybookEls();
      const el = els.catalogOut;
      const list = els.publicList;
      const reader = els.publicReader;
      if (!el || !list || !reader) return;
      list.hidden = false;
      reader.hidden = true;
      const ro = els.readerOut;
      if (ro) {
        ro.innerHTML = "";
        try {
          ro.removeAttribute("data-sb-nav-wired");
        } catch (_) {}
      }
      storybooksCatalogLoaded = false;
      el.innerHTML = '<p class="empty" role="status">Betöltés…</p>';
      try {
        const rows = await api("/storybooks");
        storybooksCatalogLoaded = true;
        if (!Array.isArray(rows) || !rows.length) {
          el.innerHTML = '<p class="empty" role="status">Jelenleg nincs közzétett mesekönyv.</p>';
          return;
        }
        el.innerHTML = rows
          .map((b) => {
            const slug = b.slug != null ? String(b.slug).trim() : "";
            const bid = Number(b.id);
            const idAttr = Number.isFinite(bid) ? String(bid) : "";
            const cover = b.cover_image_url ? storybookAssetUrl(b.cover_image_url) : "";
            const thumb = cover
              ? '<div class="product-card__thumb"><img src="' +
                escapeHtml(cover) +
                '" alt="" loading="lazy" decoding="async" onerror="this.style.display=\'none\'"/></div>'
              : '<div class="product-card__thumb" aria-hidden="true">📖</div>';
            const desc = b.description ? '<p class="desc">' + escapeHtml(String(b.description).slice(0, 200)) + "</p>" : "";
            return (
              '<article class="product-card product-card--catalog" data-storybook-slug="' +
              escapeHtml(slug) +
              '" data-storybook-id="' +
              escapeHtml(idAttr) +
              '">' +
              thumb +
              "<h3>" +
              escapeHtml(b.title || "") +
              "</h3>" +
              desc +
              '<button type="button" class="user-panel__nav-btn user-panel__nav-btn--wood btn-storybook-open-full" data-storybook-open>Olvasás indítása</button></article>'
            );
          })
          .join("");
        el.querySelectorAll("[data-storybook-slug]").forEach((card) => {
          function openFromCard() {
            const slug = (card.getAttribute("data-storybook-slug") || "").trim();
            const bid = parseInt(card.getAttribute("data-storybook-id"), 10);
            if (slug) openStorybookReader(slug, 1);
            else if (Number.isFinite(bid)) openStorybookReader(bid + ":1", 1);
          }
          const openBtn = card.querySelector("[data-storybook-open]");
          if (openBtn) {
            openBtn.addEventListener("click", function (e) {
              e.stopPropagation();
              openFromCard();
            });
          }
        });
      } catch (e) {
        showStorybookCatalogErrorPanel(els, "A mesekönyvek listája jelenleg nem tölthető be.");
      }
    }

    const btnStorybookBackList = $("btnStorybookBackList");
    if (btnStorybookBackList) {
      btnStorybookBackList.addEventListener("click", () => {
        const list = $("storybooksPublicList");
        const reader = $("storybooksPublicReader");
        if (list) list.hidden = false;
        if (reader) reader.hidden = true;
      });
    }

    function syncHomeNewsChrome(viewName) {
      const heroBand = $("heroBand");
      const archive = $("homeNewsArchive");
      const onHome = viewName === "home";
      const stack = $("pageStack");
      const accountOpen = stack && stack.getAttribute("data-user-account-open") === "1";
      const showNews = onHome && !accountOpen;
      if (heroBand) heroBand.hidden = !showNews;
      if (archive) {
        const archiveList = $("homeNewsArchiveList");
        const hasItems = !!(archiveList && archiveList.children && archiveList.children.length);
        archive.hidden = !showNews || !hasItems;
      }
      document.querySelectorAll("[data-news-post-comments]").forEach(function (block) {
        block.hidden = !showNews;
      });
      if (showNews) void refreshAllNewsCommentsOnHome();
    }

    function showView(name) {
      closeUserAccountPanelsOnly();
      if ((name === "webshop" || name === "cart" || name === "storybooks") && !isShopUserLoggedIn()) {
        const msg =
          name === "webshop" ? MSG_WEBSHOP_AUTH : name === "cart" ? MSG_PURCHASE_AUTH : MSG_STORYBOOKS_AUTH;
        setAuthLine($("loginMsg"), msg, false);
        showView("home");
        return;
      }

      if (name !== "home") {
        try {
          if (typeof window.mesencsiCloseMobileNav === "function") window.mesencsiCloseMobileNav();
        } catch (_) {}
      }

      const stack = $("pageStack");
      const prevView = stack ? stack.getAttribute("data-current-view") || "home" : "home";
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
        syncHomeNewsChrome("home");
        VIEWS.forEach((v) => {
          const el = $("view-" + v);
          if (!el) return;
          el.classList.remove("is-active");
          el.hidden = true;
        });
        window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
        syncCartFabVisibility();
        return;
      }

      if (!VIEWS.includes(name)) {
        showView("home");
        return;
      }

      stack.setAttribute("data-current-view", name);
      homeIntro.hidden = true;
      syncHomeNewsChrome(name);
      const target = $("view-" + name);
      target.hidden = false;
      target.classList.add("is-active");
      window.scrollTo({ top: 0, left: 0, behavior: "smooth" });

      if (name === "webshop") {
        ensureCatalog();
      }
      if (name === "cart") {
        updateCartUI();
        syncCheckoutEmailFromSession();
        wireCheckoutAddressConfirmPreview();
        updateCheckoutCouponDisplay();
        if (isShopUserLoggedIn()) {
          if (cart.length) scheduleCartPricingEstimate();
          else void restoreStoredCheckoutCoupon();
        }
      }
      if (name === "gallery" && prevView !== "gallery") {
        void ensureGallery();
      }
      if (name === "stories") {
        ensureProductsCatalog();
      }
      if (name === "storybooks") {
        ensureStorybooksCatalog();
      }
      syncCartFabVisibility();
    }

    function navigateTo(path, viewName) {
      try {
        history.pushState({ view: viewName }, "", path);
      } catch {
        // ignore
      }
      showView(viewName);
    }

    function viewFromPathname(pathname) {
      if (pathname === "/aszf") return "aszf";
      if (pathname === "/adatkezeles") return "adatkezeles";
      if (pathname === "/impresszum") return "impresszum";
      return "home";
    }

    document.querySelectorAll("[data-view]").forEach((el) => {
      el.addEventListener("click", () => {
        const v = el.getAttribute("data-view");
        if (!v) return;
        if ((v === "webshop" || v === "cart" || v === "storybooks") && !isShopUserLoggedIn()) {
          const msg =
            v === "webshop" ? MSG_WEBSHOP_AUTH : v === "cart" ? MSG_PURCHASE_AUTH : MSG_STORYBOOKS_AUTH;
          setAuthLine($("loginMsg"), msg, false);
          try {
            const le = $("loginEmail");
            if (le) le.focus();
          } catch (_) {}
          return;
        }
        // belső nézeteknél maradunk a fő URL-en
        try {
          history.pushState({ view: v }, "", "/");
        } catch {
          // ignore
        }
        showView(v);
      });
    });

    document.querySelectorAll("[data-route]").forEach((el) => {
      el.addEventListener("click", (e) => {
        const path = el.getAttribute("data-route");
        if (!path) return;
        // ugyanazon origin esetén SPA navigáció
        e.preventDefault();
        const view = viewFromPathname(path);
        if (view === "home") {
          navigateTo("/", "home");
        } else {
          navigateTo(path, view);
        }
      });
    });

    window.addEventListener("popstate", () => {
      showView(viewFromPathname(window.location.pathname));
    });

    const cartWithItems = $("cartWithItems");
    if (cartWithItems) {
      cartWithItems.addEventListener("click", (e) => {
        if (!isShopUserLoggedIn()) return;
        const rm = e.target.closest("[data-cart-remove]");
        if (!rm) return;
        const i = parseInt(rm.getAttribute("data-cart-remove"), 10);
        if (Number.isNaN(i)) return;
        cart.splice(i, 1);
        updateCartUI();
        if (isShopUserLoggedIn() && cart.length) scheduleCartPricingEstimate();
      });
      cartWithItems.addEventListener("change", (e) => {
        if (!isShopUserLoggedIn()) return;
        const t = e.target;
        if (!(t instanceof HTMLInputElement) || !t.matches("input[data-cart-qty]")) return;
        const i = parseInt(t.getAttribute("data-cart-qty"), 10);
        if (Number.isNaN(i) || !cart[i]) return;
        let q = parseInt(t.value, 10);
        if (!Number.isFinite(q) || q < 1) q = 1;
        cart[i].quantity = q;
        updateCartUI();
        if (isShopUserLoggedIn() && cart.length) scheduleCartPricingEstimate();
      });
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
      const raw = startPayload.redirect_url != null ? startPayload.redirect_url : startPayload.gateway_url;
      return raw != null ? String(raw).trim() : "";
    }

    async function retryBarionPaymentForOrderGroup(orderIds, minId, productLabel, triggerBtn) {
      if (orderPaymentRetryBusy) return;
      const token = shopUserAccessToken();
      const st = $("userOrdersStatus");
      if (!token) {
        if (st) {
          st.textContent = "A fizetés újrapróbálásához jelentkezz be.";
        }
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
        (productLabel ? " — " + productLabel : defaultLabel ? " — " + defaultLabel : "");

      orderPaymentRetryBusy = true;
      if (triggerBtn) {
        if (!triggerBtn.dataset.retryLabelDefault) {
          triggerBtn.dataset.retryLabelDefault = (triggerBtn.textContent || "Fizetés újrapróbálása").trim();
        }
        triggerBtn.disabled = true;
        triggerBtn.setAttribute("aria-busy", "true");
        triggerBtn.textContent = "Fizetés indítása...";
      }
      if (st) st.textContent = "Fizetés indítása…";

      let redirecting = false;
      try {
        const payStart = await api("/payments/barion/start", {
          method: "POST",
          headers: { Authorization: "Bearer " + token },
          body: JSON.stringify({ order_ids: ids, description: desc.slice(0, 500) }),
        });
        const redirectUrl = barionRedirectUrlFromStart(payStart);
        if (redirectUrl) {
          redirecting = true;
          try {
            sessionStorage.setItem("mesencsi_barion_checkout_redirect", "1");
          } catch (_) {}
          window.location.assign(redirectUrl);
          return;
        }
        const info =
          (payStart && payStart.message) ||
          "A fizetés nem indult el — nincs átirányítási cím. Próbáld újra később.";
        if (st) st.textContent = info;
      } catch (e) {
        const detail = (e && e.message) || "A fizetés indítása sikertelen.";
        if (st) {
          st.textContent =
            detail + " Ha a gond továbbra is fennáll, vedd fel velünk a kapcsolatot.";
        }
      } finally {
        orderPaymentRetryBusy = false;
        if (!redirecting && triggerBtn) {
          triggerBtn.disabled = false;
          triggerBtn.removeAttribute("aria-busy");
          triggerBtn.textContent = triggerBtn.dataset.retryLabelDefault || "Fizetés újrapróbálása";
        }
      }
    }

    let checkoutSubmitting = false;

    function setCheckoutSubmitBusy(busy) {
      checkoutSubmitting = !!busy;
      if (checkoutForm) {
        if (busy) {
          checkoutForm.setAttribute("aria-busy", "true");
          checkoutForm.setAttribute("inert", "");
        } else {
          checkoutForm.removeAttribute("aria-busy");
          checkoutForm.removeAttribute("inert");
        }
      }
      const btn = checkoutForm ? checkoutForm.querySelector('button[type="submit"]') : null;
      if (!btn) return;
      if (!btn.dataset.checkoutLabelDefault) {
        btn.dataset.checkoutLabelDefault = (btn.textContent || "Megrendelés és fizetés indítása").trim();
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

    /**
     * Kosár ürítése: sikeres Barion redirect előtt (dupla checkout elkerülése), vagy megerősített paid return után.
     * Payment start fail / hiányzó redirect URL esetén nem hívandó.
     */
    function finalizeCheckoutCartUi() {
      cart = [];
      clearCheckoutCouponState();
      updateCartUI();
      persistCart();
      const checkoutFormEl = $("checkoutForm");
      if (checkoutFormEl) checkoutFormEl.reset();
    }

    const checkoutForm = document.getElementById("checkoutForm");
    if (checkoutForm) {
      checkoutForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        if (checkoutSubmitting) return;

        let checkoutRedirecting = false;
        setCheckoutSubmitBusy(true);

        const msg = $("cartMsg");
        hide(msg);

        try {
        if (!isShopUserLoggedIn()) {
          show(msg, MSG_PURCHASE_AUTH, false);
          return;
        }

        if (!cart.length) {
          show(msg, "A kosár üres — előbb válassz terméket a webshopban.", false);
          return;
        }

        const customer_name = $("checkoutName").value.trim();
        const token = shopUserAccessToken();

        const nameErr = validatePersonNameField(customer_name, "Név", "customer_name");
        if (nameErr) {
          show(msg, nameErr, false);
          return;
        }
        const emailErr = validateEmailField($("checkoutEmail") && $("checkoutEmail").value);
        if (emailErr) {
          show(msg, emailErr, false);
          return;
        }
        const phoneErr = validatePhoneOnly($("checkoutPhone") && $("checkoutPhone").value);
        if (phoneErr) {
          show(msg, phoneErr, false);
          return;
        }
        const shipBuilt = checkoutShippingAddressPayload();
        if (!shipBuilt.ok) {
          show(msg, (shipBuilt.errors[0] && shipBuilt.errors[0].message) || "Érvénytelen szállítási cím.", false);
          return;
        }
        const confirmCb = $("checkoutAddressConfirmCb");
        if (confirmCb && !confirmCb.checked) {
          show(msg, "Kérjük, erősítsd meg, hogy a szállítási adatok helyesek.", false);
          return;
        }
        if (!token) {
          show(msg, MSG_PURCHASE_AUTH + " (A belépő a bal oldali fióknál van, mobilon a menüben.)", false);
          return;
        }

        const body = {
          customer_name,
          items: cart.map((c) => ({ product_id: c.id, quantity: c.quantity })),
          company_website: ($("checkoutCompanyWebsite") && $("checkoutCompanyWebsite").value) || "",
          shipping_address: shipBuilt.json,
        };
        const notes = $("checkoutNotes").value.trim();
        if (notes) {
          if (containsUnsafeMarkup(notes) || notes.length > 2000) {
            show(msg, "A megjegyzés érvénytelen vagy túl hosszú.", false);
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
        const couponForOrder = checkoutCouponCode || getStoredCheckoutCoupon() || "";
        if (
          couponForOrder &&
          lastOrderEstimate &&
          checkoutEstimateSig === cartSig &&
          lastOrderEstimate.coupon_code &&
          String(lastOrderEstimate.coupon_code).toUpperCase() === String(couponForOrder).toUpperCase()
        ) {
          body.coupon_code = lastOrderEstimate.coupon_code;
        }

        const payDescription =
          "Mesencsi rendelés — " +
          cart
            .map(function (c) {
              return (c.name || "termék") + " ×" + c.quantity;
            })
            .join(", ");

          const data = await api("/orders", {
            method: "POST",
            headers: { Authorization: "Bearer " + token },
            body: JSON.stringify(body),
          });

          const orderIds = orderIdsFromCreateResponse(data);
          if (!orderIds.length) {
            show(
              msg,
              "A rendelés létrejöhetett, de a fizetés nem indult el (hiányzó rendelés azonosító). A kosár megmaradt — nézd a Fiók → Rendeléseim menüt, vagy próbáld újra.",
              false
            );
            window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
            return;
          }

          let payStart;
          try {
            payStart = await api("/payments/barion/start", {
              method: "POST",
              headers: { Authorization: "Bearer " + token },
              body: JSON.stringify({ order_ids: orderIds, description: payDescription }),
            });
          } catch (payErr) {
            const payDetail =
              (payErr && payErr.message) || "A fizetés indítása sikertelen (hálózati vagy szerverhiba).";
            show(
              msg,
              "A rendelés létrejöhetett, de a fizetés nem indult el. A kosár megmaradt — " +
                payDetail +
                " Nézd a Fiók → Rendeléseim menüt, vagy próbáld újra a fizetést.",
              false
            );
            window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
            return;
          }

          const redirectUrl = barionRedirectUrlFromStart(payStart);
          if (redirectUrl) {
            checkoutRedirecting = true;
            try {
              sessionStorage.setItem("mesencsi_barion_checkout_redirect", "1");
            } catch (_) {}
            finalizeCheckoutCartUi();
            window.location.assign(redirectUrl);
            return;
          }

          const info =
            payStart && payStart.message
              ? String(payStart.message)
              : "A rendelés létrejöhetett, de nincs Barion átirányítás. A kosár megmaradt — nézd a Fiók → Rendeléseim menüt.";
          show(msg, info, false);
          window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
        } catch (e) {
          const detail = e && e.message ? String(e.message) : friendlyBackendError();
          show(msg, detail || "Nem sikerült elküldeni a rendelést. Próbáld újra.", false);
        } finally {
          if (!checkoutRedirecting) setCheckoutSubmitBusy(false);
        }
      });
    }

    const loginForm = $("loginForm");
    if (loginForm) {
      loginForm.addEventListener("submit", async function (e) {
        e.preventDefault();
        clearBarionReturnNotice();
        setAuthLine($("loginMsg"), "", null);
        const email = ($("loginEmail") && $("loginEmail").value.trim()) || "";
        const password = ($("loginPassword") && $("loginPassword").value) || "";
        if (!email || !password) {
          setAuthLine($("loginMsg"), "Add meg az e-mail címet és a jelszót.", false);
          return;
        }
        const loginEmailEl = $("loginEmail");
        if (loginEmailEl && !loginEmailEl.checkValidity()) {
          try {
            loginEmailEl.reportValidity();
          } catch (_) {}
          return;
        }
        try {
          const data = await api("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email, password }),
          });
          if (!data || !data.access_token) {
            setAuthLine($("loginMsg"), "Váratlan válasz a szervertől.", false);
            return;
          }
          saveAuthSession(data.access_token, data.user);
          if ($("loginPassword")) $("loginPassword").value = "";
          clearBarionReturnNotice();
          showAuthUser(data.user);
          setAuthLine($("loginMsg"), "Sikeres belépés.", true);
          syncCheckoutEmailFromSession();
        } catch (err) {
          setAuthLine($("loginMsg"), (err && err.message) || "Belépés sikertelen.", false);
        }
      });
    }

    const showReg = $("showRegisterBtn");
    if (showReg) showReg.addEventListener("click", showAuthRegister);

    const backLogin = $("backToLoginBtn");
    if (backLogin) {
      backLogin.addEventListener("click", function () {
        showAuthGuest();
        setAuthLine($("registerMsg"), "", null);
      });
    }

    const registerForm = $("registerForm");
    if (registerForm) {
      registerForm.addEventListener("submit", async function (e) {
        e.preventDefault();
        setAuthLine($("registerMsg"), "", null);
        const email = ($("regEmail") && $("regEmail").value.trim()) || "";
        const password = ($("regPassword") && $("regPassword").value) || "";
        const password2 = ($("regPassword2") && $("regPassword2").value) || "";
        if (!email || !password) {
          setAuthLine($("registerMsg"), "Az e-mail és a jelszó kötelező.", false);
          return;
        }
        if (password.length < 8) {
          setAuthLine($("registerMsg"), "A jelszónak legalább 8 karakter hosszúnak kell lennie.", false);
          return;
        }
        if (password !== password2) {
          setAuthLine($("registerMsg"), "A két jelszó nem egyezik.", false);
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
          company_website: ($("regCompanyWebsite") && $("regCompanyWebsite").value) || "",
        };
        try {
          const regData = await api("/auth/register", { method: "POST", body: JSON.stringify(payload) });
          registerForm.reset();
          if ($("loginEmail")) $("loginEmail").value = email;
          showAuthGuest();
          let okMsg =
            "Regisztráció rendben — nézd meg a postafiókodat, erősítsd meg az e-mailt, majd lépj be.";
          if (regData && regData.verification_email_sent === false && regData.message) {
            okMsg = regData.message;
          } else if (regData && regData.verification_email_sent === false) {
            okMsg =
              "A regisztráció sikeres, de a visszaigazoló email küldése sikertelen. Kérj új levelet bejelentkezés után, vagy nézd a szerver naplót.";
          }
          setAuthLine($("loginMsg"), okMsg, regData && regData.verification_email_sent === false ? false : true);
          setAuthLine($("registerMsg"), "", null);
          if ($("loginPassword")) $("loginPassword").focus();
        } catch (err) {
          setAuthLine($("registerMsg"), (err && err.message) || "Regisztráció sikertelen.", false);
        }
      });
    }

    const logoutBtn = $("logoutBtn");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", function () {
        clearBarionReturnNotice();
        setAuthLine($("loginMsg"), "", null);
        void flushCartToServer().finally(function () {
          cart = [];
          clearAuthSession();
          showAuthGuest();
          const em = $("checkoutEmail");
          if (em) em.value = "";
          const cn = $("checkoutName");
          if (cn) cn.value = "";
          clearCheckoutShippingFields();
          try {
            if (typeof window.mesencsiCloseMobileNav === "function") window.mesencsiCloseMobileNav();
          } catch (_) {}
        });
      });
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
        const btn = ev.target && ev.target.closest ? ev.target.closest("[data-user-section]") : null;
        if (!btn) return;
        const sec = btn.getAttribute("data-user-section");
        if (!sec) return;
        ev.preventDefault();
        void setActiveUserSection(sec);
      });
    }

    const resendVerificationBtn = $("resendVerificationBtn");
    if (resendVerificationBtn) {
      resendVerificationBtn.addEventListener("click", async function () {
        const t = shopUserAccessToken();
        const rmsg = $("resendVerificationMsg");
        if (!t) return;
        if (rmsg) {
          rmsg.textContent = "Küldés…";
          rmsg.className = "auth-msg";
        }
        try {
          await api("/auth/resend-verification", {
            method: "POST",
            headers: { Authorization: "Bearer " + t, "Content-Type": "application/json" },
            body: "{}",
          });
          if (rmsg) {
            rmsg.textContent = "Ha van aktív SMTP, a levél úton van. (Fejlesztői módban nézd a szerver naplót.)";
            rmsg.className = "auth-msg";
          }
        } catch (e) {
          if (rmsg) {
            rmsg.textContent = (e && e.message) || "Nem sikerült elkérni az új levelet.";
            rmsg.className = "auth-msg";
          }
        }
      });
    }

    document.addEventListener("click", function (ev) {
      const link = ev.target && ev.target.closest ? ev.target.closest("[data-open-user-discounts]") : null;
      if (!link) return;
      ev.preventDefault();
      if (!isShopUserLoggedIn()) {
        setAuthLine($("loginMsg"), MSG_PURCHASE_AUTH, false);
        return;
      }
      void setActiveUserSection("discounts");
    });

    const btnCouponClear = $("btnCouponClear");
    if (btnCouponClear) {
      btnCouponClear.addEventListener("click", function () {
        clearCheckoutCouponState();
        updateCartUI();
        if (cart.length) scheduleCartPricingEstimate();
        const msg = $("cartMsg");
        if (msg) hide(msg);
      });
    }

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

    if (!document.body.dataset.newsCommentsDelegated) {
      document.body.dataset.newsCommentsDelegated = "1";
      document.body.addEventListener("submit", async function (e) {
        const form = e.target && e.target.closest ? e.target.closest("[data-news-comment-form]") : null;
        if (!form) return;
        e.preventDefault();
        const block = form.closest("[data-news-post-comments]");
        if (!block) return;
        const newsId = parseInt(block.getAttribute("data-news-id") || "", 10);
        if (!Number.isFinite(newsId)) return;
        if (newsCommentsSubmitting.has(newsId)) return;
        const t = shopUserAccessToken();
        const msgEl = form.querySelector("[data-comment-form-msg]");
        if (!t) {
          setAuthLine(msgEl, "Kommenteléshez kérlek jelentkezz be.", false);
          return;
        }
        if (!newsCommentCanPost()) {
          setAuthLine(
            msgEl,
            "Kommenteléshez erősítsd meg az e-mail címed — a Fiók → Fiók adatok menüben.",
            false
          );
          void refreshNewsCommentsBlock(block);
          return;
        }
        const bodyEl = form.querySelector("[data-comment-body]");
        const content = (bodyEl && bodyEl.value.trim()) || "";
        if (content.length < 2) {
          setAuthLine(msgEl, "A hozzászólás legalább 2 karakter legyen.", false);
          return;
        }
        const submitBtn = form.querySelector('button[type="submit"]');
        newsCommentsSubmitting.add(newsId);
        setAuthLine(msgEl, "", null);
        try {
          if (submitBtn) submitBtn.disabled = true;
          if (bodyEl) bodyEl.disabled = true;
          form.setAttribute("aria-busy", "true");
          setAuthLine(msgEl, "Küldés…", null);
          await api("/news/" + newsId + "/comments", {
            method: "POST",
            headers: { Authorization: "Bearer " + t },
            body: JSON.stringify({ content: content }),
          });
          if (bodyEl) bodyEl.value = "";
          setAuthLine(msgEl, "Közzétettük a hozzászólásod — azonnal látható ennél a hírnél.", true);
          await refreshNewsCommentsBlock(block);
          const list = block.querySelector("[data-comment-list]");
          if (list && list.lastElementChild) {
            list.lastElementChild.scrollIntoView({ behavior: "smooth", block: "nearest" });
          }
        } catch (err) {
          setAuthLine(msgEl, (err && err.message) || "A hozzászólás küldése sikertelen.", false);
        } finally {
          newsCommentsSubmitting.delete(newsId);
          form.removeAttribute("aria-busy");
          if (submitBtn) submitBtn.disabled = false;
          if (bodyEl) bodyEl.disabled = false;
        }
      });
    }

    const profileForm = $("profileForm");
    if (profileForm) {
      profileForm.addEventListener("submit", async function (e) {
        e.preventDefault();
        const t = shopUserAccessToken();
        if (!t) return;
        setAuthLine($("profileMsg"), "", null);
        const billSameEl = $("profBillSame");
        const sameBilling = !!(billSameEl && billSameEl.checked);
        const profPhoneVal = ($("profPhone") && $("profPhone").value.trim()) || "";
        const phoneErrProf = profPhoneVal ? validatePhoneOnly(profPhoneVal) : null;
        if (phoneErrProf) {
          setAuthLine($("profileMsg"), phoneErrProf, false);
          return;
        }
        const shipBuilt = buildOptionalProfileAddressJson(
          profileAddressPartsFromInputs("profShip"),
          profPhoneVal
        );
        if (!shipBuilt.ok) {
          setAuthLine(
            $("profileMsg"),
            (shipBuilt.errors[0] && shipBuilt.errors[0].message) || "Érvénytelen szállítási cím.",
            false
          );
          return;
        }
        let billBuilt = { ok: true, json: null };
        if (!sameBilling) {
          billBuilt = buildOptionalProfileAddressJson(profileAddressPartsFromInputs("profBill"), null);
          if (!billBuilt.ok) {
            setAuthLine(
              $("profileMsg"),
              (billBuilt.errors[0] && billBuilt.errors[0].message) || "Érvénytelen számlázási cím.",
              false
            );
            return;
          }
        }
        const imgHidden = $("profProfileImageUrl");
        const profileImg = imgHidden && imgHidden.value != null ? String(imgHidden.value).trim() : "";
        const body = {
          nickname: ($("profNickname") && $("profNickname").value.trim()) || null,
          email: ($("profEmail") && $("profEmail").value.trim()) || "",
          phone: profPhoneVal || null,
          shipping_address: shipBuilt.json,
          billing_address: billBuilt.json,
          short_bio: ($("profShortBio") && $("profShortBio").value.trim()) || null,
          family_note: ($("profFamilyNote") && $("profFamilyNote").value.trim()) || null,
          profile_image_url: profileImg || null,
        };
        const profEmailErr = validateEmailField(body.email);
        if (profEmailErr) {
          setAuthLine($("profileMsg"), profEmailErr, false);
          return;
        }
        try {
          const updated = await api("/users/me", {
            method: "PATCH",
            headers: { Authorization: "Bearer " + t },
            body: JSON.stringify(body),
          });
          saveAuthSession(t, updated);
          showAuthUser(updated);
          setAuthLine($("profileMsg"), "Profil mentve. A „Mégse” gombbal zárhatod.", true);
          syncCheckoutEmailFromSession();
        } catch (err) {
          setAuthLine($("profileMsg"), (err && err.message) || "Mentés sikertelen.", false);
        }
      });
    }

    const profNicknameInput = $("profNickname");
    if (profNicknameInput) {
      profNicknameInput.addEventListener("input", function () {
        const img = $("profAvatarPreviewImg");
        if (img && !img.hidden) return;
        const hidden = $("profProfileImageUrl");
        const url = hidden && hidden.value != null ? String(hidden.value).trim() : "";
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
        const t = shopUserAccessToken();
        if (!t) return;
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
          const updated = await apiMultipart("/users/me/avatar", fd, t);
          saveAuthSession(t, updated);
          showAuthUser(updated);
          applyProfileAvatarPreview(updated.profile_image_url || "", updated);
          try {
            inp.value = "";
          } catch (_) {}
          setAuthLine($("profileMsg"), "Profilkép feltöltve és elmentve.", true);
        } catch (err) {
          setAuthLine($("profileMsg"), (err && err.message) || "Feltöltés sikertelen.", false);
        } finally {
          profAvatarUploadBtn.disabled = false;
        }
      });
    }

    const profAvatarClearBtn = $("profAvatarClearBtn");
    if (profAvatarClearBtn) {
      profAvatarClearBtn.addEventListener("click", async function () {
        const t = shopUserAccessToken();
        if (!t) return;
        setAuthLine($("profileMsg"), "", null);
        try {
          profAvatarClearBtn.disabled = true;
          const updated = await api("/users/me", {
            method: "PATCH",
            headers: { Authorization: "Bearer " + t },
            body: JSON.stringify({ profile_image_url: null }),
          });
          saveAuthSession(t, updated);
          showAuthUser(updated);
          applyProfileAvatarPreview("", updated);
          setAuthLine($("profileMsg"), "Profilkép eltávolítva.", true);
        } catch (err) {
          setAuthLine($("profileMsg"), (err && err.message) || "Nem sikerült eltávolítani.", false);
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
      if (deactivateAccountModalCancel) deactivateAccountModalCancel.disabled = false;
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
      if (deactivateAccountModalCancel) deactivateAccountModalCancel.disabled = false;
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
        const t = shopUserAccessToken();
        if (!t) {
          closeDeactivateAccountModal();
          return;
        }
        if (deactivateAccountModalError) {
          deactivateAccountModalError.textContent = "";
          deactivateAccountModalError.hidden = true;
        }
        deactivateAccountModalConfirm.disabled = true;
        if (deactivateAccountModalCancel) deactivateAccountModalCancel.disabled = true;
        deactivateAccountModalConfirm.textContent = "Deaktiválás…";
        try {
          await api("/users/me", {
            method: "DELETE",
            headers: { Authorization: "Bearer " + t },
          });
          closeDeactivateAccountModal();
          clearAuthSession();
          showAuthGuest();
          const em = $("checkoutEmail");
          if (em) em.value = "";
          const cn = $("checkoutName");
          if (cn) cn.value = "";
          clearCheckoutShippingFields();
          try {
            if (typeof window.mesencsiCloseMobileNav === "function") window.mesencsiCloseMobileNav();
          } catch (_) {}
          setAuthLine(
            $("loginMsg"),
            "A fiókod inaktiválva lett. Most kijelentkeztettünk — új regisztrációval tudsz majd belépni.",
            true
          );
        } catch (err) {
          const msg = (err && err.message) || "A deaktiválás nem sikerült. Próbáld újra később.";
          if (deactivateAccountModalError) {
            deactivateAccountModalError.textContent = msg;
            deactivateAccountModalError.hidden = false;
          }
          deactivateAccountModalConfirm.disabled = false;
          if (deactivateAccountModalCancel) deactivateAccountModalCancel.disabled = false;
          deactivateAccountModalConfirm.textContent = "Igen, deaktiválom";
        }
      });
    }

    async function bootstrapAuthUiAsync() {
      const t = shopUserAccessToken();
      if (!t) {
        showAuthGuest();
        return;
      }
      showAuthBoot();
      try {
        await refreshShopUser();
      } finally {
        hideAuthBoot();
      }
    }

    const cartFab = $("cartFab");
    if (cartFab) {
      cartFab.addEventListener("click", () => {
        if (!isShopUserLoggedIn()) {
          setAuthLine($("loginMsg"), MSG_PURCHASE_AUTH, false);
          return;
        }
        try {
          history.pushState({ view: "cart" }, "", "/");
        } catch {
          // ignore
        }
        showView("cart");
      });
    }

    (function initMobileDrawerNav() {
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
          if (!isMobileNav() || !document.body.classList.contains("mobile-nav-open")) return;
          closeMobileNav();
        });
      }
      document.addEventListener("keydown", function (e) {
        if (e.key !== "Escape") return;
        if (typeof window.mesencsiResetOverlays === "function") window.mesencsiResetOverlays();
        var bootEl = document.getElementById("authBoot");
        if (bootEl && !bootEl.hidden && typeof window.mesencsiAuthBootEscape === "function") {
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
          if (!isMobileNav() || !document.body.classList.contains("mobile-nav-open")) return;
          if (e.target.closest("[data-view]")) {
            closeMobileNav();
          }
        });
      }
    })();

    (function mesencsiOverlaySafetyNet() {
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
          if (typeof window.mesencsiCloseMobileNav === "function") window.mesencsiCloseMobileNav();
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
    })();

    (function initPaymentReturnBanner() {
      const closeBtn = $("paymentReturnBannerClose");
      if (closeBtn) {
        closeBtn.addEventListener("click", function () {
          clearBarionReturnNotice();
        });
      }
      const actionBtn = $("paymentReturnBannerAction");
      if (actionBtn) {
        actionBtn.addEventListener("click", function () {
          openOrdersFromPaymentBanner();
        });
      }
    })();

    void (async function mesencsiBoot() {
      if (typeof window.mesencsiResetOverlays === "function") window.mesencsiResetOverlays();
      let clearCartAfterBarionPaid = false;
      try {
        const params = new URLSearchParams(window.location.search);
        const vtok = params.get("email_verify_token");
        const paymentQ = (params.get("payment") || "").trim().toLowerCase();
        const resultQ = (params.get("result") || "").trim().toLowerCase();
        const barionReturn = paymentQ === "barion";
        const barionPaymentErrorLanding = paymentQ === "error" || resultQ === "error";
        if (vtok) {
          try {
            await api("/auth/verify-email?token=" + encodeURIComponent(vtok));
            params.delete("email_verify_token");
            const qs = params.toString();
            history.replaceState(null, "", window.location.pathname + (qs ? "?" + qs : "") + window.location.hash);
            setAuthLine($("loginMsg"), "E-mail cím megerősítve — most már beléphetsz.", true);
          } catch (e) {
            setAuthLine($("loginMsg"), (e && e.message) || "A megerősítés nem sikerült (lejárt vagy hibás link).", false);
          }
        }
        if (barionPaymentErrorLanding) {
          showBarionPaymentLandingNotice(barionPaymentLandingErrorMsg(), "error");
          stripBarionPaymentQueryFromUrl(params);
          try {
            sessionStorage.removeItem("mesencsi_barion_checkout_redirect");
          } catch (_) {}
        } else if (barionReturn) {
          const pid = (params.get("pid") || "").trim();
          let barionMsg = "";
          let barionKind = "error";
          let paymentConfirmedPaid = false;
          const shopTok = shopUserAccessToken();
          const barionCautiousMsg = function (prefix) {
            const pending =
              "Fizetés feldolgozása folyamatban. Visszaigazolást emailben küldünk sikeres fizetés után.";
            return checkoutAbandonedGuidanceMsg(((prefix || "").trim() + " " + pending).trim());
          };
          if (!isBarionPaymentIdUsable(pid)) {
            const prefix = !shopTok
              ? "Hiányzik vagy érvénytelen a fizetés azonosítója. Lépj be ugyanazzal a fiókkal, amellyel rendeltél."
              : "Hiányzik vagy érvénytelen a fizetés azonosítója.";
            barionMsg = barionPaymentLandingErrorMsg(prefix);
            barionKind = "error";
          } else if (shopTok) {
            try {
              const st = await api("/payments/barion/payment/" + encodeURIComponent(pid) + "/state", {
                headers: { Authorization: "Bearer " + shopTok },
              });
              const ps = st && st.payment_status ? st.payment_status : "pending";
              if (ps === "paid") {
                barionMsg =
                  "Fizetés sikeresen teljesült. Visszaigazolást emailben küldünk. A rendelés állapota a Fiók → Rendeléseim menüben követhető.";
                barionKind = "success";
                paymentConfirmedPaid = true;
              } else if (ps === "failed" || ps === "cancelled") {
                barionMsg = barionPaymentLandingErrorMsg("Fizetés: " + shopPaymentStatusHu(ps) + ".");
                barionKind = "error";
              } else {
                barionMsg = barionCautiousMsg("Fizetés: " + shopPaymentStatusHu(ps) + ".");
                barionKind = "pending";
              }
            } catch (e) {
              barionMsg = barionPaymentLandingErrorMsg(
                (e && e.message) || "A fizetés állapotát most nem ellenőrizhető."
              );
              barionKind = "error";
            }
          } else {
            barionMsg = barionPaymentLandingErrorMsg(
              "A pontos állapothoz lépj be ugyanazzal a fiókkal, amellyel rendeltél."
            );
            barionKind = "error";
          }
          clearCartAfterBarionPaid = paymentConfirmedPaid;
          stripBarionPaymentQueryFromUrl(params);
          showBarionPaymentLandingNotice(barionMsg, barionKind);
          try {
            sessionStorage.removeItem("mesencsi_barion_checkout_redirect");
          } catch (_) {}
        }
      } catch (_) {}
      await bootstrapAuthUiAsync();
      applyBarionReturnNotice();
      loadCartFromStorage();
      if (clearCartAfterBarionPaid && cart.length) {
        finalizeCheckoutCartUi();
      }
      applyPurchaseGates();
      updateCartUI();
      void loadHomeNews();
      showView(viewFromPathname(window.location.pathname));
    })();

    // Hidden admin entry point — mindig az API hostra mutat (static szerverről is)
    (function initAdminFab() {
      const fab = document.getElementById("adminFab");
      if (!fab) return;
      let token = "";
      try {
        token = localStorage.getItem("token") || "";
      } catch {
        token = "";
      }
      const base = apiBase().replace(/\/$/, "");
      fab.href = base + (token ? "/admin" : "/admin/login");
    })();
