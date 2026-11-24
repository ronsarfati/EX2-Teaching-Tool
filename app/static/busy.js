// Busy feedback: a long request (photo count, LLM call, upload) must not look frozen or be submitted twice. Runs after validation (video.js).
document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!form.hasAttribute("data-busy") || event.defaultPrevented) return;
  const button = form.querySelector("button[type=submit]");
  button.setAttribute("aria-busy", "true"); // Pico draws the spinner
  button.disabled = true;
});
// Safari's back/forward cache restores the page with the button still busy: undo it.
window.addEventListener("pageshow", (event) => {
  if (!event.persisted) return;
  for (const b of document.querySelectorAll("form[data-busy] button[type=submit]")) {
    b.removeAttribute("aria-busy"); b.disabled = false;
  }
});
