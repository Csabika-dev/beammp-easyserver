// Games page: the live map, races, cops and robbers, speed traps, badges, seasons, the weekly
// recap and lap times. The games themselves run in the server plugin; this page sets their rules
// and shows the results.
import { useCallback, useEffect, useRef, useState } from "react";
import * as L from "./legacy.js";
import { useApi } from "./pages.jsx";
import { CardWait, Empty, PageWait, Toggle, chk, useLoad } from "./ui.jsx";
import { LapTimes, ProfileHost, Who } from "./extras.jsx";

const S = () => L.state();
export function canEditGames() {
  const r = L.myRole();
  if (r && r.perms) return r.perms.includes("config");
  return ["owner", "admin"].includes((r ? r.role : S().SESSION.role) || "owner");
}
const fmtSecs = s => s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : `${s} s`;

/* ================================================================== live map */
const ROLE = {
  cop: { label: "Cop", color: "var(--accent)" },
  robber: { label: "Robber", color: "var(--critical)" },
  race: { label: "Racing", color: "var(--good)" },
  out: { label: "Busted", color: "var(--muted)" },
  "": { label: "Driving", color: "var(--text-2)" },
};
const STEPS = [25, 50, 100, 250, 500, 1000, 2500, 5000];

function Marker({ c, u, x, y }) {
  const col = ROLE[c.role] ? ROLE[c.role].color : ROLE[""].color, r = 6 * u;
  // shape as well as colour: square = cop, triangle = robber, circle = everyone else
  if (c.role === "cop") return <rect x={x - r} y={y - r} width={2 * r} height={2 * r} rx={1.5 * u} fill={col} stroke="var(--surface)" strokeWidth={2 * u} />;
  if (c.role === "robber") return <path d={`M${x} ${y - r * 1.25}L${x + r * 1.15} ${y + r * 0.9}L${x - r * 1.15} ${y + r * 0.9}Z`} fill={col} stroke="var(--surface)" strokeWidth={2 * u} />;
  return <circle cx={x} cy={y} r={r} fill={col} stroke="var(--surface)" strokeWidth={2 * u} />;
}

