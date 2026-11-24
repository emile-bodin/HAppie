// view switching (desktop/tablet switch, phone tab)
const VIEW_TITLES = { inv: "HAppie · Voorraad", spend: "HAppie · Uitgaven" };
const viewForTab = (tab) => (tab === "inv" || tab === "spend" ? tab : "shop");
function setView(view) {
  document.body.dataset.view = view;
  document.querySelectorAll("#viewSwitch button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  $("#brandTitle").textContent = VIEW_TITLES[view] || "HAppie";
  try { localStorage.setItem("happie-view", view); } catch (_) {}
  if (view === "inv" && status.logged_in !== undefined) {
    loadInventory().catch((e) => toast(e.message));
    loadOrders();
  }
  if (view === "spend" && status.logged_in) showSpendPage();
}
document.querySelectorAll("#viewSwitch button").forEach((b) => (b.onclick = () => {
  setView(b.dataset.view);
  if (matchMedia("(max-width: 767px)").matches) setTab(b.dataset.view === "shop" ? "list" : b.dataset.view);
}));

// ---------------- tabs (phone) + keyboard ----------------
function setTab(tab) {
  document.body.dataset.tab = tab;
  // on a phone the tab bar decides the view; on larger screens the header switch does
  const view = viewForTab(tab);
  if (matchMedia("(max-width: 767px)").matches && document.body.dataset.view !== view) setView(view);
  document.querySelectorAll(".tabbar button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  try { localStorage.setItem("happie-tab", tab); } catch (_) {}
  if (tab === "search") setTimeout(() => $("#searchInput").focus(), 50);
  window.scrollTo(0, 0);
}
document.querySelectorAll(".tabbar button").forEach((b) => (b.onclick = () => setTab(b.dataset.tab)));
try { const t = localStorage.getItem("happie-tab"); if (t && t !== "search") setTab(t); } catch (_) {}
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && !/input|textarea/i.test(document.activeElement.tagName)) {
    e.preventDefault();
    if (matchMedia("(max-width: 767px)").matches) setTab("search"); else $("#searchInput").focus();
  }
});
