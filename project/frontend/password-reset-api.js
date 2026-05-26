/** Minimal JSON API helper for forgot/reset password pages (shop users, not admin). */
(() => {
  function humanizeError(status, data, rawText) {
    const detail =
      data && typeof data.detail === "string"
        ? data.detail.trim()
        : data && data.detail != null && !Array.isArray(data.detail)
          ? String(data.detail).trim()
          : "";
    if (detail && detail.length > 0 && detail.length < 400) return detail;
    if (status === 422) return "Valamelyik megadott adat nem megfelelő.";
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
    if (!res.ok) throw new Error(humanizeError(res.status, data, text));
    return data;
  }

  window.MesencsiPasswordResetApi = { api };
})();
