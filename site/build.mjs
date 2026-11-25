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
const OG_LOCALE = { en: "en_US", de: "de_DE", es: "es_ES", hu: "hu_HU", pl: "pl_PL" };

// Lets phones add the site to the home screen with the real icon (link-preview cards and icons:
// site/images/make.py).
writeFileSync(join(docs, "site.webmanifest"), JSON.stringify({
  name: "BeamMP EasyServer", short_name: "EasyServer", start_url: "./", display: "browser",
  background_color: "#202328", theme_color: "#202328",
  icons: [{ src: "img/icon-192.png", sizes: "192x192", type: "image/png" }, { src: "img/icon-512.png", sizes: "512x512", type: "image/png" }],
}, null, 1) + "\n");

// Runs before anything is drawn. Turns on the scroll-in effects (with a safety net in case the
// script never arrives) and, on an English page, sends a first-time visitor to their language.
const THEME = `try{var th=localStorage.getItem("es-site-theme");if(th==="dark"||th==="light")document.documentElement.dataset.theme=th}catch(e){}`;
const boot = (code, file) => `<script>(function(){var d=document.documentElement;d.classList.add("js");${THEME}setTimeout(function(){if(!window.esReady)d.classList.add("reveal-all")},4000);` +
  (code === "en" ? `try{var L=${JSON.stringify(codes)},s=localStorage.getItem("es-site-lang");if(!s){var n=(navigator.languages||[navigator.language||""]);for(var i=0;i<n.length&&!s;i++){var c=String(n[i]).slice(0,2).toLowerCase();if(L.indexOf(c)>=0)s=c}}if(s&&s!=="en"&&L.indexOf(s)>=0)location.replace(s+"/${file === "index.html" ? "" : file}"+location.hash)}catch(e){}` : "") +
  `})()</script>`;

// The dashboard shows the same "New in" cards after an update: dashboard/whatsnew.json, in every language.
{
  const plain = x => String(x).replace(/\*\*(.+?)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
  const out = { about: "Made from CHANGELOG.md by site/build.mjs - don't edit by hand.", version: news?.version || "", status: news?.status || "", languages: {} };
  if (news) for (const { code, text } of LANGS) {
    const t = textFor(code);
    const own = code !== "en" && text.whatsNew?.[news.version];
    out.languages[code] = {
      title: t.common.newTitle.replace("{v}", news.version),
      note: news.status === "rolling" ? t.common.newRolling : t.common.newStable,
      items: (own?.length ? own : news.items).map(([a, b]) => [plain(a), plain(b)]),
    };
  }
  writeFileSync(join(here, "..", "dashboard", "whatsnew.json"), JSON.stringify(out, null, 1) + "\n");
}

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
<link rel="icon" href="${root}img/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="${root}img/apple-touch-icon.png">
<link rel="manifest" href="${root}site.webmanifest">
<title>${esc(m.title)}</title>
<meta name="description" content="${esc(m.description)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="BeamMP EasyServer">
<meta property="og:locale" content="${OG_LOCALE[code]}">
<meta property="og:url" content="${SITE + addr(code, p.file)}">
<meta property="og:title" content="${esc(m.ogTitle)}">
<meta property="og:description" content="${esc(m.ogDescription)}">
<meta property="og:image" content="${SITE}img/card-${code}.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="${esc(m.ogTitle)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#e9ebee" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#202328" media="(prefers-color-scheme: dark)">
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
// GitHub Pages shows docs/404.html for any address that doesn't exist, at any depth, so it
// uses full paths and picks its language in the browser (from the address, the saved choice
// or the browser's language). The little driving game is site/notfound-game.js.
{
  const BASE = "/beammp-easyserver/";
  const nf = Object.fromEntries(LANGS.map(({ code }) => [code, textFor(code).notFound]));
  const en = nf.en;
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<link rel="icon" href="${BASE}img/logo.svg" type="image/svg+xml">
<title>${esc(en.title)}</title>
<meta name="color-scheme" content="light dark">
<link rel="stylesheet" href="${BASE}assets/site.css?v=${cssV}">
<script>${THEME}</script>
</head>
<body class="nf-page">
<nav class="top"><div class="wrap"><a class="logo" href="${BASE}" data-nf="home-logo"><img src="${BASE}img/logo.svg" alt="" width="28" height="28"><span>BeamMP EasyServer</span></a></div></nav>
<main class="wrap nf">
<h1 data-nf="h1">${esc(en.h1)}</h1>
<p class="joke" data-nf="joke">${esc(en.joke)}</p>
<p data-nf="text">${esc(en.text)}</p>
<div class="game">
<canvas id="game" width="600" height="190" role="img" aria-label="${esc(en.gameLabel)}" data-nf="gameLabel"></canvas>
<div class="game-bar"><span id="game-say" aria-live="polite"></span><span id="game-score"></span></div>
</div>
<div class="btns"><a class="btn go" href="${BASE}" data-nf="home">${esc(en.home)}</a><a class="btn" href="${BASE}help.html" data-nf="help">${esc(en.help)}</a></div>
</main>
<script>(function(){var T=${JSON.stringify(nf)},L=Object.keys(T),c="en";
var seg=location.pathname.slice(${BASE.length}).split("/")[0];
if(L.indexOf(seg)>=0)c=seg;else{try{var s=localStorage.getItem("es-site-lang");if(s&&L.indexOf(s)>=0)c=s}catch(e){}
if(c==="en"){var n=navigator.languages||[navigator.language||""];for(var i=0;i<n.length;i++){var k=String(n[i]).slice(0,2).toLowerCase();if(L.indexOf(k)>=0){c=k;break}}}}
var t=window.NF=T[c];if(c==="en")return;var pre="${BASE}"+c+"/";document.documentElement.lang=c;document.title=t.title;
document.querySelectorAll("[data-nf]").forEach(function(e){var k=e.getAttribute("data-nf");
if(k==="gameLabel")e.setAttribute("aria-label",t.gameLabel);else if(k==="home-logo")e.href=pre;else{e.textContent=t[k];if(k==="home")e.href=pre;if(k==="help")e.href=pre+"help.html"}})})()</script>
<script>${readFileSync(join(here, "notfound-game.js"), "utf8")}</script>
</body>
</html>
`;
  writeFileSync(join(docs, "404.html"), html);
  console.log("404.html", Math.round(html.length / 1024) + " KB");
}
console.log("site.js", Math.round(readFileSync(join(assets, "site.js")).length / 1024) + " KB");
