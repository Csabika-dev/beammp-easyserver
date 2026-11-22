# Website source

The website at https://csabika-dev.github.io/beammp-easyserver/ is built from this folder with React.

- `src/Home.jsx`, `src/Features.jsx`, `src/Help.jsx`: the three pages, text included
- `src/site.css`: all styles
- `src/pages.jsx`: page titles and descriptions
- `build.mjs`: renders every page to plain HTML in `docs/` and bundles the script that makes them interactive

Each page is complete HTML before any script runs, so it loads fast, works without JavaScript and is
found by search engines. React then takes over the same markup in the browser.

## Changing the site

Edit the files in `src/` and push. The **Website** workflow builds `docs/` and commits it.
Don't edit `docs/index.html`, `docs/features.html` or `docs/help.html` by hand: the next build replaces them.

To build on your own computer (Node.js 20 or newer):

```
cd site
npm install
npm run build
```

Then open `docs/index.html` through any local web server, for example `python3 -m http.server -d docs`.
