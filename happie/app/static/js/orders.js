// ---------------- orders ----------------
const ORDER_STATE_SHORT = { DELIVERED: "bezorgd", COMPLETED: "bezorgd", OUT_FOR_DELIVERY: "onderweg", CONFIRMED: "bevestigd",
  SUBMITTED: "geplaatst", REOPENED: "open", IN_PROGRESS: "onderweg", PROCESSING: "in behandeling" };
let orders = [], orderSel = null, orderData = null;
function orderLabel(o) {
  const d = new Date(o.date + "T12:00:00").toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short" });
  return `${d}<small>${ORDER_STATE_SHORT[o.state] || o.state.toLowerCase()}</small>`;
}
async function openOrders() {
  $("#orderModal").classList.remove("hidden");
  $("#orderBody").innerHTML = `<div class="hint"><span class="spinner"></span></div>`;
  try { orders = (await api("api/orders")).orders; }
  catch (err) { $("#orderBody").innerHTML = `<div class="hint">${esc(err.message)}</div>`; return; }
  if (!orders.length) { $("#orderTabs").innerHTML = ""; $("#orderSum").innerHTML = ""; $("#orderBody").innerHTML = `<div class="hint">Geen bestellingen gevonden.</div>`; return; }
  // start at the next delivery, or the first upcoming order
  const next = $("#delivery").dataset.order;
  const pick = orders.find((o) => String(o.order_id) === next) || orders[0];
  showOrder(pick.order_id);
}
async function showOrder(id, refresh = false) {
  orderSel = id;
  const o = orders.find((x) => x.order_id === id);
  const tab = (x) => `<button data-o="${x.order_id}" class="${x.order_id === id ? "active" : ""}" role="tab" aria-selected="${x.order_id === id}">${orderLabel(x)}</button>`;
  const up = orders.filter((x) => !x.done), past = orders.filter((x) => x.done);
  $("#orderTabs").innerHTML = (up.length ? `<span class="rowlbl">Komend</span>${up.map(tab).join("")}` : "")
    + (up.length && past.length ? `<span style="flex-basis:100%;height:0"></span>` : "")
    + (past.length ? `<span class="rowlbl">Bezorgd</span>${past.map(tab).join("")}` : "");
  $("#orderSum").innerHTML = ""; $("#orderTools").classList.add("hidden");
  $("#orderBody").innerHTML = `<div class="hint"><span class="spinner"></span></div>`;
  try { orderData = await api(`api/orders/${id}?done=${o.done ? 1 : 0}` + (refresh ? "&refresh=1" : "")); }
  catch (err) { $("#orderBody").innerHTML = `<div class="hint">${esc(err.message)}</div>`; return; }
  if (orderSel !== id) return;
  orderData.unpacked = orderData.unpacked || o.unpacked;
  renderOrder(o);
}
function renderOrder(o) {
  const d = orderData, lines = d.lines;
  const date = new Date(o.date + "T12:00:00").toLocaleDateString("nl-NL", { weekday: "long", day: "numeric", month: "long" });
  const dupes = lines.filter((l) => l.on_list).length;
  const sum = [`<span class="grow"><b>${esc(date)}</b> · ${esc((ORDER_STATE[o.state] || ORDER_STATE_SHORT[o.state] || o.state).toLowerCase())}<br>
    <span class="muted">${lines.length} producten · ${d.items} stuks</span></span>`];
  if (o.total) sum.push(`<span><b>${euro(o.total)}</b>${o.discount ? ` <span class="disc">−${euro(o.discount)} korting</span>` : ""}</span>`);
  if (o.done) sum.push(d.unpacked ? `<span class="onlist">✓ uitgepakt</span>` : `<button class="btn sm" id="orderUnpack">Uitpakken naar voorraad</button>`);
  $("#orderSum").innerHTML = `<div class="ordersum">${sum.join("")}</div>`
    + (dupes && !o.done ? `<div class="muted" style="font-size:13px;margin-top:6px"><span class="dupe">ook op lijst</span> ${dupes} ${dupes === 1 ? "product staat" : "producten staan"} ook nog op je boodschappenlijst.</div>` : "");
  $("#orderTools").classList.toggle("hidden", lines.length < 8);
  $("#orderFilter").value = "";
  renderOrderLines();
}
function renderOrderLines() {
  const o = orders.find((x) => x.order_id === orderSel), q = $("#orderFilter").value.trim().toLowerCase();
  if (!orderData.lines.length) {
    $("#orderBody").innerHTML = `<div class="hint">${o.done ? "Geen producten gevonden in deze bestelling." : "Deze bestelling is nog leeg. Vul hem in de AH-app."}</div>`;
    $("#orderCount").textContent = ""; return;
  }
  const lines = orderData.lines.filter((l) => !q || `${l.product.title} ${l.product.brand || ""}`.toLowerCase().includes(q));
  const groups = new Map();
  for (const l of lines) { const c = l.product.category || "Overig"; if (!groups.has(c)) groups.set(c, []); groups.get(c).push(l); }
  $("#orderCount").textContent = q ? `${lines.length} van ${orderData.lines.length}` : "";
  $("#orderBody").innerHTML = lines.length ? [...groups].map(([cat, ls]) => `<div class="group">${esc(cat)}</div><ul class="items">${ls.map((l) => {
    const p = l.product, bits = [];
    if (p.unit_size) bits.push(esc(p.unit_size));
    if (l.line) bits.push(l.quantity > 1 ? `${euro(p.price_before || p.price)} × ${l.quantity} ≈ ${euro(l.line.total)}` : `≈ ${euro(l.line.total)}`);
    if (l.on_list && !o.done) bits.push(`<span class="dupe">ook op lijst${l.on_list > 1 ? ` (${l.on_list}×)` : ""}</span>`);
    const short = l.ordered > l.quantity ? `<small>van ${l.ordered}</small>` : "";
    return `<li>${p.image ? `<img class="thumb" src="${esc(p.image)}" alt="" loading="lazy">` : `<div class="ph">?</div>`}
      <div class="name"><span>${esc(p.title)}</span>${bits.length ? `<small>${bits.join("<span>·</span>")}</small>` : ""}</div>
      <div class="oq">${l.quantity}×${short}</div></li>`;
  }).join("")}</ul>`).join("") : `<div class="hint">Niets gevonden voor “${esc(q)}”.</div>`;
}
const closeOrders = () => $("#orderModal").classList.add("hidden");
$("#delivery").addEventListener("click", openOrders);
$("#delivery").addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openOrders(); } });
$("#orderClose").onclick = closeOrders;
$("#orderModal").addEventListener("click", (e) => { if (e.target.id === "orderModal") closeOrders(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#orderModal").classList.contains("hidden")) closeOrders(); });
$("#orderTabs").addEventListener("click", (e) => { const b = e.target.closest("button[data-o]"); if (b) showOrder(+b.dataset.o); });
$("#orderFilter").addEventListener("input", renderOrderLines);
$("#orderRefresh").onclick = () => { if (orderSel != null) showOrder(orderSel, true); };
$("#orderSum").addEventListener("click", async (e) => {
  const btn = e.target.closest("#orderUnpack");
  if (!btn) return;
  if (!confirm(`Alle ${orderData.items} artikelen van deze bezorging aan je voorraad toevoegen?`)) return;
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>`;
  try {
    const r = await api("api/inventory/unpack", { order_id: orderSel });
    toast(r.already ? "Deze bestelling was al uitgepakt" : `${r.added} artikelen (${r.products} producten) toegevoegd aan je voorraad`);
    orderData.unpacked = true;
    const o = orders.find((x) => x.order_id === orderSel); o.unpacked = true; renderOrder(o);
  } catch (err) { toast(err.message); btn.disabled = false; btn.textContent = "Uitpakken naar voorraad"; }
});
