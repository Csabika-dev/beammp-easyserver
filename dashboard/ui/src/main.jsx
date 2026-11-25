import { createRoot } from "react-dom/client";
import { App } from "./app.jsx";
import * as L from "./legacy.js";

(async () => {
  await L.loadLangList();
  await L.loadLang(L.pickLang());
  createRoot(document.getElementById("root")).render(<App />);
})();
if ("serviceWorker" in navigator && window.isSecureContext) navigator.serviceWorker.register("/sw.js").catch(() => {});
