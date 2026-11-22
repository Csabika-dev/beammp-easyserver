// Builds the website in docs/ from the React source in site/src.
//
//   cd site && npm install && npm run build
//
// Every page is rendered to plain HTML here, so it shows (and is indexed)
// without JavaScript. In the browser React then takes over the same markup
// for the tour, the step road, search and the other interactive parts.
import * as esbuild from "esbuild";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const docs = join(here, "..", "docs");
const assets = join(docs, "assets");
mkdirSync(assets, { recursive: true });

const common = {
  bundle: true,
  jsx: "automatic",
  loader: { ".jsx": "jsx" },
  define: { "process.env.NODE_ENV": '"production"' },
  nodePaths: process.env.NODE_PATH ? process.env.NODE_PATH.split(":") : [],
  logLevel: "warning",
};

// 1. The browser bundle.
await esbuild.build({ ...common, entryPoints: [join(here, "src/client.jsx")], outfile: join(assets, "site.js"),
  format: "iife", minify: true, target: ["es2020"], legalComments: "none" });
await esbuild.build({ ...common, entryPoints: [join(here, "src/site.css")], outfile: join(assets, "site.css"),
  minify: true, loader: { ".css": "css" } });

// 2. Render each page to HTML with the same components.
const tmp = join(here, ".render.mjs");
await esbuild.build({ ...common, entryPoints: [join(here, "src/server.jsx")], outfile: tmp, platform: "node", format: "esm", packages: "external" });
const { PAGES, renderPage } = await import(pathToFileURL(tmp).href + "?t=" + Date.now());
rmSync(tmp);

const v = f => createHash("sha256").update(readFileSync(join(assets, f))).digest("hex").slice(0, 10);
const js = "assets/site.js?v=" + v("site.js"), css = "assets/site.css?v=" + v("site.css");

for (const p of PAGES) {
  const body = renderPage(p.id);
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="img/logo.svg" type="image/svg+xml">
<title>${p.title}</title>
<meta name="description" content="${p.description}">
<meta property="og:title" content="${p.ogTitle}">
<meta property="og:description" content="${p.ogDescription}">
<meta property="og:image" content="https://csabika-dev.github.io/beammp-easyserver/img/overview-dark.webp">
<meta name="color-scheme" content="light dark">
<link rel="stylesheet" href="${css}">
<noscript><style>.fold-body{grid-template-rows:1fr!important}.fold-body>div{visibility:visible!important}.js-only{display:none!important}.tabpanel[hidden]{display:block!important}.tour-frame img{position:static!important;opacity:1!important;margin-bottom:8px}.tour-frame{aspect-ratio:auto!important}.nojs-label{display:inline!important}.ex-panel{margin-bottom:28px}</style></noscript>
<!-- Privacy-friendly visit counter: no cookies, no personal data (goatcounter.com) -->
<script data-goatcounter="https://easyserver.goatcounter.com/count" async src="https://gc.zgo.at/count.v5.js" crossorigin="anonymous" integrity="sha384-atnOLvQb9t+jTSipvd75X2yginT4PjVbqDdlJAmxMm+wYElFmeR6EmLP5bYeoRVQ"></script>
<script defer src="${js}"></script>
</head>
<body>
<div id="app" data-page="${p.id}">${body}</div>
</body>
</html>
`;
  writeFileSync(join(docs, p.file), html);
  console.log(p.file, Math.round(html.length / 1024) + " KB");
}
console.log("site.js", Math.round(readFileSync(join(assets, "site.js")).length / 1024) + " KB");
