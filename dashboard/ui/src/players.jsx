// Players page: maintenance mode, reports, moderation and bans, chat history, statistics, records, maps.
import { useEffect, useRef, useState } from "react";
import * as L from "./legacy.js";
import { useApi } from "./pages.jsx";

const S = () => L.state();
const pad2 = n => String(n).padStart(2, "0");
const fmtClock = t => new Date(t * 1000).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" });
export function canModerate() {
  const r = L.myRole();
  if (r && r.perms) return r.perms.includes("players");
  return (r ? r.role : S().SESSION.role) !== "viewer";
}

/* ---------------- bar chart (players per day, busiest hours) */
function BarChart({ values, labels, tip, title, h = 190, labelsMax = 8 }) {
  const box = useRef(null), [W, setW] = useState(640), [hover, setHover] = useState(-1);
  useEffect(() => {
    const el = box.current; if (!el) return;
    const measure = () => setW(Math.max(280, Math.round(el.clientWidth || 640)));
    measure();
    const ro = new ResizeObserver(measure); ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const H = h, padL = 30, padB = 22, padT = 10, n = values.length;
  const max = Math.max(1, ...values), step = (W - padL) / n, bw = Math.max(2, Math.min(28, step - 2));
  const nice = max <= 4 ? Math.ceil(max) : Math.ceil(max / 4) * 4;
  const y = v => padT + (H - padT - padB) * (1 - v / nice);
  const every = Math.ceil(n / Math.max(3, Math.min(labelsMax, Math.floor((W - padL) / 52))));
  const ticks = [0, 1, 2, 3, 4].map(i => nice * i / 4);
  const sc = box.current ? (box.current.getBoundingClientRect().width || W) / W : 1;
  return (<div ref={box}><div className="chart">
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title}>
      <g className="grid">{ticks.map((v, i) => <line key={i} x1={padL} x2={W} y1={y(v)} y2={y(v)} />)}</g>
      <g className="axis">{ticks.map((v, i) => <text key={"t" + i} x={padL - 6} y={y(v) + 4} textAnchor="end">{Number.isInteger(v) ? v : v.toFixed(1)}</text>)}
        {labels.map((l, i) => i % every === 0 && <text key={"l" + i} x={padL + step * i + step / 2} y={H - 6} textAnchor="middle">{l}</text>)}</g>
      <g className="bars">
        {values.map((v, i) => {
          if (!(v > 0)) return null;
          const x = padL + step * i + (step - bw) / 2, top = y(v), base = y(0), r = Math.min(4, bw / 2, base - top);
          return <path key={"b" + i} fill="var(--accent)" style={{ opacity: hover < 0 || hover === i ? 1 : .35 }} d={`M${x},${base}V${top + r}q0,-${r} ${r},-${r}h${bw - 2 * r}q${r},0 ${r},${r}V${base}Z`} />;
        })}
        {values.map((_, i) => <rect key={"h" + i} className="hit" x={padL + step * i} y={padT} width={step} height={H - padT - padB} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(-1)} />)}
      </g>
    </svg>
    {hover >= 0 && <div className="tip" style={{ left: (padL + step * hover + step / 2) * sc, top: y(values[hover]) * sc }}>{tip(hover)}</div>}
  </div></div>);
}

