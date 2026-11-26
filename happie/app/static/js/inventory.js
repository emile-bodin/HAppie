// ---------------- voorraad ----------------
let inv = [], invSummary = {}, invResults = [], invLoaded = false;
const invMode = () => { try { return localStorage.getItem("happie-scanmode") || "choose"; } catch (_) { return "choose"; } };
function setInvMode(m) {
  try { localStorage.setItem("happie-scanmode", m); } catch (_) {}
  document.querySelectorAll("#scanModeSeg button").forEach((b) => b.classList.toggle("active", b.dataset.mode === m));
}
document.querySelectorAll("#scanModeSeg button").forEach((b) => (b.onclick = () => setInvMode(b.dataset.mode)));
setInvMode(invMode());
// on a phone the stock list matters most: start with "Bestelling uitpakken" folded
if (matchMedia("(max-width: 767px)").matches) $("#unpackBox").open = false;

async function loadInventory() {
  const d = await api("api/inventory");
  inv = d.items; invSummary = d.summary; invLoaded = true;
  if (document.activeElement?.classList.contains("qtyinput")) return;  // don't interrupt typing a count
  renderInventory();
}
function renderInventory() {
  $("#ivProducts").textContent = invSummary.products ?? 0;
  $("#ivUnits").textContent = invSummary.total_units ?? 0;
  $("#ivEmpty").textContent = (invSummary.empty || []).length;
  $("#invCount").textContent = invSummary.products ?? 0;
  const f = $("#invFilter").value.trim().toLowerCase();
  const shown = inv.filter((i) => !f || i.name.toLowerCase().includes(f));
  $("#invFilterBox").classList.toggle("hidden", !inv.length);
  if (!inv.length) {
    $("#invList").innerHTML = `<div class="empty"><div style="font-size:40px">📦</div><div><b>Nog geen voorraad</b></div>
      <div style="font-size:13px">Houd bij wat je in huis hebt: scan een barcode, zoek een product of pak een bezorging in één keer uit.</div>
      <div class="actions"><button class="btn" data-inv-empty="scan">Barcode scannen</button><button class="btn ghost" data-inv-empty="unpack">Bezorging uitpakken</button></div></div>`;
    return;
  }
  if (!shown.length) { $("#invList").innerHTML = `<div class="hint">Niets gevonden voor “${esc(f)}”.</div>`; return; }
  const groups = new Map();
  for (const i of shown) {
    const cat = i.quantity <= 0 ? "Op" : (i.category || "Overig");
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat).push(i);
  }
  const order = [...groups.keys()].sort((a, b) => (a === "Op") - (b === "Op") || (a === "Overig") - (b === "Overig") || a.localeCompare(b));
  $("#invList").innerHTML = order.map((cat) => `<div class="group">${esc(cat)}</div><ul class="items">${groups.get(cat).map(invRow).join("")}</ul>`).join("");
}
function invRow(i) {
  const k = esc(i.key);
  const img = i.image ? `<img class="thumb" src="${esc(i.image)}" alt="" loading="lazy">` : `<div class="ph" aria-hidden="true">${esc(initialOf(i.name))}</div>`;
  const bits = [esc(i.unit_size || ""), i.price ? euro(i.price) : "", i.is_bonus ? `<span class="badge">${esc(bonusLabel(i.bonus))}</span>` : "",
                i.quantity <= 0 ? `<span class="oplabel">op</span>` : ""].filter(Boolean);
  return `<li class="${i.quantity <= 0 ? "empty-stock" : ""}" data-key="${k}">
    ${img}
    <div class="name"><span>${esc(i.name)}</span>${bits.length ? `<small>${bits.join("<span>·</span>")}</small>` : ""}</div>
    <div class="qty">
      <button data-iact="dec" aria-label="Eén minder">${ICON_MINUS}</button>
      <button class="qtybtn" data-iact="edit" title="Aantal instellen">${i.quantity}</button>
      <button data-iact="inc" aria-label="Eén meer">${ICON_PLUS}</button>
    </div>
    <button class="tolist" data-iact="tolist" title="Op de boodschappenlijst" aria-label="Op de boodschappenlijst">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M17 18a2 2 0 1 1 0 4 2 2 0 0 1 0-4M1 2h3.27l.94 2H20a1 1 0 0 1 1 1c0 .17-.05.34-.12.5l-3.58 6.47c-.34.61-1 1.03-1.75 1.03H8.1l-.9 1.63-.03.12a.25.25 0 0 0 .25.25H19v2H7a2 2 0 0 1-2-2c0-.35.09-.68.24-.96l1.36-2.45L3 4H1V2m6 16a2 2 0 1 1 0 4 2 2 0 0 1 0-4"/></svg>
    </button>
    <button class="del" data-iact="del" aria-label="Uit voorraad verwijderen">${ICON_X}</button>
  </li>`;
}
function invApply(item) {
  // merge a changed item from the API into the local list
  if (!item) return;
  const idx = inv.findIndex((i) => i.key === item.key);
  if (idx >= 0) inv[idx] = { ...inv[idx], ...item }; else inv.push(item);
}
async function invChange(path, body) {
  const r = await api(path, body);
  invApply(r.item);
  loadInventory().catch(() => {});  // refresh summary/order in the background
  renderInventory();
  return r.item;
}
async function toList(key, name) {
  try { await api("api/inventory/to-list", { key }); toast(`${name} op de boodschappenlijst`); loadList().catch(() => {}); }
  catch (err) { toast(err.message); }
}
function emptyToast(item) {
  toast(`${item.name} is op`, { label: "Op de lijst", fn: () => toList(item.key, item.name) });
}
$("#invList").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-iact]");
  if (!btn) return;
  const li = btn.closest("li"), key = li.dataset.key, item = inv.find((i) => i.key === key);
  if (!item) return;
  const act = btn.dataset.iact;
  try {
    if (act === "inc" || act === "dec") {
      const r = await invChange("api/inventory/adjust", { key, delta: act === "inc" ? 1 : -1 });
      if (act === "dec" && r && r.quantity === 0 && r.before > 0) emptyToast(r);
    } else if (act === "edit") {
      const input = document.createElement("input");
      input.type = "number"; input.min = "0"; input.inputMode = "numeric"; input.className = "qtyinput"; input.value = item.quantity;
      btn.replaceWith(input); input.focus(); input.select();
      let done = false;
      const commit = async () => {
        if (done) return; done = true;
        const q = Math.max(0, parseInt(input.value, 10) || 0);
        if (q === item.quantity) { renderInventory(); return; }
        const r = await invChange("api/inventory/set", { key, quantity: q }).catch((err) => toast(err.message));
        if (r && r.quantity === 0 && r.before > 0) emptyToast(r);
      };
      input.addEventListener("keydown", (ev) => { if (ev.key === "Enter") commit(); if (ev.key === "Escape") { done = true; renderInventory(); } });
      input.addEventListener("blur", commit);
    } else if (act === "tolist") {
      await toList(key, item.name);
    } else if (act === "del") {
      if (!confirm(`${item.name} uit je voorraad verwijderen?`)) return;
      inv = inv.filter((i) => i !== item); renderInventory();
      await api("api/inventory/remove", { key }); loadInventory().catch(() => {});
    }
  } catch (err) { toast(err.message); }
});
$("#invFilter").addEventListener("input", renderInventory);
$("#invList").addEventListener("click", (e) => {
  const b = e.target.closest("[data-inv-empty]");
  if (!b) return;
  if (b.dataset.invEmpty === "scan") return openScanner("inventory");
  const box = $("#unpackBox"); box.open = true; box.scrollIntoView({ behavior: "smooth", block: "start" });
});

