(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});

  function _get(storage, key) {
    if (
      window.Mesencsi &&
      window.Mesencsi.cookieConsent &&
      !window.Mesencsi.cookieConsent.storageAllowed(key)
    ) {
      return null;
    }
    try {
      return storage.getItem(key);
    } catch {
      return null;
    }
  }

  function _set(storage, key, value) {
    if (
      window.Mesencsi &&
      window.Mesencsi.cookieConsent &&
      !window.Mesencsi.cookieConsent.storageAllowed(key)
    ) {
      return false;
    }
    try {
      storage.setItem(key, String(value));
      return true;
    } catch {
      return false;
    }
  }

  function _remove(storage, key) {
    try {
      storage.removeItem(key);
      return true;
    } catch {
      return false;
    }
  }

  function getLocal(key) {
    return _get(window.localStorage, key);
  }
  function setLocal(key, value) {
    return _set(window.localStorage, key, value);
  }
  function removeLocal(key) {
    return _remove(window.localStorage, key);
  }

  function getSession(key) {
    return _get(window.sessionStorage, key);
  }
  function setSession(key, value) {
    return _set(window.sessionStorage, key, value);
  }
  function removeSession(key) {
    return _remove(window.sessionStorage, key);
  }

  function getJsonLocal(key) {
    const raw = getLocal(key);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  function setJsonLocal(key, value) {
    try {
      return setLocal(key, JSON.stringify(value));
    } catch {
      return false;
    }
  }

  ns.storage = ns.storage || {
    getLocal,
    setLocal,
    removeLocal,
    getSession,
    setSession,
    removeSession,
    getJsonLocal,
    setJsonLocal,
  };
})();