/* ---------------- maintenance mode */
function Maintenance() {
  const [mt, err, load] = useApi("/api/maintenance", 0);
  const [f, setF] = useState(null);
  useEffect(() => { if (mt) setF({ message: mt.message, allow: mt.allow.join("\n"), kick: !!mt.kick }); }, [mt]);
  if (!mt || !f) return null;
  const go = async st => { try { const r = await L.api("/api/maintenance", { json: { state: st, ...f } }); L.toast(r.note, 7000); load(); } catch (e) { L.toast(e.message, 6000); } };
  return (<div className="card" style={{ marginBottom: 16, ...(mt.on ? { borderColor: "var(--warning)" } : {}) }}>
    <div className="row"><h2 style={{ margin: 0 }}>Maintenance mode</h2><span className="spacer" />
      <span className={"pill " + (mt.on ? "warn" : "")}><span className="dot" />{mt.on ? `On since ${L.fmtTime(mt.since)}` : "Off"}</span></div>
    <p className="small muted">Close the server while you work on it: only admins (Config → Moderation) and the names below can join. Everyone else sees your message. Works right away, no restart.</p>
    <label className="f"><span>Message players see</span><input type="text" maxLength={200} value={f.message} onChange={e => setF({ ...f, message: e.target.value })} /></label>
    <label className="f"><span>May still join (one name per line)</span><textarea rows={2} spellCheck={false} style={{ minHeight: 52 }} value={f.allow} onChange={e => setF({ ...f, allow: e.target.value })} /></label>
    <label className="toggle"><input type="checkbox" checked={f.kick} onChange={e => setF({ ...f, kick: e.target.checked })} /><span><b>Disconnect the other players</b><small>They get a 10-second warning in the chat first</small></span></label>
    <div className="row" style={{ marginTop: 10 }}>{mt.on
      ? <><button className="btn primary" onClick={() => go("off")}>End maintenance</button><button className="btn" onClick={() => go("on")}>Save changes</button></>
      : <button className="btn primary" onClick={() => confirm("Start maintenance? Only admins and the listed players can join until you end it.") && go("on")}>Start maintenance</button>}</div>
  </div>);
}

/* ---------------- chat lines (reports and chat history) */
const ChatRows = ({ lines, onPick }) => lines.map((c, i) => <div key={i} className={"chatline" + (c.hid ? " hid" : "")} onClick={onPick ? () => onPick(c.t) : undefined}>
  <span className="muted">{fmtClock(c.t)}</span> <b>{c.name}</b> {c.msg}{c.hid && <> <span className="badge" title="Players didn't see this: the sender was muted or the chat filter caught it">hidden</span></>}</div>);

/* ---------------- player reports */
let SHOW_CLOSED = false;
function Reports({ onBan }) {
  const [d, , load] = useApi("/api/reports", 0);
  const [all, setAll] = useState(SHOW_CLOSED);
  if (!d || !d.items.length) return null;
  const list = d.items.filter(x => all || x.open);
  const close = async id => { try { await L.api("/api/reports/close", { json: { id } }); load(); } catch (e) { L.toast(e.message); } };
  return (<div className="card" style={{ marginBottom: 16 }}>
    <div className="row"><h2 style={{ margin: 0 }}>Reports</h2>{d.open > 0 && <span className="badge warn">{`${d.open} open`}</span>}<span className="spacer" />
      <label className="small muted" style={{ display: "flex", gap: 6, alignItems: "center" }}><input type="checkbox" checked={all} onChange={e => { SHOW_CLOSED = e.target.checked; setAll(e.target.checked); }} /> Show handled</label>
      {d.open > 1 && <button className="btn sm" onClick={() => close("all")}>Mark all handled</button>}</div>
    {!d.on && <p className="small muted">Reports are turned off (Config → Moderation).</p>}
    {list.length ? list.map(r => <div key={r.id} className={"report" + (r.open ? "" : " done")}>
      <div className="row"><div><b>{r.by}</b> reported <b>{r.target}</b> <span className="muted small">{"· " + fmtClock(r.t)}</span><div>{r.reason}</div></div><span className="spacer" />
        {r.open ? <><button className="btn sm" onClick={() => onBan(r.target)}>Ban…</button><button className="btn sm" onClick={() => close(r.id)}>Handled</button></>
          : <span className="small muted">{`Handled by ${r.closed_by || "?"}`}</span>}</div>
      {r.chat && r.chat.length > 0 && <details style={{ marginTop: 6 }}><summary className="small">{`Chat before the report (${r.chat.length})`}</summary><div className="chatbox"><ChatRows lines={r.chat} /></div></details>}
    </div>) : <p className="small muted" style={{ margin: "8px 0 0" }}>No open reports.</p>}
  </div>);
}

