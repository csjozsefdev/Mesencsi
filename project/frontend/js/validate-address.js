(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});

  const PROFILE_ADDRESS_JSON_V = 2;

  const _UNSAFE_MARKUP_RE =
    /[<>]|javascript\s*:|data\s*:|vbscript\s*:|on\w+\s*=/i;
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
    p.recipient_name =
      o.recipient_name != null ? String(o.recipient_name).trim() : "";
    p.phone = o.phone != null ? String(o.phone).trim() : "";
    p.postal_code = o.postal_code != null ? String(o.postal_code).trim() : "";
    p.city = o.city != null ? String(o.city).trim() : "";
    p.street = o.street != null ? String(o.street).trim() : "";
    p.house_number =
      o.house_number != null ? String(o.house_number).trim() : "";
    p.line2 = o.line2 != null ? String(o.line2).trim() : "";
    p.country = o.country != null ? String(o.country).trim() : "";
    if (!p.country) p.country = "Magyarország";
    return p;
  }

  function normalizeHuPhoneDigits(raw) {
    let digits = String(raw || "").replace(/\D/g, "");
    if (digits.indexOf("36") === 0 && digits.length >= 10)
      digits = digits.slice(2);
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

    function requireField(
      field,
      label,
      value,
      minLen,
      maxLen,
      pattern,
      patternMsg,
    ) {
      const s = value != null ? String(value).trim() : "";
      if (!s) {
        if (requireAll)
          pushError(field, "A(z) " + label + " megadása kötelező.");
        return "";
      }
      if (s.length < minLen) {
        pushError(field, "A(z) " + label + " túl rövid.");
        return s;
      }
      if (s.length > maxLen) {
        pushError(
          field,
          "A(z) " + label + " legfeljebb " + maxLen + " karakter lehet.",
        );
        return s;
      }
      if (containsUnsafeMarkup(s)) {
        pushError(
          field,
          "A(z) " + label + " nem tartalmazhat HTML-t vagy szkriptet.",
        );
        return s;
      }
      if (pattern && !pattern.test(s)) {
        pushError(
          field,
          patternMsg || "A(z) " + label + " formátuma érvénytelen.",
        );
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
        return {
          ok: true,
          errors: [],
          warnings: [],
          normalized: emptyProfileAddressParts(),
        };
      }
    }

    const recipient_name = requireField(
      "recipient_name",
      "átvevő neve",
      p.recipient_name,
      2,
      128,
      _NAME_RE,
      "Az átvevő neve csak betűket és szóközt tartalmazhat.",
    );
    const phoneRaw = requireField(
      "phone",
      "telefonszám",
      p.phone,
      8,
      32,
      null,
      null,
    );
    if (
      phoneRaw &&
      !errors.some(function (e) {
        return e.field === "phone";
      })
    ) {
      const digits = normalizeHuPhoneDigits(phoneRaw);
      if (digits.length < 8 || digits.length > 9 || digits.charAt(0) === "0") {
        pushError(
          "phone",
          "Érvénytelen magyar telefonszám (pl. 06 30 123 4567).",
        );
      }
    }
    const postal_code = requireField(
      "postal_code",
      "irányítószám",
      p.postal_code,
      4,
      4,
      _HU_ZIP_RE,
      "Az irányítószám pontosan 4 számjegy legyen.",
    );
    const city = requireField(
      "city",
      "város",
      p.city,
      2,
      128,
      _CITY_RE,
      "A város formátuma érvénytelen.",
    );
    const street = requireField(
      "street",
      "utca",
      p.street,
      2,
      256,
      _STREET_RE,
      "Az utca formátuma érvénytelen.",
    );
    const house_number = requireField(
      "house_number",
      "házszám",
      p.house_number,
      1,
      32,
      _HOUSE_RE,
      "A házszám formátuma érvénytelen.",
    );
    let line2 = p.line2 != null ? String(p.line2).trim() : "";
    if (line2) {
      if (line2.length > 256)
        pushError("line2", "Az emelet/ajtó legfeljebb 256 karakter lehet.");
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
      "Az ország formátuma érvénytelen.",
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
    if (s.length < 2 || s.length > 128)
      return label + " 2–128 karakter legyen.";
    if (containsUnsafeMarkup(s) || !_NAME_RE.test(s)) {
      return label + " formátuma érvénytelen.";
    }
    return null;
  }

  function validateEmailField(value) {
    const s = value != null ? String(value).trim() : "";
    if (!s) return "Az e-mail megadása kötelező.";
    if (s.length > 320) return "Az e-mail túl hosszú.";
    if (containsUnsafeMarkup(s) || !_EMAIL_RE.test(s))
      return "Érvénytelen e-mail cím.";
    return null;
  }

  function validateCheckoutShippingAddressParts(parts, customerName) {
    const errors = [];
    const warnings = [];
    const p = normalizeProfileAddressObject(parts);
    const customer = customerName != null ? String(customerName).trim() : "";

    function pushError(field, message) {
      errors.push({ field: field, message: message });
    }

    function optionalName(value) {
      const s = value != null ? String(value).trim() : "";
      if (!s) return "";
      if (s.length < 2 || s.length > 128) {
        pushError("recipient_name", "Az átvevő neve 2–128 karakter legyen.");
        return s;
      }
      if (containsUnsafeMarkup(s) || !_NAME_RE.test(s)) {
        pushError(
          "recipient_name",
          "Az átvevő neve csak betűket és szóközt tartalmazhat.",
        );
      }
      return s;
    }

    const recipientInput = optionalName(p.recipient_name);
    let effectiveRecipient = recipientInput;
    if (!effectiveRecipient) {
      if (!customer) {
        pushError("customer_name", "A név megadása kötelező.");
      } else if (
        customer.length < 2 ||
        customer.length > 128 ||
        containsUnsafeMarkup(customer) ||
        !_NAME_RE.test(customer)
      ) {
        pushError("customer_name", "A név formátuma érvénytelen.");
      } else {
        effectiveRecipient = customer;
      }
    }

    const postal_code = (function () {
      const s = p.postal_code != null ? String(p.postal_code).trim() : "";
      if (!s) {
        pushError("postal_code", "Az irányítószám megadása kötelező.");
        return "";
      }
      if (!_HU_ZIP_RE.test(s)) {
        pushError(
          "postal_code",
          "Az irányítószám pontosan 4 számjegy legyen.",
        );
      }
      return s;
    })();

    const city = (function () {
      const s = p.city != null ? String(p.city).trim() : "";
      if (!s) {
        pushError("city", "A város megadása kötelező.");
        return "";
      }
      if (
        s.length < 2 ||
        s.length > 128 ||
        containsUnsafeMarkup(s) ||
        !_CITY_RE.test(s)
      ) {
        pushError("city", "A város formátuma érvénytelen.");
      }
      return s;
    })();

    const streetLine = (function () {
      let s = p.street != null ? String(p.street).trim() : "";
      if (!s && p.house_number) {
        s = String(p.house_number).trim();
      }
      if (!s) {
        pushError("street", "Az utca, házszám megadása kötelező.");
        return "";
      }
      if (
        s.length < 2 ||
        s.length > 256 ||
        containsUnsafeMarkup(s) ||
        !_STREET_RE.test(s)
      ) {
        pushError("street", "Az utca, házszám formátuma érvénytelen.");
      }
      return s;
    })();

    let line2 = p.line2 != null ? String(p.line2).trim() : "";
    if (line2) {
      if (line2.length > 256) {
        pushError("line2", "Az emelet/ajtó legfeljebb 256 karakter lehet.");
      } else if (containsUnsafeMarkup(line2) || !_LINE2_RE.test(line2)) {
        pushError("line2", "Az emelet/ajtó formátuma érvénytelen.");
      }
    } else {
      line2 = "";
    }

    if (postal_code && city && !errors.length) {
      const w = zipCityMismatchWarningHu(postal_code, city);
      if (w) warnings.push({ field: "city", message: w });
    }

    return {
      ok: errors.length === 0,
      errors: errors,
      warnings: warnings,
      normalized: {
        recipient_name: effectiveRecipient,
        phone: "",
        postal_code: postal_code,
        city: city,
        street: streetLine,
        house_number: "",
        line2: line2,
        country: "Magyarország",
      },
    };
  }

  function buildValidatedCheckoutShippingJson(parts, customerName) {
    const v = validateCheckoutShippingAddressParts(parts, customerName);
    if (!v.ok) {
      return { ok: false, errors: v.errors, warnings: v.warnings };
    }
    const json = serializeProfileAddressFromParts(v.normalized);
    if (!json) {
      return {
        ok: false,
        errors: [
          { field: null, message: "A szállítási cím megadása kötelező." },
        ],
        warnings: [],
      };
    }
    return {
      ok: true,
      json: json,
      warnings: v.warnings,
      normalized: v.normalized,
    };
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
        errors: [
          { field: null, message: "A szállítási cím megadása kötelező." },
        ],
        warnings: [],
      };
    }
    return {
      ok: true,
      json: json,
      warnings: v.warnings,
      normalized: v.normalized,
    };
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
    const streetLine = [p.street, p.house_number].filter(Boolean).join(" ").trim();
    const lines = [
      p.recipient_name,
      [p.postal_code, p.city].filter(Boolean).join(" "),
      streetLine,
    ];
    if (p.line2) lines.push(p.line2);
    if (p.country && p.country !== "Magyarország") lines.push(p.country);
    return lines.filter(Boolean).join("\n");
  }

  function formatShippingAddressPlainFromRaw(raw) {
    const parsed = parseProfileAddressRaw(raw);
    if (parsed.mode === "legacy")
      return parsed.parts.street || String(raw || "").trim();
    if (parsed.mode === "empty") return "";
    return formatShippingAddressPlainFromParts(parsed.parts);
  }

  function parseProfileAddressRaw(raw) {
    if (raw == null)
      return { mode: "empty", parts: emptyProfileAddressParts() };
    const s = String(raw).trim();
    if (!s) return { mode: "empty", parts: emptyProfileAddressParts() };
    if (s.startsWith("{")) {
      try {
        const o = JSON.parse(s);
        if (
          o &&
          typeof o === "object" &&
          (o.v === PROFILE_ADDRESS_JSON_V ||
            o.street != null ||
            o.postal_code != null)
        ) {
          return { mode: "json", parts: normalizeProfileAddressObject(o) };
        }
      } catch (_) {}
    }
    return {
      mode: "legacy",
      parts: Object.assign(emptyProfileAddressParts(), { street: s }),
    };
  }

  function profileAddressPartsFromInputs(prefix) {
    function gv(id) {
      const el = $(id);
      return el && el.value != null ? String(el.value).trim() : "";
    }
    if (prefix === "checkoutShip") {
      return {
        recipient_name: gv("checkoutShipName"),
        phone: "",
        postal_code: gv("checkoutShipZip"),
        city: gv("checkoutShipCity"),
        street: gv("checkoutShipStreetLine"),
        house_number: "",
        line2: gv("checkoutShipLine2"),
        country: "Magyarország",
      };
    }
    let phone = "";
    if (prefix === "profShip") {
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
    if (prefix === "checkoutShip") {
      const map = {
        recipient_name: "checkoutShipName",
        postal_code: "checkoutShipZip",
        city: "checkoutShipCity",
        line2: "checkoutShipLine2",
      };
      Object.keys(map).forEach(function (k) {
        const el = $(map[k]);
        if (el) el.value = parts[k] != null ? String(parts[k]) : "";
      });
      const lineEl = $("checkoutShipStreetLine");
      if (lineEl) {
        const street = parts.street != null ? String(parts.street).trim() : "";
        const house =
          parts.house_number != null ? String(parts.house_number).trim() : "";
        lineEl.value = [street, house].filter(Boolean).join(" ").trim();
      }
      return;
    }
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
      if (prefix === "profShip") {
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
    if (containsUnsafeMarkup(s))
      return "A telefonszám nem tartalmazhat HTML-t vagy szkriptet.";
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
  ns.address = {
    PROFILE_ADDRESS_JSON_V,
    emptyProfileAddressParts,
    containsUnsafeMarkup,
    normalizeProfileAddressObject,
    normalizeHuPhoneDigits,
    zipCityMismatchWarningHu,
    validateShippingAddressParts,
    validatePersonNameField,
    validateEmailField,
    buildValidatedShippingJson,
    buildValidatedCheckoutShippingJson,
    buildOptionalProfileAddressJson,
    formatShippingAddressPlainFromParts,
    formatShippingAddressPlainFromRaw,
    parseProfileAddressRaw,
    profileAddressPartsFromInputs,
    applyProfileAddressPartsToInputs,
    validatePhoneOnly,
    serializeProfileAddressFromParts,
  };
})();
