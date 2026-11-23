// Polls the job status every 3 s (D4) and reloads the page once the job has ended.
const POLL_MS = 3000;
const labelEl = document.getElementById("job-label");
const progressEl = document.getElementById("job-progress");
const errorEl = document.getElementById("job-error");

async function poll() {
  try {
    const response = await fetch(document.body.dataset.api, { cache: "no-store" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    const data = await response.json();
    if (data.finished) {
      location.reload(); // the server renders the summary or the failure message
      return;
    }
    labelEl.textContent = data.label;
    progressEl.textContent = data.status === "transcribing" ? data.progress + " %" : "";
    errorEl.hidden = true;
  } catch (error) {
    errorEl.hidden = false; // keep the last status, tell the lecturer
  }
}

setInterval(poll, POLL_MS);