/* ---------------- chat history */
function Chat() {
  const [opts, setOpts] = useState({}), [d, setD] = useState(null), [q, setQ] = useState(""), [player, setPlayer] = useState("");
  const box = useRef(null);
  const load = async o => {
    const qs = new URLSearchParams();
    if (o.q) qs.set("q", o.q); if (o.player) qs.set("player", o.player); if (o.around) qs.set("around", o.around);
    try { setD(await L.api("/api/chat?" + qs)); setOpts(o); setQ(o.q || ""); setPlayer(o.player || ""); } catch (e) { setD(null); }
  };
  useEffect(() => { load({}); }, []);
  useEffect(() => { if (box.current) box.current.scrollTop = box.current.scrollHeight; }, [d]);
  if (!d) return null;
  const role = S().SESSION.role;
  const go = () => load({ q: q.trim(), player });
  const clear = async () => {
    if (!confirm("Delete the whole chat history of this server? This can't be undone.")) return;
    try { const r = await L.api("/api/chat/clear", { json: {} }); L.toast(r.note); load({}); } catch (e) { L.toast(e.message); }
  };
  return (<div className="card" style={{ marginBottom: 16 }}>
    <div className="row"><h2 style={{ margin: 0 }}>Chat history</h2><span className="spacer" />
      {(role === "owner" || role === "admin" || !role) && <button className="btn sm ghost" onClick={clear}>Delete history</button>}</div>
    {!d.on && <p className="small muted">{d.total ? "The chat history is turned off (Config → Moderation). Older messages are still here." : "The chat history is turned off (Config → Moderation)."}</p>}
    <div className="row" style={{ gap: 8, margin: "10px 0", flexWrap: "wrap" }}>
      <input type="text" placeholder="Search words or names" style={{ maxWidth: 260 }} value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => { if (e.key === "Enter") go(); }} />
      <select style={{ maxWidth: 200 }} value={player} onChange={e => setPlayer(e.target.value)}><option value="">Everyone</option>{(opts.player ? [opts.player] : d.players).map(n => <option key={n} value={n}>{n}</option>)}</select>
      <button className="btn sm" onClick={go}>Search</button>{(opts.q || opts.player || opts.around) && <button className="btn sm ghost" onClick={() => load({})}>Show all</button>}</div>
    {opts.around && <p className="small muted">{`The 10 minutes around ${fmtClock(opts.around)}.`}</p>}
    {d.lines.length ? <><div className="chatbox" ref={box}><ChatRows lines={d.lines} onPick={t => load({ around: t })} /></div>
      <p className="small muted" style={{ margin: "6px 0 0" }}>{(d.total > d.lines.length ? `Newest ${d.lines.length} of ${d.total} messages. ` : "") + "Click a message to see what was said around it."}</p></>
      : <p className="small muted">{opts.q || opts.player ? "Nothing found." : "No chat yet."}</p>}
  </div>);
}

