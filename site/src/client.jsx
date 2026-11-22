import { hydrateRoot } from "react-dom/client";
import { PAGES } from "./pages.jsx";

const root = document.getElementById("app");
const page = PAGES.find(p => p.id === root.dataset.page);
document.documentElement.classList.add("js");
hydrateRoot(root, <page.Page />);
