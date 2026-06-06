/**
 * Digital storybooks catalog and spread-based public reader.
 */
(() => {
  const ns = (window.Mesencsi = window.Mesencsi || {});
  const $ = ns.$ || ((id) => document.getElementById(id));
  const apiClient = ns.api || null;
  const notify = ns.notify || null;
  const SBR = window.MesencsiStorybookReader;

  let storybooksCatalogLoaded = false;
  let storybookReaderState = {
    title: "",
    description: "",
    cover_url: "",
    pages: [],
    spreadIndex: 0,
    isPageTurning: false,
    turnDirection: null,
  };

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

  function storybookEls() {
    return {
      catalogOut: $("storybooksCatalogOut"),
      publicList: $("storybooksPublicList"),
      publicReader: $("storybooksPublicReader"),
      bookViewport: $("storybooksBookViewport"),
      readerOut: $("storybooksReaderOut"),
    };
  }

  function setStorybookImmersive(on) {
    const SBR2 = window.MesencsiStorybookReaderV2;
    if (SBR2 && SBR2.setV2Immersive) {
      SBR2.setV2Immersive(on);
    } else if (on) {
      console.error("[storybook-v2] missing V2 reader module");
    }
  }

  function showV2ReaderFailure(out, reason) {
    if (!out) return;
    const detail =
      reason === "missing-content"
        ? "A tartalom modul nem érhető el."
        : reason === "mount-failed"
          ? "A V2 olvasó felületét nem sikerült felépíteni."
          : "A V2 olvasó modul nem érhető el.";
    out.innerHTML =
      '<p class="empty" role="alert">A mesekönyv olvasó nem tölthető be. ' +
      escapeHtml(detail) +
      " Próbáld újra frissítéssel.</p>";
  }

  /** Clear #storybooksReaderOut (catalog return / new book). */
  function clearReaderOutForV2(out) {
    if (!out || !out.childNodes.length) return;
    out.innerHTML = "";
    try {
      out.removeAttribute("data-sbv2-nav-wired");
    } catch (_) {}
  }

  function shouldIgnoreV2HitClick(e) {
    const t = e.target;
    if (!t || !t.closest) return false;
    if (t.closest("[data-sbv2-zone]")) return false;
    return !!t.closest(
      "audio, .sb-read-audio-wrap, .sbv2-zone--audio, a[href], input, textarea, select, button:not([data-sbv2-zone])",
    );
  }

  function wireStorybookV2Nav(out) {
    if (!out || out.dataset.sbv2NavWired === "1") return;
    out.dataset.sbv2NavWired = "1";
    out.addEventListener("click", function (e) {
      if (shouldIgnoreV2HitClick(e)) return;
      const btn =
        e.target && e.target.closest ? e.target.closest("[data-sbv2-zone]") : null;
      if (!btn || btn.disabled || storybookReaderState.isPageTurning) return;
      const dir = btn.getAttribute("data-sbv2-zone");
      if (dir === "prev" || dir === "next") navigateStorybookSpread(dir);
    });
  }

  function v2ReaderModuleReady() {
    const SBR2 = window.MesencsiStorybookReaderV2;
    return !!(
      SBR2 &&
      typeof SBR2.mountV2ShellIfNeeded === "function" &&
      typeof SBR2.paintSpreadResting === "function" &&
      typeof SBR2.setV2Immersive === "function" &&
      typeof SBR2.runV2SpreadPageTurn === "function"
    );
  }

  function syncStorybookV2Nav(out) {
    const SBR2 = window.MesencsiStorybookReaderV2;
    if (!out || !SBR2 || typeof SBR2.syncV2NavState !== "function") return;
    const st = storybookReaderState;
    SBR2.syncV2NavState(out, {
      spreadIndex: st.spreadIndex,
      pages: st.pages || [],
      busy: st.isPageTurning,
    });
  }

  /**
   * V2: persistent shell; animated page turn when opts.direction + targetSpreadIndex.
   * @param {object} [opts] targetSpreadIndex, direction ("prev"|"next")
   * @returns {boolean}
   */
  function renderStorybookReaderV2(opts) {
    opts = opts || {};
    const out = storybookEls().readerOut;
    if (!out) {
      console.error("[storybook-v2] missing #storybooksReaderOut");
      return false;
    }
    if (!v2ReaderModuleReady()) {
      console.error("[storybook-v2] missing V2 reader module");
      showV2ReaderFailure(out, "missing-v2-module");
      return false;
    }
    const SBR2 = window.MesencsiStorybookReaderV2;
    if (!SBR) {
      console.error("[storybook-v2] missing content module (MesencsiStorybookReader)");
      showV2ReaderFailure(out, "missing-content");
      return false;
    }

    wireStorybookKeyboard();
    wireStorybookV2Nav(out);

    const st = storybookReaderState;
    const pages = st.pages || [];

    if (!pages.length) {
      clearReaderOutForV2(out);
      out.innerHTML =
        '<p class="empty" role="status">Nincs megjeleníthető oldal.</p>';
      return true;
    }

    const spreadIndex =
      typeof opts.targetSpreadIndex === "number"
        ? opts.targetSpreadIndex
        : st.spreadIndex;

    const renderResult = SBR2.runV2SpreadRender({
      mountEl: out,
      pages: pages,
      currentSpreadIndex: st.spreadIndex,
      targetSpreadIndex: spreadIndex,
      direction: opts.direction,
      panelOpts: panelOpts(),
      isAnimating: function () {
        return storybookReaderState.isPageTurning;
      },
      setAnimating: function (v) {
        setReaderBusy(v, v ? (opts.direction === "prev" ? "prev" : "next") : null);
      },
      onSpreadCommitted: function (newSpreadIndex) {
        storybookReaderState.spreadIndex = newSpreadIndex;
      },
      preloadAdjacent: function () {
        SBR.preloadSpreadImages(
          pages,
          storybookReaderState.spreadIndex,
          storybookAssetUrl,
        );
      },
      syncNav: function () {
        syncStorybookV2Nav(out);
      },
    });
    if (renderResult.reason === "mount-failed") {
      console.error("[storybook-v2] shell mount failed");
      showV2ReaderFailure(out, "mount-failed");
      return false;
    }
    return true;
  }

  function storybookAssetUrl(u) {
    if (!u) return "";
    const s = String(u).trim();
    if (/^https?:\/\//i.test(s)) return "";
    return s.startsWith("/") ? s : "/" + s;
  }

  function panelOpts() {
    return {
      escapeHtml: escapeHtml,
      assetUrl: storybookAssetUrl,
      layout: "mesencsi",
    };
  }

  function setReaderBusy(busy, direction) {
    storybookReaderState.isPageTurning = !!busy;
    storybookReaderState.turnDirection = busy ? direction || null : null;
  }

  function navigateStorybookSpread(direction) {
    if (storybookReaderState.isPageTurning || !SBR) return false;
    const pages = storybookReaderState.pages || [];
    const si = storybookReaderState.spreadIndex;
    let target = null;
    if (direction === "prev") {
      if (!SBR.canSpreadPrev(si)) return false;
      target = si - 1;
    } else if (direction === "next") {
      if (!SBR.canSpreadNext(si, pages)) return false;
      target = si + 1;
    } else {
      return false;
    }
    renderStorybookReader({
      direction: direction,
      targetSpreadIndex: target,
    });
    return true;
  }

  function wireStorybookKeyboard() {
    if (document.documentElement.dataset.sbBookKeyWired === "1") return;
    document.documentElement.dataset.sbBookKeyWired = "1";
    document.addEventListener("keydown", function (e) {
      const readerHost = storybookEls().publicReader;
      if (!readerHost || readerHost.hidden) return;
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      const tag = (e.target && e.target.tagName) || "";
      if (/^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(tag)) return;
      if (storybookReaderState.isPageTurning) return;
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        navigateStorybookSpread("prev");
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        navigateStorybookSpread("next");
      }
    });
  }

  /** @deprecated Use renderStorybookReaderV2 — V1 reader removed. */
  function renderStorybookReader(opts) {
    renderStorybookReaderV2(opts || {});
  }

  function showStorybookCatalogErrorPanel(els, message) {
    const el = els.catalogOut;
    const list = els.publicList;
    const reader = els.publicReader;
    const ro = els.readerOut;
    if (!el || !list || !reader) return;
    setStorybookImmersive(false);
    list.hidden = false;
    reader.hidden = true;
    if (ro) {
      clearReaderOutForV2(ro);
    }
    const safeMsg =
      message && String(message).trim()
        ? String(message).trim()
        : "A mesekönyv jelenleg nem tölthető be.";
    if (notify) notify.error(safeMsg);
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
        const row = Array.isArray(rows)
          ? rows.find((b) => b.id === legacyBookId)
          : null;
        if (!row || !String(row.slug || "").trim()) {
          throw new Error("legacy_resolve");
        }
        slugPart = String(row.slug).trim();
      } catch (e) {
        showStorybookCatalogErrorPanel(
          els,
          "A mesekönyv jelenleg nem tölthető be.",
        );
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
      const pages = (book.pages || [])
        .slice()
        .sort((a, b) => (a.page_index || 0) - (b.page_index || 0));
      const pageIdx = pages.length
        ? Math.max(0, Math.min(pageIndex - 1, pages.length - 1))
        : 0;
      if (!SBR || typeof SBR.spreadIndexForPageIndex !== "function") {
        console.warn("[storybook-v2] MesencsiStorybookReader unavailable");
        showStorybookCatalogErrorPanel(
          els,
          "A mesekönyv olvasója jelenleg nem tölthető be.",
        );
        return;
      }
      const spreadIndex = SBR.spreadIndexForPageIndex(pageIdx);
      storybookReaderState = {
        title: book.title || "",
        description: (book.description || "").trim(),
        cover_url: book.cover_image_url || "",
        pages,
        spreadIndex,
        isPageTurning: false,
        turnDirection: null,
      };
      list.hidden = true;
      reader.hidden = false;
      setStorybookImmersive(true);
      renderStorybookReader();
    } catch (e) {
      showStorybookCatalogErrorPanel(
        els,
        "A mesekönyv jelenleg nem tölthető be.",
      );
    }
  }

  async function ensureStorybooksCatalog() {
    const els = storybookEls();
    const el = els.catalogOut;
    const list = els.publicList;
    const reader = els.publicReader;
    if (!el || !list || !reader) return;
    setStorybookImmersive(false);
    list.hidden = false;
    reader.hidden = true;
    const ro = els.readerOut;
    if (ro) {
      clearReaderOutForV2(ro);
    }
    storybooksCatalogLoaded = false;
    el.innerHTML = '<p class="empty" role="status">Betöltés…</p>';
    try {
      const rows = await api("/storybooks");
      storybooksCatalogLoaded = true;
      if (!Array.isArray(rows) || !rows.length) {
        el.innerHTML =
          '<p class="empty" role="status">Jelenleg nincs közzétett mesekönyv.</p>';
        return;
      }
      el.innerHTML = rows
        .map((b) => {
          const slug = b.slug != null ? String(b.slug).trim() : "";
          const bid = Number(b.id);
          const idAttr = Number.isFinite(bid) ? String(bid) : "";
          const cover = b.cover_image_url
            ? storybookAssetUrl(b.cover_image_url)
            : "";
          const thumb = cover
            ? '<div class="product-card__thumb"><img src="' +
              escapeHtml(cover) +
              '" alt="" loading="lazy" decoding="async" onerror="this.style.display=\'none\'"/></div>'
            : '<div class="product-card__thumb" aria-hidden="true">📖</div>';
          const desc = b.description
            ? '<p class="desc">' +
              escapeHtml(String(b.description).slice(0, 200)) +
              "</p>"
            : "";
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
      showStorybookCatalogErrorPanel(
        els,
        "A mesekönyvek listája jelenleg nem tölthető be.",
      );
    }
  }

  function wireStorybookBackButton() {
    const btnStorybookBackList = $("btnStorybookBackList");
    if (!btnStorybookBackList || btnStorybookBackList.dataset.storybooksWired)
      return;
    btnStorybookBackList.dataset.storybooksWired = "1";
    btnStorybookBackList.addEventListener("click", () => {
      void ensureStorybooksCatalog();
    });
  }

  function init(injectedDeps) {
    deps = injectedDeps || {};
    wireStorybookBackButton();
  }

  ns.storybooks = {
    ensureStorybooksCatalog,
    openStorybookReader,
    storybookEls,
    init,
  };
})();
