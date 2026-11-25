import { Features } from "./Features.jsx";
import { Help } from "./Help.jsx";
import { Home } from "./Home.jsx";

// Titles and descriptions come from the language files (meta.home, meta.features, meta.help).
export const PAGES = [
  { id: "home", file: "index.html", Page: Home },
  { id: "features", file: "features.html", Page: Features },
  { id: "help", file: "help.html", Page: Help },
];
