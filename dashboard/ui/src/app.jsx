// The dashboard's React app: logging in, the frame around every page (menu, server picker, theme,
// language, security alerts) and the Overview page. The other pages are in their own files; the
// helpers in legacy.js reach the app through `bridge`.
import { useCallback, useEffect, useRef, useState } from "react";
import * as L from "./legacy.js";
import { Logs, Notifications, Servers, Updates } from "./pages.jsx";
import { Health } from "./health.jsx";
import { Players } from "./players.jsx";
import { Mods } from "./mods.jsx";
import { Config } from "./config.jsx";
import { Settings } from "./settings.jsx";
import { cacheGet, cachedApi, cacheClear, prefetch, PageWait } from "./ui.jsx";

// What each page asks for first: fetched quietly in the background after logging in, so pages open without waiting
const PREFETCH = ["/api/overview", "/api/config", "/api/allowlist", "/api/mapvote", "/api/restarts", "/api/vehicles", "/api/tools", "/api/preset", "/api/timed",
  "/api/config/history", "/api/templates", "/api/rotation", "/api/messages", "/api/events", "/api/moderation", "/api/extras", "/api/joinalerts",
  "/api/mods", "/api/mods/updates", "/api/plugins", "/api/players", "/api/bans", "/api/updates", "/api/notifications", "/api/settings", "/api/supporter",
  "/api/phoneapp", "/api/ntfy", "/api/discordbot", "/api/integrations", "/api/statuspage", "/api/users", "/api/devices", "/api/guard", "/api/backups", "/api/resources"];

const S = () => L.state();
const Icon = ({ n }) => <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" dangerouslySetInnerHTML={{ __html: L.I[n] }} />;
const Logo = () => <div className="logo" dangerouslySetInnerHTML={{ __html: L.LOGO_SVG }} />;
const Ip = ({ children }) => <span className="ipb" title="Hidden - click to show">{children}</span>;

