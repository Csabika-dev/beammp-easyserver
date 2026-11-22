// Builds dashboard/webui.html from this folder: head.html + src/styles.css + the React app in src/.
// The dashboard serves that one file with a fresh nonce, so everything stays inline:
//   cd dashboard/ui && npm install && node build.mjs
import * as esbuild from "esbuild";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const r = await esbuild.build({
  entryPoints: [join(here, "src/main.jsx")], bundle: true, write: false, format: "iife", minify: process.env.NOMIN ? false : true,
  target: ["es2020"], jsx: "automatic", loader: { ".jsx": "jsx" }, legalComments: "none", charset: "utf8",
  define: { "process.env.NODE_ENV": '"production"' }, logLevel: "warning",
  nodePaths: process.env.NODE_PATH ? process.env.NODE_PATH.split(":") : [],
});
// The script goes inline, so text in it must not be able to end the tag early
const S = "scr" + "ipt";
const js = r.outputFiles[0].text.split("</" + S).join("<\\/" + S).split("<!" + "--").join("<\\!--");
const css = readFileSync(join(here, "src/styles.css"), "utf8");
const html = readFileSync(join(here, "head.html"), "utf8") +
  `<style nonce="__NONCE__">\n${css}</style>\n</head>\n<body>\n<div id="root"></div>\n<div id="toast" class="hidden"></div>\n` +
  `<!-- Built from dashboard/ui by build.mjs - edit the files there, not this one. -->\n` +
  `<${S} nonce="__NONCE__">${js}</${S}>\n</body>\n</html>\n`;
writeFileSync(join(here, "..", "webui.html"), html);
console.log("webui.html", Math.round(html.length / 1024), "KB");
