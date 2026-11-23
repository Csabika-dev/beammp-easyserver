// Lap times, player profiles, the performance graphs, the first-time checklist and quick search (Ctrl+K).
import { useEffect, useMemo, useRef, useState } from "react";
import * as L from "./legacy.js";
import { CardWait, Empty, Toggle, chk, useLoad } from "./ui.jsx";
import { PLACES } from "./search-places.js";

const S = () => L.state();

/* ================================================================== lap times (Players page) */
export function LapTimes({ canEdit }) {
  const [d, again, v, err] = useLoad("/api/laps");
  const [open, setOpen] = useState(null);
  if (!d) return <CardWait err={err} retry={again} style={{ marginTop: 16 }} />;
  const save = async body => { try { const r = await L.api("/api/laps", { json: body }); L.toast(r.note, 6000); again(); } catch (e) { L.toast(e.message, 6000); } };
  const rename = t => { const n = (prompt("New name for " + t.name, t.name) || "").trim(); if (n && n !== t.name) save({ action: "rename", id: t.id, name: n }); };
  const del = t => {
    // gone at once, really deleted after the Undo time
    L.undoable(`${t.name} deleted.`, "/api/laps", { action: "delete", id: t.id }, { onUndo: again, after: again });
    setOpen(null);
  };
  const here = d.tracks.filter(t => !t.map || t.map === d.map), other = d.tracks.filter(t => t.map && t.map !== d.map);
  const Board = ({ t }) => <div className="card tight laptrack">
    <div className="row" style={{ padding: "12px 14px 6px" }}>
      <div><b>{t.name}</b><div className="small muted">{`${t.kind === "sprint" ? "Sprint" : "Loop"} · ${t.checkpoints === 1 ? "1 checkpoint" : `${t.checkpoints} checkpoints`}${t.map ? " · " + t.map : ""} · ${t.drivers === 1 ? "1 driver" : `${t.drivers} drivers`}`}</div></div>
      <span className="spacer" />
      {canEdit && <button className="btn sm ghost" aria-expanded={open === t.id} onClick={() => setOpen(open === t.id ? null : t.id)}>Manage</button>}</div>
    {open === t.id && <div className="row" style={{ padding: "0 14px 10px", gap: 6 }}>
      <button className="btn sm" onClick={() => rename(t)}>Rename</button>
      <button className="btn sm" onClick={() => { if (confirm(`Clear every time on ${t.name}? The track stays.`)) save({ action: "clear", id: t.id }); }}>Clear times</button>
      <button className="btn sm danger" onClick={() => del(t)}>Delete track</button></div>}
    {t.top.length ? <table><tbody>{t.top.map((r, i) => <tr key={r.name}>
      <td className="num muted" style={{ width: 34 }}>{i + 1}</td><td><Who name={r.name} /></td><td className="num mono">{r.time}</td>
      <td className="small muted">{r.car}</td>
      {canEdit && open === t.id && <td className="num"><button className="btn sm ghost" title="Remove this time" onClick={() => save({ action: "remove_time", id: t.id, name: r.name })}>Remove</button></td>}</tr>)}</tbody></table>
      : <p className="small muted" style={{ padding: "0 14px 12px", margin: 0 }}>No times yet - cross the start line to set one.</p>}
  </div>;
  return (<div className="card" style={{ marginTop: 16 }} key={v}>
    <div className="row"><h2 style={{ margin: 0 }}>Lap times</h2><span className="spacer" />
      <span className={"pill " + (d.on ? "good" : "")}><span className="dot" />{d.on ? "On" : "Off"}</span></div>
    <p className="small muted">{"Make a track in the game and every lap on it is timed. Players see the best times with /laps, and new records are announced in the chat."}</p>
    {canEdit && <>
      <Toggle id="lp_on" on={d.on} title="Time laps on this server">Admins (Config → Moderation) make tracks in the game with /track</Toggle>
      <Toggle id="lp_pub" on={d.public} title="Show the best times on the public status page">{d.status_page ? "The top 10 of each track on this map" : "Turn the status page on under Settings first"}</Toggle>
      <div className="row" style={{ gap: 8, margin: "6px 0 4px" }}>
        <label className="small" htmlFor="lp_rad">How wide the start line and checkpoints are</label>
        <select id="lp_rad" defaultValue={d.radius} style={{ width: "auto" }}>{d.radii.map(r => <option key={r} value={r}>{`${r} m`}</option>)}</select>
        <span className="spacer" /><button className="btn primary sm" onClick={() => save({ on: chk("lp_on"), public: chk("lp_pub"), radius: Number(document.getElementById("lp_rad").value) })}>Save</button></div>
    </>}
    <details className="small" style={{ margin: "10px 0" }}><summary>{"How to make a track"}</summary>
      <ol style={{ margin: "8px 0 0", paddingLeft: 20, lineHeight: 1.7 }}>
        <li>{"Drive to the start line and type /track new followed by a name, like /track new Canyon run."}</li>
        <li>{"Drive the route and type /track cp at each checkpoint, in order. Checkpoints stop people cutting corners."}</li>
        <li>{"For a lap that comes back to the start, type /track done. For a point-to-point sprint, type /track finish where it ends."}</li>
      </ol>
      <p className="muted" style={{ margin: "6px 0 0" }}>{"Made a mistake? /track undo removes the last checkpoint and /track cancel starts again. Tracks belong to the map they were made on. Laps are timed with each car's own game clock, so lag doesn't change the time."}</p>
    </details>
    {!d.plugin && <p className="small" style={{ color: "var(--warn-ink)" }}>The EasyServer plugin isn't on this server yet - run the installer again.</p>}
    {here.length ? <div className="grid g2" style={{ gap: 12 }}>{here.map(t => <Board key={t.id} t={t} />)}</div>
      : <Empty title="No tracks on this map yet">{d.on ? "An admin makes one in the game: drive to the start line and type /track new followed by a name." : "Turn lap times on, then make a track in the game with /track new."}</Empty>}
    {other.length > 0 && <details className="small" style={{ marginTop: 12 }}><summary>{other.length === 1 ? "1 track on other maps" : `${other.length} tracks on other maps`}</summary>
      <div className="grid g2" style={{ gap: 12, marginTop: 8 }}>{other.map(t => <Board key={t.id} t={t} />)}</div></details>}
  </div>);
}

/* ================================================================== player profiles */
// Any player name on the Players page opens their profile (for people who may moderate).
const PROFILE = { open: null };
export const Who = ({ name, bold = true }) => {
  const can = canSeeProfiles();
  if (!can) return bold ? <b>{name}</b> : <span>{name}</span>;
  return <button type="button" className={"who" + (bold ? " b" : "")} onClick={() => PROFILE.open && PROFILE.open(name)} title={`${name}'s profile`}>{name}</button>;
};
function canSeeProfiles() {
  const r = L.myRole();
  if (r && r.perms) return r.perms.includes("players");
  return (r ? r.role : S().SESSION.role) !== "viewer";
}

const evText = h => {
  const by = h.by ? ` by ${h.by}` : "";
  switch (h.ev) {
    case "kick": return `Kicked${by}${h.reason ? ": " + h.reason : ""}`;
    case "ban": return `Banned${by} ${h.until ? "until " + L.fmtTime(h.until) : "forever"}${h.reason ? ": " + h.reason : ""}`;
    case "unban": return `Unbanned${by}`;
    case "mute": return `Muted for ${h.minutes} min${by}`;
    case "report": return `Reported by ${h.by}${h.reason ? ": " + h.reason : ""}`;
    case "votekick": return `Vote kick started by ${h.by}${h.reason ? ": " + h.reason : ""}`;
    case "vehblock": return `Spawned a blocked car (${h.jbm || "?"})`;
    case "vehspam": return "Spawned cars too fast";
    case "refused": return h.why === "banned" ? "Tried to join while banned" : h.why === "maintenance" ? "Tried to join during maintenance" : "Wasn't let in";
    case "denied": return "Not on the allow-list";
    case "lap": return h.record ? `Track record on ${h.track}: ${h.time}` : `Personal best on ${h.track}: ${h.time}`;
    case "racepos": return `Race on ${h.track}: P${h.pos} of ${h.of}${h.time ? " in " + h.time : ""}`;
    case "bust": return h.me === "cop" ? `Busted ${h.robber} (cops and robbers)` : `Busted by ${h.cop} (cops and robbers)`;
    case "badge": return `Earned the badge ${h.title || ""}`;
    case "trap": return `Speed trap record at ${h.trap}: ${Math.round(h.kmh || 0)} km/h`;
    default: return h.ev;
  }
};
const evKind = ev => ["kick", "ban", "vehblock", "vehspam", "refused"].includes(ev) ? "bad" : ["mute", "report", "votekick", "denied"].includes(ev) ? "warn" : "info";

export function ProfileHost({ onBan }) {
  const [name, setName] = useState(null);
  useEffect(() => { PROFILE.open = setName; return () => { PROFILE.open = null; }; }, []);
  return name ? <Profile name={name} close={() => setName(null)} onBan={onBan} /> : null;
}

function Profile({ name, close, onBan }) {
  const [p, setP] = useState(null), [err, setErr] = useState(""), [note, setNote] = useState("");
  const box = useRef(null), back = useRef(document.activeElement);
  const load = async () => { try { setP(await L.api("/api/players/profile?name=" + encodeURIComponent(name))); setErr(""); } catch (e) { setErr(e.message); } };
  useEffect(() => { load(); }, [name]);
  useEffect(() => {
    const key = e => { if (e.key === "Escape") close(); };
    addEventListener("keydown", key);
    box.current && box.current.focus();
    return () => { removeEventListener("keydown", key); back.current && back.current.focus && back.current.focus(); };
  }, []);
  const addNote = async () => {
    const t = note.trim(); if (!t) return;
    try { const r = await L.api("/api/players/note", { json: { name: p.name, text: t } }); setNote(""); setP({ ...p, notes: r.notes }); } catch (e) { L.toast(e.message, 6000); }
  };
  const delNote = async id => { try { const r = await L.api("/api/players/note", { json: { name: p.name, delete: id } }); setP({ ...p, notes: r.notes }); } catch (e) { L.toast(e.message); } };
  const act = async body => { try { const r = await L.api("/api/players/act", { json: body }); L.toast(r.note); } catch (e) { L.toast(e.message); } };
  const Stat = ({ label, value }) => <div className="pstat"><div className="small muted">{label}</div><b>{value}</b></div>;
  return (<div className="modalbg" onClick={e => { if (e.target === e.currentTarget) close(); }}>
    <div className="card profile" role="dialog" aria-modal="true" aria-label={`${name}'s profile`} tabIndex={-1} ref={box}>
      <div className="row"><h2 style={{ margin: 0, fontSize: 19 }}>{p ? p.name : name}</h2>
        {p && p.online && <span className="pill good"><span className="dot" />Online</span>}
        {p && p.ban && <span className="pill bad"><span className="dot" />{p.ban.until ? `Banned until ${L.fmtTime(p.ban.until)}` : "Banned"}</span>}
        <span className="spacer" /><button className="btn sm" onClick={close}>Close</button></div>
      {!p ? (err ? <p className="small muted">{err}</p> : <div className="skel" style={{ height: 120, marginTop: 14 }} />) : <>
        {!p.seen && <p className="small muted">This name hasn't played on this server in the last year.</p>}
        <div className="pstats">
          <Stat label="Time played" value={L.fmtDur(p.seconds)} />
          <Stat label="Last 30 days" value={L.fmtDur(p.seconds_30d)} />
          <Stat label="Sessions" value={p.sessions} />
          <Stat label="Last seen" value={p.online ? "Now" : p.last_seen ? L.ago(p.last_seen) : "-"} />
        </div>
        {p.first_seen && <p className="small muted" style={{ margin: "4px 0 0" }}>{`First played ${L.fmtTime(p.first_seen)}${p.reports_by ? ` · sent ${p.reports_by === 1 ? "1 report" : p.reports_by + " reports"}` : ""}`}</p>}
        <div className="row" style={{ gap: 6, marginTop: 12 }}>
          {p.online && <><button className="btn sm" onClick={() => act({ action: "mute", name: p.name, minutes: 10 })}>Mute 10 min</button>
            <button className="btn sm" onClick={() => act({ action: "kick", name: p.name, minutes: 10 })}>Kick</button></>}
          {!p.ban && onBan && <button className="btn sm danger" onClick={() => { close(); onBan(p.name); }}>Ban…</button>}</div>
        {(p.laps.length > 0 || p.records) && <><h3 className="ph">Driving</h3>
          <div className="small">{p.laps.map(l => <div key={l.track}>{`${l.track}: `}<span className="mono">{l.time}</span>{` · P${l.pos} of ${l.of}${l.car ? " · " + l.car : ""}`}</div>)}
            {p.records && <div className="muted">{`Top speed ${p.records.speed} km/h · ${p.records.dist} km driven`}</div>}</div></>}
        {p.games && (p.games.all || p.games.badges.length > 0) && <><h3 className="ph">Games</h3>
          <div className="small">{p.games.all && <div>{[`${p.games.all.races === 1 ? "1 race" : p.games.all.races + " races"}, ${p.games.all.wins === 1 ? "1 win" : p.games.all.wins + " wins"}`,
            p.games.all.cnr ? `${p.games.all.cnr === 1 ? "1 game" : p.games.all.cnr + " games"} of cops and robbers: ${p.games.all.busts} busts, ${p.games.all.escapes} getaways` : null,
            `${p.games.all.laps === 1 ? "1 timed lap" : p.games.all.laps + " timed laps"}`].filter(Boolean).join(" · ")}</div>}
            {p.games.badges.length > 0 && <div className="muted">{"Badges: " + p.games.badges.map(b => b.title).join(", ")}</div>}</div></>}
        <h3 className="ph">Notes <span className="small muted" style={{ fontWeight: 400 }}>only your team sees these</span></h3>
        <div className="row" style={{ gap: 8, flexWrap: "nowrap" }}><input type="text" maxLength={500} placeholder="Warned about ramming at spawn…" value={note}
          onChange={e => setNote(e.target.value)} onKeyDown={e => { if (e.key === "Enter") addNote(); }} /><button className="btn sm primary" onClick={addNote}>Add</button></div>
        {p.notes.map(n => <div key={n.id} className="pnote"><div>{n.text}</div><div className="small muted">{`${n.by} · ${L.fmtTime(n.t)} · `}
          <button type="button" className="linkbtn" onClick={() => delNote(n.id)}>Delete</button></div></div>)}
        <h3 className="ph">History</h3>
        {p.history.length ? <div className="phist">{p.history.map((h, i) => <div key={i} className={"issue " + evKind(h.ev)}>
          <span className="ic">{evKind(h.ev) === "bad" ? "!" : evKind(h.ev) === "warn" ? "⚠" : "i"}</span><span>{evText(h)}</span><span className="ln">{L.ago(h.t)}</span></div>)}</div>
          : <p className="small muted">Nothing on record - no kicks, bans, mutes or reports.</p>}
      </>}
    </div></div>);
}

/* ================================================================== performance (Health page) */
const SERIES = [
  { i: 1, title: "Processor", unit: "%", max: 100, fmt: v => Math.round(v) + "%" },
  { i: 2, title: "Memory used", unit: "%", max: 100, fmt: v => Math.round(v) + "%" },
  { i: 3, title: "Upload", unit: "Mbit/s", fmt: v => v.toFixed(1) + " Mbit/s" },
  { i: 4, title: "Players", unit: "", fmt: v => String(Math.round(v)) },
  { i: 5, title: "Average ping", unit: "ms", fmt: v => Math.round(v) + " ms" },
];

function LineChart({ rows, s, range }) {
  const ref = useRef(null), [w, setW] = useState(320), [hover, setHover] = useState(null);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const ro = new ResizeObserver(() => setW(Math.max(200, el.clientWidth)));
    ro.observe(el); return () => ro.disconnect();
  }, []);
  const H = 110, P = 4;
  const pts = rows.filter(r => r[s.i] !== null && r[s.i] !== undefined);
  const t0 = rows.length ? rows[0][0] : 0, t1 = rows.length ? rows[rows.length - 1][0] : 1;
  const top = s.max || Math.max(1, ...pts.map(r => r[s.i])) * 1.15;
  const x = t => P + (t1 > t0 ? (t - t0) / (t1 - t0) : 0) * (w - 2 * P), y = vv => H - P - (vv / top) * (H - 2 * P);
  let d = "", prev = null;
  for (const r of rows) {
    const vv = r[s.i];
    if (vv === null || vv === undefined) { prev = null; continue; }
    d += (prev === null || r[0] - prev > (range === "day" ? 900 : 5400) ? "M" : "L") + x(r[0]).toFixed(1) + "," + y(vv).toFixed(1);
    prev = r[0];
  }
  const last = pts.length ? pts[pts.length - 1][s.i] : null;
  const move = e => {
    const b = e.currentTarget.getBoundingClientRect(), tx = t0 + (e.clientX - b.left - P) / (w - 2 * P) * (t1 - t0);
    let best = null; for (const r of pts) if (!best || Math.abs(r[0] - tx) < Math.abs(best[0] - tx)) best = r;
    setHover(best);
  };
  const fmtT = t => new Date(t * 1000).toLocaleString([], range === "day" ? { hour: "2-digit", minute: "2-digit" } : { weekday: "short", hour: "2-digit", minute: "2-digit" });
  return (<div className="perf">
    <div className="row" style={{ alignItems: "baseline" }}><span className="small">{s.title}</span><span className="spacer" />
      <b className="small" style={{ fontVariantNumeric: "tabular-nums" }}>{hover ? s.fmt(hover[s.i]) : last !== null ? s.fmt(last) : "-"}</b></div>
    <div ref={ref} style={{ position: "relative" }}>
      {pts.length ? <svg width={w} height={H} role="img" aria-label={`${s.title}, ${range === "day" ? "last 24 hours" : "last 7 days"}, now ${last !== null ? s.fmt(last) : "unknown"}`}
        onMouseMove={move} onMouseLeave={() => setHover(null)} style={{ display: "block", touchAction: "pan-y" }}>
        {s.max && [50].map(g => <line key={g} x1={P} x2={w - P} y1={y(g)} y2={y(g)} stroke="var(--line)" strokeDasharray="3 4" />)}
        <line x1={P} x2={w - P} y1={H - P} y2={H - P} stroke="var(--line-strong)" />
        <path d={d} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {hover && <><line x1={x(hover[0])} x2={x(hover[0])} y1={P} y2={H - P} stroke="var(--muted)" strokeWidth="1" />
          <circle cx={x(hover[0])} cy={y(hover[s.i])} r="4" fill="var(--accent)" stroke="var(--surface)" strokeWidth="2" /></>}
      </svg> : <div className="small muted" style={{ height: H, display: "grid", placeItems: "center" }}>No data yet</div>}
      {hover && <div className="small muted" style={{ position: "absolute", top: 0, left: 6 }}>{fmtT(hover[0])}</div>}
    </div></div>);
}