function LangSelect({ onChange }) {
  const { LANG, LANGS } = S();
  return (
    <select className="langpick" aria-label="Language" data-notr value={LANG} onChange={e => onChange(e.target.value)}>
      {LANGS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
    </select>
  );
}

/* ------------------------------------------------------------------ before logging in */
function AuthCard({ onLang, children }) {
  return (
    <div className="center"><div className="card authcard">
      <div className="row"><Logo /><span className="spacer" /><LangSelect onChange={onLang} /></div>
      {children}
    </div></div>
  );
}

function Setup({ onLang, boot }) {
  const [p1, setP1] = useState(""), [p2, setP2] = useState(""), [busy, setBusy] = useState(false);
  if (!S().SESSION.setup_allowed) return (
    <AuthCard onLang={onLang}><h1>Almost ready</h1>
      <p className="sub">Open this dashboard once on the server computer itself (<span className="mono">http://localhost:{location.port || 30815}</span>) to create the password.</p>
    </AuthCard>
  );
  const go = async () => {
    if (p1 !== p2) return L.toast("The passwords don't match");
    if (busy) return; setBusy(true);                      // no double submit
    try { await L.api("/api/setup", { json: { password: p1 } }); boot(); } catch (e) { setBusy(false); L.toast(e.message); }
  };
  return (
    <AuthCard onLang={onLang}><h1>Create a password</h1><p className="sub">You'll use it to open the dashboard from any device.</p>
      <label className="f"><span>Password</span><input type="password" autoComplete="new-password" value={p1} onChange={e => setP1(e.target.value)} /><small>At least 8 characters. 12+ if you want internet access later.</small></label>
      <label className="f"><span>Repeat password</span><input type="password" autoComplete="new-password" value={p2} onChange={e => setP2(e.target.value)} /></label>
      <button className="btn primary" disabled={busy} onClick={go}>Create password</button>
    </AuthCard>
  );
}

function Login({ onLang, boot, msg: msg0, needCode: need0 }) {
  const ses = S().SESSION;
  const [user, setUser] = useState(""), [pw, setPw] = useState(""), [code, setCode] = useState("");
  const [needCode, setNeedCode] = useState(!!(need0 || ses.totp));
  const [remember, setRemember] = useState(L.store.get("es-remember", L.IN_APP ? "1" : "0") === "1");
  const [msg, setMsg] = useState(msg0 || ""), [busy, setBusy] = useState(false);
  const submit = async ev => {
    ev.preventDefault();
    setBusy(true); L.store.set("es-remember", remember ? "1" : "0");
    try {
      await L.api("/api/login", { json: { user: user.trim(), password: pw, code, remember } });
      // Lets the browser's password manager offer to save the password (Chrome / Edge / Android; others save on submit)
      try { if (window.PasswordCredential) await navigator.credentials.store(new window.PasswordCredential({ id: user.trim() || "owner", password: pw, name: "BeamMP Dashboard" })); } catch (e) {}
      boot();
    } catch (e) { setMsg(e.message); if (e.data && e.data.need_code) setNeedCode(true); setBusy(false); }
  };
  const discord = async () => {
    L.store.set("es-remember", remember ? "1" : "0");
    try { location.href = (await L.api("/api/discord/start", { method: "POST" })).url; } catch (e) { setMsg(e.message); }
  };
  return (
    <AuthCard onLang={onLang}><h1>BeamMP Dashboard</h1><p className="sub">Log in to manage your server.</p>
      <form autoComplete="on" onSubmit={submit}>
        <label className="f"><span>Name <span className="muted">(leave empty if you're the owner)</span></span><input type="text" autoComplete="username" spellCheck="false" maxLength={24} value={user} onChange={e => setUser(e.target.value)} /></label>
        <label className="f"><span>Password</span><input type="password" autoComplete="current-password" autoFocus value={pw} onChange={e => setPw(e.target.value)} /></label>
        {needCode && <label className="f"><span>Two-step code</span><input type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={7} placeholder="123456" value={code} onChange={e => setCode(e.target.value)} /><small>From your authenticator app (only if two-step login is on for your account)</small></label>}
        <label className="toggle" style={{ border: 0, padding: "4px 0 12px" }}><input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)} /><span><b>Stay logged in on this device</b><small>For 30 days. Only turn this on on your own phone or computer. Log out (or Settings → Remembered devices) to forget it</small></span></label>
        <button className="btn primary" type="submit" disabled={busy}>Log in</button>
        {ses.discord_login && <button className="btn" type="button" style={{ marginLeft: 8 }} onClick={discord}>Sign in with Discord</button>}
        <p className="small muted">{msg}</p>
      </form>
    </AuthCard>
  );
}

function DiscordCode({ onLang, retry, onCode }) {
  const [code, setCode] = useState("");
  return (
    <AuthCard onLang={onLang}><h1>Two-step code</h1><p className="sub">Discord said it's you. Now the code from your authenticator app.</p>
      <form onSubmit={e => { e.preventDefault(); onCode(code); }}>
        <label className="f"><span>Two-step code</span><input type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={7} placeholder="123456" autoFocus value={code} onChange={e => setCode(e.target.value)} /></label>
        <button className="btn primary" type="submit">Log in</button><p className="small muted">{retry ? "That code didn't work - try the next one." : ""}</p>
      </form>
    </AuthCard>
  );
}

const Qr = ({ size, path, px = 200, label }) => {
  const n = Number(size) || 0, qp = /^[MhvzZ0-9 -]*$/.test(path || "") ? path : "";
  if (!n || !qp) return null;
  return (
    <div style={{ background: "#fff", padding: 12, borderRadius: 8, display: "inline-block", margin: "6px 0" }}>
      <svg width={px} height={px} viewBox={`-4 -4 ${n + 8} ${n + 8}`} shapeRendering="crispEdges" role="img" aria-label={label}>
        <rect x="-4" y="-4" width={n + 8} height={n + 8} fill="#fff" /><path d={qp} fill="#000" />
      </svg>
    </div>
  );
};

function TeamInvite({ onLang, tok, boot }) {
  const [d, setD] = useState(null);
  const [f, setF] = useState({ name: "", pw: "", pw2: "", code: "" }), [err, setErr] = useState(""), [busy, setBusy] = useState(false);
  useEffect(() => { (async () => { try { setD(await (await fetch("/api/teaminvite/info?t=" + encodeURIComponent(tok))).json()); } catch (e) { setD({ error: e.message }); } })(); }, [tok]);
  const set = k => e => setF({ ...f, [k]: e.target.value });
  const toLogin = () => { history.replaceState(null, "", location.pathname); boot(); };
  if (!d) return <AuthCard onLang={onLang}><p className="muted">Loading…</p></AuthCard>;
  if (d.error) return <AuthCard onLang={onLang}><h1>Invite</h1><p className="sub">{d.error}</p><button className="btn" onClick={toLogin}>Go to the login page</button></AuthCard>;
  const t = d.totp;
  const go = async () => {
    if (f.pw !== f.pw2) return setErr("The passwords don't match");
    setBusy(true);
    try {
      const r = await fetch("/api/teaminvite/accept", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ t: tok, name: f.name.trim(), password: f.pw, code: t ? f.code : "" }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || "Didn't work");
      L.toast("Done - log in with your new name and password", 8000); toLogin();
    } catch (e) { setErr(e.message); setBusy(false); }
  };
  return (
    <AuthCard onLang={onLang}><h1>Join the team</h1>
      <p className="sub">You're invited to help run <b>{d.server}</b> as <b>{d.role}</b>{d.servers ? " (" + d.servers.join(", ") + ")" : ""}. Pick your login:</p>
      <label className="f"><span>Your name</span><input type="text" maxLength={24} autoComplete="username" spellCheck="false" placeholder="letters, numbers, . _ -" value={f.name} onChange={set("name")} /></label>
      <label className="f"><span>Password</span><input type="password" autoComplete="new-password" placeholder="at least 10 characters" value={f.pw} onChange={set("pw")} /></label>
      <label className="f"><span>Repeat password</span><input type="password" autoComplete="new-password" value={f.pw2} onChange={set("pw2")} /></label>
      {t && <>
        <p className="small">You may log in from the internet, so your account gets <b>two-step login</b>. Scan this with an authenticator app (Google Authenticator, Microsoft Authenticator, Aegis…):</p>
        <Qr size={t.qr_size} path={t.qr_path} label="QR code for two-step login" />
        <p className="small muted">Or type this key in the app: <span className="mono">{t.secret}</span></p>
        <label className="f"><span>6-digit code from the app</span><input type="text" inputMode="numeric" maxLength={7} autoComplete="one-time-code" value={f.code} onChange={set("code")} /></label>
      </>}
      <button className="btn primary" disabled={busy} onClick={go}>Create my login</button><p className="small muted">{err}</p>
    </AuthCard>
  );
}

