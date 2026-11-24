// ---------------- spending ----------------
let spend = null, spendPeriod = "week", spendSel = null;
const listCost = () => items.filter((i) => !i.checked).reduce((n, i) => n + (i.line ? i.line.total : 0), 0);
const shortDate = (d) => new Date(d + "T12:00:00").toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short" });
async function loadSpending(refresh = false) {
  try { spend = await api(`api/spending?period=${spendPeriod}` + (refresh ? "&refresh=1" : "")); }
  catch (err) {
    $("#spVal").textContent = "–"; $("#spLbl").textContent = "Uitgaven niet beschikbaar"; $("#spendTile").title = err.message;
    if (!$("#spendModal").classList.contains("hidden")) $("#spendChart").innerHTML = `<div class="hint">${esc(err.message)}</div>`;
    return;
  }
  renderSpendTile();
  if (!$("#spendModal").classList.contains("hidden")) renderSpendModal();
}
// budget with the live list cost (the server value lags behind until the next sync)
function budgetNow() {
  const b = spend?.summary?.budget;
  if (!b) return null;
  const list = listCost(), spent = spend.summary.this_week, projected = spent + list;
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
  $("#spendBanner").innerHTML = b?.over && document.body.dataset.view !== "inv"
    ? `<div class="banner error"><div><b>Boven je weekbudget.</b> Deze week ${euro(b.spent)} uitgegeven, met je lijst erbij ${euro(b.projected)}:
       ${euro(-b.remaining)} meer dan je budget van ${euro(b.budget)}.</div><button class="btn ghost sm" data-spend>Bekijk uitgaven</button></div>` : "";
}
function niceStep(x) {
  const p = 10 ** Math.floor(Math.log10(x || 1));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= x) return m * p;
  return 10 * p;
}
const spendVisible = () => (spend ? spend.buckets.slice(-($("#spendChart").clientWidth < 480 ? 6 : 12)) : []);
function spendChartSvg(buckets, budget) {
  // draw at the real width, so text stays 11px on a phone instead of being scaled down
  const W = Math.max(280, Math.min(680, $("#spendChart").clientWidth || 680));
  const H = W < 480 ? 200 : 230, L = 46, R = 8, T = 12, B = 24, n = buckets.length || 1;
  const max = Math.max(1, ...buckets.map((b) => b.total), budget || 0);
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
    if (b.online) svg += `<rect class="b-online" x="${bx}" y="${y(b.online)}" width="${w}" height="${y(0) - y(b.online)}" rx="2"${cur ? ' opacity=".75"' : ""}/>`;
    if (b.winkel) svg += `<rect class="b-winkel" x="${bx}" y="${y(b.online + b.winkel)}" width="${w}" height="${y(b.online) - y(b.online + b.winkel)}" rx="2"${cur ? ' opacity=".75"' : ""}/>`;
    const showLabel = bw >= 38 || (n - 1 - i) % 2 === 0;  // narrow: every other label, always the current one
    svg += (showLabel ? `<text class="al${cur ? " cur" : ""}" x="${x + bw / 2}" y="${H - 7}" text-anchor="middle">${esc(b.label)}</text>` : "") + "</g>";
  });
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
function renderSpendModal() {
  const s = spend.summary, b = budgetNow(), week = spendPeriod === "week";
  document.querySelectorAll("#spendTabs button").forEach((x) => x.classList.toggle("active", x.dataset.p === spendPeriod));
  // cards follow the chosen period; the average covers the complete periods in the chart
  const done = spend.buckets.slice(0, -1);
  const avg = done.length ? done.reduce((n, x) => n + x.total, 0) / done.length : 0;
  const kpi = (v, l, t = "") => `<div title="${esc(t)}"><b>${euro(v)}</b><small>${l}</small></div>`;
  $("#spendKpis").innerHTML = week
    ? kpi(s.this_week, "Deze week") + kpi(s.last_week, "Vorige week") + kpi(avg, "Gemiddeld per week", `Over de laatste ${done.length} hele weken`)
    : kpi(s.this_month, "Deze maand") + kpi(s.last_month, "Vorige maand") + kpi(avg, "Gemiddeld per maand", `Over de laatste ${done.length} hele maanden`);
  $("#spendFresh").innerHTML = `<span>${spend.updated_at ? `Bijgewerkt ${ago(spend.updated_at)}` : "Nog niet opgehaald"}</span>`
    + `<button class="btn ghost sm" data-spend-refresh>Nu bijwerken</button>`;
  const shown = spendVisible();
  if (spendSel == null || spendSel >= shown.length) spendSel = shown.length - 1;
  $("#spendChart").innerHTML = spendChartSvg(shown, week && b ? b.budget : null);
  $("#spendTable").innerHTML = `<caption>Uitgaven per ${week ? "week" : "maand"}</caption><tr><th>Periode</th><th>Totaal</th><th>Online</th><th>Winkel</th></tr>`
    + shown.map((x) => `<tr><td>${esc(spendTipRange(x))}</td><td>${euro(x.total)}</td><td>${euro(x.online)}</td><td>${euro(x.winkel)}</td></tr>`).join("");
  const leg = [`<span><i style="background:var(--brand)"></i>Online bestellingen</span>`];
  if (spend.receipts_ok !== false) leg.push(`<span><i style="background:var(--bonus)"></i>Winkel (kassabonnen)</span>`);
  if (spendPeriod === "week" && b) leg.push(`<span><i class="dash"></i>Weekbudget ${euro(b.budget)}</span>`);
  $("#spendLegend").innerHTML = leg.join("");
  $("#spendTip").innerHTML = spendTip(spendSel);
  const pct = (v) => (Math.min(v, Math.max(b.budget, b.projected)) / (Math.max(b.budget, b.projected) || 1) * 100).toFixed(1) + "%";
  $("#spendBudget").innerHTML = b
    ? `<div class="budgetbox ${b.over ? "over" : b.warn ? "warn" : ""}">
         <div class="bb-head"><span>Weekbudget</span><b>${b.over ? `${euro(-b.remaining)} boven budget` : `Nog ${euro(b.remaining)} over`}</b></div>
         <div class="budgetbar"><i style="width:${pct(b.spent)}"></i><i class="list" style="width:${pct(b.list)}"></i></div>
         <div class="bb-foot"><span>Uitgegeven ${euro(b.spent)} + lijst ${euro(b.list)}</span><span>${euro(b.projected)} van ${euro(b.budget)}</span></div></div>`
    : `<div class="muted" style="font-size:13px;margin-top:8px">Wil je zien hoeveel je deze week nog kunt uitgeven? Stel een weekbudget in bij de instellingen van HAppie (Instellingen › Apps › HAppie › Configuratie).</div>`;
  $("#spendRecent").innerHTML = (spend.recent || []).map((p) =>
    `<li><span>${esc(shortDate(p.date))}<span class="src ${p.source}">${p.source === "online" ? "online" : "winkel"}</span></span><b>${euro(p.total)}</b></li>`).join("")
    || `<li class="muted">Nog geen aankopen gevonden.</li>`;
  $("#spendNote").textContent = spend.receipts_ok === false
    ? "Kassabonnen konden niet opgehaald worden; je ziet alleen online bestellingen." : "";
}
function openSpending() {
  $("#spendModal").classList.remove("hidden");
  if (spend) renderSpendModal();
  loadSpending();
}
const closeSpending = () => $("#spendModal").classList.add("hidden");
$("#spendTile").onclick = openSpending;
$("#spendClose").onclick = closeSpending;
$("#spendModal").addEventListener("click", (e) => { if (e.target.id === "spendModal") closeSpending(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#spendModal").classList.contains("hidden")) closeSpending(); });
$("#spendBanner").addEventListener("click", (e) => { if (e.target.closest("[data-spend]")) openSpending(); });
$("#spendTabs").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-p]");
  if (!btn || btn.dataset.p === spendPeriod) return;
  spendPeriod = btn.dataset.p; spendSel = null; loadSpending();
});
$("#spendChart").addEventListener("click", (e) => {
  const g = e.target.closest("g[data-i]");
  if (!g || !spend) return;
  spendSel = +g.dataset.i; renderSpendModal();
});
$("#spendChart").addEventListener("mouseover", (e) => {
  const g = e.target.closest("g[data-i]");
  if (g && spend) $("#spendTip").innerHTML = spendTip(+g.dataset.i);
});
window.addEventListener("resize", () => { if (spend && !$("#spendModal").classList.contains("hidden")) renderSpendModal(); });
$("#spendChart").addEventListener("mouseleave", () => { if (spend) $("#spendTip").innerHTML = spendTip(spendSel); });
$("#spendRefresh").onclick = async () => {
  const btn = $("#spendRefresh"); btn.disabled = true;
  await loadSpending(true); btn.disabled = false;
};
$("#spendFresh").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-spend-refresh]");
  if (!btn) return;
  btn.disabled = true; btn.innerHTML = `<span class="spinner"></span>`;
  await loadSpending(true);
});
