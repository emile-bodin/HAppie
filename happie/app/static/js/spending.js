// ---------------- spending ----------------
let spend = null, spendPeriod = "week", spendSel = null;
let spendItems = null, spendRange = "12", spendSrc = "all", spendShown = 15, spendTopAll = false, spendItemsTimer = null;
const purchaseLines = {};  // purchase id -> lines (or a promise while loading)
const listCost = () => items.filter((i) => !i.checked).reduce((n, i) => n + (i.line ? i.line.total : 0), 0);
const shortDate = (d) => new Date(d + "T12:00:00").toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short" });
const spendPageOpen = () => document.body.dataset.view === "spend" && !$("#spendPage").classList.contains("hidden");
const euro0 = (n) => "€ " + Math.round(n);
const UNMATCHED = "Niet herkend";

async function loadSpending(refresh = false) {
  try { spend = await api(`api/spending?period=${spendPeriod}` + (refresh ? "&refresh=1" : "")); }
  catch (err) {
    if (spendPageOpen() && !spend) $("#spendChart").innerHTML = `<div class="hint">${esc(err.message)}</div>`;
    return;
  }
  renderSpendTile();
  if (spendPageOpen()) renderSpendPage();
}
async function loadSpendItems() {
  clearTimeout(spendItemsTimer);
  try { spendItems = await api(`api/spending/items?months=${spendRange}`); }
  catch (err) { $("#spTop").innerHTML = `<li class="hint">${esc(err.message)}</li>`; return; }
  if (!spendPageOpen()) return;
  renderSpendItems(); renderSpendInsights();
  // articles are fetched in the background: keep the page up to date while that runs
  if (spendItems.running) spendItemsTimer = setTimeout(() => { if (spendPageOpen()) loadSpendItems(); }, 8000);
}
function showSpendPage() {
  if (spend) renderSpendPage();
  if (spendItems) { renderSpendItems(); renderSpendInsights(); }
  loadSpending(); loadSpendItems();
}
function openSpendPage() {
  setView("spend");
  if (isPhone()) setTab("spend");
}

// budget with the live list cost (the server value lags behind until the next sync)
function budgetNow(which = "week") {
  const b = which === "month" ? spend?.summary?.month_budget : spend?.summary?.budget;
  if (!b) return null;
  const list = listCost(), spent = which === "month" ? spend.summary.this_month : spend.summary.this_week, projected = spent + list;
  return { budget: b.budget, spent, list, projected, remaining: b.budget - projected,
           over: projected > b.budget + 0.004, warn: projected > b.budget * 0.9 };
}
function renderSpendTile() {
  const s = spend.summary, b = budgetNow(), tile = $("#spendTile");
  $("#spVal").textContent = euro(s.this_week);
  tile.classList.toggle("over", !!b?.over);
  tile.classList.toggle("warn", !!b && !b.over && b.warn);
  $("#spBar").classList.toggle("hidden", !b);
  if (b) {
    $("#spLbl").textContent = b.over ? `${euro(-b.remaining)} boven budget` : `Nog ${euro(b.remaining)} over`;
    const max = Math.max(b.budget, b.projected) || 1;
    $("#spBarSpent").style.width = (b.spent / max * 100) + "%";
    $("#spBarList").style.width = (b.list / max * 100) + "%";
    tile.title = `Deze week ${euro(b.spent)} + lijst ${euro(b.list)} = ${euro(b.projected)} van ${euro(b.budget)}`;
  } else {
    $("#spLbl").textContent = "Uitgegeven deze week";
    tile.title = `Uitgavenoverzicht · vorige week ${euro(s.last_week)}`;
  }
  $("#spendBanner").innerHTML = b?.over && document.body.dataset.view === "shop"
    ? `<div class="banner error"><div><b>Boven je weekbudget.</b> Deze week ${euro(b.spent)} uitgegeven, met je lijst erbij ${euro(b.projected)}:
       ${euro(-b.remaining)} meer dan je budget van ${euro(b.budget)}.</div><button class="btn ghost sm" data-spend>Bekijk uitgaven</button></div>` : "";
}

