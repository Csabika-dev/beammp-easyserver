# Dashboard page

`dashboard/webui.html` (the page the dashboard serves) is built from this folder:

- `src/app.jsx`: the React app: logging in, the frame around every page (menu, server picker,
  theme, language, security alerts) and the Overview page
- the other pages, also React: `src/pages.jsx` (Servers, Updates, Logs, Notifications),
  `src/health.jsx`, `src/players.jsx`, `src/mods.jsx`, `src/config.jsx`, and Settings in
  `src/settings.jsx`, `src/settings-cards.jsx` and `src/power.jsx`
- `src/ui.jsx`: small pieces the pages share (switches, pills, loading a card's data). The
  forms keep their values in the inputs, and a Save button reads them by id.
- `src/legacy.js`: the shared helpers (talking to the dashboard, translations, toasts) and a
  few dialogs that are still plain HTML (browse mods, mod pack code, my account, invites)
- `src/styles.css`: all styles
- `head.html`: the start of the page

Translations stay in `dashboard/lang/*.json` (English text -> translation) and are applied to
whatever is drawn. Keep each sentence in one piece of text (a template string like
`` `Port ${port} open` `` rather than `"Port " + port + " open"`) so it matches one entry. `python3 tools/i18n.py missing de` lists what isn't translated.

Build (Node.js 20 or newer):

```
cd dashboard/ui
npm install
node build.mjs
```

After a push, the **Website** workflow builds it and commits `webui.html`, so you can also just
edit `src/` and push. The page is served with a fresh nonce for its one inline script; keep it
that way (no extra script files, no `onclick="..."` in HTML).