// search -> add to stock
let invTimer, invSeq = 0;
$("#invSearch").addEventListener("input", () => {
  clearTimeout(invTimer);
  const q = $("#invSearch").value.trim();
  const ft = $("#invFreeText");
  ft.classList.toggle("hidden", !q);
  ft.innerHTML = q ? `<a id="invAddFree">+ “${esc(q)}” als eigen product</a> <span class="muted">(Enter)</span>` : "";
  const a = $("#invAddFree"); if (a) a.onclick = () => invAddName(q);
  if (q.length < 2) { $("#invResults").innerHTML = ""; return; }
  invTimer = setTimeout(async () => {
    const seq = ++invSeq;
    $("#invResults").innerHTML = `<div class="muted"><span class="spinner"></span> Zoeken…</div>`;
    try {
      const { products } = await api("api/search?q=" + encodeURIComponent(q));
      if (seq !== invSeq) return;
      invResults = products;
      $("#invResults").innerHTML = products.length ? products.map((p, i) => productCard(p, i, "+ Voorraad")).join("") : `<div class="muted">Niets gevonden.</div>`;
    } catch (err) { if (seq === invSeq) $("#invResults").innerHTML = `<div class="muted">${esc(err.message)}</div>`; }
  }, 300);
});
$("#invSearchForm").addEventListener("submit", (e) => { e.preventDefault(); const q = $("#invSearch").value.trim(); if (q) invAddName(q); });
async function invAddName(name) {
  try {
    const r = await invChange("api/inventory/adjust", { name, delta: 1 });
    toast(`${r.name}: ${r.before} → ${r.quantity}`);
    $("#invSearch").value = ""; $("#invResults").innerHTML = ""; $("#invFreeText").classList.add("hidden");
  } catch (err) { toast(err.message); }
}
$("#invResults").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-idx]");
  if (!btn) return;
  const p = invResults[+btn.dataset.idx];
  btn.disabled = true;
  try {
    const r = await invChange("api/inventory/adjust", { product: p, delta: 1 });
    btn.textContent = `✓ ${r.quantity} op voorraad`;
    toast(`${r.name}: ${r.before} → ${r.quantity}`);
  } catch (err) { toast(err.message); btn.textContent = "+ Voorraad"; }
  btn.disabled = false;
});