export function Performance() {
  const [range, setRange] = useState("day");
  const [d, again, , err] = useLoad("/api/resources?range=" + range, [range]);
  if (!d) return <CardWait err={err} retry={again} style={{ marginTop: 16 }} />;
  const rows = d.series || [];
  const hasPing = rows.some(r => r[5] !== null && r[5] !== undefined);
  return (<div className="card" style={{ marginTop: 16 }}>
    <div className="row"><div><h2 style={{ margin: 0 }}>Performance</h2>
      <p className="small muted" style={{ margin: "4px 0 0" }}>How hard this computer works, and how laggy it is for players. You get a notification when it's too much for a few minutes.</p></div>
      <span className="spacer" /><div className="seg" role="group" aria-label="Time range">
        <button className={range === "day" ? "on" : ""} aria-pressed={range === "day"} onClick={() => setRange("day")}>24 hours</button>
        <button className={range === "week" ? "on" : ""} aria-pressed={range === "week"} onClick={() => setRange("week")}>7 days</button></div></div>
    {rows.length < 2 ? <Empty title="Collecting data">The graphs fill in over the next few minutes - one point every minute.</Empty>
      : <div className="grid g2" style={{ marginTop: 12 }}>{SERIES.filter(s => s.i !== 5 || hasPing).map(s => <LineChart key={s.i} rows={rows} s={s} range={range} />)}</div>}
    {rows.length >= 2 && !hasPing && <p className="small muted" style={{ marginTop: 8 }}>The ping graph appears once players are online with the updated EasyServer plugin.</p>}
  </div>);
}

