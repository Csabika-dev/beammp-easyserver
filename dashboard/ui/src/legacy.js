// The dashboard pages that are still drawn the old way (HTML text put into the page), plus the shared
// helpers: talking to the dashboard, translations, toasts, pop-ups. app.jsx (React) draws the rest.
/* ------------------------------------------------------------------ helpers */
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
/* IP addresses are blurred until clicked, like a password */
const ipb = html => `<span class="ipb" title="Hidden - click to show">${html}</span>`;
const blurIPs = html => String(html).replace(/(?<!\d)(?<!\d\.)(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?(?!\d|\.\d)/g, ipb);
document.addEventListener("click", e => { const t = e.target.closest && e.target.closest(".ipb"); if (t) { t.classList.toggle("shown"); t.title = t.classList.contains("shown") ? "Click to hide" : "Hidden - click to show"; } });
const h = (strings, ...vals) => strings.reduce((a, s, i) => a + s + (i < vals.length ? (vals[i] && vals[i].__raw !== undefined ? vals[i].__raw : esc(vals[i])) : ""), "");
const raw = s => ({__raw: s});
const IN_APP = /EasyServerApp/.test(navigator.userAgent);
const store = { get(k, d) { try { return localStorage.getItem(k) ?? d; } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };
let CSRF = null, SESSION = null, TAB = "overview", TIMER = null;

/* ------------------------------------------------------------------ languages
   The page is written in English. A language file (dashboard/lang/xx.json, English text -> translation) is
   applied to everything that is drawn: text, placeholders, tooltips, toasts and questions. "{}" in a text
   stands for a name or number; in the translation "{}" are filled in order, or "{1}", "{2}" ... to reorder.
   Text without a translation stays English. */
let LANGS = [["en", "English"]];                // + every file in dashboard/lang (filled in by loadLangList)
async function loadLangList() {
  try {
    const r = await fetch("/lang/index.json", { cache: "no-cache" });
    const d = await r.json();
    LANGS = [["en", "English"]].concat((d.languages || []).map(l => [l.code, l.name]));
  } catch (e) {}
}
let LANG = "en", DICT = null, PATS = [];
const escRe = x => x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
function pickLang() {
  const saved = store.get("es-lang", "");
  if (LANGS.some(l => l[0] === saved)) return saved;
  const nav = (navigator.languages || [navigator.language || "en"]).map(x => String(x).slice(0, 2).toLowerCase());
  return nav.find(c => LANGS.some(l => l[0] === c)) || "en";
}
async function loadLang(code) {
  LANG = "en"; DICT = null; PATS = [];
  if (code !== "en") {
    try {
      const r = await fetch("/lang/" + code + ".json", { cache: "no-cache" });
      if (!r.ok) throw new Error("no language file");
      const d = await r.json(), S = d.strings || {};
      DICT = Object.create(null);
      for (const [k, v] of Object.entries(S)) {
        if (typeof v !== "string" || !v) continue;
        DICT[k] = v;
        if (!k.includes("{}") || !/[A-Za-z]{2}/.test(k.replace(/\{\}/g, ""))) continue;
        const parts = k.split("{}");
        PATS.push({ re: new RegExp("^" + parts.map(escRe).join("([\\s\\S]+?)") + "$"), v, pre: parts[0], post: parts[parts.length - 1], len: k.length });
      }
      PATS.sort((a, b) => b.len - a.len);         // the most specific text first
      LANG = code;
    } catch (e) { DICT = null; }
  }
  document.documentElement.lang = LANG;
}
function tr(text, depth = 0) {
  if (!DICT || typeof text !== "string" || !/[A-Za-z]/.test(text)) return text;
  const core = text.trim().replace(/\s+/g, " ");
  if (!core) return text;
  let out = DICT[core];
  if (out === undefined) {
    out = null;
    for (const p of PATS) {
      if (!core.startsWith(p.pre) || !core.endsWith(p.post)) continue;
      const m = core.match(p.re);
      if (!m) continue;
      let i = 0;
      // a filled-in part can be English text of its own ("Checks: {}. {}" + a sentence): translate it too
      out = p.v.replace(/\{(\d*)\}/g, (_, d) => { const x = m[d ? +d : ++i]; return x == null ? "" : depth < 2 ? tr(x, depth + 1) : x; });
      break;
    }
    if (out === null) return text;
  }
  return text.match(/^\s*/)[0] + out + text.match(/\s*$/)[0];
}
const trLines = t => typeof t === "string" ? t.split("\n").map(tr).join("\n") : t;
const NO_TR = "script,style,textarea,code,pre,.mono,.log,.chatbox,[data-notr]";
function trNode(n) {
  if (!DICT || !n) return;
  if (n.nodeType === 3) { const v = tr(n.nodeValue); if (v !== n.nodeValue) n.nodeValue = v; return; }
  if (n.nodeType !== 1 || n.closest(NO_TR)) return;
  const w = document.createTreeWalker(n, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: x => x.nodeType === 1 && x.matches(NO_TR) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
  for (let x = n; x; x = w.nextNode()) {
    if (x.nodeType === 3) { const v = tr(x.nodeValue); if (v !== x.nodeValue) x.nodeValue = v; continue; }
    for (const a of ["placeholder", "title", "aria-label"]) { const v = x.getAttribute(a); if (v) { const t = tr(v); if (t !== v) x.setAttribute(a, t); } }
    if (x.tagName === "INPUT" && (x.type === "button" || x.type === "submit") && x.value) x.value = tr(x.value);
  }
}
// React changes text in place (not only by adding nodes), so changed text and labels are translated too
new MutationObserver(ms => {
  if (!DICT) return;
  for (const m of ms) {
    if (m.type === "childList") m.addedNodes.forEach(trNode);
    else if (m.type === "characterData") { const p = m.target.parentElement; if (!p || !p.closest(NO_TR)) trNode(m.target); }
    else if (m.type === "attributes") { const x = m.target, v = x.getAttribute(m.attributeName); if (v && !x.closest(NO_TR)) { const t = tr(v); if (t !== v) x.setAttribute(m.attributeName, t); } }
  }
}).observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["placeholder", "title", "aria-label"] });
{
  const c0 = window.confirm.bind(window), p0 = window.prompt.bind(window), a0 = window.alert.bind(window);
  window.confirm = m => c0(trLines(m));
  window.prompt = (m, d) => p0(trLines(m), d);
  window.alert = m => a0(trLines(m));
}

function toast(msg, ms = 3500) { const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden"); clearTimeout(t._t); t._t = setTimeout(() => t.classList.add("hidden"), ms); }
let SERVER = new URLSearchParams(location.search).get("srv") || store.get("es-server", "main"), SERVERS = [];
async function api(path, opts = {}) {
  const o = Object.assign({ headers: {} }, opts);
  o.headers = Object.assign({}, o.headers); if (!o.headers["X-ES-Server"]) o.headers["X-ES-Server"] = SERVER;
  if (o.json !== undefined) { o.method = o.method || "POST"; o.body = JSON.stringify(o.json); o.headers["Content-Type"] = "application/json"; }
  if (o.method && o.method !== "GET" && CSRF) o.headers["X-ES-CSRF"] = CSRF;
  const r = await fetch(path, o);
  let data = {};
  try { data = await r.json(); } catch (e) {}
  if (r.status === 401 && !path.endsWith("/login") && !path.endsWith("/discord/finish")) { boot(); throw new Error("Please log in"); }
  if (!r.ok) { const e = new Error(data.error || ("Error " + r.status)); e.data = data; e.status = r.status; throw e; }
  return data;
}
async function copyText(t) {
  try { if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(t); return true; } } catch (e) {}
  const ta = document.createElement("textarea"); ta.value = t; ta.style.cssText = "position:fixed;opacity:0;min-height:0"; document.body.appendChild(ta); ta.select();
  let ok = false; try { ok = document.execCommand("copy"); } catch (e) {}
  ta.remove(); return ok;
}
function modal(inner) {
  const bg = document.createElement("div"); bg.className = "modalbg"; bg.innerHTML = `<div class="card">${inner}</div>`;
  bg.onclick = e => { if (e.target === bg) bg.remove(); };
  document.body.appendChild(bg); return bg;
}
/* ---------------- mod browser (BeamNG repository) */
async function modBrowser() {
  const bg = modal(`<div class="row"><h2 style="margin:0">Browse mods</h2><span class="spacer"></span><button class="btn sm" data-x>Close</button></div>
    <p class="small muted">From the official BeamNG repository (beamng.com). Install = download, virus check, ready for players. You can also paste a link to a mod page.</p>
    <div class="row" style="gap:8px;flex-wrap:wrap"><select id="mb_cat" style="flex:1;min-width:140px"></select><select id="mb_ord" style="flex:1;min-width:140px"></select></div>
    <div class="row" style="margin-top:8px"><input type="text" id="mb_q" placeholder="Search, or paste a beamng.com mod link" maxlength="200" style="flex:1"><button class="btn" id="mb_go">Search</button></div>
    <div id="mb_list" style="margin-top:12px"><p class="muted small">Loading…</p></div>`);
  bg.querySelector(".card").style.width = "min(820px,100%)";
  bg.querySelector("[data-x]").onclick = () => { bg.remove(); if (TAB === "mods") show("mods"); };
  let page = 1, installedAny = false;
  const load = async (more) => {
    const L = $("#mb_list", bg); if (!more) { page = 1; L.innerHTML = `<p class="muted small">Loading…</p>`; }
    const qs = new URLSearchParams({ cat: $("#mb_cat", bg).value || "", order: $("#mb_ord", bg).value || "", q: $("#mb_q", bg).value.trim(), page });
    let d; try { d = await api("/api/modbrowser?" + qs); } catch (e) { L.innerHTML = `<div class="banner bad">${esc(e.message)}</div>`; return; }
    if (!$("#mb_cat", bg).options.length) {
      $("#mb_cat", bg).innerHTML = d.cats.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join("");
      $("#mb_ord", bg).innerHTML = Object.entries(d.orders).map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join("");
      $("#mb_cat", bg).value = d.cat; $("#mb_ord", bg).value = d.order;
    }
    const rows = d.items.map(it => `<div class="check" style="align-items:flex-start">
        <img src="/api/modbrowser/icon?id=${it.id}&srv=${encodeURIComponent(SERVER)}" alt="" loading="lazy" width="56" height="56" style="border-radius:8px;object-fit:cover;flex:none;background:var(--surface-2)">
        <div style="flex:1;min-width:0"><b>${esc(it.title)}</b> <span class="small muted">${esc(it.version)}</span>
          <div class="small muted">${[it.author, it.category, it.downloads ? it.downloads.toLocaleString() + " downloads" : "", it.rating ? "★ " + it.rating : "", it.updated ? "updated " + ago(it.updated) : ""].filter(Boolean).map(esc).join(" · ")}</div>
          <div class="small">${esc(it.tagline)}</div>
          <a class="small" href="${esc(it.page)}" target="_blank" rel="noopener noreferrer">Open on beamng.com</a></div>
        ${it.installed ? `<span class="badge good">Installed</span>` : `<button class="btn sm primary" data-inst="${it.id}" data-title="${esc(it.title)}">Install</button>`}</div>`).join("");
    const html = (d.error ? `<div class="banner warn">${esc(d.error)}</div>` : "") + (rows || (d.error ? "" : `<p class="muted small">Nothing found${$("#mb_q", bg).value.trim() ? " in this category - try another category, or paste the mod's link" : ""}.</p>`)) +
      (d.more ? `<div class="row" style="justify-content:center;margin-top:10px"><button class="btn" id="mb_more">${$("#mb_q", bg).value.trim() ? "Search further" : "More"}</button></div>` : "");
    if (more) { $("#mb_more", bg) && $("#mb_more", bg).parentElement.remove(); L.insertAdjacentHTML("beforeend", html); } else L.innerHTML = html;
    if ($("#mb_more", bg)) $("#mb_more", bg).onclick = () => { page++; load(true); };
    L.querySelectorAll("[data-inst]").forEach(b => b.onclick = () => install(b));
    L.querySelectorAll("img").forEach(i => { i.onerror = () => { i.style.visibility = "hidden"; }; });
  };
  const install = async b => {
    b.disabled = true; b.textContent = "Starting…";
    let r; try { r = await api("/api/modbrowser/install", { json: { id: +b.dataset.inst, title: b.dataset.title } }); } catch (e) { b.disabled = false; b.textContent = "Install"; return toast(e.message, 7000); }
    const tick = async () => {
      let j; try { j = await api("/api/modbrowser/job?job=" + r.job); } catch (e) { b.textContent = "Install"; b.disabled = false; return toast(e.message); }
      if (!j.finished) { b.textContent = j.total ? Math.round(100 * j.done / j.total) + "%" : j.done ? fmtSize(j.done) : j.state; return setTimeout(tick, 800); }
      if (j.ok) { b.outerHTML = `<span class="badge good">Installed</span>`; installedAny = true; toast(j.note, 8000); }
      else { b.disabled = false; b.textContent = "Install"; toast(j.error, 10000); }
    };
    tick();
  };
  $("#mb_go", bg).onclick = () => load(false);
  $("#mb_q", bg).onkeydown = e => { if (e.key === "Enter") load(false); };
  $("#mb_cat", bg).onchange = () => load(false); $("#mb_ord", bg).onchange = () => load(false);
  load(false);
}
async function openInvite() {
  let d; try { d = await api("/api/invite"); } catch (e) { return toast(e.message); }
  const bg = modal(`<div class="row"><h2 style="margin:0">Invite friends</h2><span class="spacer"></span><button class="btn sm" data-x>Close</button></div>
    <p class="small muted">Paste this into Discord, WhatsApp or anywhere. ${d.internet ? "" : "<b>No internet address was found yet</b> - check the Health page. "}${d.relay ? "It uses your relay address, so your home IP stays hidden." : ""}</p>
    <div class="row" style="margin-bottom:8px"><button class="btn sm on" data-v="net">${d.internet ? "Friends anywhere" : "Message"}</button><button class="btn sm" data-v="lan">Same Wi-Fi</button></div>
    <textarea id="inv_t" readonly></textarea>
    <label class="f" style="margin-top:10px"><span>Extra line <span class="muted">(rules, your Discord link…)</span></span><input type="text" id="inv_note" maxlength="300" value="${esc(d.note)}" placeholder="Be nice, no ramming at spawn"></label>
    <label class="small" style="display:flex;gap:6px;align-items:center;margin-top:8px"><input type="checkbox" id="inv_credit" ${d.credit ? "checked" : ""}> Mention EasyServer at the end, so friends who want their own server can find it</label>
    <div class="row" style="margin-top:12px"><button class="btn primary" id="inv_copy">Copy invite</button><span class="small muted">Discord shows the **bold** parts in bold.</span></div>`);
  let view = "net";
  const fill = () => { const note = $("#inv_note", bg).value.trim(), credit = $("#inv_credit", bg).checked;
    $("#inv_t", bg).value = (view === "lan" ? d.lan_text : d.base) + (note ? "\n\n" + note : "") + "\n\nNeed BeamMP? https://beammp.com" + (credit ? "\n" + d.credit_line : ""); };
  fill();
  bg.querySelectorAll("[data-v]").forEach(b => b.onclick = () => { view = b.dataset.v; bg.querySelectorAll("[data-v]").forEach(x => x.classList.toggle("on", x === b)); fill(); });
  $("#inv_note", bg).oninput = fill;
  $("#inv_note", bg).onchange = () => api("/api/invite", { json: { note: $("#inv_note", bg).value.trim() } }).catch(() => {});
  $("#inv_credit", bg).onchange = () => { fill(); api("/api/invite", { json: { credit: $("#inv_credit", bg).checked } }).catch(() => {}); };
  bg.querySelector("[data-x]").onclick = () => bg.remove();
  $("#inv_copy", bg).onclick = async () => {
    if (view === "net") api("/api/upnp", { json: { open_for: 7200 } }).catch(() => {});   // "only when needed": friends are about to join
    if (await copyText($("#inv_t", bg).value)) { toast("Invite copied - paste it in Discord"); } else { $("#inv_t", bg).removeAttribute("readonly"); $("#inv_t", bg).select(); toast("Press Ctrl+C to copy"); } };
}
const fmtSize = b => b > 1073741824 ? (b / 1073741824).toFixed(1) + " GB" : b > 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1024)) + " KB";
const fmtDur = s => { s = Math.max(0, s | 0); const d = Math.floor(s / 86400), hh = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60); return d ? `${d}d ${hh}h` : hh ? `${hh}h ${m}m` : `${m}m`; };
const fmtTime = t => t ? new Date(t * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "-";
const ago = t => { const s = Date.now() / 1000 - t; return s < 60 ? "just now" : s < 3600 ? Math.round(s / 60) + " min ago" : s < 86400 ? Math.round(s / 3600) + " h ago" : Math.round(s / 86400) + " d ago"; };

/* ------------------------------------------------------------------ theme */
function applyTheme() {
  const pref = store.get("es-theme", "auto");
  const dark = pref === "dark" || (pref === "auto" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
applyTheme();

/* ------------------------------------------------------------------ icons */
const I = {
  overview: '<path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/>',
  config: '<path d="M19.4 13a7.6 7.6 0 0 0 0-2l2.1-1.6-2-3.5-2.5 1a7.4 7.4 0 0 0-1.7-1L15 3h-4l-.3 2.9a7.4 7.4 0 0 0-1.7 1l-2.5-1-2 3.5L6.6 11a7.6 7.6 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1a7.4 7.4 0 0 0 1.7 1L11 21h4l.3-2.9a7.4 7.4 0 0 0 1.7-1l2.5 1 2-3.5L19.4 13zM13 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z"/>',
  mods: '<path d="M20 6h-8l-2-2H4a2 2 0 0 0-2 2v12c0 1.1.9 2 2 2h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2zm-7 11l-4-4h3V9h2v4h3l-4 4z"/>',
  players: '<path d="M16 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm-8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm0 2c-2.3 0-7 1.2-7 3.5V19h14v-2.5C15 14.2 10.3 13 8 13zm8 0c-.3 0-.6 0-1 .1 1.2.8 2 2 2 3.4V19h6v-2.5c0-2.3-4.7-3.5-7-3.5z"/>',
  network: '<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm6.9 6h-2.9a15.7 15.7 0 0 0-1.4-3.6A8 8 0 0 1 18.9 8zM12 4c.8 1.2 1.5 2.5 1.9 4h-3.8c.4-1.4 1.1-2.8 1.9-4zM4.3 14a8.2 8.2 0 0 1 0-4h3.4a16.5 16.5 0 0 0 0 4H4.3zm.8 2h2.9c.3 1.3.8 2.5 1.4 3.6A8 8 0 0 1 5.1 16zM8 8H5.1a8 8 0 0 1 4.3-3.6C8.8 5.5 8.4 6.7 8 8zm4 12c-.8-1.2-1.5-2.5-1.9-4h3.8c-.4 1.4-1.1 2.8-1.9 4zm2.3-6H9.7a14.7 14.7 0 0 1 0-4h4.6a14.7 14.7 0 0 1 0 4zm.3 5.6c.6-1.1 1.1-2.3 1.4-3.6h2.9a8 8 0 0 1-4.3 3.6zm1.7-5.6a16.5 16.5 0 0 0 0-4h3.4a8.2 8.2 0 0 1 0 4h-3.4z"/>',
  updates: '<path d="M12 4V1L8 5l4 4V6a6 6 0 0 1 6 6 6 6 0 0 1-.7 2.8l1.5 1.5A8 8 0 0 0 12 4zm0 14a6 6 0 0 1-6-6c0-1 .3-2 .7-2.8L5.2 7.7A8 8 0 0 0 12 20v3l4-4-4-4v3z"/>',
  logs: '<path d="M14 2H6a2 2 0 0 0-2 2v16c0 1.1.9 2 2 2h12a2 2 0 0 0 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>',
  notifications: '<path d="M12 22a2 2 0 0 0 2-2h-4a2 2 0 0 0 2 2zm6-6v-5c0-3.1-1.6-5.6-4.5-6.3V4a1.5 1.5 0 0 0-3 0v.7C7.6 5.4 6 7.9 6 11v5l-2 2v1h16v-1l-2-2z"/>',
  settings: '<path d="M12 1 3 5v6c0 5.6 3.8 10.7 9 12 5.2-1.3 9-6.4 9-12V5l-9-4zm0 10.9h7c-.5 4.1-3.3 7.8-7 8.9V12H5V6.3l7-3.1v8.7z"/>',
  servers: '<path d="M4 3h16a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zm0 8h16a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1zm2-6v2h2V5H6zm0 8v2h2v-2H6zM4 19h16v2H4z"/>',
  sun: '<path d="M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM2 13h2a1 1 0 0 0 0-2H2a1 1 0 0 0 0 2zm18 0h2a1 1 0 0 0 0-2h-2a1 1 0 0 0 0 2zM11 2v2a1 1 0 0 0 2 0V2a1 1 0 0 0-2 0zm0 18v2a1 1 0 0 0 2 0v-2a1 1 0 0 0-2 0zM5.99 4.58a1 1 0 0 0-1.41 1.41l1.06 1.06a1 1 0 0 0 1.41-1.41L5.99 4.58zm12.37 12.37a1 1 0 0 0-1.41 1.41l1.06 1.06a1 1 0 0 0 1.41-1.41l-1.06-1.06zm1.06-10.96a1 1 0 0 0-1.41-1.41l-1.06 1.06a1 1 0 0 0 1.41 1.41l1.06-1.06zM7.05 18.36a1 1 0 0 0-1.41-1.41l-1.06 1.06a1 1 0 0 0 1.41 1.41l1.06-1.06z"/>',
  moon: '<path d="M12 3a9 9 0 1 0 9 9c0-.5 0-.9-.1-1.4A5.5 5.5 0 0 1 12.4 3.1L12 3z"/>',
  logout: '<path d="M10 17l1.4-1.4-2.6-2.6H20v-2H8.8l2.6-2.6L10 7l-5 5 5 5zM4 5h8V3H4a2 2 0 0 0-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/>',
};
const LOGO_SVG = `<svg width="100%" height="100%" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="lga" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2f8cff"/><stop offset="1" stop-color="#1747b8"/></linearGradient><linearGradient id="lgb" gradientUnits="userSpaceOnUse" x1="0" y1="92" x2="0" y2="222"><stop offset="0" stop-color="#ffb24a"/><stop offset="1" stop-color="#ff6516"/></linearGradient></defs><rect width="512" height="512" rx="112" fill="url(#lga)"/><g fill="none" stroke="#fff" stroke-linecap="round"><path d="M192 148A136 136 0 1 0 320 148" stroke-width="40"/><path d="M124 300H388M256 300V392" stroke-width="34"/></g><circle cx="256" cy="300" r="44" fill="#fff"/><circle cx="256" cy="300" r="17" fill="#1f5fd6"/><path d="M256 104V214" stroke="url(#lgb)" stroke-width="40" stroke-linecap="round"/></svg>`;
const icon = n => `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">${I[n]}</svg>`;
const TABS = [["overview","Overview"],["servers","Servers"],["config","Config"],["mods","Mods"],["players","Players"],["network","Health"],["updates","Updates"],["logs","Logs"],["notifications","Notifications"],["settings","Settings"]];

/* ------------------------------------------------------------------ boot / auth */
async function approveFromLink(name) {
  const srv = SERVERS.find(x => x.id === SERVER) || {};
  history.replaceState(null, "", location.pathname + "#config");
  if (name && confirm("Let " + name + " join " + (srv.name || "this server") + "?\n\nThey are added to the allow-list (Config -> Who can join) and can join right away.")) {
    try {
      const al = await api("/api/allowlist");
      if (!al.names.some(n => n.toLowerCase() === name.toLowerCase())) al.names.push(name);
      await api("/api/allowlist", { json: { enabled: al.enabled, names: al.names } });
      toast(name + " can join now");
    } catch (e) { toast(e.message); }
  }
  show("config");
}

// Put the server computer to sleep (Overview "Sleep PC" and Settings -> Sleep & wake-up). True once it's on its way.
async function sleepComputer(note) {
  if (!confirm((note ? note + "\n\n" : "") + "Put the server computer to sleep now? The game servers pause and players are disconnected.\n\nWake it with the phone app's Wake up button (if Wake-on-LAN is set up) or its power button.")) return false;
  try { await api("/api/power/sleep", { json: {} }); } catch (e) {
    if (e.status !== 409 || !confirm(e.message + "\n\nSleep anyway?")) { toast(e.message, 6000); return false; }
    try { await api("/api/power/sleep", { json: { force: true } }); } catch (e2) { toast(e2.message, 6000); return false; }
  }
  toast("💤 Going to sleep in a few seconds", 6000);
  return true;
}

const ROLE_TABS = { viewer: ["overview", "players", "network", "logs", "notifications"], moderator: ["overview", "players", "network", "logs", "notifications"] };
const myRole = () => (SESSION.server_roles && SESSION.server_roles[SERVER]) || null;
const myTabs = () => {
  const r = myRole();
  if (r && r.perms) {                    // custom role: base tabs + what it may change
    const extra = { config: ["config"], mods: ["mods"], settings: ["settings", "updates", "servers"] };
    const keep = new Set(["overview", "players", "network", "logs", "notifications"]);
    r.perms.forEach(p => (extra[p] || []).forEach(t => keep.add(t)));
    return TABS.filter(t => keep.has(t[0]));
  }
  const role = r ? r.role : SESSION.role;
  return ROLE_TABS[role] ? TABS.filter(t => ROLE_TABS[role].includes(t[0])) : TABS;
};
/* ------------------------------------------------------------------ security alerts */
async function stopAlerts(id) {
  try { const r = await api("/api/security/ack", { json: { id } }); toast(r.stopped ? "Alerts stopped - you won't get reminders for this any more" : "Already stopped"); } catch (e) { toast(e.message); }
  checkSecurity().catch(() => {});
}
/* ------------------------------------------------------------------ status helpers */
function statePill(state) {
  const map = { running: ["good", "Running"], stopped: ["", "Stopped"], failed: ["bad", "Crashed"], starting: ["warn", "Starting"], restarting: ["warn", "Restarting"], stopping: ["warn", "Stopping"] };
  const [cls, label] = map[state] || ["", state || "Unknown"];
  return `<span class="pill ${cls}"><span class="dot"></span>${esc(label)}</span>`;
}
/* Before a server's first start: look over the settings once */
async function reviewGate(id, starting = true) {
  const hdr = id ? { headers: { "X-ES-Server": id } } : {};
  const r = await api("/api/review", hdr);
  if (r.reviewed) return true;
  const yes = (b, good = true) => `<span class="pill ${b === good ? "good" : "warn"}"><span class="dot"></span>${b ? "On" : "Off"}</span>`;
  const g = r.game, sc = r.security, p = r.protection, c = r.cars, rs = r.restarts;
  const every = (on, n, at) => on ? (n === 24 ? "Daily at " + esc(at) : "Every " + n + " h from " + esc(at)) : "Off";
  return new Promise(resolve => {
    const back = document.createElement("div");
    back.className = "rv-back";
    back.innerHTML = `<div class="rv"><h2 style="margin-top:0">Check the settings before starting "${esc(r.server)}"</h2>
      <p class="small muted">You only need to do this once per server. Anything you want to change? Open the settings first - nothing is started yet.</p>
      <table style="width:100%;border-collapse:collapse"><tbody>
        <tr><td>Server name</td><td><b>${esc(g.name || "-")}</b></td></tr>
        <tr><td>Map</td><td>${esc(g.map || "-")}</td></tr>
        <tr><td>Players / cars per player</td><td>${esc(g.max_players ?? "-")} / ${esc(g.max_cars ?? "-")}</td></tr>
        <tr><td>Server list</td><td>${g.private ? "Private (hidden from the list)" : "Public (anyone can find it)"}</td></tr>
        <tr><td>Who can join</td><td>${g.allowlist ? "Only players on your allow-list" : "Everyone"}</td></tr>
        <tr><td>AuthKey</td><td>${g.authkey ? yes(true) : `<span class="pill bad"><span class="dot"></span>Missing - the server can't start</span>`}</td></tr>
        <tr><td>Two-step login for the dashboard</td><td>${yes(sc.totp)}</td></tr>
        <tr><td>Dashboard reachable from the internet</td><td>${yes(sc.remote, false)}${sc.remote && !sc.https ? " (without HTTPS!)" : ""}</td></tr>
        <tr><td>Security alerts / Discord</td><td>${yes(sc.alerts)} ${yes(sc.discord)}</td></tr>
        <tr><td>Anti-bot / chat filter</td><td>${yes(p.antibot)} ${yes(p.filter)}</td></tr>
        <tr><td>Admins in game</td><td>${p.admins.length ? esc(p.admins.join(", ")) : "None"}</td></tr>
        <tr><td>Hide my IP (relay)</td><td>${yes(p.relay)}</td></tr>
        <tr><td>Remove all cars</td><td>${every(c.clear, c.every, c.at)}</td></tr>
        <tr><td>Scheduled restart</td><td>${every(rs.on, rs.every, rs.at)}</td></tr>
      </tbody></table>
      <div class="row" style="margin-top:18px;gap:8px;justify-content:flex-end">
        <button class="btn" id="rv_settings">Open Settings</button><button class="btn" id="rv_config">Open Config</button>
        <button class="btn primary" id="rv_ok" ${g.authkey || !starting ? "" : "disabled"}>${starting ? "Looks good - start" : "Looks good"}</button></div></div>`;
    document.body.appendChild(back);
    const done = (v, view) => { back.remove(); if (view) { if (id && id !== SERVER) switchServer(id); show(view); } resolve(v); };
    back.querySelector("#rv_settings").onclick = () => done(false, "settings");
    back.querySelector("#rv_config").onclick = () => done(false, "config");
    back.querySelector("#rv_ok").onclick = async () => { try { await api("/api/review/ok", Object.assign({ json: {} }, hdr)); done(true); } catch (e) { toast(e.message); } };
    back.addEventListener("click", e => { if (e.target === back) done(false); });
  });
}
async function serverAction(action, btn) {
  if (action === "start" && !(await reviewGate())) return;
  if (action !== "start" && !confirm(action === "stop" ? "Stop the server? Players will be disconnected." : "Restart the server? Players will be disconnected.")) return;
  if (btn) btn.disabled = true;
  try { await api("/api/server/action", { json: { action } }); toast(action === "stop" ? "Server stopped" : action === "start" ? "Server starting…" : "Server restarting…"); }
  catch (e) { toast(e.message); }
  setTimeout(() => show(TAB), 1500);
}

/* ------------------------------------------------------------------ views */
const VIEWS = {};

/* ---------------- servers */
/* Servers is React now (pages.jsx) */

/* ---------------- config */
VIEWS.config = async m => {
  const [d, al, mv, ja, ex, md, rs] = await Promise.all([api("/api/config"), api("/api/allowlist"), api("/api/mapvote"), api("/api/joinalerts"), api("/api/extras"), api("/api/moderation"), api("/api/restarts")]);
  const mode = store.get("es-config-mode", "form");
  const issuesHtml = list => list.length ? list.map(i => `<div class="issue ${i.level}"><span class="ic">${i.level === "error" ? "!" : i.level === "warning" ? "⚠" : "i"}</span><span>${esc(i.message)}</span>${i.line ? `<span class="ln">line ${i.line}</span>` : ""}</div>`).join("") : `<div class="issue info"><span class="ic">✓</span><span>No problems found.</span></div>`;
  const opts = (cur) => {
    const all = [...new Set([...(d.maps.mods || []), ...d.maps.builtin])];
    if (cur && !all.includes(cur)) all.unshift(cur);
    return `<optgroup label="Built-in maps">${d.maps.builtin.map(x => `<option ${x === cur ? "selected" : ""}>${esc(x)}</option>`).join("")}</optgroup>` +
      (d.maps.mods.length ? `<optgroup label="Map mods">${d.maps.mods.map(x => `<option ${x === cur ? "selected" : ""}>${esc(x)}</option>`).join("")}</optgroup>` : "") +
      (cur && !d.maps.builtin.includes(cur) && !d.maps.mods.includes(cur) ? `<optgroup label="Current"><option selected>${esc(cur)}</option></optgroup>` : "");
  };
  const field = f => {
    const id = "f_" + f.section + "_" + f.key;
    if (f.type === "bool") return `<label class="toggle"><input type="checkbox" id="${id}" ${f.value ? "checked" : ""}><span><b>${esc(f.label)}</b><small>${esc(f.help)}</small></span></label>`;
    if (f.type === "map") return `<label class="f"><span>${esc(f.label)}</span><select id="${id}">${opts(f.value)}</select><small>${esc(f.help)}</small></label>`;
    const t = f.type === "int" ? `type="number" min="${f.min ?? ""}" max="${f.max ?? ""}"` : `type="text" maxlength="${f.max ?? 500}"`;
    return `<label class="f"><span>${esc(f.label)}</span><input ${t} id="${id}" value="${esc(f.value ?? "")}"><small>${esc(f.help)}</small></label>`;
  };
  const basic = d.fields.filter(f => !f.advanced && f.type !== "bool"), toggles = d.fields.filter(f => !f.advanced && f.type === "bool"), adv = d.fields.filter(f => f.advanced);
  m.innerHTML = `
    <div class="row"><div><h1>Server config</h1><p class="sub">Change settings without touching files. Everything is checked before saving.</p></div><span class="spacer"></span>
      <div class="seg"><button data-mode="form" class="${mode === "form" ? "on" : ""}">Simple</button><button data-mode="raw" class="${mode === "raw" ? "on" : ""}">Text (TOML)</button></div></div>
    <div id="issues">${issuesHtml(d.issues)}</div>
    <div id="formmode" class="${mode === "form" ? "" : "hidden"}">
      <div class="grid g2" style="margin-top:12px">
        <div class="card"><h2>Basics</h2>${basic.map(field).join("")}</div>
        <div class="grid" style="align-content:start">
          <div class="card"><h2>Options</h2>${toggles.map(field).join("")}</div>
          <div class="card"><h2>AuthKey</h2><p class="small muted">${d.has_authkey ? "✓ An AuthKey is saved (encrypted). Paste a new one to replace it." : "No AuthKey yet. Get one free at keymaster.beammp.com (Keys → +)."}</p>
            <div class="row"><input type="password" id="ak" placeholder="Paste AuthKey" autocomplete="off"><button class="btn" id="saveak">Save key</button></div></div>
          <details class="card"><summary><b>Advanced</b></summary><div style="margin-top:14px">${adv.map(field).join("")}</div></details>
        </div>
      </div>
      <div class="row" style="margin-top:16px"><button class="btn primary" id="saveform">Save changes</button><span class="muted small" id="note"></span></div>
    </div>
    <div class="card" style="margin-top:16px" id="whocard"><div class="row"><h2 style="margin:0">Who can join</h2><span class="spacer"></span>
        <span class="pill ${al.enabled ? "good" : ""}"><span class="dot"></span>${al.enabled ? "Invite-only" : "Anyone can join"}</span></div>
      <p class="small muted">BeamMP has no join password, so this works like a guest list: when it's on, only the BeamMP usernames below can join and everyone else gets a friendly "invite-only" message. Guests (players without an account) are refused while it's on. Changes work immediately - no restart.</p>
      ${al.plugin ? "" : `<div class="issue warning"><span class="ic">⚠</span><span>The EasyServerStats plugin is missing, so the list can't be enforced. Run the installer's Update once.</span></div>`}
      <label class="toggle"><input type="checkbox" id="al_on" ${al.enabled ? "checked" : ""}><span><b>Only let in players on the list</b><small>Players already online are not kicked</small></span></label>
      <label class="f"><span>Allowed players (one BeamMP username per line, not case-sensitive)</span><textarea id="al_names" rows="6" spellcheck="false" placeholder="Bazsi&#10;Dani&#10;Zoli" style="min-height:120px">${esc(al.names.join("\n"))}</textarea><small>${al.names.length} on the list</small></label>
      ${(al.denied = al.denied.filter(x => !al.names.some(n => n.toLowerCase() === x.name.toLowerCase()))).length ? `<p class="small" style="margin:14px 0 6px"><b>Recently refused</b> <span class="muted">(last 7 days)</span></p><div class="row" style="flex-wrap:wrap;gap:6px">${al.denied.map(x => `<span class="badge">${esc(x.name)}${x.guest ? " · guest" : ""} · ${esc(ago(x.t))}${x.guest ? "" : ` <a href="#" data-allow="${esc(x.name)}">+ allow</a>`}</span>`).join("")}</div>` : ""}
      <div class="row" style="margin-top:14px"><button class="btn primary" id="al_save">Save list</button></div>
    </div>
    <div class="card" style="margin-top:16px" id="votecard"><div class="row"><h2 style="margin:0">Map vote</h2><span class="spacer"></span>
        <span class="pill ${mv.enabled ? "good" : ""}"><span class="dot"></span>${mv.enabled ? "On" : "Off"}</span></div>
      <p class="small muted">Players type <span class="mono">/vote</span> in the game chat to see the maps, then <span class="mono">/vote 2</span> to pick one. When more than half of the players online agree, everyone is told and the server switches about 30 seconds later. At most one change every 5 minutes.</p>
      <label class="toggle"><input type="checkbox" id="mv_on" ${mv.enabled ? "checked" : ""}><span><b>Let players vote for the map</b><small>Pick at least two maps below</small></span></label>
      <div class="row" style="flex-wrap:wrap;gap:6px;margin-top:8px">${mv.available.map(x => `<label class="badge" style="cursor:pointer"><input type="checkbox" data-vm="${esc(x)}" ${mv.maps.includes(x) || (!mv.maps.length) ? "checked" : ""}> ${esc(x)}</label>`).join("")}</div>
      <div class="row" style="margin-top:14px"><button class="btn primary" id="mv_save">Save map vote</button></div>
    </div>
    <div class="card" style="margin-top:16px" id="rscard"><div class="row"><h2 style="margin:0">Restarts &amp; updates</h2><span class="spacer"></span>
        <span class="pill ${rs.on ? "good" : ""}"><span class="dot"></span>${rs.on ? "Restart " + (rs.every === 24 ? "daily " + esc(rs.at) : "every " + rs.every + " h") : "Off"}</span></div>
      <p class="small muted">A fresh start now and then keeps a long-running server smooth. Players get a countdown in the chat first and can rejoin right after.</p>
      <label class="toggle"><input type="checkbox" id="rs_on" ${rs.on ? "checked" : ""}><span><b>Restart the server on a schedule</b><small>Off by default</small></span></label>
      <div class="grid g3" style="gap:12px;margin:4px 0 8px">
        <label class="f" style="margin:0"><span>How often</span><select id="rs_every">${rs.every_choices.map(n => `<option value="${n}" ${n === rs.every ? "selected" : ""}>${n === 24 ? "Once a day" : "Every " + n + " hour" + (n === 1 ? "" : "s")}</option>`).join("")}</select></label>
        <label class="f" style="margin:0"><span>${rs.every === 24 ? "At" : "Starting at"}</span><input type="time" id="rs_at" value="${esc(rs.at)}" style="color-scheme:light dark;color:inherit"><small>This computer's time</small></label>
        <label class="f" style="margin:0"><span>Countdown in chat</span><select id="rs_warn">${rs.warn_choices.map(n => `<option value="${n}" ${n === rs.warn ? "selected" : ""}>${n ? n + " min before" : "No countdown"}</option>`).join("")}</select></label>
      </div>
      <label class="f"><span>If players are online</span><select id="rs_when"><option value="countdown" ${rs.when === "countdown" ? "selected" : ""}>Restart anyway, after the countdown</option><option value="empty" ${rs.when === "empty" ? "selected" : ""}>Wait until nobody is online (up to 2 hours, then skip)</option></select></label>
      ${rs.next ? `<p class="small muted">Next restart: <b>${esc(new Date(rs.next * 1000).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" }))}</b></p>` : ""}
      ${SERVER === "main" ? `<label class="toggle"><input type="checkbox" id="rs_auto" ${rs.auto_update ? "checked" : ""}><span><b>Install BeamMP updates automatically</b><small>At the scheduled restart, if a new BeamMP server version is out. All servers use the same BeamMP program, so the others restart too.${rs.update_available ? " <b>An update is available now.</b>" : ""}</small></span></label>` : ""}
      <div class="row" style="margin-top:12px"><button class="btn primary" id="rs_save">Save restarts</button></div>
    </div>
    <div id="vehrules"></div>
    <div id="cfg111"></div>
    <div id="cfg17"></div>
    <div id="evcard"></div>
    <div class="card" style="margin-top:16px" id="mdcard"><div class="row"><h2 style="margin:0">Moderation &amp; anti-bot</h2><span class="spacer"></span>
        <span class="pill ${md.antibot ? "good" : ""}"><span class="dot"></span>${md.antibot ? "Anti-bot on" : "Anti-bot off"}</span></div>
      <p class="small muted">Kick, mute and ban players on the Players page. Everything here works right away, no restart needed.</p>
      <label class="f"><span>Admins (comma-separated BeamMP names)</span><input type="text" id="md_admins" value="${esc(md.admins.join(", "))}" placeholder="e.g. Bazsi, Dani"><small>Admins can use <span class="mono">/kick name</span>, <span class="mono">/ban name 1d reason</span>, <span class="mono">/mute name 10</span>, <span class="mono">/unmute</span> and <span class="mono">/unban</span> in the game chat</small></label>
      <label class="toggle"><input type="checkbox" id="md_filter" ${md.filter ? "checked" : ""}><span><b>Chat filter</b><small>Hides messages with the words below, @everyone and Discord invite links, and refuses player names with links or those words. 3 blocked messages in 10 minutes = 5 minute mute. Off by default</small></span></label>
      <label class="f"><span>Blocked words (comma-separated)</span><input type="text" id="md_words" value="${esc(md.words.join(", "))}" placeholder="words you don't want in chat"></label>
      <label class="f"><span>Kick words (comma-separated)</span><input type="text" id="md_kwords" value="${esc((md.kickwords || []).join(", "))}" placeholder="words that get a player removed at once"><small>A player who writes one of these is removed straight away - even with the chat filter off. Whole words only ("ass" doesn't match "class"), capitals don't matter. Admins are never removed. Empty = off</small></label>
      <label class="f" style="max-width:260px"><span>When someone uses a kick word</span><select id="md_kact">${[["kick", "Kick them (they can rejoin)"], ["ban60", "Ban for 1 hour"], ["ban1440", "Ban for 1 day"], ["ban10080", "Ban for 7 days"], ["banperm", "Ban forever"]].map(o => `<option value="${o[0]}" ${md.kickwords_action === o[0] ? "selected" : ""}>${o[1]}</option>`).join("")}</select></label>
      <label class="toggle"><input type="checkbox" id="md_spam" ${md.spam ? "checked" : ""}><span><b>Anti-spam</b><small>More than the number below of messages in 10 seconds = 2 minute mute. Admins are never muted. Off by default</small></span></label>
      <label class="f" style="max-width:220px"><span>Messages per 10 seconds</span><input type="number" id="md_spamlimit" min="2" max="30" value="${esc(md.spam_limit)}"></label>
      <h2 style="margin-top:16px">Reports, vote kick &amp; chat history</h2>
      <label class="toggle"><input type="checkbox" id="md_report" ${md.report ? "checked" : ""}><span><b>Player reports</b><small>Players type <span class="mono">/report name what happened</span>. You get an alert (dashboard, Discord, phone - whatever is set up under Notifications) with the chat just before it, and admins in the game see it too. A player can send one report a minute. On by default</small></span></label>
      <label class="toggle"><input type="checkbox" id="md_votekick" ${md.votekick ? "checked" : ""}><span><b>Vote kick</b><small>When no admin is online, players can type <span class="mono">/votekick name reason</span>. If more than half of the others type <span class="mono">/yes</span> within 90 seconds, that player is kicked and can't rejoin for 10 minutes. Admins can't be voted out, players who just joined can't vote, and nobody can start more than one vote every 5 minutes. Off by default</small></span></label>
      <label class="f" style="max-width:260px"><span>Players needed online for a vote kick</span><input type="number" id="md_vkmin" min="3" max="20" value="${esc(md.votekick_min)}"><small>So two friends can't kick the third</small></label>
      <label class="toggle"><input type="checkbox" id="md_chatlog" ${md.chatlog ? "checked" : ""}><span><b>Keep a chat history</b><small>Saves the game chat on this computer so you can search it on the Players page (about the last few weeks, up to 10 MB). It never leaves this computer. On by default</small></span></label>
      <h2 style="margin-top:16px">Anti-bot</h2>
      <p class="small muted">Stops bots from filling your server. Cloudflare can't protect a game server, so this works inside the game instead. Players who passed the check: ${esc(md.verified)}.</p>
      <label class="toggle"><input type="checkbox" id="md_antibot" ${md.antibot ? "checked" : ""}><span><b>Turn on anti-bot</b><small>Off by default. Turns on the checks below</small></span></label>
      <label class="toggle"><input type="checkbox" id="md_verify" ${md.verify ? "checked" : ""}><span><b>Join check</b><small>New players must type a code shown in the chat (like <span class="mono">/verify 4821</span>) within 2 minutes, or they're kicked. Each player only does this once</small></span></label>
      <label class="toggle"><input type="checkbox" id="md_guests" ${md.guests ? "" : "checked"}><span><b>Block guests</b><small>Players without a BeamMP account can't join - bots usually use guest accounts</small></span></label>
      <div class="grid g2" style="gap:12px">
        <label class="f" style="margin:0"><span>Max players from one internet connection</span><input type="number" id="md_perip" min="0" max="20" value="${esc(md.per_ip)}"><small>0 = no limit. Your home network is never limited</small></label>
        <label class="f" style="margin:0"><span>Max new players per minute</span><input type="number" id="md_flood" min="0" max="100" value="${esc(md.join_flood)}"><small>More than this pauses new joins for 2 minutes and alerts you. 0 = no limit</small></label>
      </div>
      <div class="row" style="margin-top:14px"><button class="btn primary" id="md_save">Save moderation</button></div>
    </div>
    <div class="card" style="margin-top:16px" id="excard"><div class="row"><h2 style="margin:0">Cars &amp; chat</h2><span class="spacer"></span>
        <span class="pill ${ex.clear ? "good" : ""}"><span class="dot"></span>${ex.clear ? "Cleanup " + (ex.every === 24 ? "daily " + esc(ex.at) : "every " + ex.every + " h") : "Cleanup off"}</span></div>
      <p class="small muted">Keeps the map tidy and adds a few chat commands. Everything here works right away - no restart, and players don't need to install anything.</p>
      ${ex.plugin ? "" : `<div class="issue warning"><span class="ic">⚠</span><span>The EasyServerStats plugin is missing on this server, so these can't work. Run the installer again once.</span></div>`}
      <label class="toggle"><input type="checkbox" id="ex_clear" ${ex.clear ? "checked" : ""}><span><b>Remove all cars on a schedule</b><small>Clears wrecks and forgotten cars. Players get a countdown in the chat first, then can spawn a fresh car right away. On by default.</small></span></label>
      <div class="grid g3" style="gap:12px;margin:4px 0 8px">
        <label class="f" style="margin:0"><span>How often</span><select id="ex_every">${ex.every_choices.map(n => `<option value="${n}" ${n === ex.every ? "selected" : ""}>${n === 24 ? "Once a day" : "Every " + n + " hour" + (n === 1 ? "" : "s")}</option>`).join("")}</select><small>Busy server? Clear more often.</small></label>
        <label class="f" style="margin:0"><span id="ex_at_label">${ex.every === 24 ? "At" : "Starting at"}</span><input type="time" id="ex_at" value="${esc(ex.at)}" style="color-scheme:light dark;color:inherit"><small>This computer's time</small></label>
        <label class="f" style="margin:0"><span>Countdown in chat</span><select id="ex_warn">${ex.warn_choices.map(n => `<option value="${n}" ${n === ex.warn ? "selected" : ""}>${n ? n + " min before" : "No countdown"}</option>`).join("")}</select><small>Then reminders at 15, 10, 5, 2, 1 min, 30 s and 10…1</small></label>
      </div>
      <p class="small muted" id="ex_next">${ex.next_clear ? "Next cleanup: <b>" + esc(new Date(ex.next_clear * 1000).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" })) + "</b>" : ""}</p>
      <label class="toggle"><input type="checkbox" id="ex_afk" ${ex.afk ? "checked" : ""}><span><b>Remove abandoned cars</b><small>A car that hasn't moved for the time below is removed (its owner gets a warning 1 minute before). Covers AFK players and spare cars left at intersections. Cars of players who leave are removed by BeamMP itself.</small></span></label>
      <label class="f" style="max-width:220px"><span>After (minutes)</span><input type="number" id="ex_afkmin" min="2" max="120" value="${esc(ex.afk_minutes)}"></label>
      <h2 style="margin-top:16px">Chat commands</h2>
      <label class="toggle"><input type="checkbox" id="ex_countdown" ${ex.countdown ? "checked" : ""}><span><b>/countdown</b><small>Anyone can type <span class="mono">/countdown 5</span> for a "3… 2… 1… GO!" in the chat - for drag races and touge runs</small></span></label>
      <label class="toggle"><input type="checkbox" id="ex_tag" ${ex.tag ? "checked" : ""}><span><b>/tag</b><small>Players pick a tag that shows in front of their chat messages, like <span class="mono">[DRIFT] Dani: anyone tandem?</span>. <span class="mono">/tag off</span> removes it</small></span></label>
      <label class="f"><span>Tags players can choose (comma-separated)</span><input type="text" id="ex_tags" value="${esc(ex.tags.join(", "))}" maxlength="300"><small>Letters, numbers and - only, up to 12 characters each</small></label>
      <label class="toggle"><input type="checkbox" id="ex_top" ${ex.top ? "checked" : ""}><span><b>/top server records</b><small>Tracks top speed, distance driven and the longest drive without a reset. <span class="mono">/top</span> shows the leaders, <span class="mono">/top me</span> your own. Also shown on the Players page</small></span></label>
      <p class="small muted">Players can type <span class="mono">/help</span> to see the commands that are on.</p>
      <div class="row" style="margin-top:14px"><button class="btn primary" id="ex_save">Save cars &amp; chat</button></div>
    </div>
    <div class="card" style="margin-top:16px" id="jacard"><div class="row"><h2 style="margin:0">Join alerts (Discord)</h2><span class="spacer"></span>
        <span class="pill ${ja.enabled ? "good" : ""}"><span class="dot"></span>${ja.enabled ? "On" : "Off"}</span></div>
      <p class="small muted">Invite your friends automatically: when one of the players below joins this server, a message goes to your Discord channel ("Dani just joined - 3/8 online, come and play!"). Leave the list empty to announce everyone. When someone who isn't on the allow-list tries to join, you also get a Discord message with a one-click <b>Approve</b> link (turn on "Refused players" under Settings → Notifications).</p>
      ${ja.discord ? "" : `<div class="issue warning"><span class="ic">⚠</span><span>Add your Discord webhook under Settings → Notifications first.</span></div>`}
      <label class="toggle"><input type="checkbox" id="ja_on" ${ja.enabled ? "checked" : ""}><span><b>Send join alerts</b><small>Uses your Discord webhook from Settings</small></span></label>
      <label class="f"><span>Players to announce (one per line, empty = everyone)</span><textarea id="ja_players" rows="4" spellcheck="false" placeholder="Dani&#10;Zoli" style="min-height:90px">${esc(ja.players.join("\n"))}</textarea></label>
      <label class="f"><span>Who to ping (optional)</span><input id="ja_mention" type="text" value="${esc(ja.mention)}" placeholder="@here, <@123456789012345678> or <@&role id>"><small>In Discord: Settings → Advanced → Developer Mode, then right-click a person or role → Copy ID</small></label>
      <label class="toggle"><input type="checkbox" id="ja_addr" ${ja.address ? "checked" : ""}><span><b>Include the server address</b><small>Your public IP and port, so friends can direct-connect. Only do this in a private channel.</small></span></label>
      <div class="row" style="margin-top:14px"><button class="btn primary" id="ja_save">Save join alerts</button><button class="btn" id="ja_test">Save + send test</button></div>
    </div>
    <div id="rawmode" class="${mode === "raw" ? "" : "hidden"}" style="margin-top:12px">
      <div class="card"><textarea id="raw" spellcheck="false">${esc(d.raw)}</textarea>
      <div class="row" style="margin-top:12px"><button class="btn primary" id="saveraw">Save</button><button class="btn" id="checkraw">Check</button><span class="muted small">Your AuthKey isn't shown here - it's stored encrypted.</span></div></div>
    </div>`;
  m.querySelectorAll("[data-mode]").forEach(b => b.onclick = () => { store.set("es-config-mode", b.dataset.mode); show("config"); });
  const showIssues = list => { $("#issues").innerHTML = issuesHtml(list || []); };
  const portOk = newPort => {
    const oldPort = String(d.fields.find(f => f.key === "Port")?.value ?? "");
    if (!newPort || String(newPort) === oldPort) return true;
    return confirm("This changes your network settings:\n\n" +
      "• Server port " + oldPort + " → " + newPort + "\n" +
      "• This computer's firewall: port " + newPort + " is opened (TCP + UDP) and " + oldPort + " is closed\n" +
      "• Your router is NOT changed - forward port " + newPort + " there yourself for internet play\n" +
      "• Players who saved your server must use the new port\n\nContinue?");
  };
  const networkNote = r => { if (r.network) setTimeout(() => toast("🌐 " + r.network, 9000), 2600); };
  $("#saveform").onclick = async () => {
    const fields = d.fields.map(f => { const el = $("#f_" + f.section + "_" + f.key); return { section: f.section, key: f.key, value: f.type === "bool" ? el.checked : el.value }; });
    if (!portOk((fields.find(f => f.key === "Port") || {}).value)) return;
    try { const r = await api("/api/config/save", { json: { fields } }); showIssues(r.issues); toast(r.note); networkNote(r); }
    catch (e) { showIssues(e.data && e.data.issues); toast(e.message); }
  };
  let tmr;
  $("#raw").oninput = () => { clearTimeout(tmr); tmr = setTimeout(async () => { try { showIssues((await api("/api/config/validate", { json: { raw: $("#raw").value } })).issues); } catch (e) {} }, 500); };
  $("#checkraw").onclick = async () => showIssues((await api("/api/config/validate", { json: { raw: $("#raw").value } })).issues);
  $("#saveraw").onclick = async () => {
    const m2 = $("#raw").value.match(/^\s*Port\s*=\s*(\d+)/m);
    if (!portOk(m2 && m2[1])) return;
    try { const r = await api("/api/config/save", { json: { raw: $("#raw").value } }); showIssues(r.issues); toast(r.note); networkNote(r); }
    catch (e) { showIssues(e.data && e.data.issues); toast(e.message); }
  };
  m.querySelectorAll("[data-allow]").forEach(a => a.onclick = e => {
    e.preventDefault();
    const ta = $("#al_names"), have = ta.value.split("\n").map(x => x.trim().toLowerCase());
    if (!have.includes(a.dataset.allow.toLowerCase())) ta.value = (ta.value.trim() ? ta.value.trim() + "\n" : "") + a.dataset.allow;
    toast(a.dataset.allow + " added - press Save list");
  });
  const jaSave = async test => {
    const body = { enabled: $("#ja_on").checked, players: $("#ja_players").value.split("\n").map(x => x.trim()).filter(Boolean),
                   mention: $("#ja_mention").value, address: $("#ja_addr").checked, test };
    try { const r = await api("/api/joinalerts", { json: body }); toast(r.note); if (!test) show("config"); } catch (e) { toast(e.message); }
  };
  loadCfg17();
  loadVeh();
  loadCfg111();
  loadEvents();
  $("#rs_save").onclick = async () => {
    const body = { on: $("#rs_on").checked, every: Number($("#rs_every").value), at: $("#rs_at").value, warn: Number($("#rs_warn").value), when: $("#rs_when").value };
    if ($("#rs_auto")) body.auto_update = $("#rs_auto").checked;
    try { const r = await api("/api/restarts", { json: body }); toast(r.note, 6000); show("config"); } catch (e) { toast(e.message); }
  };
  $("#md_save").onclick = async () => {
    const list = id => $(id).value.split(",").map(x => x.trim()).filter(Boolean);
    const body = { admins: list("#md_admins"), words: list("#md_words"), filter: $("#md_filter").checked, spam: $("#md_spam").checked,
                   spam_limit: Number($("#md_spamlimit").value), antibot: $("#md_antibot").checked, verify: $("#md_verify").checked,
                   guests: !$("#md_guests").checked, per_ip: Number($("#md_perip").value), join_flood: Number($("#md_flood").value),
                   kickwords: list("#md_kwords"), kickwords_action: $("#md_kact").value,
                   report: $("#md_report").checked, votekick: $("#md_votekick").checked, votekick_min: Number($("#md_vkmin").value), chatlog: $("#md_chatlog").checked };
    try { const r = await api("/api/moderation", { json: body }); toast(r.note, 5000); show("config"); } catch (e) { toast(e.message); }
  };
  $("#ex_every").onchange = () => { $("#ex_at_label").textContent = $("#ex_every").value === "24" ? "At" : "Starting at"; };
  $("#ex_save").onclick = async () => {
    const body = { clear: $("#ex_clear").checked, every: Number($("#ex_every").value), at: $("#ex_at").value, warn: Number($("#ex_warn").value),
                   afk: $("#ex_afk").checked, afk_minutes: Number($("#ex_afkmin").value), countdown: $("#ex_countdown").checked,
                   tag: $("#ex_tag").checked, top: $("#ex_top").checked, tags: $("#ex_tags").value.split(",").map(x => x.trim()).filter(Boolean) };
    try { const r = await api("/api/extras", { json: body }); toast(r.note, 6000); show("config"); } catch (e) { toast(e.message); }
  };
  $("#ja_save").onclick = () => jaSave(false);
  $("#ja_test").onclick = () => jaSave(true);
  $("#mv_save").onclick = async () => {
    const maps = [...m.querySelectorAll("[data-vm]")].filter(x => x.checked).map(x => x.dataset.vm);
    try { const r = await api("/api/mapvote", { json: { enabled: $("#mv_on").checked, maps } }); toast(r.note); show("config"); } catch (e) { toast(e.message); }
  };
  $("#al_save").onclick = async () => {
    const on = $("#al_on").checked, names = $("#al_names").value.split("\n").map(x => x.trim()).filter(Boolean);
    if (on && !names.length) { toast("Add at least one player name first"); return; }
    if (on && !al.enabled && !confirm("Make the server invite-only?\n\n• Only these " + names.length + " player(s) can join: " + names.slice(0, 8).join(", ") + (names.length > 8 ? ", …" : "") + "\n• Everyone else and all guests get an \"invite-only\" message\n• Players already online stay connected\n\nContinue?")) return;
    if (!on && al.enabled && !confirm("Turn the allow-list off? Anyone will be able to join again.")) return;
    try { const r = await api("/api/allowlist", { json: { enabled: on, names } }); toast(r.note); show("config"); } catch (e) { toast(e.message); }
  };
  $("#saveak").onclick = async () => {
    try { const r = await api("/api/authkey", { json: { key: $("#ak").value } }); $("#ak").value = ""; toast(r.note); show("config"); } catch (e) { toast(e.message); }
  };
};

/* ---------------- mods */
let MOD_SORT = store.get("es-modsort", "name");
VIEWS.mods = async m => {
  const [d, mu] = await Promise.all([api("/api/mods"), api("/api/mods/updates").catch(() => ({ mods: {} }))]);
  const U = mu.mods || {};
  const ST = d.storage || {}, SETS = d.sets || [];
  let roomLeft = ST.free == null ? null : Math.max(0, ST.free - (ST.spare || 0));
  if (MOD_SORT === "size") d.mods.sort((a, b) => b.size - a.size);
  setTimeout(() => { const t = $("#descsize"); if (t) t.onchange = async () => { try { const r = await api("/api/mods/desc", { json: { enabled: t.checked } }); toast(r.note, 7000); } catch (e) { toast(e.message); t.checked = !t.checked; } }; }, 0);
  const B = { clean: ["good", "✓ safe"], warning: ["warn", "⚠ check"], unchecked: ["", "not checked yet"] };
  m.innerHTML = `
    <div class="row"><div><h1>Mods</h1><p class="sub">Drop mod .zip files here, or find mods in the BeamNG repository. Every mod is virus-checked before players can download it.</p></div><span class="spacer"></span><button class="btn primary" id="mb_open">Browse mods</button></div>
    <div class="drop" id="drop"><b>Drag &amp; drop mods here</b><br><span class="muted">or click to choose files</span><input id="file" type="file" accept=".zip" multiple hidden></div>
    <div id="uploads"></div>
    <p class="small muted" style="margin:10px 0 16px">🛡 Active checks: ${esc(d.checks.join(" + "))}. ${d.auto_apply ? "The server restarts by itself ~15 s after a change." : "Restart the server after changes."}</p>
    <div class="card" style="margin-bottom:16px"><div class="row"><div><div class="small muted">Players download before they can join</div><div style="font-size:22px;font-weight:650">${d.download ? fmtSize(d.download) : "Nothing - vanilla"}</div>
      ${d.maps_size && !d.light ? `<div class="small muted">${fmtSize(d.maps_size)} of that is map mods. Light mode (below) sends only the map being played.</div>` : ""}
      ${d.light && d.all_maps_size > d.maps_size ? `<div class="small" style="color:var(--good-ink)">Light mode saves players ${fmtSize(d.all_maps_size - d.maps_size)} of map downloads.</div>` : ""}</div></div>
      ${ST.free != null ? `<div style="margin-top:12px"><div class="row small"><span>Mods take <b>${fmtSize(ST.mods)}</b> on this drive</span><span class="spacer"></span><span class="${ST.low ? "" : "muted"}" style="${ST.low ? "color:var(--warn-ink);font-weight:600" : ""}">${fmtSize(ST.free)} free of ${fmtSize(ST.total)}</span></div>
        <div class="bar" role="img" aria-label="Disk space: ${fmtSize(ST.total - ST.free)} used of ${fmtSize(ST.total)}"><i style="width:${Math.min(100, Math.round((ST.total - ST.free) / ST.total * 100))}%;${ST.low ? "background:var(--warning)" : ""}"></i></div>
        ${ST.low ? `<p class="small" style="color:var(--warn-ink);margin:6px 0 0">This drive is almost full. Turn off or delete mods you don't play (sort by size below), or move the server to a bigger drive. On a Raspberry Pi, a USB 3 stick or SSD is faster and bigger than the SD card.</p>` : ""}</div>` : ""}
      <label class="toggle" style="margin-top:10px"><input type="checkbox" id="lightmode" ${d.light ? "checked" : ""}><span><b>Light mode: only send the map being played</b><small>Map mods for other maps wait and come back by themselves when you switch to their map (Config, map vote, rotation or events). Mods that aren't maps are always sent. Players join much faster on servers with several map mods</small></span></label>
      <label class="toggle" style="margin-top:10px"><input type="checkbox" id="descsize" ${d.desc_modsize ? "checked" : ""}><span><b>Show the download size in the server description</b><small>Adds "| Mods: ${esc(d.download ? fmtSize(d.download) : "0")}" to the end of the description in the BeamMP server list and keeps it up to date. Takes effect after the server restarts</small></span></label></div>
    <div class="card" style="margin-bottom:16px"><div class="row"><div style="flex:1;min-width:240px"><h2 style="margin:0">Mod sets</h2><p class="small muted" style="margin:4px 0 0">Save the mods that are on now under a name, like "Drift night", and switch between sets in one click. Mods outside the set are turned off, not deleted.</p></div><button class="btn sm" id="set_save">Save as a set…</button></div>
      ${SETS.length ? `<table style="margin-top:10px"><tbody>${SETS.map(x => `<tr><td><b>${esc(x.name)}</b>${x.active ? '<span class="badge good">on now</span>' : ""}<div class="small muted">${x.mods.length} mod${x.mods.length === 1 ? "" : "s"} · ${fmtSize(x.size)}${x.missing.length ? ` · <span style="color:var(--warn-ink)">${x.missing.length} no longer on the server</span>` : ""}</div></td>
        <td class="num"><div class="row" style="justify-content:flex-end">${x.active ? "" : `<button class="btn sm primary" data-set="apply" data-sn="${esc(x.name)}">Switch to this set</button>`}<button class="btn sm" data-set="save" data-sn="${esc(x.name)}" title="Replace this set with the mods that are on now">Update</button><button class="btn sm danger" data-set="delete" data-sn="${esc(x.name)}">Delete</button></div></td></tr>`).join("")}</tbody></table>` : `<p class="small muted" style="margin:10px 0 0">No sets yet.</p>`}</div>
    <div class="row" style="margin-bottom:6px"><span class="spacer"></span><label class="small muted" for="modsort">Sort</label><select id="modsort" style="width:auto"><option value="name" ${MOD_SORT === "name" ? "selected" : ""}>By name</option><option value="size" ${MOD_SORT === "size" ? "selected" : ""}>Biggest first</option></select></div>
    <div class="card tight"><table><thead><tr><th>Mod</th><th class="num">Size</th><th></th></tr></thead><tbody>
      ${d.mods.length ? d.mods.map(x => `<tr><td><b class="${x.enabled ? "" : "muted"}">${esc(x.name)}</b>${x.builtin ? '<span class="badge good">EasyServer tools</span>' : `<span class="badge ${B[x.safety][0]}">${B[x.safety][1]}</span>`}${x.enabled ? "" : x.parked ? '<span class="badge">waiting - light mode</span>' : '<span class="badge">off</span>'}${x.maps.map(mp => `<span class="badge">map: ${esc(mp)}</span>`).join("")}${(x.needs || []).length ? `<span class="badge warn" title="This mod adds parts to a vehicle that isn't in the game or in your other mods, so it does nothing on its own. Add the mod that has this vehicle.">needs the mod for: ${esc(x.needs.join(", "))}</span>` : ""}${U[x.name] ? (U[x.name].update ? `<span class="badge warn">update ${esc(U[x.name].have || "?")} → ${esc(U[x.name].latest || "new")}</span>` : `<span class="badge good">up to date${U[x.name].have ? " (" + esc(U[x.name].have) + ")" : ""}</span>`) : ""}
        ${x.reasons.length ? `<div class="small" style="color:var(--warn-ink);margin-top:4px">${x.reasons.map(esc).join("<br>")}</div>` : ""}</td>
        <td class="num muted">${fmtSize(x.size)}</td>
        <td class="num"><div class="row" style="justify-content:flex-end">${U[x.name] && U[x.name].update ? `<button class="btn sm primary" data-upd="${esc(x.name)}">Update</button><a class="btn sm" href="${esc(U[x.name].page)}" target="_blank" rel="noopener noreferrer">Page</a>` : ""}${x.maps.length && (x.enabled || x.parked) ? `<button class="btn sm" data-map="${esc(x.maps[0])}">Use map</button>` : ""}${x.builtin ? `<span class="small muted">Config → In-game tools</span>` : `${x.parked ? "" : `<button class="btn sm" data-a="toggle" data-n="${esc(x.name)}">${x.enabled ? "Turn off" : "Turn on"}</button>`}<button class="btn sm danger" data-a="delete" data-n="${esc(x.name)}">Delete</button>`}</div></td></tr>`).join("")
        : `<tr><td colspan="3" class="muted">No mods yet.</td></tr>`}
    </tbody></table></div>
    <div class="card" style="margin-top:16px"><h2>Modpack</h2><p class="small muted">One .zip with every mod that's turned on, plus a list with checksums. Share it with another server owner, move mods to another server, or give it to players with slow internet so they can copy the mods before joining.</p>
      <div class="row" style="flex-wrap:wrap"><a class="btn sm" href="/api/modpack?srv=${encodeURIComponent(SERVER)}" download ${d.mods.some(x => x.enabled) ? "" : 'aria-disabled="true" style="pointer-events:none;opacity:.5"'}>Download modpack</a>
        ${SESSION.role === "owner" || !SESSION.role ? `<button class="btn sm" id="mpimp">Import a modpack…</button><input type="file" id="mpfile" accept=".zip" hidden>` : ""}<button class="btn sm" id="mpcode">Share code…</button><span class="small muted" id="mpres"></span></div></div>
    <div id="plugcard"></div>
    <div class="row" style="margin-top:12px;flex-wrap:wrap"><button class="btn sm" id="rescan" title="Checks only mods that are new or changed since their last check">Check new mods</button><button class="btn sm ghost" id="rescanall" title="Checks every mod again, e.g. after your antivirus got new virus definitions">Check all again</button><button class="btn sm" id="modupd">Check for updates</button>
      <label class="toggle" style="margin:0 0 0 8px"><input type="checkbox" id="modupd_on" ${mu.on !== false ? "checked" : ""}><span><b>Check every day</b><small>Mods from the BeamNG repository${mu.checked ? " · last check " + esc(ago(mu.checked)) : ""}</small></span></label></div>
    ${d.quarantine.length ? `<h2 style="margin-top:26px">⛔ Blocked mods (quarantine)</h2><div class="card tight"><table><tbody>${d.quarantine.map(q => `<tr><td><b>${esc(q.name)}</b><div class="small" style="color:var(--crit-ink);white-space:pre-wrap">${esc(q.why)}</div></td><td class="num"><button class="btn sm danger" data-a="qdelete" data-n="${esc(q.name)}">Delete</button></td></tr>`).join("")}</tbody></table></div>` : ""}`;
  $("#mb_open").onclick = () => modBrowser();
  $("#mpcode").onclick = () => modpackCode();
  $("#modsort").onchange = e => { MOD_SORT = e.target.value; store.set("es-modsort", MOD_SORT); show("mods"); };
  const setAct = async (action, name) => {
    try { const r = await api("/api/mods/sets", { json: { action, name } }); toast(r.note, 8000); show("mods"); } catch (e) { toast(e.message, 6000); }
  };
  $("#set_save").onclick = () => {
    const n = (prompt("Name for this mod set (for example Drift night). It saves the mods that are on now.") || "").trim();
    if (!n) return;
    if (SETS.some(x => x.name.toLowerCase() === n.toLowerCase()) && !confirm("There's already a set called " + n + ". Replace it with the mods that are on now?")) return;
    setAct("save", n);
  };
  m.querySelectorAll("[data-set]").forEach(b => b.onclick = () => {
    const a = b.dataset.set, n = b.dataset.sn;
    if (a === "delete" && !confirm("Delete the mod set " + n + "? The mods themselves stay.")) return;
    if (a === "save" && !confirm("Replace " + n + " with the mods that are on now?")) return;
    if (a === "apply" && !confirm("Switch to " + n + "? Mods that aren't in this set are turned off (not deleted).")) return;
    setAct(a, n);
  });
  loadPlugins();
  const D = $("#drop");
  D.onclick = () => $("#file").click();
  $("#file").onchange = e => upload([...e.target.files]);
  ["dragenter", "dragover"].forEach(t => D.addEventListener(t, e => { e.preventDefault(); D.classList.add("over"); }));
  ["dragleave", "drop"].forEach(t => D.addEventListener(t, e => { e.preventDefault(); D.classList.remove("over"); }));
  D.addEventListener("drop", e => upload([...e.dataTransfer.files]));
  m.querySelectorAll("[data-a]").forEach(b => b.onclick = async () => {
    if (b.dataset.a.includes("delete") && !confirm("Delete " + b.dataset.n + "?")) return;
    try { const r = await api("/api/mods/action", { json: { action: b.dataset.a, name: b.dataset.n } }); toast(r.note || "Done"); show("mods"); } catch (e) { toast(e.message); }
  });
  m.querySelectorAll("[data-map]").forEach(b => b.onclick = async () => {
    try {
      const cfg = await api("/api/config");
      const r = await api("/api/config/save", { json: { fields: [{ section: "General", key: "Map", value: b.dataset.map }] } });
      toast("Map set to " + b.dataset.map + ". " + r.note);
    } catch (e) { toast(e.message); }
  });
  $("#modupd").onclick = async () => { $("#modupd").disabled = true; toast("Asking beamng.com…", 15000); try { const r = await api("/api/mods/updates", { json: {} }); toast(r.note, 6000); show("mods"); } catch (e) { toast(e.message, 6000); $("#modupd").disabled = false; } };
  $("#modupd_on").onchange = async () => { try { await api("/api/mods/updates", { json: { on: $("#modupd_on").checked } }); toast("Saved"); } catch (e) { toast(e.message); } };
  m.querySelectorAll("[data-upd]").forEach(b => b.onclick = async () => {
    b.disabled = true; toast("Downloading and checking " + b.dataset.upd + "…", 60000);
    try { const r = await api("/api/mods/update", { json: { name: b.dataset.upd } }); toast(r.note, 7000); show("mods"); }
    catch (e) { toast(e.data && e.data.blocked ? "The update failed the virus check - the old version stays." : e.message, 9000); b.disabled = false; }
  });
  const rescan = all => async () => {
    $("#rescan").disabled = $("#rescanall").disabled = true;
    toast(all ? "Checking every mod again…" : "Checking new mods…");
    try {
      const r = await api("/api/mods/rescan", { json: { all } });
      const bad = r.results.filter(x => x.verdict === "blocked" && !x.skipped).length;
      toast(bad ? bad + " mod(s) blocked" : !r.checked ? "Nothing new to check - all " + r.skipped + " mods were checked before"
        : r.checked + " mod(s) checked, all passed" + (r.skipped ? " (" + r.skipped + " already checked)" : ""), 6000);
    } catch (e) { toast(e.message); }
    show("mods");
  };
  $("#rescan").onclick = rescan(false);
  $("#rescanall").onclick = () => { if (confirm("Check every mod again? Big mod folders can take a few minutes.")) rescan(true)(); };
  $("#lightmode").onchange = async e => {
    try { const r = await api("/api/mods/light", { json: { on: e.target.checked } }); toast(r.note, 8000); show("mods"); } catch (x) { toast(x.message, 6000); e.target.checked = !e.target.checked; }
  };
  if ($("#mpimp")) {
    $("#mpimp").onclick = () => $("#mpfile").click();
    $("#mpfile").onchange = async e => {
      const f = e.target.files[0]; if (!f) return;
      $("#mpres").textContent = "Importing and virus-checking…";
      const r = await fetch("/api/import?settings=0", { method: "PUT", headers: { "X-ES-CSRF": CSRF, "X-ES-Server": SERVER }, body: f });
      let j = {}; try { j = await r.json(); } catch (x) {}
      if (!r.ok) { $("#mpres").textContent = j.error || "Import failed"; return; }
      if (!j.report.modpack) { $("#mpres").textContent = "That was a full server export - it was imported as one."; return; }
      toast(j.note + (j.report.mods_blocked.length ? " " + j.report.mods_blocked.length + " blocked by the virus check." : ""), 8000); show("mods");
    };
  }
  async function upload(files) {
    for (const f of files) await one(f);
    show("mods");
  }
  function one(f) {
    return new Promise(res => {
      const box = document.createElement("div"); box.className = "card"; box.style.marginTop = "10px";
      box.innerHTML = `<b>${esc(f.name)}</b><div class="bar"><i></i></div><div class="small muted" data-s>Uploading…</div>`;
      $("#uploads").appendChild(box);
      if (!/\.zip$/i.test(f.name)) { box.querySelector("[data-s]").textContent = "Only .zip files"; return res(); }
      if (roomLeft != null && f.size > roomLeft) {
        box.querySelector("[data-s]").innerHTML = `<span style="color:var(--crit-ink)">Not enough space: this mod is ${fmtSize(f.size)} and only ${fmtSize(roomLeft)} is free. Delete or turn off mods you don't play, or use a bigger drive.</span>`;
        return res();
      }
      const x = new XMLHttpRequest();
      x.open("PUT", "/api/mods/upload?name=" + encodeURIComponent(f.name));
      x.setRequestHeader("X-ES-CSRF", CSRF); x.setRequestHeader("X-ES-Server", SERVER);
      x.upload.onprogress = e => { if (e.lengthComputable) box.querySelector("i").style.width = (e.loaded / e.total * 100) + "%"; };
      x.upload.onload = () => { box.querySelector("[data-s]").textContent = "Checking for viruses…"; };
      x.onload = () => {
        let j = {}; try { j = JSON.parse(x.responseText); } catch (e) {}
        const s = box.querySelector("[data-s]");
        if (x.status === 422) { s.innerHTML = `<b style="color:var(--crit-ink)">Blocked - not uploaded.</b><br>${(j.reasons || []).map(esc).join("<br>")}`; }
        else if (x.status !== 200) { s.textContent = j.error || "Upload failed"; }
        else { if (roomLeft != null) roomLeft = Math.max(0, roomLeft - f.size); s.innerHTML = `<span style="color:var(--good-ink)">✓ Uploaded and checked (${esc((j.checks || []).join(" + "))})</span>${j.maps && j.maps.length ? " · contains map " + esc(j.maps.join(", ")) : ""}${j.safety === "warning" ? `<div style="color:var(--warn-ink)">⚠ ${j.reasons.map(esc).join("<br>⚠ ")}</div>` : ""}`; }
        res();
      };
      x.onerror = () => { box.querySelector("[data-s]").textContent = "Upload failed"; res(); };
      x.send(f);
    });
  }
};

/* ---------------- players (analytics) */
function barChart(el, values, labels, tipFn, opts = {}) {
  const W = Math.max(280, Math.round(el.clientWidth || 640)), H = opts.h || 190, padL = 30, padB = 22, padT = 10;
  const max = Math.max(1, ...values), n = values.length;
  const step = (W - padL) / n, bw = Math.max(2, Math.min(28, step - 2));
  const nice = max <= 4 ? Math.ceil(max) : Math.ceil(max / 4) * 4;
  const y = v => padT + (H - padT - padB) * (1 - v / nice);
  let g = "";
  for (let i = 0; i <= 4; i++) { const v = nice * i / 4; g += `<line x1="${padL}" x2="${W}" y1="${y(v)}" y2="${y(v)}"/>`; }
  let ax = "";
  for (let i = 0; i <= 4; i++) { const v = nice * i / 4; ax += `<text x="${padL - 6}" y="${y(v) + 4}" text-anchor="end">${Number.isInteger(v) ? v : v.toFixed(1)}</text>`; }
  const every = Math.ceil(n / Math.max(3, Math.min(opts.labelsMax || 8, Math.floor((W - padL) / 52))));
  labels.forEach((l, i) => { if (i % every === 0) ax += `<text x="${padL + step * i + step / 2}" y="${H - 6}" text-anchor="middle">${esc(l)}</text>`; });
  let bars = "", hits = "";
  values.forEach((v, i) => {
    const x = padL + step * i + (step - bw) / 2, top = y(v), base = y(0), hh = Math.max(0, base - top);
    if (v > 0) { const r = Math.min(4, bw / 2, hh); bars += `<path data-i="${i}" d="M${x},${base}V${top + r}q0,-${r} ${r},-${r}h${bw - 2 * r}q${r},0 ${r},${r}V${base}Z"/>`; }
    hits += `<rect class="hit" data-i="${i}" x="${padL + step * i}" y="${padT}" width="${step}" height="${H - padT - padB}"/>`;
  });
  el.innerHTML = `<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.title || "chart")}"><g class="grid">${g}</g><g class="axis">${ax}</g><g class="bars">${bars.replace(/<path/g, '<path fill="var(--accent)"')}${hits}</g></svg><div class="tip hidden"></div></div>`;
  const tip = el.querySelector(".tip"), svg = el.querySelector("svg");
  el.querySelectorAll("rect.hit").forEach(r => {
    r.addEventListener("mouseenter", () => {
      const i = +r.dataset.i; el.querySelectorAll("path[data-i]").forEach(p => p.style.opacity = +p.dataset.i === i ? 1 : .35);
      tip.innerHTML = tipFn(i); tip.classList.remove("hidden");
      const bb = svg.getBoundingClientRect(), sc = bb.width / W;
      tip.style.left = ((padL + step * i + step / 2) * sc) + "px"; tip.style.top = (y(values[i]) * sc) + "px";
    });
    r.addEventListener("mouseleave", () => { tip.classList.add("hidden"); el.querySelectorAll("path[data-i]").forEach(p => p.style.opacity = 1); });
  });
}

let RESIZE_T;
window.addEventListener("resize", () => { clearTimeout(RESIZE_T); RESIZE_T = setTimeout(() => { if (TAB === "players") show("players"); }, 400); });
VIEWS.players = async m => {
  const [d, bn] = await Promise.all([api("/api/players"), api("/api/bans")]);
  const s = d.summary;
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const hm = d.heatmap, hmMax = Math.max(0.0001, ...hm.flat().filter(v => v !== null));
  const shade = v => v === null ? "var(--surface-2)" : `var(--heat-${Math.min(6, Math.round(v / hmMax * 6))})`;
  m.innerHTML = `
    <div class="row"><div><h1>Players</h1><p class="sub">Activity over the last 30 days. Recorded by the EasyServerStats plugin on your server.</p></div><span class="spacer"></span><button class="btn sm" id="clear">Clear statistics</button></div>
    ${d.has_data ? "" : `<div class="banner info">No player data yet. Statistics start once the server runs with the stats plugin and someone plays.</div>`}
    <div id="maintcard"></div>
    <div id="reportcard"></div>
    <div class="card" style="margin-bottom:16px" id="modcard"><div class="row"><h2 style="margin:0">Online now &amp; moderation</h2><span class="spacer"></span><span class="small muted">Takes a second to reach the game</span></div>
      ${bn.online.length ? `<table style="margin-top:8px"><tbody>${bn.online.map(n => `<tr><td><b>${esc(n)}</b></td><td class="num"><div class="row" style="justify-content:flex-end;gap:6px">
          <button class="btn sm" data-act="mute" data-n="${esc(n)}">Mute 10 min</button><button class="btn sm" data-act="unmute" data-n="${esc(n)}">Unmute</button>
          <button class="btn sm" data-act="kick" data-n="${esc(n)}">Kick</button><button class="btn sm danger" data-banopen="${esc(n)}">Ban…</button></div></td></tr>`).join("")}</tbody></table>`
        : `<p class="small muted">Nobody is online right now${d.online.fresh ? "" : " (or the server isn't reporting)"}.</p>`}
      <div class="row" style="gap:8px;margin-top:12px;flex-wrap:wrap">
        <input type="text" id="ban_name" placeholder="Player name" style="max-width:180px" maxlength="64">
        <select id="ban_len" style="max-width:150px"><option value="60">1 hour</option><option value="1440">1 day</option><option value="10080">7 days</option><option value="43200">30 days</option><option value="0" selected>Forever</option></select>
        <input type="text" id="ban_reason" placeholder="Reason (players see it)" style="max-width:240px" maxlength="200">
        <button class="btn danger" id="ban_go">Ban</button></div>
      <div class="row" style="gap:8px;margin-top:10px"><input type="text" id="say_text" placeholder="Send a message to everyone in the game chat" maxlength="300"><button class="btn" id="say_go">Send</button></div>
      <h2 style="margin-top:18px">Banned players (${bn.bans.length})</h2>
      ${bn.bans.length ? `<table><thead><tr><th>Player</th><th>Until</th><th>Reason</th><th>By</th><th></th></tr></thead><tbody>${bn.bans.map(b => `<tr><td><b>${esc(b.name)}</b></td><td class="muted">${b.until ? esc(fmtTime(b.until)) : "Forever"}</td><td>${esc(b.reason || "-")}</td><td class="muted">${esc(b.by || "-")}</td><td class="num"><button class="btn sm" data-unban="${esc(b.name)}">Unban</button></td></tr>`).join("")}</tbody></table>`
        : `<p class="small muted">Nobody is banned. Admins you set under Config → Moderation can also ban from the game chat.</p>`}
    </div>
    <div id="chatcard"></div>
    <div class="grid g4">
      <div class="card stat"><div class="label">Online now</div><div class="value">${d.online.players.length}</div><div class="note">${d.online.fresh ? esc(d.online.players.slice(0, 3).join(", ") || "Nobody") : "Server not reporting"}</div></div>
      <div class="card stat"><div class="label">Players (30 days)</div><div class="value">${esc(s.unique_30d)}</div><div class="note">${esc(s.unique_7d)} in the last 7 days</div></div>
      <div class="card stat"><div class="label">Peak at once</div><div class="value">${esc(s.peak)}</div><div class="note">${s.peak_at ? esc(fmtTime(s.peak_at)) : "-"}</div></div>
      <div class="card stat"><div class="label">Server usage</div><div class="value">${esc(s.utilization)}%</div><div class="note">avg ${esc(s.avg_players)} players · ${esc(s.hours_30d)} h played</div></div>
    </div>
    <div class="card" style="margin-top:16px"><h2>Players per day</h2><div id="daily"></div></div>
    <div class="grid g2" style="margin-top:16px">
      <div class="card"><h2>Busiest hours</h2><p class="small muted">Average players online by time of day${s.busiest_hour !== null ? ` · busiest around ${String(s.busiest_hour).padStart(2, "0")}:00` : ""}</p><div id="hourly"></div></div>
      <div class="card"><h2>Week overview</h2><p class="small muted">Average players by day and hour</p>
        <div class="heat" id="heat"><span></span>${Array.from({ length: 24 }, (_, i) => `<span class="lab">${i % 6 === 0 ? i : ""}</span>`).join("")}
        ${hm.map((row, di) => `<span class="lab rl">${days[di]}</span>` + row.map((v, hh) => `<span class="c" data-tip="${days[di]} ${String(hh).padStart(2, "0")}:00 · ${v === null ? "no data" : v + " players avg"}"></span>`).join("")).join("")}</div>
        <div class="legend">fewer ${[0, 2, 4, 6].map(i => `<i data-heat="${i}"></i>`).join("")} more</div></div>
    </div>
    <div class="grid g2" style="margin-top:16px">
      <div class="card tight"><table><thead><tr><th>Top players (30 days)</th><th class="num">Time played</th><th class="num">Sessions</th></tr></thead><tbody>
        ${d.top.length ? d.top.map(p => `<tr><td><b>${esc(p.name)}</b><div class="small muted">last seen ${esc(ago(p.last_seen))}</div></td><td class="num">${fmtDur(p.seconds)}</td><td class="num">${esc(p.sessions)}</td></tr>`).join("") : `<tr><td colspan="3" class="muted">No players yet</td></tr>`}
      </tbody></table></div>
      <div class="card tight"><table><thead><tr><th>Recent sessions</th><th class="num">Started</th><th class="num">Length</th></tr></thead><tbody>
        ${d.recent.length ? d.recent.slice(0, 12).map(r => `<tr><td>${esc(r.name)}</td><td class="num muted">${esc(fmtTime(r.start))}</td><td class="num">${esc(r.minutes)} min</td></tr>`).join("") : `<tr><td colspan="3" class="muted">No sessions yet</td></tr>`}
      </tbody></table></div>
    </div>
    ${(() => {
      const R = d.records || {}, any = ["speed", "dist", "streak"].some(k => (R[k] || []).length);
      if (!any && !d.records_on) return "";
      const col = (title, list, val) => `<div class="card tight"><table><thead><tr><th>${title}</th><th class="num"></th></tr></thead><tbody>${(list || []).length ? list.map((r, i) => `<tr><td>${i + 1}. <b>${esc(r.name)}</b></td><td class="num">${val(r)}</td></tr>`).join("") : `<tr><td colspan="2" class="muted">Nobody yet</td></tr>`}</tbody></table></div>`;
      return `<h2 style="margin:22px 0 10px">Server records</h2>${d.records_on ? "" : `<p class="small muted">Records are paused - turn on "/top server records" under Config → Cars &amp; chat.</p>`}
        <div class="grid g3">${col("Top speed", R.speed, r => esc(Math.round(r.speed)) + " km/h")}${col("Distance driven", R.dist, r => esc(r.dist.toFixed(1)) + " km")}${col("Longest drive without a reset", R.streak, r => fmtDur(r.streak))}</div>`;
    })()}
    <div id="mapstats"></div>`;
  const dl = d.days.map(x => x.date.slice(5).replace("-", "/"));
  barChart($("#daily"), d.days.map(x => x.players), dl, i => `<b>${esc(d.days[i].date)}</b><br>${d.days[i].players} players · peak ${d.days[i].peak} · ${d.days[i].hours} h played`, { title: "Players per day", labelsMax: 10 });
  barChart($("#hourly"), d.hourly, d.hourly.map((_, i) => String(i).padStart(2, "0")), i => `<b>${String(i).padStart(2, "0")}:00</b><br>${d.hourly[i]} players on average`, { title: "Average players by hour", labelsMax: 8, h: 170 });
  m.querySelectorAll("#heat .c").forEach((c, idx) => { const v = hm[Math.floor(idx / 24)][idx % 24]; c.style.background = shade(v); c.title = c.dataset.tip; });
  m.querySelectorAll("[data-heat]").forEach(i => i.style.background = `var(--heat-${i.dataset.heat})`);
  const act = async (body) => { try { const r = await api("/api/players/act", { json: body }); toast(r.note); } catch (e) { toast(e.message); } };
  m.querySelectorAll("[data-act]").forEach(b => b.onclick = () => act({ action: b.dataset.act, name: b.dataset.n, minutes: 10 }));
  loadMaint();
  if (canModerate()) { loadReports(); loadChat(); }
  loadMapStats();
  m.querySelectorAll("[data-banopen]").forEach(b => b.onclick = () => { $("#ban_name").value = b.dataset.banopen; $("#ban_reason").focus(); });
  $("#ban_go").onclick = async () => {
    const name = $("#ban_name").value.trim(); if (!name) return toast("Type the player's name");
    try { const r = await api("/api/bans/add", { json: { name, minutes: Number($("#ban_len").value), reason: $("#ban_reason").value } }); toast(r.note); show("players"); } catch (e) { toast(e.message); }
  };
  m.querySelectorAll("[data-unban]").forEach(b => b.onclick = async () => { try { const r = await api("/api/bans/remove", { json: { name: b.dataset.unban } }); toast(r.note); show("players"); } catch (e) { toast(e.message); } });
  $("#say_go").onclick = async () => { const t = $("#say_text").value.trim(); if (!t) return; await act({ action: "say", name: "x", text: t }); $("#say_text").value = ""; };
  $("#clear").onclick = async () => { if (!confirm("Delete all player statistics?")) return; await api("/api/players/clear", { method: "POST" }); show("players"); };
};

/* ---------------- network */
/* Health is React now (health.jsx) */

/* ---------------- updates */
/* Updates, Logs and Notifications are React now (pages.jsx) */

/* ---------------- 1.12: per-map statistics (Players) */
async function loadMapStats(days = 30) {
  const el = $("#mapstats"); if (!el) return;
  let d; try { d = await api("/api/players/maps?days=" + days); } catch (e) { return; }
  const rows = d.maps, top = Math.max(0.01, ...rows.map(r => r.player_hours));
  el.innerHTML = `<div class="row" style="margin:22px 0 10px"><h2 style="margin:0">Maps</h2><span class="spacer"></span>
      <div class="seg">${[7, 30, 90].map(n => `<button data-md="${n}" class="${n === days ? "on" : ""}">${n} days</button>`).join("")}</div></div>
    ${rows.length ? `<div class="card tight"><table><thead><tr><th>Map</th><th>Time played by everyone</th><th class="num">Players</th><th class="num">Avg. stay</th><th class="num">Peak</th><th class="num">Map was on</th></tr></thead><tbody>
      ${rows.map(r => `<tr><td><b>${esc(r.map)}</b>${r.map === d.current ? ' <span class="badge">now</span>' : ""}</td>
        <td><div class="row" style="gap:8px;flex-wrap:nowrap"><div style="flex:1;min-width:60px;max-width:220px;height:8px;border-radius:4px;background:var(--surface-2)"><div style="width:${Math.round(r.player_hours / top * 100)}%;height:100%;border-radius:4px;background:var(--accent)"></div></div><span class="small">${r.player_hours >= 0.1 ? r.player_hours + " h" : r.players ? "&lt;0.1 h" : "0 h"}</span></div></td>
        <td class="num">${r.players}</td><td class="num">${r.avg_session_min ? r.avg_session_min + " min" : "-"}</td><td class="num">${r.peak}</td><td class="num muted">${r.map_hours >= 0.1 ? r.map_hours + " h" : "&lt;0.1 h"}</td></tr>`).join("")}</tbody></table></div>
      <p class="small muted" style="margin-top:6px">${(() => { const busy = rows.filter(r => r.map_hours >= 2).sort((a, b) => b.per_hour - a.per_hour); return busy.length > 1 ? `Busiest map per hour it's on: <b>${esc(busy[0].map)}</b> (${busy[0].per_hour} players on average). Quietest: <b>${esc(busy[busy.length - 1].map)}</b> (${busy[busy.length - 1].per_hour}).` : ""; })()} Counted since ${esc(fmtTime(d.since))}.</p>`
    : `<p class="small muted">${d.since ? "Nobody has played since " + esc(fmtTime(d.since)) + "." : "Map statistics start now - they appear once people have played on this server."}</p>`}`;
  el.querySelectorAll("[data-md]").forEach(b => b.onclick = () => loadMapStats(+b.dataset.md));
}

/* ---------------- 1.11: maintenance mode (Players) */
/* ---------------- player reports + chat history (Players page) */
function canModerate() {
  const r = myRole();
  if (r && r.perms) return r.perms.includes("players");
  return (r ? r.role : SESSION.role) !== "viewer";
}
const fmtClock = t => new Date(t * 1000).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" });
const chatRows = lines => lines.map(c => `<div class="chatline${c.hid ? " hid" : ""}" data-around="${c.t}"><span class="muted">${esc(fmtClock(c.t))}</span> <b>${esc(c.name)}</b> ${esc(c.msg)}${c.hid ? ' <span class="badge" title="Players didn\'t see this: the sender was muted or the chat filter caught it">hidden</span>' : ""}</div>`).join("");
let SHOW_CLOSED = false;
async function loadReports() {
  const el = $("#reportcard"); if (!el) return;
  let d;
  try { d = await api("/api/reports"); } catch (e) { el.innerHTML = ""; return; }
  const list = d.items.filter(x => SHOW_CLOSED || x.open);
  if (!d.items.length) { el.innerHTML = ""; return; }
  el.innerHTML = `<div class="card" style="margin-bottom:16px"><div class="row"><h2 style="margin:0">Reports</h2>${d.open ? `<span class="badge warn">${d.open} open</span>` : ""}<span class="spacer"></span>
      <label class="small muted" style="display:flex;gap:6px;align-items:center"><input type="checkbox" id="rp_all" ${SHOW_CLOSED ? "checked" : ""}> Show handled</label>${d.open > 1 ? '<button class="btn sm" id="rp_closeall">Mark all handled</button>' : ""}</div>
    ${d.on ? "" : `<p class="small muted">Reports are turned off (Config → Moderation).</p>`}
    ${list.length ? list.map(r => `<div class="report${r.open ? "" : " done"}"><div class="row"><div><b>${esc(r.by)}</b> reported <b>${esc(r.target)}</b> <span class="muted small">· ${esc(fmtClock(r.t))}</span><div>${esc(r.reason)}</div></div><span class="spacer"></span>
        ${r.open ? `<button class="btn sm" data-rpban="${esc(r.target)}">Ban…</button><button class="btn sm" data-rpclose="${esc(r.id)}">Handled</button>` : `<span class="small muted">Handled by ${esc(r.closed_by || "?")}</span>`}</div>
        ${r.chat && r.chat.length ? `<details style="margin-top:6px"><summary class="small">Chat before the report (${r.chat.length})</summary><div class="chatbox">${chatRows(r.chat)}</div></details>` : ""}</div>`).join("")
      : `<p class="small muted" style="margin:8px 0 0">No open reports.</p>`}</div>`;
  $("#rp_all").onchange = e => { SHOW_CLOSED = e.target.checked; loadReports(); };
  if ($("#rp_closeall")) $("#rp_closeall").onclick = async () => { try { await api("/api/reports/close", { json: { id: "all" } }); loadReports(); } catch (e) { toast(e.message); } };
  el.querySelectorAll("[data-rpclose]").forEach(b => b.onclick = async () => { try { await api("/api/reports/close", { json: { id: b.dataset.rpclose } }); loadReports(); } catch (e) { toast(e.message); } });
  el.querySelectorAll("[data-rpban]").forEach(b => b.onclick = () => { const i = $("#ban_name"); if (i) { i.value = b.dataset.rpban; i.scrollIntoView({ block: "center" }); i.focus(); } });
}
async function loadChat(opts = {}) {
  const el = $("#chatcard"); if (!el) return;
  const qs = new URLSearchParams();
  if (opts.q) qs.set("q", opts.q);
  if (opts.player) qs.set("player", opts.player);
  if (opts.around) qs.set("around", opts.around);
  let d;
  try { d = await api("/api/chat?" + qs); } catch (e) { el.innerHTML = ""; return; }
  el.innerHTML = `<div class="card" style="margin-bottom:16px"><div class="row"><h2 style="margin:0">Chat history</h2><span class="spacer"></span>
      ${SESSION.role === "owner" || SESSION.role === "admin" || !SESSION.role ? '<button class="btn sm ghost" id="ch_clear">Delete history</button>' : ""}</div>
    ${d.on ? "" : `<p class="small muted">The chat history is turned off (Config → Moderation). ${d.total ? "Older messages are still here." : ""}</p>`}
    <div class="row" style="gap:8px;margin:10px 0;flex-wrap:wrap"><input type="text" id="ch_q" placeholder="Search words or names" value="${esc(opts.q || "")}" style="max-width:260px">
      <select id="ch_p" style="max-width:200px"><option value="">Everyone</option>${(opts.player ? [opts.player] : d.players).map(n => `<option ${n === opts.player ? "selected" : ""}>${esc(n)}</option>`).join("")}</select>
      <button class="btn sm" id="ch_go">Search</button>${opts.q || opts.player || opts.around ? '<button class="btn sm ghost" id="ch_reset">Show all</button>' : ""}</div>
    ${opts.around ? `<p class="small muted">The 10 minutes around ${esc(fmtClock(opts.around))}.</p>` : ""}
    ${d.lines.length ? `<div class="chatbox" id="ch_box">${chatRows(d.lines)}</div><p class="small muted" style="margin:6px 0 0">${d.total > d.lines.length ? "Newest " + d.lines.length + " of " + d.total + " messages. " : ""}Click a message to see what was said around it.</p>`
      : `<p class="small muted">${opts.q || opts.player ? "Nothing found." : "No chat yet."}</p>`}</div>`;
  const box = $("#ch_box"); if (box) box.scrollTop = box.scrollHeight;
  const go = () => loadChat({ q: $("#ch_q").value.trim(), player: $("#ch_p").value });
  $("#ch_go").onclick = go;
  $("#ch_q").onkeydown = e => { if (e.key === "Enter") go(); };
  if ($("#ch_reset")) $("#ch_reset").onclick = () => loadChat();
  el.querySelectorAll("[data-around]").forEach(r => r.onclick = () => loadChat({ around: r.dataset.around }));
  if ($("#ch_clear")) $("#ch_clear").onclick = async () => {
    if (!confirm("Delete the whole chat history of this server? This can't be undone.")) return;
    try { const r = await api("/api/chat/clear", { json: {} }); toast(r.note); loadChat(); } catch (e) { toast(e.message); }
  };
}

async function loadMaint() {
  const el = $("#maintcard"); if (!el) return;
  let mt; try { mt = await api("/api/maintenance"); } catch (e) { return; }
  el.innerHTML = `<div class="card" style="margin-bottom:16px;${mt.on ? "border-color:var(--warning)" : ""}"><div class="row"><h2 style="margin:0">Maintenance mode</h2><span class="spacer"></span>
      <span class="pill ${mt.on ? "warn" : ""}"><span class="dot"></span>${mt.on ? "On since " + esc(fmtTime(mt.since)) : "Off"}</span></div>
    <p class="small muted">Close the server while you work on it: only admins (Config → Moderation) and the names below can join. Everyone else sees your message. Works right away, no restart.</p>
    <label class="f"><span>Message players see</span><input type="text" id="mt_msg" maxlength="200" value="${esc(mt.message)}"></label>
    <label class="f"><span>May still join (one name per line)</span><textarea id="mt_allow" rows="2" spellcheck="false" style="min-height:52px">${esc(mt.allow.join("\n"))}</textarea></label>
    <label class="toggle"><input type="checkbox" id="mt_kick" ${mt.kick ? "checked" : ""}><span><b>Disconnect the other players</b><small>They get a 10-second warning in the chat first</small></span></label>
    <div class="row" style="margin-top:10px">${mt.on ? `<button class="btn primary" id="mt_off">End maintenance</button><button class="btn" id="mt_save">Save changes</button>` : `<button class="btn primary" id="mt_on">Start maintenance</button>`}</div></div>`;
  const body = st => ({ state: st, message: $("#mt_msg").value, allow: $("#mt_allow").value, kick: $("#mt_kick").checked });
  const go = async st => { try { const r = await api("/api/maintenance", { json: body(st) }); toast(r.note, 7000); loadMaint(); } catch (e) { toast(e.message, 6000); } };
  if ($("#mt_on")) $("#mt_on").onclick = () => confirm("Start maintenance? Only admins and the listed players can join until you end it.") && go("on");
  if ($("#mt_off")) $("#mt_off").onclick = () => go("off");
  if ($("#mt_save")) $("#mt_save").onclick = () => go("on");
}

/* ---------------- 1.15: server plugins (Mods page) */
async function loadPlugins() {
  const el = $("#plugcard"); if (!el) return;
  let d; try { d = await api("/api/plugins"); } catch (e) { el.innerHTML = ""; return; }
  const inst = Object.fromEntries(d.installed.filter(p => !p.id.startsWith("file-") && !p.id.startsWith("manual-")).map(p => [p.id, p]));
  const errs = p => p.errors ? `<div class="small" style="color:var(--crit-ink)">${p.errors} Lua error${p.errors === 1 ? "" : "s"} in the log: <span class="mono">${esc(p.last_error)}</span></div>` : "";
  el.innerHTML = `<div class="card" style="margin-top:16px"><h2>Server plugins</h2>
    <p class="small muted">Plugins add game modes and tools that run on the server (Lua scripts in Resources/Server). EasyServer downloads each one from its author's own GitHub page, shows you what goes where, and installs it only when you say so. <b>A plugin can do anything the server can</b> - only install ones you trust. Restart the server after a change.</p>
    ${d.writable ? "" : `<div class="banner warn">EasyServer can't write to Resources/Server yet. Run the installer once more - it updates the folder permissions.</div>`}
    ${d.installed.length ? `<h3>Installed</h3><table><tbody>${d.installed.map(p => `<tr><td><b class="${p.on ? "" : "muted"}">${esc(p.name)}</b> ${p.on ? "" : '<span class="badge">off</span>'}${p.catalog ? "" : '<span class="badge warn">not from the list</span>'}
        <div class="small muted">${p.author ? "By " + esc(p.author) + " · " : ""}${esc(p.version || "")}${p.client.length ? " · players download: " + esc(p.client.join(", ")) : ""}${p.page ? ` · <a href="${esc(p.page)}" target="_blank" rel="noopener noreferrer">page</a>` : ""}</div>${errs(p)}</td>
        <td class="num">${d.owner ? `<div class="row" style="justify-content:flex-end;gap:6px"><button class="btn sm" data-ptog="${esc(p.id)}" data-on="${p.on ? 0 : 1}">${p.on ? "Turn off" : "Turn on"}</button><button class="btn sm danger" data-prm="${esc(p.id)}" data-n="${esc(p.name)}">Remove</button></div>` : ""}</td></tr>`).join("")}</tbody></table>` : ""}
    ${d.other.length ? `<h3>Copied in by hand</h3><table><tbody>${d.other.map(p => `<tr><td><b>${esc(p.folder)}</b>${errs(p)}</td><td class="num">${d.owner ? `<button class="btn sm" data-padopt="${esc(p.folder)}">Manage</button>` : ""}</td></tr>`).join("")}</tbody></table>` : ""}
    ${d.own_errors ? `<div class="banner warn">EasyServer's own plugin has ${d.own_errors} Lua error(s) in the log - another plugin may be interfering. Check Logs.</div>` : ""}
    <h3>Community plugins</h3>
    <div class="grid g2" style="gap:10px">${d.catalog.map(p => `<div class="card tight" style="padding:12px 14px"><div class="row"><b>${esc(p.name)}</b><span class="spacer"></span>${inst[p.id] ? `<span class="badge good">installed</span>` : ""}</div>
      <div class="small">${esc(p.about)}</div>
      <div class="small muted" style="margin-top:4px">By <b>${esc(p.author)}</b> · <a href="${esc(p.page)}" target="_blank" rel="noopener noreferrer">${esc(p.repo)}</a>${p.license ? " · License: " + esc(p.license) : ""}</div>
      ${p.notes.length ? `<ul class="small" style="margin:6px 0 0 16px;padding:0">${p.notes.map(n => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}
      ${d.owner ? `<div class="row" style="margin-top:8px"><button class="btn sm ${inst[p.id] ? "" : "primary"}" data-pget="${esc(p.id)}">${inst[p.id] ? "Update" : "Install…"}</button></div>` : ""}</div>`).join("")}</div>
    <p class="small muted" style="margin-top:8px">Plugins belong to their authors - thank them on their pages! Missing one? It can be added to the list on GitHub.</p>
    ${d.owner ? `<div class="row" style="margin-top:6px"><button class="btn sm" id="pl_up">Install a plugin from a .zip file…</button><input type="file" id="pl_file" accept=".zip" hidden></div>` : ""}
  </div>`;
  const review = j => new Promise(res => {
    const pl = j.plan;
    const bg = modal(`<h2 style="margin-top:0">Install ${esc(j.name)}?</h2>
      <p class="small muted">${esc(j.version || "")} · ${fmtSize(j.size || 0)} · SHA-256 <span class="mono">${esc((j.sha256 || "").slice(0, 16))}…</span></p>
      <p class="small"><b>Goes on the server</b> (Resources/Server):</p><ul class="small">${pl.server.map(s => `<li><span class="mono">${esc(s.folder)}</span> - ${s.files} files, ${s.lua} Lua script${s.lua === 1 ? "" : "s"}</li>`).join("") || "<li>nothing</li>"}</ul>
      <p class="small"><b>Players download</b> (Resources/Client, virus-checked):</p><ul class="small">${pl.client.map(c => `<li class="mono">${esc(c)}</li>`).join("") || "<li>nothing</li>"}</ul>
      ${pl.skipped ? `<p class="small muted">${pl.skipped} other file(s) (readme, licence …) are left out.</p>` : ""}
      ${j.entry ? "" : `<label class="toggle"><input type="checkbox" id="pl_trust"><span><b>I trust this plugin's author</b><small>It isn't on the list. A server plugin can read and change files the server can reach.</small></span></label>`}
      <div class="row" style="margin-top:12px"><button class="btn primary" id="pl_ok">Install</button><button class="btn" data-x>Cancel</button></div>`);
    bg.querySelector("[data-x]").onclick = () => { bg.remove(); res(false); };
    $("#pl_ok", bg).onclick = async () => {
      try { const r = await api("/api/plugins/install", { json: { job: j.job, trust: $("#pl_trust", bg) ? $("#pl_trust", bg).checked : false } }); toast(r.note, 9000); bg.remove(); res(true); }
      catch (e) { toast(e.message, 8000); }
    };
  });
  el.querySelectorAll("[data-pget]").forEach(b => b.onclick = async () => {
    b.disabled = true; b.textContent = "Starting…";
    let r; try { r = await api("/api/plugins/fetch", { json: { id: b.dataset.pget } }); } catch (e) { b.disabled = false; b.textContent = "Install…"; return toast(e.message, 7000); }
    const tick = async () => {
      let j; try { j = await api("/api/plugins/job?job=" + r.job); } catch (e) { b.disabled = false; return toast(e.message); }
      if (!j.finished) { b.textContent = j.total ? Math.round(100 * j.done / j.total) + "%" : j.done ? fmtSize(j.done) : j.state; return setTimeout(tick, 800); }
      b.disabled = false; b.textContent = "Install…";
      if (!j.ok) return toast(j.error, 10000);
      if (await review(j)) loadPlugins();
    };
    tick();
  });
  if ($("#pl_up")) {
    $("#pl_up").onclick = () => $("#pl_file").click();
    $("#pl_file").onchange = async e => {
      const f = e.target.files[0]; if (!f) return;
      const r = await fetch("/api/plugins/upload?name=" + encodeURIComponent(f.name), { method: "PUT", headers: { "X-ES-CSRF": CSRF, "X-ES-Server": SERVER }, body: f });
      let j = {}; try { j = await r.json(); } catch (x) {}
      e.target.value = "";
      if (!r.ok) return toast(j.error || "Upload failed", 9000);
      if (await review(j)) loadPlugins();
    };
  }
  el.querySelectorAll("[data-ptog]").forEach(b => b.onclick = async () => { try { const r = await api("/api/plugins/toggle", { json: { id: b.dataset.ptog, on: b.dataset.on === "1" } }); toast(r.note, 7000); loadPlugins(); } catch (e) { toast(e.message, 7000); } });
  el.querySelectorAll("[data-prm]").forEach(b => b.onclick = async () => {
    if (!confirm(`Remove ${b.dataset.n}? Its files are deleted from the server (its saved data too, if it keeps any in its folder).`)) return;
    try { const r = await api("/api/plugins/remove", { json: { id: b.dataset.prm } }); toast(r.note, 7000); loadPlugins(); } catch (e) { toast(e.message, 7000); }
  });
  el.querySelectorAll("[data-padopt]").forEach(b => b.onclick = async () => { try { await api("/api/plugins/adopt", { json: { folder: b.dataset.padopt } }); loadPlugins(); } catch (e) { toast(e.message, 7000); } });
}

async function modpackCode() {
  let d; try { d = await api("/api/modpack/code"); } catch (e) { return toast(e.message); }
  const bg = modal(`<div class="row"><h2 style="margin:0">Mod pack code</h2><span class="spacer"></span><button class="btn sm" data-x>Close</button></div>
    <p class="small muted">A short code instead of a big file. Another EasyServer owner pastes it and gets the same mods straight from the BeamNG repository (each one virus-checked).</p>
    ${d.code ? `<textarea id="mpc_t" readonly rows="3" class="mono">${esc(d.code)}</textarea><div class="row" style="margin-top:6px"><button class="btn sm primary" id="mpc_copy">Copy code</button><span class="small muted">${d.count} mod${d.count === 1 ? "" : "s"}</span></div>` : `<p class="small">None of your mods come from the BeamNG repository, so there's nothing to put in a code - use "Download modpack" instead.</p>`}
    ${d.not_included.length ? `<p class="small muted">Not in the code (not from the repository): ${esc(d.not_included.join(", "))} - send these as a modpack file.</p>` : ""}
    <label class="f" style="margin-top:12px"><span>Got a code? Paste it here</span><textarea id="mpc_in" rows="3" class="mono" placeholder="ES1-…" spellcheck="false"></textarea></label>
    <div class="row"><button class="btn sm" id="mpc_go">Install these mods</button></div>`);
  bg.querySelector("[data-x]").onclick = () => bg.remove();
  if ($("#mpc_copy", bg)) $("#mpc_copy", bg).onclick = async () => toast(await copyText(d.code) ? "Code copied" : "Select the code and press Ctrl+C");
  $("#mpc_go", bg).onclick = async () => {
    try { const r = await api("/api/modpack/code", { json: { code: $("#mpc_in", bg).value } }); toast(r.note, 10000); bg.remove(); } catch (e) { toast(e.message, 8000); }
  };
}

/* ---------------- 1.15: vehicle rules (Config) */
async function loadVeh() {
  const el = $("#vehrules"); if (!el) return;
  let v; try { v = await api("/api/vehicles"); } catch (e) { el.innerHTML = ""; return; }
  const r = v.rules, act = v.activity;
  const blockedSet = new Set(v.blocked.map(b => b.jbm.toLowerCase()));
  const sugg = v.mods.filter(m => (m.heavy || m.kind !== "car") && !blockedSet.has(m.jbm.toLowerCase()));
  const kindBadge = k => k === "unknown" ? "" : `<span class="badge ${/heavy/.test(k) ? "warn" : ""}">${esc(k)}</span>`;
  el.innerHTML = `<div class="card" style="margin-top:16px" id="vehcard"><div class="row"><h2 style="margin:0">Vehicle rules: block props, heavy cars &amp; spawn spam</h2><span class="spacer"></span>
      <span class="pill ${r.on ? "good" : ""}"><span class="dot"></span>${r.on ? v.blocked.length + " blocked" : "Off"}</span></div>
    <p class="small muted">The server refuses a blocked car or prop before anyone sees it, and tells the player why. Works within 10 seconds, no restart, no extra mod for players.</p>
    <div class="grid g2" style="gap:10px">${v.presets.map(p => `<div class="card tight" style="padding:12px 14px;${p.id === v.preset ? "border-color:var(--accent)" : ""}"><div class="row"><b>${esc(p.label)}</b><span class="spacer"></span><button class="btn sm" data-vpre="${esc(p.id)}" ${p.id === v.preset ? "disabled" : ""}>${p.id === v.preset ? "In use" : "Use"}</button></div><div class="small muted">${esc(p.about)}</div></div>`).join("")}</div>
    <label class="toggle" style="margin-top:12px"><input type="checkbox" id="vr_on" ${r.on ? "checked" : ""}><span><b>Vehicle rules on</b><small>Turn off to allow everything without losing your choices</small></span></label>
    <label class="toggle"><input type="checkbox" id="vr_props" ${r.props ? "checked" : ""}><span><b>Block props</b><small>Cones, barrels, balls, ramps, walls … (${v.base.props.length} game props + prop mods)</small></span></label>
    <label class="toggle"><input type="checkbox" id="vr_hprops" ${r.heavyprops ? "checked" : ""}><span><b>Block big physics props</b><small>Crushers, spinners, giant rollers, shipping containers, bridges - the usual cause of sudden server-wide lag</small></span></label>
    <label class="toggle"><input type="checkbox" id="vr_trail" ${r.trailers ? "checked" : ""}><span><b>Block trailers</b><small>Caravans, flatbeds, tankers, dry vans …</small></span></label>
    <label class="toggle"><input type="checkbox" id="vr_hmods" ${r.heavymods ? "checked" : ""}><span><b>Block heavy mod cars (auto-detected)</b><small>EasyServer looks inside your car mods and counts how complex they are (over ${v.heavy_limits.nodes.toLocaleString()} nodes or ${v.heavy_limits.beams.toLocaleString()} beams). Very complex cars make everyone's game slower.</small></span></label>
    <label class="toggle"><input type="checkbox" id="vr_exempt" ${r.exempt ? "checked" : ""}><span><b>Admins may spawn anything</b><small>Admins are set under Moderation</small></span></label>
    <div class="grid g2" style="gap:12px">
      <label class="f" style="margin:0"><span>Seconds between spawns</span><input type="number" id="vr_cd" min="0" max="3600" value="${esc(r.cooldown)}"><small>0 = no wait</small></label>
      <label class="f" style="margin:0"><span>Max spawns per minute</span><input type="number" id="vr_spam" min="0" max="120" value="${esc(r.spam)}"><small>Stops spawn spam. 0 = no limit</small></label></div>
    <label class="f"><span>Also block these cars (model names)</span><input type="text" id="vr_cars" value="${esc(r.cars.join(", "))}" placeholder="e.g. bolide, sbr" spellcheck="false"><small>Use the Block buttons below, or type model names separated by commas</small></label>
    <label class="toggle"><input type="checkbox" id="vr_only" ${r.only ? "checked" : ""}><span><b>Only allow these cars</b><small>One-make racing: everything else is refused</small></span></label>
    <label class="f"><span>Allowed cars (when "only" is on)</span><input type="text" id="vr_allow" value="${esc(r.allow.join(", "))}" placeholder="e.g. covet" spellcheck="false"></label>
    <div class="row"><button class="btn primary sm" id="vr_save">Save rules</button></div>
    ${sugg.length ? `<h3 style="margin-top:16px">Found in your mods</h3><p class="small muted">Auto-detected props, trailers and heavy cars that are still allowed.</p>
      <table><tbody>${sugg.slice(0, 20).map(m => `<tr><td><b>${esc(m.name || m.jbm)}</b> <span class="small muted mono">${esc(m.jbm)}</span> ${kindBadge((m.heavy && m.kind === "car" ? "heavy " : "") + m.kind)}<div class="small muted">${esc(m.mod)} · ${m.nodes.toLocaleString()} nodes, ${m.beams.toLocaleString()} beams</div></td><td class="num"><button class="btn sm" data-vblk="${esc(m.jbm)}">Block</button></td></tr>`).join("")}</tbody></table>` : ""}
    <h3 style="margin-top:16px">Spawned on this server (last ${act.days} days)</h3>
    ${act.seen.length ? `<table><tbody>${act.seen.slice(0, 25).map(s => `<tr><td><span class="mono">${esc(s.jbm)}</span> ${kindBadge(s.kind)}${s.blocked ? '<span class="badge bad">blocked</span>' : ""}<div class="small muted">${s.count}× by ${s.players} player${s.players === 1 ? "" : "s"} · last ${esc(fmtTime(s.last))}</div></td>
        <td class="num">${r.cars.some(c => c.toLowerCase() === s.jbm.toLowerCase()) ? `<button class="btn sm" data-vunb="${esc(s.jbm)}">Allow</button>` : s.blocked ? "" : `<button class="btn sm" data-vblk="${esc(s.jbm)}">Block</button>`}</td></tr>`).join("")}</tbody></table>`
      : `<p class="small muted">Nothing yet - the list fills up as players spawn cars.</p>`}
    ${act.blocked.length || act.spam.length ? `<h3 style="margin-top:16px">Refused lately</h3><ul class="small">${act.blocked.slice(0, 10).map(b => `<li>${esc(fmtTime(b.t))}: <b>${esc(b.name)}</b> tried <span class="mono">${esc(b.jbm)}</span> (${esc(b.why)})</li>`).join("")}${act.spam.slice(0, 5).map(b => `<li>${esc(fmtTime(b.t))}: <b>${esc(b.name)}</b> spawned too many cars in a minute</li>`).join("")}</ul>` : ""}
  </div>`;
  const list = id => $(id).value.split(/[\s,]+/).map(x => x.trim()).filter(Boolean);
  $("#vr_save").onclick = async () => {
    try { const x = await api("/api/vehicles", { json: { on: $("#vr_on").checked, props: $("#vr_props").checked, heavyprops: $("#vr_hprops").checked, trailers: $("#vr_trail").checked, heavymods: $("#vr_hmods").checked, exempt: $("#vr_exempt").checked, only: $("#vr_only").checked, cooldown: $("#vr_cd").value, spam: $("#vr_spam").value, cars: list("#vr_cars"), allow: list("#vr_allow") } }); toast(x.note, 7000); loadVeh(); } catch (e) { toast(e.message, 6000); }
  };
  el.querySelectorAll("[data-vpre]").forEach(b => b.onclick = async () => { try { const x = await api("/api/vehicles/preset", { json: { preset: b.dataset.vpre } }); toast(x.note, 6000); loadVeh(); } catch (e) { toast(e.message, 6000); } });
  el.querySelectorAll("[data-vblk],[data-vunb]").forEach(b => b.onclick = async () => { const blk = !!b.dataset.vblk; try { const x = await api("/api/vehicles/block", { json: { jbm: b.dataset.vblk || b.dataset.vunb, block: blk } }); toast(x.note, 6000); loadVeh(); } catch (e) { toast(e.message, 6000); } });
}

/* ---------------- 1.11: security presets + config history (Config) */
async function loadCfg111() {
  const el = $("#cfg111"); if (!el) return;
  let pr, hi;
  let tm = { items: [] };
  try { [pr, hi, tm] = await Promise.all([api("/api/preset"), api("/api/config/history"), api("/api/timed")]); }
  catch (e) { el.innerHTML = ""; return; }
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const others = SERVERS.filter(x => x.id !== SERVER);
  let tl = null; try { tl = await api("/api/tools"); } catch (e) {}
  el.innerHTML = `
    ${tl ? `<div class="card" style="margin-top:16px" id="toolscard"><div class="row"><h2 style="margin:0">In-game tools: commands, teleport &amp; repair</h2><span class="spacer"></span><span class="pill ${tl.installed ? "good" : ""}"><span class="dot"></span>${tl.installed ? "On" : "Off"}</span></div>
      <p class="small muted">Chat commands players can use. They need a tiny helper mod (${fmtSize(tl.size)}) that players download automatically when they join - EasyServer adds and removes it for you. It only shows this server's commands, and moves or repairs the player's own car when the server allows it.</p>
      <label class="toggle"><input type="checkbox" id="tl_sug" ${tl.suggest ? "checked" : ""}><span><b>Command suggestions in the chat</b><small>When players type "/" in the chat they see the commands of this server and can press Tab to complete them. A mistyped command gets a "did you mean ...?" answer either way.</small></span></label>
      <label class="toggle"><input type="checkbox" id="tl_tp" ${tl.tp ? "checked" : ""}><span><b>/tp name - teleport to another player</b><small>The other player has to type /tpaccept, so nobody can be followed against their will</small></span></label>
      <label class="f" style="max-width:260px"><span>Wait between teleports (seconds)</span><input type="number" id="tl_tpcd" min="0" max="3600" value="${esc(tl.tp_cd)}"></label>
      <label class="f" style="max-width:420px"><span>Repairing cars</span><select id="tl_rep">
        <option value="free" ${tl.repair === "free" ? "selected" : ""}>Normal - reset keys work (and /repair)</option>
        <option value="cooldown" ${tl.repair === "cooldown" ? "selected" : ""}>Realism - reset keys off, /repair every few minutes</option>
        <option value="off" ${tl.repair === "off" ? "selected" : ""}>Hardcore - no resets, no repairs</option></select>
        <small>Realism and Hardcore turn off the reset / recover / teleport keys for everyone on this server (good for roleplay and realism servers)</small></label>
      <label class="f" style="max-width:260px"><span>Minutes between repairs (Realism)</span><input type="number" id="tl_repcd" min="1" max="120" value="${esc(tl.repair_cd)}"></label>
      <div class="row"><button class="btn primary sm" id="tl_save">Save</button></div></div>` : ""}
    <div class="card" style="margin-top:16px" id="presetcard"><h2>Security presets</h2>
      <p class="small muted">One click sets who can join, guests, anti-bot checks, the chat filter and flood protection together. ${pr.current ? "Right now this server matches <b>" + esc(pr.presets.find(x => x.id === pr.current).label) + "</b>." : "Your current settings are a custom mix."}</p>
      <div class="grid g2" style="gap:10px">${pr.presets.map(p => `<div class="card tight" style="padding:12px 14px;${p.id === pr.current ? "border-color:var(--accent)" : ""}"><div class="row"><b>${esc(p.label)}</b>${p.id === "most_secure" ? ' <span class="badge">recommended</span>' : ""}<span class="spacer"></span><button class="btn sm" data-preset="${esc(p.id)}" ${p.id === pr.current ? "disabled" : ""}>${p.id === pr.current ? "In use" : "Use"}</button></div>
        <div class="small muted">${esc(p.about)}</div></div>`).join("")}</div>
    </div>
    <div class="card" style="margin-top:16px" id="timedcard"><h2>Announcements at set times</h2>
      <p class="small muted">Say something in the game chat at a fixed time, e.g. "Race night starts at 21:00!" every Friday at 20:30. Only sent when someone is online${tm.discord ? "; tick Discord to post it there too (and to Telegram / the webhook if set up)" : ""}.</p>
      <div id="tm_rows"></div>
      <div class="row" style="margin-top:8px;gap:6px"><button class="btn sm" id="tm_add">+ Add</button><button class="btn sm primary" id="tm_save">Save</button></div>
    </div>
    <div class="card" style="margin-top:16px" id="histcard"><div class="row"><h2 style="margin:0">What changed?</h2><span class="spacer"></span><span class="small muted">Last ${hi.keep} versions are kept</span></div>
      <p class="small muted">Every time the config is saved - here, by a template, a preset or a map switch - the old version is kept. Compare and go back with one click.</p>
      ${hi.items.length ? `<table style="margin-top:6px"><tbody>${hi.items.slice(0, 15).map((v, i) => `<tr><td>${esc(fmtTime(v.t))}</td><td>${esc(v.who)}</td><td class="small muted">${esc(v.why || "")}</td>
          <td class="num"><div class="row" style="justify-content:flex-end;gap:6px"><button class="btn sm" data-hdiff="${esc(v.id)}">${i === 0 ? "Show change" : "Compare with now"}</button>${i === 0 ? "" : `<button class="btn sm" data-hres="${esc(v.id)}">Restore</button>`}</div></td></tr>`).join("")}</tbody></table>`
        : `<p class="small muted">No changes saved yet.</p>`}
      ${others.length ? `<div class="row" style="margin-top:10px;gap:8px"><span class="small">Compare with another server:</span><select id="h_other" style="max-width:220px">${others.map(x => `<option value="${esc(x.id)}">${esc(x.name)}</option>`).join("")}</select><button class="btn sm" id="h_cmp">Compare</button></div>` : ""}
      <div id="h_out"></div>
    </div>`;
  if ($("#tl_save")) $("#tl_save").onclick = async () => {
    try { const r = await api("/api/tools", { json: { suggest: $("#tl_sug").checked, tp: $("#tl_tp").checked, tp_cd: $("#tl_tpcd").value, repair: $("#tl_rep").value, repair_cd: $("#tl_repcd").value } }); toast(r.note, 8000); loadCfg111(); } catch (e) { toast(e.message, 6000); }
  };
  let rows = tm.items.map(x => ({ ...x }));
  const drawTm = () => {
    $("#tm_rows").innerHTML = rows.length ? rows.map((x, i) => `<div class="card tight" style="padding:10px 12px;margin-top:8px" data-tm="${i}">
      <div class="row" style="flex-wrap:wrap;gap:8px"><input type="time" data-k="at" value="${esc(x.at || "20:00")}" style="width:auto;color-scheme:light dark;color:inherit">
        ${DAYS.map((d, j) => `<label class="badge" style="cursor:pointer"><input type="checkbox" data-day="${j}" ${(x.days || []).includes(j) ? "checked" : ""}> ${d}</label>`).join("")}
        <span class="spacer"></span><label class="small"><input type="checkbox" data-k="discord" ${x.discord ? "checked" : ""}> Discord</label><label class="small"><input type="checkbox" data-k="on" ${x.on !== false ? "checked" : ""}> On</label><button class="btn sm danger" data-tmdel="${i}">✕</button></div>
      <textarea data-k="text" rows="2" maxlength="600" style="min-height:44px;margin-top:6px" placeholder="Up to 3 lines">${esc(x.text || "")}</textarea></div>`).join("") : `<p class="small muted">None yet.</p>`;
    $("#tm_rows").querySelectorAll("[data-tmdel]").forEach(b => b.onclick = () => { collect(); rows.splice(+b.dataset.tmdel, 1); drawTm(); });
  };
  const collect = () => { $("#tm_rows").querySelectorAll("[data-tm]").forEach(c => { const x = rows[+c.dataset.tm];
    x.at = c.querySelector('[data-k="at"]').value; x.text = c.querySelector('[data-k="text"]').value; x.discord = c.querySelector('[data-k="discord"]').checked;
    x.on = c.querySelector('[data-k="on"]').checked; x.days = [...c.querySelectorAll("[data-day]")].filter(y => y.checked).map(y => +y.dataset.day); }); };
  drawTm();
  $("#tm_add").onclick = () => { collect(); if (rows.length >= 20) return toast("At most 20"); rows.push({ at: "20:00", days: [4, 5], text: "", discord: false, on: true }); drawTm(); };
  $("#tm_save").onclick = async () => { collect(); try { const r = await api("/api/timed", { json: { items: rows } }); toast(r.note); loadCfg111(); } catch (e) { toast(e.message, 6000); } };
  el.querySelectorAll("[data-preset]").forEach(b => b.onclick = async () => {
    const p = pr.presets.find(x => x.id === b.dataset.preset);
    if (!confirm("Use the \"" + p.label + "\" preset?\n\n" + p.about + "\n\nYou can change every setting afterwards.")) return;
    try { const r = await api("/api/preset", { json: { id: p.id, preset: p.label } }); toast(r.note, 8000); show("config"); } catch (e) { toast(e.message, 6000); }
  });
  const showDiff = d => {
    const val = v => v === undefined || v === null ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v);
    $("#h_out").innerHTML = `<div style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px"><p class="small"><b>${esc(d.a)}</b> → <b>${esc(d.b)}</b></p>
      ${d.changes.length ? `<table><thead><tr><th>Setting</th><th>Before</th><th>After</th></tr></thead><tbody>${d.changes.map(c => `<tr><td class="mono">${esc(c.key)}</td><td>${esc(val(c.old))}</td><td><b>${esc(val(c.new))}</b></td></tr>`).join("")}</tbody></table>` : `<p class="small muted">No setting changed (only spacing or comments).</p>`}
      ${d.lines.length ? `<details style="margin-top:8px"><summary class="small">Show the exact lines</summary><pre class="mono small" style="white-space:pre-wrap">${d.lines.map(l => `<span style="color:${l[0] === "+" ? "var(--good-ink)" : l[0] === "-" ? "var(--crit-ink)" : "inherit"}">${esc(l)}</span>`).join("\n")}</pre></details>` : ""}</div>`;
  };
  el.querySelectorAll("[data-hdiff]").forEach(b => b.onclick = async () => {
    const i = hi.items.findIndex(x => x.id === b.dataset.hdiff);
    const q = i === 0 && hi.items[1] ? "v=" + encodeURIComponent(hi.items[1].id) + "&w=" + encodeURIComponent(hi.items[0].id) : "v=" + encodeURIComponent(b.dataset.hdiff);
    try { showDiff(await api("/api/config/diff?" + q)); } catch (e) { toast(e.message); }
  });
  el.querySelectorAll("[data-hres]").forEach(b => b.onclick = async () => {
    if (!confirm("Go back to this version of the config? The current one is kept in the history too.")) return;
    try { const r = await api("/api/config/restore", { json: { v: b.dataset.hres } }); toast(r.note, 7000); show("config"); } catch (e) { toast(e.message); }
  });
  if ($("#h_cmp")) $("#h_cmp").onclick = async () => { try { showDiff(await api("/api/config/diff?other=" + encodeURIComponent($("#h_other").value))); } catch (e) { toast(e.message); } };
}

/* ---------------- 1.7: templates, map rotation, welcome & announcements (Config) */
async function loadCfg17() {
  const el = $("#cfg17"); if (!el) return;
  let tp, ro, ms;
  try { [tp, ro, ms] = await Promise.all([api("/api/templates"), api("/api/rotation"), api("/api/messages")]); }
  catch (e) { el.innerHTML = `<div class="card" style="margin-top:16px"><p class="small muted">${esc(e.message)}</p></div>`; return; }
  const pill = (on, txt) => `<span class="pill ${on ? "good" : ""}"><span class="dot"></span>${esc(txt)}</span>`;
  const everyOpt = (list, cur, day) => list.map(n => `<option value="${n}" ${n === cur ? "selected" : ""}>${n === 24 && day ? "Once a day" : "Every " + n + (day ? " hour" + (n === 1 ? "" : "s") : " minutes")}</option>`).join("");
  el.innerHTML = `
    <div class="card" style="margin-top:16px" id="tplcard"><h2>Quick setup: server templates</h2>
      <p class="small muted">One click sets the player limit, car cleanup, AFK removal, chat tags, chat rules, a welcome message and tips for the kind of server you want. You can change everything afterwards.</p>
      <div class="grid g2" style="gap:10px">${tp.templates.map(t => `<div class="card tight" style="padding:12px 14px"><div class="row"><b>${esc(t.label)}</b><span class="spacer"></span><button class="btn sm" data-tpl="${esc(t.id)}">Use</button></div>
        <div class="small muted">${esc(t.about)}</div><div class="small" style="margin-top:4px">Map ${esc(t.map)} · ${t.max_players} players · tags ${esc(t.tags.join(", "))}</div></div>`).join("")}</div>
      <label class="toggle" style="margin-top:8px"><input type="checkbox" id="tpl_map" checked><span><b>Also switch to the template's map</b><small>Restarts the server if it's running</small></span></label>
    </div>
    <div class="card" style="margin-top:16px" id="rotcard"><div class="row"><h2 style="margin:0">Map rotation</h2><span class="spacer"></span>${pill(ro.on, ro.on ? "On" : "Off")}</div>
      <p class="small muted">Switch to the next map in the list every few hours, so the server doesn't get boring. Players get a countdown in the chat. Now playing: <b>${esc(ro.current || "?")}</b>${ro.next ? " · next change " + esc(fmtTime(ro.next)) : ""}.</p>
      <label class="toggle"><input type="checkbox" id="ro_on" ${ro.on ? "checked" : ""}><span><b>Rotate the map</b><small>Off by default. Pick at least two maps, in order</small></span></label>
      <div class="row" style="flex-wrap:wrap;gap:6px;margin:8px 0">${ro.available.map(x => `<label class="badge" style="cursor:pointer"><input type="checkbox" data-rm="${esc(x)}" ${ro.maps.includes(x) ? "checked" : ""}> ${esc(x)}</label>`).join("")}</div>
      <div class="grid g3" style="gap:12px;margin:4px 0 8px">
        <label class="f" style="margin:0"><span>How often</span><select id="ro_every">${everyOpt(ro.every_choices, ro.every, true)}</select></label>
        <label class="f" style="margin:0"><span>Starting at</span><input type="time" id="ro_at" value="${esc(ro.at)}" style="color-scheme:light dark;color:inherit"></label>
        <label class="f" style="margin:0"><span>Countdown in chat</span><select id="ro_warn">${ro.warn_choices.map(n => `<option value="${n}" ${n === ro.warn ? "selected" : ""}>${n ? n + " min before" : "No countdown"}</option>`).join("")}</select></label>
      </div>
      <label class="toggle"><input type="checkbox" id="ro_empty" ${ro.empty_only ? "checked" : ""}><span><b>Only change the map when nobody is online</b><small>Waits up to 2 hours, then skips that change</small></span></label>
      <div class="row" style="margin-top:12px"><button class="btn primary" id="ro_save">Save rotation</button></div>
    </div>
    <div class="card" style="margin-top:16px" id="msgcard"><div class="row"><h2 style="margin:0">Welcome message &amp; announcements</h2><span class="spacer"></span>${pill(ms.welcome || ms.announce, ms.welcome && ms.announce ? "Both on" : ms.welcome ? "Welcome on" : ms.announce ? "Announcements on" : "Off")}</div>
      <p class="small muted">Use <span class="mono">{name}</span> for the player's name and <span class="mono">{players}</span> for how many are online. Works right away, no restart needed.${ms.plugin ? "" : " <b>Start the server once</b> so the stats plugin is installed."}</p>
      <label class="toggle"><input type="checkbox" id="ms_welcome" ${ms.welcome ? "checked" : ""}><span><b>Greet players when they join</b><small>Only the new player sees it. One line per chat message (up to 5)</small></span></label>
      <textarea id="ms_wtext" rows="2" spellcheck="false" style="min-height:60px">${esc(ms.welcome_text.join("\n"))}</textarea>
      <label class="toggle" style="margin-top:10px"><input type="checkbox" id="ms_announce" ${ms.announce ? "checked" : ""}><span><b>Post announcements in the chat</b><small>One message to everyone, in turn - only while someone is online</small></span></label>
      <label class="f"><span>Every</span><select id="ms_every" style="max-width:220px">${everyOpt(ms.every_choices, ms.every, false)}</select></label>
      <label class="f"><span>Announcements (one per line, up to 30)</span><textarea id="ms_list" rows="4" spellcheck="false" placeholder="Join our Discord: discord.gg/...&#10;Type /help for the commands&#10;No ramming - be nice!" style="min-height:90px">${esc(ms.messages.join("\n"))}</textarea></label>
      <div class="row" style="margin-top:12px"><button class="btn primary" id="ms_save">Save messages</button></div>
    </div>`;
  el.querySelectorAll("[data-tpl]").forEach(b => b.onclick = async () => {
    const t = tp.templates.find(x => x.id === b.dataset.tpl);
    if (!confirm(`Use the ${t.label} template? It changes the player limit, car cleanup, AFK removal, chat tags, chat rules and the welcome message${$("#tpl_map").checked ? ", and switches the map to " + t.map : ""}.`)) return;
    try { const r = await api("/api/template", { json: { id: t.id, map: $("#tpl_map").checked } }); toast(r.note, 6000); show("config"); } catch (e) { toast(e.message, 6000); }
  });
  $("#ro_save").onclick = async () => {
    const order = [...el.querySelectorAll("[data-rm]")].filter(x => x.checked).map(x => x.dataset.rm);
    const body = { on: $("#ro_on").checked, maps: order, every: Number($("#ro_every").value), at: $("#ro_at").value, warn: Number($("#ro_warn").value), empty_only: $("#ro_empty").checked };
    try { const r = await api("/api/rotation", { json: body }); toast(r.note, 6000); loadCfg17(); } catch (e) { toast(e.message, 6000); }
  };
  $("#ms_save").onclick = async () => {
    const body = { welcome: $("#ms_welcome").checked, welcome_text: $("#ms_wtext").value, announce: $("#ms_announce").checked, every: Number($("#ms_every").value), messages: $("#ms_list").value };
    try { const r = await api("/api/messages", { json: body }); toast(r.note); loadCfg17(); } catch (e) { toast(e.message, 6000); }
  };
}

/* ---------------- 1.7: backups, DuckDNS, computer load (Settings) */
async function loadSet17() {
  const el = $("#set17"); if (!el) return;
  let bk, st, rs;
  try { [bk, st, rs] = await Promise.all([api("/api/backups"), api("/api/settings"), api("/api/resources")]); }
  catch (e) { el.innerHTML = `<p class="small muted">${esc(e.message)}</p>`; return; }
  const n = rs.now || {};
  const fmtUp = k => k == null ? "-" : k >= 1000 ? (k / 1000).toFixed(1) + " Mbit/s" : Math.round(k) + " kbit/s";
  el.innerHTML = `
  <div class="grid g2" style="margin-top:16px">
    <div class="card"><div class="row"><h2 style="margin:0">Automatic backups</h2><span class="spacer"></span><span class="pill ${bk.on ? "good" : ""}"><span class="dot"></span>${bk.on ? "Nightly " + esc(bk.at) : "Off"}</span></div>
      <p class="small muted">Every night the settings of all servers (config, allow-list, bans, moderation, messages, rotation) are saved. The last ${bk.keep} are kept. ${SESSION.role === "owner" || !SESSION.role ? "Click Restore to put one back - how things are right now is saved first, so you can undo it." : "The owner can restore one."}</p>
      <label class="toggle"><input type="checkbox" id="bk_on" ${bk.on ? "checked" : ""}><span><b>Back up every night</b><small>On by default. Keys and passwords are never in a backup</small></span></label>
      <label class="toggle"><input type="checkbox" id="bk_mods" ${bk.mods ? "checked" : ""}><span><b>Include the mods</b><small>Can use a lot of disk space</small></span></label>
      <label class="f"><span>At</span><input type="time" id="bk_at" value="${esc(bk.at)}" style="max-width:160px;color-scheme:light dark;color:inherit"></label>
      <div class="row"><button class="btn primary" id="bk_save">Save</button><button class="btn" id="bk_now">Back up now</button></div>
      ${bk.items.length ? `<div style="margin-top:10px">${bk.items.map(b => `<div class="row small" style="padding:3px 0"><span>${esc(fmtTime(b.t))}${b.mods ? " · with mods" : ""} · ${esc(fmtSize(b.size))}</span><span class="spacer"></span>${SESSION.role === "owner" || !SESSION.role ? `<button class="btn sm" data-bres="${esc(b.file)}" data-bmods="${b.mods ? 1 : ""}" data-bt="${esc(fmtTime(b.t))}">Restore</button>` : ""}<a href="/api/backups/download?file=${encodeURIComponent(b.file)}&srv=${encodeURIComponent(SERVER)}" download>Download</a></div>`).join("")}</div>` : `<p class="small muted" style="margin-top:8px">No backups of this server yet.</p>`}
    </div>
    <div class="card"><div class="row"><h2 style="margin:0">Fixed address (DuckDNS)</h2><span class="spacer"></span><span class="pill ${st.duckdns_domain ? (st.duck_err ? "warn" : "good") : ""}"><span class="dot"></span>${st.duckdns_domain ? esc(st.duckdns_domain) + ".duckdns.org" : "Off"}</span></div>
      <p class="small muted">Most home internet gets a new IP address now and then, and your friends' saved address stops working. With a free DuckDNS name they always use <b>yourname.duckdns.org</b> - the dashboard keeps it pointing at your home.</p>
      ${st.duck_err ? `<div class="issue warning"><span class="ic">⚠</span><span>Last update failed: ${esc(st.duck_err)}</span></div>` : ""}
      <ol class="small" style="margin:6px 0 10px"><li>Sign in at <a href="https://www.duckdns.org" target="_blank" rel="noopener noreferrer">duckdns.org</a> (free, with Google, GitHub, Reddit...).</li><li>Type a name under "sub domain" and click <b>add domain</b>.</li><li>Copy the <b>token</b> from the top of the page and paste both below.</li></ol>
      <label class="f"><span>DuckDNS name</span><input type="text" id="dk_dom" value="${esc(st.duckdns_domain || "")}" placeholder="myserver" autocomplete="off" spellcheck="false"><small>Just the name - .duckdns.org is added. Empty + Save turns it off</small></label>
      <label class="f"><span>Token</span><input type="password" id="dk_tok" placeholder="${st.has_duck ? "Saved (encrypted) - paste a new one to replace" : "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}" autocomplete="off"></label>
      <button class="btn primary" id="dk_save">Save</button>
      ${st.duckdns_domain ? `<p class="small" style="margin-top:8px">Friends join at <span class="mono">${esc(st.duckdns_domain)}.duckdns.org:${esc(st.port_main || 30814)}</span> (the game port still has to be forwarded on your router).</p>` : ""}
    </div>
  </div>
  <div class="card" style="margin-top:16px"><h2>Computer load</h2>
    <p class="small muted">You get a warning when this computer runs out of memory, the processor is maxed out for 5 minutes, or the server uses almost all of your upload - with a suggested player limit.</p>
    <div class="grid g3" style="gap:10px;margin:8px 0">
      <div class="card tight stat" style="padding:10px 14px"><div class="label">Processor</div><div class="value">${n.cpu == null ? "-" : esc(Math.round(n.cpu)) + "%"}</div><div class="note">${rs.cpus} cores</div></div>
      <div class="card tight stat" style="padding:10px 14px"><div class="label">Free memory</div><div class="value">${n.mem_free == null ? "-" : esc(fmtSize(n.mem_free * 1048576))}</div><div class="note">of ${n.mem_total == null ? "?" : esc(fmtSize(n.mem_total * 1048576))}</div></div>
      <div class="card tight stat" style="padding:10px 14px"><div class="label">Upload used</div><div class="value">${esc(fmtUp(n.up_kbps))}</div><div class="note">${rs.upload_mbit ? "of " + esc(rs.upload_mbit) + " Mbit/s" : "set your speed below"}</div></div>
    </div>
    <div id="loadgraphs" style="margin:8px 0 12px"></div>
    <label class="f"><span>Your upload speed (Mbit/s)</span><div class="row"><input type="number" id="up_mbit" min="0" step="0.1" value="${esc(rs.upload_mbit || "")}" placeholder="e.g. 20" style="max-width:160px"><button class="btn" id="up_save">Save</button></div><small>Run a speed test (for example speedtest.net) on this computer and enter the <b>upload</b> number. Without it you only get memory and processor warnings.</small></label>
  </div>`;
  $("#bk_save").onclick = async () => { try { const r = await api("/api/backups", { json: { on: $("#bk_on").checked, mods: $("#bk_mods").checked, at: $("#bk_at").value } }); toast(r.note); loadSet17(); } catch (e) { toast(e.message); } };
  el.querySelectorAll("[data-bres]").forEach(b => b.onclick = async () => {
    if (!confirm("Restore the backup from " + b.dataset.bt + "? The server's config, allow-list, bans, moderation and messages go back to how they were then. How things are right now is saved as a backup first.")) return;
    const mods = !!b.dataset.bmods && confirm("This backup has the mods in it too. Put those mods back as well?\n\nOK = settings and mods, Cancel = only the settings.");
    b.disabled = true; toast("Restoring…", 20000);
    try { const r = await api("/api/backups/restore", { json: { file: b.dataset.bres, mods } }); toast(r.note, 9000); loadSet17(); } catch (e) { toast(e.message, 8000); b.disabled = false; }
  });
  $("#bk_now").onclick = async () => { $("#bk_now").disabled = true; try { const r = await api("/api/backups/now", { json: { mods: $("#bk_mods").checked } }); toast(r.note); loadSet17(); } catch (e) { toast(e.message, 6000); $("#bk_now").disabled = false; } };
  $("#dk_save").onclick = async () => { $("#dk_save").disabled = true; try { const r = await api("/api/duckdns", { json: { domain: $("#dk_dom").value, token: $("#dk_tok").value } }); toast(r.note, 7000); loadSet17(); } catch (e) { toast(e.message, 7000); $("#dk_save").disabled = false; } };
  drawLoadGraphs(rs.upload_mbit, rs.cpus);
  $("#up_save").onclick = async () => { try { const r = await api("/api/resources", { json: { upload_mbit: $("#up_mbit").value } }); toast(r.note); loadSet17(); } catch (e) { toast(e.message); } };
}

/* ---------------- 1.8: scheduled events (Config) */
async function loadEvents() {
  const el = $("#evcard"); if (!el) return;
  let d; try { d = await api("/api/events"); } catch (e) { el.innerHTML = ""; return; }
  const days = d.days;
  const row = (e, i) => `<div class="card tight" style="padding:12px 14px;margin-top:10px" data-ev="${i}">
      <div class="row"><input type="text" data-k="name" value="${esc(e.name || "")}" placeholder="Friday drift night" style="flex:1;font-weight:600"><label class="toggle" style="margin:0 0 0 10px"><input type="checkbox" data-k="on" ${e.on !== false ? "checked" : ""}><span><b>On</b></span></label><button class="btn sm danger" data-del="${i}" style="margin-left:8px">Remove</button></div>
      <div class="row" style="flex-wrap:wrap;gap:6px;margin:8px 0">${days.map((n, k) => `<label class="badge" style="cursor:pointer"><input type="checkbox" data-day="${k}" ${(e.days || []).includes(k) ? "checked" : ""}> ${n}</label>`).join("")}</div>
      <div class="grid g3" style="gap:10px">
        <label class="f" style="margin:0"><span>Starts at</span><input type="time" data-k="at" value="${esc(e.at || "20:00")}" style="color-scheme:light dark;color:inherit"></label>
        <label class="f" style="margin:0"><span>Lasts</span><select data-k="minutes">${[30, 60, 90, 120, 180, 240, 360].map(m => `<option value="${m}" ${m === (e.minutes || 120) ? "selected" : ""}>${m < 60 ? m + " min" : m / 60 + " h"}</option>`).join("")}</select></label>
        <label class="f" style="margin:0"><span>Map</span><select data-k="map">${d.maps.map(m => `<option ${m === e.map ? "selected" : ""}>${esc(m)}</option>`).join("")}</select></label>
      </div>
      ${d.mods.length ? `<div class="small" style="margin:8px 0 2px">Turn these mods on during the event (they're turned off again after):</div><div class="row" style="flex-wrap:wrap;gap:6px">${d.mods.map(m => `<label class="badge" style="cursor:pointer"><input type="checkbox" data-mod="${esc(m)}" ${(e.mods || []).includes(m) ? "checked" : ""}> ${esc(m)}</label>`).join("")}</div>` : ""}
      <div class="grid g2" style="gap:10px;margin-top:8px">
        <label class="f" style="margin:0"><span>Announce in Discord and the game</span><select data-k="announce">${[[0, "Only when it starts"], [10, "10 min before"], [30, "30 min before"], [60, "1 hour before"], [120, "2 hours before"], [1440, "1 day before"]].map(([v, l]) => `<option value="${v}" ${v === (e.announce ?? 30) ? "selected" : ""}>${l}</option>`).join("")}</select></label>
        <label class="f" style="margin:0"><span>Extra text (optional)</span><input type="text" data-k="text" value="${esc(e.text || "")}" placeholder="Bring your best drift car!"></label>
      </div>
      <label class="toggle"><input type="checkbox" data-k="ping" ${e.ping ? "checked" : ""}><span><b>Ping @everyone in Discord</b><small>Only in the announcement</small></span></label>
      ${e.next ? `<div class="small muted">Next: ${esc(fmtTime(e.next))}</div>` : ""}
    </div>`;
  let list = d.events.map(e => Object.assign({}, e));
  const render = () => {
    el.innerHTML = `<div class="card" style="margin-top:16px"><div class="row"><h2 style="margin:0">Events</h2><span class="spacer"></span><span class="pill ${list.some(e => e.on !== false) ? "good" : ""}"><span class="dot"></span>${list.length ? list.length + " planned" : "None"}</span></div>
      <p class="small muted">Weekly events like "Friday 20:00 drift night": announced in Discord${d.has_webhook ? "" : " (add a webhook in Settings)"} and the game chat, then the server switches to the event's map and mods, and back to your normal map when it's over. Players can type <span class="mono">/events</span> in Discord to see what's coming.</p>
      ${d.active ? `<div class="issue info"><span class="ic">★</span><span><b>${esc(d.active.name)}</b> is running until ${esc(fmtTime(d.active.end))}.</span><button class="btn sm" id="ev_stop" style="margin-left:auto">End now</button></div>` : ""}
      <div id="evlist">${list.map(row).join("")}</div>
      <div class="row" style="margin-top:12px"><button class="btn" id="ev_add">Add event</button><button class="btn primary" id="ev_save">Save events</button></div></div>`;
    el.querySelectorAll("[data-del]").forEach(b => b.onclick = () => { collect(); list.splice(Number(b.dataset.del), 1); render(); });
    $("#ev_add").onclick = () => { collect(); list.push({ name: "", days: [4], at: "20:00", minutes: 120, map: d.maps[0], announce: 30, on: true }); render(); };
    $("#ev_save").onclick = async () => { collect(); try { const r = await api("/api/events", { json: { events: list } }); toast(r.note); loadEvents(); } catch (e) { toast(e.message, 6000); } };
    if ($("#ev_stop")) $("#ev_stop").onclick = async () => { try { const r = await api("/api/events/stop", { method: "POST" }); toast(r.note); setTimeout(loadEvents, 4000); } catch (e) { toast(e.message); } };
  };
  const collect = () => {
    list = [...el.querySelectorAll("[data-ev]")].map((c, i) => {
      const v = k => c.querySelector(`[data-k="${k}"]`);
      return { id: list[i] && list[i].id, name: v("name").value, on: v("on").checked, at: v("at").value, minutes: Number(v("minutes").value),
               map: v("map").value, announce: Number(v("announce").value), text: v("text").value, ping: v("ping").checked,
               days: [...c.querySelectorAll("[data-day]")].filter(x => x.checked).map(x => Number(x.dataset.day)),
               mods: [...c.querySelectorAll("[data-mod]")].filter(x => x.checked).map(x => x.dataset.mod) };
    });
  };
  render();
}

/* ---------------- 1.8: CPU / memory / upload graphs (Settings -> Computer load) */
async function drawLoadGraphs(upMbit, cpus) {
  const el = $("#loadgraphs"); if (!el) return;
  let r; try { r = await api("/api/resources?n=1440"); } catch (e) { return; }
  const h = r.history || [];
  if (h.length < 3) { el.innerHTML = `<p class="small muted">Graphs appear after a few minutes - one point per minute, last 24 hours (kept while the dashboard runs).</p>`; return; }
  const W = 560, H = 90, t0 = h[0].t, t1 = h[h.length - 1].t || t0 + 1;
  const chart = (title, key, max, fmt, note) => {
    const pts = h.filter(p => p[key] != null);
    if (!pts.length) return "";
    const top = Math.max(max || 0, ...pts.map(p => p[key])) || 1;
    const xy = p => [((p.t - t0) / Math.max(1, t1 - t0)) * W, H - (p[key] / top) * (H - 6) - 2];
    const line = pts.map(p => xy(p).map(n => n.toFixed(1)).join(",")).join(" ");
    const last = pts[pts.length - 1][key];
    return `<div class="card tight" style="padding:10px 12px"><div class="row small"><b>${title}</b><span class="spacer"></span><span>now ${esc(fmt(last))}</span></div>
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" style="width:100%;height:70px;display:block;margin-top:4px" role="img" aria-label="${esc(title)} over the last ${Math.round((t1 - t0) / 3600) || 1} hours">
        <line x1="0" y1="${H - 1}" x2="${W}" y2="${H - 1}" stroke="currentColor" stroke-opacity=".15"/>
        <polyline points="${line}" fill="none" stroke="var(--accent)" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
      </svg><div class="row small muted"><span>${esc(fmtTime(t0))}</span><span class="spacer"></span><span>${note || "max " + esc(fmt(top))}</span></div></div>`;
  };
  const mb = v => fmtSize(v * 1048576);
  const up = k => k >= 1000 ? (k / 1000).toFixed(1) + " Mbit/s" : Math.round(k) + " kbit/s";
  el.innerHTML = `<div class="grid g2" style="gap:10px">
    ${chart("Processor", "cpu", 100, v => Math.round(v) + "%", "0-100%")}
    ${chart("Free memory", "mem_free", 0, mb)}
    ${chart("Upload", "up_kbps", upMbit ? upMbit * 1000 : 0, up, upMbit ? "line top = your " + upMbit + " Mbit/s" : "")}
    ${chart("Players online", "players", 1, v => String(v))}</div>`;
}

/* ---------------- 1.9: phone app + push (Settings) */
async function loadSupporter() {
  const b = $("#supbox"); if (!b) return;
  let d; try { d = await api("/api/supporter"); } catch (e) { b.remove(); return; }
  if (d.off) { b.remove(); return; }
  const owner = (SESSION.role || "owner") === "owner";
  b.innerHTML = d.active ? `<div class="row"><h2 style="margin:0">Supporter <span class="badge good">Active</span></h2><span class="spacer"></span>${owner ? `<button class="btn sm" id="sup_rm">Remove from this computer</button>` : ""}</div>
      <p class="small" style="margin:8px 0">Thank you for supporting EasyServer! ${d.plan ? esc(d.plan) + " · " : ""}${d.email ? esc(d.email) + " · " : ""}${d.expires_at ? "renews/ends " + esc(String(d.expires_at).slice(0, 10)) : "no end date"}</p>
      <label class="toggle"><input type="checkbox" id="sup_ea" ${d.early_access ? "checked" : ""} ${owner ? "" : "disabled"}><span><b>Experimental versions</b><small>Get the newest features first, before they're fully tested${d.early ? " - " + esc(d.early) + " is ready now" : ""}</small></span></label>
      ${d.early && d.early_url ? `<p class="small"><a href="${esc(d.early_url)}" target="_blank" rel="noopener">Download EasyServer ${esc(d.early)} (preview)</a></p>` : ""}`
    : `<div class="row"><h2 style="margin:0">Support EasyServer</h2><span class="spacer"></span><a class="btn sm" href="${esc(d.url)}" target="_blank" rel="noopener">${d.shop_open ? "Become a supporter" : "Coming soon"}</a></div>
      <p class="small muted" style="margin:8px 0">EasyServer is free and stays free - every feature works without paying. Supporters get early access to new versions and a bigger say in what gets built next.</p>
      ${d.status && d.status !== "active" ? `<div class="banner warn"><span class="small">Your licence isn't active (${esc(d.status)}). Supporter extras are off - everything else keeps working.</span></div>` : ""}
      ${owner ? `<div class="row"><input type="text" id="sup_key" placeholder="Licence key from your email" maxlength="80" spellcheck="false" autocomplete="off" style="flex:1"><button class="btn primary" id="sup_go">Activate</button></div>` : ""}`;
  if ($("#sup_go")) $("#sup_go").onclick = async () => { $("#sup_go").disabled = true; try { const r = await api("/api/supporter", { json: { key: $("#sup_key").value.trim() } }); toast(r.note, 7000); renderShell(); show("settings"); } catch (e) { toast(e.message, 8000); $("#sup_go").disabled = false; } };
  if ($("#sup_rm")) $("#sup_rm").onclick = async () => { if (!confirm("Remove the supporter licence from this computer? You can activate it again here or on another computer.")) return; try { const r = await api("/api/supporter", { json: { action: "remove" } }); toast(r.note, 6000); show("settings"); } catch (e) { toast(e.message); } };
  if ($("#sup_ea")) $("#sup_ea").onchange = async () => { try { await api("/api/supporter", { json: { early_access: $("#sup_ea").checked } }); toast("Saved"); } catch (e) { toast(e.message); } };
}
async function loadPhone() {
  const el = $("#phonecard"); if (!el) return;
  let pa, nt;
  try { [pa, nt] = await Promise.all([api("/api/phoneapp"), api("/api/ntfy")]); } catch (e) { el.innerHTML = `<h2>Phone app</h2><p class="small muted">${esc(e.message)}</p>`; return; }
  const qr = (q, px) => q ? `<svg viewBox="-4 -4 ${q[0] + 8} ${q[0] + 8}" width="${px}" height="${px}" style="background:#fff;border-radius:8px;display:block" role="img" aria-label="QR code"><path d="${q[1]}" fill="#000"/></svg>` : "";
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  el.innerHTML = `<h2>Phone app</h2>
    <p class="small muted">Manage your servers from your phone like a normal app - with its own icon, full screen, no browser bar.${standalone ? " <b>You're using it as an app right now.</b>" : ""}</p>
    <div class="grid g2" style="gap:12px;margin-top:6px">
      <div class="card tight" style="padding:12px 14px"><b>Android</b>
        <ol class="small" style="margin:6px 0">
          <li>On the phone, download <b>BeamMP-EasyServer.apk</b> from <a href="${esc(pa.apk)}" target="_blank" rel="noopener noreferrer">the latest release</a> and open it (allow "install unknown apps" for your browser when asked).</li>
          <li>Open the app and scan this code with the phone's camera - the app connects to this dashboard${pa.https ? " and remembers its certificate, so nobody can pretend to be your server" : ""}.</li></ol>
        ${pa.https ? qr(pa.qr, 170) : `<div class="issue warning"><span class="ic">⚠</span><span>Turn on <b>HTTPS</b> (Settings → Access from the internet) first - the app only connects over an encrypted connection.</span></div>`}
        ${pa.https ? `<div class="small muted" style="margin-top:6px">Address: <span class="mono">${blurIPs(esc(pa.url))}</span></div>` : ""}
      </div>
      <div class="card tight" style="padding:12px 14px"><b>iPhone</b>
        <ol class="small" style="margin:6px 0">
          <li>Open this dashboard in <b>Safari</b> on the iPhone (same address as on this computer).</li>
          <li>Tap the <b>Share</b> button, then <b>Add to Home Screen</b> → Add.</li>
          <li>Open it from the new <b>BeamMP</b> icon - it opens full screen like an app.</li></ol>
        <p class="small muted">Apple only allows apps from the App Store, so on iPhone it's a home-screen app. Android phones can do the same in Chrome (⋮ → Add to Home screen) instead of the .apk.</p>
      </div>
    </div>
    <h3 style="margin:16px 0 4px">Push notifications on the phone</h3>
    <p class="small muted">Get crashes, security alerts, joins and everything else you picked under "Notify me about" as real phone notifications - through the free <b>ntfy</b> app (Android and iPhone), even when the dashboard isn't open.</p>
    <label class="toggle"><input type="checkbox" id="nt_on" ${nt.enabled ? "checked" : ""}><span><b>Send notifications to my phone</b><small>Off by default</small></span></label>
    ${nt.has_topic ? `<div class="row" style="align-items:flex-start;gap:14px;margin:8px 0;flex-wrap:wrap">${qr(nt.qr, 150)}
      <ol class="small" style="margin:0;flex:1;min-width:220px"><li>Install <b>ntfy</b> from the Play Store / App Store.</li>
        <li>In ntfy tap <b>+</b> (subscribe to topic), paste this topic and subscribe:<br><span class="mono" style="word-break:break-all">${esc(nt.subscribe.split("/").pop())}</span> <button class="btn sm" id="nt_copy">Copy</button></li>
        <li>Or on the phone just open: <a href="${esc(nt.app_link)}">${esc(nt.app_link)}</a></li>
        <li>Press <b>Send test</b> below.</li></ol></div>
      <p class="small muted">Keep the topic secret - anyone who knows it can read your notifications. "New topic" makes a new one (subscribe again on the phone).</p>` : ""}
    <div class="row"><button class="btn primary" id="nt_save">Save</button>${nt.has_topic ? `<button class="btn" id="nt_test">Send test</button><button class="btn" id="nt_new">New topic</button>` : ""}</div>`;
  $("#nt_save").onclick = async () => { try { await api("/api/ntfy", { json: { enabled: $("#nt_on").checked } }); toast("Saved"); loadPhone(); } catch (e) { toast(e.message); } };
  if ($("#nt_test")) $("#nt_test").onclick = async () => { try { await api("/api/ntfy", { json: { test: true } }); toast("Test sent - check your phone"); } catch (e) { toast(e.message, 6000); } };
  if ($("#nt_new")) $("#nt_new").onclick = async () => { if (!confirm("Make a new topic? Phones subscribed to the old one stop getting notifications.")) return; try { await api("/api/ntfy", { json: { new_topic: true } }); loadPhone(); } catch (e) { toast(e.message); } };
  if ($("#nt_copy")) $("#nt_copy").onclick = () => { navigator.clipboard && navigator.clipboard.writeText(nt.subscribe.split("/").pop()).then(() => toast("Copied")); };
}

/* ---------------- users + roles (Settings, owner only) */
async function loadInteg() {
  const el = $("#integcard"); if (!el) return;
  let d; try { d = await api("/api/integrations"); } catch (e) { el.innerHTML = `<h2>Telegram, Slack &amp; other apps</h2><p class="small muted">${esc(e.message)}</p>`; return; }
  const T = d.telegram, W = d.webhook;
  el.innerHTML = `<h2>Telegram, Slack &amp; other apps</h2>
    <p class="small muted">The same alerts as Discord and email (the switches under Notifications decide which), sent to more places. Security alerts always go to every channel that is set up.</p>
    <div class="grid g2" style="gap:16px">
      <div><h3 style="margin:0 0 6px;font-size:15px">Telegram</h3>
        <ol class="small muted" style="margin:0 0 8px;padding-left:18px"><li>In Telegram, open <b>@BotFather</b>, send <span class="mono">/newbot</span> and copy the token.</li><li>Paste it below and save.</li><li>Send your new bot a message (or add it to a group), then click <b>Find my chat</b>.</li></ol>
        <label class="f"><span>Bot token</span><input type="password" id="tg_token" autocomplete="off" placeholder="${T.has_token ? "Saved (encrypted) - paste a new one to replace" : "123456789:ABC…"}"></label>
        <label class="f"><span>Chat ID</span><div class="row" style="gap:6px"><input type="text" id="tg_chat" value="${esc(T.chat)}" placeholder="found automatically"><button class="btn sm" id="tg_find" ${T.has_token ? "" : "disabled"}>Find my chat</button></div></label>
        <label class="toggle"><input type="checkbox" id="tg_on" ${T.enabled ? "checked" : ""}><span><b>Send alerts to Telegram</b></span></label>
        <div class="row" style="gap:6px"><button class="btn sm primary" id="tg_save">Save</button><button class="btn sm" id="tg_test" ${T.has_token && T.chat ? "" : "disabled"}>Send test</button>${T.has_token ? `<button class="btn sm" id="tg_del">Remove</button>` : ""}</div></div>
      <div><h3 style="margin:0 0 6px;font-size:15px">Any app with a webhook</h3>
        <p class="small muted" style="margin:0 0 8px">Slack, Mattermost, Rocket.Chat, Google Chat, Microsoft Teams (Workflows), Home Assistant, n8n, Zapier… Paste the incoming-webhook address the app gives you.</p>
        <label class="f"><span>Webhook address</span><input type="password" id="wh_url" autocomplete="off" placeholder="${W.has_url ? "Saved: " + esc(W.host) + " - paste a new one to replace" : "https://hooks.slack.com/services/…"}"></label>
        <label class="toggle"><input type="checkbox" id="wh_on" ${W.enabled ? "checked" : ""}><span><b>Send alerts to the webhook</b></span></label>
        <div class="row" style="gap:6px"><button class="btn sm primary" id="wh_save">Save</button><button class="btn sm" id="wh_test" ${W.has_url ? "" : "disabled"}>Send test</button>${W.has_url ? `<button class="btn sm" id="wh_del">Remove</button>` : ""}</div></div>
    </div>
    <div style="border-top:1px solid var(--line);margin-top:14px;padding-top:12px">
      <label class="toggle"><input type="checkbox" id="ev_ads" ${d.event_ads ? "checked" : ""}><span><b>Advertise events automatically</b><small>Posts to ${d.discord ? "Discord" : "Discord (once the webhook is set)"}, Telegram and the webhook when you plan a new event and the day before it, and reminds players in the game chat every 30 minutes in the 3 hours before. Events are set up in Config → Events</small></span></label></div>`;
  const send = async (body, again = true) => { try { const r = await api("/api/integrations", { json: body }); toast(r.note, 6000); if (again) loadInteg(); } catch (e) { toast(e.message, 8000); } };
  $("#tg_save").onclick = () => { const b = { telegram_enabled: $("#tg_on").checked, telegram_chat: $("#tg_chat").value }; if ($("#tg_token").value.trim()) b.telegram_token = $("#tg_token").value.trim(); send(b); };
  $("#tg_find").onclick = () => send({ telegram_find: true });
  $("#tg_test").onclick = () => send({ test: "telegram" }, false);
  if ($("#tg_del")) $("#tg_del").onclick = () => confirm("Remove the Telegram bot token?") && send({ telegram_token: "" });
  $("#wh_save").onclick = () => { const b = { webhook_enabled: $("#wh_on").checked }; if ($("#wh_url").value.trim()) b.webhook_url = $("#wh_url").value.trim(); send(b); };
  $("#wh_test").onclick = () => send({ test: "webhook" }, false);
  if ($("#wh_del")) $("#wh_del").onclick = () => confirm("Remove the webhook?") && send({ webhook_url: "" });
  $("#ev_ads").onchange = () => send({ event_ads: $("#ev_ads").checked });
}

async function loadStatusPage() {
  const el = $("#statuscard"); if (!el) return;
  let d; try { d = await api("/api/statuspage"); } catch (e) { el.innerHTML = `<h2>Public status page</h2><p class="small muted">${esc(e.message)}</p>`; return; }
  const P = d.preview;
  el.innerHTML = `<div class="row"><h2 style="margin:0">Public status page</h2><span class="spacer"></span><span class="pill ${d.on ? "good" : ""}"><span class="dot"></span>${d.on ? "On" : "Off"}</span></div>
    <p class="small muted">A simple page anyone can open without logging in: is the server up, how many players, the map, the next event and the uptime of the last 30 days. No addresses, settings or admin buttons. Also as JSON for bots and websites (<span class="mono">/status.json</span>).</p>
    <label class="toggle"><input type="checkbox" id="sp_on" ${d.on ? "checked" : ""}><span><b>Turn on the status page</b></span></label>
    <label class="toggle"><input type="checkbox" id="sp_players" ${d.players ? "checked" : ""}><span><b>Show the names of online players</b><small>Off = only the number</small></span></label>
    <label class="toggle"><input type="checkbox" id="sp_mods" ${d.mods ? "checked" : ""}><span><b>Show the mods and the download size</b><small>So players know what they'll download before they launch the game</small></span></label>
    <label class="toggle"><input type="checkbox" id="sp_credit" ${d.credit ? "checked" : ""}><span><b>"Hosted with BeamMP EasyServer" at the bottom</b><small>A small link, so players who want their own server can find it</small></span></label>
    <label class="f"><span>Page title</span><input type="text" id="sp_title" maxlength="80" value="${esc(d.title)}" placeholder="${esc(P.title)}"></label>
    ${d.on ? `<p class="small">On your network: <a href="${esc(d.lan_url)}" target="_blank" rel="noopener">${esc(d.lan_url)}</a>${d.remote ? `<br>On the internet: <a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.url)}</a>` : `<br><span class="muted">Players outside your network can only open it once internet access to the dashboard is on (Network). Or share the Discord status message instead.</span>`}</p>` : ""}
    <div class="row" style="flex-wrap:wrap;gap:6px">${P.servers.map(x => `<span class="badge">${esc(x.name)}: ${esc(x.state)}${x.history.d30 != null ? " · " + x.history.d30 + "% (30 d)" : ""}</span>`).join("")}</div>
    <div class="row" style="margin-top:10px"><button class="btn sm primary" id="sp_save">Save</button></div>`;
  $("#sp_save").onclick = async () => {
    if ($("#sp_on").checked && !d.on && !confirm("Turn on the public status page? Anyone who can reach your dashboard address can see it without logging in.")) return;
    try { const r = await api("/api/statuspage", { json: { on: $("#sp_on").checked, players: $("#sp_players").checked, mods: $("#sp_mods").checked, credit: $("#sp_credit").checked, title: $("#sp_title").value } }); toast(r.note, 6000); loadStatusPage(); } catch (e) { toast(e.message, 6000); }
  };
}

async function loadDevices() {
  const el = $("#devcard"); if (!el) return;
  let d; try { d = await api("/api/devices"); } catch (e) { el.innerHTML = `<h2>Remembered devices</h2><p class="small muted">${esc(e.message)}</p>`; return; }
  const owner = SESSION.role === "owner";
  const rows = d.devices.map(x => `<tr><td>${esc(x.name || "Browser")}${x.this ? ' <span class="pill good">this device</span>' : ""}${owner && x.user !== "owner" ? ` <span class="muted small">· ${esc(x.user)}</span>` : ""}</td>
    <td class="small muted">${ago(x.last)}<br>${esc(x.ip)}</td><td class="small muted">since ${fmtTime(x.created)}</td>
    <td class="num"><button class="btn sm" data-forget="${esc(x.id)}">Forget</button></td></tr>`).join("");
  el.innerHTML = `<h2>Remembered devices</h2>
    <p class="small muted">Phones and browsers where "Stay logged in" was turned on. They log in by themselves for ${d.days} days after the last visit. Forget a device you lost or don't recognise - changing the password forgets all of them.</p>
    ${d.devices.length ? `<table><tbody>${rows}</tbody></table><div class="row" style="margin-top:10px"><button class="btn sm danger" id="forgetall">Forget all</button></div>` : '<p class="small muted">None yet.</p>'}`;
  const call = async body => { try { await api("/api/devices", { json: body }); toast("Forgotten"); loadDevices(); } catch (e) { toast(e.message); } };
  el.querySelectorAll("[data-forget]").forEach(b => b.onclick = () => call({ action: "forget", id: b.dataset.forget }));
  const fa = $("#forgetall"); if (fa) fa.onclick = () => { if (confirm("Forget every remembered device? They'll have to log in again.")) call({ action: "forget_all" }); };
}

async function loadUsers() {
  const el = $("#userscard"); if (!el) return;
  let d; try { d = await api("/api/users"); } catch (e) { el.innerHTML = `<h2>Users &amp; roles</h2><p class="small muted">${esc(e.message)}</p>`; return; }
  const allRoles = [...d.roles.map(r => ({ id: r, name: r })), ...d.custom_roles.map(r => ({ id: r.id, name: r.name }))];
  const rname = id => (allRoles.find(r => r.id === id) || { name: "deleted role" }).name;
  const roleSel = (attr, cur) => `<select ${attr} style="width:auto">${allRoles.map(r => `<option value="${esc(r.id)}" ${r.id === cur ? "selected" : ""}>${esc(r.name)}</option>`).join("")}</select>`;
  const many = d.servers.length > 1;
  const svText = u => u.servers === "all" ? (many ? "all servers" : "") : Object.entries(u.servers).map(([sid, r]) => `${(d.servers.find(s => s.id === sid) || { name: sid }).name}: ${rname(r)}`).join(", ");
  const RL = { admin: "Admin - everything except accounts, passwords, internet access and plugins", moderator: "Moderator - players: kick, mute, ban, allow-list, chat, start/restart", viewer: "Viewer - can look, can't change anything" };
  el.innerHTML = `<h2>Users &amp; roles</h2>
    <p class="small muted">Give friends their own login with only the rights they need. You (the owner) log in with the main password and an empty name. Everything they do shows up in Logs → Activity log.</p>
    ${d.users.length ? d.users.map(u => `<div class="small" style="padding:8px 0;border-top:1px solid var(--line)"><div class="row" style="gap:8px;flex-wrap:wrap"><b>${esc(u.name)}</b>${u.disabled ? '<span class="badge warn">disabled</span>' : ""}${u.totp ? '<span class="badge good">two-step on</span>' : ""}${u.remote ? `<span class="badge ${u.totp ? "good" : "warn"}">${u.totp ? "can log in from the internet" : "internet: needs two-step"}</span>` : ""}${u.discord ? `<span class="badge">Discord: ${esc(u.discord)}</span>` : ""}
      ${u.servers === "all" ? roleSel(`data-role="${esc(u.name)}"`, u.role) : `<span class="muted">${esc(svText(u))}</span>`}
      <span class="muted">${u.last_login ? "last login " + esc(ago(u.last_login)) : "never logged in"}${u.invited_by ? " · invited" : ""}</span><span class="spacer"></span></div>
      <div class="row" style="gap:6px;flex-wrap:wrap;margin-top:6px">${many ? `<button class="btn sm" data-usrv="${esc(u.name)}">Servers…</button>` : ""}
        <label class="small" style="display:flex;gap:4px;align-items:center"><input type="checkbox" data-uremote="${esc(u.name)}" ${u.remote ? "checked" : ""}> From the internet</label>
        ${u.totp ? `<button class="btn sm" data-u2fa="${esc(u.name)}">Reset two-step</button>` : ""}${u.discord ? `<button class="btn sm" data-udc="${esc(u.name)}">Unlink Discord</button>` : ""}
        <button class="btn sm" data-upw="${esc(u.name)}">New password</button><button class="btn sm" data-udis="${esc(u.name)}">${u.disabled ? "Enable" : "Disable"}</button><button class="btn sm danger" data-udel="${esc(u.name)}">Delete</button></div></div>`).join("") : `<p class="small muted">No extra accounts yet.</p>`}
    ${d.discord_login.available ? `<label class="toggle" style="margin-top:12px"><input type="checkbox" id="dl_on" ${d.discord_login.on ? "checked" : ""}><span><b>Let team members sign in with Discord</b><small>They link their Discord once under My account, then sign in with one click instead of typing a password. Two-step login and the internet rules stay the same. You (the owner) always use your password. It goes through a small EasyServer sign-in service, which stores nothing.</small></span></label>` : ""}
    <h3 style="margin-top:16px">Invite someone</h3>
    <p class="small muted">Easiest: send a link. They pick their own name and password${d.remote_enabled ? " (and set up two-step login if they may log in from the internet)" : ""} - you never handle their password. The link works once and stops working after 1 hour, so send it right away.</p>
    <div class="row" style="gap:8px;flex-wrap:wrap"><label class="small">Role ${roleSel('id="iv_role"', "moderator")}</label>
      ${many ? `<label class="small">Servers <select id="iv_srv" style="width:auto"><option value="all">All servers</option>${d.servers.map(s => `<option value="${esc(s.id)}">Only ${esc(s.name)}</option>`).join("")}</select></label>` : ""}
      <label class="small" style="display:flex;gap:4px;align-items:center"><input type="checkbox" id="iv_remote" ${d.remote_enabled ? "" : "disabled"}> May log in from the internet${d.remote_enabled ? "" : " (turn on Internet access first)"}</label>
      <button class="btn sm primary" id="iv_make">Make invite link</button></div>
    <div id="iv_out"></div>
    ${d.invites.length ? `<div class="small" style="margin-top:8px">${d.invites.map(x => `<div class="row" style="gap:8px;padding:4px 0">Open invite: <b>${esc(rname(x.role))}</b>${x.servers ? " · " + esc(Object.keys(x.servers).map(s => (d.servers.find(v => v.id === s) || { name: s }).name).join(", ")) : ""}${x.remote ? " · internet" : ""} <span class="muted">until ${esc(fmtTime(x.expires))}</span><span class="spacer"></span><button class="btn sm" data-ivrev="${esc(x.id)}">Revoke</button></div>`).join("")}</div>` : ""}
    <details style="margin-top:12px"><summary class="small">Or add an account yourself (you set the password)</summary>
    <div class="grid g2" style="gap:0 12px;margin-top:10px">
      <label class="f"><span>Name</span><input id="nu_name" maxlength="24" autocomplete="off" spellcheck="false" placeholder="e.g. dani"></label>
      <label class="f"><span>Role</span>${roleSel('id="nu_role"', "moderator")}</label>
      <label class="f"><span>Password</span><input id="nu_pw" type="password" autocomplete="new-password" placeholder="at least 10 characters"></label>
      <div class="small muted" style="align-self:center">${Object.entries(RL).map(([k, v]) => `<div>${esc(v)}</div>`).join("")}</div></div>
    <button class="btn" id="nu_add">Add account</button></details>
    <h3 style="margin-top:16px">Custom roles</h3>
    <p class="small muted">Make your own role by ticking what it may do, e.g. "Map master": maps &amp; events plus mods, but no banning.</p>
    ${d.custom_roles.map(r => `<div class="card tight" style="padding:10px 12px;margin-top:8px" data-crole="${esc(r.id)}"><div class="row"><input type="text" data-k="name" value="${esc(r.name)}" maxlength="40" style="max-width:220px"><span class="spacer"></span><button class="btn sm" data-crsave="${esc(r.id)}">Save</button><button class="btn sm danger" data-crdel="${esc(r.id)}">Delete</button></div>
      <div class="row small" style="flex-wrap:wrap;gap:10px;margin-top:6px">${d.perm_groups.map(g => `<label title="${esc(g.about)}" style="display:flex;gap:4px;align-items:center"><input type="checkbox" data-perm="${esc(g.id)}" ${r.perms.includes(g.id) ? "checked" : ""}> ${esc(g.name)}</label>`).join("")}</div></div>`).join("")}
    <div class="row" style="margin-top:8px;gap:8px"><input type="text" id="cr_name" maxlength="40" placeholder="New role name" style="max-width:220px"><button class="btn sm" id="cr_add">Add role</button></div>
    <p class="small muted">Every role can look at everything. Only you can manage accounts, passwords, internet access and server plugins. ${d.perm_groups.map(g => `<b>${esc(g.name)}</b>: ${esc(g.about)}`).join(" · ")}</p>`;
  const call = async (body, msg) => { try { const r = await api("/api/users", { json: body }); loadUsers(); toast(r.note || msg || "Saved", 8000); } catch (e) { toast(e.message, 6000); } };
  $("#nu_add").onclick = () => call({ action: "add", name: $("#nu_name").value.trim(), role: $("#nu_role").value, password: $("#nu_pw").value });
  el.querySelectorAll("[data-role]").forEach(x => x.onchange = () => call({ action: "role", name: x.dataset.role, role: x.value }));
  el.querySelectorAll("[data-uremote]").forEach(x => x.onchange = () => call({ action: "remote", name: x.dataset.uremote, remote: x.checked }));
  if ($("#dl_on")) $("#dl_on").onchange = async () => { try { await api("/api/discordlogin", { json: { on: $("#dl_on").checked } }); toast($("#dl_on").checked ? "Discord sign-in is on" : "Discord sign-in is off"); } catch (e) { toast(e.message, 7000); loadUsers(); } };
  el.querySelectorAll("[data-udc]").forEach(x => x.onclick = () => { if (confirm("Unlink Discord from " + x.dataset.udc + "? They'll be logged out.")) call({ action: "discord_unlink", name: x.dataset.udc }); });
  el.querySelectorAll("[data-u2fa]").forEach(x => x.onclick = () => { if (confirm("Turn off two-step login for " + x.dataset.u2fa + "? They'll be logged out and can set it up again (at home).")) call({ action: "reset_2fa", name: x.dataset.u2fa }); });
  el.querySelectorAll("[data-upw]").forEach(x => x.onclick = () => { const pw = prompt("New password for " + x.dataset.upw + " (at least 10 characters):"); if (pw) call({ action: "password", name: x.dataset.upw, password: pw }); });
  el.querySelectorAll("[data-udis]").forEach(x => x.onclick = () => call({ action: "disable", name: x.dataset.udis }));
  el.querySelectorAll("[data-udel]").forEach(x => x.onclick = () => { if (confirm("Delete the account " + x.dataset.udel + "?")) call({ action: "delete", name: x.dataset.udel }); });
  el.querySelectorAll("[data-usrv]").forEach(x => x.onclick = () => {
    const u = d.users.find(v => v.name === x.dataset.usrv);
    const bg = modal(`<h2 style="margin-top:0">Servers for ${esc(u.name)}</h2>
      <label class="toggle"><input type="checkbox" id="sv_all" ${u.servers === "all" ? "checked" : ""}><span><b>All servers, same role</b><small>${esc(rname(u.role))} everywhere - change it in the list</small></span></label>
      <div id="sv_list">${d.servers.map(s => { const cur = u.servers === "all" ? "" : (u.servers[s.id] || ""); return `<div class="row small" style="gap:8px;padding:4px 0"><b style="min-width:140px">${esc(s.name)}</b><select data-sv="${esc(s.id)}" style="width:auto"><option value="">No access</option>${allRoles.map(r => `<option value="${esc(r.id)}" ${r.id === cur ? "selected" : ""}>${esc(r.name)}</option>`).join("")}</select></div>`; }).join("")}</div>
      <p class="small muted">With only some servers, the account can't change dashboard-wide settings.</p>
      <div class="row"><button class="btn primary" id="sv_ok">Save</button><button class="btn" data-x>Cancel</button></div>`);
    const sync = () => { $("#sv_list", bg).style.opacity = $("#sv_all", bg).checked ? ".4" : "1"; };
    $("#sv_all", bg).onchange = sync; sync();
    bg.querySelector("[data-x]").onclick = () => bg.remove();
    $("#sv_ok", bg).onclick = async () => {
      const map = {}; bg.querySelectorAll("[data-sv]").forEach(s => { if (s.value) map[s.dataset.sv] = s.value; });
      bg.remove(); call({ action: "servers", name: u.name, servers: $("#sv_all", bg).checked ? "all" : map });
    };
  });
  $("#iv_make").onclick = async () => {
    const srv = $("#iv_srv") ? $("#iv_srv").value : "all";
    const role = $("#iv_role").value;
    try {
      const r = await api("/api/teaminvite", { json: { role, servers: srv === "all" ? "all" : { [srv]: role }, remote: $("#iv_remote").checked } });
      $("#iv_out").innerHTML = `<div class="card tight" style="padding:10px 12px;margin-top:8px"><div class="small">${esc(r.note)}</div><textarea readonly rows="2" class="mono" id="iv_link" style="margin-top:6px">${esc(r.link)}</textarea>
        <div class="row" style="margin-top:6px"><button class="btn sm primary" id="iv_copy">Copy link</button>${r.internet_link && r.link !== r.internet_link ? `<span class="small muted">Home network link. They need to be on your Wi-Fi to use it.</span>` : ""}</div></div>`;
      $("#iv_copy").onclick = async () => toast(await copyText(r.link) ? "Link copied" : "Select the link and press Ctrl+C");
    } catch (e) { toast(e.message, 6000); }
  };
  el.querySelectorAll("[data-ivrev]").forEach(x => x.onclick = async () => { try { await api("/api/teaminvite", { json: { action: "revoke", id: x.dataset.ivrev } }); loadUsers(); } catch (e) { toast(e.message); } });
  const roleCall = async body => { try { await api("/api/roles", { json: body }); loadUsers(); toast("Saved"); } catch (e) { toast(e.message, 7000); } };
  $("#cr_add").onclick = () => roleCall({ action: "save", name: $("#cr_name").value, perms: ["map"] });
  el.querySelectorAll("[data-crsave]").forEach(b => b.onclick = () => { const c = b.closest("[data-crole]"); roleCall({ action: "save", id: b.dataset.crsave, name: c.querySelector('[data-k="name"]').value, perms: [...c.querySelectorAll("[data-perm]:checked")].map(x => x.dataset.perm) }); });
  el.querySelectorAll("[data-crdel]").forEach(b => b.onclick = () => { if (confirm("Delete this role?")) roleCall({ action: "delete", id: b.dataset.crdel }); });
}

/* ---------------- team invite link (#team=...) */
/* ---------------- my account (extra accounts) */
async function openMyAccount() {
  let m; try { m = await api("/api/me"); } catch (e) { return toast(e.message); }
  if (m.owner) return show("settings");
  const roles = Object.entries(m.roles || {}).map(([sid, r]) => `${esc((SERVERS.find(s => s.id === sid) || { name: sid }).name)}: <b>${esc(r.name)}</b>`).join(" · ");
  const bg = modal(`<div class="row"><h2 style="margin:0">My account: ${esc(m.name)}</h2><span class="spacer"></span><button class="btn sm" data-x>Close</button></div>
    <p class="small muted">${roles}</p>
    <h3>Two-step login</h3><div id="ma_2fa">${m.totp ? `<span class="pill good"><span class="dot"></span>On</span> <button class="btn sm danger" id="ma_off" style="margin-left:8px">Turn off</button>` : `<p class="small">${m.remote ? "<b>Set this up to log in from the internet.</b> " : ""}A code from your phone as well as your password.</p><button class="btn" id="ma_on">Set up two-step login</button>`}</div>
    ${m.remote ? `<p class="small muted">The owner allows your account from the internet${m.remote_enabled ? "" : " (internet access is switched off at the moment)"}${m.totp ? "." : " - once two-step login is on."}</p>` : ""}
    ${m.discord_login ? `<h3>Discord</h3><div class="row" style="gap:8px">${m.discord ? `<span class="small">Linked to <b>${esc(m.discord)}</b> - you can press "Sign in with Discord" instead of typing your password.</span><span class="spacer"></span><button class="btn sm" id="ma_dcoff">Unlink</button>` : `<span class="small">Link your Discord account to sign in with one click. Your two-step code (if you have one) is still asked for.</span><span class="spacer"></span><button class="btn sm" id="ma_dc">Link Discord</button>`}</div>` : ""}
    <h3>Change password</h3>
    <label class="f"><span>Current password</span><input type="password" id="ma_cur" autocomplete="current-password"></label>
    <label class="f"><span>New password</span><input type="password" id="ma_new" autocomplete="new-password" placeholder="at least 10 characters"></label>
    <button class="btn" id="ma_pw">Change password</button>`);
  bg.querySelector("[data-x]").onclick = () => bg.remove();
  $("#ma_pw", bg).onclick = async () => { try { await api("/api/me/password", { json: { current: $("#ma_cur", bg).value, new: $("#ma_new", bg).value } }); toast("Password changed"); bg.remove(); } catch (e) { toast(e.message); } };
  if ($("#ma_dc", bg)) $("#ma_dc", bg).onclick = async () => { try { location.href = (await api("/api/me/discord/link", { method: "POST" })).url; } catch (e) { toast(e.message, 7000); } };
  if ($("#ma_dcoff", bg)) $("#ma_dcoff", bg).onclick = async () => { try { await api("/api/me/discord/unlink", { method: "POST" }); toast("Discord unlinked"); bg.remove(); } catch (e) { toast(e.message); } };
  if ($("#ma_off", bg)) $("#ma_off", bg).onclick = async () => { const pw = prompt("Your password, to turn off two-step login:"); if (!pw) return; try { await api("/api/me/2fa/disable", { json: { password: pw } }); toast("Two-step login is off"); bg.remove(); } catch (e) { toast(e.message, 7000); } };
  if ($("#ma_on", bg)) $("#ma_on", bg).onclick = async () => {
    let r; try { r = await api("/api/me/2fa/begin", { method: "POST" }); } catch (e) { return toast(e.message); }
    const n = Number(r.qr_size) || 0, qp = /^[MhvzZ0-9 -]*$/.test(r.qr_path || "") ? r.qr_path : "";
    $("#ma_2fa", bg).innerHTML = `${n && qp ? `<div style="background:#fff;padding:12px;border-radius:8px;display:inline-block;margin:6px 0"><svg width="200" height="200" viewBox="-4 -4 ${n + 8} ${n + 8}" shape-rendering="crispEdges"><rect x="-4" y="-4" width="${n + 8}" height="${n + 8}" fill="#fff"/><path d="${qp}" fill="#000"/></svg></div>` : ""}
      <p class="small muted">Or type this key in the app: <span class="mono">${esc(r.secret)}</span></p>
      <label class="f"><span>6-digit code</span><input type="text" id="ma_code" inputmode="numeric" maxlength="7" style="max-width:180px"></label><button class="btn primary" id="ma_ok">Turn on</button>`;
    $("#ma_ok", bg).onclick = async () => { try { await api("/api/me/2fa/confirm", { json: { code: $("#ma_code", bg).value } }); toast("Two-step login is on"); bg.remove(); } catch (e) { toast(e.message); } };
  };
}

/* ---------------- sleep + Wake-on-LAN (Settings) */
const ROUTERS = [
  ["fritz", "FRITZ!Box", m => `<ol class="small"><li>Open <b>fritz.box</b> → <b>Home Network</b> → <b>Network</b> → <b>Network Connections</b>.</li>
    <li>Click the pencil next to this computer (MAC <span class="mono">${m}</span>).</li>
    <li>Turn on <b>"Start this computer automatically as soon as it is accessed from the internet"</b> → OK. <b>Start Computer</b> on the same page wakes it right now.</li></ol>
    <p class="small muted">Then friends who join with your address (or DuckDNS name) wake the computer up just by trying to connect - the first try fails, joining again after about 30 seconds works. Away from home you can press <b>Start Computer</b> through MyFRITZ! or the FRITZ!Box VPN. The FRITZ!Box only does this if the computer was idle for at least 15 minutes.</p>`],
  ["asus", "ASUS", m => `<ol class="small"><li>Open <b>router.asus.com</b> → <b>Advanced Settings</b> → <b>Network Tools</b> → <b>Wake on LAN</b>.</li>
    <li>Enter the MAC <span class="mono">${m}</span> (or pick the computer from the list and press <b>+</b>), then <b>Wake up</b>.</li></ol>
    <p class="small muted">Away from home: the <b>ASUS Router</b> app (Android/iPhone) has <b>WOL</b> too, when remote access is on in the app.</p>`],
  ["tplink", "TP-Link (Deco, Archer)", m => `<ol class="small"><li><b>Deco app</b>: More → Advanced → <b>WOL</b> → Add WOL Device. <b>Tether app</b> (Archer routers): More → Advanced Settings → <b>WOL</b> → Add WOL Device.</li>
    <li>Pick this computer (MAC <span class="mono">${m}</span>) while it's on, then tap the alarm icon to wake it.</li></ol>
    <p class="small muted">Only on models with recent firmware - if you don't see WOL, update the firmware in the app or use the wake helper.</p>`],
  ["unifi", "Ubiquiti (UniFi, EdgeRouter)", m => `<p class="small">UniFi gateways and EdgeRouters have no Wake-on-LAN button, and a wake-up signal doesn't travel through the UniFi VPN (Teleport / WireGuard) either. Use the <b>wake helper</b> below on any device that's always on - it works with every UniFi setup, needs no port forwarding and adds <b>/start</b> in Discord.</p>
    <p class="small muted">At home, any Wake-on-LAN phone app on your Wi-Fi works too (MAC <span class="mono">${m}</span>). Wired and wireless clients must be in the same network (VLAN) as this computer.</p>`],
  ["mikrotik", "MikroTik", m => `<p class="small">WinBox / WebFig: <b>Tools → WoL</b> → MAC <span class="mono">${m}</span>, interface <b>bridge</b> → Wake. In the terminal:</p>
    <pre class="mono small" style="white-space:pre-wrap">/tool/wol mac=${m.toUpperCase()} interface=bridge</pre><p class="small muted">From outside, connect with the MikroTik app or your VPN first.</p>`],
  ["openwrt", "OpenWrt / GL.iNet", m => `<ol class="small"><li>LuCI → <b>System → Software</b> → install <b>luci-app-wol</b> (GL.iNet: open LuCI from Advanced first).</li>
    <li><b>Services → Wake on LAN</b> → interface <b>br-lan</b>, host MAC <span class="mono">${m}</span> → Wake up.</li></ol>`],
  ["netgear", "Netgear (Nighthawk, Orbi)", m => `<p class="small">Netgear's own firmware has no Wake-on-LAN button. Use the <b>wake helper</b> below, or a Wake-on-LAN phone app while you're on the home Wi-Fi (MAC <span class="mono">${m}</span>).</p>`],
  ["other", "Something else / don't know", m => `<p class="small">Look for <b>Wake on LAN</b> or <b>WOL</b> in your router's web page or app (often under Tools, Advanced or the device list). Many provider routers, Google/Nest Wifi, eero and Linksys don't have it - then use the <b>wake helper</b> below. At home, any Wake-on-LAN app on your phone works with the MAC <span class="mono">${m}</span>.</p>`],
];
async function cacheWake() {   // lets the "server is asleep" page offer a Wake button (needs HTTPS)
  if (!("caches" in window) || !window.isSecureContext) return;
  try { const d = await api("/api/power/offline"); const c = await caches.open("es-shell-v2"); if (d.topic) await c.put("/__wake.json", new Response(JSON.stringify(d))); else await c.delete("/__wake.json"); } catch (e) {}
}
async function loadPower(refresh) {
  const el = $("#powercard"); if (!el) return;
  let p; try { p = await api("/api/power" + (refresh ? "?refresh=1" : "")); } catch (e) { el.innerHTML = `<h2>Sleep &amp; wake-up</h2><p class="small muted">${esc(e.message)}</p>`; return; }
  cacheWake();
  const S = p.settings, wired = p.adapters.filter(a => !a.wifi), main = p.adapters.find(a => a.name === p.main);
  const wolOk = main && main.wol === "on";
  const WB = { on: ["good", "On"], off: ["warn", "Off"], unsupported: ["bad", "Not supported"], wifi: ["", "Wi-Fi - can't wake"], unknown: ["", "Unknown"], "no-ethtool": ["warn", "Off?"] };
  const mins = [15, 30, 45, 60, 120, 240, 480];
  if (!mins.includes(S.sleep_idle)) mins.push(S.sleep_idle);
  const status = !S.sleep_on ? "" : p.busy ? `Staying awake: ${esc(p.busy)}.` : !p.in_window ? "Outside the sleep hours - staying awake." : p.sleeps_at ? `Nobody's around - goes to sleep in about ${esc(fmtDur(p.sleeps_at - Date.now() / 1000))}.` : "";
  const m = esc(p.mac || "aa:bb:cc:dd:ee:ff");
  el.innerHTML = `<h2>Sleep &amp; wake-up <span class="badge ${S.sleep_on ? "good" : ""}">${S.sleep_on ? "Auto-sleep on" : "Auto-sleep off"}</span></h2>
    <p class="small muted">Don't run the computer 24/7: it can go to sleep when nobody plays and wake up again when someone wants to play - from your router, your phone, Discord, or by itself before an event. Sleeping uses about as little power as switched off.</p>
    ${p.error ? `<div class="issue warning"><span class="ic">⚠</span><span>${esc(p.error)}</span></div>` : ""}
    <h3 style="margin:14px 0 4px">1. Wake-on-LAN ${wolOk ? `<span class="badge good">Ready</span>` : `<span class="badge warn">Not ready</span>`}</h3>
    <p class="small muted">Lets another device wake this computer with a "magic packet". Needs a <b>network cable</b> - it doesn't work over Wi-Fi - and laptops must stay plugged in.</p>
    ${(() => { const W = p.wol_score; if (!W) return ""; const col = W.blocking ? "var(--crit-ink)" : W.score >= 90 ? "var(--good-ink)" : "var(--warn-ink)";
      const ic = { pass: ["✓", "var(--good-ink)"], warn: ["!", "var(--warn-ink)"], fail: ["✕", "var(--crit-ink)"], unknown: ["?", "var(--text-2)"] };
      const order = { fail: 0, warn: 1, unknown: 2, pass: 3 };
      return `<div class="card tight" style="padding:12px 14px;margin:8px 0"><div class="row" style="gap:14px;align-items:center">
        <div style="font-size:30px;font-weight:700;color:${col};min-width:64px">${W.score}<span class="small muted" style="font-weight:400">/100</span></div>
        <div><b>Compatibility: ${esc(W.verdict)}</b><div class="small muted">${W.blocking ? W.blocking + " thing" + (W.blocking > 1 ? "s" : "") + " must be changed before it can wake up." : "Nothing is blocking it."}</div></div></div>
        <div style="margin-top:8px">${W.checks.slice().sort((x, y) => order[x.state] - order[y.state]).map(c => `<div class="row small" style="align-items:flex-start;gap:8px;padding:4px 0;border-top:1px solid var(--line)">
          <b style="color:${ic[c.state][1]};width:14px;flex:none;text-align:center">${ic[c.state][0]}</b>
          <div style="flex:1"><b>${esc(c.title)}</b> - ${esc(c.why)}${c.fix && c.state !== "pass" ? `<div style="margin-top:2px"><b>What to change:</b> ${esc(c.fix)}</div>` : ""}</div></div>`).join("")}</div></div>`; })()}
    ${p.on_wifi ? `<div class="issue warning"><span class="ic">⚠</span><span>This computer is on <b>Wi-Fi</b>. Connect it to the router with a network cable, then press Refresh.</span></div>` : ""}
    ${!wired.length ? `<div class="issue warning"><span class="ic">⚠</span><span>No network cable adapter found. Wake-on-LAN needs one (a USB network adapter usually can't wake a computer).</span></div>` : ""}
    <div style="margin:6px 0">${p.adapters.map(a => `<div class="row small" style="padding:4px 0;gap:8px;flex-wrap:wrap"><b>${esc(a.name)}</b>${a.desc ? `<span class="muted">${esc(a.desc)}</span>` : ""}<span class="mono">${esc(a.mac)}</span>${a.ip ? `<span class="mono">${blurIPs(esc(a.ip))}</span>` : ""}<span class="muted">${a.wifi ? "Wi-Fi" : a.cable ? "cable plugged in" : "no cable"}</span><span class="badge ${(WB[a.wol] || WB.unknown)[0]}">${(WB[a.wol] || WB.unknown)[1]}</span><span class="spacer"></span>${!a.wifi && a.wol !== "on" && a.wol !== "unsupported" ? `<button class="btn sm" data-wol="${esc(a.name)}">Turn on</button>` : ""}</div>`).join("") || `<p class="small muted">No network adapters found.</p>`}</div>
    <details style="margin:6px 0"><summary class="small"><b>It still doesn't wake up? Check the BIOS</b></summary><div class="small">
      <p>Wake-on-LAN must also be allowed in the computer's BIOS/UEFI setup (press F2, F10, F12 or Del while it starts). Look for:</p><ul>
      <li><b>Wake on LAN</b>, <b>Power On By PCI-E</b>, <b>Resume by LAN</b> or <b>PME Event Wake Up</b> → Enabled</li>
      <li><b>ErP</b> / <b>EuP</b> / <b>Deep Sleep</b> → Disabled (they cut power to the network chip)</li>
      <li>HP: <b>Built-In Device Options → Wake on LAN</b>. Dell: <b>Power Management → Wake on LAN</b>. Lenovo ThinkPad: <b>Config → Network → Wake On LAN</b> (AC only).</li></ul>
      <p>Test it: press <b>Sleep now</b>, wait a minute, then wake it from your router or phone. The network light on the computer should stay on while it sleeps.</p></div></details>

    <h3 style="margin:16px 0 4px">2. Auto-sleep</h3>
    ${!p.can_sleep ? `<div class="issue warning"><span class="ic">⚠</span><span>This computer can't go to sleep (no sleep support found).</span></div>` : ""}
    <label class="toggle"><input type="checkbox" id="pw_on" ${S.sleep_on ? "checked" : ""}><span><b>Go to sleep when nobody plays</b><small>Off by default. Never while someone is online, an event runs or starts soon, or the dashboard is in use</small></span></label>
    <div class="grid g2" style="gap:0 12px;margin-top:8px">
      <label class="f"><span>After nobody played for</span><select id="pw_idle">${mins.sort((a, b) => a - b).map(v => `<option value="${v}" ${v === S.sleep_idle ? "selected" : ""}>${v < 60 ? v + " minutes" : v / 60 + (v === 60 ? " hour" : " hours")}</option>`).join("")}</select></label>
      <label class="f"><span>Only between (optional)</span><span class="row" style="gap:6px"><input type="time" id="pw_from" value="${esc(S.sleep_from)}" style="max-width:130px;color-scheme:light dark;color:inherit"> and <input type="time" id="pw_to" value="${esc(S.sleep_to)}" style="max-width:130px;color-scheme:light dark;color:inherit"></span><small>For example 01:00 and 15:00. Empty = any time</small></label>
      <label class="f"><span>Wake up by itself every day at (optional)</span><input type="time" id="pw_wake" value="${esc(S.sleep_wake_at)}" style="max-width:160px;color-scheme:light dark;color:inherit"><small>${p.rtc ? "Uses the computer's built-in alarm clock - no other device needed" : "This computer has no wake-up alarm, so this may not work"}</small></label>
      <label class="toggle" style="align-self:center"><input type="checkbox" id="pw_ev" ${S.sleep_wake_events ? "checked" : ""}><span><b>Wake up before events</b><small>10 minutes before every scheduled event (Config → Events)</small></span></label>
    </div>
    ${status ? `<p class="small" style="margin:4px 0">${status}</p>` : ""}
    ${p.next_wake ? `<p class="small muted" style="margin:4px 0">Next wake-up by itself: ${esc(fmtTime(p.next_wake))}.</p>` : ""}
    ${p.woke_at ? `<p class="small muted" style="margin:4px 0">Last woke up: ${esc(ago(p.woke_at))}.</p>` : ""}
    <div class="row"><button class="btn primary" id="pw_save">Save</button><button class="btn" id="pw_sleep" ${p.can_sleep ? "" : "disabled"}>Sleep now</button><button class="btn" id="pw_ref">Refresh</button></div>

    <h3 style="margin:16px 0 4px">3. How to wake it up</h3>
    <p class="small muted">The address to wake: MAC <span class="mono">${m}</span>${p.brd && p.brd.length ? `, network <span class="mono">${blurIPs(esc(p.brd[0]))}</span>` : ""}. Pick what you have:</p>
    <label class="f"><span>Your router</span><select id="pw_router" style="max-width:320px"><option value="">- pick your router -</option>${ROUTERS.map(r => `<option value="${r[0]}">${esc(r[1])}</option>`).join("")}</select></label>
    <div id="pw_rguide"></div>
    <div class="card tight" style="padding:12px 14px;margin-top:10px"><b>Wake helper</b> ${p.helper.paired ? (p.helper.last_seen ? `<span class="badge good">Answered ${esc(ago(p.helper.last_seen))}</span>` : `<span class="badge warn">Set up - not tested yet</span>`) : `<span class="badge">Not set up</span>`}
      <p class="small muted" style="margin:4px 0">A tiny program for any device at home that's always on - a Raspberry Pi, a NAS, another PC. While this computer sleeps it answers <b>/start</b> in Discord${p.helper.bot ? "" : " (needs the Discord bot)"} and the <b>Wake up</b> button in the phone app or on this page - from anywhere, without port forwarding. It can only send wake-up signals; it gets no access to this computer.</p>
      ${p.helper.paired ? `<div id="pw_code"></div>
        <details style="margin:6px 0"><summary class="small"><b>Install it</b></summary><div class="small">
        <p><b>Raspberry Pi / Linux</b> - in a terminal on that device:</p>
        <pre class="mono small" style="white-space:pre-wrap;word-break:break-all">curl -fsSLO https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/main/wake/install-wake-helper.sh
sudo bash install-wake-helper.sh</pre>
        <p><b>Windows</b> - download <b>BeamMP-EasyServer-WakeHelper.zip</b> from the <a href="https://github.com/Csabika-dev/beammp-easyserver/releases/latest" target="_blank" rel="noopener noreferrer">latest release</a>, unzip it and double-click <b>Install-Wake-Helper.bat</b>.</p>
        <p>Paste the pairing code when it asks. For <b>/start</b> in Discord it also asks for your bot token (Developer Portal → Bot → Reset Token - then paste the new token here in Settings → Discord bot too). The device must stay on and be in your home network, ideally with a cable.</p></div></details>
        <div class="row"><button class="btn" id="pw_show">Show pairing code</button><button class="btn" id="pw_test">Test the helper</button><button class="btn" id="pw_new">New code</button><button class="btn danger" id="pw_forget">Remove</button></div>`
      : `<button class="btn" id="pw_pair" ${p.mac ? "" : "disabled"}>Set up a wake helper</button>`}
    </div>
    <p class="small muted" style="margin-top:10px"><b>Phone:</b> the Android app shows a <b>Wake up</b> button when the server doesn't answer - scan the QR code under Phone app again after setting up the helper. At home it wakes the computer even without the helper. The home-screen app on iPhone shows the same button (with the helper).</p>`;
  const save = async quiet => { await api("/api/power", { json: { sleep_on: $("#pw_on").checked, sleep_idle: +$("#pw_idle").value, sleep_from: $("#pw_from").value, sleep_to: $("#pw_to").value, sleep_wake_at: $("#pw_wake").value, sleep_wake_events: $("#pw_ev").checked } }); if (!quiet) toast("Saved"); };
  $("#pw_save").onclick = async () => { try { await save(); loadPower(); } catch (e) { toast(e.message, 6000); } };
  $("#pw_ref").onclick = () => { el.querySelector("h2").insertAdjacentHTML("beforeend", ` <span class="small muted">checking…</span>`); loadPower(true); };
  $("#pw_sleep").onclick = async () => {
    if (await sleepComputer(wolOk ? "" : "Wake-on-LAN isn't ready yet - you may have to press the power button to wake it up.")) el.innerHTML = `<h2>Sleep &amp; wake-up</h2><p>💤 Going to sleep in a few seconds…</p>`;
  };
  el.querySelectorAll("[data-wol]").forEach(b => b.onclick = async () => { b.disabled = true; b.textContent = "Working…"; try { const r = await api("/api/power/wol", { json: { adapter: b.dataset.wol } }); toast(r.msg, 7000); loadPower(true); } catch (e) { toast(e.message, 8000); b.disabled = false; b.textContent = "Turn on"; } });
  $("#pw_router").onchange = () => { const r = ROUTERS.find(x => x[0] === $("#pw_router").value); $("#pw_rguide").innerHTML = r ? `<div class="card tight" style="padding:10px 14px">${r[2](m)}</div>` : ""; store.set("es-router", $("#pw_router").value); };
  if (store.get("es-router", "")) { $("#pw_router").value = store.get("es-router", ""); $("#pw_router").onchange(); }
  const showCode = async neu => { try { const r = await api("/api/power/helper", { json: { action: "pair", new: !!neu } }); if (!$("#pw_code")) return loadPower();
    $("#pw_code").innerHTML = `<label class="f"><span>Pairing code</span><textarea readonly rows="3" class="mono" style="min-height:70px;word-break:break-all">${esc(r.code)}</textarea><small>Treat it like a password: anyone with it can wake this computer. "New code" makes the old one stop working.</small></label><button class="btn sm" id="pw_copy">Copy</button>`;
    $("#pw_copy").onclick = () => navigator.clipboard && navigator.clipboard.writeText(r.code).then(() => toast("Copied")); } catch (e) { toast(e.message, 6000); } };
  if ($("#pw_pair")) $("#pw_pair").onclick = async () => { try { await api("/api/power/helper", { json: { action: "pair" } }); } catch (e) { return toast(e.message, 6000); } await loadPower(); showCode(false); };
  if ($("#pw_show")) $("#pw_show").onclick = () => showCode(false);
  if ($("#pw_new")) $("#pw_new").onclick = () => { if (confirm("Make a new pairing code? The helper (and phones) set up with the old one stop working until you set them up again.")) showCode(true); };
  if ($("#pw_forget")) $("#pw_forget").onclick = async () => { if (!confirm("Remove the wake helper? It stops answering right away.")) return; try { await api("/api/power/helper", { json: { action: "forget" } }); loadPower(); } catch (e) { toast(e.message); } };
  if ($("#pw_test")) $("#pw_test").onclick = async () => { const b = $("#pw_test"); b.disabled = true; b.textContent = "Asking…"; try { const r = await api("/api/power/helper", { json: { action: "test" } }); toast(r.found ? "The helper answered (version " + r.version + ") - it's ready." : "No answer. Is the helper running and connected to the internet?", 7000); if (r.found) loadPower(); } catch (e) { toast(e.message, 6000); } b.disabled = false; b.textContent = "Test the helper"; };
}

/* ---------------- Discord bot (Settings) */
async function loadBot(keepOpen) {
  const el = $("#botcard"); if (!el) return;
  let b; try { b = await api("/api/discordbot"); } catch (e) { el.innerHTML = `<h2>Discord bot</h2><p class="small muted">${esc(e.message)}</p>`; return; }
  const pill = !b.enabled ? `<span class="badge">Off</span>` : !b.has_token ? `<span class="badge warn">No token yet</span>` : b.state === "online" ? `<span class="badge good">Online${b.bot_name ? " as " + esc(b.bot_name) : ""}</span>`
    : b.state === "error" ? `<span class="badge bad">Problem</span>` : `<span class="badge warn">Connecting…</span>`;
  const g = b.guilds.find(x => x.id === b.guild);
  el.innerHTML = `<h2>Discord bot ${pill}</h2>
    <p class="small muted">Control your servers from Discord with slash commands. Anyone in your Discord can use <b>/status</b> (players, map, CPU, memory), <b>/top</b> (who played most) and <b>/events</b>. <b>/start</b>, <b>/stop</b>, <b>/restart</b> and <b>/whitelist</b> (add, remove, list, on, off) only work for people with <b>Manage Server</b> in your Discord, or the people you list below. A server has to be started from the dashboard once (to check its settings) before Discord can start it.</p>
    ${b.error && b.enabled ? `<div class="issue error"><span class="ic">✕</span><span>${esc(b.error)}</span></div>` : ""}
    <details style="margin:8px 0" ${b.has_token && !keepOpen ? "" : "open"}><summary class="small"><b>How to set it up (5 minutes)</b></summary><ol class="small">
      <li>Open <a href="https://discord.com/developers/applications" target="_blank" rel="noopener noreferrer">discord.com/developers/applications</a> → <b>New Application</b> → give it a name (for example "BeamMP server").</li>
      <li>Open <b>Bot</b> on the left → <b>Reset Token</b> → <b>Copy</b>. On the same page turn <b>Public Bot</b> off, so only you can add it to a Discord server.</li>
      <li>Paste the token below, turn the bot on and press Save.</li>
      <li>When it says <b>Online</b>, click <b>Add the bot to your Discord</b> and pick your Discord server.</li>
      <li>Type <b>/status</b> in any channel. (New commands can take a minute to show up - restart Discord if they don't.)</li></ol></details>
    <label class="toggle"><input type="checkbox" id="bot_on" ${b.enabled ? "checked" : ""}><span><b>Turn on the Discord bot</b><small>Off by default. The bot connects out to Discord - no port forwarding needed</small></span></label>
    <label class="f" style="margin-top:10px"><span>Bot token</span><input type="password" id="bot_token" placeholder="${b.has_token ? "Saved (encrypted) - paste a new one to replace" : "Paste the bot token"}" autocomplete="off" spellcheck="false"><small>Keep it secret - anyone with the token can control the bot. Stored encrypted.</small></label>
    ${b.invite ? `<p><a class="btn sm" href="${esc(b.invite)}" target="_blank" rel="noopener noreferrer">Add the bot to your Discord</a></p>` : ""}
    ${b.guilds.length ? `<label class="f"><span>Discord server the bot answers in</span><select id="bot_guild"><option value="">- pick one -</option>${b.guilds.map(x => `<option value="${esc(x.id)}" ${x.id === b.guild ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select><small>Commands only appear and only work there. If someone else adds your bot to another Discord, it ignores them.</small></label>`
      : b.enabled && b.state === "online" ? `<p class="small muted">The bot isn't in any Discord server yet - use the button above.</p>` : ""}
    ${b.guild && !g && b.guilds.length ? `<p class="small" style="color:var(--warn-ink)">The bot is no longer in the Discord server it was set up for - pick another one.</p>` : ""}
    <label class="f"><span>Also allow these people to start/stop (optional)</span><textarea id="bot_users" rows="2" spellcheck="false" placeholder="123456789012345678" style="min-height:60px">${esc(b.users.join("\n"))}</textarea><small>Discord user IDs, one per line. In Discord: Settings → Advanced → Developer Mode, then right-click a person → Copy User ID. People with Manage Server can always use the commands.</small></label>
    <h3 style="margin:16px 0 4px">In your Discord channel</h3>
    <p class="small muted">These use the channel of your Discord webhook (Settings → Notifications).${b.has_webhook ? "" : " <b>Add the webhook first.</b>"}</p>
    <label class="toggle"><input type="checkbox" id="bot_status" ${b.status_msg ? "checked" : ""}><span><b>Live status message</b><small>One message that shows every server, its players, CPU and memory and the next events - updated every minute. Pin it in the channel. Works without the bot</small></span></label>
    <label class="toggle"><input type="checkbox" id="bot_bridge" ${b.bridge ? "checked" : ""}><span><b>Chat bridge</b><small>The game chat shows up in the channel, and messages written there appear in the game as [Discord] name: text. Needs the bot, and MESSAGE CONTENT INTENT turned on (Developer Portal → Bot). Commands, muted players and filtered words are never sent</small></span></label>
    ${b.servers.length > 1 ? `<label class="f"><span>Bridge which server</span><select id="bot_bserver" style="max-width:260px">${b.servers.map(x => `<option value="${esc(x.id)}" ${x.id === b.bridge_server ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></label>` : ""}
    <div class="row"><button class="btn primary" id="bot_save">Save</button><button class="btn" id="bot_refresh">Refresh</button></div>`;
  $("#bot_refresh").onclick = () => loadBot(true);
  $("#bot_save").onclick = async () => {
    const body = { enabled: $("#bot_on").checked, users: $("#bot_users").value, status_msg: $("#bot_status").checked, bridge: $("#bot_bridge").checked };
    if ($("#bot_bserver")) body.bridge_server = $("#bot_bserver").value;
    const t = $("#bot_token").value.trim(); if (t) body.token = t;
    const gs = $("#bot_guild"); if (gs) body.guild = gs.value;
    try { await api("/api/discordbot", { json: body }); toast(body.enabled ? "Saved - connecting to Discord…" : "Saved"); setTimeout(() => loadBot(true), body.enabled ? 4000 : 0); }
    catch (e) { toast(e.message, 6000); }
  };
}

/* ---------------- settings */
VIEWS.settings = async m => {
  const s = await api("/api/settings");
  const tg = (id, label, help, on) => `<label class="toggle"><input type="checkbox" id="${id}" ${on ? "checked" : ""}><span><b>${esc(label)}</b><small>${esc(help)}</small></span></label>`;
  const N = s.notify;
  m.innerHTML = `<h1>Settings</h1><p class="sub">Notifications, security, remote access and backups.</p>
  <div class="card" id="supbox" style="margin-bottom:16px"></div>
  <div class="grid g2">
    <div class="card"><h2>Security alerts</h2>
      ${tg("security_alerts", "Alert me about attacks", "Password guessing, websites probing the dashboard, mods with viruses, tampered server files, zip bombs, connection floods. Sent to every channel that is set up (here, Discord, email) - even if its switch below is off", s.security_alerts)}
      ${tg("security_reminders", "Repeat every 15 minutes", "Until you click \"Got it - stop alerts\" (or the link/pop-up in the message)", s.security_reminders)}
      <div class="row" style="margin-top:8px"><button class="btn sm" id="popups">Show pop-ups on this device</button><span class="small muted" id="popupnote"></span></div>
    </div>
    <div class="card"><h2>Notify me about</h2>
      ${tg("n_crash", "Crashes", "The server crashed or keeps crashing", N.crash)}
      ${tg("n_stopped", "Unexpected stops", "The server stopped without you stopping it", N.stopped)}
      ${tg("n_update", "Updates", "New BeamMP or EasyServer versions", N.update)}
      ${tg("n_mod_blocked", "Blocked mods", "A mod failed the virus check", N.mod_blocked)}
      ${tg("n_player_join", "Player joins", "Every time someone joins (can be a lot)", N.player_join)}
      ${tg("n_player_denied", "Refused players", "Someone not on the allow-list tried to join", N.player_denied)}
      ${tg("n_moderation", "Moderation", "Bans, kicks and mutes made in game by your admins", N.moderation)}
      ${tg("n_report", "Player reports", "A player used /report in the game - with the chat just before it", N.report !== false)}
      ${tg("n_network", "Address changes", "This computer's home address or your public IP changed", N.network)}
      ${tg("n_restart", "Scheduled restarts", "A scheduled restart or update ran", N.restart)}
      ${tg("n_rotation", "Map rotation", "The map was changed by the rotation", N.rotation)}
      ${tg("n_resources", "Computer overloaded", "Out of memory, processor maxed out, or upload almost used up", N.resources)}
      ${tg("n_backup", "Backup problems", "A nightly backup failed", N.backup)}
      ${tg("n_mod_update", "Mod updates", "A newer version of a repository mod is out", N.mod_update)}
      ${tg("n_sleep", "Sleep and wake-up", "The server computer went to sleep or woke up", N.sleep)}
      ${s.platform === "windows" ? tg("auto_restart", "Restart after a crash", "Start the server again automatically", s.auto_restart) : ""}
      ${tg("update_check", "Check for updates", "Every 6 hours", s.update_check)}
      <p class="small muted" style="margin-top:12px">Notifications always appear on the Notifications page. Also send them to:</p>
    </div>
    <div class="grid" style="align-content:start">
      <div class="card"><h2>Discord</h2>${tg("discord_enabled", "Send to Discord", "Posts to a channel via a webhook", s.discord_enabled)}
        <label class="f" style="margin-top:10px"><span>Webhook URL</span><input type="password" id="webhook" placeholder="${s.has_discord ? "Saved (encrypted) - paste a new one to replace" : "https://discord.com/api/webhooks/…"}" autocomplete="off"><small>Discord channel → Edit channel → Integrations → Webhooks → New webhook → Copy URL</small></label>
        <button class="btn sm" data-test="discord">Send test</button></div>
      <div class="card"><h2>Email</h2>${tg("email_enabled", "Send emails", "Uses your email provider's SMTP server", s.email_enabled)}
        <div class="grid g2" style="margin-top:10px;gap:0 12px">
          <label class="f"><span>SMTP server</span><input type="text" id="smtp_host" value="${esc(s.smtp_host)}" placeholder="smtp.gmail.com"></label>
          <label class="f"><span>Port</span><input type="number" id="smtp_port" value="${esc(s.smtp_port)}"></label>
          <label class="f"><span>Username</span><input type="text" id="smtp_user" value="${esc(s.smtp_user)}" autocomplete="off"></label>
          <label class="f"><span>Password</span><input type="password" id="smtp_password" placeholder="${s.has_smtp_password ? "Saved (encrypted)" : "App password"}" autocomplete="new-password"></label>
          <label class="f"><span>Security</span><select id="smtp_security"><option value="starttls">STARTTLS (port 587)</option><option value="ssl">SSL (port 465)</option><option value="none">None</option></select></label>
          <label class="f"><span>Send to</span><input type="email" id="smtp_to" value="${esc(s.smtp_to)}" placeholder="you@example.com"></label>
        </div>
        <small class="muted">Gmail/Outlook: create an "app password" in your account security settings.</small>
        <div class="row" style="margin-top:10px"><button class="btn sm" data-test="email">Send test</button></div></div>
    </div>
  </div>
  <div class="row" style="margin:16px 0 30px"><button class="btn primary" id="savenotif">Save notification settings</button></div>

  <div class="card" style="margin:0 0 16px" id="phonecard"><h2>Phone app</h2><p class="muted small">Loading…</p></div>
  <div class="card" style="margin:0 0 16px" id="botcard"><h2>Discord bot</h2><p class="muted small">Loading…</p></div>
  <div class="card" style="margin:0 0 16px" id="integcard"><h2>Telegram, Slack &amp; other apps</h2><p class="muted small">Loading…</p></div>
  ${SESSION.role === "owner" || !SESSION.role ? `<div class="card" style="margin:0 0 16px" id="statuscard"><h2>Public status page</h2><p class="muted small">Loading…</p></div>` : ""}
  <div class="card" style="margin:0 0 16px" id="powercard"><h2>Sleep &amp; wake-up</h2><p class="muted small">Loading…</p></div>
  ${SESSION.role === "owner" ? `<div class="card" style="margin:0 0 16px" id="userscard"><h2>Users &amp; roles</h2><p class="muted small">Loading…</p></div>` : ""}

  <div class="grid g2">
    <div class="card"><h2>Mod virus check</h2><p class="small muted">Optional VirusTotal key (free account at virustotal.com → your name → API key). Stored encrypted.</p>
      <div class="row"><input type="password" id="vt" placeholder="${s.has_vt ? "Saved - paste a new key or type off" : "VirusTotal API key"}" autocomplete="off"><button class="btn" id="savevt">Save</button></div></div>
    <div class="card"><h2>Password</h2>
      <label class="f"><span>Current password</span><input type="password" id="pw_cur" autocomplete="current-password"></label>
      <label class="f"><span>New password</span><input type="password" id="pw_new" autocomplete="new-password"><small>${s.remote_enabled ? "At least 12 characters" : "At least 8 characters (12 for internet access)"}</small></label>
      <button class="btn" id="savepw">Change password</button></div>
  </div>

  <div class="card" style="margin-top:16px" id="devcard"><h2>Remembered devices</h2><p class="muted small">Loading…</p></div>

  <div class="card" style="margin-top:16px"><h2>Two-step login</h2>
    <p class="small muted">Ask for a 6-digit code from an app like Google Authenticator, Microsoft Authenticator or Aegis on every login. Required for access from the internet.</p>
    <div id="twofa">${s.totp ? `<span class="pill good"><span class="dot"></span>On</span> <button class="btn sm danger" id="tfaoff" style="margin-left:8px">Turn off</button>` : `<button class="btn" id="tfaon">Set up two-step login</button>`}</div></div>

  <div class="card" style="margin-top:16px"><h2>Access from the internet</h2>
    <p class="small muted">Manage the server from anywhere: needs HTTPS, two-step login and a 12+ character password. You also have to forward port ${esc(s.port)} (TCP) on your router. Leave this off if you only use the dashboard at home.</p>
    ${tg("https", "HTTPS (encrypted connection)", "Uses a self-made certificate - your browser shows a warning the first time; check the fingerprint below and continue", s.https)}
    ${tg("remote_enabled", "Allow access from the internet", "Only with HTTPS + two-step login", s.remote_enabled)}
    ${s.cert_fingerprint ? `<p class="small">Certificate fingerprint (SHA-256): <span class="mono">${esc(s.cert_fingerprint)}</span></p>` : ""}
    <button class="btn" id="saveremote">Apply</button></div>

  <div class="card" style="margin-top:16px" id="relaycard"><h2>Hide your IP (DDoS protection) <span class="badge ${s.relay_enabled ? "good" : ""}">${s.relay_enabled ? "On" : "Off"}</span></h2>
    <p class="small muted">Normally players connect straight to your home internet address. Everyone who plays on your server can see it, and someone could use it to flood (DDoS) your connection so your whole home loses internet. With this on, players join through a relay instead.</p>
    <div class="grid g2" style="margin:10px 0">
      <div class="card tight" style="padding:10px 14px"><b style="color:var(--good-ink)">✓ Much less chance of DDoS</b><div class="small muted">Your home address stays hidden. Attacks hit the relay, which is built to take them - not your home.</div></div>
      <div class="card tight" style="padding:10px 14px"><b style="color:var(--warn-ink)">✕ Higher latency (more lag)</b><div class="small muted">Every packet makes a detour through the relay: usually +10-40 ms with a relay in your country, more if it's far away. Pick one close to you and your players.</div></div>
    </div>
    ${tg("relay_enabled", "Hide my IP - players join through a relay", "Off by default. You need a relay first (see below)", s.relay_enabled)}
    <details style="margin:8px 0"><summary class="small"><b>How do I get a relay?</b></summary><ul class="small">
      <li><b>playit.gg</b> - easiest: install their app on this computer and make a tunnel to port ${esc((s.relay_servers[0] || {}).port || 30814)}. BeamMP needs TCP and UDP, which needs playit Premium.</li>
      <li><b>A VPN with port forwarding</b> (for example Proton VPN or PIA - many big VPNs don't offer it). The forwarded port can change when the VPN reconnects.</li>
      <li><b>Your own VPS</b> (about €4/month) with WireGuard - most work to set up, but you control it and the address never changes.</li>
      <li>Step-by-step: <a href="https://github.com/Csabika-dev/beammp-easyserver/blob/main/PROTECT-YOUR-IP.md" target="_blank" rel="noopener noreferrer">PROTECT-YOUR-IP guide</a></li></ul></details>
    <label class="f"><span>Relay address</span><input type="text" id="relay_host" value="${esc(s.relay_host || "")}" placeholder="e.g. your-name.playit.gg or 203.0.113.5" autocomplete="off" spellcheck="false"><small>The host name or IP address the relay gave you, without the port</small></label>
    ${s.relay_servers.map(r => `<label class="f"><span>Port on the relay${s.relay_servers.length > 1 ? " for " + esc(r.name) : ""}</span><input type="number" min="1" max="65535" data-rp="${esc(r.id)}" value="${esc(r.relay_port ?? "")}" placeholder="${esc(r.port ?? "")}" style="max-width:220px"><small>Leave empty if the relay uses the same port as the server (${esc(r.port ?? "?")})</small></label>`).join("")}
    <div class="small" style="margin:8px 0 12px"><b>When it's on:</b><ul style="margin:4px 0">
      <li>Remove the port forward for the game port from your router - otherwise your home address is still reachable.</li>
      <li>Make the server private (Config → Private server) and share the relay address. The public server list shows the address the server reports from, which is usually your home IP.</li>
      <li>If your home IP was already shared, restart your router - most providers then give you a new address.</li>
      ${s.remote_enabled ? `<li>"Access from the internet" is on, so the dashboard is still reachable at your home address.</li>` : ""}</ul></div>
    <div class="row"><button class="btn primary" id="saverelay">Save</button><button class="btn" id="testrelay">Test the relay</button></div>
    <div id="relayres"></div>
    <hr style="border:0;border-top:1px solid var(--line);margin:16px 0">
    ${s.platform === "linux" ? `${tg("flood_protect", "Flood protection", "Off by default. Limits how fast one address can connect to and send to your game server. Stops floods from single computers; it can't stop a big DDoS - only hiding your IP can. Your home network is never limited.", s.flood_protect)}<div class="small muted" id="floodst"></div>`
      : `<p class="small muted"><b>Flood protection</b> (per-address limits on the game port) is only available on Linux. On Windows, hiding your IP is the protection that matters.</p>`}
    <hr style="border:0;border-top:1px solid var(--line);margin:16px 0">
    ${tg("guard_on", "BeamMP-only guard", "Off by default. Port scanners and bots knock on any open port, get nothing and hang up. Real players stay connected. An address that keeps knocking (lots of short connections in 10 minutes) without ever staying to play is blocked by the firewall - for an hour, longer if it comes back. Your home network and anyone who has played here are never blocked.", s.guard_on)}
    <div id="guardbox" class="small"></div>
  </div>

  <div id="set17"></div>
  <div class="card" style="margin-top:16px"><h2>Backup / move to another computer</h2>
    <p class="small muted">Export your server settings (and optionally all mods) into one file, then import it on another server. Keys and passwords are never exported.</p>
    <div class="row"><a class="btn" href="/api/export?srv=${encodeURIComponent(SERVER)}" download>Export settings</a><a class="btn" href="/api/export?mods=1&srv=${encodeURIComponent(SERVER)}" download>Export settings + mods</a>
      <span class="spacer"></span><button class="btn" id="imp">Import…</button><input type="file" id="impfile" accept=".zip" hidden></div>
    <div id="impres"></div></div>
  <p class="small muted" style="margin-top:24px">BeamMP EasyServer ${esc(SESSION.version)} · ${esc(s.platform)} · not affiliated with the BeamMP team</p>`;
  $("#smtp_security").value = s.smtp_security;
  m.querySelectorAll("[data-test]").forEach(b => b.onclick = async () => { b.disabled = true; try { await saveNotif(true); await api("/api/notifications/test", { json: { channel: b.dataset.test } }); toast("Test sent"); } catch (e) { toast(e.message); } b.disabled = false; });
  async function saveNotif(quiet) {
    const body = { notify: {} };
    ["crash", "stopped", "update", "mod_blocked", "player_join", "player_denied", "moderation", "network", "restart", "rotation", "resources", "backup", "mod_update", "sleep", "report"].forEach(k => body.notify[k] = $("#n_" + k).checked);
    ["discord_enabled", "email_enabled", "update_check", "security_alerts", "security_reminders"].forEach(k => body[k] = $("#" + k).checked);
    if ($("#auto_restart")) body.auto_restart = $("#auto_restart").checked;
    ["smtp_host", "smtp_port", "smtp_user", "smtp_to", "smtp_security"].forEach(k => body[k] = $("#" + k).value);
    body.smtp_from = $("#smtp_user").value.includes("@") ? $("#smtp_user").value : $("#smtp_to").value;
    if ($("#webhook").value) body.discord_webhook = $("#webhook").value;
    if ($("#smtp_password").value) body.smtp_password = $("#smtp_password").value;
    await api("/api/settings", { json: body });
    $("#webhook").value = ""; $("#smtp_password").value = "";
    if (!quiet) toast("Saved");
  }
  $("#savenotif").onclick = () => saveNotif(false).catch(e => toast(e.message));
  loadBot();
  loadSupporter();
  loadPhone();
  loadPower();
  loadUsers();
  loadDevices();
  loadInteg();
  loadStatusPage();
  loadSet17();
  ["security_alerts", "security_reminders"].forEach(k => $("#" + k).onchange = () => saveNotif(false).catch(e => toast(e.message)));
  const popNote = () => { $("#popupnote").textContent = !window.Notification ? (window.isSecureContext ? "This browser has no pop-ups" : "Pop-ups need HTTPS (turn it on below) or http://localhost") : Notification.permission === "granted" ? "On for this browser" : Notification.permission === "denied" ? "Blocked - allow notifications for this site in the browser settings" : ""; };
  popNote();
  $("#popups").onclick = async () => { if (window.Notification) { await Notification.requestPermission(); popNote(); if (Notification.permission === "granted") new Notification("BeamMP dashboard", { body: "Security alerts will pop up here while the dashboard is open." }); } else popNote(); };
  $("#relay_host").onchange = () => {   // pasted "host:port"? split it
    const v = $("#relay_host").value.trim().replace(/^[a-z]+:\/\//i, "").replace(/\/.*$/, ""), m = v.match(/^([^:\s]+):(\d{1,5})$/);
    $("#relay_host").value = m ? m[1] : v;
    const first = document.querySelector("[data-rp]");
    if (m && first && !first.value) first.value = m[2];
  };
  const relayBody = () => { const ports = {}; document.querySelectorAll("[data-rp]").forEach(i => ports[i.dataset.rp] = i.value === "" ? null : Number(i.value)); return { relay_enabled: $("#relay_enabled").checked, relay_host: $("#relay_host").value.trim(), relay_ports: ports }; };
  $("#saverelay").onclick = async () => { try { await api("/api/settings", { json: relayBody() }); toast($("#relay_enabled").checked ? "Hide my IP is on - players now get the relay address" : "Saved"); show("settings"); } catch (e) { toast(e.message); } };
  $("#testrelay").onclick = async () => {
    const b = $("#testrelay"); b.disabled = true; b.textContent = "Testing…";
    try {
      const body = relayBody(); delete body.relay_enabled;
      await api("/api/settings", { json: body });
      const r = await api("/api/relay-check");
      $("#relayres").innerHTML = `<div class="card tight" style="margin-top:12px">${r.results.map(x => `<div class="check"><span class="mark ${x.ok ? "ok" : "bad"}">${x.ok ? "✓" : "✕"}</span><div><b>${esc(x.name)} - ${blurIPs(esc(x.address))}</b><div class="small muted">${x.ok ? "Reachable (about " + esc(x.ms) + " ms from here to the relay and back). UDP can't be tested from here - join once to be sure." : "Nothing answers. Is the relay running, and does it forward TCP and UDP to this computer?"}</div></div></div>`).join("") || `<p class="small muted">No servers to test.</p>`}</div>`;
    } catch (e) { toast(e.message); }
    b.disabled = false; b.textContent = "Test the relay";
  };
  const guardBox = async () => {
    const b = $("#guardbox"); if (!b) return;
    let g; try { g = await api("/api/guard"); } catch (e) { b.textContent = e.message; return; }
    const warn = g.on && !g.relay && !g.enforced ? `<div class="banner warn" style="margin:8px 0 0"><span class="small">${g.error ? esc(g.error) : g.platform === "windows" ? "The firewall task isn't running yet, so nothing is actually blocked. Run Update-BeamMP-Server.bat once (it sets it up)." : "The server helper didn't answer."}</span></div>` : "";
    if (g.mac) { b.innerHTML = `<p class="muted">Not available on a Mac yet: players reach the server through the Mac, so they all look like the same address.</p>`; if ($("#guard_on")) $("#guard_on").disabled = true; return; }
    b.innerHTML = (g.relay ? `<p class="muted">Not needed while "Hide my IP" is on.</p>` : !g.on ? "" :
      `<p class="muted" style="margin:6px 0 0">Watching. ${g.count ? `<b>${g.count}</b> blocked right now` : "Nobody blocked right now"} · ${g.total} blocked so far · ${g.players_known} addresses known as players.</p>${warn}
       ${g.blocked.length ? `<div style="margin-top:6px">${g.blocked.map(x => `<div class="check"><span class="mark bad">✕</span><div><b>${ipb(esc(x.ip))}</b> <span class="muted">until ${fmtTime(x.until)} - ${esc(x.why)}</span> <button class="btn sm" data-unblock="${esc(x.ip)}">Unblock</button></div></div>`).join("")}</div>
         <button class="btn sm" id="guard_all" style="margin-top:6px">Unblock everyone</button>` : ""}
       <div class="row" style="margin-top:8px"><input type="text" id="guard_ip" placeholder="A friend can't join? Paste their IP" style="max-width:260px"><button class="btn sm" id="guard_ok">Never block</button></div>`) ;
    const un = async body => { try { const r = await api("/api/guard", { json: body }); toast(r.note, 6000); } catch (e) { toast(e.message); } guardBox(); };
    b.querySelectorAll("[data-unblock]").forEach(x => x.onclick = () => un({ unblock: x.dataset.unblock }));
    if ($("#guard_all")) $("#guard_all").onclick = () => un({ unblock_all: true });
    if ($("#guard_ok")) $("#guard_ok").onclick = () => un({ unblock: $("#guard_ip").value.trim() });
  };
  if ($("#guard_on")) {
    $("#guard_on").onchange = async () => { try { await api("/api/settings", { json: { guard_on: $("#guard_on").checked } }); toast($("#guard_on").checked ? "BeamMP-only guard is on" : "BeamMP-only guard is off - nothing is blocked while it is off"); setTimeout(guardBox, 1200); } catch (e) { toast(e.message); $("#guard_on").checked = !$("#guard_on").checked; } };
    guardBox();
  }
  if ($("#flood_protect")) {
    const fst = async () => { try { const f = await api("/api/flood-status"); $("#floodst").textContent = f.active ? "Active - blocked " + f.dropped + " packets since it was turned on" : ($("#flood_protect").checked ? "Starting…" : ""); } catch (e) { } };
    $("#flood_protect").onchange = async () => { try { await api("/api/settings", { json: { flood_protect: $("#flood_protect").checked } }); toast($("#flood_protect").checked ? "Flood protection is on" : "Flood protection is off"); setTimeout(fst, 1500); } catch (e) { toast(e.message); $("#flood_protect").checked = !$("#flood_protect").checked; } };
    fst();
  }
  $("#savevt").onclick = async () => { const v = $("#vt").value.trim(); try { await api("/api/settings", { json: { vt_key: v === "off" ? "" : v } }); toast(v === "off" ? "VirusTotal turned off" : "Saved"); show("settings"); } catch (e) { toast(e.message); } };
  $("#savepw").onclick = async () => { try { await api("/api/password", { json: { current: $("#pw_cur").value, new: $("#pw_new").value } }); toast("Password changed - remembered devices have to log in again"); $("#pw_cur").value = $("#pw_new").value = ""; loadDevices(); } catch (e) { toast(e.message); } };
  const on = $("#tfaon");
  if (on) on.onclick = async () => {
    const r = await api("/api/2fa/begin", { method: "POST" });
    const n = Number(r.qr_size) || 0, qp = /^[MhvzZ0-9 -]*$/.test(r.qr_path || "") ? r.qr_path : "";
    const qr = n && qp ? `<div style="background:#fff;padding:12px;border-radius:8px;display:inline-block;margin:6px 0"><svg width="220" height="220" viewBox="-4 -4 ${n + 8} ${n + 8}" shape-rendering="crispEdges" role="img" aria-label="QR code for the two-step login key"><rect x="-4" y="-4" width="${n + 8}" height="${n + 8}" fill="#fff"/><path d="${qp}" fill="#000"/></svg></div>` : "";
    $("#twofa").innerHTML = `<p class="small">Scan this with your authenticator app (Google Authenticator, Microsoft Authenticator, Aegis...):</p>${qr}
      <p class="small muted">Can't scan? In the app choose <b>"Enter a setup key"</b>, account name <b>BeamMP</b>, and type this key:</p>
      <div class="secret">${esc(r.secret)}</div><p class="small muted">On a phone you can also <a href="${esc(r.uri)}">tap here</a> to add it directly. Clicking "Set up" again makes a new key - only the one shown here works.</p>
      <label class="f"><span>Enter the 6-digit code the app shows</span><input type="text" id="tfacode" inputmode="numeric" maxlength="7" style="max-width:180px"></label><button class="btn primary" id="tfaok">Turn on</button>`;
    $("#tfaok").onclick = async () => { try { await api("/api/2fa/confirm", { json: { code: $("#tfacode").value } }); toast("Two-step login is on"); show("settings"); } catch (e) { toast(e.message); } };
  };
  const off = $("#tfaoff");
  if (off) off.onclick = async () => { const p = prompt("Enter your password to turn off two-step login"); if (!p) return; try { await api("/api/2fa/disable", { json: { password: p } }); toast("Two-step login turned off"); show("settings"); } catch (e) { toast(e.message); } };
  $("#saveremote").onclick = async () => {
    const wantRemote = $("#remote_enabled").checked, wantHttps = $("#https").checked || wantRemote;
    const lines = [];
    if (wantRemote !== !!s.remote_enabled) lines.push(wantRemote
      ? "• Internet access ON: this computer's firewall opens port " + s.port + " (TCP) for the dashboard\n• Your router is NOT changed - forward port " + s.port + " there yourself"
      : "• Internet access OFF: this computer's firewall closes port " + s.port + " again");
    if (wantHttps !== !!s.https) lines.push("• The dashboard restarts on " + (wantHttps ? "https://" : "http://") + " - your browser reconnects by itself" + (wantHttps ? "\n• The first time, your browser warns about the self-made certificate" : ""));
    if (!lines.length) { toast("Nothing changed"); return; }
    if (!confirm("This changes your network settings:\n\n" + lines.join("\n") + "\n\nContinue?")) return;
    try {
      toast("Applying… (creating a certificate can take a few seconds)", 8000);
      const r = await api("/api/remote", { json: { https: $("#https").checked, remote_enabled: $("#remote_enabled").checked } });
      if (r.network) toast("🌐 " + r.network, 7000);
      if (r.restart) { setTimeout(() => toast("Restarting the dashboard - you'll be taken to the new address", 6000), r.network ? 1500 : 0); setTimeout(() => location.href = r.url.replace(/\/\/[^:/]+/, "//" + location.hostname), 4500); }
      else { toast("Saved"); show("settings"); }
    } catch (e) { toast(e.message); }
  };
  $("#imp").onclick = () => $("#impfile").click();
  $("#impfile").onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    if (!confirm("Import " + f.name + "? Your current server config will be replaced (mods in the file are added and virus-checked).")) return;
    $("#impres").innerHTML = `<p class="muted">Importing…</p>`;
    const r = await fetch("/api/import", { method: "PUT", headers: { "X-ES-CSRF": CSRF, "X-ES-Server": SERVER }, body: f });
    let j = {}; try { j = await r.json(); } catch (x) {}
    if (!r.ok) { $("#impres").innerHTML = `<div class="banner bad">${esc(j.error || "Import failed")}</div>` + ((j.issues || []).map(i => `<div class="issue ${i.level}"><span class="ic">!</span><span>${esc(i.message)}</span></div>`).join("")); return; }
    const rep = j.report;
    $("#impres").innerHTML = `<div class="banner info"><span>✓ Imported. ${rep.mods_added.length} mod(s) added${rep.mods_blocked.length ? ", " + rep.mods_blocked.length + " blocked by the virus check" : ""}. ${esc(j.note)}</span></div>`;
  };
};

/* ---- These used to draw the page. The React app (app.jsx) does that now; the page code above still
   calls them by these names, so they hand over to it. */
export const bridge = { show() {}, boot() {}, refreshShell() {}, switchServer() {}, setUnread() {}, checkSecurity: async () => {} };
function boot() { return bridge.boot(); }
function show(tab) { bridge.show(tab); }
function renderShell() { bridge.refreshShell(); }
function switchServer(id) { bridge.switchServer(id); }
function setUnread(n) { bridge.setUnread(n); }
function checkSecurity() { return bridge.checkSecurity(); }

/* ---- shared with the React app */
export const state = () => ({ CSRF, SESSION, TAB, SERVER, SERVERS, LANG, LANGS });
export function setSession(s) { SESSION = s; CSRF = s ? s.csrf : null; }
export function setTab(t) { TAB = t; }
export function setServer(id) { SERVER = id; store.set("es-server", id); }
export function setServers(xs) { SERVERS = xs; }
export function clearTimer() { clearInterval(TIMER); TIMER = null; }
export {
  $, esc, ipb, store, IN_APP, api, toast, copyText, modal, fmtSize, fmtDur, fmtTime, ago, applyTheme, I, LOGO_SVG, TABS,
  loadLangList, loadLang, pickLang, tr, approveFromLink, stopAlerts, sleepComputer, myRole, myTabs, reviewGate, serverAction,
  openInvite, openMyAccount, VIEWS, modBrowser,
};