/* ------------------------------------------------------------------ the frame */
function SecurityBar() {
  const [d, setD] = useState(null);
  const seen = useRef(new Set());
  const load = useCallback(async () => {
    const x = await L.api("/api/security");
    const a = x.active || [];
    document.title = (a.length ? "⚠️ " : "") + "BeamMP Dashboard";
    setD(x);
    // pop-up on this device (needs permission, given under Settings); clicking it stops the alert
    if (window.Notification && Notification.permission === "granted") a.filter(y => !seen.current.has(y.id + ":" + y.sent)).forEach(y => {
      seen.current.add(y.id + ":" + y.sent);
      try { const n = new Notification("⚠️ " + y.title, { body: "Click to stop these alerts.", tag: y.id, requireInteraction: true }); n.onclick = () => { window.focus(); L.stopAlerts(y.id); n.close(); }; } catch (e) {}
    });
  }, []);
  useEffect(() => {
    L.bridge.checkSecurity = () => load().catch(() => {});
    load().catch(() => {});
    const t = setInterval(() => load().catch(() => {}), 30000);
    return () => { clearInterval(t); L.bridge.checkSecurity = async () => {}; };
  }, [load]);
  const a = (d && d.active) || [];
  if (!a.length) return <div id="secbar" />;
  return (
    <div id="secbar"><div className="secbar" role="alert"><div style={{ flex: 1 }}>
      <b>⚠️ Security alert{a.length > 1 ? "s (" + a.length + ")" : ""}</b>
      {a.slice(0, 3).map(x => <div className="small" key={x.id}><b>{x.title}</b>{(x.count > 1 ? " · " + x.count + " times" : "") + " · last " + L.fmtTime(x.last)}</div>)}
      <div className="small">{d.reminders && d.enabled ? "Sent to all your notification channels and repeated every 15 minutes until you stop it." : "Details under Notifications."}</div>
    </div><button className="btn sm" onClick={() => L.stopAlerts("all")}>Got it - stop alerts</button></div></div>
  );
}

function ServerPick() {
  const { SERVERS, SERVER } = S();
  if (SERVERS.length < 2) return null;
  return (
    <label className="srvpick"><span className="small muted">Server</span>
      <select value={SERVER} onChange={e => L.bridge.switchServer(e.target.value)}>
        {SERVERS.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}
      </select>
    </label>
  );
}

