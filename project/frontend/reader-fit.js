/* Mesekönyv olvasó, telefonon: a szöveg olvasható marad, és soha nem marad ki.
 * Ha egy lap szövege nem fér ki a szövegdobozba, a betűméretet csökkentjük (legfeljebb 12 px-ig);
 * ha így sem fér ki, a szövegdoboz legörgethető (a jelzés: elhalványodó alsó szél, vékony görgetősáv).
 * Csak telefonos nézetben (álló és fekvő) fut. Álló telefonon "fordítsd el a telefont" jelzést mutat. */
(function () {
  "use strict";
  var MIN_PX = 12;
  var PHONE =
    "(max-width: 900px) and (orientation: portrait), (max-width: 560px), (orientation: landscape) and (max-height: 520px)";
  var mq = window.matchMedia ? window.matchMedia(PHONE) : null;
  var scheduled = false;

  function updateMore(box) {
    var more = box.scrollHeight > box.clientHeight + 2 && box.scrollTop + box.clientHeight < box.scrollHeight - 3;
    box.classList.toggle("sbv2-more", more);
  }

  function fitOne(box) {
    var t = box.querySelector(".sb-canvas-text") || box;
    if (t.dataset.fitOrig === undefined) t.dataset.fitOrig = t.getAttribute("style") || "";
    t.setAttribute("style", t.dataset.fitOrig); // mindig az eredeti mérettől indulunk
    if (!mq || !mq.matches) {
      box.classList.remove("sbv2-more");
      return;
    }
    // az automatikus (nem kézzel elhelyezett) szövegdoboz telefonon szélesebb és magasabb: több hely a szövegnek
    var st = box.getAttribute("style") || "";
    if (box.dataset.fitBox === undefined) box.dataset.fitBox = st;
    box.setAttribute("style", box.dataset.fitBox);
    if (/left:\s*6%;\s*top:\s*6%;\s*width:\s*88%;\s*height:\s*88%/.test(box.dataset.fitBox)) {
      box.style.left = "3%";
      box.style.top = "3%";
      box.style.width = "94%";
      box.style.height = "94%";
    }
    var px = parseFloat(getComputedStyle(t).fontSize) || 16;
    var guard = 0;
    while (box.scrollHeight > box.clientHeight + 1 && px > MIN_PX && guard++ < 14) {
      px = Math.max(MIN_PX, px * 0.94);
      t.style.fontSize = px.toFixed(2) + "px";
    }
    if (!box.dataset.fitScroll) {
      box.dataset.fitScroll = "1";
      box.addEventListener(
        "scroll",
        function () {
          updateMore(box);
        },
        { passive: true }
      );
    }
    box.scrollTop = 0;
    updateMore(box);
  }

  function fitAll() {
    scheduled = false;
    var boxes = document.querySelectorAll("#storybooksPublicReader .sbv2-obj--text");
    for (var i = 0; i < boxes.length; i++) {
      if (boxes[i].classList.contains("sbv2-obj--text-blank")) continue;
      try {
        fitOne(boxes[i]);
      } catch (_) {}
    }
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    setTimeout(fitAll, 90);
  }

  // Álló telefonon: "fordítsd el a telefont" jelzés (a CSS csak ott mutatja).
  function ensureHint(root) {
    if (root.querySelector(".sbv2-rotate-hint")) return;
    var d = document.createElement("div");
    d.className = "sbv2-rotate-hint";
    d.setAttribute("role", "status");
    d.innerHTML =
      '<svg viewBox="0 0 64 64" fill="none" stroke="#fff6e0" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<rect x="20" y="6" width="24" height="44" rx="5"/><path d="M29 44h6"/><path d="M12 58c10 4 30 4 40 0M46 54l6 4-7 3"/></svg>' +
      "<div><strong>Fordítsd el a telefont!</strong>A mesekönyv fekvő helyzetben olvasható a legjobban.</div>";
    root.appendChild(d);
  }

  function start() {
    var root = document.getElementById("storybooksPublicReader");
    if (!root) return;
    ensureHint(root);
    new MutationObserver(function (muts) {
      // a saját beállításaink (style) ne indítsanak újra: csak a tartalom változása számít
      for (var i = 0; i < muts.length; i++) {
        if (muts[i].type === "childList") return schedule();
      }
    }).observe(root, { childList: true, subtree: true });
    window.addEventListener("resize", schedule);
    window.addEventListener("orientationchange", schedule);
    if (mq && mq.addEventListener) mq.addEventListener("change", schedule);
    schedule();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
