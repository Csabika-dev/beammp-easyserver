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
// Deleting something: it disappears at once and the toast offers "Undo" for a few seconds; only
// then is it really deleted. Closing the page sends it straight away (keepalive), so nothing is
// left half done. The request goes to the server that was open when you clicked.
const PENDING = new Set();
function undoable(msg, path, json, { onUndo, after, ms = 6000 } = {}) {
  const srv = SERVER, t = $("#toast");
  const job = { done: false };
  const finish = () => { job.done = true; PENDING.delete(job); clearTimeout(job.timer); };
  job.go = () => {
    if (job.done) return; finish();
    api(path, { json, keepalive: true, headers: { "X-ES-Server": srv } })
      .then(r => after && after(r), e => { toast(e.message, 7000); onUndo && onUndo(); });
  };
  t.textContent = msg + " ";
  const b = document.createElement("button");
  b.type = "button"; b.className = "undo"; b.textContent = "Undo";
  b.onclick = () => { if (job.done) return; finish(); t.classList.add("hidden"); onUndo && onUndo(); };
  t.appendChild(b); t.classList.remove("hidden"); clearTimeout(t._t); t._t = setTimeout(() => t.classList.add("hidden"), ms);
  job.timer = setTimeout(job.go, ms); PENDING.add(job);
  return job;
}
addEventListener("pagehide", () => PENDING.forEach(j => j.go()));
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
    api("/api/checklist", { json: { invited: true } }).catch(() => {});   // ticks "Invite your friends" off
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
  document.documentElement.dataset.look = store.get("es-look", "glass");   // "glass" or "classic"
}
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
applyTheme();

/* ------------------------------------------------------------------ icons */
const I = {
  games: '<path d="M5 3h2v18H5V3zm3 1h11.5l-2.6 4.5L19.5 13H8V4z"/>',
  search: '<path d="M10 4a6 6 0 1 0 3.7 10.7l4.8 4.8 1.4-1.4-4.8-4.8A6 6 0 0 0 10 4zm0 2a4 4 0 1 1 0 8 4 4 0 0 1 0-8z"/>',
  glass: '<path d="M12 3c-5 0-9 3.6-9 8.5 0 4 2.8 7.4 6.7 8.3.8.2 1.3-.5 1.1-1.2l-.4-1.4c-.2-.8.4-1.5 1.2-1.5h2.7c3.1 0 5.7-2.4 5.7-5.5C20 6.2 16.4 3 12 3zm-5 9a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm3-4a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm4 0a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm3 4a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z"/>',
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
const TABS = [["overview","Overview"],["servers","Servers"],["config","Config"],["mods","Mods"],["players","Players"],["games","Games"],["network","Health"],["updates","Updates"],["logs","Logs"],["notifications","Notifications"],["settings","Settings"]];

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

const ROLE_TABS = { viewer: ["overview", "players", "games", "network", "logs", "notifications"], moderator: ["overview", "players", "games", "network", "logs", "notifications"] };
const myRole = () => (SESSION.server_roles && SESSION.server_roles[SERVER]) || null;
const myTabs = () => {
  const r = myRole();
  if (r && r.perms) {                    // custom role: base tabs + what it may change
    const extra = { config: ["config"], mods: ["mods"], settings: ["settings", "updates", "servers"] };
    const keep = new Set(["overview", "players", "games", "network", "logs", "notifications"]);
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
// Start / stop / restart. A server that was moved to another computer asks first before it starts here too.
async function serverActionApi(action, headers) {
  try { return await api("/api/server/action", { json: { action }, headers }); }
  catch (e) {
    if (!(e.data && e.data.moved) || !confirm(e.message)) throw e;
    return api("/api/server/action", { json: { action, anyway: true }, headers });
  }
}
async function serverAction(action, btn) {
  if (action === "start" && !(await reviewGate())) return;
  if (action !== "start" && !confirm(action === "stop" ? "Stop the server? Players will be disconnected." : "Restart the server? Players will be disconnected.")) return;
  if (btn) btn.disabled = true;
  try { await serverActionApi(action); toast(action === "stop" ? "Server stopped" : action === "start" ? "Server starting…" : "Server restarting…"); }
  catch (e) { toast(e.message); }
  setTimeout(() => show(TAB), 1500);
}

/* ------------------------------------------------------------------ pages: all drawn by React now
   (app.jsx, pages.jsx, health.jsx, players.jsx, mods.jsx, config.jsx, settings.jsx, settings-cards.jsx, power.jsx).
   What is left here: shared helpers and a few dialogs. */

/* ---------------- modpack share code (Mods page) */
async function modpackCode() {
  let d; try { d = await api("/api/modpack/code"); } catch (e) { return toast(e.message); }
  const bg = modal(`<div class="row"><h2 style="margin:0">Mod pack code</h2><span class="spacer"></span><button class="btn sm" data-x>Close</button></div>
    <p class="small muted">A short code instead of a big file. Another EasyServer owner pastes it and gets the same mods straight from the BeamNG repository (each one virus-checked).</p>
    ${d.code ? `<textarea id="mpc_t" readonly rows="3" class="mono">${esc(d.code)}</textarea><div class="row" style="margin-top:6px"><button class="btn sm primary" id="mpc_copy">Copy code</button><span class="small muted">${d.count === 1 ? "1 mod" : d.count + " mods"}</span></div>` : `<p class="small">None of your mods come from the BeamNG repository, so there's nothing to put in a code - use "Download modpack" instead.</p>`}
    ${d.not_included.length ? `<p class="small muted">Not in the code (not from the repository): ${esc(d.not_included.join(", "))} - send these as a modpack file.</p>` : ""}
    <label class="f" style="margin-top:12px"><span>Got a code? Paste it here</span><textarea id="mpc_in" rows="3" class="mono" placeholder="ES1-…" spellcheck="false"></textarea></label>
    <div class="row"><button class="btn sm" id="mpc_go">Install these mods</button></div>`);
  bg.querySelector("[data-x]").onclick = () => bg.remove();
  if ($("#mpc_copy", bg)) $("#mpc_copy", bg).onclick = async () => toast(await copyText(d.code) ? "Code copied" : "Select the code and press Ctrl+C");
  $("#mpc_go", bg).onclick = async () => {
    try { const r = await api("/api/modpack/code", { json: { code: $("#mpc_in", bg).value } }); toast(r.note, 10000); bg.remove(); } catch (e) { toast(e.message, 8000); }
  };
}

/* ---------------- settings: React now (settings.jsx, settings-cards.jsx, power.jsx) */

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
  $, esc, ipb, store, IN_APP, api, toast, undoable, copyText, modal, fmtSize, fmtDur, fmtTime, ago, applyTheme, I, LOGO_SVG, TABS,
  loadLangList, loadLang, pickLang, tr, approveFromLink, stopAlerts, sleepComputer, myRole, myTabs, reviewGate, serverAction, serverActionApi,
  openInvite, openMyAccount, modBrowser, modpackCode,
};
