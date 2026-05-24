(() => {
  const TOKEN_KEY = "token";

  function getToken() {
    try {
      return localStorage.getItem(TOKEN_KEY) || "";
    } catch {
      return "";
    }
  }

  function setToken(token) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      // ignore
    }
  }

  function clearToken() {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      // ignore
    }
  }

  /** @returns {Record<string, string>} */
  function getAuthHeaders() {
    const t = getToken();
    if (!t) return {};
    return { Authorization: "Bearer " + t };
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
    if (status === 403) return "Ehhez a művelethez nincs jogosultságod.";
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
    let res;
    try {
      res = await fetch(path, {
        ...opts,
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          ...getAuthHeaders(),
          ...(opts.headers || {}),
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
    if (!res.ok) {
      throw new Error(humanizeAdminError(res.status, data, text));
    }
    return data;
  }

  /**
   * Multipart feltöltés (pl. galéria kép). Ne állíts Content-Type fejlécet — a böngésző állítja be a boundary-t.
   * @param {string} path
   * @param {FormData} formData
   */
  async function uploadForm(path, formData) {
    let res;
    try {
      res = await fetch(path, {
        method: "POST",
        headers: {
          ...getAuthHeaders(),
        },
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
    if (!res.ok) {
      throw new Error(humanizeAdminError(res.status, data, text));
    }
    return data;
  }

  /**
   * Multipart feltöltés XMLHttpRequest-tel — opcionális progress (0–100).
   * @param {string} path
   * @param {FormData} formData
   * @param {(pct: number) => void} [onProgress]
   */
  function uploadFormWithProgress(path, formData, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", path);
      const headers = getAuthHeaders();
      Object.keys(headers).forEach((k) => {
        xhr.setRequestHeader(k, headers[k]);
      });
      xhr.upload.onprogress = (ev) => {
        if (typeof onProgress === "function" && ev.lengthComputable && ev.total > 0) {
          onProgress(Math.min(100, Math.round((ev.loaded / ev.total) * 100)));
        }
      };
      xhr.onerror = () => {
        reject(new Error("Nem sikerült kapcsolódni. Ellenőrizd az internetet, és próbáld újra."));
      };
      xhr.onload = () => {
        const text = xhr.responseText || "";
        let data = null;
        try {
          data = text ? JSON.parse(text) : null;
        } catch {
          data = text;
        }
        if (xhr.status < 200 || xhr.status >= 300) {
          reject(new Error(humanizeAdminError(xhr.status, data, text)));
          return;
        }
        resolve(data);
      };
      xhr.send(formData);
    });
  }

  window.MesencsiAdminAuth = {
    TOKEN_KEY,
    getToken,
    setToken,
    clearToken,
    getAuthHeaders,
    api,
    uploadForm,
    uploadFormWithProgress,
  };
})();
