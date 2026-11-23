// Polls the server every second (D31) and shows the current QR and 3-digit code.
// The image is only replaced when it changed, so it does not flicker between rotations.
const POLL_MS = 1000;
const qrImg = document.getElementById("qr");
const codeEl = document.getElementById("code");
const waitingEl = document.getElementById("waiting");

function show(state) {
  const open = state.open;
  qrImg.hidden = !open;
  codeEl.hidden = !open;
  waitingEl.hidden = open;
  if (!open) return;
  if (qrImg.src !== state.qr) qrImg.src = state.qr;
  codeEl.textContent = state.code;
}

async function poll() {
  try {
    const response = await fetch(document.body.dataset.api, { cache: "no-store" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    show(await response.json());
  } catch (error) {
    // Keep the last QR on screen over a network blip, but tell the lecturer.
    waitingEl.textContent = "Connection problem, retrying...";
    waitingEl.hidden = false;
  }
}

poll();
setInterval(poll, POLL_MS);
