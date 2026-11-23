// ---------------- suggestions ----------------
let discover = "foryou";
try { discover = localStorage.getItem("happie-discover") || "foryou"; } catch (_) {}
const DISCOVER_NOTE = {
  foryou: "Persoonlijke suggesties van AH, afgestemd op je lijst",
  frequent: "Uit je laatste online bestellingen",
  bonus: "Deze week in de bonus, voor jou",
};
// "on the list" is always derived from the current list, so it follows adds and removals
const onList = (p) => items.some((i) => i.product_id && i.product_id === p.id);
const pending = new Set();  // product ids being added right now
function srow(p, idx, extra = "") {
  const bits = [esc(p.unit_size || ""), p.price ? `<span class="price">${euro(p.price)}</span>` : "", extra,
                p.is_bonus ? `<span class="badge">${esc(bonusLabel(p.bonus))}</span>` : ""].filter(Boolean);
  const action = pending.has(p.id) ? `<span class="onlist"><span class="spinner"></span></span>`
    : onList(p) ? `<span class="onlist">✓ op lijst</span>`
    : `<button class="add" data-idx="${idx}" aria-label="Toevoegen: ${esc(p.title)}" title="Op de lijst" ${p.orderable === false ? "disabled" : ""}>+</button>`;
  return `<div class="srow">
    ${p.image ? `<img class="thumb" src="${esc(p.image)}" alt="" loading="lazy">` : `<div class="ph"></div>`}
    <div class="name"><span>${esc(p.title)}</span><small>${bits.join("<span>·</span>")}</small></div>
    ${action}
  </div>`;
}
let discoverData = null;  // {mode, ...data} of what's currently shown
function renderDiscover() {
  const d = discoverData;
  if (!d || d.mode !== discover) return;
  const scroll = $("#suggestions").parentElement.scrollTop;
  if (d.mode === "foryou") {
    suggestions = d.products;
    $("#suggestions").innerHTML = d.products.length ? d.products.map((p, i) => srow(p, i)).join("") : `<div class="hint">Geen suggesties op dit moment.</div>`;
  } else if (d.mode === "frequent") {
    suggestions = d.products;
    $("#suggestions").innerHTML = d.products.length
      ? d.products.map((p, i) => srow(p, i, `<span class="freq">${p.times}× in ${p.orders}</span>`)).join("")
      : `<div class="hint">Nog geen afgeleverde online bestellingen gevonden.</div>`;
  } else {
    const { personal, previously_bought } = d;
    suggestions = [...personal, ...previously_bought];
    let html = `<div class="subhead">Persoonlijke bonus</div>`;
    html += personal.length ? personal.map((p, i) => srow(p, i)).join("") : `<div class="hint" style="padding:8px 0;text-align:left">Deze week geen persoonlijke bonus.</div>`;
    html += `<div class="subhead">Eerder gekocht · nu in de bonus (${previously_bought.length})</div>`;
    html += previously_bought.map((p, i) => srow(p, personal.length + i)).join("") || `<div class="hint">Niets gevonden.</div>`;
    $("#suggestions").innerHTML = html;
  }
  $("#suggestions").parentElement.scrollTop = scroll;
}
async function loadSuggestions(refresh = false) {
  const mode = discover;
  document.querySelectorAll("#discoverTabs button").forEach((b) => b.classList.toggle("active", b.dataset.d === mode));
  $("#discoverNote").textContent = DISCOVER_NOTE[mode];
  if (!discoverData || discoverData.mode !== mode) $("#suggestions").innerHTML = `<div class="hint"><span class="spinner"></span></div>`;
  const q = refresh ? "?refresh=1" : "";
  try {
    let data;
    if (mode === "foryou") data = { products: (await api("api/suggestions")).products };
    else if (mode === "frequent") data = { products: (await api("api/frequent" + q)).products };
    else data = await api("api/bonus" + q);
    if (mode !== discover) return;
    discoverData = { mode, ...data };
    renderDiscover();
  } catch (err) { if (mode === discover) $("#suggestions").innerHTML = `<div class="hint">${esc(err.message)}</div>`; }
}
document.querySelectorAll("#discoverTabs button").forEach((b) => (b.onclick = () => {
  discover = b.dataset.d; suggestions = [];
  try { localStorage.setItem("happie-discover", discover); } catch (_) {}
  loadSuggestions();
}));
$("#suggestions").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-idx]");
  if (!btn) return;
  const p = suggestions[+btn.dataset.idx];
  pending.add(p.id); renderDiscover();
  try { await addItem(p.title, p.id, { keepSearch: true }); }  // reloads the list -> renderDiscover()
  finally { pending.delete(p.id); renderDiscover(); }
  if (discover === "foryou") loadSuggestions();  // AH adapts these to the list
});
$("#refreshSug").onclick = () => loadSuggestions(true);

async function addItem(name, productId, opts = {}) {
  if (opts.btn) { opts.btn.disabled = true; opts.btn.innerHTML = `<span class="spinner"></span>`; }
  try {
    await api("api/list/add", { name, product_id: productId, quantity: 1 });
    toast(`${name} toegevoegd`);
    if (!opts.keepSearch) { $("#searchInput").value = ""; $("#results").innerHTML = ""; renderFreeText(""); $("#searchHint").classList.remove("hidden"); }
    await loadList();
  } catch (err) { toast(err.message); }
  if (opts.btn) { opts.btn.disabled = false; opts.btn.textContent = "✓ Toegevoegd"; setTimeout(() => { opts.btn.textContent = "+ Toevoegen"; }, 1500); }
}
