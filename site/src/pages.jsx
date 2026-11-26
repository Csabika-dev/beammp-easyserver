import { Features } from "./Features.jsx";
import { Help } from "./Help.jsx";
import { Home } from "./Home.jsx";
import { Privacy } from "./Privacy.jsx";

// Titles and descriptions come from the language files (meta.home, meta.features, meta.help, meta.privacy).
export const PAGES = [
  { id: "home", file: "index.html", Page: Home },
  { id: "features", file: "features.html", Page: Features },
  { id: "help", file: "help.html", Page: Help },
  { id: "privacy", file: "privacy.html", Page: Privacy },
];
