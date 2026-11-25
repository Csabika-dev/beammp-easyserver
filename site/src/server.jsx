import { renderToString } from "react-dom/server";
import { LANGS, Site, textFor } from "./i18n.jsx";
import { PAGES } from "./pages.jsx";

export { PAGES, LANGS, textFor };
export function renderPage(id, lang) {
  const { Page, file } = PAGES.find(p => p.id === id);
  const root = lang === "en" ? "" : "../";
  return renderToString(<Site.Provider value={{ lang, root, file, t: textFor(lang) }}><Page /></Site.Provider>);
}