function Shell({ tab, reload, unread, onLang, logout }) {
  const [, redraw] = useState(0);
  const ses = S().SESSION, role = L.myRole();
  useEffect(() => { const t = setTimeout(() => prefetch(PREFETCH), 900); return () => clearTimeout(t); }, []);
  const dark = document.documentElement.dataset.theme === "dark";
  const glass = L.store.get("es-look", "glass") !== "classic";
  const flipLook = () => { L.store.set("es-look", glass ? "classic" : "glass"); L.applyTheme(); redraw(x => x + 1); };
  const flip = () => { L.store.set("es-theme", dark ? "light" : "dark"); L.applyTheme(); redraw(x => x + 1); if (tab === "players") L.bridge.show("players"); };
  const navs = L.myTabs().map(([k, label]) => (
    <button key={k} className={"nav" + (k === tab ? " active" : "")} onClick={() => L.bridge.show(k)}>
      <Icon n={k} /><span>{label}</span>{k === "notifications" && <span className={"count" + (unread ? "" : " hidden")}>{unread}</span>}
    </button>
  ));
  // A page slides in once when you open it. After that, parts that finish loading or refresh
  // appear in place, so nothing slides around under your finger.
  const settle = useCallback(el => { if (el) setTimeout(() => el.classList.remove("enter"), 900); }, []);
  return (
    <div className="app">
      <aside className="side">
        <div className="brand"><Logo /><div>BeamMP EasyServer<small>{"Dashboard " + ses.version + (ses.supporter ? " · ❤ Supporter" : "")}</small></div></div>
        <ServerPick />{navs}<div className="grow" />
        <div className="foot">
          <button className="iconbtn" title="Light / dark mode" onClick={flip}><Icon n={dark ? "sun" : "moon"} /></button>
          <button className="iconbtn" title={glass ? "Classic look" : "Glass look"} aria-pressed={glass} onClick={flipLook}><Icon n="glass" /></button>
          <button className="small muted" title="My account" style={{ background: "none", border: 0, cursor: "pointer", padding: 0, color: "inherit" }} onClick={() => L.openMyAccount()}>{ses.user || "owner"}{role ? " · " + role.name : ""}</button>
          <span className="spacer" /><LangSelect onChange={onLang} />
          <button className="iconbtn" title="Log out" onClick={logout}><Icon n="logout" /></button>
        </div>
      </aside>
      <div>
        <nav className="mobilebar"><ServerPick />{navs}<button className="nav" onClick={flip}>Theme</button><button className="nav" onClick={flipLook}>{glass ? "Classic look" : "Glass look"}</button></nav>
        <SecurityBar />
        <main id="main" className="enter" key={tab} ref={settle}>{(P => <P reload={reload} />)(PAGES[tab] || Overview)}</main>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Overview */
const PILL = { running: ["good", "Running"], stopped: ["", "Stopped"], failed: ["bad", "Crashed"], starting: ["warn", "Starting"], restarting: ["warn", "Restarting"], stopping: ["warn", "Stopping"] };
function StatePill({ state }) {
  const [cls, label] = PILL[state] || ["", state || "Unknown"];
  return <span className={"pill " + cls}><span className="dot" />{label}</span>;
}
const Banner = ({ kind, title, note, btn, primary, onClick }) => (
  <div className={"banner " + kind}><b>{title}</b>{note && <span className="muted">{note}</span>}<span className="spacer" />
    <button className={"btn sm" + (primary ? " primary" : "")} onClick={onClick}>{btn}</button></div>
);

// "New in …" after an update: dashboard/whatsnew.json is made from CHANGELOG.md with the website.
// Shown once per version in each browser until "Got it" is pressed.
let NEWS = null;
function News() {
  const [n, setN] = useState(null);
  useEffect(() => {
    let live = true;
    (async () => {
      try { NEWS = NEWS || await (await fetch("/whatsnew.json", { cache: "no-cache" })).json(); } catch (e) { return; }
      const Ls = NEWS.languages || {}, x = Ls[S().LANG] || Ls.en;
      if (live && NEWS.version && x && x.items && x.items.length && L.store.get("es-news-seen", "") !== NEWS.version) setN(x);
    })();
    return () => { live = false; };
  }, []);
  if (!n) return null;
  return (
    <div className="card news">
      <div className="head"><h2>{n.title}</h2><span className="muted small">{n.note}</span><span className="spacer" />
        <a className="btn ghost sm" href="https://github.com/Csabika-dev/beammp-easyserver/blob/main/CHANGELOG.md" target="_blank" rel="noopener">All changes</a>
        <button className="btn sm" onClick={() => { L.store.set("es-news-seen", NEWS.version); setN(null); }}>Got it</button></div>
      <div className="items">{n.items.map(([t, x]) => <div className="item" key={t}><b>{t}</b><p>{x}</p></div>)}</div>
    </div>
  );
}

function Overview({ reload }) {
  const [d, setD] = useState(() => cacheGet("/api/overview") ?? null), [err, setErr] = useState(""), [map, setMap] = useState(() => (cacheGet("/api/overview") || {}).map || ""), [sleeping, setSleeping] = useState(false);
  const last = useRef(null);
  const load = useCallback(async () => {
    const x = await cachedApi("/api/overview");
    last.current = x; setD(x); setMap(x.map || ""); L.bridge.setUnread(x.unread);
  }, []);
  useEffect(() => { setErr(""); load().catch(e => { if (e.message !== "Please log in") setErr(e.message); }); }, [load, reload]);
  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const x = await L.api("/api/overview"), d0 = last.current;
        if (!d0 || x.status.state !== d0.status.state || (x.online || []).length !== (d0.online || []).length || x.unread !== d0.unread) { last.current = x; setD(x); L.bridge.setUnread(x.unread); }
      } catch (e) {}
    }, 10000);
    return () => clearInterval(t);
  }, []);
  if (!d) return <PageWait err={err} retry={() => load().then(() => setErr(""), e => setErr(e.message))} />;
  const s = d.status, online = d.online || [], go = v => () => L.bridge.show(v);
  const act = a => e => L.serverAction(a, e.currentTarget);
  const applyMap = async e => {
    const b = e.currentTarget;
    if (map === d.map) { L.toast("That's already the current map"); return; }
    if (s.state === "running" && !confirm("Switch to " + map + "?\n\nThe server restarts now" + (online.length ? " and " + online.length + " player(s) are disconnected for a moment" : "") + ".")) return;
    b.disabled = true;
    try { const r = await L.api("/api/map", { json: { map } }); L.toast(r.note, 6000); } catch (x) { L.toast(x.message); }
    setTimeout(() => L.bridge.show("overview"), 1500);
  };
  const groups = [["Built-in maps", d.maps.builtin], ["Map mods", d.maps.mods]].filter(g => g[1].length);
  const known = d.maps.builtin.includes(d.map) || d.maps.mods.includes(d.map);
  return (<>
    <div className="row">
      <div><h1>{d.name || "BeamMP server"}</h1>
        <p className="sub"><Ip>{d.lan_ip + ":" + d.port}</Ip>{" · " + (d.map || "?") + " · "}{d.private ? "Private" : "Public"}{d.relay && <>{" · players join via "}<Ip>{d.relay}</Ip></>}</p></div>
      <span className="spacer" />
      <button className="btn sm" title="A ready-to-paste message with the address" onClick={() => L.openInvite()}>Copy invite</button><StatePill state={s.state} />
    </div>
    {!d.reviewed && <div className="banner info" style={{ marginTop: 12 }}>Before this server goes live, look over its settings once. <a href="#" onClick={async e => { e.preventDefault(); if (await L.reviewGate(undefined, false)) { L.toast("Thanks - this server is ready to start"); L.bridge.show("overview"); } }}>Review settings</a></div>}
    {d.restart_needed && <Banner kind="info" title="Restart needed" note="Your changes apply after a restart." btn="Restart now" primary onClick={act("restart")} />}
    {s.state === "failed" && <Banner kind="bad" title="The server crashed." note="Check the Logs page for the reason." btn="Open logs" onClick={go("logs")} />}
    {!!d.config_errors && <Banner kind="bad" title={d.config_errors + " config error(s)"} btn="Fix" onClick={go("config")} />}
    {!d.has_authkey && <Banner kind="warn" title="No AuthKey set." note="Players outside your network can't find the server." btn="Add AuthKey" onClick={go("config")} />}
    {d.update_available && <Banner kind="info" title="A BeamMP server update is available." btn="See update" onClick={go("updates")} />}
    {!!d.quarantined && <Banner kind="warn" title={d.quarantined + " mod(s) blocked by the virus check."} btn="Review" onClick={go("mods")} />}
    <News />
    <div className="grid g4">
      <div className="card stat"><div className="label">Players online</div><div className="value">{online.length}<span className="muted small"> / {d.max_players ?? "?"}</span></div><div className="note">{online.length ? online.slice(0, 3).join(", ") + (online.length > 3 ? "…" : "") : "Nobody right now"}</div></div>
      <div className="card stat"><div className="label">Uptime</div><div className="value">{s.state === "running" ? L.fmtDur(s.uptime) : "-"}</div><div className="note">{s.restarts ? s.restarts + " automatic restart(s)" : "No crashes"}</div></div>
      <div className="card stat"><div className="label">Mods</div><div className="value">{d.mods}</div><div className="note">{d.quarantined ? d.quarantined + " blocked" : "All virus-checked"}</div></div>
      <div className="card stat"><div className="label">BeamMP server</div><div className="value">{d.installed_version || "?"}</div><div className="note">{d.update_available ? "Update available" : "Up to date"}</div></div>
    </div>
    <div className="grid g3" style={{ marginTop: 16 }}>
      <div className="card"><h2>Server control</h2><p className="muted small">Start, stop or restart the BeamMP server. A restart disconnects everyone who is playing.</p>
        <div className="row">
          {s.state === "running" ? <><button className="btn" onClick={act("restart")}>Restart</button><button className="btn danger" onClick={act("stop")}>Stop</button></> : <button className="btn primary" onClick={act("start")}>Start server</button>}
          {L.myTabs().some(t => t[0] === "settings") && <><span className="spacer" />
            <button className="btn" disabled={sleeping} title="Put the server computer to sleep - wake it with the phone app's Wake up button or its power button" onClick={async () => { if (await L.sleepComputer()) setSleeping(true); }}>{sleeping ? "Going to sleep…" : "Sleep PC"}</button></>}
        </div></div>
      <div className="card"><h2>Map</h2><p className="muted small">Switch the map in one click. The server restarts, so players are disconnected for a moment and reconnect on the new map.</p>
        <div className="row">
          <select style={{ flex: 1, minWidth: 0 }} value={map} onChange={e => setMap(e.target.value)}>
            {groups.map(([l, xs]) => <optgroup key={l} label={l}>{xs.map(x => <option key={x} value={x}>{x}</option>)}</optgroup>)}
            {d.map && !known && <option value={d.map}>{d.map}</option>}
          </select>
          <button className="btn primary" onClick={applyMap}>Apply</button></div></div>
      <div className="card"><h2>Who's online</h2>{online.length ? <div className="row">{online.map(p => <span className="pill" key={p}><span className="dot" />{p}</span>)}</div> : <p className="muted">Nobody is playing right now.</p>}</div>
    </div>
  </>);
}

