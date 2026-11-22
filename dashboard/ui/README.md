# Dashboard page

`dashboard/webui.html` (the page the dashboard serves) is built from this folder:

- `src/app.jsx`: the React app: logging in, the frame around every page (menu, server picker,
  theme, language, security alerts) and the Overview page
- `src/legacy.js`: the other pages, still drawn the old way while they move over to React, plus
  the shared helpers (talking to the dashboard, translations, toasts, pop-ups)
- `src/styles.css`: all styles
- `head.html`: the start of the page

Translations stay in `dashboard/lang/*.json` (English text -> translation) and are applied to
whatever is drawn, React or not. `python3 tools/i18n.py missing de` lists what isn't translated.

Build (Node.js 20 or newer):

```
cd dashboard/ui
npm install
node build.mjs
```

After a push, the **Website** workflow builds it and commits `webui.html`, so you can also just
edit `src/` and push. The page is served with a fresh nonce for its one inline script; keep it
that way (no extra script files, no `onclick="..."` in HTML).
