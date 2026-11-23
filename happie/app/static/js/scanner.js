// ---------------- barcode scanner ----------------
// Live camera via the native BarcodeDetector (Chrome/Android) or ZXing (Safari/iOS, loaded on demand).
// Falls back to taking a photo (works inside the HA app/iframe) or typing the code.
const ZXING_URL = "https://unpkg.com/@zxing/library@0.21.3/umd/index.min.js";
const BARCODE_FORMATS = ["ean_13", "ean_8", "upc_a", "upc_e"];
let scan = { stream: null, timer: null, zxing: null, busy: false };

function loadZXing() {
  if (window.ZXing) return Promise.resolve(window.ZXing);
  return new Promise((ok, fail) => {
    const s = document.createElement("script");
    s.src = ZXING_URL; s.onload = () => ok(window.ZXing); s.onerror = () => fail(new Error("Barcodebibliotheek laden mislukt"));
    document.head.appendChild(s);
  });
}
async function nativeDetector() {
  if (!("BarcodeDetector" in window)) return null;
  try {
    const supported = await BarcodeDetector.getSupportedFormats();
    const formats = BARCODE_FORMATS.filter((f) => supported.includes(f));
    return formats.length ? new BarcodeDetector({ formats }) : null;
  } catch (_) { return null; }
}
function scanUI(live, msg) {
  $("#scanVideo").classList.toggle("hidden", !live);
  $("#scanFrame").classList.toggle("hidden", !live);
  $("#scanLaser").classList.toggle("hidden", !live);
  $("#scanMsg").classList.toggle("hidden", !!live);
  if (msg) $("#scanMsg").innerHTML = msg;
}
function stopScan() {
  clearInterval(scan.timer); scan.timer = null;
  if (scan.zxing) { try { scan.zxing.reset(); } catch (_) {} scan.zxing = null; }
  if (scan.stream) { scan.stream.getTracks().forEach((t) => t.stop()); scan.stream = null; }
}
const MODE_LABEL = { choose: "", in: "Inruimen +1", out: "Verbruiken −1" };
function scanTitle() {
  if (scan.target !== "inventory") return "Barcode scannen";
  const m = invMode();
  return `Scannen naar voorraad${m !== "choose" ? `<span class="modebadge ${m}">${MODE_LABEL[m]}</span>` : ""}`;
}
async function openScanner(target = "list") {
  scan.target = target;
  $("#scanTitle").innerHTML = scanTitle();
  $("#scanModal").classList.remove("hidden");
  $("#scanResult").innerHTML = ""; $("#scanCode").value = "";
  await startLive();
}
function closeScanner() { stopScan(); $("#scanModal").classList.add("hidden"); }
async function startLive() {
  stopScan();
  scanUI(false, "Camera starten…");
  if (!navigator.mediaDevices?.getUserMedia || !window.isSecureContext) {
    scanUI(false, "Live scannen kan hier niet (camera alleen via https).<br>Maak een foto van de barcode, of typ hem in.");
    return;
  }
  const video = $("#scanVideo");
  try {
    const detector = await nativeDetector();
    if (detector) {
      scan.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      video.srcObject = scan.stream; await video.play();
      scanUI(true);
      scan.timer = setInterval(async () => {
        if (scan.busy || video.readyState < 2) return;
        scan.busy = true;
        try { const codes = await detector.detect(video); if (codes.length) onCode(codes[0].rawValue); } catch (_) {}
        scan.busy = false;
      }, 250);
    } else {
      const ZX = await loadZXing();
      scan.zxing = new ZX.BrowserMultiFormatReader();
      scanUI(true);
      await scan.zxing.decodeFromConstraints({ video: { facingMode: "environment" } }, video, (result) => { if (result) onCode(result.getText()); });
    }
  } catch (err) {
    stopScan();
    const denied = err && (err.name === "NotAllowedError" || err.name === "SecurityError");
    scanUI(false, denied ? "Geen toegang tot de camera.<br>Maak een foto van de barcode, of typ hem in."
                         : `Camera niet beschikbaar (${esc(err.message || err.name || err)}).<br>Maak een foto, of typ de barcode in.`);
  }
}
async function decodePhoto(file) {
  scanUI(false, `<span class="spinner"></span> Barcode zoeken in foto…`);
  try {
    const detector = await nativeDetector();
    if (detector) {
      const codes = await detector.detect(await createImageBitmap(file));
      if (codes.length) return onCode(codes[0].rawValue);
    } else {
      const ZX = await loadZXing();
      const url = URL.createObjectURL(file);
      try { const r = await new ZX.BrowserMultiFormatReader().decodeFromImageUrl(url); return onCode(r.getText()); }
      finally { URL.revokeObjectURL(url); }
    }
    throw new Error("geen barcode");
  } catch (_) {
    scanUI(false, "Geen barcode gevonden in de foto.<br>Probeer het van dichterbij en scherp, of typ de code in.");
  }
}
async function onCode(code) {
  code = String(code || "").replace(/\D/g, "");
  if (!code) return;
  const wasLive = !!(scan.stream || scan.zxing);
  stopScan();
  if (navigator.vibrate) navigator.vibrate(60);
  $("#scanCode").value = code;
  scanUI(false, `Barcode <b>${esc(code)}</b>`);
  $("#scanResult").innerHTML = `<div class="hint"><span class="spinner"></span> Product opzoeken…</div>`;
  if (scan.target === "inventory") return invOnCode(code, wasLive);
  try {
    const { product: p } = await api("api/barcode/" + code);
    if (!p) {
      $("#scanResult").innerHTML = `<div class="hint">Barcode ${esc(code)} is niet bekend bij AH.</div>
        <div class="row"><button class="btn ghost" id="scanAgain" style="flex:1">Opnieuw scannen</button></div>`;
    } else {
      scan.product = p;
      $("#scanResult").innerHTML = `<div class="scanresult">
          ${p.image ? `<img src="${esc(p.image)}" alt="">` : ""}
          <div class="name"><span><b>${esc(p.title)}</b></span><small>${[esc(p.unit_size || ""), p.price ? `<span class="price">${euro(p.price)}</span>` : "", p.is_bonus ? `<span class="badge">${esc(bonusLabel(p.bonus))}</span>` : ""].filter(Boolean).join("<span>·</span>")}</small></div>
        </div>
        <div class="row"><button class="btn" id="scanAdd" style="flex:2">+ Op de lijst</button><button class="btn ghost" id="scanAgain" style="flex:1">Nog een</button></div>`;
      $("#scanAdd").onclick = async () => { await addItem(p.title, p.id, { keepSearch: true }); $("#scanAdd").textContent = "✓ Toegevoegd"; $("#scanAdd").disabled = true; };
    }
    const again = $("#scanAgain"); if (again) again.onclick = () => { $("#scanResult").innerHTML = ""; startLive(); };
  } catch (err) { $("#scanResult").innerHTML = `<div class="hint">${esc(err.message)}</div>`; }
}
$("#scanBtn").onclick = () => openScanner("list");
$("#scanClose").onclick = closeScanner;
$("#scanModal").addEventListener("click", (e) => { if (e.target.id === "scanModal") closeScanner(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#scanModal").classList.contains("hidden")) closeScanner(); });
$("#scanPhoto").addEventListener("change", (e) => { const f = e.target.files[0]; if (f) { stopScan(); decodePhoto(f); } e.target.value = ""; });
$("#scanManual").addEventListener("submit", (e) => { e.preventDefault(); onCode($("#scanCode").value); });
