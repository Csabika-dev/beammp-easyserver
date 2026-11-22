// Dashboard pages written in React. Each gets `reload` (bumped when the page should load again).
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import * as L from "./legacy.js";

const S = () => L.state();
export const Ip = ({ children }) => <span className="ipb" title="Hidden - click to show">{children}</span>;

// IP addresses inside text are blurred until clicked, like a password
const IP_RE = /(?<!\d)(?<!\d\.)(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?(?!\d|\.\d)/g;
export function Blur({ text }) {
  const s = String(text ?? ""), out = [];
  let last = 0;
  for (const m of s.matchAll(IP_RE)) { out.push(s.slice(last, m.index)); out.push(<Ip key={m.index}>{m[0]}</Ip>); last = m.index + m[0].length; }
  out.push(s.slice(last));
  return <>{out}</>;
}

// Load data for a page; again whenever `reload` or the deps change.
export function useApi(path, reload, deps = []) {
  const [state, setState] = useState({ d: null, err: "" });
  const load = useCallback(async () => {
    try { setState({ d: await L.api(path), err: "" }); }
    catch (e) { if (e.message !== "Please log in") setState(s => ({ ...s, err: e.message })); }
  }, [path]);
  useEffect(() => { load(); }, [load, reload, ...deps]);
  return [state.d, state.err, load];
}
const Wait = ({ err }) => err ? <div className="banner bad">{err}</div> : <p className="muted">Loading…</p>;
const Pill = ({ ok, yes, no }) => <span className={"pill " + (ok ? "good" : "warn")}><span className="dot" />{ok ? yes : no}</span>;

/* ------------------------------------------------------------------ Updates */
const isNew = (a, b) => { if (!a || !b) return false; const x = a.split(".").map(Number), y = b.split(".").map(Number); for (let i = 0; i < 3; i++) { if (x[i] !== y[i]) return x[i] > y[i]; } return false; };
export function Updates({ reload }) {
  const [d, err] = useApi("/api/updates", reload);
  const [busy, setBusy] = useState("");
  if (!d) return <Wait err={err} />;
  const srvNew = isNew(d.latest, d.installed), esNew = isNew(d.easy_latest, d.easy_installed), exp = d.channel === "experimental";
  const chan = c => async () => { try { await L.api("/api/updates/check", { json: { channel: c } }); L.toast(c === "stable" ? "Stable versions only" : "You'll hear about newer versions too"); } catch (e) { L.toast(e.message); } L.bridge.show("updates"); };
  const check = async () => { setBusy("check"); try { await L.api("/api/updates/check", { method: "POST" }); } catch (e) { L.toast(e.message); } setBusy(""); L.bridge.show("updates"); };
  const install = async () => {
    if (!confirm("Install the update now? Players will be disconnected.")) return;
    setBusy("install");
    try { const r = await L.api("/api/updates/install", { method: "POST" }); L.toast("Updated to " + (r.installed || "the newest version")); } catch (e) { L.toast(e.message); }
    setBusy(""); L.bridge.show("updates");
  };
  const Stat = ({ label, v }) => <div className="stat"><div className="label">{label}</div><div className="value">{v || "?"}</div></div>;
  const note = !d.paid
    ? (exp ? "You hear about the Rolling release too: the newest features as soon as they're made. They may have bugs - if something breaks, install the newest Stable over it (settings and mods stay)." : "Tested versions only. Pick Rolling to get the newest features as soon as they're made (may have bugs).")
    : exp ? "You hear about every new version first. Experimental versions have the newest features but aren't fully tested - if something breaks, go back to the newest Stable download."
      : d.supporter ? "Tested versions only. Pick Experimental to try new features before everyone else." : "Tested versions only. Experimental versions (newest features first) are a thank-you for supporters - Settings → Supporter.";
  return (<>
    <div className="row"><div><h1>Updates</h1><p className="sub">{(d.checked_at ? "Last checked " + L.ago(d.checked_at) : "Not checked yet") + ". The dashboard checks every 6 hours and notifies you."}</p></div>
      <span className="spacer" /><button className="btn" disabled={busy === "check"} onClick={check}>Check now</button></div>
    {d.error && <div className="banner warn">{d.error}</div>}
    <div className="grid g2">
      <div className="card"><h2>BeamMP server</h2>
        <div className="row"><Stat label="Installed" v={d.installed} /><span className="spacer" /><Stat label="Newest" v={d.latest} /></div>
        <p><Pill ok={!srvNew} yes="Up to date" no="Update available" /></p>
        {srvNew && <><p className="small muted">Installing stops the server for a moment (players are disconnected), then starts it again.</p>
          <button className="btn primary" disabled={busy === "install"} onClick={install}>{busy === "install" ? "Installing…" : "Install " + d.latest}</button></>}
      </div>
      <div className="card"><h2>BeamMP EasyServer (this dashboard)</h2>
        <div className="row"><Stat label="Installed" v={d.easy_installed} /><span className="spacer" /><Stat label="Newest" v={d.easy_latest} /></div>
        <p><Pill ok={!esNew} yes="Up to date" no="Update available" /></p>
        {esNew && <p className="small">Download it from <a href={`https://github.com/${d.repo}/releases/latest`} target="_blank" rel="noopener noreferrer">GitHub</a> and run the installer again - your settings and mods are kept.</p>}
        {d.easy_early && <div className="banner" style={{ margin: "8px 0" }}><span className="small"><b>{(exp ? (d.paid ? "Experimental" : "Rolling release") : "Early access") + " " + d.easy_early}</b> is out. <a href={d.easy_early_url || `https://github.com/${d.repo}/releases`} target="_blank" rel="noopener noreferrer">Download it</a> and run the installer again.</span></div>}
        <div className="row" style={{ marginTop: 10, flexWrap: "wrap", gap: 6 }}><span className="small"><b>Version:</b></span>
          <button className={"btn sm" + (exp ? "" : " on")} onClick={chan("stable")}>Stable</button>
          {d.paid
            ? <button className={"btn sm" + (exp ? " on" : "")} disabled={!d.supporter} title={d.supporter ? undefined : "Supporters only"} onClick={chan("experimental")}>{"Experimental" + (d.supporter ? "" : " ❤")}</button>
            : <button className={"btn sm" + (exp ? " on" : "")} onClick={chan("experimental")}>Rolling</button>}
        </div>
        <p className="small muted" style={{ margin: "6px 0 0" }}>{note}</p>
      </div>
    </div>
  </>);
}

/* ------------------------------------------------------------------ Notifications */
export function Notifications({ reload }) {
  const [d, err] = useApi("/api/notifications", reload);
  useEffect(() => { if (d && d.items.some(n => !n.read)) L.api("/api/notifications/read", { method: "POST" }).then(() => L.bridge.setUnread(0)).catch(() => {}); }, [d]);
  if (!d) return <Wait err={err} />;
  const read = async () => { await L.api("/api/notifications/read", { method: "POST" }); L.bridge.setUnread(0); L.bridge.show("notifications"); };
  const clear = async () => { if (!confirm("Delete all notifications?")) return; await L.api("/api/notifications/clear", { method: "POST" }); L.bridge.setUnread(0); L.bridge.show("notifications"); };
  return (<>
    <div className="row"><div><h1>Notifications</h1><p className="sub">Crashes, updates, blocked mods and security events. Choose where they're sent under Settings.</p></div><span className="spacer" />
      <button className="btn" onClick={read}>Mark all read</button><button className="btn danger" onClick={clear}>Clear</button></div>
    <div className="card tight">
      {d.items.length ? d.items.map((n, i) => (
        <div key={i} className={"notif" + (n.read ? "" : " unread")}><span className={"lv " + n.level} /><div><b>{n.title}</b>
          <div className="small" style={{ whiteSpace: "pre-wrap" }}><Blur text={n.message} /></div>
          <div className="small muted">{L.fmtTime(n.t) + (n.delivery && n.delivery.length ? " · sent: " + n.delivery.join(", ") : "")}</div></div></div>
      )) : <div className="notif"><span className="muted">Nothing yet.</span></div>}
    </div>
  </>);
}

/* ------------------------------------------------------------------ Logs */
const LV = { error: ["error", "!"], warning: ["warning", "⚠"], info: ["info", "i"] };
function Issue({ x }) {
  return (
    <div className={"issue " + x.level}><span className="ic">{LV[x.level] ? LV[x.level][1] : "i"}</span><span>
      <b>{x.title}</b>{x.count ? <span className="muted small">{" ×" + x.count + (x.last ? " · last " + x.last : "")}</span> : null}<br />
      {x.what}<br /><b>What to do:</b> {x.fix}
      {x.example && <div className="mono muted small" style={{ marginTop: 4 }}><Blur text={x.example} /></div>}
    </span></div>
  );
}
const VIA = { dashboard: "Dashboard", discord: "Discord", game: "In game" };
function Activity() {
  const [who, setWho] = useState(""), [via, setVia] = useState(""), [d, setD] = useState(null);
  const load = useCallback(async () => { try { setD(await L.api("/api/activity?limit=500&who=" + encodeURIComponent(who) + "&via=" + encodeURIComponent(via))); } catch (e) { L.toast(e.message); } }, [who, via]);
  useEffect(() => { load(); }, []);                 // eslint-disable-line react-hooks/exhaustive-deps
  const { SERVERS } = S();
  return (
    <div className="card tight" style={{ padding: "12px 14px" }}>
      <p className="small muted" style={{ margin: "0 0 8px" }}>Every change made by an admin: in the dashboard, with Discord commands and with in-game admin commands - who, what, when and from where.</p>
      <div className="row" style={{ gap: 8, marginBottom: 8 }}>
        <input placeholder="Filter by name" value={who} onChange={e => setWho(e.target.value)} style={{ maxWidth: 200 }} />
        <select value={via} onChange={e => setVia(e.target.value)} style={{ width: "auto" }}><option value="">Everywhere</option>{Object.entries(VIA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <button className="btn sm" onClick={load}>Filter</button></div>
      {!d ? <p className="muted small">Loading…</p> : d.rows.length ? (
        <table className="small" style={{ width: "100%", borderCollapse: "collapse" }}><tbody>
          {d.rows.map((r, i) => (
            <tr key={i} style={{ borderTop: "1px solid var(--line)" }}>
              <td style={{ padding: "4px 6px", whiteSpace: "nowrap" }} className="muted">{L.fmtTime(r.t)}</td>
              <td style={{ padding: "4px 6px" }}><b>{r.who}</b></td>
              <td style={{ padding: "4px 6px" }}>{r.ok === false && <span style={{ color: "var(--crit-ink)" }}>✕ </span>}{r.action}
                {SERVERS.length > 1 && r.server && <span className="muted">{" (" + ((SERVERS.find(x => x.id === r.server) || {}).name || r.server) + ")"}</span>}</td>
              <td style={{ padding: "4px 6px" }} className="muted">{VIA[r.via] || r.via}{r.ip && <> · <Ip>{r.ip}</Ip></>}</td>
            </tr>))}
        </tbody></table>) : <p className="muted small">Nothing yet.</p>}
    </div>
  );
}
export function Logs({ reload }) {
  const ses = S().SESSION, canAct = ses.role === "owner" || ses.role === "admin";
  const [view, setView] = useState("server"), [lines, setLines] = useState(300);
  const [d, setD] = useState(null), [err, setErr] = useState("");
  const [open, setOpen] = useState({});              // line number -> explanation (or null while loading)
  const [explained, setExplained] = useState(null);
  const box = useRef(null), follow = useRef(true), first = useRef(true);
  const draw = useCallback(async () => {
    try { setD(await L.api("/api/logs?lines=" + lines)); setErr(""); } catch (e) { if (e.message !== "Please log in") setErr(e.message); }
  }, [lines]);
  useEffect(() => { setView("server"); setOpen({}); setExplained(null); follow.current = true; first.current = true; }, [reload]);
  useEffect(() => {
    if (view !== "server") return;
    draw();
    const t = setInterval(() => { if (!Object.keys(open).length) draw(); }, 5000);    // an explanation is open - don't redraw under it
    return () => clearInterval(t);
  }, [draw, view, open, reload]);
  // keep following the end of the log, unless you scrolled up or opened a line
  const atBottom = useRef(true);
  const onScroll = () => { const b = box.current; atBottom.current = b.scrollTop + b.clientHeight >= b.scrollHeight - 30; };
  useEffect(() => { const b = box.current; if (b && (first.current || (follow.current && atBottom.current))) { b.scrollTop = b.scrollHeight; first.current = false; } }, [d]);
  const explainAll = async () => {
    setExplained("loading");
    try { setExplained(await L.api("/api/logs/explain")); } catch (e) { setExplained(null); L.toast(e.message); }
  };
  const explainLine = async (i, text) => {
    if (i in open) { const o = { ...open }; delete o[i]; return setOpen(o); }
    follow.current = false;
    setOpen(o => ({ ...o, [i]: null }));
    try { const r = await L.api("/api/logs/explain", { json: { line: text } }); setOpen(o => ({ ...o, [i]: r.explain || false })); }
    catch (e) { L.toast(e.message); setOpen(o => { const x = { ...o }; delete x[i]; return x; }); }
  };
  const tabLink = (v, label) => <a href="#" onClick={e => { e.preventDefault(); if (v === "server") L.bridge.show("logs"); else setView(v); }}>{view === v ? <b>{label}</b> : label}</a>;
  return (<>
    <div className="row"><div><h1>Logs</h1><p className="sub">{canAct ? <>{tabLink("server", "Server log")} · {tabLink("activity", "Activity log")}</> : "Live view of Server.log. Refreshes every 5 seconds."}</p></div><span className="spacer" />
      {view === "server" && <select value={lines} onChange={e => setLines(+e.target.value)} style={{ width: "auto" }}><option value="300">Last 300 lines</option><option value="1000">Last 1000 lines</option><option value="2000">Last 2000 lines</option></select>}</div>
    {view === "activity" ? <Activity /> : <>
      {err && <div className="banner bad">{err}</div>}
      {d && d.hints.length > 0 && <div className="card" style={{ marginBottom: 16 }}><h2>What the log is telling you</h2>
        {d.hints.map((x, i) => <div key={i} className="issue warning"><span className="ic">⚠</span><span><b>{x.title + "."}</b> {x.text}<div className="mono muted" style={{ marginTop: 4 }}>{x.line}</div></span></div>)}</div>}
      <div className="row" style={{ margin: "0 0 10px", gap: 8 }}><button className="btn sm" onClick={explainAll}>Explain the whole log</button><span className="small muted">or click a red or yellow line</span></div>
      {explained === "loading" ? <p className="small muted">Reading the log…</p> : explained && (
        <div className="card" style={{ marginBottom: 16 }}><div className="row"><h2 style={{ margin: 0 }}>What happened</h2><span className="spacer" /><button className="btn sm" onClick={() => setExplained(null)}>Close</button></div>
          <p className="small muted">{explained.note + " Grouped by problem, most important first."}</p>
          {explained.groups.length ? explained.groups.map((x, i) => <Issue key={i} x={x} />) : <div className="issue info"><span className="ic">✓</span><span>No errors or warnings found.</span></div>}</div>)}
      <div className="log" ref={box} onScroll={onScroll}>
        {!d ? null : d.lines.length ? d.lines.map((l, i) => {
          const cls = /\[ERROR\]/.test(l) ? "e" : /\[WARN\]/.test(l) ? "w" : "";
          return <Fragment key={i}>
            <div className={cls} onClick={cls ? () => explainLine(i, l) : undefined}><Blur text={l} /></div>
            {i in open && <div className="xpl" style={{ whiteSpace: "normal", fontFamily: "inherit", margin: "4px 0 8px" }}>
              {open[i] === null ? <p className="small muted">…</p> : open[i] ? <Issue x={open[i]} /> : <div className="issue info"><span className="ic">i</span><span>Nothing known about this line.</span></div>}</div>}
          </Fragment>;
        }) : <span className="muted">The log is empty.</span>}
      </div>
    </>}
  </>);
}