// ---------------- chart ----------------
function niceStep(x) {
  const p = 10 ** Math.floor(Math.log10(x || 1));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= x) return m * p;
  return 10 * p;
}
const spendVisible = () => (spend ? spend.buckets.slice(-($("#spendChart").clientWidth < 480 ? 6 : 12)) : []);
const spendAvg = () => {
  const done = spend.buckets.slice(0, -1);
  return done.length ? done.reduce((n, x) => n + x.total, 0) / done.length : 0;
};
function spendChartSvg(buckets, budget, avg) {
  // draw at the real width, so text stays 11px on a phone instead of being scaled down
  const W = Math.max(280, Math.min(900, $("#spendChart").clientWidth || 680));
  const H = W < 480 ? 200 : 240, L = 46, R = 8, T = 12, B = 24, n = buckets.length || 1;
  const list = spendPeriod === "week" || spend.summary.month_budget ? listCost() : 0;
  const last = buckets[n - 1];
  const max = Math.max(1, ...buckets.map((b) => b.total), (last?.total || 0) + list, budget || 0);
  const step = niceStep(max / 4), top = Math.ceil(max / step) * step;
  const y = (v) => T + (H - T - B) * (1 - v / top);
  const bw = (W - L - R) / n;
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Uitgaven per ${spendPeriod === "week" ? "week" : "maand"}">`;
  for (let v = 0; v <= top + 0.001; v += step)
    svg += `<line class="gl" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text class="al" x="${L - 6}" y="${y(v) + 4}" text-anchor="end">€${Math.round(v)}</text>`;
  buckets.forEach((b, i) => {
    const x = L + i * bw, w = Math.min(bw * 0.62, 38), bx = x + (bw - w) / 2;
    const cur = i === n - 1;
    svg += `<g data-i="${i}" class="${spendSel === i ? "sel" : ""}"><rect class="hit" x="${x}" y="${T}" width="${bw}" height="${H - T - B}" rx="6"/>`;
    if (b.online) svg += `<rect class="b-online" x="${bx}" y="${y(b.online)}" width="${w}" height="${y(0) - y(b.online)}" rx="2"/>`;
    if (b.winkel) svg += `<rect class="b-winkel" x="${bx}" y="${y(b.online + b.winkel)}" width="${w}" height="${y(b.online) - y(b.online + b.winkel)}" rx="2"/>`;
    // what's on the list now comes on top of the current period
    if (cur && list > 0.004) svg += `<rect class="b-list" x="${bx}" y="${y(b.total + list)}" width="${w}" height="${y(b.total) - y(b.total + list)}" rx="2"/>`;
    const showLabel = bw >= 38 || (n - 1 - i) % 2 === 0;  // narrow: every other label, always the current one
    svg += (showLabel ? `<text class="al${cur ? " cur" : ""}" x="${x + bw / 2}" y="${H - 7}" text-anchor="middle">${esc(b.label)}</text>` : "") + "</g>";
  });
  if (avg) svg += `<line class="avgl" x1="${L}" x2="${W - R}" y1="${y(avg)}" y2="${y(avg)}"/>`;
  // budget on top of the bars, with a halo so it stays visible across them; its amount is in the legend
  if (budget) svg += `<line class="bl-halo" x1="${L}" x2="${W - R}" y1="${y(budget)}" y2="${y(budget)}"/><line class="bl" x1="${L}" x2="${W - R}" y1="${y(budget)}" y2="${y(budget)}"/>`;
  const sel = buckets[spendSel];
  if (sel?.total) svg += `<text class="vl" x="${L + spendSel * bw + bw / 2}" y="${Math.max(T + 10, y(sel.total) - 5)}" text-anchor="middle">€${Math.round(sel.total)}</text>`;
  return svg + "</svg>";
}
const spendTipRange = (b) => spendPeriod === "week"
  ? `${b.label} · ${shortDate(b.start)} – ${shortDate(b.end)}`
  : new Date(b.start + "T12:00:00").toLocaleDateString("nl-NL", { month: "long", year: "numeric" });
function spendTip(i) {
  const b = spendVisible()[i];
  if (!b) return "";
  const cell = (v, l, dot = "") => `<div>${dot ? `<i style="background:${dot}"></i>` : ""}<b>${v}</b><small>${l}</small></div>`;
  const cells = [cell(euro(b.online), "Online", "var(--brand)")];
  if (spend.receipts_ok !== false) cells.push(cell(euro(b.winkel), "Winkel", "var(--bonus)"));
  cells.push(cell(b.count, b.count === 1 ? "Aankoop" : "Aankopen"));
  return `<div class="tip-head"><span>${esc(spendTipRange(b))}</span><b>${euro(b.total)}</b></div><div class="tip-cells">${cells.join("")}</div>`;
}

