// ---------------- status / account ----------------
const STATE = {
  ok: ["ok", "Verbonden"], expired: ["bad", "Sessie verlopen"], unknown: ["busy", "Verbonden (naam onbekend)"], logged_out: ["", "Niet ingelogd"],
};
async function loadStatus() {
  status = await api("api/status");
  const st = status.account_state || (status.logged_in ? "ok" : "logged_out");
  const [dotCls, stateTxt] = STATE[st] || STATE.unknown;
  const name = status.account?.name || (status.logged_in ? "AH-account" : "Niet ingelogd");

  for (const id of ["#avatar", "#menuAvatar"]) $(id).textContent = status.logged_in ? initials(status.account?.name) : "?";
  $("#accName").textContent = status.account?.first_name || name;
  $("#menuName").textContent = name;
  $("#accDot").className = "dot " + dotCls;
  $("#accState").textContent = stateTxt;
  $("#menuState").innerHTML = `<span class="dot ${dotCls}"></span>${esc(stateTxt)}`;
  $("#menuHa").innerHTML = status.ha_connected
    ? `<span class="dot ${status.todo_exists === false ? "bad" : "ok"}"></span><code>${esc(status.todo_entity)}</code>`
    : `<span class="dot"></span>Niet verbonden`;
  $("#menuSync").textContent = status.logged_in ? ago(status.last_sync) : "–";
  $("#menuLogout").classList.toggle("hidden", !status.logged_in);
  $("#menuSyncBtn").classList.toggle("hidden", !status.logged_in);
  $("#menuLogin").classList.toggle("hidden", status.logged_in && st !== "expired");
  $("#accountChip").title = `${name} · ${stateTxt}`;

  const syncBad = !!status.last_error;
  $("#syncChip").classList.toggle("hidden", !status.logged_in);
  $("#syncDot").className = "dot " + (syncBad ? "bad" : status.order_mode ? "busy" : "ok");
  $("#syncTxt").textContent = syncBad ? "Sync-fout" : status.order_mode ? "Sync gepauzeerd" : "Sync " + ago(status.last_sync);

  const showLogin = !status.logged_in || forceLogin;
  $("#loginView").classList.toggle("hidden", !showLogin);
  $("#loginTitle").textContent = st === "expired" ? "Je AH-sessie is verlopen" : "Koppel je Albert Heijn-account";
  $("#loginCancel").classList.toggle("hidden", !status.logged_in);
  for (const id of ["#stats", "#grid", "#tabbar", "#invStats", "#invGrid", "#spendPage", "#viewSwitch"]) $(id).classList.toggle("hidden", showLogin);
  $("#loginLink").href = status.login_url;

  const b = [];
  if (st === "expired" && !showLogin)
    b.push(`<div class="banner error"><div><b>Je AH-sessie is verlopen.</b> De sync staat stil tot je opnieuw inlogt.</div><button class="btn sm" data-relogin>Opnieuw inloggen</button></div>`);
  else if (status.last_error && !showLogin) b.push(`<div class="banner error"><div><b>Sync-fout:</b> ${esc(status.last_error)}</div></div>`);
  if (status.order_mode && !showLogin)
    b.push(`<div class="banner"><div><b>Je bestelling staat open voor wijzigingen.</b> Zolang dat zo is, vergrendelt AH je boodschappenlijst.
      De sync is gepauzeerd en er wordt niets verwijderd. Rond je wijzigingen af in de AH-app (of annuleer ze), dan gaat alles vanzelf verder.</div></div>`);
  if (status.ha_connected && status.todo_exists === false)
    b.push(`<div class="banner"><div><b>To-do-lijst <code>${esc(status.todo_entity)}</code> niet gevonden.</b>
      Maak hem aan via Instellingen › Apparaten &amp; diensten › Integratie toevoegen › <i>Lokale to-do</i>.</div></div>`);
  for (const w of status.warnings || []) b.push(`<div class="banner"><div>${esc(w)}</div></div>`);
  $("#banners").innerHTML = b.join("");
}
$("#banners").addEventListener("click", (e) => { if (e.target.closest("[data-relogin]")) showLoginView(); });
function showLoginView() { forceLogin = true; closeMenu(); loadStatus(); window.scrollTo(0, 0); }
$("#loginCancel").onclick = () => { forceLogin = false; loadStatus(); };

function closeMenu() { $("#accountMenu").classList.add("hidden"); }
$("#accountChip").onclick = (e) => { e.stopPropagation(); $("#accountMenu").classList.toggle("hidden"); };
document.addEventListener("click", (e) => { if (!e.target.closest("#accountMenu")) closeMenu(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMenu(); });
$("#menuLogin").onclick = showLoginView;
$("#menuLogout").onclick = async () => {
  if (!confirm("Wil je je AH-account ontkoppelen? De sync stopt dan.")) return;
  closeMenu(); await api("api/logout", {}); items = []; await refresh();
};
async function syncNow() {
  $("#syncIco").outerHTML = `<span id="syncIco" class="spinner"></span>`;
  try { await api("api/sync", {}); toast("Gesynchroniseerd"); } catch (err) { toast(err.message); }
  loadDelivery(true);
  $("#syncIco").outerHTML = `<svg id="syncIco" width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4V1L8 5l4 4V6a6 6 0 0 1 6 6 6 6 0 0 1-.7 2.8l1.46 1.46A8 8 0 0 0 20 12a8 8 0 0 0-8-8m0 14a6 6 0 0 1-6-6c0-1 .25-1.97.7-2.8L5.24 7.74A8 8 0 0 0 4 12a8 8 0 0 0 8 8v3l4-4-4-4z"/></svg>`;
  await refresh();
}
$("#syncChip").onclick = syncNow;
$("#menuSyncBtn").onclick = () => { closeMenu(); syncNow(); };

// ---------------- stats ----------------
function renderStats() {
  const open = items.filter((i) => !i.checked);
  const done = items.length - open.length;
  let cost = 0, saving = 0, unknown = 0, bonus = 0;
  for (const i of open) {
    if (i.line) { cost += i.line.total; saving += i.line.saving; } else unknown++;
    if (i.product?.is_bonus) bonus++;
  }
  $("#stOpen").textContent = open.reduce((n, i) => n + i.quantity, 0);
  $("#stCost").textContent = euro(cost).replace(",00", ",–");
  const lbl = [];
  if (saving > 0.004) lbl.push(`−${euro(saving)} bonus`);
  if (unknown) lbl.push(`+${unknown} zonder prijs`);
  $("#stCostLbl").textContent = lbl.length ? lbl.join(" · ") : "Geschatte kosten";
  $("#stCostLbl").title = saving > 0.004 ? `Inclusief ${euro(saving)} bonusvoordeel` : "";
  $("#stBonus").textContent = bonus;
  $("#stDone").textContent = `${done}/${items.length}`;
  $("#stProg").style.width = items.length ? (done / items.length * 100) + "%" : "0";
  $("#listCount").textContent = open.length;
  $("#tabCount").textContent = open.length;
  $("#tabCount").classList.toggle("hidden", !open.length);
  if (spend) renderSpendTile();
}
