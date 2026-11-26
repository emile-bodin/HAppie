// ---------------- spending ----------------
let spend = null, spendPeriod = "week", spendSel = null;
let spendItems = null, spendRange = "12", spendSrc = "all", spendShown = 15, spendTopAll = false, spendItemsTimer = null;
const purchaseLines = {};  // purchase id -> {lines, discounts, deposit, total} (or a promise while loading)
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
  // don't redraw while a category is being picked: that would throw the open dropdown away
  if (!document.querySelector("#spCats .linkpick")) { renderSpendItems(); renderSpendInsights(); }
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
