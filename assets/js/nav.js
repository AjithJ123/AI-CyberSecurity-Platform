const header = document.querySelector(".pg-header");
const toggle = document.querySelector(".pg-nav-toggle");
const nav = document.querySelector(".pg-nav");

if (header && toggle && nav) {
  const setOpen = (isOpen) => {
    header.classList.toggle("is-nav-open", isOpen);
    toggle.setAttribute("aria-expanded", String(isOpen));
    toggle.setAttribute("aria-label", isOpen ? "Close navigation" : "Open navigation");
  };

  toggle.addEventListener("click", () => {
    setOpen(!header.classList.contains("is-nav-open"));
  });

  nav.addEventListener("click", (event) => {
    if (event.target instanceof HTMLAnchorElement) setOpen(false);
  });

  document.addEventListener("click", (event) => {
    if (!header.contains(event.target)) setOpen(false);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setOpen(false);
  });

  window.addEventListener("resize", () => {
    if (window.matchMedia("(min-width: 901px)").matches) setOpen(false);
  });
}
