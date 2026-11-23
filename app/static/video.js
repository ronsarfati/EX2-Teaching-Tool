// UX only: refuse a file above the limit before sending it. The server enforces the real limit.
const form = document.getElementById("video-form");
const errorEl = document.getElementById("video-error");

form.addEventListener("submit", (event) => {
  const file = form.elements.video.files[0];
  if (file && file.size > Number(form.dataset.maxBytes)) {
    event.preventDefault();
    errorEl.textContent = form.dataset.tooLarge;
    errorEl.hidden = false;
  }
});
