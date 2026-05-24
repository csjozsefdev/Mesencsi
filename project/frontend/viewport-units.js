/** Sync --app-vh-px for mobile rotation / dynamic browser chrome (lightweight). */
(function () {
  function syncAppViewportHeight() {
    var vv = window.visualViewport;
    var h = Math.round(
      (vv && vv.height) || window.innerHeight || document.documentElement.clientHeight || 0
    );
    if (h > 0) {
      document.documentElement.style.setProperty("--app-vh-px", h + "px");
    }
  }
  syncAppViewportHeight();
  window.addEventListener("resize", syncAppViewportHeight, { passive: true });
  window.addEventListener(
    "orientationchange",
    function () {
      requestAnimationFrame(function () {
        syncAppViewportHeight();
        window.setTimeout(syncAppViewportHeight, 150);
      });
    },
    { passive: true }
  );
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", syncAppViewportHeight, { passive: true });
  }
})();
