// RemoteGenerationService — Alpine.js components and utilities

// HTMX configuration
document.addEventListener("DOMContentLoaded", () => {
  // Show loading indicator during HTMX requests
  document.body.addEventListener("htmx:beforeRequest", () => {
    document.querySelectorAll("[hx-indicator]").forEach((el) => el.classList.add("loading"));
  });
  document.body.addEventListener("htmx:afterRequest", () => {
    document.querySelectorAll("[hx-indicator]").forEach((el) => el.classList.remove("loading"));
  });
});

// Clipboard utility
function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    // Brief visual feedback
    const el = document.activeElement;
    if (el) {
      const orig = el.textContent;
      el.textContent = "Copied!";
      setTimeout(() => (el.textContent = orig), 1200);
    }
  });
}
