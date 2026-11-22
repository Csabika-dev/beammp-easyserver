// Health page: health report, "someone can't join?", automatic port forwarding, network check.
import { useEffect, useState } from "react";
import * as L from "./legacy.js";
import { Blur, Ip } from "./pages.jsx";
import { cacheGet, cachedApi, Oops, Skel, SkelCard } from "./ui.jsx";
import { Performance } from "./extras.jsx";

const MARK = { pass: ["ok", "✓"], ok: ["ok", "✓"], fail: ["bad", "✕"], bad: ["bad", "✕"], warn: ["warn", "!"], info: ["info", "i"] };
const Check = ({ state, children }) => { const k = MARK[state] || MARK.info; return <div className="check"><span className={"mark " + k[0]}>{k[1]}</span><div>{children}</div></div>; };
const Msg = ({ text }) => <p className="small muted">{text}</p>;
const srv = () => encodeURIComponent(L.state().SERVER || "");

/* ---------------- server health report */
function HealthReport({ tick }) {
  const [st, setSt] = useState(() => ({ h: cacheGet("/api/health") ?? null, reps: cacheGet("/api/health/reports") ?? null, err: "" }));
  const [deep, setDeep] = useState(false);
  const load = async d => {
    setDeep(!!d);
    try { const [h, reps] = await Promise.all([d ? L.api("/api/health?deep=1") : cachedApi("/api/health"), cachedApi("/api/health/reports")]); setSt({ h, reps, err: "" }); }
    catch (e) { setSt(s => ({ ...s, err: e.message })); }
    setDeep(false);
  };
  useEffect(() => { load(false); }, [tick]);
  const { h, reps, err } = st;
  if (err && !h) return <div className="card"><Msg text={err} /></div>;
  if (!h) return <SkelCard lines={7} />;
  const pill = h.overall === "fail" ? <span className="badge bad">{h.failed > 1 ? `${h.failed} problems` : `${h.failed} problem`}</span>
    : h.overall === "warn" ? <span className="badge warn">{h.warned > 1 ? `${h.warned} warnings` : `${h.warned} warning`}</span> : <span className="badge good">All good</span>;
  const word = s => s === "pass" ? "Passed" : s === "fail" ? "Failed" : s === "warn" ? "Warning" : "";
  return (<div className="card">
    <div className="row"><h2 style={{ margin: 0 }}>Server health report {pill}</h2><span className="spacer" />
      <button className="btn sm" onClick={() => load(false)}>Check again</button>
      <button className="btn sm" disabled={deep} onClick={() => load(true)}>{deep ? "Checking…" : "Full check"}</button>
      <a className={"btn sm" + (h.failed ? " primary" : "")} href={"/api/health/report?srv=" + srv()} download>Download diagnostic report</a></div>
    <div style={{ marginTop: 8 }}>{h.checks.map((c, i) => <Check key={i} state={c.state}>
      <b>{c.title}</b> <span className="small muted">{word(c.state)}</span>
      <div className="small muted"><Blur text={c.detail} /></div>
      {c.fix && <div className="small"><b>What to do:</b> <Blur text={c.fix} /></div>}
    </Check>)}</div>
    <p className="small muted" style={{ margin: "8px 0 0" }}>{h.failed
      ? <>Something failed - the <b>diagnostic report</b> has everything needed to get help (versions, checks, settings, the end of the log). Keys, tokens and your public IP are removed from it.</>
      : "The diagnostic report collects versions, these checks, settings and the end of the log for when you need help - keys, tokens and your public IP are removed."}{" The dashboard re-checks every 30 minutes and saves a report by itself when something breaks."}</p>
    {reps && reps.reports.length > 0 && <details style={{ marginTop: 6 }}><summary className="small"><b>{`Saved reports (${reps.reports.length})`}</b></summary>
      {reps.reports.map(r => <div className="row small" style={{ padding: "3px 0" }} key={r.file}><span>{L.fmtTime(r.t)}</span><span className="spacer" />
        <a href={"/api/health/saved?file=" + encodeURIComponent(r.file) + "&srv=" + srv()} download>Download</a></div>)}</details>}
  </div>);
}

