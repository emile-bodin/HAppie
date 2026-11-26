// ---------------- list ----------------
function renderList() {
  renderStats();
  renderDiscover();
  if ($("#results").classList.contains("list") && lastResults.length) renderResults();
  const open = items.filter((i) => !i.checked), done = items.filter((i) => i.checked);
  $("#clearChecked").classList.toggle("hidden", !done.length);
  if (!items.length) {
    $("#list").innerHTML = `<div class="empty"><svg width="56" height="56" viewBox="0 0 24 24" fill="currentColor"><path d="M17 18a2 2 0 1 1 0 4 2 2 0 0 1 0-4M1 2h3.27l.94 2H20a1 1 0 0 1 1 1c0 .17-.05.34-.12.5l-3.58 6.47c-.34.61-1 1.03-1.75 1.03H8.1l-.9 1.63-.03.12a.25.25 0 0 0 .25.25H19v2H7a2 2 0 0 1-2-2c0-.35.09-.68.24-.96l1.36-2.45L3 4H1V2m6 16a2 2 0 1 1 0 4 2 2 0 0 1 0-4"/></svg>
      <div><b>Je lijst is leeg</b></div><div style="font-size:13px">Zoek een product of kies een suggestie.</div>
      <div class="actions"><button class="btn" data-goto="search">Product zoeken</button></div></div>`;
    return;
  }
  const groups = new Map();
  for (const i of open) {
    const cat = i.product?.category || "Overig";
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat).push(i);
  }
  let html = "";
  for (const [cat, list] of [...groups].sort((a, b) => (a[0] === "Overig") - (b[0] === "Overig") || a[0].localeCompare(b[0])))
    html += `<div class="group">${esc(cat)}</div><ul class="items">${list.map(row).join("")}</ul>`;
  if (done.length) html += `<div class="group">Afgevinkt</div><ul class="items">${done.map(row).join("")}</ul>`;
  $("#list").innerHTML = html;
}
function row(i) {
  const p = i.product, k = esc(i.key);
  const img = p?.image ? `<img class="thumb" src="${esc(p.image)}" alt="" loading="lazy">` : `<div class="ph" aria-hidden="true">${esc(initialOf(i.name))}</div>`;
  const bits = [];
  if (p?.unit_size) bits.push(esc(p.unit_size));
  const l = i.line, unit = p?.price_before || p?.price;
  if (l && unit) {
    // the calculation is hidden on a phone, where only the line total fits
    const reg = i.quantity > 1 ? `<span class="calc">${euro(unit)} × ${i.quantity} = </span>` : "";
    bits.push(l.applied
      ? `${reg}<s>${euro(l.regular)}</s> <b class="bonusprice">${euro(l.total)}</b>`
      : i.quantity > 1 ? `${reg}<b>${euro(l.total)}</b>` : euro(l.total));
  }
  if (p?.is_bonus) bits.push(`<span class="badge">${esc(bonusLabel(p.bonus))}</span>`);
  if (l?.hint && !i.checked) bits.push(`<span class="bonushint">${esc(bonusLabel(l.hint))}</span>`);
  return `<li class="${i.checked ? "checked" : ""}">
    <button class="chk ${i.checked ? "on" : ""}" data-act="check" data-key="${k}" aria-label="Afvinken">${i.checked ? ICON_CHECK : ""}</button>
    ${img}
    <div class="name"><span>${esc(i.name)}</span>${bits.length ? `<small>${bits.join("<span>·</span>")}</small>` : ""}</div>
    <div class="qty">
      <button data-act="dec" data-key="${k}" aria-label="Minder">${ICON_MINUS}</button><span>${i.quantity}</span><button data-act="inc" data-key="${k}" aria-label="Meer">${ICON_PLUS}</button>
    </div>
    <button class="del" data-act="del" data-key="${k}" aria-label="Verwijderen">${ICON_X}</button>
  </li>`;
}
async function loadList() {
  try { items = (await api("api/list")).items; }
  catch (err) {
    if (!err.data?.order_mode) throw err;
    items = []; renderStats(); renderDiscover(); $("#clearChecked").classList.add("hidden");
    $("#list").innerHTML = `<div class="empty"><div style="font-size:40px">🔒</div><div><b>Lijst tijdelijk vergrendeld</b></div>
      <div style="font-size:13px">Je bestelling staat open voor wijzigingen. Zodra je die afrondt in de AH-app, verschijnt je lijst hier weer.</div></div>`;
    return;
  }
  renderList();
}

$("#list").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-act]");
  if (!btn) return;
  const item = items.find((i) => i.key === btn.dataset.key);
  if (!item) return;
  try {
    if (btn.dataset.act === "check") {
      item.checked = !item.checked; renderList();
      await api("api/list/check", { key: item.key, checked: item.checked });
    } else if (btn.dataset.act === "inc" || btn.dataset.act === "dec") {
      const q = item.quantity + (btn.dataset.act === "inc" ? 1 : -1);
      if (q <= 0) return await removeWithUndo(item);
      item.quantity = q; renderList();
      await api("api/list/quantity", { key: item.key, quantity: q });
    } else if (btn.dataset.act === "del") {
      return await removeWithUndo(item);
    }
  } catch (err) { toast(err.message); }
  await loadList().catch(() => {});
});
// remove right away, with a way back in the toast instead of a confirmation first
async function removeWithUndo(item) {
  items = items.filter((i) => i !== item); renderList();
  try { await api("api/list/remove", { key: item.key }); }
  catch (err) { toast(err.message); await loadList().catch(() => {}); return; }
  toast(`${item.name} verwijderd`, { label: "Ongedaan maken", fn: async () => {
    try { await api("api/list/add", { name: item.name, product_id: item.product_id, quantity: item.quantity }); }
    catch (err) { toast(err.message); }
    await loadList().catch(() => {});
  } });
  await loadList().catch(() => {});
}
$("#list").addEventListener("click", (e) => { if (e.target.closest("[data-goto=search]")) goSearch(); });
function goSearch() { if (isPhone()) setTab("search"); else $("#searchInput").focus(); }
$("#clearChecked").onclick = async () => {
  const keys = items.filter((i) => i.checked).map((i) => i.key);
  items = items.filter((i) => !i.checked); renderList();
  try { await api("api/list/remove", { keys }); } catch (err) { toast(err.message); }
  await loadList().catch(() => {});
};
