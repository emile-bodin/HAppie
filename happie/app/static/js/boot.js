// ---------------- boot ----------------
async function refresh() {
  await loadStatus();
  if (status.logged_in) await loadList().catch((e) => toast(e.message));
}
try { const v = localStorage.getItem("happie-view"); if (v === "inv" && !matchMedia("(max-width: 767px)").matches) document.body.dataset.view = "inv"; } catch (_) {}
if (document.body.dataset.view !== "inv") document.body.dataset.view = document.body.dataset.tab === "inv" ? "inv" : "shop";
refresh().then(() => {
  if (!status.logged_in) return;
  loadSuggestions(); loadDelivery(); loadSpending();
  setView(document.body.dataset.view);
}).catch((e) => toast(e.message));
setInterval(() => {
  if (document.hidden) return;
  refresh().catch(() => {});
  if (document.body.dataset.view === "inv" && status.logged_in) loadInventory().catch(() => {});
}, 20000);
setInterval(() => { if (!document.hidden && status.logged_in) { loadDelivery(); loadSpending(); } }, 300000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh().catch(() => {}); });
