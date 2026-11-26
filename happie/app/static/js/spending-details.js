// ---------------- spending: purchases, products, categories, insights ----------------
// lists on the Uitgaven page; state and loading live in spending.js

// ---------------- purchases ----------------
const ICON_ONLINE = `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M18 18.5a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3m1.5-9 1.96 2.5H17V9.5M6 18.5a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3M20 8h-3V4H3a2 2 0 0 0-2 2v11h2a3 3 0 0 0 3 3 3 3 0 0 0 3-3h6a3 3 0 0 0 3 3 3 3 0 0 0 3-3h2v-5z"/></svg>`;
const ICON_STORE = `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M4 4h16l1 5a3 3 0 0 1-5 2 3 3 0 0 1-4 0 3 3 0 0 1-4 0 3 3 0 0 1-5-2zm1 9h14v7H5z"/></svg>`;
function renderSpendPurchases() {
  document.querySelectorAll("#spSrc button").forEach((x) => x.classList.toggle("active", x.dataset.s === spendSrc));
  const all = (spend.recent || []).filter((p) => spendSrc === "all" || p.source === spendSrc);
  const open = new Set([...document.querySelectorAll("#spendRecent details[open]")].map((d) => d.dataset.id));
  $("#spendRecent").innerHTML = all.length ? all.slice(0, spendShown).map((p) =>
    `<details class="sp-row purchase" data-id="${esc(p.id)}"${open.has(p.id) ? " open" : ""}><summary>
       <span class="pico ${p.source}">${p.source === "online" ? ICON_ONLINE : ICON_STORE}</span>
       <span class="ptxt"><b>${p.source === "online" ? "Bezorging" : "Winkel"}</b><small>${esc(shortDate(p.date))}</small></span>
       <b class="pamt">${euro(p.total)}</b><span class="chev" aria-hidden="true">›</span></summary>
       <div class="plines">${purchaseLinesHtml(p.id)}</div></details>`).join("")
    + (all.length > spendShown ? `<button class="btn ghost sm sp-more" data-more-purchases>Meer aankopen (${all.length - spendShown})</button>` : "")
    : `<p class="muted sp-empty">Nog geen aankopen gevonden.</p>`;
  $("#spendNote").textContent = spend.receipts_ok === false ? "Kassabonnen konden niet opgehaald worden; je ziet alleen online bestellingen." : "";
}
const signedEuro = (n) => (n < 0 ? "−" : "") + euro(Math.abs(n));
// a receipt line: its price after its own bonus, the price before it struck through
function lineAmountHtml(l) {
  if (l.amount == null) return "";
  if (l.gross == null || !l.bonus) return euro(l.gross ?? l.amount);
  return `<s class="was">${euro(l.gross)}</s>${euro(l.gross + l.bonus)}`;
}
function purchaseLinesHtml(id) {
  const p = purchaseLines[id];
  if (!p || p instanceof Promise) return `<div class="hint"><span class="spinner"></span></div>`;
  if (p.error) return `<div class="hint">${esc(p.error)}</div>`;
  const lines = p.lines;
  const extra = (label, amount, cls = "") => `<li class="extra ${cls}"><span class="nm"><span>${label}</span></span><b>${amount}</b></li>`;
  const receipt = lines.some((l) => l.gross != null);
  return `<ul class="sp-sub-list">${lines.map((l) => `<li>${thumb(l.image)}
      <div class="nm"><span>${esc(l.name)}</span><small>${l.quantity !== 1 ? `${+l.quantity.toFixed(2)}× · ` : ""}${l.bonus ? `<span class="tag bonus">Bonus</span> ` : ""}${esc(l.category)}${l.category === UNMATCHED || l.receipt_name === l.name ? "" : ` · bon: ${esc(l.receipt_name)}`}</small></div>
      <b class="amt">${lineAmountHtml(l)}</b></li>`).join("")}
    ${(p.discounts || []).map((d) => extra(`Korting <small>${esc(d.name)}</small>`, signedEuro(d.amount))).join("")}
    ${p.deposit ? extra("Statiegeld", euro(p.deposit)) : ""}
    ${receipt && p.total != null ? extra("Betaald", euro(p.total), "sum") : ""}</ul>
    ${lines.some((l) => l.amount == null) ? `<div class="sp-note">AH geeft bij bestellingen geen prijs per artikel.</div>` : ""}`;
}
async function loadPurchaseLines(id) {
  if (purchaseLines[id] && !purchaseLines[id].error) return;
  purchaseLines[id] = api(`api/spending/purchase/${encodeURIComponent(id)}`)
    .catch((err) => ({ error: err.message }));
  purchaseLines[id] = await purchaseLines[id];
  // the list may have been drawn again meanwhile: look the row up now
  const box = document.querySelector(`#spendRecent details[data-id="${CSS.escape(id)}"] .plines`);
  if (box) box.innerHTML = purchaseLinesHtml(id);
}
const thumb = (img) => img ? `<img class="thumb" src="${esc(img)}" alt="" loading="lazy">` : `<span class="thumb ph"></span>`;

