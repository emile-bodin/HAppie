// ---------------- search ----------------
let searchTimer, searchSeq = 0;
$("#searchInput").addEventListener("input", () => {
  clearTimeout(searchTimer);
  const q = $("#searchInput").value.trim();
  renderFreeText(q);
  $("#searchHint").classList.toggle("hidden", !!q);
  if (q.length < 2) { $("#results").innerHTML = ""; return; }
  searchTimer = setTimeout(() => doSearch(q), 300);
});
$("#searchForm").addEventListener("submit", (e) => { e.preventDefault(); const q = $("#searchInput").value.trim(); if (q) addItem(q, null); });
function renderFreeText(q) {
  const el = $("#freeText");
  el.classList.toggle("hidden", !q);
  el.innerHTML = q ? `<a id="addFree">+ “${esc(q)}” als losse tekst</a> <span class="muted">(Enter)</span>` : "";
  const a = $("#addFree"); if (a) a.onclick = () => addItem(q, null);
}
function productCard(p, idx, label = "+ Toevoegen") {
  label = typeof label === "string" ? label : "+ Toevoegen";
  return `<div class="product">
    ${p.is_bonus ? `<span class="badge">${esc(bonusLabel(p.bonus))}</span>` : ""}
    ${p.image ? `<img src="${esc(p.image)}" alt="" loading="lazy">` : ""}
    <div class="title">${esc(p.title)}</div>
    <div class="meta">${esc(p.unit_size || "")}</div>
    <div class="price">${euro(p.price)}${p.is_bonus && p.price_before && p.price_before !== p.price ? `<s>${euro(p.price_before)}</s>` : ""}</div>
    <button class="btn" data-idx="${idx}" aria-label="${esc(label.replace(/^\+\s*/, ""))}: ${esc(p.title)}" ${p.orderable === false && label === "+ Toevoegen" ? "disabled title='Niet leverbaar'" : ""}>${label}</button>
  </div>`;
}
async function doSearch(q) {
  const seq = ++searchSeq;
  $("#results").innerHTML = `<div class="muted"><span class="spinner"></span> Zoeken…</div>`;
  try {
    const { products } = await api("api/search?q=" + encodeURIComponent(q));
    if (seq !== searchSeq) return;
    lastResults = products;
    renderResults();
  } catch (err) { if (seq === searchSeq) $("#results").innerHTML = `<div class="muted">${esc(err.message)}</div>`; }
}
// cards on larger screens, one product per line on a phone
function renderResults() {
  const el = $("#results"), phone = isPhone();
  el.classList.toggle("list", phone);
  el.innerHTML = lastResults.length
    ? lastResults.map((p, i) => (phone ? srow(p, i) : productCard(p, i))).join("")
    : `<div class="muted">Niets gevonden.</div>`;
}
matchMedia("(max-width: 767px)").addEventListener("change", () => { if (lastResults.length && $("#searchInput").value.trim()) renderResults(); });
$("#results").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-idx]");
  if (!btn) return;
  const p = lastResults[+btn.dataset.idx];
  if (!btn.classList.contains("add")) return addItem(p.title, p.id, { keepSearch: true, btn });
  pending.add(p.id); renderResults();
  try { await addItem(p.title, p.id, { keepSearch: true }); }
  finally { pending.delete(p.id); if (lastResults.includes(p)) renderResults(); }
});
