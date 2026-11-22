# Website source

The website at https://csabika-dev.github.io/beammp-easyserver/ is built from this folder with React.

- `src/lang/en.js`: every piece of text on the site, in English
- `src/lang/de.js`, `es.js`, `hu.js`, `pl.js`: the same text translated. Anything missing shows in English.
  `**bold**`, `` `code` `` and `[text](url)` work inside the text.
- `src/Home.jsx`, `src/Features.jsx`, `src/Help.jsx`: the three pages
- `src/site.css`: all styles
- `src/pages.jsx`: the list of pages
- `build.mjs`: renders every page to plain HTML in `docs/` and bundles the script that makes them interactive

Each page is complete HTML before any script runs, so it loads fast, works without JavaScript and is
found by search engines. Each language gets its own copy: English at the top level, the others in
`docs/de/`, `docs/es/`, `docs/hu/` and `docs/pl/`. To add a language, copy `src/lang/en.js`, translate it
and add it to `LANGS` in `src/i18n.jsx`. React then takes over the same markup in the browser.

## "What's new" on the site

The "New in …" cards on the home and Features pages come from `CHANGELOG.md`. Under a version heading,
add a hidden block (GitHub doesn't show it), one card per line:

```
<!-- website
Race mode: Set up a race with checkpoints in two clicks.
Live map: See where everyone is driving.
-->
```

Push the changelog and the site rebuilds itself. The newest version with a block is shown, and the note
under the title says "in Rolling" when the heading mentions Rolling, otherwise "in Stable". Without a block,
the first bold bullets of the newest version are used. Translations go in `whatsNew` at the end of each
language file, under the version number; until then that language shows the English cards.

## Changing the site

Edit the files in `src/` and push. The **Website** workflow builds `docs/` and commits it.
Don't edit `docs/index.html`, `docs/features.html`, `docs/help.html` or the language folders (`docs/de/` etc.) by hand: the next build replaces them.

To build on your own computer (Node.js 20 or newer):

```
cd site
npm install
npm run build
```

Then open `docs/index.html` through any local web server, for example `python3 -m http.server -d docs`.