// Pages drawn by React; the rest are still in legacy.js
const PAGES = { overview: Overview, servers: Servers, updates: Updates, logs: Logs, notifications: Notifications, network: Health, players: Players, mods: Mods, config: Config, settings: Settings };

/* ------------------------------------------------------------------ the app */
export function App() {
  const [screen, setScreen] = useState({ kind: "loading" });
  const [tab, setTabState] = useState("overview"), [reload, setReload] = useState(0), [unread, setUnread] = useState(0);
  const [epoch, setEpoch] = useState(0);              // a new language draws everything again from scratch
  const tabRef = useRef("overview");

  // show(): open a page, or draw it again when it's already open. open(): just make it the open page
  // (after logging in or a language change the frame is drawn from scratch anyway).
  const open = useCallback(t => { history.replaceState(null, "", "#" + t); L.setTab(t); tabRef.current = t; setTabState(t); }, []);
  const show = useCallback(t => {
    L.clearTimer();
    // Drawing the open page again (after saving something) keeps your place; only a new page starts at the top.
    if (t === tabRef.current) { history.replaceState(null, "", "#" + t); setReload(r => r + 1); } else { open(t); window.scrollTo(0, 0); }
  }, [open]);

  const finishDiscord = useCallback(async (note, code) => {
    try {
      const r = await L.api("/api/discord/finish", { json: { a: note, code: code || "", remember: L.store.get("es-remember", "0") === "1" } });
      await boot();
      if (r.linked) L.toast("Discord linked: " + r.linked + ". Next time you can press \"Sign in with Discord\".", 7000);
    } catch (e) {
      if (e.data && e.data.need_code) return setScreen({ kind: "dccode", note, retry: !!code });
      if (S().SESSION.logged_in) { await boot(); L.toast(e.message, 8000); } else setScreen({ kind: "login", msg: e.message });
    }
  }, []);

  const boot = useCallback(async () => {
    L.clearTimer();
    let ses;
    try { ses = await L.api("/api/session"); } catch (e) { return setScreen({ kind: "error", msg: e.message }); }
    L.setSession(ses);
    if (ses.needs_setup) return setScreen({ kind: "setup" });
    const h = location.hash;
    if (h.startsWith("#team=")) return setScreen({ kind: "team", tok: h.slice(6) });
    if (h.startsWith("#dc=") || h.startsWith("#dc_err=")) {      // back from "Sign in with Discord"
      history.replaceState(null, "", location.pathname);
      if (h.startsWith("#dc_err=")) {
        const denied = h === "#dc_err=denied";
        if (!ses.logged_in) return setScreen({ kind: "login", msg: denied ? "Discord sign-in was cancelled." : "Discord sign-in didn't work - try again." });
        L.toast(denied ? "Discord sign-in was cancelled" : "Discord sign-in didn't work - try again");
      } else return finishDiscord(h.slice(4));
    }
    if (!ses.logged_in) return setScreen({ kind: "login" });
    try { L.setServers((await L.api("/api/servers")).servers); } catch (e) { L.setServers([{ id: "main", name: "Main server" }]); }
    const { SERVERS, SERVER } = S();
    if (!SERVERS.some(x => x.id === SERVER)) L.setServer(SERVERS[0] ? SERVERS[0].id : "main"); else L.setServer(SERVER);
    const hash = location.hash.slice(1);
    setScreen({ kind: "app" });
    if (/^ack=[a-f0-9]{16}$/.test(hash)) { history.replaceState(null, "", location.pathname + "#overview"); await L.stopAlerts(hash.slice(4)); return open("overview"); }
    if (hash.startsWith("approve=")) { let n = ""; try { n = decodeURIComponent(hash.slice(8)).slice(0, 40); } catch (e) {} open("overview"); return setTimeout(() => L.approveFromLink(n), 0); }
    open(L.myTabs().some(t => t[0] === hash) ? hash : "overview");
  }, [open, finishDiscord]);

  useEffect(() => {
    Object.assign(L.bridge, {
      boot, show,
      refreshShell: () => setEpoch(e => e + 0.001),      // redraw the frame (new server names, roles …)
      setUnread: n => setUnread(n || 0),
      switchServer: id => {
        L.setServer(id);
        const u = new URL(location.href); u.searchParams.delete("srv"); history.replaceState(null, "", u.pathname + "#" + tabRef.current);
        const t = tabRef.current === "servers" || !L.myTabs().some(x => x[0] === tabRef.current) ? "overview" : tabRef.current;
        setEpoch(e => e + 1); tabRef.current = t; setTabState(t); L.setTab(t);
      },
    });
    boot();
  }, [boot, show]);

  const onLang = async code => { L.store.set("es-lang", code); await L.loadLang(code); setEpoch(e => Math.floor(e) + 1); boot(); };
  const logout = async () => {
    try { await L.api("/api/logout", { method: "POST" }); } catch (e) {}
    cacheClear();
    try { if ("caches" in window) (await caches.open("es-shell-v2")).delete("/__wake.json"); } catch (e) {}
    boot();
  };

  const k = "e" + Math.floor(epoch);
  switch (screen.kind) {
    case "loading": return null;
    case "error": return <div className="center"><div className="card authcard"><h2>Can't reach the dashboard</h2><p className="muted">{screen.msg}</p></div></div>;
    case "setup": return <Setup key={k} onLang={onLang} boot={boot} />;
    case "login": return <Login key={k + (screen.msg || "")} onLang={onLang} boot={boot} msg={screen.msg} />;
    case "dccode": return <DiscordCode key={k} onLang={onLang} retry={screen.retry} onCode={c => finishDiscord(screen.note, c)} />;
    case "team": return <TeamInvite key={k} onLang={onLang} tok={screen.tok} boot={boot} />;
    default: return <Shell key={k} tab={tab} reload={reload} unread={unread} onLang={onLang} logout={logout} epoch={epoch} />;
  }
}
