/**
 * Public gallery list, pagination, and lightbox (Milestone 8d).
 */
(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const $ = ns.$ || ((id) => document.getElementById(id));
  const apiClient = ns.api || null;
  const notify = ns.notify || null;

  const GALLERY_PAGE_SIZE = 12;
  let galleryPublicPage = 1;
  let galleryLoadSeq = 0;
  let galleryLightboxState = { items: [], index: 0, page: 1, pages: 0, total: 0 };
  let galleryLightboxNavBusy = false;
  let galleryLightboxLastFocus = null;

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

  function friendlyBackendError() {
    if (deps.friendlyBackendError) return deps.friendlyBackendError();
    return "Most nem érjük el a boltot.";
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
    const descRaw =
      it && it.description && String(it.description).trim()
        ? String(it.description).trim()
        : "";
    const desc = descRaw
      ? '<p class="gallery-public-card__desc">' + escapeHtml(descRaw) + "</p>"
      : "";
    const imgBlock =
      '<div class="gallery-public-card__img-wrap"><img class="gallery-public-card__img" src="' +
      escapeHtml(imgUrl) +
      '" alt="" loading="lazy" decoding="async" onerror="var c=this.closest(\'article.gallery-public-card\');if(c)c.remove();" /></div>';
    const idxAttr =
      indexInPage != null && Number.isFinite(Number(indexInPage))
        ? ' data-gallery-index="' + Math.floor(Number(indexInPage)) + '"'
        : "";
    const clickable =
      ' class="gallery-public-card gallery-public-card--clickable" role="button" tabindex="0" data-gallery-img="' +
      escapeHtml(imgUrl) +
      '" data-gallery-title="' +
      escapeHtml(titleRaw) +
      '" data-gallery-desc="' +
      escapeHtml(descRaw) +
      '"' +
      idxAttr;
    return (
      "<article" +
      clickable +
      ">" +
      imgBlock +
      '<h3 class="gallery-public-card__title">' +
      title +
      "</h3>" +
      desc +
      "</article>"
    );
  }

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
    const descRaw =
      it && it.description && String(it.description).trim()
        ? String(it.description).trim()
        : "";
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
    const idx = Math.max(
      0,
      Math.min(st.items.length - 1, Math.floor(Number(index)) || 0),
    );
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
    if (
      galleryLightboxLastFocus &&
      typeof galleryLightboxLastFocus.focus === "function"
    ) {
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
    const data = await api(
      "/gallery?page=" + reqPage + "&page_size=" + GALLERY_PAGE_SIZE,
    );
    const items =
      data && Array.isArray(data.items)
        ? data.items.filter(galleryHasDisplayImage)
        : [];
    const total = data && data.total != null ? Number(data.total) : 0;
    let pages = data && data.pages != null ? Number(data.pages) : 0;
    if (!pages && total > 0)
      pages = Math.max(1, Math.ceil(total / GALLERY_PAGE_SIZE));
    const page = data && data.page != null ? Number(data.page) : reqPage;
    return { items: items, page: page, pages: pages, total: total };
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
      const pageBtn =
        ev.target && ev.target.closest
          ? ev.target.closest("[data-gallery-page]")
          : null;
      if (pageBtn && !pageBtn.disabled) {
        const p = parseInt(pageBtn.getAttribute("data-gallery-page"), 10);
        if (Number.isFinite(p) && p >= 1) {
          ev.preventDefault();
          ev.stopPropagation();
          void loadGalleryPublic(p, { fromPager: true });
        }
        return;
      }
      const card =
        ev.target && ev.target.closest
          ? ev.target.closest(".gallery-public-card--clickable")
          : null;
      if (!card) return;
      const idx = parseInt(card.getAttribute("data-gallery-index"), 10);
      openGalleryLightboxAtIndex(Number.isFinite(idx) ? idx : 0);
    });
    out.addEventListener("keydown", function (ev) {
      if (ev.key !== "Enter" && ev.key !== " ") return;
      const card =
        ev.target && ev.target.closest
          ? ev.target.closest(".gallery-public-card--clickable")
          : null;
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
      if (notify) notify.error(msg);
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

  function init(injectedDeps) {
    deps = injectedDeps || {};
  }

  ns.gallery = {
    ensureGallery,
    loadGalleryPublic,
    init,
  };
})();
