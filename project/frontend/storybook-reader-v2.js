/**

 * Storybook Reader V2 — isolated fullscreen open-book shell (sbv2-*).

 * Content helpers reused from MesencsiStorybookReader; no V1 layout/flip.

 */

(function () {

  "use strict";

  const PAGE_TURN_MS = 1000;

  const PAGE_TURN_MS_REDUCED = 400;

  function contentApi() {

    return window.MesencsiStorybookReader || null;

  }



  function pauseAudioInMount(mountEl) {

    const SBR = contentApi();

    if (SBR && typeof SBR.pauseAudioInBook === "function") {

      SBR.pauseAudioInBook(mountEl);

      return;

    }

    if (!mountEl) return;

    mountEl.querySelectorAll("audio").forEach(function (a) {

      try {

        a.pause();

      } catch (_) {}

    });

  }



  function buildEndPaperHtml() {

    return (

      '<div class="sbv2-page__end-paper" aria-hidden="true">' +

      '<span class="sbv2-page__end-paper-label">—</span></div>'

    );

  }

  function buildV2HitLayerHtml() {
    return (
      '<div class="sbv2-hit-layer" role="group" aria-label="Lapozás">' +
      '<button type="button" class="sbv2-hit-zone sbv2-hit-zone--prev" data-sbv2-zone="prev" aria-label="Előző oldal"></button>' +
      '<button type="button" class="sbv2-hit-zone sbv2-hit-zone--next" data-sbv2-zone="next" aria-label="Következő oldal"></button>' +
      "</div>"
    );
  }

  /** Backward-compat: inject hit layer when shell predates spread edge zones. */
  function ensureV2HitLayerOnSpread(spreadEl) {
    if (!spreadEl || spreadEl.querySelector(".sbv2-hit-layer")) return;
    spreadEl.insertAdjacentHTML("beforeend", buildV2HitLayerHtml());
  }

  function buildV2FlipLayerHtml() {
    return (
      '<div class="sbv2-page-flip" hidden aria-hidden="true">' +
      '<div class="sbv2-page-flip__backing" aria-hidden="true"></div>' +
      '<div class="sbv2-page-flip__inner">' +
      '<div class="sbv2-page-flip__front">' +
      '<div class="sbv2-page__content"></div></div>' +
      '<div class="sbv2-page-flip__back">' +
      '<div class="sbv2-page__content"></div></div>' +
      "</div></div>"
    );
  }

  /** 3D turn kick: reflow then CSS class drives transform. */
  function startV2InnerTurn(inner, turnClass) {
    if (!inner || !turnClass) return;
    inner.classList.remove(
      "sbv2-page-flip__inner--turn-next",
      "sbv2-page-flip__inner--turn-prev"
    );
    inner.style.transition = "none";
    inner.style.animation = "none";
    inner.style.transform = "rotateY(0deg)";
    void inner.offsetWidth;
    inner.style.transition = "";
    inner.style.animation = "";
    inner.style.transform = "";
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        inner.classList.add(turnClass);
      });
    });
  }

  /** Backward-compat: inject flip layer when shell predates page-flip overlay. */
  function ensureV2FlipLayerOnSpread(spreadEl) {
    if (!spreadEl) return;
    const flip = spreadEl.querySelector(".sbv2-page-flip");
    if (!flip) {
      const hit = spreadEl.querySelector(".sbv2-hit-layer");
      if (hit) {
        hit.insertAdjacentHTML("beforebegin", buildV2FlipLayerHtml());
      } else {
        spreadEl.insertAdjacentHTML("beforeend", buildV2FlipLayerHtml());
      }
      return;
    }
    if (!flip.querySelector(".sbv2-page-flip__backing")) {
      flip.insertAdjacentHTML(
        "afterbegin",
        '<div class="sbv2-page-flip__backing" aria-hidden="true"></div>'
      );
    }
  }

  /** Resolve host/viewport/output roots — public shop and admin preview use different IDs. */
  var V2_HOST_IDS = ["storybooksPublicReader", "sbReaderRoot"];
  var V2_VIEWPORT_IDS = ["storybooksBookViewport", "sbReaderViewport"];
  var V2_READER_OUT_IDS = ["storybooksReaderOut", "sbReaderMount"];

  function firstElementById(ids) {
    for (var i = 0; i < ids.length; i++) {
      var el = document.getElementById(ids[i]);
      if (el) return el;
    }
    return null;
  }

  function firstElementByIdsInRoot(root, ids) {
    if (!root || !root.querySelector) return null;
    for (var j = 0; j < ids.length; j++) {
      var found = root.querySelector("#" + ids[j]);
      if (found) return found;
    }
    return null;
  }

  function resolveV2ReaderRoots(opts) {
    opts = opts || {};
    const mountEl = opts.readerOutEl || opts.mountEl || null;
    let host = opts.hostEl || null;
    let viewport = opts.viewportEl || null;
    let readerOut = opts.readerOutEl || mountEl || null;

    if (!host && mountEl && mountEl.closest) {
      host = mountEl.closest(".storybook-v2-root");
    }
    if (!host) {
      host = firstElementById(V2_HOST_IDS);
    }
    if (!viewport && host) {
      viewport =
        firstElementByIdsInRoot(host, V2_VIEWPORT_IDS) ||
        host.querySelector(".sbv2-viewport");
    }
    if (!viewport) {
      viewport = firstElementById(V2_VIEWPORT_IDS);
    }
    if (!readerOut && viewport) {
      readerOut = firstElementByIdsInRoot(viewport, V2_READER_OUT_IDS);
    }
    if (!readerOut) {
      readerOut = firstElementById(V2_READER_OUT_IDS);
    }
    return { host: host, viewport: viewport, readerOut: readerOut };
  }

  function setV2SpreadPageTurnMode(els, on, rootsOpts) {
    const active = !!on;
    if (els && els.spread) {
      const pageTurnClassTargets = [
        [els.spread, "sbv2-spread--page-turn"],
        [els.spread.closest ? els.spread.closest(".sbv2-cover") : null, "sbv2-cover--page-turn"],
        [els.spread.closest ? els.spread.closest(".sbv2-open-book") : null, "sbv2-open-book--page-turn"],
        [els.spread.closest ? els.spread.closest(".sbv2-book-frame") : null, "sbv2-book-frame--page-turn"],
        [els.spread.closest ? els.spread.closest(".sbv2-stage") : null, "sbv2-stage--page-turn"],
        [els.spread.closest ? els.spread.closest(".sbv2-reader") : null, "sbv2-reader--page-turn"],
      ];
      pageTurnClassTargets.forEach(function (pair) {
        if (pair[0]) pair[0].classList.toggle(pair[1], active);
      });
    }
    const roots = resolveV2ReaderRoots(
      Object.assign({}, rootsOpts || {}, {
        readerOutEl:
          (rootsOpts && rootsOpts.readerOutEl) ||
          (els && els.reader && els.reader.parentElement) ||
          null,
      }),
    );
    if (roots.host) roots.host.classList.toggle("storybook-v2-root--page-turn", active);
    if (roots.readerOut) roots.readerOut.classList.toggle("sbv2-reader-out--page-turn", active);
    if (roots.viewport) roots.viewport.classList.toggle("sbv2-viewport--page-turn", active);
  }

  function resetV2FlipState(els, mountEl) {
    if (!els || !els.flip || !els.flipInner) return;
    const rootsMount =
      mountEl || (els && els.reader && els.reader.parentElement) || null;
    setV2SpreadPageTurnMode(els, false, { readerOutEl: rootsMount });
    els.flip.hidden = true;
    els.flip.setAttribute("aria-hidden", "true");
    els.flip.classList.remove(
      "sbv2-page-flip--from-right",
      "sbv2-page-flip--from-left",
      "sbv2-page-flip--is-active"
    );
    els.flipInner.classList.remove(
      "sbv2-page-flip__inner--turn-next",
      "sbv2-page-flip__inner--turn-prev"
    );
    els.flipInner.style.transform = "";
    els.flipInner.style.transition = "";
    els.flipInner.style.animation = "";
    els.flip.style.removeProperty("--sbv2-turn-ms");
    if (els.flipFrontContent) els.flipFrontContent.innerHTML = "";
    if (els.flipBackContent) els.flipBackContent.innerHTML = "";
  }

  /**

   * Fullscreen open-book shell (.sbv2-page-flip sits above pages, below hit layer).

   */

  function buildV2ShellHtml() {

    return (

      '<div class="sbv2-reader">' +

      '<p class="sbv2-spread-indicator" aria-live="polite"></p>' +

      '<div class="sbv2-stage">' +

      '<div class="sbv2-scaler">' +

      '<div class="sbv2-open-book">' +

      '<div class="sbv2-book-shadow" aria-hidden="true"></div>' +

      '<div class="sbv2-book-frame">' +

      '<div class="sbv2-cover">' +

      '<div class="sbv2-page-effects" aria-hidden="true">' +

      '<span class="sbv2-page-edge sbv2-page-edge--top"></span>' +

      '<span class="sbv2-page-edge sbv2-page-edge--bottom"></span>' +

      '<span class="sbv2-page-edge sbv2-page-edge--left"></span>' +

      '<span class="sbv2-page-edge sbv2-page-edge--right"></span>' +

      "</div>" +

      '<div class="sbv2-book-spread sbv2-spread">' +

      '<div class="sbv2-page sbv2-page--left">' +

      '<div class="sbv2-page__content"></div></div>' +

      '<div class="sbv2-spine" aria-hidden="true"></div>' +

      '<div class="sbv2-page sbv2-page--right">' +

      '<div class="sbv2-page__content"></div></div>' +

      buildV2FlipLayerHtml() +

      buildV2HitLayerHtml() +

      "</div></div></div></div></div></div></div>"

    );

  }



  /**

   * Mount shell once per reader session (#storybooksReaderOut must be empty or stale).

   * @returns {HTMLElement|null} .sbv2-reader

   */

  function mountV2ShellIfNeeded(mountEl) {

    if (!mountEl) return null;

    let readerRoot = mountEl.querySelector(".sbv2-reader");

    if (readerRoot) {
      const spread = readerRoot.querySelector(".sbv2-spread");
      ensureV2FlipLayerOnSpread(spread);
      ensureV2HitLayerOnSpread(spread);
      return readerRoot;
    }

    mountEl.innerHTML = buildV2ShellHtml();

    readerRoot = mountEl.querySelector(".sbv2-reader");

    const spread = readerRoot && readerRoot.querySelector(".sbv2-spread");
    ensureV2FlipLayerOnSpread(spread);
    ensureV2HitLayerOnSpread(spread);

    return readerRoot;

  }



  function getV2Elements(readerRoot) {

    if (!readerRoot) return null;

    const root = readerRoot.querySelector

      ? readerRoot.querySelector(".sbv2-reader") || readerRoot

      : readerRoot;

    if (!root || !root.querySelector) return null;

    return {

      reader: root,

      ind: root.querySelector(".sbv2-spread-indicator"),

      leftContent: root.querySelector(".sbv2-page--left .sbv2-page__content"),

      rightContent: root.querySelector(".sbv2-page--right .sbv2-page__content"),

      spread: root.querySelector(".sbv2-book-spread.sbv2-spread, .sbv2-spread"),

      flip: root.querySelector(".sbv2-page-flip"),

      flipInner: root.querySelector(".sbv2-page-flip__inner"),

      flipFront: root.querySelector(".sbv2-page-flip__front"),

      flipBack: root.querySelector(".sbv2-page-flip__back"),

      flipFrontContent: root.querySelector(".sbv2-page-flip__front .sbv2-page__content"),

      flipBackContent: root.querySelector(".sbv2-page-flip__back .sbv2-page__content"),

      hitLayer: root.querySelector(".sbv2-hit-layer"),

    };

  }



  function paintPageSlot(el, page, panelOpts, side, spreadMeta) {

    const SBR = contentApi();

    if (!el) return;

    if (!page) {

      el.innerHTML = buildEndPaperHtml();

      el.classList.remove("sbv2-page__content--standard-spread");

      return;

    }

    const opts = panelOpts || {};

    spreadMeta = spreadMeta || {};

    const ctx = {

      pageNumber:

        side === "right"

          ? spreadMeta.rightPageNumber

          : spreadMeta.leftPageNumber,

      opts: opts,

    };

    if (side === "left" && SBR && typeof SBR.buildV2LeftPageHtml === "function") {

      el.innerHTML = SBR.buildV2LeftPageHtml(page, ctx);

      el.classList.add("sbv2-page__content--standard-spread");

      return;

    }

    if (side === "right" && SBR && typeof SBR.buildV2RightPageHtml === "function") {

      el.innerHTML = SBR.buildV2RightPageHtml(page, ctx);

      el.classList.add("sbv2-page__content--standard-spread");

      return;

    }

    if (SBR && typeof SBR.buildPanelHtml === "function") {

      el.innerHTML = SBR.buildPanelHtml(page, opts);

    } else {

      el.innerHTML = '<p class="empty">—</p>';

    }

    el.classList.remove("sbv2-page__content--standard-spread");

  }



  function spreadMetaFromSpread(spread) {

    spread = spread || { leftIndex: -1, rightIndex: -1 };

    return {

      leftPageNumber: spread.leftIndex >= 0 ? spread.leftIndex + 1 : 0,

      rightPageNumber: spread.rightIndex >= 0 ? spread.rightIndex + 1 : 0,

    };

  }



  function prefersReducedMotion() {

    try {

      return window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    } catch (_) {

      return false;

    }

  }

  function getPageTurnMs() {

    return prefersReducedMotion() ? PAGE_TURN_MS_REDUCED : PAGE_TURN_MS;

  }



  /**

   * Repaint resting spread only (no shell recreate).

   * @returns {HTMLElement|null} .sbv2-reader

   */

  function paintSpreadResting(mountEl, pages, spreadIndex, panelOpts) {

    const SBR = contentApi();

    if (!mountEl) return null;

    const readerRoot = mountEl.querySelector(".sbv2-reader");

    if (!readerRoot) return null;



    pauseAudioInMount(mountEl);



    const els = getV2Elements(mountEl);

    if (!els) return readerRoot;



    const si = Math.max(0, Math.floor(Number(spreadIndex) || 0));

    const spread =

      SBR && typeof SBR.pagesForSpread === "function"

        ? SBR.pagesForSpread(pages, si)

        : { left: null, right: null, leftIndex: -1, rightIndex: -1 };



    const spreadMeta = spreadMetaFromSpread(spread);

    paintPageSlot(els.leftContent, spread.left, panelOpts, "left", spreadMeta);

    paintPageSlot(els.rightContent, spread.right, panelOpts, "right", spreadMeta);



    if (els.ind && SBR && typeof SBR.formatSpreadIndicator === "function") {
      els.ind.textContent = SBR.formatSpreadIndicator(si, pages);
    }

    resetV2FlipState(els, mountEl);

    return readerRoot;

  }



  /**

   * Enable/disable prev/next hit zones on .sbv2-hit-layer.

   * @param {HTMLElement} mountEl

   * @param {{ spreadIndex: number, pages: object[], busy?: boolean }} state

   */

  function syncV2NavState(mountEl, state) {

    if (!mountEl) return;

    const SBR = contentApi();

    const pages = (state && state.pages) || [];

    const si = Math.floor(Number(state && state.spreadIndex) || 0);

    const busy = !!(state && state.busy);

    const atStart = SBR && typeof SBR.canSpreadPrev === "function" ? !SBR.canSpreadPrev(si) : true;

    const atEnd =

      SBR && typeof SBR.canSpreadNext === "function"

        ? !SBR.canSpreadNext(si, pages)

        : true;

    const layer = mountEl.querySelector(".sbv2-hit-layer");

    if (!layer) return;

    const prevZones = layer.querySelectorAll('[data-sbv2-zone="prev"]');

    const nextZones = layer.querySelectorAll('[data-sbv2-zone="next"]');

    prevZones.forEach(function (el) {
      const off = atStart || busy;
      el.disabled = off;
      el.setAttribute("aria-disabled", off ? "true" : "false");
    });

    nextZones.forEach(function (el) {
      const off = atEnd || busy;
      el.disabled = off;
      el.setAttribute("aria-disabled", off ? "true" : "false");
    });

    layer.classList.toggle("sbv2-hit-layer--busy", busy);

    layer.classList.toggle("sbv2-hit-layer--at-start", atStart);

    layer.classList.toggle("sbv2-hit-layer--at-end", atEnd);

  }



  /**

   * 3D page turn between spreads. Commits target spread only after animation ends.

   */

  function runV2SpreadPageTurn(opts) {

    opts = opts || {};

    const mountEl = opts.mountEl;

    const pages = opts.pages || [];

    const direction = opts.direction === "prev" ? "prev" : "next";

    const currentSpreadIndex = Math.floor(Number(opts.currentSpreadIndex) || 0);

    const panelOpts = opts.panelOpts || {};

    const targetSpreadIndex =

      direction === "next" ? currentSpreadIndex + 1 : currentSpreadIndex - 1;



    function finish() {

      if (typeof opts.setAnimating === "function") opts.setAnimating(false);

      if (typeof opts.preloadAdjacent === "function") opts.preloadAdjacent();

      if (typeof opts.onDone === "function") opts.onDone();

    }



    const SBR = contentApi();

    const maxSpread =
      SBR && typeof SBR.spreadCount === "function" ? SBR.spreadCount(pages) : 0;
    if (targetSpreadIndex < 0 || targetSpreadIndex >= maxSpread) {
      finish();
      return;
    }

    const els = getV2Elements(mountEl);

    if (!els || !els.flip || !els.flipInner || !els.flipFrontContent || !els.flipBackContent) {
      // Graceful skip when flip layer is missing (instant commit, no animation).
      if (typeof opts.onSpreadCommitted === "function") opts.onSpreadCommitted(targetSpreadIndex);

      paintSpreadResting(mountEl, pages, targetSpreadIndex, panelOpts);

      finish();

      return;

    }



    if (typeof opts.setAnimating === "function") opts.setAnimating(true);

    pauseAudioInMount(mountEl);



    const current =

      SBR && typeof SBR.pagesForSpread === "function"

        ? SBR.pagesForSpread(pages, currentSpreadIndex)

        : { left: null, right: null, leftIndex: -1, rightIndex: -1 };

    const target =

      SBR && typeof SBR.pagesForSpread === "function"

        ? SBR.pagesForSpread(pages, targetSpreadIndex)

        : { left: null, right: null, leftIndex: -1, rightIndex: -1 };



    const turnMs = getPageTurnMs();

    // Optional debug: set localStorage.debugStorybookV2 = "1" to log page-turn timing.
    if (
      typeof localStorage !== "undefined" &&
      localStorage.getItem("debugStorybookV2") === "1"
    ) {
      console.log(
        "[storybook-v2] page turn animating",
        direction,
        turnMs < PAGE_TURN_MS ? "(reduced duration " + turnMs + "ms)" : ""
      );
    }



    let finished = false;
    let fallback = 0;

    function doneOnce() {

      if (finished) return;

      finished = true;

      els.flipInner.removeEventListener("animationend", onTurnEnd);

      window.clearTimeout(fallback);

      resetV2FlipState(els, mountEl);

      if (typeof opts.onSpreadCommitted === "function") opts.onSpreadCommitted(targetSpreadIndex);

      paintSpreadResting(mountEl, pages, targetSpreadIndex, panelOpts);

      finish();

    }



    resetV2FlipState(els, mountEl);

    setV2SpreadPageTurnMode(els, true, { readerOutEl: mountEl });



    if (direction === "next") {

      els.flip.classList.add("sbv2-page-flip--from-right");

      paintPageSlot(

        els.flipFrontContent,

        current.right,

        panelOpts,

        "right",

        spreadMetaFromSpread(current)

      );

      paintPageSlot(

        els.flipBackContent,

        target.left,

        panelOpts,

        "left",

        spreadMetaFromSpread(target)

      );

    } else {

      els.flip.classList.add("sbv2-page-flip--from-left");

      paintPageSlot(

        els.flipFrontContent,

        current.left,

        panelOpts,

        "left",

        spreadMetaFromSpread(current)

      );

      paintPageSlot(

        els.flipBackContent,

        target.right,

        panelOpts,

        "right",

        spreadMetaFromSpread(target)

      );

    }



    els.flip.hidden = false;

    els.flip.removeAttribute("aria-hidden");

    els.flip.classList.add("sbv2-page-flip--is-active");
    els.flip.style.setProperty("--sbv2-turn-ms", turnMs + "ms");



    fallback = window.setTimeout(function () {

      doneOnce();

    }, turnMs + 120);



    const turnClass =

      direction === "next"

        ? "sbv2-page-flip__inner--turn-next"

        : "sbv2-page-flip__inner--turn-prev";

    requestAnimationFrame(function () {

      requestAnimationFrame(function () {

        startV2InnerTurn(els.flipInner, turnClass);

      });

    });



    function onTurnEnd(ev) {

      if (ev.target !== els.flipInner) return;

      var animName = ev.animationName || "";
      if (
        animName.indexOf("sbv2-turn-next-keyframes") === -1 &&
        animName.indexOf("sbv2-turn-prev-keyframes") === -1
      ) {
        return;
      }

      els.flipInner.removeEventListener("animationend", onTurnEnd);

      doneOnce();

    }



    els.flipInner.addEventListener("animationend", onTurnEnd);

  }



  /**

   * Toggle fullscreen immersive mode on #storybooksPublicReader.

   * @param {boolean} on

   */

  function setV2Immersive(on, opts) {
    const roots = resolveV2ReaderRoots(opts || {});
    const root = document.documentElement;
    if (roots.host) {
      roots.host.classList.toggle("storybook-v2-root--immersive", !!on);
      if (on) {
        roots.host.classList.remove("sb-book-immersive");
      }
    }
    if (root) {
      root.classList.toggle("sb-book-scroll-lock", !!on);
    }
  }



  function runV2SpreadRender(opts) {
    opts = opts || {};
    const mountEl = opts.mountEl;
    const pages = opts.pages || [];
    if (!mountEl || !pages.length) {
      return { ok: false, reason: "empty" };
    }
    const spreadIndex =
      typeof opts.targetSpreadIndex === "number"
        ? opts.targetSpreadIndex
        : opts.currentSpreadIndex;
    const wantTurn =
      !!(opts.direction && typeof opts.targetSpreadIndex === "number");

    mountV2ShellIfNeeded(mountEl);
    if (!mountEl.querySelector(".sbv2-reader")) {
      return { ok: false, reason: "mount-failed" };
    }

    if (!wantTurn) {
      if (typeof opts.onSpreadCommitted === "function") {
        opts.onSpreadCommitted(spreadIndex);
      }
      paintSpreadResting(mountEl, pages, spreadIndex, opts.panelOpts || null);
      if (typeof opts.preloadAdjacent === "function") opts.preloadAdjacent();
      if (typeof opts.syncNav === "function") opts.syncNav();
      return { ok: true };
    }

    if (typeof opts.isAnimating === "function" && opts.isAnimating()) {
      return { ok: true, skipped: true };
    }

    const dir = opts.direction === "prev" ? "prev" : "next";
    const targetIndex = opts.targetSpreadIndex;
    try {
      if (typeof opts.setAnimating === "function") opts.setAnimating(true);
      if (typeof opts.syncNav === "function") opts.syncNav();
      runV2SpreadPageTurn({
        mountEl: mountEl,
        direction: dir,
        pages: pages,
        currentSpreadIndex: opts.currentSpreadIndex,
        panelOpts: opts.panelOpts || null,
        onSpreadCommitted: opts.onSpreadCommitted,
        setAnimating: opts.setAnimating,
        preloadAdjacent: opts.preloadAdjacent,
        onDone: opts.syncNav,
      });
    } catch (err) {
      if (typeof opts.onSpreadCommitted === "function") {
        opts.onSpreadCommitted(targetIndex);
      }
      paintSpreadResting(mountEl, pages, targetIndex, opts.panelOpts || null);
      if (typeof opts.setAnimating === "function") opts.setAnimating(false);
      if (typeof opts.preloadAdjacent === "function") opts.preloadAdjacent();
      if (typeof opts.syncNav === "function") opts.syncNav();
    }
    return { ok: true };
  }



  window.MesencsiStorybookReaderV2 = {

    buildV2ShellHtml: buildV2ShellHtml,

    buildV2FlipLayerHtml: buildV2FlipLayerHtml,

    ensureV2FlipLayerOnSpread: ensureV2FlipLayerOnSpread,

    resetV2FlipState: resetV2FlipState,

    mountV2ShellIfNeeded: mountV2ShellIfNeeded,

    getV2Elements: getV2Elements,

    paintSpreadResting: paintSpreadResting,

    runV2SpreadPageTurn: runV2SpreadPageTurn,

    runV2SpreadRender: runV2SpreadRender,

    syncV2NavState: syncV2NavState,

    PAGE_TURN_MS: PAGE_TURN_MS,

    setV2Immersive: setV2Immersive,

  };

})();


