/**
 * Hírek mini-markup: [b], [i], [left], [center], [list] — textarea + megjelenítés.
 * API: window.MesencsiNewsFormat
 */
(function () {
  "use strict";

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderInlineRaw(text) {
    text = String(text || "");
    if (!text) return "";

    function tokenize(str) {
      const tokens = [];
      const re = /\[b\]([\s\S]*?)\[\/b\]|\[i\]([\s\S]*?)\[\/i\]/gi;
      let last = 0;
      let m;
      while ((m = re.exec(str)) !== null) {
        if (m.index > last) tokens.push({ type: "text", v: str.slice(last, m.index) });
        if (m[1] !== undefined) tokens.push({ type: "b", v: m[1] });
        else tokens.push({ type: "i", v: m[2] });
        last = m.index + m[0].length;
      }
      if (last < str.length) tokens.push({ type: "text", v: str.slice(last) });
      return tokens;
    }

    return tokenize(text)
      .map(function (t) {
        if (t.type === "text") return escapeHtml(t.v);
        if (t.type === "b") return "<strong>" + renderInlineRaw(t.v) + "</strong>";
        if (t.type === "i") return "<em>" + renderInlineRaw(t.v) + "</em>";
        return "";
      })
      .join("");
  }

  function renderParagraphs(text) {
    const paras = String(text)
      .split(/\n\s*\n/)
      .map(function (p) {
        return p.trim();
      })
      .filter(Boolean);
    if (!paras.length) return renderInlineRaw(text).replace(/\n/g, "<br/>");
    return paras
      .map(function (p) {
        return "<p>" + renderInlineRaw(p).replace(/\n/g, "<br/>") + "</p>";
      })
      .join("");
  }

  function renderNewsHtml(raw) {
    const src = String(raw || "");
    if (!src.trim()) return "";

    const blockRe = /\[(left|center|list)\]([\s\S]*?)\[\/\1\]/gi;
    let html = "";
    let last = 0;
    let m;
    while ((m = blockRe.exec(src)) !== null) {
      if (m.index > last) html += renderParagraphs(src.slice(last, m.index));
      const kind = m[1].toLowerCase();
      const inner = m[2];
      if (kind === "left") {
        html += '<div class="news-mini-align news-mini-align--left">' + renderParagraphs(inner) + "</div>";
      } else if (kind === "center") {
        html += '<div class="news-mini-align news-mini-align--center">' + renderParagraphs(inner) + "</div>";
      } else if (kind === "list") {
        const items = inner
          .split(/\n/)
          .map(function (line) {
            return line.replace(/^[\s\-*•]+/, "").trim();
          })
          .filter(Boolean);
        html +=
          '<ul class="news-mini-list">' +
          items
            .map(function (it) {
              return "<li>" + renderInlineRaw(it) + "</li>";
            })
            .join("") +
          "</ul>";
      }
      last = m.index + m[0].length;
    }
    if (last < src.length) html += renderParagraphs(src.slice(last));
    return html;
  }

  function wrapSelection(textarea, before, after, placeholder) {
    const start = textarea.selectionStart != null ? textarea.selectionStart : textarea.value.length;
    const end = textarea.selectionEnd != null ? textarea.selectionEnd : start;
    const sel = textarea.value.slice(start, end);
    const mid = sel || placeholder || "";
    const ins = before + mid + after;
    textarea.value = textarea.value.slice(0, start) + ins + textarea.value.slice(end);
    const pos = start + before.length + mid.length;
    textarea.setSelectionRange(pos, pos);
    textarea.focus();
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function applyToolbarAction(textarea, act) {
    if (!textarea || !act) return;
    switch (String(act).toLowerCase()) {
      case "bold":
        wrapSelection(textarea, "[b]", "[/b]", "szöveg");
        break;
      case "italic":
        wrapSelection(textarea, "[i]", "[/i]", "szöveg");
        break;
      case "left":
        wrapSelection(textarea, "[left]\n", "\n[/left]", "szöveg");
        break;
      case "center":
        wrapSelection(textarea, "[center]\n", "\n[/center]", "szöveg");
        break;
      case "list":
        wrapSelection(textarea, "[list]\n- ", "\n[/list]", "tétel");
        break;
      default:
        break;
    }
  }

  window.MesencsiNewsFormat = {
    renderNewsHtml: renderNewsHtml,
    applyToolbarAction: applyToolbarAction,
  };
})();