function LiveMap() {
  const [d, setD] = useState(null), [err, setErr] = useState(""), [hover, setHover] = useState(null), [fitKey, setFit] = useState(0);
  const trails = useRef(new Map()), ro = useRef(null), [aspect, setAspect] = useState(1.6);
  // the drawing has the same shape as its box, so the grid fills it on any screen
  const box = useCallback(el => {
    if (ro.current) { ro.current.disconnect(); ro.current = null; }
    if (!el) return;
    const measure = () => { const a = el.clientWidth / Math.max(1, el.clientHeight); if (a > 0.3 && a < 4) setAspect(x => Math.abs(x - a) > 0.02 ? a : x); };
    measure();
    ro.current = new ResizeObserver(measure); ro.current.observe(el);
  }, []);
  useEffect(() => {
    let stop = false, timer;
    const poll = async () => {
      if (!document.hidden) {
        try {
          const r = await L.api("/api/livemap");
          if (stop) return;
          for (const c of r.cars) {
            const tr = trails.current.get(c.n) || [];
            const last = tr[tr.length - 1];
            if (!last || Math.hypot(last[0] - c.x, last[1] - c.y) > 400) tr.length = 0;    // a reset or teleport: start the trail again
            tr.push([c.x, c.y]);
            if (tr.length > 24) tr.shift();
            trails.current.set(c.n, tr);
          }
          for (const k of [...trails.current.keys()]) if (!r.cars.some(c => c.n === k)) trails.current.delete(k);
          setD(r); setErr("");
        } catch (e) { if (!stop) setErr(e.message); }
      }
      if (!stop) timer = setTimeout(poll, 1000);
    };
    poll();
    return () => { stop = true; clearTimeout(timer); };
  }, []);
  // The view only grows (so it doesn't jump about as cars move) until "Fit" is pressed.
  const view = useRef(null);
  useEffect(() => { view.current = null; }, [fitKey]);
  if (!d) return <CardWait err={err} lines={6} />;
  const pts = [];
  d.tracks.forEach(t => t.pts.forEach(p => pts.push(p)));
  d.traps.forEach(t => pts.push([t.x, t.y]));
  d.cars.forEach(c => pts.push([c.x, c.y]));
  let v = view.current;
  if (pts.length) {
    let [x0, x1, y0, y1] = [Infinity, -Infinity, Infinity, -Infinity];
    pts.forEach(([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); });
    if (v) { x0 = Math.min(x0, v.x0); x1 = Math.max(x1, v.x1); y0 = Math.min(y0, v.y0); y1 = Math.max(y1, v.y1); }
    const w = Math.max(200 * aspect, x1 - x0, (y1 - y0) * aspect) * 1.15, h = w / aspect, cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    v = { x0: cx - w / 2, x1: cx + w / 2, y0: cy - h / 2, y1: cy + h / 2 };
    view.current = { x0, x1, y0, y1 };
  }
  const empty = !d.cars.length;
  const g = d.game || {};
  const status = g.cnr ? (g.cnr.state === "join" ? "Cops and robbers is starting" : `Cops and robbers · ${fmtSecs(g.cnr.left)} left`)
    : g.race ? `Race on ${g.race.track} · ${g.race.state === "on" ? "racing" : "about to start"}` : null;
  return (<div className="card livemap">
    <div className="row"><h2 style={{ margin: 0 }}>Live map</h2>
      {status && <span className="pill good"><span className="dot" />{status}</span>}
      <span className="spacer" />
      <span className="small muted">{d.cars.length === 1 ? "1 car" : `${d.cars.length} cars`}</span>
      {pts.length > 0 && <button className="btn sm ghost" onClick={() => setFit(x => x + 1)} title="Zoom to what's on the map now">Fit</button>}</div>
    <p className="small muted" style={{ margin: "4px 0 10px" }}>{"Where everyone is right now, with your tracks and speed traps. North is up. It updates every second while this page is open."}</p>
    {!v ? <Empty title={d.running ? "Nobody is driving right now" : "The server is stopped"}>{d.running ? "Cars show up here as soon as someone spawns one. Tracks and speed traps you make in the game show up too." : "Start the server to see the cars."}</Empty> : (() => {
      const W = v.x1 - v.x0, H = v.y1 - v.y0, u = W / 800;
      const X = x => x - v.x0, Y = y => v.y1 - y;                 // north up
      const step = STEPS.find(s => W / s <= 10) || 10000;
      const lines = [];
      for (let gx = Math.ceil(v.x0 / step) * step; gx <= v.x1; gx += step) lines.push(<line key={"x" + gx} x1={X(gx)} x2={X(gx)} y1={0} y2={H} />);
      for (let gy = Math.ceil(v.y0 / step) * step; gy <= v.y1; gy += step) lines.push(<line key={"y" + gy} y1={Y(gy)} y2={Y(gy)} x1={0} x2={W} />);
      return <div className="mapbox" ref={box}>
        <svg className="mapsvg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Live map: ${d.cars.map(c => c.n).join(", ") || "no cars"}`} onMouseLeave={() => setHover(null)}>
          <g className="grid" strokeWidth={u}>{lines}</g>
          {d.tracks.map(t => <g key={t.name}>
            <polyline points={(t.kind === "loop" ? [...t.pts, t.pts[0]] : t.pts).map(p => `${X(p[0])},${Y(p[1])}`).join(" ")} fill="none" className="trk" strokeWidth={4 * u} strokeLinejoin="round" />
            <circle cx={X(t.pts[0][0])} cy={Y(t.pts[0][1])} r={5 * u} className="trkstart" strokeWidth={2 * u} />
            <text x={X(t.pts[0][0]) + 8 * u} y={Y(t.pts[0][1]) - 8 * u} fontSize={11 * u} className="maplabel">{t.name}</text></g>)}
          {d.traps.map(t => <g key={t.name}>
            <rect x={X(t.x) - 4 * u} y={Y(t.y) - 4 * u} width={8 * u} height={8 * u} transform={`rotate(45 ${X(t.x)} ${Y(t.y)})`} className="trap" />
            <text x={X(t.x) + 8 * u} y={Y(t.y) + 4 * u} fontSize={10 * u} className="maplabel muted">{"📸 " + t.name}</text></g>)}
          {[...trails.current.entries()].map(([n, tr]) => tr.length > 1 && <polyline key={"t" + n} points={tr.map(p => `${X(p[0])},${Y(p[1])}`).join(" ")}
            fill="none" stroke={(ROLE[(d.cars.find(c => c.n === n) || {}).role] || ROLE[""]).color} strokeOpacity=".35" strokeWidth={2.5 * u} strokeLinecap="round" />)}
          {d.cars.map(c => <g key={c.n} onMouseEnter={() => setHover(c)} onFocus={() => setHover(c)} tabIndex={0} className="carpin">
            <circle cx={X(c.x)} cy={Y(c.y)} r={14 * u} fill="transparent" />
            <Marker c={c} u={u} x={X(c.x)} y={Y(c.y)} />
            <text x={X(c.x) + 10 * u} y={Y(c.y) + 4 * u} fontSize={12 * u} className="maplabel">{c.n}</text></g>)}
        </svg>
        <div className="mapscale small muted"><span style={{ width: `${(step / W) * 100}%` }} />{step >= 1000 ? `${step / 1000} km` : `${step} m`}</div>
        {hover && <div className="maptip small"><b>{hover.n}</b>{` · ${hover.v} km/h${hover.car ? " · " + hover.car : ""}${hover.role ? " · " + ROLE[hover.role].label : ""}`}</div>}
      </div>;
    })()}
    {!empty && <div className="row small muted maplegend">{["cop", "robber", "out", "race", ""].filter(r => r === "" || d.cars.some(c => c.role === r)).map(r =>
      <span key={r} className="row" style={{ gap: 5 }}><svg width="14" height="14" viewBox="-8 -8 16 16" aria-hidden="true"><Marker c={{ role: r }} u={1} x={0} y={0} /></svg>{ROLE[r].label}</span>)}</div>}
    {!d.plugin && <p className="small" style={{ color: "var(--warn-ink)" }}>The EasyServer plugin isn't on this server yet - run the installer again.</p>}
  </div>);
}

/* ================================================================== rules */
function Rules({ d, again }) {
  const sel = id => document.getElementById(id).value;
  const save = async () => {
    const body = { race: chk("g_race"), cnr: chk("g_cnr"), traps: chk("g_traps"), badges: chk("g_badges"), seasons: chk("g_seasons"),
      race_who: sel("g_rwho"), cnr_who: sel("g_cwho"), cnr_minutes: Number(sel("g_min")), cnr_catch: Number(sel("g_catch")),
      cnr_hold: Number(sel("g_hold")), cnr_busted: sel("g_busted") };
    if (body.seasons && !d.seasons && !confirm("With seasons on, lap times, speed trap records and win counts start from zero on the 1st of every month. The winners are kept and get a badge. Turn seasons on?")) return;
    try { const r = await L.api("/api/games", { json: body }); L.toast(r.note, 6000); again(); } catch (e) { L.toast(e.message, 6000); }
  };
  const Who = ({ id, v }) => <select id={id} defaultValue={v} style={{ width: "auto" }}><option value="everyone">Anyone can start one</option><option value="admins">Only admins can start one</option></select>;
  return (<div className="card">
    <h2>{"Game rules"}</h2>
    <p className="small muted">{"Players start these games themselves with chat commands. Admins are the ones under Config → Moderation."}</p>
    <div className="grid g2" style={{ gap: 4 }}>
      <div><Toggle id="g_race" on={d.race} title="Races">{"/race and a track name - everyone who types /race join races, with a countdown"}</Toggle>
        <div style={{ margin: "0 0 8px 46px" }}><Who id="g_rwho" v={d.race_who} /></div></div>
      <div><Toggle id="g_cnr" on={d.cnr} title="Cops and robbers">{"/cnr start - cops chase robbers until the time runs out"}</Toggle>
        <div style={{ margin: "0 0 8px 46px" }}><Who id="g_cwho" v={d.cnr_who} /></div></div>
      <Toggle id="g_traps" on={d.traps} title="Speed traps">{"Admins put one up with /trap new; everyone sees the fastest with /trap"}</Toggle>
      <Toggle id="g_badges" on={d.badges} title="Badges">{"Earned for laps, wins, busts, distance and more - announced in the chat"}</Toggle>
      <Toggle id="g_seasons" on={d.seasons} title="Monthly seasons">{"Times and win counts start again every month; the winners are kept"}</Toggle>
    </div>
    <details className="small" style={{ margin: "8px 0 4px" }}><summary>{"Cops and robbers rules"}</summary>
      <div className="grid g2" style={{ gap: 10, marginTop: 10 }}>
        <label className="small">How long a game lasts (unless /cnr start 15 says otherwise)
          <select id="g_min" defaultValue={d.cnr_minutes}>{d.minutes.map(m => <option key={m} value={m}>{`${m} minutes`}</option>)}</select></label>
        <label className="small">How close a cop has to be
          <select id="g_catch" defaultValue={d.cnr_catch}>{d.catches.map(m => <option key={m} value={m}>{`${m} m`}</option>)}</select></label>
        <label className="small">How long the robber has to be stopped
          <select id="g_hold" defaultValue={d.cnr_hold}>{d.holds.map(m => <option key={m} value={m}>{`${m} seconds`}</option>)}</select></label>
        <label className="small">A busted robber
          <select id="g_busted" defaultValue={d.cnr_busted}><option value="out">is out of the game</option><option value="cop">becomes a cop</option></select></label>
      </div>
      <p className="muted" style={{ margin: "8px 0 0" }}>{"About one player in three is a cop. Robbers get a 30-second head start. A robber is busted when a cop stays this close while the robber is going under 20 km/h. Cops get a hint every 30 seconds where the nearest robber is; robbers are warned when a cop gets close. Nobody in a game can teleport."}</p>
    </details>
    <div className="row" style={{ marginTop: 8 }}><span className="spacer" /><button className="btn primary sm" onClick={save}>Save</button></div>
  </div>);
}

/* ================================================================== results */
const Board = ({ title, rows, unit, empty }) => <div className="card tight">
  <table><thead><tr><th colSpan={2}>{title}</th><th className="num">{unit}</th></tr></thead><tbody>
    {rows.length ? rows.map((r, i) => <tr key={r.name}><td className="num muted" style={{ width: 34 }}>{i + 1}</td><td><Who name={r.name} /></td><td className="num">{r.n}</td></tr>)
      : <tr><td colSpan={3} className="muted small">{empty}</td></tr>}</tbody></table></div>;

function Races({ d }) {
  return (<div className="card">
    <div className="row"><h2 style={{ margin: 0 }}>Races</h2><span className="spacer" /><span className={"pill " + (d.race ? "good" : "")}><span className="dot" />{d.race ? "On" : "Off"}</span></div>
    <p className="small muted">{"Start one in the game with /race and a track name, like /race Canyon run 3 for three laps. Everyone types /race join within 30 seconds, then a 5-second countdown. Positions come from each car's own clock, so lag doesn't change the result."}</p>
    <div className="grid g2" style={{ gap: 12, alignItems: "start" }}>
      <div>{d.races.length ? d.races.slice(0, 6).map((r, i) => <div className="card tight laptrack" key={i} style={{ marginBottom: 10 }}>
        <div style={{ padding: "10px 14px 4px" }}><b>{r.track}</b><div className="small muted">{`${r.laps === 1 ? "1 lap" : r.laps + " laps"} · ${L.ago(r.t)}${r.by ? " · started by " + r.by : ""}`}</div></div>
        <table><tbody>{r.results.map((x, j) => <tr key={x.name}><td className="num muted" style={{ width: 34 }}>{j + 1}</td><td><Who name={x.name} /></td>
          <td className="num mono">{j ? x.gap : x.time}</td></tr>)}
          {r.dnf.length > 0 && <tr><td /><td colSpan={2} className="small muted">{"Didn't finish: " + r.dnf.join(", ")}</td></tr>}</tbody></table></div>)
        : <Empty title="No races yet">{d.race ? "Make a track with /track new first, then start a race with /race." : "Turn races on under Game rules."}</Empty>}</div>
      <Board title="Race wins this season" rows={d.wins} unit="Wins" empty="Wins against at least one other driver count here." />
    </div>
  </div>);
}

function Championship({ d, canEdit, again }) {
  const [start, setStart] = useState(false);
  const act = async body => { try { const r = await L.api("/api/games", { json: body }); L.toast(r.note, 6000); setStart(false); again(); } catch (e) { L.toast(e.message, 6000); } };
  const begin = () => {
    const name = document.getElementById("ch_name").value.trim();
    if (d.champ && d.champ_rounds > 0 && !confirm(`Start ${name || "a new championship"}? ${d.champ_name || "The current one"} ends now and its leader is kept as the winner.`)) return;
    act({ action: "champ_new", name });
  };
  const points = async e => { try { const r = await L.api("/api/games", { json: { champ_points: e.target.value } }); L.toast(r.note, 6000); again(); } catch (x) { L.toast(x.message, 6000); } };
  const scale = d.champ_scales[d.champ_points] || [];
  return (<div className="card">
    <div className="row"><h2 style={{ margin: 0 }}>{d.champ && d.champ_name ? d.champ_name : "Championship"}</h2><span className="spacer" />
      <span className={"pill " + (d.champ ? "good" : "")}><span className="dot" />{d.champ ? (d.champ_rounds === 1 ? "1 race" : `${d.champ_rounds} races`) : "Off"}</span></div>
    <p className="small muted">{`While a championship is on, every race with 2 or more drivers gives points by finishing place (${scale.join("-")}). The points are announced after each race, and players see the standings with /champ.`}</p>
    {d.champ && (d.champ_table.length ? <div className="card tight"><table><thead><tr><th colSpan={2}>{"Standings"}</th><th className="num">{"Races"}</th><th className="num">{"Wins"}</th><th className="num">{"Podiums"}</th><th className="num">{"Points"}</th></tr></thead>
      <tbody>{d.champ_table.map((r, i) => <tr key={r.name}><td className="num muted" style={{ width: 34 }}>{i + 1}</td><td><Who name={r.name} /></td>
        <td className="num">{r.races}</td><td className="num">{r.wins}</td><td className="num">{r.podiums}</td><td className="num"><b>{r.points}</b></td></tr>)}</tbody></table></div>
      : <Empty title="No points yet">{"The first race with 2 or more drivers gives the first points."}</Empty>)}
    {!d.champ && !canEdit && <p className="small muted">{"No championship is running right now."}</p>}
    {canEdit && <div className="row" style={{ gap: 8, marginTop: 10, flexWrap: "wrap" }}>
      {start ? <>
        <input id="ch_name" placeholder="Name, like Winter Cup" maxLength={60} style={{ width: 220 }} autoFocus onKeyDown={e => e.key === "Enter" && begin()} />
        <button className="btn primary sm" onClick={begin}>Start</button><button className="btn sm ghost" onClick={() => setStart(false)}>Cancel</button></>
        : <button className={"btn sm" + (d.champ ? "" : " primary")} onClick={() => setStart(true)}>{d.champ ? "Start a new championship" : "Start a championship"}</button>}
      {d.champ && !start && <button className="btn sm ghost" onClick={() => { if (confirm(`End ${d.champ_name || "the championship"}? Its leader is kept as the winner.`)) act({ action: "champ_end" }); }}>End it</button>}
      <span className="spacer" />
      <label className="small" htmlFor="ch_pts">{"Points"}</label>
      <select id="ch_pts" defaultValue={d.champ_points} onChange={points} style={{ width: "auto" }}>
        <option value="f1">{"25-18-15-12-10-8-6-4-2-1 (top 10)"}</option><option value="simple">{"10-8-6-5-4-3-2-1 (top 8)"}</option></select></div>}
    {d.champ_history.length > 0 && <details className="small" style={{ marginTop: 12 }}><summary>{"Past championships"}</summary>
      <table style={{ marginTop: 6 }}><tbody>{d.champ_history.map((h, i) => <tr key={i}><td><b>{h.name}</b><div className="muted">{`${h.races === 1 ? "1 race" : h.races + " races"} · ended ${L.ago(h.ended)}`}</div></td>
        <td>{"🏆 "}<Who name={h.winner} /></td><td className="num">{`${h.points} pts`}</td></tr>)}</tbody></table></details>}
  </div>);
}

function CopsAndRobbers({ d }) {
  return (<div className="card">
    <div className="row"><h2 style={{ margin: 0 }}>Cops and robbers</h2><span className="spacer" /><span className={"pill " + (d.cnr ? "good" : "")}><span className="dot" />{d.cnr ? "On" : "Off"}</span></div>
    <p className="small muted">{`Someone types /cnr start (or /cnr start 15 for 15 minutes) and everyone has 30 seconds to type /cnr join - add cop or robber to ask for a side. Robbers win if anyone is still free when the ${d.cnr_minutes} minutes are up.`}</p>
    <div className="grid g2" style={{ gap: 12, alignItems: "start" }}>
      <div>{d.cnr_games.length ? d.cnr_games.slice(0, 5).map((g, i) => <div className="issue info" key={i} style={{ marginBottom: 8 }}>
        <span className="ic">{g.winner === "cops" ? "🚓" : "💨"}</span>
        <span><b>{g.winner === "cops" ? "Cops won" : "Robbers won"}</b>{` · ${fmtSecs(g.seconds)} · ${g.busts.length === 1 ? "1 bust" : g.busts.length + " busts"}`}
          <div className="small muted">{`Cops: ${g.cops.join(", ") || "-"} · Robbers: ${g.robbers.join(", ") || "-"}`}</div>
          {g.escaped.length > 0 && <div className="small muted">{"Got away: " + g.escaped.join(", ")}</div>}</span>
        <span className="ln">{L.ago(g.t)}</span></div>)
        : <Empty title="No games yet">{"It needs at least 2 players. With 3 or more it's more fun."}</Empty>}</div>
      <div style={{ display: "grid", gap: 12 }}>
        <Board title="Most busts this season" rows={d.busts} unit="Busts" empty="Nobody busted yet." />
        <Board title="Most getaways this season" rows={d.escapes} unit="Escapes" empty="Nobody got away yet." /></div>
    </div>
  </div>);
}

function Traps({ d, canEdit, again }) {
  const [open, setOpen] = useState(null);
  const act = async body => { try { const r = await L.api("/api/games", { json: body }); L.toast(r.note, 6000); again(); } catch (e) { L.toast(e.message, 6000); } };
  const here = d.trap_boards.filter(t => !t.map || t.map === d.map), other = d.trap_boards.filter(t => t.map && t.map !== d.map);
  const Card = ({ t }) => <div className="card tight laptrack">
    <div className="row" style={{ padding: "12px 14px 6px" }}><div><b>{t.name}</b><div className="small muted">{`${t.drivers === 1 ? "1 driver" : t.drivers + " drivers"}${t.map ? " · " + t.map : ""}`}</div></div>
      <span className="spacer" />{canEdit && <button className="btn sm ghost" aria-expanded={open === t.id} onClick={() => setOpen(open === t.id ? null : t.id)}>Manage</button>}</div>
    {open === t.id && <div className="row" style={{ padding: "0 14px 10px", gap: 6 }}>
      <button className="btn sm" onClick={() => { if (confirm(`Clear every speed on ${t.name}?`)) act({ action: "clear_trap", id: t.id }); }}>Clear speeds</button>
      <button className="btn sm danger" onClick={() => L.undoable(`${t.name} deleted.`, "/api/games", { action: "delete_trap", id: t.id }, { onUndo: again, after: again })}>Delete trap</button></div>}
    {t.top.length ? <table><tbody>{t.top.map((r, i) => <tr key={r.name}><td className="num muted" style={{ width: 34 }}>{i + 1}</td><td><Who name={r.name} /></td>
      <td className="num mono">{r.shown}</td><td className="small muted">{r.car}</td>
      {canEdit && open === t.id && <td className="num"><button className="btn sm ghost" onClick={() => act({ action: "remove_speed", id: t.id, name: r.name })}>Remove</button></td>}</tr>)}</tbody></table>
      : <p className="small muted" style={{ padding: "0 14px 12px", margin: 0 }}>No speeds yet - drive through it.</p>}</div>;
  return (<div className="card">
    <div className="row"><h2 style={{ margin: 0 }}>Speed traps</h2><span className="spacer" /><span className={"pill " + (d.traps ? "good" : "")}><span className="dot" />{d.traps ? "On" : "Off"}</span></div>
    <p className="small muted">{"An admin parks where the trap should be and types /trap new followed by a name. Everyone who drives through it sees their speed; a new record is announced to everyone. /trap delete and a name removes one."}</p>
    {here.length ? <div className="grid g2" style={{ gap: 12 }}>{here.map(t => <Card key={t.id} t={t} />)}</div>
      : <Empty title="No speed traps on this map">{"Put one on a long straight: park there and type /trap new Main straight."}</Empty>}
    {other.length > 0 && <details className="small" style={{ marginTop: 12 }}><summary>{other.length === 1 ? "1 speed trap on other maps" : `${other.length} speed traps on other maps`}</summary>
      <div className="grid g2" style={{ gap: 12, marginTop: 8 }}>{other.map(t => <Card key={t.id} t={t} />)}</div></details>}
  </div>);
}

const BADGE_ICON = { first_lap: "⏱", laps_25: "🔁", record: "🏁", race_win: "🥇", race_5: "🏆", sheriff: "⭐", getaway: "💨", speed_demon: "📸",
  flat_out: "🔥", km_100: "🛣", km_1000: "🗺", night_owl: "🦉", season_champ: "👑" };
function Badges({ d }) {
  const title = id => (d.badge_list.find(b => b.id === id) || {}).title || id;
  return (<div className="card">
    <div className="row"><h2 style={{ margin: 0 }}>Badges</h2><span className="spacer" /><span className={"pill " + (d.badges ? "good" : "")}><span className="dot" />{d.badges ? "On" : "Off"}</span></div>
    <p className="small muted">{`Players earn these by playing, and everyone sees it in the chat. They check theirs with /badges. ${d.players_with_badges === 1 ? "1 player has" : d.players_with_badges + " players have"} at least one.`}</p>
    <div className="badges">{d.badge_list.map(b => <div key={b.id} className={"badge" + (b.owners ? "" : " none")}>
      <span className="bi" aria-hidden="true">{BADGE_ICON[b.id] || "🏅"}</span>
      <span><b>{b.title}</b><span className="small muted">{b.how}</span></span>
      <span className="small muted bn">{b.owners === 1 ? "1 player" : `${b.owners} players`}</span></div>)}</div>
    {(d.badge_leaders.length > 0 || d.recent_badges.length > 0) && <div className="grid g2" style={{ gap: 12, marginTop: 12, alignItems: "start" }}>
      <Board title="Most badges" rows={d.badge_leaders} unit="Badges" empty="" />
      <div className="card tight"><table><thead><tr><th>{"Earned lately"}</th><th /><th className="num" /></tr></thead><tbody>
        {d.recent_badges.map((r, i) => <tr key={i}><td><Who name={r.name} /></td><td className="small">{`${BADGE_ICON[r.badge] || "🏅"} ${title(r.badge)}`}</td><td className="num small muted">{L.ago(r.t)}</td></tr>)}</tbody></table></div>
    </div>}
  </div>);
}

function Seasons({ d }) {
  return (<div className="card">
    <div className="row"><h2 style={{ margin: 0 }}>Seasons</h2><span className="spacer" />
      <span className={"pill " + (d.seasons ? "good" : "")}><span className="dot" />{d.seasons ? `Season ${d.season.season} · ${d.season.days_left === 1 ? "1 day" : d.season.days_left + " days"} left` : "Off"}</span></div>
    <p className="small muted">{d.seasons ? "On the 1st of every month the plugin keeps each leaderboard's winner, gives them the Season champion badge, and starts lap times, speed traps and win counts again from zero. Players see it with /season."
      : "Turn monthly seasons on under Game rules to give everyone a fresh start every month. Until then times are kept forever."}</p>
    {d.seasons && d.season_archive.length === 0 && <p className="small muted">The first season ends on the 1st. Its winners show up here.</p>}
    {d.season_archive.map((s, i) => <details key={s.season} open={i === 0} className="small" style={{ marginTop: 8 }}><summary><b>{`Season ${s.season}`}</b></summary>
      <table style={{ marginTop: 6 }}><tbody>{s.winners.map((w, j) => <tr key={j}><td className="muted">{w.label}{w.what ? ": " + w.what : ""}</td><td><Who name={w.name} /></td><td className="num mono">{w.shown}</td></tr>)}</tbody></table></details>)}
  </div>);
}

/* ================================================================== weekly recap */
function Recap() {
  const [d, again, v, err] = useLoad("/api/recap");
  if (!d) return <CardWait err={err} retry={again} />;
  const sel = id => Number(document.getElementById(id).value);
  const save = async () => { try { const r = await L.api("/api/recap", { json: { on: chk("rc_on"), day: sel("rc_day"), hour: sel("rc_hour") } }); L.toast(r.note, 6000); again(); } catch (e) { L.toast(e.message, 6000); } };
  const send = async () => {
    if (!confirm(`Post this week's recap to ${d.channels.join(" and ")} now?`)) return;
    try { const r = await L.api("/api/recap", { json: { send: true } }); L.toast(r.note, 6000); again(); } catch (e) { L.toast(e.message, 6000); }
  };
  return (<div className="card" key={v}>
    <div className="row"><h2 style={{ margin: 0 }}>Weekly recap</h2><span className="spacer" /><span className={"pill " + (d.on ? "good" : "")}><span className="dot" />{d.on ? "On" : "Off"}</span></div>
    <p className="small muted">{"Once a week, a short post about the week on your server: who played most, new records, races, cops and robbers and badges. It goes where your event announcements go."}</p>
    <Toggle id="rc_on" on={d.on} title="Post a recap every week">{d.channels.length ? "To " + d.channels.join(" and ") : "Set up the Discord webhook (Settings → Discord), Telegram or a custom webhook first"}</Toggle>
    <div className="row" style={{ gap: 8, margin: "6px 0" }}>
      <label className="small" htmlFor="rc_day">{"Day"}</label>
      <select id="rc_day" defaultValue={d.day} style={{ width: "auto" }}>{d.days.map((x, i) => <option key={x} value={i}>{x}</option>)}</select>
      <label className="small" htmlFor="rc_hour">{"Time"}</label>
      <select id="rc_hour" defaultValue={d.hour} style={{ width: "auto" }}>{Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{`${String(h).padStart(2, "0")}:00`}</option>)}</select>
      <span className="spacer" /><button className="btn primary sm" onClick={save}>Save</button></div>
    <h3 className="ph">This week's recap would say</h3>
    {d.preview ? <div className="recap"><b>{d.preview.title}</b>{d.preview.text.split("\n").map((l, i) => <div key={i}>{l.replace(/\\([*_~\x60|>])/g, "$1")}</div>)}</div>
      : <p className="small muted">Nobody played in the last 7 days, so there's nothing to post. A week without players is skipped.</p>}
    <div className="row" style={{ marginTop: 8 }}>{d.last && <span className="small muted">{"Last posted " + L.ago(d.last)}</span>}<span className="spacer" />
      {d.preview && d.channels.length > 0 && <button className="btn sm" onClick={send}>Post it now</button>}</div>
  </div>);
}

/* ================================================================== the page */
const HOWTO = [
  ["/race Canyon run 3", "start a race on a track, 3 laps"], ["/race join", "take part in the race that's starting"],
  ["/cnr start", "start cops and robbers"], ["/cnr join cop", "join, and ask to be a cop (or robber)"],
  ["/laps", "best lap times"], ["/trap", "speed trap records"], ["/badges", "your badges"], ["/season", "this season and last season's winners"],
  ["/champ", "championship standings"],
];

export function Games({ reload }) {
  const [d, err, retry] = useApi("/api/games", reload);
  if (!d) return <PageWait err={err} retry={retry} cards={4} />;
  const canEdit = canEditGames();
  return (<>
    <h1>{"Games"}</h1>
    <p className="muted" style={{ marginTop: -6 }}>{"Races, cops and robbers, speed traps and badges - all started by players in the chat. Results show up here."}</p>
    {!d.plugin && <div className="issue warning"><span className="ic">⚠</span><span>{"The EasyServer plugin isn't on this server yet - run the installer again."}</span></div>}
    <LiveMap />
    <details className="card howto"><summary><b>{"Commands for players"}</b></summary>
      <table className="small" style={{ marginTop: 8 }}><tbody>{HOWTO.map(([c, w]) => <tr key={c}><td className="mono" style={{ whiteSpace: "nowrap" }}>{c}</td><td className="muted">{w}</td></tr>)}</tbody></table>
      <p className="small muted" style={{ margin: "6px 0 0" }}>{"Admins make tracks with /track new and speed traps with /trap new. Everyone sees the list with /help."}</p></details>
    {canEdit && <Rules d={d} again={retry} />}
    <Races d={d} />
    {(d.champ || canEdit || d.champ_history.length > 0) && <Championship d={d} canEdit={canEdit} again={retry} />}
    <CopsAndRobbers d={d} />
    <LapTimes key={"l" + reload} canEdit={canEdit} />
    <Traps d={d} canEdit={canEdit} again={retry} />
    <Badges d={d} />
    <Seasons d={d} />
    {canEdit && <Recap />}
    <ProfileHost />
  </>);
}
