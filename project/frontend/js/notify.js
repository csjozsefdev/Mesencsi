/**
 * Shared toast + async action feedback for Mesencsi shop and admin.
 */
(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const DEFAULT_MS = 4200;
  const LOADING_MS = 60000;

  /** @type {Map<string, { el: HTMLElement, timer: number }>} */
  const active = new Map();
  let seq = 0;

  function stackEl() {
    let el = document.getElementById("mesencsiToastStack");
    if (!el) {
      el = document.createElement("div");
      el.id = "mesencsiToastStack";
      el.className = "mesencsi-toast-stack";
      el.setAttribute("aria-live", "polite");
      el.setAttribute("aria-relevant", "additions");
      document.body.appendChild(el);
    }
    return el;
  }

  function kindClass(kind) {
    if (kind === "ok" || kind === "success") return "mesencsi-toast--ok";
    if (kind === "err" || kind === "error") return "mesencsi-toast--err";
    if (kind === "warn") return "mesencsi-toast--warn";
    if (kind === "loading") return "mesencsi-toast--loading";
    return "mesencsi-toast--info";
  }

  function dismiss(id) {
    const row = active.get(id);
    if (!row) return;
    clearTimeout(row.timer);
    row.el.classList.remove("is-visible");
    const remove = function () {
      if (row.el.parentNode) row.el.parentNode.removeChild(row.el);
    };
    row.el.addEventListener("transitionend", remove, { once: true });
    setTimeout(remove, 400);
    active.delete(id);
  }

  function push(kind, message, opts) {
    const optsSafe = opts || {};
    const text = message != null ? String(message).trim() : "";
    if (!text) return null;

    const id = "t" + ++seq;
    const stack = stackEl();
    const el = document.createElement("div");
    el.className = "mesencsi-toast " + kindClass(kind);
    el.setAttribute("role", kind === "loading" ? "status" : "alert");
    el.textContent = text;
    stack.appendChild(el);
    requestAnimationFrame(function () {
      el.classList.add("is-visible");
    });

    const ms =
      optsSafe.durationMs != null
        ? optsSafe.durationMs
        : kind === "loading"
          ? LOADING_MS
          : DEFAULT_MS;
    const timer = window.setTimeout(function () {
      dismiss(id);
    }, ms);
    active.set(id, { el, timer });
    return { id: id, dismiss: function () { dismiss(id); } };
  }

  function messageFromError(err, fallback) {
    if (err && err.message) return String(err.message);
    const api = ns.api;
    if (api && typeof api.friendlyBackendError === "function")
      return api.friendlyBackendError();
    return fallback || "Hiba történt. Próbáld újra.";
  }

  /** Mirrors auth inline status (ok / warn / err). */
  function inline(el, text, ok) {
    if (!el) return;
    const t = text != null ? String(text) : "";
    if (!t) {
      el.textContent = "";
      el.className = el.classList.contains("auth-msg")
        ? "auth-msg"
        : el.classList.contains("msg")
          ? "msg"
          : el.classList.contains("status")
            ? "status"
            : "status";
      if (el.hidden !== undefined) el.hidden = true;
      return;
    }
    if (el.hidden !== undefined) el.hidden = false;
    el.textContent = t;
    if (el.classList.contains("auth-msg")) {
      el.className =
        "auth-msg" +
        (ok === true ? " ok" : ok === "warn" ? " warn" : ok === false ? " err" : "");
      return;
    }
    if (el.classList.contains("msg")) {
      el.className = "msg " + (ok === true ? "ok" : ok === false ? "err" : "");
      el.style.display = "";
      return;
    }
    el.className = "status " + (ok === true ? "ok" : ok === false ? "err" : "");
  }

  function inlineAndToast(el, text, ok) {
    inline(el, text, ok);
    const t = text != null ? String(text).trim() : "";
    if (!t || ok === null) return;
    if (ok === true) success(t);
    else if (ok === "warn") warn(t);
    else if (ok === false) error(t);
  }

  function success(message, opts) {
    return push("ok", message, opts);
  }

  function error(message, opts) {
    return push("err", message, opts);
  }

  function warn(message, opts) {
    return push("warn", message, opts);
  }

  function info(message, opts) {
    return push("info", message, opts);
  }

  function loading(message, opts) {
    return push("loading", message, opts);
  }

  /**
   * Run async work with optional button busy state and feedback.
   * @param {object} opts
   */
  async function run(opts) {
    const o = opts || {};
    const btn =
      typeof o.button === "string"
        ? document.getElementById(o.button)
        : o.button || null;
    const inlineEl = o.inlineEl || null;
    const prevDisabled = btn ? btn.disabled : false;
    const prevText = btn ? btn.textContent : "";
    const prevBusy = btn ? btn.getAttribute("aria-busy") : null;
    let loadingHandle = null;

    try {
      if (btn) {
        btn.disabled = true;
        btn.setAttribute("aria-busy", "true");
        if (o.loadingText) btn.textContent = o.loadingText;
      }
      if (o.loadingMessage) {
        loadingHandle = loading(o.loadingMessage, { durationMs: LOADING_MS });
      } else if (inlineEl && o.loadingInline) {
        inline(inlineEl, o.loadingInline, null);
      }
      const result = await o.fn();
      if (loadingHandle) loadingHandle.dismiss();
      if (o.success != null && String(o.success).trim()) {
        if (o.toastOnly) success(o.success);
        else inlineAndToast(inlineEl, o.success, true);
      }
      if (typeof o.onSuccess === "function") o.onSuccess(result);
      return result;
    } catch (err) {
      if (loadingHandle) loadingHandle.dismiss();
      const msg = messageFromError(err, o.errorFallback || "Nem sikerült.");
      if (o.toastOnly) error(msg);
      else inlineAndToast(inlineEl, msg, false);
      if (typeof o.onError === "function") o.onError(err);
      throw err;
    } finally {
      if (btn) {
        btn.disabled = prevDisabled;
        if (prevBusy == null) btn.removeAttribute("aria-busy");
        else btn.setAttribute("aria-busy", prevBusy);
        if (o.loadingText) btn.textContent = prevText;
      }
    }
  }

  /** Admin-compatible: true = ok, false = err, else info. */
  function toast(text, kind) {
    if (kind === true) return success(text);
    if (kind === false) return error(text);
    return info(text);
  }

  ns.notify = {
    success,
    error,
    warn,
    info,
    loading,
    dismiss,
    push,
    toast,
    inline,
    inlineAndToast,
    messageFromError,
    run,
  };
})();