/* ---------------- someone can't join? */
function JoinDoctor() {
  const [name, setName] = useState(""), [busy, setBusy] = useState(false), [found, setFound] = useState(null);
  const go = async () => {
    setBusy(true);
    try { setFound((await L.api("/api/health/join?player=" + encodeURIComponent(name.trim()))).findings); } catch (e) { L.toast(e.message); }
    setBusy(false);
  };
  return (<div className="card" style={{ marginTop: 16 }}>
    <h2>Someone can't join?</h2><p className="small muted">Type their BeamMP name - the dashboard looks at what the server recorded for them (refused, banned, not on the list, server full…) and the usual network problems.</p>
    <div className="row"><input type="text" placeholder="Player name (optional)" maxLength={40} style={{ maxWidth: 260 }} autoComplete="off" spellCheck={false}
      value={name} onChange={e => setName(e.target.value)} onKeyDown={e => { if (e.key === "Enter") go(); }} />
      <button className="btn primary" disabled={busy} onClick={go}>Find out why</button></div>
    {found && <div style={{ marginTop: 10 }}>{found.map((f, i) => <Check key={i} state={f.state}><b>{f.title}</b><div className="small muted" style={{ whiteSpace: "pre-wrap" }}><Blur text={f.text} /></div></Check>)}</div>}
  </div>);
}

