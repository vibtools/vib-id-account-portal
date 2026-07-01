(() => {
  "use strict";

  const navToggle = document.querySelector("[data-nav-toggle]");
  const mobileNav = document.getElementById("mobile-nav");
  if (navToggle && mobileNav) {
    navToggle.addEventListener("click", () => {
      const expanded = navToggle.getAttribute("aria-expanded") === "true";
      navToggle.setAttribute("aria-expanded", String(!expanded));
      mobileNav.hidden = expanded;
    });
  }

  const preferencesForm = document.querySelector("[data-preferences-form]");
  if (preferencesForm) {
    preferencesForm.querySelectorAll('input[name="theme"]').forEach((input) => {
      input.addEventListener("change", (event) => {
        const target = event.currentTarget;
        if (target instanceof HTMLInputElement) {
          document.documentElement.dataset.theme = target.value;
        }
      });
    });
  }

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const message = form.getAttribute("data-confirm");
      if (message && !window.confirm(message)) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll("[data-auto-submit]").forEach((control) => {
    control.addEventListener("change", () => {
      if (control instanceof HTMLSelectElement && control.form) {
        control.form.requestSubmit();
      }
    });
  });
})();
