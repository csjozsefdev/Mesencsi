/**
 * Webshop + catalog product grids (Milestone 9).
 */
(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const $ = ns.$ || ((id) => document.getElementById(id));
  const apiClient = ns.api || null;
  const notify = ns.notify || null;

  /** @type {Record<string, Function>} */
  let deps = {};

  function api(path, opts) {
    if (apiClient && apiClient.api) return apiClient.api(path, opts);
    throw new Error("Most nem érjük el a boltot.");
  }

  function escapeHtml(s) {
    if (deps.escapeHtml) return deps.escapeHtml(s);
    return String(s);
  }

  function formatPrice(n) {
    if (deps.formatPrice) return deps.formatPrice(n);
    return String(n);
  }

  function isLoggedIn() {
    return deps.isShopUserLoggedIn ? !!deps.isShopUserLoggedIn() : false;
  }

  function msgWebshopAuth() {
    return deps.MSG_WEBSHOP_AUTH || "A webshop használatához kérlek jelentkezz be.";
  }

  function msgPurchaseAuth() {
    return deps.MSG_PURCHASE_AUTH || "A vásárláshoz kérlek jelentkezz be.";
  }

  function msgEmptyPublic() {
    return deps.MSG_EMPTY_PUBLIC || "Jelenleg nincs megjeleníthető tartalom.";
  }

  function friendlyBackendError() {
    if (deps.friendlyBackendError) return deps.friendlyBackendError();
    return "Most nem érjük el a boltot.";
  }

  function addToCart(product) {
    if (deps.addToCart) return deps.addToCart(product);
  }

  const COMING_SOON_DEFAULT_MSG =
    "A webshop kínálata hamarosan megjelenik itt. Addig is böngéssz a hírek, a galéria és a mesekönyv részek között — köszönjük a türelmedet!";

  /** @type {Promise<{products_coming_soon?: boolean, products_coming_soon_message?: string | null}> | null} */
  let shopConfigPromise = null;

  async function fetchShopConfig() {
    if (!shopConfigPromise) {
      shopConfigPromise = api("/shop/config")
        .then(function (cfg) {
          return cfg && typeof cfg === "object" ? cfg : { products_coming_soon: false };
        })
        .catch(function () {
          return { products_coming_soon: false };
        });
    }
    return shopConfigPromise;
  }

  function buildComingSoonMarkup(customMessage) {
    const msg =
      customMessage && String(customMessage).trim()
        ? String(customMessage).trim()
        : COMING_SOON_DEFAULT_MSG;
    return (
      '<div class="shop-coming-soon" role="status">' +
      '<div class="shop-coming-soon__icon" aria-hidden="true">📚</div>' +
      "<h3 class=\"shop-coming-soon__title\">Hamarosan</h3>" +
      '<p class="shop-coming-soon__text">' +
      escapeHtml(msg) +
      "</p>" +
      "</div>"
    );
  }

  async function renderComingSoonIfNeeded(outEl) {
    if (!outEl) return false;
    const cfg = await fetchShopConfig();
    if (!cfg || !cfg.products_coming_soon) return false;
    outEl.innerHTML = buildComingSoonMarkup(cfg.products_coming_soon_message);
    return true;
  }

  function safeProductImageUrl(p) {
    if (p && typeof p.image_url === "string") {
      const t = p.image_url.trim();
      if (t && !/^https?:\/\//i.test(t) && t.startsWith("/")) return t;
    }
    return "";
  }

  function buildProductCardMarkup(p, shop) {
    const imgUrl = safeProductImageUrl(p);
    const thumb = imgUrl
      ? `<div class="product-card__thumb"><img src="${escapeHtml(imgUrl)}" alt="" loading="lazy" decoding="async" /></div>`
      : `<div class="product-card__thumb" aria-hidden="true">📦</div>`;
    const desc = (p.description && String(p.description).trim()) || "";
    const descBlock = desc ? `<p class="desc">${escapeHtml(desc)}</p>` : "";
    const extraClass = shop ? "" : " product-card--catalog";
    const browseNote = isLoggedIn()
      ? "Megrendeléshez használd a Webshop menüt."
      : msgPurchaseAuth();
    const footer = shop
      ? `<button type="button" class="btn-card btn-add-cart" data-id="${escapeHtml(String(p.id))}" data-name="${escapeHtml(p.name)}" data-price="${escapeHtml(String(p.price))}" data-description="${escapeHtml(desc)}">
            Kosárba
          </button>`
      : `<p class="product-card__browse-note">${escapeHtml(browseNote)}</p>`;
    return `
        <article class="product-card${extraClass}" data-product-id="${escapeHtml(String(p.id))}">
          ${thumb}
          <h3>${escapeHtml(p.name)}</h3>
          <p class="price">${escapeHtml(formatPrice(p.price))}</p>
          ${descBlock}
          ${footer}
        </article>`;
  }

  async function loadProducts() {
    const out = $("productsOut");
    if (!out) return;
    if (!isLoggedIn()) {
      out.innerHTML = '<p class="empty">' + escapeHtml(msgWebshopAuth()) + "</p>";
      return;
    }
    out.innerHTML = '<p class="empty">Betöltés…</p>';

    if (await renderComingSoonIfNeeded(out)) return;

    const list = await api("/products");
    if (!Array.isArray(list)) {
      throw new Error("Nem sikerült betölteni a termékeket. Próbáld újra.");
    }
    if (!list.length) {
      out.innerHTML =
        '<p class="empty" role="status">' +
        escapeHtml(msgEmptyPublic()) +
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
      if (el)
        el.innerHTML =
          '<p class="empty" role="alert">' + escapeHtml(msg) + "</p>";
      if (notify) notify.error(msg);
    }
  }

  async function loadProductsCatalogReadOnly() {
    const out = $("productsCatalogOut");
    if (!out) return;
    out.innerHTML = '<p class="empty">Betöltés…</p>';
    if (await renderComingSoonIfNeeded(out)) return;
    const list = await api("/products");
    if (!Array.isArray(list)) {
      throw new Error("Nem sikerült betölteni a termékeket. Próbáld újra.");
    }
    if (!list.length) {
      out.innerHTML =
        '<p class="empty" role="status">' +
        escapeHtml(msgEmptyPublic()) +
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
      if (el)
        el.innerHTML =
          '<p class="empty" role="alert">' + escapeHtml(msg) + "</p>";
      if (notify) notify.error(msg);
    }
  }

  function init(injectedDeps) {
    deps = injectedDeps || {};
  }

  ns.products = {
    ensureCatalog,
    ensureProductsCatalog,
    loadProducts,
    init,
  };
})();
