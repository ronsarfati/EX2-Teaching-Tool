// Polls the server every second (D31) and shows the current QR and 4-digit code.
// The image is only replaced when it changed, so it does not flicker between rotations.
const POLL_MS = 1000;
const qrImg = document.getElementById("qr");
const codeEl = document.getElementById("code");
const waitingEl = document.getElementById("waiting");
const hintEl = document.getElementById("waiting-hint");
const qrBox = document.getElementById("qr-box");
const stepsEl = document.getElementById("steps");
const errorEl = document.getElementById("projector-error");
const fullscreenLink = document.getElementById("fullscreen");

function show(state) {
  const open = state.open;
  qrImg.hidden = !open;
  codeEl.hidden = !open;
  waitingEl.hidden = open;
  hintEl.hidden = open;
  qrBox.hidden = !open;
  stepsEl.hidden = !open;
  if (!open) return;
  if (qrImg.src !== state.qr) qrImg.src = state.qr;
  codeEl.textContent = state.code;
}

async function poll() {
  try {
    const response = await fetch(document.body.dataset.api, { cache: "no-store" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    show(await response.json());
    errorEl.hidden = true;
  } catch (error) {
    // Keep the last QR on screen over a connection blip: the error has its own element,
    // so the "No session is open." text is never overwritten and returns after a success.
    errorEl.hidden = false;
  }
}

fullscreenLink.addEventListener("click", (event) => {
  event.preventDefault();
  document.documentElement.requestFullscreen();
});

poll();
setInterval(poll, POLL_MS);