/* ---------------- automatic port forwarding (UPnP) */
function PortForward({ onChange }) {
  const [d, setD] = useState(null), [err, setErr] = useState(""), [busy, setBusy] = useState("");
  const load = async check => {
    try { setD(await L.api("/api/upnp" + (check ? "?check=1" : ""))); setErr(""); } catch (e) { setErr(e.message); }
    setBusy("");
  };
  useEffect(() => { load(false); }, []);
  if (err && !d) return <div className="card" style={{ marginTop: 16 }}><Msg text={err} /></div>;
  if (!d) return <SkelCard lines={2} style={{ marginTop: 16 }} />;
  const ports = [...new Set(d.ports.map(x => x.port))].join(", ");
  const relayTxt = "\"Hide my IP\" is on: players join through the relay, so nothing has to be opened on your router.";
  const send = async (body, key) => {
    setBusy(key);
    try { const r = await L.api("/api/upnp", { json: body }); L.toast(r.note, 8000); } catch (e) { L.toast(e.message, 8000); }
    load(false); if ("on" in body) onChange();
  };
  if (d.mac) {
    const ip = d.mac_ip ? <Ip>{d.mac_ip}</Ip> : "your Mac";
    const badge = d.relay ? <span className="badge">Not needed</span> : !d.on ? <span className="badge">Off</span> : d.mac_upnp === "ok" ? <span className="badge good">{`Port ${ports} open`}</span> : <span className="badge warn">Problem</span>;
    return (<div className="card" style={{ marginTop: 16 }}>
      <div className="row"><b>Automatic port forwarding</b><span className="spacer" />{badge}</div>
      <p className="small muted" style={{ margin: "8px 0 0" }}>{d.relay ? relayTxt
        : d.on ? (d.mac_upnp === "ok"
          ? <>{`Your Mac asks the router to keep port ${ports} (TCP + UDP) open to `}{ip}{d.mac_upnp_at ? ` while the Mac is on, and checks it every 20 minutes (last time ${L.fmtTime(d.mac_upnp_at)}).` : " while the Mac is on, and checks it every 20 minutes."}</>
          : <>{d.state && d.state.error ? `Your Mac asked the router to open port ${ports} but it said no (${d.state.error}). Forward port ${ports} TCP + UDP to ` : `Your Mac asked the router to open port ${ports} but it said no. Forward port ${ports} TCP + UDP to `}{ip}{" by hand in your router's settings page, or turn on \"Hide my IP\" (Settings)."}</>)
        : <>{`Forward port ${ports} TCP + UDP to `}{ip}{" in your router's settings page (search \""}<i>your router model</i>{" port forwarding\"). Or run the Mac installer again and pick "}<b>Do it for me</b>{" to have the Mac open it."}</>}</p>
    </div>);
  }
  const s = d.state || {}, rows = s.ports || [];
  const needed = d.mode === "needed", sleeping = d.on && needed && !d.is_open && !s.error;
  const allOk = d.on && rows.length && rows.every(r => r.ok) && !s.error;
  const badge = d.relay ? <span className="badge">Not needed</span> : sleeping ? <span className="badge">Closed - opens when needed</span>
    : allOk ? <span className="badge good">{`Port ${ports} open`}</span> : d.on ? <span className="badge warn">Problem</span> : <span className="badge">Off</span>;
  const left = d.open_until - Date.now() / 1000;
  const modeTxt = !d.on || d.relay ? "" : needed
    ? (d.is_open ? (d.players ? `Open - ${d.players} playing. Closes ${Math.round(d.idle / 60)} minutes after the last player leaves.` : left > 0 ? `Open for about ${L.fmtDur(left)} more (or as long as someone is playing).` : "Closing…")
      : "Closed right now, so nobody can reach your server from outside. Copying an invite or /join in Discord opens it.")
    : "Open all the time.";
  const B = ({ k, cls = "btn sm", body, label, wait }) => <button className={cls} disabled={busy === k} onClick={() => send(body, k)}>{busy === k && wait ? wait : label}</button>;
  return (<div className="card" style={{ marginTop: 16 }}>
    <div className="row"><h2 style={{ margin: 0 }}>Automatic port forwarding {badge}</h2><span className="spacer" />
      {d.relay ? null : d.on ? <><button className="btn sm" disabled={busy === "check"} onClick={() => { setBusy("check"); load(true); }}>Check again</button>
        <B k="off" body={{ on: false }} label="Turn off" wait="Closing…" /></>
        : <B k="on" cls="btn primary" body={{ on: true }} label={`Open port ${ports} automatically`} wait="Asking your router…" />}</div>
    <p className="small muted" style={{ margin: "8px 0 0" }}>{d.relay ? relayTxt
      : `Friends outside your home can only join when your router forwards port ${ports} (TCP + UDP) to this computer. Most routers let the dashboard do that itself (UPnP) - one click, no router settings page. It's checked every 20 minutes and put back after a router restart.`}</p>
    {d.on && !d.relay && <>
      <div className="row" style={{ marginTop: 10, flexWrap: "wrap", gap: 6 }}><span className="small"><b>When:</b></span>
        <B k="always" cls={"btn sm" + (needed ? "" : " on")} body={{ mode: "always" }} label="Always open" />
        <B k="needed" cls={"btn sm" + (needed ? " on" : "")} body={{ mode: "needed" }} label="Only when needed" />
        {needed && (d.is_open ? <B k="close" body={{ close_now: true }} label="Close now" /> : <B k="open" body={{ open_for: 3600 }} label="Open for 1 hour" />)}</div>
      <p className="small muted" style={{ margin: "6px 0 0" }}>{modeTxt}{needed ? " Your router can't tell the dashboard that someone is knocking on a closed port, so the port opens when you invite people, press Open, or a friend types /join in your Discord (when the Discord bot is set up), and stays open while anyone plays. Strangers from the public server list can't join while it's closed." : ""}</p>
    </>}
    {s.router && <p className="small" style={{ margin: "6px 0 0" }}>Router: <b>{s.router}</b>{s.external_ip && <>{" · internet address "}<Ip>{s.external_ip}</Ip></>}{s.local_ip && <>{" · this computer "}<Ip>{s.local_ip}</Ip></>}</p>}
    {rows.length > 0 && <div style={{ marginTop: 6 }}>{rows.map((r, i) => <Check key={i} state={r.ok ? "ok" : "bad"}><b>{`${r.port} ${r.proto}`}</b> <span className="small muted">{r.ok ? (r.lease ? "open (renewed every day)" : "open") : r.error}</span></Check>)}</div>}
    {s.error && <div className="banner warn" style={{ margin: "10px 0 0" }}><span className="small">{s.error}</span></div>}
    {!d.relay && (s.error || rows.some(r => !r.ok)) && <p className="small muted" style={{ margin: "8px 0 0" }}>{`No luck? Forward port ${ports} TCP + UDP to `}{s.local_ip ? <Ip>{s.local_ip}</Ip> : "this computer"}{" by hand in your router's settings page (search \""}<i>your router model</i>{" port forwarding\"), or turn on \"Hide my IP\" (Settings) to use a relay instead."}</p>}
  </div>);
}

