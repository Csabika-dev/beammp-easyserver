import { hydrateRoot } from "react-dom/client";
import { Site, textFor } from "./i18n.jsx";
import { PAGES } from "./pages.jsx";

const root = document.getElementById("app");
const { page: id, lang, root: base } = root.dataset;
const page = PAGES.find(p => p.id === id);
hydrateRoot(root, <Site.Provider value={{ lang, root: base, file: page.file, t: textFor(lang) }}><page.Page /></Site.Provider>);

// Parts of the page slide in as they scroll into view. Marked with data-reveal in the markup;
// "stagger" lets the children of a list arrive one after another.
window.esReady = true;
const els = document.querySelectorAll("[data-reveal]");
if ("IntersectionObserver" in window) {
  const io = new IntersectionObserver(entries => entries.forEach(e => {
    if (e.isIntersecting) { e.target.setAttribute("data-shown", ""); io.unobserve(e.target); }
  }), { rootMargin: "0px 0px -8% 0px", threshold: 0.05 });
  els.forEach(el => io.observe(el));
} else els.forEach(el => el.setAttribute("data-shown", ""));
