// ---------------- settings (in the account menu) ----------------
const SYNC_CHOICES = [15, 30, 60, 120, 300, 600, 900, 1800, 3600];
const SYNC_DEFAULT = 60;
const intervalLabel = (s) => s === 3600 ? "Elk uur" : s % 60 === 0 ? `Elke ${s / 60} min` : `Elke ${s} s`;
// the interval to go back to when automatic sync is switched on again
const lastInterval = {
  get() { try { return +localStorage.getItem("happie-sync-interval") || SYNC_DEFAULT; } catch (_) { return SYNC_DEFAULT; } },
  set(v) { try { localStorage.setItem("happie-sync-interval", String(v)); } catch (_) {} },
};

function renderSettings(interval) {
  const auto = interval > 0;
  $("#setAuto").checked = auto;
  for (const el of document.querySelectorAll("#accountMenu .setrow")) el.classList.toggle("hidden", !auto);
  const cur = auto ? interval : lastInterval.get();
  const choices = [...new Set([...SYNC_CHOICES, cur])].sort((a, b) => a - b);
  $("#setInterval").innerHTML = choices.map((v) => `<option value="${v}">${esc(intervalLabel(v))}</option>`).join("");
  $("#setInterval").value = String(cur);
  $("#setHelp").textContent = auto ? "" : "Wat je in de AH-app verandert, haal je op met Nu synchroniseren. Wijzigingen in Home Assistant gaan wel meteen naar AH.";
}
async function loadSettings() {
  try {
    const s = await api("api/settings");
    if (s.sync_interval > 0) lastInterval.set(s.sync_interval);
    renderSettings(s.sync_interval);
    $("#setAuto").closest(".switch").title = s.saved_in_ha ? "Wordt ook opgeslagen in de configuratie van de app" : "";
  } catch (err) { toast(err.message); }
}
async function saveInterval(interval) {
  $("#setAuto").disabled = $("#setInterval").disabled = true;
  try {
    await api("api/settings", { sync_interval: interval });
    if (interval > 0) lastInterval.set(interval);
    renderSettings(interval);
    toast(interval > 0 ? `Automatisch synchroniseren: ${intervalLabel(interval).toLowerCase()}` : "Automatisch synchroniseren uit");
    await loadStatus();
  } catch (err) { toast(err.message); await loadSettings(); }
  $("#setAuto").disabled = $("#setInterval").disabled = false;
}

// refresh each time the menu opens (it may have changed on the configuration page)
$("#accountChip").addEventListener("click", () => { if (!$("#accountMenu").classList.contains("hidden")) loadSettings(); });
$("#setAuto").addEventListener("change", () => saveInterval($("#setAuto").checked ? lastInterval.get() : 0));
$("#setInterval").addEventListener("change", () => saveInterval(+$("#setInterval").value));
