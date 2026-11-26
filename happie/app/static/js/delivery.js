// ---------------- delivery ----------------
const ORDER_STATE = { OUT_FOR_DELIVERY: "Onderweg", REOPENED: "Open voor wijzigingen", SUBMITTED: "Geplaatst", CONFIRMED: "Bevestigd", IN_PROGRESS: "Onderweg", PROCESSING: "Wordt verwerkt" };
function dayLabel(dateStr) {
  const d = new Date(dateStr + "T12:00:00"), now = new Date(); now.setHours(12, 0, 0, 0);
  const diff = Math.round((d - now) / 864e5);
  return diff === 0 ? "Vandaag" : diff === 1 ? "Morgen" : diff > 1 ? `Over ${diff} dagen` : "";
}
async function loadDelivery(refresh = false) {
  let d;
  try { d = (await api("api/delivery" + (refresh ? "?refresh=1" : ""))).delivery; }
  catch (err) { $("#dlvVal").textContent = "Niet beschikbaar"; $("#dlvSub").textContent = err.message; return; }
  // a date in the past means the cached order is outdated: fetch it again once
  if (d && !refresh && d.date < new Date().toLocaleDateString("sv-SE")) return loadDelivery(true);
  const el = $("#delivery");
  el.dataset.order = d ? d.order_id : "";
  el.classList.toggle("none", !d);
  if (!d) { $("#dlvLbl").textContent = "Volgende bezorging"; $("#dlvVal").textContent = "Geen bestelling gepland"; $("#dlvSub").innerHTML = ""; return; }
  const date = new Date(d.date + "T12:00:00");
  const dateTxt = date.toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short" });
  const pickup = d.type === "PICKUP";
  // a reserved slot without groceries yet: AH only sends "fill up to €45 before ..." then
  const empty = d.min_order != null && !d.item_count && !d.total;
  $("#dlvLbl").textContent = empty ? (pickup ? "Gereserveerd ophaalmoment" : "Gereserveerd bezorgmoment") : pickup ? "Volgende ophaalmoment" : "Volgende bezorging";
  $("#dlvVal").textContent = dateTxt + (d.start ? ` · ${d.start}–${d.end}` : "");
  // one line: pills first, then the most important text; the rest is cut off (full text in the tooltip)
  const pills = [], txt = [];
  const rel = dayLabel(d.date); if (rel === "Vandaag" || rel === "Morgen") pills.push(`<span class="pill">${rel}</span>`);
  if (d.state === "REOPENED") pills.push(`<span class="pill">✎ Open</span>`);
  const closing = d.closing_time && new Date(d.closing_time);
  const day = (t) => t.toLocaleDateString("nl-NL", { weekday: "short" });
  const hm = (t) => t.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" });
  if (d.eta_start) pills.push(`<span class="pill eta">Verwacht ${d.eta_start}–${d.eta_end}</span>`);
  else if (d.min_order != null && (d.total || 0) < d.min_order) {
    const by = closing ? ` vóór ${day(closing)} ${d.fill_by || hm(closing)}` : "";
    txt.push(empty ? `Vul aan tot ${euro(d.min_order).replace(",00", "")}${by}` : `Nog ${euro(d.min_order - d.total)} tot min.${by}`);
  } else if (d.eta_message && d.track_state && d.track_state !== "UNKNOWN") txt.push(d.eta_message);
  else if (closing && closing > new Date()) txt.push(`Wijzigen tot ${day(closing)} ${hm(closing)}`);
  if (d.item_count) txt.push(`${d.item_count} artikelen`);
  if (d.total) txt.push(euro(d.total));
  $("#dlvSub").innerHTML = pills.join("") + (txt.length ? `<span class="txt">${esc(txt.join(" · "))}</span>` : "");
  el.title = [ORDER_STATE[d.state] || d.state, rel, d.eta_message, ...txt].filter((v, i, a) => v && a.indexOf(v) === i).join("\n");
}
