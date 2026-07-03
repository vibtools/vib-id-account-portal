(() => {
  "use strict";

  const body = document.body;

  document.querySelectorAll(".brand").forEach((brand) => {
    const images = Array.from(brand.querySelectorAll(".brand-image"));
    if (!images.length) return;
    const updateFallback = () => {
      const usable = images.some((image) => image instanceof HTMLImageElement && image.complete && image.naturalWidth > 0);
      brand.classList.toggle("brand-load-failed", !usable);
    };
    images.forEach((image) => {
      image.addEventListener("load", updateFallback);
      image.addEventListener("error", updateFallback);
    });
    window.requestAnimationFrame(updateFallback);
  });
  const navToggle = document.querySelector("[data-nav-toggle]");
  const sidebar = document.querySelector("[data-sidebar]");
  const navClose = document.querySelector("[data-nav-close]");
  const mobileQuery = window.matchMedia("(max-width: 920px)");

  const closeNavigation = () => {
    if (!sidebar || !navToggle) return;
    sidebar.classList.remove("is-open");
    sidebar.hidden = mobileQuery.matches;
    navToggle.setAttribute("aria-expanded", "false");
    navToggle.setAttribute("aria-label", "Open navigation");
    if (navClose) {
      navClose.classList.remove("is-open");
      navClose.hidden = true;
    }
    body.classList.remove("nav-open");
  };

  const openNavigation = () => {
    if (!sidebar || !navToggle) return;
    sidebar.hidden = false;
    sidebar.classList.add("is-open");
    navToggle.setAttribute("aria-expanded", "true");
    navToggle.setAttribute("aria-label", "Close navigation");
    if (navClose) {
      navClose.hidden = false;
      navClose.classList.add("is-open");
    }
    body.classList.add("nav-open");
    const current = sidebar.querySelector('[aria-current="page"]');
    if (current instanceof HTMLElement) current.focus({ preventScroll: true });
  };

  const syncNavigation = () => {
    if (!sidebar || !navToggle) return;
    if (mobileQuery.matches) {
      closeNavigation();
    } else {
      sidebar.hidden = false;
      sidebar.classList.remove("is-open");
      navToggle.setAttribute("aria-expanded", "false");
      if (navClose) {
        navClose.hidden = true;
        navClose.classList.remove("is-open");
      }
      body.classList.remove("nav-open");
    }
  };

  if (navToggle && sidebar) {
    navToggle.addEventListener("click", () => {
      const expanded = navToggle.getAttribute("aria-expanded") === "true";
      if (expanded) closeNavigation();
      else openNavigation();
    });
    navClose?.addEventListener("click", closeNavigation);
    sidebar.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        if (mobileQuery.matches) closeNavigation();
      });
    });
    mobileQuery.addEventListener?.("change", syncNavigation);
    syncNavigation();
  }

  const closePopovers = (except = null) => {
    document.querySelectorAll("details[data-popover][open]").forEach((details) => {
      if (details !== except) details.removeAttribute("open");
    });
  };

  document.querySelectorAll("details[data-popover]").forEach((details) => {
    details.addEventListener("toggle", () => {
      if (details.open) closePopovers(details);
    });
  });

  document.addEventListener("pointerdown", (event) => {
    const target = event.target;
    if (!(target instanceof Node)) return;
    document.querySelectorAll("details[data-popover][open]").forEach((details) => {
      if (!details.contains(target)) details.removeAttribute("open");
    });
  });

  const palette = document.querySelector("[data-command-palette]");
  const paletteInput = document.querySelector("[data-command-input]");
  const paletteItems = Array.from(document.querySelectorAll("[data-command-item]"));
  const paletteEmpty = document.querySelector("[data-command-empty]");
  let activeIndex = -1;
  let previousFocus = null;

  const visiblePaletteItems = () => paletteItems.filter((item) => !item.hidden);

  const setActiveItem = (index) => {
    const visible = visiblePaletteItems();
    paletteItems.forEach((item) => item.classList.remove("active"));
    if (!visible.length) {
      activeIndex = -1;
      return;
    }
    activeIndex = ((index % visible.length) + visible.length) % visible.length;
    const item = visible[activeIndex];
    item.classList.add("active");
    item.scrollIntoView({ block: "nearest" });
  };

  const filterCommands = () => {
    if (!(paletteInput instanceof HTMLInputElement)) return;
    const query = paletteInput.value.trim().toLocaleLowerCase();
    let matches = 0;
    paletteItems.forEach((item) => {
      const haystack = `${item.getAttribute("data-search") || ""} ${item.textContent || ""}`.toLocaleLowerCase();
      item.hidden = Boolean(query) && !haystack.includes(query);
      if (!item.hidden) matches += 1;
    });
    if (paletteEmpty) paletteEmpty.hidden = matches !== 0;
    setActiveItem(matches ? 0 : -1);
  };

  const openPalette = () => {
    if (!palette || !(paletteInput instanceof HTMLInputElement)) return;
    previousFocus = document.activeElement;
    closePopovers();
    closeNavigation();
    palette.hidden = false;
    body.classList.add("command-open");
    paletteInput.value = "";
    filterCommands();
    window.requestAnimationFrame(() => paletteInput.focus());
  };

  const closePalette = () => {
    if (!palette) return;
    palette.hidden = true;
    body.classList.remove("command-open");
    paletteItems.forEach((item) => item.classList.remove("active"));
    activeIndex = -1;
    if (previousFocus instanceof HTMLElement) previousFocus.focus({ preventScroll: true });
  };

  document.querySelectorAll("[data-command-open]").forEach((trigger) => {
    trigger.addEventListener("click", openPalette);
  });
  document.querySelectorAll("[data-command-close]").forEach((trigger) => {
    trigger.addEventListener("click", closePalette);
  });
  paletteInput?.addEventListener("input", filterCommands);

  paletteInput?.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveItem(activeIndex + 1);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveItem(activeIndex - 1);
    } else if (event.key === "Enter") {
      const visible = visiblePaletteItems();
      if (!visible.length) return;
      event.preventDefault();
      const selected = visible[Math.max(activeIndex, 0)];
      if (selected instanceof HTMLAnchorElement) selected.click();
    }
  });

  document.addEventListener("keydown", (event) => {
    const target = event.target;
    const typing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || target?.isContentEditable;

    if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === "k") {
      event.preventDefault();
      if (palette?.hidden === false) closePalette();
      else openPalette();
      return;
    }

    if (event.key === "Escape") {
      if (palette?.hidden === false) {
        event.preventDefault();
        closePalette();
      } else if (body.classList.contains("nav-open")) {
        event.preventDefault();
        closeNavigation();
      } else {
        closePopovers();
      }
      return;
    }

    if (!typing && event.key === "/" && palette?.hidden !== false) {
      event.preventDefault();
      openPalette();
    }
  });

  const preferencesForm = document.querySelector("[data-preferences-form]");
  if (preferencesForm) {
    preferencesForm.querySelectorAll('input[name="theme"]').forEach((input) => {
      input.addEventListener("change", (event) => {
        const target = event.currentTarget;
        if (target instanceof HTMLInputElement) document.documentElement.dataset.theme = target.value;
      });
    });
  }

  document.querySelectorAll("[data-quick-theme-form] button[name='theme']").forEach((button) => {
    button.addEventListener("click", () => {
      if (button instanceof HTMLButtonElement) document.documentElement.dataset.theme = button.value;
    });
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const message = form.getAttribute("data-confirm");
      if (message && !window.confirm(message)) event.preventDefault();
    });
  });

  document.querySelectorAll("[data-auto-submit]").forEach((control) => {
    control.addEventListener("change", () => {
      if (control instanceof HTMLSelectElement && control.form) control.form.requestSubmit();
    });
  });
})();
