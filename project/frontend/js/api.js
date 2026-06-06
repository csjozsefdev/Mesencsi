(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const $ = ns.$ || ((id) => document.getElementById(id));

  function apiBase() {
    if (window.__MESENCsi_API_ORIGIN) return window.__MESENCsi_API_ORIGIN;
    const el = $("apiBase");
    const raw = (el && el.value ? String(el.value) : "")
      .replace(/\/$/, "")
      .trim();
    if (raw) return raw;
    const loc = window.location;
    if (loc.port === "5500") return `${loc.protocol}//127.0.0.1:8000`;
    return loc.origin;
  }

  function apiBaseFallbacks() {
    const base = apiBase();
    const fallbacks = [base];
    if (base !== "http://127.0.0.1:8000")
      fallbacks.push("http://127.0.0.1:8000");
    if (base !== "http://localhost:8000")
      fallbacks.push("http://localhost:8000");
    return fallbacks;
  }

  function friendlyBackendError() {
    return "Most nem érjük el a boltot. Nézd meg az internetet, vagy próbáld újra egy kicsit később.";
  }

  /** Human-readable Hungarian message from server response (not raw jargon). */
  function humanizeServerError(status, data, rawText) {
    const t = (rawText || "").toLowerCase();
    const detailStr =
      data && typeof data.detail === "string"
        ? data.detail
        : data && data.detail != null && !Array.isArray(data.detail)
          ? String(data.detail)
          : "";
    const detailIsList = Array.isArray(data && data.detail);

    if (
      detailStr &&
      detailStr.length > 0 &&
      detailStr.length < 400 &&
      !detailIsList
    ) {
      if (status >= 500 || status === 409 || status === 429) {
        return detailStr;
      }
    }

    if (status >= 500) {
      return "A bolt éppen nem tud válaszolni. Próbáld újra néhány perc múlva.";
    }

    if (
      detailStr &&
      detailStr.length > 0 &&
      detailStr.length < 400 &&
      !detailIsList
    ) {
      return detailStr;
    }

    if (status === 404) {
      if (/termék|product/i.test(detailStr + t))
        return "Nincs ilyen termék, vagy már nem kapható.";
      if (/rendelés|order/i.test(detailStr + t)) return "Nincs ilyen rendelés.";
      if (/galéria|gallery/i.test(detailStr + t))
        return "Nincs ilyen galériakép.";
      return "Nem találjuk, amit kértél — lehet, hogy már nem elérhető.";
    }
    if (status === 401 || status === 403) {
      if (detailStr && detailStr.length > 0 && detailStr.length < 400)
        return detailStr;
      return "Be kell jelentkezned, vagy lejárt a belépésed — jelentkezz be újra.";
    }
    if (status === 429) {
      if (detailStr && detailStr.length > 0 && detailStr.length < 400)
        return detailStr;
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
          if (
            loc.includes("items") &&
            (msg.includes("least") || msg.includes("min"))
          ) {
            return "Legalább egy termék kell a rendeléshez. Frissítsd az oldalt, és próbáld újra.";
          }
          if (loc.includes("quantity")) {
            return "A darabszámnak legalább 1-nek kell lennie.";
          }
        }
        return "Valamelyik mező hiányzik vagy hibás — nézd át az űrlapot.";
      }
      if (detailStr) {
        if (/page|oldal|galéri/i.test(detailStr))
          return "Érvénytelen oldalszám a galériánál. Nyisd meg újra a galériát.";
        return detailStr.length < 220
          ? detailStr
          : "A megadott adatok nem megfelelőek. Ellenőrizd a mezőket.";
      }
      return "A megadott adatok nem megfelelőek. Ellenőrizd a mezőket.";
    }
    if (status === 409) {
      if (detailStr && detailStr.length < 400) return detailStr;
      return "Ez most nem végezhető el — valami ütközik (pl. már van rá hivatkozás).";
    }
    if (status === 400)
      return "A kérés nem sikerült. Frissítsd az oldalt, és próbáld újra.";
    if (detailStr && detailStr.length < 220) return detailStr;
    return friendlyBackendError();
  }

  function readCsrfCookie() {
    try {
      const m = document.cookie.match(/(?:^|;\s*)mesencsi_csrf=([^;]*)/);
      return m ? decodeURIComponent(m[1].trim()) : "";
    } catch (_) {
      return "";
    }
  }

  function csrfHeaderValue() {
    const mem =
      typeof window.__MESENCSI_CSRF_TOKEN === "string"
        ? window.__MESENCSI_CSRF_TOKEN.trim()
        : "";
    if (mem) return mem;
    const fromCookie = readCsrfCookie();
    if (fromCookie) window.__MESENCSI_CSRF_TOKEN = fromCookie;
    return fromCookie;
  }

  function isCsrfForbidden(status, data, rawText) {
    if (status !== 403) return false;
    const detail =
      data && typeof data.detail === "string"
        ? data.detail
        : rawText || "";
    return /csrf/i.test(detail);
  }

  async function ensureCsrfToken() {
    if (csrfHeaderValue()) return true;
    return syncCsrfToken();
  }

  async function api(path, opts = {}) {
    const optsSafe = opts || {};
    const csrfRetry = !!optsSafe._csrfRetry;
    const fetchOpts = { ...optsSafe };
    delete fetchOpts._csrfRetry;

    const bases = apiBaseFallbacks();
    let res = null;
    let url = "";
    for (let i = 0; i < bases.length; i++) {
      url = bases[i] + path;
      try {
        const method = String(fetchOpts.method || "GET").toUpperCase();
        const headers = {
          Accept: "application/json",
          "Content-Type": "application/json",
          ...(fetchOpts.headers || {}),
        };
        if (method !== "GET" && method !== "HEAD") {
          if (!csrfHeaderValue()) await ensureCsrfToken();
          const csrf = csrfHeaderValue();
          if (csrf) headers["X-CSRF-Token"] = csrf;
        }
        res = await fetch(url, {
          ...fetchOpts,
          credentials: "include",
          headers: {
            ...headers,
          },
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
    if (
      !res.ok &&
      !csrfRetry &&
      isCsrfForbidden(res.status, data, text) &&
      (await syncCsrfToken())
    ) {
      return api(path, { ...optsSafe, _csrfRetry: true });
    }
    if (!res.ok) {
      const hu = humanizeServerError(res.status, data, text);
      throw new Error(hu);
    }
    return data;
  }

  /** Sync X-CSRF-Token with mesencsi_csrf cookie (required after login sets a new cookie). */
  async function syncCsrfToken() {
    try {
      const csrf = await api("/auth/csrf", { method: "GET" });
      if (csrf && csrf.csrf_token) {
        window.__MESENCSI_CSRF_TOKEN = String(csrf.csrf_token);
        return true;
      }
    } catch (_) {}
    return !!csrfHeaderValue();
  }

  async function apiMultipart(path, formData, bearerToken, opts) {
    const optsSafe = opts || {};
    const csrfRetry = !!optsSafe._csrfRetry;
    const bases = apiBaseFallbacks();
    let res = null;
    let url = "";
    const headers = { Accept: "application/json" };
    if (bearerToken) headers.Authorization = "Bearer " + bearerToken;
    else {
      if (!csrfHeaderValue()) await ensureCsrfToken();
      const csrf = csrfHeaderValue();
      if (csrf) headers["X-CSRF-Token"] = csrf;
    }
    for (let i = 0; i < bases.length; i++) {
      url = bases[i] + path;
      try {
        res = await fetch(url, {
          method: "POST",
          headers: headers,
          body: formData,
          credentials: "include",
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
    if (
      !res.ok &&
      !csrfRetry &&
      !bearerToken &&
      isCsrfForbidden(res.status, data, text) &&
      (await syncCsrfToken())
    ) {
      return apiMultipart(path, formData, bearerToken, { _csrfRetry: true });
    }
    if (!res.ok) {
      const hu = humanizeServerError(res.status, data, text);
      throw new Error(hu);
    }
    return data;
  }

  ns.api = {
    apiBase,
    apiBaseFallbacks,
    friendlyBackendError,
    humanizeServerError,
    api,
    syncCsrfToken,
    apiMultipart,
  };
})();
