// Reads the "What's new" section of the website from CHANGELOG.md, so the site updates itself
// when a new version is added there.
//
// Under a version heading in CHANGELOG.md, add a hidden block (GitHub doesn't show it):
//
//   <!-- website: the "New in" cards on the website. One per line, "Title: text". Not shown on GitHub.
//   Vehicle rules: Block props, trailers or any car, and stop spawn spam.
//   Server plugins: Install community game modes straight from each author's page.
//   -->
//
// One line per card, "Title: text". The newest version that has such a block is shown.
// If no version has one, the first three bold bullets of the newest version are used.
// A heading that says "Rolling" shows the "in Rolling now" note, otherwise "in Stable".
import { readFileSync } from "node:fs";

export function readNews(changelogPath) {
  let md = "";
  try { md = readFileSync(changelogPath, "utf8").replace(/\r\n/g, "\n"); } catch { return null; }
  const sections = [];
  const re = /^## +(\d+)\.(\d+)(?:\.\d+)?\b(.*)$/gm;
  let m, last = null;
  while ((m = re.exec(md))) {
    if (last) last.body = md.slice(last.start, m.index);
    last = { version: `${m[1]}.${m[2]}`, heading: m[3], start: re.lastIndex };
    sections.push(last);
  }
  if (!last) return null;
  last.body = md.slice(last.start);

  const status = s => (/rolling/i.test(s.heading) ? "rolling" : "stable");
  for (const s of sections) {
    const block = s.body.match(/<!--\s*website\b[^\n]*\n([\s\S]*?)-->/);
    if (!block) continue;
    const items = block[1].split("\n").map(l => l.trim()).filter(Boolean)
      .map(l => { const i = l.indexOf(":"); return i > 0 ? [l.slice(0, i).trim(), l.slice(i + 1).trim()] : null; })
      .filter(Boolean);
    if (items.length) return { version: s.version, status: status(s), items };
  }
  // No block anywhere: take the newest version's first bold bullets that have text after the title.
  const s = sections[0];
  const items = [];
  for (const line of s.body.split("\n")) {
    const b = line.match(/^- \*\*(.+?)\*\*:?\s*(.+)$/);
    if (!b || b[1].startsWith("Fixed")) continue;
    // "(Config): block props ..." -> "Block props ...": drop where it lives, keep the first sentence.
    let first = b[2].replace(/^\([^)]*\)\s*:?\s*/, "").replace(/^[:\-–]\s*/, "").split(/(?<=\.)\s/)[0];
    first = first.charAt(0).toUpperCase() + first.slice(1);
    if (first.length > 15 && first.length < 220 && !first.includes("`")) items.push([b[1].replace(/:$/, ""), first]);
    if (items.length === 3) break;
  }
  return { version: s.version, status: status(s), items };
}
