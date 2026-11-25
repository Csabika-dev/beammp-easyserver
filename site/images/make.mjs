// Makes the link-preview cards (docs/img/card-<lang>.jpg) and app icons (docs/img/*.png) with
// headless Chrome. The Website workflow runs it before the build; locally:  node images/make.mjs
// Each card shows the first half of that language's meta.home.ogDescription.
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const img = join(here, "..", "..", "docs", "img");
// Only redraw when something they're made from changed, so a build doesn't commit new copies of
// the same pictures every time.
const lines = {};
for (const code of ["en", "de", "es", "hu", "pl"]) {
  lines[code] = (await import(pathToFileURL(join(here, "..", "src", "lang", code + ".js")).href)).default.meta.home.ogDescription
    .split(" - ")[0].split(" y contr")[0].split(" i steruj")[0].replace(/\.$/, "");
}
const stamp = createHash("sha256").update(JSON.stringify(lines))
  .update(readFileSync(join(here, "card.html"))).update(readFileSync(join(here, "make.mjs")))
  .update(readFileSync(join(img, "logo.svg"))).update(readFileSync(join(img, "overview-dark.webp"))).digest("hex").slice(0, 16);
const stampFile = join(img, "cards.stamp");
if (existsSync(stampFile) && readFileSync(stampFile, "utf8").trim() === stamp && existsSync(join(img, "card-en.jpg"))) {
  console.log("Cards and icons are up to date."); process.exit(0);
}
const chrome = [process.env.CHROME, "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium"].find(p => p && existsSync(p));
if (!chrome) { console.log("No Chrome found: keeping the cards and icons that are there."); process.exit(0); }
const profile = mkdtempSync(join(tmpdir(), "cards-"));
const shot = (url, out, w, h, extra = []) => execFileSync(chrome, ["--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
  "--user-data-dir=" + profile, `--window-size=${w},${h}`, "--virtual-time-budget=1500", ...extra, "--screenshot=" + out, url], { stdio: "ignore" });

for (const [code, line] of Object.entries(lines)) {
  shot(pathToFileURL(join(here, "card.html")).href + "?t=" + encodeURIComponent(line), join(img, `card-${code}.jpg`), 1200, 630);
  console.log("card", code, line);
}
const logo = pathToFileURL(join(img, "logo.svg")).href;
for (const [size, name, see] of [[180, "apple-touch-icon.png", false], [192, "icon-192.png", true], [512, "icon-512.png", true], [32, "favicon-32.png", true]]) {
  const page = join(profile, "icon.html");
  writeFileSync(page, `<body style="margin:0;background:${see ? "transparent" : "#fff"}"><img src="${logo}" width="${size}" height="${size}" style="display:block"></body>`);
  shot(pathToFileURL(page).href, join(img, name), size, size, see ? ["--default-background-color=00000000"] : []);
  console.log("icon", name);
}
rmSync(profile, { recursive: true, force: true });
writeFileSync(stampFile, stamp + "\n");
