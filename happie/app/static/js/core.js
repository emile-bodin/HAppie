const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const euro = (n) => n == null ? "" : "€ " + Number(n).toFixed(2).replace(".", ",");
const bonusLabel = (t) => !t ? "Bonus" : String(t)
  .replace(/(?:€\s*)?(\d+)[.,](\d{2})(?!\d)/g, "€ $1,$2")
  .replace(/^VOOR\b/, "voor");
const isPhone = () => matchMedia("(max-width: 767px)").matches;
let status = {}, items = [], suggestions = [], lastResults = [], forceLogin = false;

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const res = await fetch(path, opts);
  let data = {};
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    if (data.auth) loadStatus().catch(() => {});
    const err = new Error(data.order_mode ? "Je bestelling staat open voor wijzigingen; de lijst is tijdelijk vergrendeld door AH." : (data.error || res.statusText));
    err.data = data; throw err;
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
const initials = (name) => (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("") || "?";
