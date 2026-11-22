import { renderToString } from "react-dom/server";
import { PAGES } from "./pages.jsx";

export { PAGES };
export function renderPage(id) {
  const { Page } = PAGES.find(p => p.id === id);
  return renderToString(<Page />);
}