/* ---------------- network check */
function NetworkCheck({ tick }) {
  const [d, setD] = useState(() => cacheGet("/api/network") ?? null), [err, setErr] = useState(""), [deep, setDeep] = useState(false);
  const load = async dp => {
    setDeep(!!dp);
    try { setD(await (dp ? L.api("/api/network?deep=1") : cachedApi("/api/network"))); setErr(""); } catch (e) { setErr(e.message); }
    setDeep(false);
  };
  useEffect(() => { load(false); }, [tick]);
  if (!d) return <div style={{ marginTop: 24 }}>{err ? <Oops err={err} retry={() => load(false)} /> : <><Skel w={180} h={20} /><Skel w="45%" style={{ margin: "10px 0 16px" }} /><div className="grid g3">{[0, 1, 2].map(i => <SkelCard key={i} lines={2} />)}</div></>}</div>;
  const Stat = ({ label, v, note, mono = true }) => <div className="card stat"><div className="label">{label}</div><div className={"value" + (mono ? " mono" : "")}>{v}</div><div className="note">{note}</div></div>;
  return (<div style={{ marginTop: 24 }}>
    <div className="row"><div><h2 style={{ fontSize: 20 }}>Network check</h2><p className="sub">{`Finds out whether players can reach your server on port ${d.port}.`}</p></div><span className="spacer" />
      <button className="btn" onClick={() => load(false)}>Check again</button>
      <button className="btn primary" disabled={deep} onClick={() => load(true)}>{deep ? "Checking…" : "Check server list"}</button></div>
    <div className="grid g3" style={{ marginBottom: 16 }}>
      <Stat label="Home network address" v={<Ip>{d.lan_ip + ":" + d.port}</Ip>} note="For friends on your Wi-Fi" />
      {d.relay ? <Stat label="Internet address (relay)" v={<Ip>{d.relay}</Ip>} note="Your home address is hidden" />
        : <Stat label="Internet address" v={d.public_ip ? <Ip>{d.public_ip + ":" + d.port}</Ip> : "unknown"} note="For friends anywhere else" />}
      <Stat label="Port" v={d.port} mono={false} note={d.relay ? "No router port forward needed" : "Forward TCP + UDP on your router"} />
    </div>
    <div className="card tight">{d.checks.map((c, i) => <Check key={i} state={c.state}><b>{c.name}</b><div className="small muted"><Blur text={c.detail} /></div></Check>)}</div>
    {d.tips.length > 0 && <div className="card" style={{ marginTop: 16 }}><h2>What to do</h2><ul>{d.tips.map((t, i) => <li key={i}><Blur text={t} /></li>)}</ul></div>}
    <p className="small muted" style={{ marginTop: 12 }}>"Check server list" downloads BeamMP's public list (a few MB) to see whether your server shows up - the most reliable test that internet players can find you.</p>
  </div>);
}

export function Health({ reload }) {
  const [net, setNet] = useState(0);
  return (<>
    <div className="row"><div><h1>Health</h1><p className="sub">Is everything working? What's wrong, and what to do about it.</p></div></div>
    <HealthReport tick={reload} />
    <PortForward key={reload} onChange={() => setNet(n => n + 1)} />
    <JoinDoctor />
    <NetworkCheck tick={reload + ":" + net} />
    <Performance key={"p" + reload} />
  </>);
}
