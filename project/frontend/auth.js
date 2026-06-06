(() => {
  // Admin auth uses HttpOnly cookies (set by POST /admin/login).
  // No tokens are stored in localStorage anymore.
  // Compatibility: some legacy admin code still calls auth.setToken/clearToken/getToken/getAuthHeaders.
  // These are now no-ops and must NOT store JWTs in localStorage.

  function getToken() {
    return "";
  }

  function setToken(_token) {
    // no-op (cookie auth)
  }

  function clearToken() {
    // no-op (cookie auth)
  }

  function getAuthHeaders() {
    return {};
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
    try {
      const csrf = await api("/auth/csrf", { method: "GET" });
      if (csrf && csrf.csrf_token) {
        window.__MESENCSI_CSRF_TOKEN = String(csrf.csrf_token);
        return true;
      }
    } catch (_) {}
    return !!csrfHeaderValue();
  }

  function humanizeAdminError(status, data, rawText) {
    const detail =
      data && typeof data.detail === "string"
        ? data.detail.trim()
        : data && data.detail != null && !Array.isArray(data.detail)
          ? String(data.detail).trim()
          : "";

    if (detail && detail.length > 0 && detail.length < 400) {
      return detail;
    }

    if (status === 401) return "Nem sikerült a belépés. Jelentkezz be újra.";
    if (status === 403) {
      if (isCsrfForbidden(status, data, rawText)) {
        return "CSRF hiba — frissítsd az oldalt, jelentkezz be újra, majd próbáld újra a feltöltést.";
      }
      return "Ehhez a művelethez nincs jogosultságod.";
    }
    if (status === 404) return "Nem található, amit kértél.";
    if (status === 422) {
      if (Array.isArray(data && data.detail)) return "Valamelyik megadott adat nem megfelelő.";
      return "Valamelyik megadott adat nem megfelelő.";
    }
    if (status === 413) return "A fájl túl nagy a szerver számára engedélyezett mérethez képest. Válassz kisebb fájlt.";
    if (status >= 500) return "A szolgáltatás átmenetileg nem érhető el. Próbáld újra később.";
    const low = (rawText || "").toLowerCase();
    if (low.includes("network") || low.includes("failed to fetch")) {
      return "Nem sikerült kapcsolódni. Ellenőrizd az internetet, és próbáld újra.";
    }
    return "Valami hiba történt. Próbáld újra.";
  }

  async function api(path, opts = {}) {
    const optsSafe = opts || {};
    const csrfRetry = !!optsSafe._csrfRetry;
    const fetchOpts = { ...optsSafe };
    delete fetchOpts._csrfRetry;
    let res;
    try {
      const method = String(fetchOpts.method || "GET").toUpperCase();
      const headers = {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(fetchOpts.headers || {}),
      };
      try {
        if (method !== "GET" && method !== "HEAD") {
          if (!csrfHeaderValue()) await ensureCsrfToken();
          const csrf = csrfHeaderValue();
          if (csrf) headers["X-CSRF-Token"] = csrf;
        }
      } catch (_) {}
      res = await fetch(path, {
        ...fetchOpts,
        credentials: "include",
        headers: {
          ...headers,
        },
      });
    } catch {
      throw new Error("Nem sikerült kapcsolódni. Ellenőrizd az internetet, és próbáld újra.");
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
      (await ensureCsrfToken())
    ) {
      return api(path, { ...optsSafe, _csrfRetry: true });
    }
    if (!res.ok) {
      throw new Error(humanizeAdminError(res.status, data, text));
    }
    return data;
  }

  /**
   * Multipart upload (gallery, storybook cover/page). Do not set Content-Type — browser sets boundary.
   * @param {string} path
   * @param {FormData} formData
   * @param {{ _csrfRetry?: boolean }} [opts]
   */
  async function uploadForm(path, formData, opts) {
    const optsSafe = opts || {};
    if (!csrfHeaderValue()) await ensureCsrfToken();
    const csrf = csrfHeaderValue();
    const headers = csrf ? { "X-CSRF-Token": csrf } : undefined;
    let res;
    try {
      res = await fetch(path, {
        method: "POST",
        credentials: "include",
        headers: headers,
        body: formData,
      });
    } catch {
      throw new Error("Nem sikerült kapcsolódni. Ellenőrizd az internetet, és próbáld újra.");
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
      !optsSafe._csrfRetry &&
      isCsrfForbidden(res.status, data, text) &&
      (await ensureCsrfToken())
    ) {
      return uploadForm(path, formData, { _csrfRetry: true });
    }
    if (!res.ok) {
      throw new Error(humanizeAdminError(res.status, data, text));
    }
    return data;
  }

  /**
   * Multipart upload via XMLHttpRequest — optional progress (0–100). Used by storybook admin uploads.
   * @param {string} path
   * @param {FormData} formData
   * @param {(pct: number) => void} [onProgress]
   * @param {{ _csrfRetry?: boolean }} [opts]
   */
  async function uploadFormWithProgress(path, formData, onProgress, opts) {
    const optsSafe = opts || {};
    if (!csrfHeaderValue()) await ensureCsrfToken();
    const csrf = csrfHeaderValue();

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", path);
      xhr.withCredentials = true;
      if (csrf) {
        try {
          xhr.setRequestHeader("X-CSRF-Token", csrf);
        } catch (_) {}
      }
      xhr.upload.onprogress = (ev) => {
        if (typeof onProgress === "function" && ev.lengthComputable && ev.total > 0) {
          onProgress(Math.min(100, Math.round((ev.loaded / ev.total) * 100)));
        }
      };
      xhr.onerror = () => {
        reject(new Error("Nem sikerült kapcsolódni. Ellenőrizd az internetet, és próbáld újra."));
      };
      xhr.onload = async () => {
        const text = xhr.responseText || "";
        let data = null;
        try {
          data = text ? JSON.parse(text) : null;
        } catch {
          data = text;
        }
        if (xhr.status < 200 || xhr.status >= 300) {
          if (
            !optsSafe._csrfRetry &&
            isCsrfForbidden(xhr.status, data, text) &&
            (await ensureCsrfToken())
          ) {
            try {
              const retryData = await uploadFormWithProgress(path, formData, onProgress, {
                _csrfRetry: true,
              });
              resolve(retryData);
              return;
            } catch (retryErr) {
              reject(retryErr);
              return;
            }
          }
          reject(new Error(humanizeAdminError(xhr.status, data, text)));
          return;
        }
        resolve(data);
      };
      xhr.send(formData);
    });
  }

  window.MesencsiAdminAuth = {
    getToken,
    setToken,
    clearToken,
    getAuthHeaders,
    api,
    uploadForm,
    uploadFormWithProgress,
  };
})();