/* ================================================================== first-time setup checklist (Overview) */
const STEPS = {
  name: ["Give your server a name", "It's what players see in the server list.", "Open Config"],
  authkey: ["Add an AuthKey", "Without it, nobody outside your home can find the server in the list.", "Add AuthKey"],
  mods: ["Add some mods", "Maps and cars from the BeamNG repository, virus-checked. Or keep it vanilla.", "Add mods"],
  reach: ["Check friends can reach it", "The Health page tests your port forwarding from outside.", "Run the check"],
  invite: ["Invite your friends", "A ready-made message for Discord or WhatsApp with everything they need.", "Copy invite"],
  alerts: ["Get alerts on your phone", "Crashes, reports and updates on Discord, your phone or by email.", "Set it up"],
};
export function Checklist() {
  const [d, again] = useLoad("/api/checklist");
  const [busy, setBusy] = useState(false);
  if (!d || d.hidden || d.done >= d.total) return null;
  const post = async body => { setBusy(true); try { await L.api("/api/checklist", { json: body }); await again(); } catch (e) { L.toast(e.message); } setBusy(false); };
  const go = it => {
    if (it.go === "invite") { L.openInvite(); post({ invited: true }); return; }
    if (it.go === "config" && it.id === "authkey") { L.bridge.show("config"); return; }
    L.bridge.show(it.go);
  };
  const pct = Math.round(d.done / d.total * 100);
  return (<div className="card checklist" style={{ marginBottom: 16 }}>
    <div className="row"><div><h2 style={{ margin: 0 }}>Get your server ready</h2>
      <p className="small muted" style={{ margin: "4px 0 0" }}>{`${d.done} of ${d.total} done. Each step ticks itself off when it's done.`}</p></div>
      <span className="spacer" /><button className="btn sm ghost" disabled={busy} onClick={() => post({ hidden: true })}>Hide</button></div>
    <div className="bar" style={{ margin: "12px 0 6px" }} role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Setup progress"><i style={{ width: pct + "%" }} /></div>
    <ol className="steps">{d.items.map(it => { const s = STEPS[it.id], ok = it.done || it.skipped; return (
      <li key={it.id} className={ok ? "ok" : ""}>
        <span className="tick" aria-hidden="true">{ok ? "✓" : ""}</span>
        <div><b>{s[0]}</b>{it.skipped && !it.done && <span className="small muted">{" (skipped)"}</span>}{!ok && <div className="small muted">{s[1]}</div>}</div>
        <span className="spacer" />
        {!ok && <><button className="btn sm" onClick={() => go(it)}>{s[2]}</button>
          <button className="btn sm ghost" disabled={busy} onClick={() => post({ skip: it.id })}>Skip</button></>}
        {it.skipped && !it.done && <button className="btn sm ghost" disabled={busy} onClick={() => post({ skip: it.id, on: false })}>Undo</button>}
      </li>); })}</ol>
  </div>);
}

