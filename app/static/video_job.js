// Polls the job status every 3 s (D4) and reloads the page once the job has ended.
const POLL_MS = 3000;
const labelEl = document.getElementById("job-label");
const progressEl = document.getElementById("job-progress"); // a <progress> element
const errorEl = document.getElementById("job-error");

function showProgress(data) {
  if (data.status === "transcribing") {
    progressEl.max = 100;
    progressEl.value = data.progress;
  } else {
    progressEl.removeAttribute("value"); // no value = indeterminate animation
  }
}

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
    showProgress(data);
    errorEl.hidden = true;
  } catch (error) {
    errorEl.hidden = false; // keep the last status, tell the lecturer
  }
}

setInterval(poll, POLL_MS);