/* ---------------- online now, moderation, bans */
function Moderation({ d, bn, ban, setBan, reload }) {
  const reasonRef = useRef(null), [say, setSay] = useState("");
  const act = async body => { try { const r = await L.api("/api/players/act", { json: body }); L.toast(r.note); } catch (e) { L.toast(e.message); } };
  const doBan = async () => {
    const name = ban.name.trim(); if (!name) return L.toast("Type the player's name");
    try { const r = await L.api("/api/bans/add", { json: { name, minutes: Number(ban.len), reason: ban.reason } }); L.toast(r.note); reload(); } catch (e) { L.toast(e.message); }
  };
  const unban = async name => { try { const r = await L.api("/api/bans/remove", { json: { name } }); L.toast(r.note); reload(); } catch (e) { L.toast(e.message); } };
  const send = async () => { const t = say.trim(); if (!t) return; await act({ action: "say", name: "x", text: t }); setSay(""); };
  return (<div className="card" style={{ marginBottom: 16 }}>
    <div className="row"><h2 style={{ margin: 0 }}>Online now &amp; moderation</h2><span className="spacer" /><span className="small muted">Takes a second to reach the game</span></div>
    {bn.online.length ? <table style={{ marginTop: 8 }}><tbody>{bn.online.map(n => <tr key={n}><td><b>{n}</b></td><td className="num"><div className="row" style={{ justifyContent: "flex-end", gap: 6 }}>
      <button className="btn sm" onClick={() => act({ action: "mute", name: n, minutes: 10 })}>Mute 10 min</button>
      <button className="btn sm" onClick={() => act({ action: "unmute", name: n, minutes: 10 })}>Unmute</button>
      <button className="btn sm" onClick={() => act({ action: "kick", name: n, minutes: 10 })}>Kick</button>
      <button className="btn sm danger" onClick={() => { setBan({ ...ban, name: n }); reasonRef.current && reasonRef.current.focus(); }}>Ban…</button></div></td></tr>)}</tbody></table>
      : <p className="small muted">{d.online.fresh ? "Nobody is online right now." : "Nobody is online right now (or the server isn't reporting)."}</p>}
    <div className="row" style={{ gap: 8, marginTop: 12, flexWrap: "wrap" }}>
      <input type="text" id="ban_name" placeholder="Player name" style={{ maxWidth: 180 }} maxLength={64} value={ban.name} onChange={e => setBan({ ...ban, name: e.target.value })} />
      <select style={{ maxWidth: 150 }} value={ban.len} onChange={e => setBan({ ...ban, len: e.target.value })}>
        <option value="60">1 hour</option><option value="1440">1 day</option><option value="10080">7 days</option><option value="43200">30 days</option><option value="0">Forever</option></select>
      <input type="text" ref={reasonRef} placeholder="Reason (players see it)" style={{ maxWidth: 240 }} maxLength={200} value={ban.reason} onChange={e => setBan({ ...ban, reason: e.target.value })} />
      <button className="btn danger" onClick={doBan}>Ban</button></div>
    <div className="row" style={{ gap: 8, marginTop: 10 }}><input type="text" placeholder="Send a message to everyone in the game chat" maxLength={300} value={say} onChange={e => setSay(e.target.value)} /><button className="btn" onClick={send}>Send</button></div>
    <h2 style={{ marginTop: 18 }}>{`Banned players (${bn.bans.length})`}</h2>
    {bn.bans.length ? <table><thead><tr><th>Player</th><th>Until</th><th>Reason</th><th>By</th><th></th></tr></thead><tbody>{bn.bans.map(b => <tr key={b.name}>
      <td><b>{b.name}</b></td><td className="muted">{b.until ? L.fmtTime(b.until) : "Forever"}</td><td>{b.reason || "-"}</td><td className="muted">{b.by || "-"}</td>
      <td className="num"><button className="btn sm" onClick={() => unban(b.name)}>Unban</button></td></tr>)}</tbody></table>
      : <p className="small muted">Nobody is banned. Admins you set under Config → Moderation can also ban from the game chat.</p>}
  </div>);
}