// ---------------- products + categories ----------------
function renderSpendItems() {
  const d = spendItems;
  document.querySelectorAll("#spRange button").forEach((x) => x.classList.toggle("active", x.dataset.r === spendRange));
  const range = spendRange === "3" ? "laatste 3 maanden" : "laatste 12 maanden";
  $("#spCatsFor").textContent = range;
  const progress = d.total && d.covered < d.total ? `Artikelen van ${d.covered} van de ${d.total} aankopen opgehaald${d.running ? "; de rest volgt" : ""}.` : "";
  const top = spendTopAll ? d.top : d.top.slice(0, 10);
  const maxT = Math.max(1, ...d.top.map((r) => r.times));
  $("#spTop").innerHTML = top.length ? top.map((r, i) => {
    const p = r.product || {};
    const tags = (p.is_bonus ? `<span class="tag bonus">${esc(bonusLabel(p.bonus))}</span>` : "") + (r.due ? `<span class="tag due">Bijna op?</span>` : "");
    return `<li>${thumb(p.image)}<div class="nm"><span>${esc(r.name)}</span>
        <small>${r.times}× gekocht${r.quantity > r.times ? ` · ${+r.quantity.toFixed(1)} st` : ""}${r.interval ? ` · elke ~${r.interval} dagen` : ""}</small>
        ${tags ? `<span class="tags">${tags}</span>` : ""}<span class="freq"><i style="width:${r.times / maxT * 100}%"></i></span></div>
      <div class="right"><b title="${r.estimated ? "Schatting met de huidige prijs" : "Betaald"}">${r.estimated ? "± " : ""}${euro(r.amount)}</b>
        ${p.id ? `<button class="addbtn${r.due ? " due" : ""}" data-add="${i}">+ Lijst</button>` : ""}</div></li>`;
  }).join("") : `<li class="hint">${d.running || d.total ? "Artikelen worden opgehaald…" : "Nog geen aankopen gevonden."}</li>`;
  $("#spItemsNote").innerHTML = [
    d.top.length > 10 ? `<button class="btn ghost sm" data-top-all>${spendTopAll ? "Minder tonen" : `Alle ${d.top.length} tonen`}</button>` : "",
    `<span>Bestellingen en kassabonnen samen. Bij bestellingen is het bedrag een schatting met de huidige prijs.</span>`,
    progress ? `<span>${progress}</span>` : "",
  ].join("");

  const open = new Set([...document.querySelectorAll("#spCats details[open]")].map((x) => x.dataset.cat));
  const maxA = Math.max(1, ...d.categories.map((c) => c.amount));
  $("#spCats").innerHTML = d.categories.length ? d.categories.map((c) => {
    const unm = c.name === UNMATCHED, w = c.amount > 0 ? Math.round(c.winkel / c.amount * 100) : 0;
    const rows = unm ? d.unmatched : c.items;
    return `<details class="sp-row cat${unm ? " unm" : ""}" data-cat="${esc(c.name)}"${open.has(c.name) ? " open" : ""}><summary>
        <span class="cname"><span class="chev" aria-hidden="true">›</span>${esc(c.name)}</span><span class="camt">${c.share < 1 ? "<1" : Math.round(c.share)}% · ${euro0(c.amount)}</span>
        <span class="cbar" title="online ${100 - w}%, winkel ${w}%"><i style="width:${c.amount / maxA * 100}%;--w:${100 - w}%"></i></span></summary>
      <ul class="sp-sub-list">${rows.map((r) => catRow(r, unm)).join("")}
        ${!unm && c.count > rows.length ? `<li class="more">en nog ${c.count - rows.length} andere producten</li>` : ""}</ul>
      ${unm ? `<div class="sp-note">Bonregels zonder AH-product, zoals statiegeld of tasjes. Met Koppel kies je zelf de categorie.</div>` : ""}</details>`;
  }).join("") + `<div class="legend"><span><i style="background:var(--brand)"></i>Online</span><span><i style="background:var(--bonus)"></i>Winkel</span></div>`
    : `<p class="muted sp-empty">${d.running ? "Artikelen worden opgehaald…" : "Nog geen artikelen."}</p>`;
}
function catRow(r, unm) {
  const src = (r.online ? `<span class="src online">online ${r.online}×</span>` : "") + (r.winkel ? `<span class="src winkel">winkel ${r.winkel}×</span>` : "");
  const linked = r.key.startsWith("r:") && !unm;
  const action = unm
    ? `<button class="addbtn" data-link="${esc(r.key)}" data-guess="${esc(r.guess || "")}">Koppel</button>`
    : linked ? `<button class="addbtn" data-unlink="${esc(r.key)}" title="Koppeling weghalen">Ontkoppel</button>` : "";
  return `<li>${unm || linked ? `<span class="thumb ph rc">🧾</span>` : thumb(r.product?.image)}
    <div class="nm"><span class="${unm ? "mono" : ""}">${esc(r.name)}</span><small>${r.times}× gekocht ${src}${unm ? ` · laatst ${esc(shortDate(r.last))}` : ""}</small></div>
    <div class="right"><b>${r.estimated ? "± " : ""}${euro(r.amount)}</b>${action}</div></li>`;
}

