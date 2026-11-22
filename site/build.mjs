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
import { readNews } from "./news.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const docs = join(here, "..", "docs");
const assets = join(docs, "assets");
mkdirSync(assets, { recursive: true });

// "What's new" comes from CHANGELOG.md, so adding a version there updates the site.
const news = readNews(join(here, "..", "CHANGELOG.md"));
console.log("What's new:", news ? `${news.version} (${news.status}), ${news.items.map(i => i[0]).join(", ")}` : "none");

const common = {
  bundle: true,
  jsx: "automatic",
  loader: { ".jsx": "jsx" },
  define: { "process.env.NODE_ENV": '"production"', __NEWS__: JSON.stringify(news) },
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
const { PAGES, LANGS, textFor, renderPage } = await import(pathToFileURL(tmp).href + "?t=" + Date.now());
rmSync(tmp);

const v = f => createHash("sha256").update(readFileSync(join(assets, f))).digest("hex").slice(0, 10);
const jsV = v("site.js"), cssV = v("site.css");
const SITE = "https://csabika-dev.github.io/beammp-easyserver/";
const esc = s => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
const addr = (code, file) => (code === "en" ? "" : code + "/") + (file === "index.html" ? "" : file);
const codes = LANGS.map(l => l.code);

// Runs before anything is drawn. Turns on the scroll-in effects (with a safety net in case the
// script never arrives) and, on an English page, sends a first-time visitor to their language.
const boot = (code, file) => `<script>(function(){var d=document.documentElement;d.classList.add("js");setTimeout(function(){if(!window.esReady)d.classList.add("reveal-all")},4000);` +
  (code === "en" ? `try{var L=${JSON.stringify(codes)},s=localStorage.getItem("es-site-lang");if(!s){var n=(navigator.languages||[navigator.language||""]);for(var i=0;i<n.length&&!s;i++){var c=String(n[i]).slice(0,2).toLowerCase();if(L.indexOf(c)>=0)s=c}}if(s&&s!=="en"&&L.indexOf(s)>=0)location.replace(s+"/${file === "index.html" ? "" : file}"+location.hash)}catch(e){}` : "") +
  `})()</script>`;

for (const { code } of LANGS) {
  const t = textFor(code);
  const root = code === "en" ? "" : "../";
  const dir = code === "en" ? docs : join(docs, code);
  mkdirSync(dir, { recursive: true });
  for (const p of PAGES) {
    const m = t.meta[p.id];
    const body = renderPage(p.id, code);
    const alternates = LANGS.map(l => `<link rel="alternate" hreflang="${l.code}" href="${SITE + addr(l.code, p.file)}">`).join("\n") +
      `\n<link rel="alternate" hreflang="x-default" href="${SITE + addr("en", p.file)}">`;
    const html = `<!doctype html>
<html lang="${code}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="${root}img/logo.svg" type="image/svg+xml">
<title>${esc(m.title)}</title>
<meta name="description" content="${esc(m.description)}">
<meta property="og:title" content="${esc(m.ogTitle)}">
<meta property="og:description" content="${esc(m.ogDescription)}">
<meta property="og:image" content="${SITE}img/overview-dark.webp">
<meta name="color-scheme" content="light dark">
<link rel="canonical" href="${SITE + addr(code, p.file)}">
${alternates}
<link rel="stylesheet" href="${root}assets/site.css?v=${cssV}">
${boot(code, p.file)}
<noscript><style>.fold-body{grid-template-rows:1fr!important}.fold-body>div{visibility:visible!important}.js-only{display:none!important}.tabpanel[hidden]{display:block!important}.tour-frame img{position:static!important;opacity:1!important;margin-bottom:8px}.tour-frame{aspect-ratio:auto!important}.nojs-label{display:inline!important}.ex-panel{margin-bottom:28px}</style></noscript>
<!-- Privacy-friendly visit counter: no cookies, no personal data (goatcounter.com) -->
<script data-goatcounter="https://easyserver.goatcounter.com/count" async src="https://gc.zgo.at/count.v5.js" crossorigin="anonymous" integrity="sha384-atnOLvQb9t+jTSipvd75X2yginT4PjVbqDdlJAmxMm+wYElFmeR6EmLP5bYeoRVQ"></script>
<script defer src="${root}assets/site.js?v=${jsV}"></script>
</head>
<body>
<div id="app" data-page="${p.id}" data-lang="${code}" data-root="${root}">${body}</div>
</body>
</html>
`;
    writeFileSync(join(dir, p.file), html);
    console.log(addr(code, p.file) || "index.html", Math.round(html.length / 1024) + " KB");
  }
}
console.log("site.js", Math.round(readFileSync(join(assets, "site.js")).length / 1024) + " KB");
