const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const euro = (n) => n == null ? "" : "€ " + Number(n).toFixed(2).replace(".", ",");
const bonusLabel = (t) => !t ? "Bonus" : String(t)
  .replace(/(?:€\s*)?(\d+)[.,](\d{2})(?!\d)/g, "€ $1,$2")
  .replace(/^VOOR\b/, "voor");
const isPhone = () => matchMedia("(max-width: 767px)").matches;
// thin line icons for the small list controls
const thinIcon = (d, size = 14) => `<svg width="${size}" height="${size}" viewBox="0 0 14 14" aria-hidden="true"><path d="${d}" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const ICON_MINUS = thinIcon("M3 7h8"), ICON_PLUS = thinIcon("M7 3v8M3 7h8"), ICON_X = thinIcon("M4 4l6 6M10 4l-6 6", 12), ICON_CHECK = thinIcon("M3.5 7.2l2.3 2.3 4.7-4.9", 13);
let status = {}, items = [], suggestions = [], lastResults = [], forceLogin = false;

// Technical errors (HTTP codes, JSON from AH, "Not Found") become a sentence a user can act on.
// The original text stays in the console and on err.raw.
function friendlyError(status, raw, data = {}) {
  raw = String(raw || "");
  const technical = /[{}]|\b\d{3}\b|^(not found|internal server error|bad gateway|service unavailable|gateway timeout)$/i.test(raw.trim());
  if (data.auth || status === 401 || /invalid[_ ]token|unauthori[sz]ed|\b401\b/i.test(raw))
    return "Je AH-sessie is verlopen. Log opnieuw in via je profiel rechtsboven.";
  if (!technical) return raw;
  if (status === 404 || /\b404\b|not found/i.test(raw)) return "Dit is nu niet te laden. Probeer het later opnieuw.";
  if (/\b429\b/.test(raw)) return "AH krijgt nu te veel verzoeken. Probeer het over een minuut opnieuw.";
  return "AH reageert nu niet goed. Probeer het zo opnieuw.";
}
async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  let res;
  try { res = await fetch(path, opts); }
  catch (e) { const err = new Error("Geen verbinding met HAppie. Controleer of de app draait."); err.raw = String(e); err.data = {}; throw err; }
  let data = {};
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    if (data.auth) loadStatus().catch(() => {});
    const raw = data.error || res.statusText;
    const err = new Error(data.order_mode ? "Je bestelling staat open voor wijzigingen; de lijst is tijdelijk vergrendeld door AH." : friendlyError(res.status, raw, data));
    if (err.message !== raw) console.warn(`HAppie ${path}: ${res.status} ${raw}`);
    err.raw = raw; err.data = data; throw err;
  }
  return data;
}
function toast(msg, action) {
  const t = $("#toast"); t.textContent = msg;
  t.classList.toggle("has-action", !!action);
  if (action) {
    const b = document.createElement("button"); b.textContent = action.label;
    b.onclick = () => { t.classList.remove("show"); action.fn(); };
    t.appendChild(b);
  }
  t.classList.add("show");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("show"), action ? 5000 : 2600);
}
function ago(ts) {
  if (!ts) return "nog niet";
  const s = Math.round(Date.now() / 1000 - ts);
  if (s < 10) return "zojuist";
  if (s < 60) return `${s} s geleden`;
  if (s < 3600) return `${Math.round(s / 60)} min geleden`;
  return new Date(ts * 1000).toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" });
}
// first letter or digit of a name, for products without a photo
const initialOf = (name) => (String(name || "").match(/[\p{L}\p{N}]/u) || ["?"])[0].toUpperCase();
const initials = (name) => (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("") || "?";

// ---------------- product image popup ----------------
// AH image URLs carry their size ("rendition=200x200_WEBP"); ask for a bigger one, fall back to the original
const bigImage = (url) => url.replace(/rendition=\d+x\d+/, "rendition=800x800");
const imgOpen = () => !$("#imgModal").classList.contains("hidden");
function openImage(src, title) {
  const big = $("#imgBig");
  big.onerror = () => { big.onerror = null; big.src = src; };
  big.src = src;  // show the small one right away, swap when the big one has loaded
  const hi = new Image();
  hi.onload = () => { if (imgOpen() && big.src === src) big.src = hi.src; };
  hi.src = bigImage(src);
  big.alt = title || "";
  $("#imgTitle").textContent = title || "Product";
  $("#imgModal").classList.remove("hidden");
  $("#imgClose").focus();
}
const closeImage = () => $("#imgModal").classList.add("hidden");
document.addEventListener("click", (e) => {
  const img = e.target.closest("img.thumb, .product img, .scanresult img");
  if (!img || !img.src || img.closest("#imgModal")) return;
  e.stopPropagation();  // only zoom: don't also trigger the row's own click
  const row = img.closest("li, .srow, .product, .scanresult, .orow");
  const name = row?.querySelector(".name > span, .title, .nm > span, b, strong");
  openImage(img.src, name?.textContent.trim());
}, true);
$("#imgClose").addEventListener("click", closeImage);
$("#imgModal").addEventListener("click", (e) => { if (e.target.id === "imgModal") closeImage(); });
// capture, so Escape closes only the image and not an order modal underneath
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && imgOpen()) { e.stopImmediatePropagation(); closeImage(); } }, true);
