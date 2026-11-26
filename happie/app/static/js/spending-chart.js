// ---------------- spending: chart ----------------
// bar chart of the Uitgaven page; state and loading live in spending.js
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
  const unit = spendPeriod === "week" ? "week" : "maand";
  const label = `Uitgaven per ${unit}` + (n > 1 ? `, ${buckets[0].label} tot ${last.label}` : "")
    + (last ? `, laatste ${unit} ${euro(last.total)}` : "") + (avg ? `, gemiddeld ${euro(avg)}` : "") + (budget ? `, budget ${euro(budget)}` : "");
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">`;
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

// chart events
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
