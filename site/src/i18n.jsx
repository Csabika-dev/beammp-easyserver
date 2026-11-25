import { createContext, Fragment, useContext } from "react";
import { GH, LATEST, ASK } from "./links.js";
import en from "./lang/en.js";
import de from "./lang/de.js";
import es from "./lang/es.js";
import hu from "./lang/hu.js";
import pl from "./lang/pl.js";

// To add a language: copy lang/en.js, translate the text, import it here and add it to LANGS.
export const LANGS = [
  { code: "en", name: "English", text: en },
  { code: "de", name: "Deutsch", text: de },
  { code: "es", name: "Español", text: es },
  { code: "hu", name: "Magyar", text: hu },
  { code: "pl", name: "Polski", text: pl },
];

// Anything missing in a translation falls back to the English text.
function merge(base, over) {
  if (over === undefined) return base;
  if (Array.isArray(base) || typeof base !== "object" || base === null) return over;
  const out = {};
  for (const k of Object.keys(base)) out[k] = merge(base[k], over?.[k]);
  return out;
}
const CACHE = {};
export function textFor(code) {
  return CACHE[code] ||= merge(en, LANGS.find(l => l.code === code)?.text || {});
}

// lang: the language code. root: how to get from this page to the site root ("" or "../").
export const Site = createContext({ lang: "en", root: "", t: en });
export const useSite = () => useContext(Site);

// Page addresses in a language: English lives at the root, others in /de/, /es/ …
export const pageHref = (root, code, file) => root + (code === "en" ? "" : code + "/") + (file === "index.html" ? "" : file) || "./";

const URLS = { GH, LATEST, ASK };
const url = u => u.replace(/^\{(\w+)\}/, (_, k) => URLS[k] ?? "");

// Tiny markup used in the language files:
//   **bold**   *italic*   `code`   [link text](https://… or {GH}/path or #anchor or page.html)
const TOKEN = /(\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\))/g;
export function Md({ s, root = "" }) {
  if (s == null) return null;
  const parts = [];
  let last = 0, m, n = 0;
  TOKEN.lastIndex = 0;
  while ((m = TOKEN.exec(s))) {
    if (m.index > last) parts.push(s.slice(last, m.index));
    if (m[2] != null) parts.push(<b key={n++}>{m[2]}</b>);
    else if (m[3] != null) parts.push(<i key={n++}>{m[3]}</i>);
    else if (m[4] != null) parts.push(<code key={n++}>{m[4]}</code>);
    else {
      const href = url(m[6]);   // page links like features.html stay relative, so they stay in this language
      parts.push(<a key={n++} href={href}>{m[5]}</a>);
    }
    last = TOKEN.lastIndex;
  }
  if (last < s.length) parts.push(s.slice(last));
  return <Fragment>{parts}</Fragment>;
}

// Plain text of a markup string, for search.
export const plain = s => String(s ?? "").replace(TOKEN, (...a) => a[2] ?? a[3] ?? a[4] ?? a[5] ?? "");

// A list of blocks: a string is a paragraph, {ul: [...]} or {ol: [...]} is a list.
export function Blocks({ blocks, root }) {
  return blocks.map((b, i) =>
    typeof b === "string" ? <p key={i}><Md s={b} root={root} /></p>
      : b.ul ? <ul key={i}>{b.ul.map((x, j) => <li key={j}><Md s={x} root={root} /></li>)}</ul>
      : <ol key={i}>{b.ol.map((x, j) => <li key={j}><Md s={x} root={root} /></li>)}</ol>);
}
export const blocksText = blocks => blocks.map(b => typeof b === "string" ? plain(b) : (b.ul || b.ol).map(plain).join(" ")).join(" ");