// ---------------- insights ----------------
function renderSpendInsights() {
  if (!spend) return;
  const s = spend.summary, out = [], today = new Date();
  const ins = (e, html) => out.push(`<div class="insight"><span class="e" aria-hidden="true">${e}</span><span>${html}</span></div>`);
  const day = today.getDate(), dim = new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate();
  if (day >= 5 && s.this_month) {
    const proj = s.this_month / day * dim, mb = s.month_budget?.budget;
    ins("📈", `Deze maand kom je op koers voor <b>${euro0(proj)}</b>` + (mb ? (proj > mb ? `: ${euro0(proj - mb)} boven je maandbudget.` : `: ${euro0(mb - proj)} onder je maandbudget.`) : "."));
  }
  const iso = (d) => d.toISOString().slice(0, 10);
  const since56 = iso(new Date(Date.now() - 56 * 864e5)), since90 = iso(new Date(Date.now() - 90 * 864e5));
  const store = (spend.recent || []).filter((p) => p.source === "winkel" && p.date >= since56);
  if (store.length) ins("🛒", `Winkelbezoeken kosten je gemiddeld <b>${euro0(store.reduce((n, p) => n + p.total, 0) / 8)} per week</b> (${(store.length / 8).toFixed(1).replace(".", ",")} keer per week).`);
  const orders = (spend.recent || []).filter((p) => p.source === "online" && p.date >= since90);
  if (orders.length) ins("📦", `Een bezorging kost gemiddeld <b>${euro(orders.reduce((n, p) => n + p.total, 0) / orders.length)}</b> (${orders.length} in de laatste 3 maanden).`);
  const bonus = spendItems?.top.find((r) => r.product?.is_bonus && r.times >= 3);
  if (bonus) ins("🏷️", `<b>${esc(bonus.name)}</b> is nu in de bonus (${esc(bonusLabel(bonus.product.bonus))}) en je koopt het ${bonus.interval ? `elke ~${bonus.interval} dagen` : "vaak"}.`);
  const due = spendItems?.top.filter((r) => r.due).slice(0, 3);
  if (due?.length) ins("⏰", `Mogelijk bijna op: ${due.map((r) => `<b>${esc(r.name)}</b>`).join(", ")}.`);
  $("#spInsights").innerHTML = out.join("") || `<p class="muted sp-empty">Nog te weinig aankopen voor inzichten.</p>`;
  const wd = spendItems?.weekday;
  const maxW = Math.max(1, ...(wd || [1]));
  $("#spHeat").innerHTML = wd ? ["ma", "di", "wo", "do", "vr", "za", "zo"].map((l, i) =>
    `<div><span>${l}</span><b style="--p:${Math.round(wd[i] / maxW * 80) + 6}%">${euro0(wd[i])}</b></div>`).join("") : "";
}