// unpack a delivered order
async function loadOrders() {
  try {
    const { orders } = await api("api/inventory/orders");
    $("#invOrders").innerHTML = orders.length ? orders.map((o) => {
      const d = new Date(o.date + "T12:00:00").toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short" });
      return `<div class="orow">
        <div class="name"><span><b>${esc(d)}</b></span><small class="muted">${o.products} producten · ${o.items} stuks</small></div>
        ${o.unpacked ? `<span class="onlist">✓ uitgepakt</span>` : `<button class="btn sm" data-order="${o.order_id}" data-items="${o.items}" data-date="${esc(d)}">Uitpakken</button>`}
      </div>`;
    }).join("") : `<div class="hint">Geen afgeleverde bestellingen gevonden.</div>`;
  } catch (err) { $("#invOrders").innerHTML = `<div class="hint">${esc(err.message)}</div>`; }
}
$("#invOrders").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-order]");
  if (!btn) return;
  if (!confirm(`Alle ${btn.dataset.items} artikelen van de bezorging van ${btn.dataset.date} aan je voorraad toevoegen?`)) return;
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>`;
  try {
    const r = await api("api/inventory/unpack", { order_id: +btn.dataset.order });
    toast(r.already ? "Deze bestelling was al uitgepakt" : `${r.added} artikelen (${r.products} producten) toegevoegd`);
    await Promise.all([loadInventory(), loadOrders()]);
  } catch (err) { toast(err.message); btn.disabled = false; btn.textContent = "Uitpakken"; }
});

// barcode -> stock
$("#invScanBtn").onclick = () => openScanner("inventory");
$("#invScanBig").onclick = () => openScanner("inventory");
function invProductCard(name, image, sub, qty) {
  return `<div class="scanresult">
    ${image ? `<img src="${esc(image)}" alt="">` : ""}
    <div class="name"><span><b>${esc(name)}</b></span>${sub ? `<small>${sub}</small>` : ""}</div>
    <div style="text-align:center;flex:none"><div class="qtybig" id="scanQty">${qty}</div><div class="muted" style="font-size:11px">op voorraad</div></div>
  </div>`;
}
function continueScanning(wasLive) {
  if (!wasLive) return;
  setTimeout(() => { if (!$("#scanModal").classList.contains("hidden") && scan.target === "inventory") startLive(); }, 1200);
}
async function invOnCode(code, wasLive) {
  let r;
  try { r = await api("api/inventory/scan/" + code); }
  catch (err) { $("#scanResult").innerHTML = `<div class="hint">${esc(err.message)}</div>`; return; }
  const item = r.item, p = r.product;
  const again = () => { const b = $("#scanAgain"); if (b) b.onclick = () => { $("#scanResult").innerHTML = ""; startLive(); }; };

  if (!item && !p) {  // unknown barcode: let the user name it
    $("#scanResult").innerHTML = `<div class="hint" style="text-align:left;padding:10px 0 0">Barcode <b>${esc(code)}</b> is onbekend. <b>Wat is dit?</b> De volgende keer wordt hij herkend.</div>
      <form class="row" id="linkForm"><input type="text" id="linkName" placeholder="Naam, bijv. Zelfgemaakte jam" required><button class="btn">+1 opslaan</button></form>
      <div class="row"><input type="text" id="linkSearch" placeholder="…of zoek het AH-product"></div>
      <div id="linkResults"></div>
      <div class="row"><button class="btn ghost" id="scanAgain" style="flex:1">Overslaan, volgende scannen</button></div>`;
    again();
    $("#linkName").focus();
    const link = async (body) => {
      const res = await api("api/inventory/link", { gtin: code, delta: 1, ...body });
      invApply(res.item); loadInventory().catch(() => {});
      $("#scanResult").innerHTML = invProductCard(res.item.name, res.item.image, "Barcode gekoppeld", res.item.quantity)
        + `<div class="row"><button class="btn ghost" id="scanAgain" style="flex:1">Volgende scannen</button></div>`;
      again(); toast(`${res.item.name}: ${res.item.before} → ${res.item.quantity}`);
    };
    $("#linkForm").onsubmit = (e) => { e.preventDefault(); const n = $("#linkName").value.trim(); if (n) link({ name: n }).catch((err) => toast(err.message)); };
    let t; $("#linkSearch").oninput = () => {
      clearTimeout(t); const q = $("#linkSearch").value.trim();
      if (q.length < 2) { $("#linkResults").innerHTML = ""; return; }
      t = setTimeout(async () => {
        const { products } = await api("api/search?q=" + encodeURIComponent(q)).catch(() => ({ products: [] }));
        $("#linkResults").innerHTML = products.slice(0, 5).map((pr, i) => `<div class="srow">
            ${pr.image ? `<img class="thumb" src="${esc(pr.image)}" alt="">` : `<div class="ph"></div>`}
            <div class="name"><span>${esc(pr.title)}</span><small>${esc(pr.unit_size || "")}</small></div>
            <button class="add" data-li="${i}" aria-label="Kiezen">✓</button></div>`).join("");
        $("#linkResults").onclick = (e) => { const b = e.target.closest("[data-li]"); if (b) link({ product: products[+b.dataset.li] }).catch((err) => toast(err.message)); };
      }, 300);
    };
    return;
  }

  const name = item?.name || p.title, image = item?.image || p?.image;
  const sub = [esc(item?.unit_size || p?.unit_size || ""), (p?.price || item?.price) ? euro(p?.price || item?.price) : ""].filter(Boolean).join(" · ");
  const target = item ? { key: item.key } : { product: p };
  const mode = invMode();

  if (mode === "in" || mode === "out") {
    const delta = mode === "in" ? 1 : -1;
    if (delta < 0 && (!item || item.quantity <= 0)) {
      $("#scanResult").innerHTML = invProductCard(name, image, sub, item ? item.quantity : 0)
        + `<div class="hint">Niet op voorraad, niets afgeboekt.</div><div class="row"><button class="btn ghost" id="scanAgain" style="flex:1">Volgende scannen</button></div>`;
      again(); continueScanning(wasLive); return;
    }
    try {
      const res = await invChange("api/inventory/adjust", { ...target, delta, gtin: code });
      $("#scanResult").innerHTML = invProductCard(res.name, image, sub, res.quantity)
        + `<div class="row"><button class="btn ghost" id="scanAgain" style="flex:1">Volgende scannen</button></div>`;
      $("#scanQty").parentElement.parentElement.classList.add("flash");
      again();
      if (res.quantity === 0 && res.before > 0) emptyToast(res); else toast(`${res.name}: ${res.before} → ${res.quantity}`);
      continueScanning(wasLive);
    } catch (err) { $("#scanResult").innerHTML = `<div class="hint">${esc(err.message)}</div>`; }
    return;
  }

  // choose per scan: +1 / -1 / set
  $("#scanResult").innerHTML = invProductCard(name, image, sub, item ? item.quantity : 0) + `
    <div class="row">
      <button class="btn" data-sact="in" style="flex:1">+1 erbij</button>
      <button class="btn ghost" data-sact="out" style="flex:1" ${!item || item.quantity <= 0 ? "disabled" : ""}>−1 op</button>
    </div>
    <form class="row" id="setForm"><input type="number" min="0" inputmode="numeric" id="setQty" placeholder="Aantal tellen" value="${item ? item.quantity : ""}"><button class="btn ghost">Aantal opslaan</button></form>
    <div class="row"><button class="btn ghost" id="scanAgain" style="flex:1">Volgende scannen</button></div>`;
  again();
  let current = item ? { ...item } : null;
  const show = (res) => {
    current = res; $("#scanQty").textContent = res.quantity;
    $("#scanQty").parentElement.parentElement.classList.remove("flash"); void $("#scanQty").offsetWidth;
    $("#scanQty").parentElement.parentElement.classList.add("flash");
    $("[data-sact=out]").disabled = res.quantity <= 0; $("#setQty").value = res.quantity;
  };
  $("#scanResult").querySelectorAll("[data-sact]").forEach((b) => (b.onclick = async () => {
    const delta = b.dataset.sact === "in" ? 1 : -1;
    try {
      const res = await invChange("api/inventory/adjust", { ...(current ? { key: current.key } : target), delta, gtin: code });
      show(res);
      if (res.quantity === 0 && res.before > 0) emptyToast(res); else toast(`${res.name}: ${res.before} → ${res.quantity}`);
    } catch (err) { toast(err.message); }
  }));
  $("#setForm").onsubmit = async (e) => {
    e.preventDefault();
    const q = Math.max(0, parseInt($("#setQty").value, 10) || 0);
    try {
      let res;
      if (current) res = await invChange("api/inventory/set", { key: current.key, quantity: q });
      else { res = await invChange("api/inventory/adjust", { product: p, delta: q, gtin: code }); }
      show(res); toast(`${res.name}: ${res.quantity} op voorraad`);
    } catch (err) { toast(err.message); }
  };
}
