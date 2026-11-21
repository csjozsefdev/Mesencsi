/* Mesekönyv olvasó, telefonon: a szöveg soha ne maradjon ki.
 * Ha egy lap szövege nem fér ki a szövegdobozba, a betűméretet fokozatosan csökkentjük (legfeljebb 11 px-ig);
 * ha így sem fér ki, a dobozban érintéssel görgethető marad. Csak telefonos nézetben (álló és fekvő) fut. */
(function () {
  "use strict";
  var MIN_PX = 11;
  var PHONE =
    "(max-width: 900px) and (orientation: portrait), (max-width: 560px), (orientation: landscape) and (max-height: 520px)";
  var mq = window.matchMedia ? window.matchMedia(PHONE) : null;
  var scheduled = false;

  function fitOne(box) {
    var t = box.querySelector(".sb-canvas-text") || box;
    if (t.dataset.fitOrig === undefined) t.dataset.fitOrig = t.getAttribute("style") || "";
    t.setAttribute("style", t.dataset.fitOrig); // mindig az eredeti mérettől indulunk
    if (!mq || !mq.matches) return;
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

  function start() {
    var root = document.getElementById("storybooksPublicReader");
    if (!root) return;
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
