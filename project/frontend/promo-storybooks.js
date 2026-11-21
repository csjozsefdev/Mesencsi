/* Nyitási akció: "Írd meg a saját mesédet" sáv a digitális mesekönyvek oldalon.
 * Csak akkor jelenik meg, ha a szerver szerint a funkció be van kapcsolva
 * (GET /my/storybooks/status → enabled). Kikapcsolva a script nem csinál semmit. */
(function () {
  "use strict";
  function ready(fn) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }
  ready(function () {
    fetch("/my/storybooks/status", { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (st) {
        if (!st || !st.enabled) return;
        var host = document.getElementById("storybooksPublicList");
        if (!host || host.querySelector(".promo-sb-banner")) return;
        var css = document.createElement("style");
        css.textContent =
          ".promo-sb-banner{margin:0 0 1.1rem;padding:1rem 1.15rem;border-radius:14px;" +
          "background:linear-gradient(135deg,rgba(255,236,190,.92),rgba(255,214,150,.86));" +
          "border:1px solid rgba(160,100,30,.35);color:#3a2410;display:flex;gap:1rem;align-items:center;flex-wrap:wrap}" +
          ".promo-sb-banner__text{flex:1 1 16rem;line-height:1.45}" +
          ".promo-sb-banner__title{display:block;font-weight:800;font-size:1.1rem;margin-bottom:.15rem}" +
          ".promo-sb-banner a.promo-sb-banner__btn{display:inline-block;white-space:nowrap;text-decoration:none;padding:.6rem 1.2rem;" +
          "border-radius:999px;font-weight:800;color:#fff;background:linear-gradient(180deg,#a8662a,#7a431a);" +
          "border:1px solid rgba(60,30,10,.5);box-shadow:0 2px 6px rgba(60,30,10,.35)}" +
          ".promo-sb-banner a.promo-sb-banner__btn:hover{filter:brightness(1.1)}" +
          ".promo-sb-banner .psb-phone{display:none}" +
          "@media (max-width:767px),(orientation:landscape) and (max-height:520px){" +
          ".promo-sb-banner .psb-phone{display:block;margin-top:.4rem;font-weight:700;color:#5a3418}" +
          ".promo-sb-banner .psb-desk{display:none}}";
        document.head.appendChild(css);
        var b = document.createElement("aside");
        b.className = "promo-sb-banner";
        b.setAttribute("aria-label", "Nyitási akció");
        b.innerHTML =
          '<div class="promo-sb-banner__text"><span class="promo-sb-banner__title">✍️ Nyitási akció: írd meg a saját mesédet!</span>' +
          "Regisztrált felhasználóként a mesekönyv-szerkesztővel megírhatod és beküldheted a saját meséd. " +
          "A beküldött meséket átnézzük, és mi döntünk a közzétételről." +
          '<span class="psb-phone">Mesét tableten vagy számítógépen írhatsz. Telefonon a meséidet megnézheted és beküldheted.</span></div>' +
          '<a class="promo-sb-banner__btn" href="/meseiro"><span class="psb-desk">Mesét írok</span><span class="psb-phone" style="margin:0;color:inherit">Meséim</span></a>';
        host.insertBefore(b, host.querySelector(".storybook-reading-tip") || host.firstChild);
      })
      .catch(function () {});
  });
})();