// ---------------- events ----------------
$("#spSrc").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-s]");
  if (!btn || btn.dataset.s === spendSrc) return;
  spendSrc = btn.dataset.s; spendShown = 15; renderSpendPurchases();
});
$("#spendRecent").addEventListener("click", (e) => {
  if (e.target.closest("[data-more-purchases]")) { spendShown += 20; renderSpendPurchases(); }
});
$("#spendRecent").addEventListener("toggle", (e) => {
  const d = e.target;
  if (d.matches?.("details.purchase") && d.open) loadPurchaseLines(d.dataset.id);
}, true);
$("#spTop").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-add]");
  if (!btn) return;
  const r = spendItems.top[+btn.dataset.add];
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>`;
  await addItem(r.product.title || r.name, r.product.id, { keepSearch: true });
  btn.textContent = "✓ Op lijst";
});
$("#spItemsNote").addEventListener("click", (e) => {
  if (e.target.closest("[data-top-all]")) { spendTopAll = !spendTopAll; renderSpendItems(); }
});
$("#spCats").addEventListener("click", async (e) => {
  const link = e.target.closest("button[data-link]"), unlink = e.target.closest("button[data-unlink]");
  if (link) {
    const names = spendItems.category_names, guess = link.dataset.guess;
    const sel = document.createElement("select");
    sel.className = "linksel"; sel.setAttribute("aria-label", "Kies een categorie");
    sel.innerHTML = `<option value="">Kies categorie…</option>` + names.map((n) => `<option${n === guess ? " selected" : ""}>${esc(n)}</option>`).join("")
      + (guess && !names.includes(guess) ? `<option selected>${esc(guess)}</option>` : "");
    sel.dataset.key = link.dataset.link;
    // the guess is often right already: confirm it with the button (choosing it again fires no change event)
    const ok = document.createElement("button");
    ok.className = "addbtn"; ok.dataset.confirm = ""; ok.textContent = "Koppel";
    const pick = document.createElement("span");
    pick.className = "linkpick"; pick.append(sel, ok);
    link.replaceWith(pick); sel.focus();
    return;
  }
  const okBtn = e.target.closest("button[data-confirm]");
  if (okBtn) return linkCategory(okBtn.previousElementSibling);
  if (unlink) {
    unlink.disabled = true;
    try { await api("api/spending/link", { key: unlink.dataset.unlink, category: "" }); await loadSpendItems(); }
    catch (err) { toast(err.message); unlink.disabled = false; }
  }
});
$("#spCats").addEventListener("change", (e) => {
  const sel = e.target.closest("select.linksel");
  if (sel) linkCategory(sel);
});
async function linkCategory(sel) {
  if (!sel || !sel.value) { sel?.focus(); return; }
  const ok = sel.nextElementSibling;
  sel.disabled = true; if (ok) ok.disabled = true;
  try {
    await api("api/spending/link", { key: sel.dataset.key, category: sel.value });
    toast(`Gekoppeld aan ${sel.value}`);
    await loadSpendItems();
  } catch (err) { toast(err.message); sel.disabled = false; if (ok) ok.disabled = false; }
}
