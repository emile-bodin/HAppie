// ---------------- login ----------------
async function linkAccount(code) {
  const btn = $("#loginBtn");
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>`;
  try {
    await api("api/login", { code });
    $("#codeInput").value = ""; forceLogin = false;
    toast("Gekoppeld met Albert Heijn");
    await refresh(); loadSuggestions(); loadDelivery(true);
  } catch (err) { toast(err.message); }
  btn.disabled = false; btn.textContent = "Koppelen";
}
$("#loginBtn").onclick = () => linkAccount($("#codeInput").value);

// Built-in login helper: a bookmarklet the user clicks on AH's own login page, before logging in.
// AH's login form submits with JavaScript in the same page, and the appie://login-exit?code=...
// link only shows up in one of the responses. So the helper listens to the page's own fetch/XHR
// responses (it does not touch the form or the captcha), and once the link appears it sends it
// back to this panel through window.opener (the AH tab was opened from here) and waits for an
// acknowledgement. Without one (no opener, or the message got lost) it sends the AH tab to this
// panel with the code in the URL fragment (never sent to a server), which links it on load.
// Keep this function free of // comments: it is turned into a one-line javascript: URL.
function happieHelper(target, panel) {
  const re = /appie:(?:\\?\/){2}login-exit\?[^"'\s<>]*?code(?:=|\\u003[dD])([A-Za-z0-9_~%-][A-Za-z0-9._~%-]{7,})/;
  const find = (t) => { const m = re.exec(t || ""); return m ? m[1] : null; };
  const bar = (text, url) => {
    let el = document.getElementById("happie-bar");
    if (!el) {
      el = document.createElement("div");
      el.id = "happie-bar";
      el.style.cssText = "position:fixed;z-index:2147483647;left:0;right:0;top:0;padding:12px 16px;background:#0e7c7b;color:#fff;font:15px system-ui,sans-serif;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.3)";
      document.documentElement.appendChild(el);
    }
    el.textContent = text;
    if (url) {
      const b = document.createElement("button");
      b.textContent = "Kopieer code";
      b.style.cssText = "margin-left:12px;padding:4px 10px;border:0;border-radius:6px;font:inherit;cursor:pointer";
      b.onclick = () => navigator.clipboard.writeText(url).then(() => { b.textContent = "Gekopieerd"; }, () => prompt("Kopieer deze link en plak hem in HAppie:", url));
      el.appendChild(b);
    }
  };
  const deliver = (code) => {
    if (window.__happieDone) return;
    window.__happieDone = true;
    const url = "appie://login-exit?code=" + code;
    let acked = false;
    window.addEventListener("message", (e) => { if (e.origin === target && e.data && e.data.type === "happie-ack") acked = true; });
    if (window.opener) {
      try { window.opener.postMessage({ type: "happie-code", url: url }, target); } catch (e) { acked = false; }
    }
    bar("HAppie: code gevonden, bezig met koppelen…", url);
    setTimeout(() => {
      if (acked) { bar("HAppie: gekoppeld. Dit tabblad sluit vanzelf.", url); return; }
      bar("HAppie: code gevonden, je gaat door naar HAppie…", url);
      location.href = panel + "#happie-code=" + encodeURIComponent(url);
    }, 1500);
  };
  const now = find(document.documentElement.innerHTML);
  if (now) { deliver(now); return; }
  if (location.hostname !== "login.ah.nl") { alert("HAppie: open eerst de AH-loginpagina via HAppie en klik daar op deze bladwijzer, vóór je inlogt."); return; }
  if (window.__happieHooked) { bar("HAppie luistert al mee. Log nu in."); return; }
  window.__happieHooked = true;
  const check = (text, extra) => { const c = find(extra) || find(text); if (c) deliver(c); };
  const origFetch = window.fetch;
  window.fetch = function () {
    const p = origFetch.apply(this, arguments);
    p.then((r) => {
      const extra = [r.headers.get("x-action-redirect"), r.headers.get("location"), r.url].join(" ");
      r.clone().text().then((t) => check(t, extra), () => check("", extra));
    }, () => { });
    return p;
  };
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function () {
    this.addEventListener("load", () => {
      try { check(this.responseType === "" || this.responseType === "text" ? this.responseText : "", this.getResponseHeader("x-action-redirect") || ""); } catch (e) { }
    });
    return origSend.apply(this, arguments);
  };
  bar("HAppie luistert mee. Log nu in, HAppie pakt de code zelf op.");
}
$("#bmLink").href = "javascript:" + encodeURIComponent(
  "(" + happieHelper.toString().replace(/\s*\n\s*/g, " ") + ")(" + JSON.stringify(location.origin) + ","
  + JSON.stringify(location.href.split("#")[0]) + ")");
$("#bmLink").onclick = (e) => { e.preventDefault(); toast("Sleep deze knop naar je bladwijzerbalk"); };

let loginWin = null;
$("#loginOpen").onclick = () => {
  // a normal tab (with bookmarks bar) that keeps window.opener, so the helper can reach us
  loginWin = window.open(status.login_url, "happie-ah-login");
  $("#loginWait").classList.remove("hidden");
};
window.addEventListener("message", (e) => {
  if (e.origin !== "https://login.ah.nl" || !e.data || e.data.type !== "happie-code" || typeof e.data.url !== "string") return;
  try { e.source.postMessage({ type: "happie-ack" }, e.origin); } catch (_) {}
  setTimeout(() => { try { if (loginWin) loginWin.close(); } catch (_) {} loginWin = null; }, 300);
  $("#loginWait").classList.add("hidden");
  linkAccount(e.data.url);
});
// fallback from the helper: the AH tab came here with the code in the fragment
{
  const fromHelper = new URLSearchParams(location.hash.slice(1)).get("happie-code");
  if (fromHelper) {
    history.replaceState(null, "", location.pathname + location.search);
    linkAccount(fromHelper);
  }
}
// the login may finish in another tab: re-check when coming back here
window.addEventListener("focus", () => { if (!$("#loginView").classList.contains("hidden")) loadStatus().catch(() => {}); });