/* ---------------- per-map statistics */
function MapStats() {
  const [days, setDays] = useState(30);
  const [d] = useApi("/api/players/maps?days=" + days, 0);
  if (!d) return null;
  const rows = d.maps, top = Math.max(0.01, ...rows.map(r => r.player_hours));
  const busy = rows.filter(r => r.map_hours >= 2).sort((a, b) => b.per_hour - a.per_hour);
  return (<div>
    <div className="row" style={{ margin: "22px 0 10px" }}><h2 style={{ margin: 0 }}>Maps</h2><span className="spacer" />
      <div className="seg">{[7, 30, 90].map(n => <button key={n} className={n === days ? "on" : ""} onClick={() => setDays(n)}>{`${n} days`}</button>)}</div></div>
    {rows.length ? <><div className="card tight"><table><thead><tr><th>Map</th><th>Time played by everyone</th><th className="num">Players</th><th className="num">Avg. stay</th><th className="num">Peak</th><th className="num">Map was on</th></tr></thead><tbody>
      {rows.map(r => <tr key={r.map}><td><b>{r.map}</b>{r.map === d.current && <> <span className="badge">now</span></>}</td>
        <td><div className="row" style={{ gap: 8, flexWrap: "nowrap" }}><div style={{ flex: 1, minWidth: 60, maxWidth: 220, height: 8, borderRadius: 4, background: "var(--surface-2)" }}><div style={{ width: Math.round(r.player_hours / top * 100) + "%", height: "100%", borderRadius: 4, background: "var(--accent)" }} /></div>
          <span className="small">{r.player_hours >= 0.1 ? r.player_hours + " h" : r.players ? "<0.1 h" : "0 h"}</span></div></td>
        <td className="num">{r.players}</td><td className="num">{r.avg_session_min ? r.avg_session_min + " min" : "-"}</td><td className="num">{r.peak}</td><td className="num muted">{r.map_hours >= 0.1 ? r.map_hours + " h" : "<0.1 h"}</td></tr>)}</tbody></table></div>
      <p className="small muted" style={{ marginTop: 6 }}>{busy.length > 1 && <>Busiest map per hour it's on: <b>{busy[0].map}</b>{` (${busy[0].per_hour} players on average). Quietest: `}<b>{busy[busy.length - 1].map}</b>{` (${busy[busy.length - 1].per_hour}).`} </>}{`Counted since ${L.fmtTime(d.since)}.`}</p></>
      : <p className="small muted">{d.since ? `Nobody has played since ${L.fmtTime(d.since)}.` : "Map statistics start now - they appear once people have played on this server."}</p>}
  </div>);
}

/* ---------------- server records */
function Records({ d }) {
  const R = d.records || {}, any = ["speed", "dist", "streak"].some(k => (R[k] || []).length);
  if (!any && !d.records_on) return null;
  const Col = ({ title, list, val }) => <div className="card tight"><table><thead><tr><th>{title}</th><th className="num"></th></tr></thead><tbody>
    {(list || []).length ? list.map((r, i) => <tr key={i}><td>{`${i + 1}. `}<b>{r.name}</b></td><td className="num">{val(r)}</td></tr>) : <tr><td colSpan={2} className="muted">Nobody yet</td></tr>}</tbody></table></div>;
  return (<>
    <h2 style={{ margin: "22px 0 10px" }}>Server records</h2>
    {!d.records_on && <p className="small muted">Records are paused - turn on "/top server records" under Config → Cars &amp; chat.</p>}
    <div className="grid g3">
      <Col title="Top speed" list={R.speed} val={r => Math.round(r.speed) + " km/h"} />
      <Col title="Distance driven" list={R.dist} val={r => r.dist.toFixed(1) + " km"} />
      <Col title="Longest drive without a reset" list={R.streak} val={r => L.fmtDur(r.streak)} />
    </div>
  </>);
}

/* ---------------- the page */
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export function Players({ reload }) {
  const [tick, setTick] = useState(0);
  const [d, err] = useApi("/api/players", reload, [tick]);
  const [bn] = useApi("/api/bans", reload, [tick]);
  const [ban, setBan] = useState({ name: "", len: "0", reason: "" });
  if (!d || !bn) return err ? <div className="banner bad">{err}</div> : <p className="muted">Loading…</p>;
  const s = d.summary, hm = d.heatmap, hmMax = Math.max(0.0001, ...hm.flat().filter(v => v !== null));
  const shade = v => v === null ? "var(--surface-2)" : `var(--heat-${Math.min(6, Math.round(v / hmMax * 6))})`;
  const again = () => { setBan({ name: "", len: "0", reason: "" }); setTick(t => t + 1); };
  const clear = async () => { if (!confirm("Delete all player statistics?")) return; await L.api("/api/players/clear", { method: "POST" }); setTick(t => t + 1); };
  const onBan = name => { setBan(b => ({ ...b, name })); const i = document.getElementById("ban_name"); if (i) { i.scrollIntoView({ block: "center" }); i.focus(); } };
  const mod = canModerate();
  return (<>
    <div className="row"><div><h1>Players</h1><p className="sub">Activity over the last 30 days. Recorded by the EasyServerStats plugin on your server.</p></div><span className="spacer" /><button className="btn sm" onClick={clear}>Clear statistics</button></div>
    {!d.has_data && <div className="banner info">No player data yet. Statistics start once the server runs with the stats plugin and someone plays.</div>}
    <Maintenance key={"m" + reload} />
    {mod && <Reports key={"r" + reload} onBan={onBan} />}
    <Moderation d={d} bn={bn} ban={ban} setBan={setBan} reload={again} />
    {mod && <Chat key={"c" + reload} />}
    <div className="grid g4">
      <div className="card stat"><div className="label">Online now</div><div className="value">{d.online.players.length}</div><div className="note">{d.online.fresh ? d.online.players.slice(0, 3).join(", ") || "Nobody" : "Server not reporting"}</div></div>
      <div className="card stat"><div className="label">Players (30 days)</div><div className="value">{s.unique_30d}</div><div className="note">{`${s.unique_7d} in the last 7 days`}</div></div>
      <div className="card stat"><div className="label">Peak at once</div><div className="value">{s.peak}</div><div className="note">{s.peak_at ? L.fmtTime(s.peak_at) : "-"}</div></div>
      <div className="card stat"><div className="label">Server usage</div><div className="value">{s.utilization + "%"}</div><div className="note">{`avg ${s.avg_players} players · ${s.hours_30d} h played`}</div></div>
    </div>
    <div className="card" style={{ marginTop: 16 }}><h2>Players per day</h2>
      <BarChart title="Players per day" labelsMax={10} values={d.days.map(x => x.players)} labels={d.days.map(x => x.date.slice(5).replace("-", "/"))}
        tip={i => <><b>{d.days[i].date}</b><br />{`${d.days[i].players} players · peak ${d.days[i].peak} · ${d.days[i].hours} h played`}</>} /></div>
    <div className="grid g2" style={{ marginTop: 16 }}>
      <div className="card"><h2>Busiest hours</h2><p className="small muted">{s.busiest_hour !== null ? `Average players online by time of day · busiest around ${pad2(s.busiest_hour)}:00` : "Average players online by time of day"}</p>
        <BarChart title="Average players by hour" labelsMax={8} h={170} values={d.hourly} labels={d.hourly.map((_, i) => pad2(i))}
          tip={i => <><b>{pad2(i) + ":00"}</b><br />{`${d.hourly[i]} players on average`}</>} /></div>
      <div className="card"><h2>Week overview</h2><p className="small muted">Average players by day and hour</p>
        <div className="heat"><span />{Array.from({ length: 24 }, (_, i) => <span key={"h" + i} className="lab">{i % 6 === 0 ? i : ""}</span>)}
          {hm.map((row, di) => [<span key={"d" + di} className="lab rl">{DAYS[di]}</span>,
            ...row.map((v, hh) => <span key={di + ":" + hh} className="c" style={{ background: shade(v) }} title={`${DAYS[di]} ${pad2(hh)}:00 · ` + (v === null ? "no data" : `${v} players avg`)} />)])}</div>
        <div className="legend">fewer {[0, 2, 4, 6].map(i => <i key={i} style={{ background: `var(--heat-${i})` }} />)} more</div></div>
    </div>
    <div className="grid g2" style={{ marginTop: 16 }}>
      <div className="card tight"><table><thead><tr><th>Top players (30 days)</th><th className="num">Time played</th><th className="num">Sessions</th></tr></thead><tbody>
        {d.top.length ? d.top.map(p => <tr key={p.name}><td><b>{p.name}</b><div className="small muted">{`last seen ${L.ago(p.last_seen)}`}</div></td><td className="num">{L.fmtDur(p.seconds)}</td><td className="num">{p.sessions}</td></tr>)
          : <tr><td colSpan={3} className="muted">No players yet</td></tr>}</tbody></table></div>
      <div className="card tight"><table><thead><tr><th>Recent sessions</th><th className="num">Started</th><th className="num">Length</th></tr></thead><tbody>
        {d.recent.length ? d.recent.slice(0, 12).map((r, i) => <tr key={i}><td>{r.name}</td><td className="num muted">{L.fmtTime(r.start)}</td><td className="num">{r.minutes + " min"}</td></tr>)
          : <tr><td colSpan={3} className="muted">No sessions yet</td></tr>}</tbody></table></div>
    </div>
    <Records d={d} />
    <MapStats key={"s" + reload} />
  </>);
}