// ---------------- page ----------------
function spendBudgetFor() {
  // the budget that goes with the chosen period: week budget per week, month budget per month
  if (spendPeriod === "month") return spend.summary.month_budget ? budgetNow("month") : null;
  return budgetNow("week");
}
function renderSpendPage() {
  const week = spendPeriod === "week", shown = spendVisible();
  document.querySelectorAll("#spendTabs button").forEach((x) => x.classList.toggle("active", x.dataset.p === spendPeriod));
  if (spendSel == null || spendSel >= shown.length) spendSel = shown.length - 1;
  const sel = shown[spendSel], prev = shown[spendSel - 1] || spend.buckets[spend.buckets.length - shown.length + spendSel - 1];
  const cur = spendSel === shown.length - 1, avg = spendAvg(), b = spendBudgetFor(), unit = week ? "week" : "maand";
  $("#spNavLbl").textContent = sel ? spendTipRange(sel) : "";
  $("#spPrev").disabled = spendSel <= 0; $("#spNext").disabled = cur;
  $("#spendFresh").innerHTML = `${spend.updated_at ? `Bijgewerkt ${ago(spend.updated_at)}` : "Nog niet opgehaald"}`
    + (spend.receipts_ok === false ? " · kassabonnen konden niet opgehaald worden" : "");

  // KPIs follow the chosen bar
  const delta = prev && prev.total ? (sel.total - prev.total) / prev.total * 100 : null;
  const deltaPill = delta == null ? "" : `<span class="delta ${delta > 0 ? "up" : "down"}">${delta > 0 ? "+" : ""}${Math.round(delta)}%</span>`;
  const online = sel && sel.total ? Math.round(sel.online / sel.total * 100) : 0;
  const stat = (lbl, val, sub, cls = "") => `<div class="stat ${cls}"><div style="min-width:0;flex:1"><div class="lbl">${lbl}</div><div class="val">${val}</div><div class="sub">${sub}</div></div></div>`;
  const kpis = [
    stat(cur ? `Uitgegeven deze ${unit}` : `Uitgegeven in ${esc(week ? sel.label : spendTipRange(sel))}`, euro(sel?.total || 0),
         prev ? `vorige ${unit} ${euro(prev.total)} ${deltaPill}` : "", "hero"),
  ];
  if (b && cur) kpis.push(stat("Budget over", `<span class="${b.over ? "neg" : "pos"}">${euro(b.remaining)}</span>`,
    `van ${euro(b.budget)}${b.list > 0.004 ? `, met lijst (${euro(b.list)})` : ""}`));
  kpis.push(stat(`Gemiddeld per ${unit}`, euro(avg), `over ${spend.buckets.length - 1} hele ${week ? "weken" : "maanden"}`));
  if (spend.receipts_ok !== false)
    kpis.push(stat("Online / winkel", `${online}% <small>online</small>`,
      `<span class="minibar"><i style="width:${online}%"></i><i class="w" style="width:${100 - online}%"></i></span>`));
  kpis.push(stat(sel?.count === 1 ? "Aankoop" : "Aankopen", sel?.count || 0, spendCountSub(sel)));
  $("#spendKpis").innerHTML = kpis.join("");

  $("#spChartTitle").textContent = `Uitgaven per ${unit}`;
  $("#spendChart").innerHTML = spendChartSvg(shown, b?.budget, avg);
  $("#spendTable").innerHTML = `<caption>Uitgaven per ${unit}</caption><tr><th>Periode</th><th>Totaal</th><th>Online</th><th>Winkel</th></tr>`
    + shown.map((x) => `<tr><td>${esc(spendTipRange(x))}</td><td>${euro(x.total)}</td><td>${euro(x.online)}</td><td>${euro(x.winkel)}</td></tr>`).join("");
  const leg = [`<span><i style="background:var(--brand)"></i>Online</span>`];
  if (spend.receipts_ok !== false) leg.push(`<span><i style="background:var(--bonus)"></i>Winkel</span>`);
  if (b && b.list > 0.004) leg.push(`<span><i class="lst"></i>Op je lijst</span>`);
  if (b) leg.push(`<span><i class="dash"></i>Budget ${euro0(b.budget)}</span>`);
  if (avg) leg.push(`<span><i class="dash avg"></i>Gemiddeld ${euro0(avg)}</span>`);
  $("#spendLegend").innerHTML = leg.join("");
  $("#spendTip").innerHTML = spendTip(spendSel);
  renderSpendBudget(); renderSpendPurchases(); renderSpendInsights();
}
function spendCountSub(sel) {
  if (!sel) return "";
  const ps = (spend.recent || []).filter((p) => p.date >= sel.start && p.date <= sel.end);
  const on = ps.filter((p) => p.source === "online").length, st = ps.length - on;
  const part = (n, one, many) => n ? `${n} ${n === 1 ? one : many}` : "";
  return [part(on, "bezorging", "bezorgingen"), part(st, "winkelbezoek", "winkelbezoeken")].filter(Boolean).join(", ") || "geen";
}
function renderSpendBudget() {
  const week = spendPeriod === "week", b = spendBudgetFor();
  const wb = spend.summary.budget?.budget, mb = spend.summary.month_budget?.budget;
  const where = `Instellingen › Apps › HAppie › Configuratie`;
  $("#spBudgetFor").textContent = b ? (week ? "deze week" : "deze maand") : "";
  if (!b) {
    $("#spendBudget").innerHTML = `<p class="muted sp-empty">${week
      ? "Stel een weekbudget in om te zien hoeveel je deze week nog kunt uitgeven, met je lijst erbij."
      : "Stel een maandbudget in om te zien hoeveel je deze maand nog kunt uitgeven, met je lijst erbij."}
      Dat doe je bij ${where} (<code>${week ? "week_budget" : "month_budget"}</code>).</p>`;
    return;
  }
  const C = 2 * Math.PI * 52, f = (v) => Math.max(0, Math.min(v / b.budget, 1)) * C;
  const state = b.over ? "over" : b.warn ? "warn" : "ok";
  const ring = `<div class="ring ${state}"><svg viewBox="0 0 120 120" aria-hidden="true"><circle class="track" cx="60" cy="60" r="52"/>
      <circle class="proj" cx="60" cy="60" r="52" stroke-dasharray="${f(b.projected)} ${C}"/>
      <circle class="spent" cx="60" cy="60" r="52" stroke-dasharray="${f(b.spent)} ${C}"/></svg>
      <div class="center"><b>${Math.round(b.projected / b.budget * 100)}%</b><small>van ${euro0(b.budget)}</small></div></div>`;
  const dl = `<dl class="bdl"><dt><i class="sw spent"></i>Uitgegeven</dt><dd>${euro(b.spent)}</dd>
      <dt><i class="sw proj"></i>Op je lijst</dt><dd>${euro(b.list)}</dd><hr>
      <dt>Prognose</dt><dd>${euro(b.projected)}</dd><dt>Over</dt><dd class="${b.over ? "neg" : "pos"}">${euro(b.remaining)}</dd></dl>`;
  const rest = week ? "de rest van de week" : "de rest van de maand";
  const msg = b.over ? `<b>Boven budget.</b> Haal ${euro(-b.remaining)} van je lijst af om binnen te blijven.`
    : b.warn ? `<b>Bijna op.</b> Nog ${euro(b.remaining)} voor ${rest}.`
    : `<b>Op koers.</b> Je houdt naar verwachting ${euro(b.remaining)} over.`;
  // complete periods before this one, against the budget
  const past = spend.buckets.slice(-9, -1);
  const inBudget = past.filter((x) => x.total <= b.budget + 0.004).length;
  const streak = past.map((x) => `<span class="${x.total > b.budget + 0.004 ? "out" : "in"}" title="${esc(spendTipRange(x))}: ${euro(x.total)}">${esc(week ? x.label.replace("wk ", "") : x.label)}</span>`).join("")
    + `<span class="now" title="Loopt nog">nu</span>`;
  $("#spendBudget").innerHTML = `<div class="ringwrap">${ring}${dl}</div><div class="sp-banner ${state}">${msg}</div>
    <div class="sp-streak-lbl">${inBudget} van de laatste ${past.length} ${week ? "weken" : "maanden"} binnen budget</div>
    <div class="sp-streak">${streak}</div>
    <div class="sp-budgetset">${wb ? `Weekbudget <b>${euro0(wb)}</b>` : "Geen weekbudget"} · ${mb ? `Maandbudget <b>${euro0(mb)}</b>` : "geen maandbudget"}
      <br><span class="muted">Wijzigen bij ${where}.</span></div>`;
}

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
function purchaseLinesHtml(id) {
  const lines = purchaseLines[id];
  if (!lines || lines instanceof Promise) return `<div class="hint"><span class="spinner"></span></div>`;
  if (lines.error) return `<div class="hint">${esc(lines.error)}</div>`;
  return `<ul class="sp-sub-list">${lines.map((l) => `<li>${thumb(l.image)}
      <div class="nm"><span>${esc(l.name)}</span><small>${l.quantity !== 1 ? `${+l.quantity.toFixed(2)}× · ` : ""}${esc(l.category)}${l.category === UNMATCHED || l.receipt_name === l.name ? "" : ` · bon: ${esc(l.receipt_name)}`}</small></div>
      <b>${l.amount == null ? "" : euro(l.amount)}</b></li>`).join("")}</ul>
    ${lines.some((l) => l.amount == null) ? `<div class="sp-note">AH geeft bij bestellingen geen prijs per artikel.</div>` : ""}`;
}
async function loadPurchaseLines(id) {
  if (purchaseLines[id] && !purchaseLines[id].error) return;
  purchaseLines[id] = api(`api/spending/purchase/${encodeURIComponent(id)}`)
    .then((r) => r.lines).catch((err) => ({ error: err.message }));
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
$("#spendTile").onclick = openSpendPage;
$("#spendBanner").addEventListener("click", (e) => { if (e.target.closest("[data-spend]")) openSpendPage(); });
$("#spendTabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-p]");
  if (!btn || btn.dataset.p === spendPeriod) return;
  spendPeriod = btn.dataset.p; spendSel = null; loadSpending();
});
$("#spPrev").onclick = () => { if (spendSel > 0) { spendSel--; renderSpendPage(); } };
$("#spNext").onclick = () => { if (spendSel < spendVisible().length - 1) { spendSel++; renderSpendPage(); } };
$("#spendChart").addEventListener("click", (e) => {
  const g = e.target.closest("g[data-i]");
  if (!g || !spend) return;
  spendSel = +g.dataset.i; renderSpendPage();
});
$("#spendChart").addEventListener("mouseover", (e) => {
  const g = e.target.closest("g[data-i]");
  if (g && spend) $("#spendTip").innerHTML = spendTip(+g.dataset.i);
});
$("#spendChart").addEventListener("mouseleave", () => { if (spend) $("#spendTip").innerHTML = spendTip(spendSel); });
let spendResizeW = 0;
window.addEventListener("resize", () => {
  const w = $("#spendChart").clientWidth;
  if (spend && spendPageOpen() && w !== spendResizeW) { spendResizeW = w; renderSpendPage(); }
});
$("#spendRefresh").onclick = async () => {
  const btn = $("#spendRefresh"); btn.disabled = true;
  await loadSpending(true); await loadSpendItems(); btn.disabled = false;
};
$("#spRange").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-r]");
  if (!btn || btn.dataset.r === spendRange) return;
  spendRange = btn.dataset.r; loadSpendItems();
});
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
    link.replaceWith(sel); sel.focus();
    return;
  }
  if (unlink) {
    unlink.disabled = true;
    try { await api("api/spending/link", { key: unlink.dataset.unlink, category: "" }); await loadSpendItems(); }
    catch (err) { toast(err.message); unlink.disabled = false; }
  }
});
$("#spCats").addEventListener("change", async (e) => {
  const sel = e.target.closest("select.linksel");
  if (!sel || !sel.value) return;
  sel.disabled = true;
  try {
    await api("api/spending/link", { key: sel.dataset.key, category: sel.value });
    toast(`Gekoppeld aan ${sel.value}`);
    await loadSpendItems();
  } catch (err) { toast(err.message); sel.disabled = false; }
});