/* ================================================================== quick search (Ctrl+K) */

export function QuickSearch() {
  const [open, setOpen] = useState(false), [q, setQ] = useState(""), [sel, setSel] = useState(0);
  const input = useRef(null), back = useRef(null);
  useEffect(() => {
    const key = e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); back.current = document.activeElement; setOpen(o => !o); }
      else if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) && !document.activeElement.isContentEditable) { e.preventDefault(); back.current = document.activeElement; setOpen(true); }
    };
    addEventListener("keydown", key);
    window.esQuickSearch = () => { back.current = document.activeElement; setOpen(true); };
    return () => { removeEventListener("keydown", key); delete window.esQuickSearch; };
  }, []);
  useEffect(() => { if (open) { setQ(""); setSel(0); setTimeout(() => input.current && input.current.focus(), 0); } else if (back.current && back.current.focus) back.current.focus(); }, [open]);
  const allowed = new Set(L.myTabs().map(t => t[0]));
  const hits = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    const list = PLACES.filter(p => allowed.has(p[0])).map(p => {
      const label = L.tr ? L.tr(p[1]) : p[1];
      const name = (label + " " + p[1]).toLowerCase(), more = p[2].toLowerCase();
      const at = (txt, w) => (" " + txt).includes(" " + w);       // a word that starts with what was typed
      // whole-word matches in the name count most, then in the extra words, then anywhere
      const one = w => at(name, w) ? 6 : at(more, w) ? 4 : name.includes(w) ? 2 : more.includes(w) ? 1 : 0;
      const score = words.length ? (words.every(w => one(w) > 0) ? words.reduce((sum, w) => sum + one(w), 0) : -1) : 1;
      return { p, label, score };
    }).filter(x => x.score > 0);
    list.sort((a, b) => b.score - a.score);
    return list.slice(0, 9);
  }, [q]);
  if (!open) return null;
  const go = h => {
    setOpen(false);
    L.bridge.show(h.p[0]);
    // after the page opens, scroll to the part that was picked and light it up for a moment
    const want = h.p[1].toLowerCase(), tr = (h.label || "").toLowerCase();
    let tries = 0;
    const find = () => {
      const els = [...document.querySelectorAll("main h1, main h2, main h3, main .toggle b, main summary")];
      const el = els.find(e => { const t = e.textContent.trim().toLowerCase(); return t === want || t === tr || t.startsWith(want) || (tr && t.startsWith(tr)); });
      if (el) { const box = el.closest(".card") || el; box.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); box.classList.add("found"); setTimeout(() => box.classList.remove("found"), 1800); }
      else if (++tries < 15) setTimeout(find, 120);
    };
    setTimeout(find, 150);
  };
  const key = e => {
    if (e.key === "Escape") setOpen(false);
    else if (e.key === "ArrowDown") { e.preventDefault(); setSel(s => Math.min(hits.length - 1, s + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel(s => Math.max(0, s - 1)); }
    else if (e.key === "Enter" && hits[sel]) go(hits[sel]);
  };
  const pageName = id => (L.TABS.find(t => t[0] === id) || [id, id])[1];
  return (<div className="modalbg qsbg" onClick={e => { if (e.target === e.currentTarget) setOpen(false); }}>
    <div className="card qs" role="dialog" aria-modal="true" aria-label="Quick search">
      <input ref={input} type="text" role="combobox" aria-expanded="true" aria-controls="qs-list" aria-activedescendant={hits[sel] ? "qs-" + sel : undefined}
        placeholder="Search pages and settings… (port, ban, backup)" value={q} onChange={e => { setQ(e.target.value); setSel(0); }} onKeyDown={key} />
      <ul id="qs-list" role="listbox">{hits.map((h, i) => <li key={h.p[0] + h.p[1]} id={"qs-" + i} role="option" aria-selected={i === sel}
        className={i === sel ? "on" : ""} onMouseEnter={() => setSel(i)} onClick={() => go(h)}>
        <span>{h.label}</span><span className="small muted">{pageName(h.p[0])}</span></li>)}
        {!hits.length && <li className="small muted" style={{ cursor: "default" }}>Nothing found. Try another word.</li>}</ul>
      <div className="small muted qsfoot"><span><kbd>↑</kbd> <kbd>↓</kbd> to move, <kbd>Enter</kbd> to open, <kbd>Esc</kbd> to close</span></div>
    </div></div>);
}
