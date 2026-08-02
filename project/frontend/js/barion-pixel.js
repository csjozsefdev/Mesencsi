(() => {
  "use strict";

  const PIXEL_ID = "BP-D1brwkHbMw-99";

  // Ne inicializáljuk többször, ha a fájl véletlenül kétszer töltődne be.
  if (window.__mesencsiBarionPixelInitialized) {
    return;
  }

  window.__mesencsiBarionPixelInitialized = true;
  window.barionpixel_function = "bp";

  window.bp =
    window.bp ||
    function () {
      (window.bp.q = window.bp.q || []).push(arguments);
    };

  window.bp.l = Date.now();

  const script = document.createElement("script");
  script.async = true;
  script.src = "https://pixel.barion.com/bp.js";

  script.onerror = () => {
    console.warn("A Barion Pixel könyvtára nem töltődött be.");
  };

  const firstScript = document.getElementsByTagName("script")[0];

  if (firstScript?.parentNode) {
    firstScript.parentNode.insertBefore(script, firstScript);
  } else {
    document.head.appendChild(script);
  }

  // Base Pixel inicializálás.
  window.bp("init", "addBarionPixelId", PIXEL_ID);
})();
