// Config page. The forms keep their values in the inputs themselves (uncontrolled); Save reads them by id.
import { useEffect, useRef, useState } from "react";
import * as L from "./legacy.js";

const S = () => L.state();
const $ = id => document.getElementById(id);
const val = id => $(id).value, chk = id => $(id).checked;
const lines = id => val(id).split("\n").map(x => x.trim()).filter(Boolean);
const commas = id => val(id).split(",").map(x => x.trim()).filter(Boolean);
const TIME = { colorScheme: "light dark", color: "inherit" };
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const clock = t => new Date(t * 1000).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" });
const Pill = ({ on, children }) => <span className={"pill " + (on ? "good" : "")}><span className="dot" />{children}</span>;
const Mono = ({ children }) => <span className="mono">{children}</span>;
const Toggle = ({ id, on, title, children, style }) => <label className="toggle" style={style}><input type="checkbox" id={id} defaultChecked={!!on} /><span><b>{title}</b>{children !== undefined && <small>{children}</small>}</span></label>;
const Warn = ({ children }) => <div className="issue warning"><span className="ic">⚠</span><span>{children}</span></div>;
const Head = ({ title, pill, on }) => <div className="row"><h2 style={{ margin: 0 }}>{title}</h2><span className="spacer" /><Pill on={on}>{pill}</Pill></div>;
const everyText = n => n === 24 ? "Once a day" : `Every ${n} hour${n === 1 ? "" : "s"}`;
const warnText = n => n ? `${n} min before` : "No countdown";

// Load data for one card; `again()` loads it again and redraws the card's inputs.
function useLoad(fn, deps = []) {
  const [st, setSt] = useState({ d: null, v: 0, err: "" });
  const again = async () => {
    try { const d = await fn(); setSt(s => ({ d, v: s.v + 1, err: "" })); }
    catch (e) { setSt(s => ({ ...s, err: e.message })); }
  };
  useEffect(() => { again(); }, deps);
  return [st.d, again, st.v, st.err];
}
const post = async (path, body, ms, after) => {
  try { const r = await L.api(path, { json: body }); L.toast(r.note, ms); if (after) after(r); return r; } catch (e) { L.toast(e.message, 6000); }
};

/* ---------------- problems found in the config */
const Issues = ({ list }) => list.length ? list.map((i, k) => <div key={k} className={"issue " + i.level}><span className="ic">{i.level === "error" ? "!" : i.level === "warning" ? "⚠" : "i"}</span><span>{i.message}</span>{i.line ? <span className="ln">{`line ${i.line}`}</span> : null}</div>)
  : <div className="issue info"><span className="ic">✓</span><span>No problems found.</span></div>;

/* ---------------- the form: basics, options, AuthKey, advanced */
function Field({ f, maps }) {
  const id = "f_" + f.section + "_" + f.key;
  if (f.type === "bool") return <Toggle id={id} on={f.value} title={f.label}>{f.help}</Toggle>;
  if (f.type === "map") {
    const cur = f.value;
    return <label className="f"><span>{f.label}</span><select id={id} defaultValue={cur}>
      <optgroup label="Built-in maps">{maps.builtin.map(x => <option key={x}>{x}</option>)}</optgroup>
      {maps.mods.length > 0 && <optgroup label="Map mods">{maps.mods.map(x => <option key={x}>{x}</option>)}</optgroup>}
      {cur && !maps.builtin.includes(cur) && !maps.mods.includes(cur) && <optgroup label="Current"><option>{cur}</option></optgroup>}
    </select><small>{f.help}</small></label>;
  }
  const t = f.type === "int" ? { type: "number", min: f.min ?? "", max: f.max ?? "" } : { type: "text", maxLength: f.max ?? 500 };
  return <label className="f"><span>{f.label}</span><input {...t} id={id} defaultValue={f.value ?? ""} /><small>{f.help}</small></label>;
}

/* ---------------- who can join (allow-list) */
function WhoCanJoin() {
  const [al, again, v] = useLoad(() => L.api("/api/allowlist"));
  if (!al) return null;
  const denied = al.denied.filter(x => !al.names.some(n => n.toLowerCase() === x.name.toLowerCase()));
  const allow = (e, name) => {
    e.preventDefault();
    const ta = $("al_names"), have = ta.value.split("\n").map(x => x.trim().toLowerCase());
    if (!have.includes(name.toLowerCase())) ta.value = (ta.value.trim() ? ta.value.trim() + "\n" : "") + name;
    L.toast(name + " added - press Save list");
  };
  const save = async () => {
    const on = chk("al_on"), names = lines("al_names");
    if (on && !names.length) return L.toast("Add at least one player name first");
    if (on && !al.enabled && !confirm("Make the server invite-only?\n\n• Only these " + names.length + " player(s) can join: " + names.slice(0, 8).join(", ") + (names.length > 8 ? ", …" : "") + "\n• Everyone else and all guests get an \"invite-only\" message\n• Players already online stay connected\n\nContinue?")) return;
    if (!on && al.enabled && !confirm("Turn the allow-list off? Anyone will be able to join again.")) return;
    post("/api/allowlist", { enabled: on, names }, undefined, again);
  };
  return (<div className="card" style={{ marginTop: 16 }} key={v}>
    <Head title="Who can join" on={al.enabled} pill={al.enabled ? "Invite-only" : "Anyone can join"} />
    <p className="small muted">BeamMP has no join password, so this works like a guest list: when it's on, only the BeamMP usernames below can join and everyone else gets a friendly "invite-only" message. Guests (players without an account) are refused while it's on. Changes work immediately - no restart.</p>
    {!al.plugin && <Warn>The EasyServerStats plugin is missing, so the list can't be enforced. Run the installer's Update once.</Warn>}
    <Toggle id="al_on" on={al.enabled} title="Only let in players on the list">Players already online are not kicked</Toggle>
    <label className="f"><span>Allowed players (one BeamMP username per line, not case-sensitive)</span><textarea id="al_names" rows={6} spellCheck={false} placeholder={"Bazsi\nDani\nZoli"} style={{ minHeight: 120 }} defaultValue={al.names.join("\n")} /><small>{`${al.names.length} on the list`}</small></label>
    {denied.length > 0 && <><p className="small" style={{ margin: "14px 0 6px" }}><b>Recently refused</b> <span className="muted">(last 7 days)</span></p>
      <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>{denied.map(x => <span key={x.name} className="badge">{x.name + (x.guest ? " · guest" : "") + " · " + L.ago(x.t)}{!x.guest && <> <a href="#" onClick={e => allow(e, x.name)}>+ allow</a></>}</span>)}</div></>}
    <div className="row" style={{ marginTop: 14 }}><button className="btn primary" onClick={save}>Save list</button></div>
  </div>);
}

/* ---------------- map vote */
function MapVote() {
  const [mv, again, v] = useLoad(() => L.api("/api/mapvote"));
  if (!mv) return null;
  const save = () => post("/api/mapvote", { enabled: chk("mv_on"), maps: [...document.querySelectorAll("[data-vm]")].filter(x => x.checked).map(x => x.dataset.vm) }, undefined, again);
  return (<div className="card" style={{ marginTop: 16 }} key={v}>
    <Head title="Map vote" on={mv.enabled} pill={mv.enabled ? "On" : "Off"} />
    <p className="small muted">Players type <Mono>/vote</Mono> in the game chat to see the maps, then <Mono>/vote 2</Mono> to pick one. When more than half of the players online agree, everyone is told and the server switches about 30 seconds later. At most one change every 5 minutes.</p>
    <Toggle id="mv_on" on={mv.enabled} title="Let players vote for the map">Pick at least two maps below</Toggle>
    <div className="row" style={{ flexWrap: "wrap", gap: 6, marginTop: 8 }}>{mv.available.map(x => <label key={x} className="badge" style={{ cursor: "pointer" }}><input type="checkbox" data-vm={x} defaultChecked={mv.maps.includes(x) || !mv.maps.length} /> {x}</label>)}</div>
    <div className="row" style={{ marginTop: 14 }}><button className="btn primary" onClick={save}>Save map vote</button></div>
  </div>);
}

/* ---------------- restarts & updates */
function Restarts() {
  const [rs, again, v] = useLoad(() => L.api("/api/restarts"));
  if (!rs) return null;
  const save = () => {
    const body = { on: chk("rs_on"), every: Number(val("rs_every")), at: val("rs_at"), warn: Number(val("rs_warn")), when: val("rs_when") };
    if ($("rs_auto")) body.auto_update = chk("rs_auto");
    post("/api/restarts", body, 6000, again);
  };
  return (<div className="card" style={{ marginTop: 16 }} key={v}>
    <Head title="Restarts & updates" on={rs.on} pill={rs.on ? "Restart " + (rs.every === 24 ? "daily " + rs.at : "every " + rs.every + " h") : "Off"} />
    <p className="small muted">A fresh start now and then keeps a long-running server smooth. Players get a countdown in the chat first and can rejoin right after.</p>
    <Toggle id="rs_on" on={rs.on} title="Restart the server on a schedule">Off by default</Toggle>
    <div className="grid g3" style={{ gap: 12, margin: "4px 0 8px" }}>
      <label className="f" style={{ margin: 0 }}><span>How often</span><select id="rs_every" defaultValue={rs.every}>{rs.every_choices.map(n => <option key={n} value={n}>{everyText(n)}</option>)}</select></label>
      <label className="f" style={{ margin: 0 }}><span>{rs.every === 24 ? "At" : "Starting at"}</span><input type="time" id="rs_at" defaultValue={rs.at} style={TIME} /><small>This computer's time</small></label>
      <label className="f" style={{ margin: 0 }}><span>Countdown in chat</span><select id="rs_warn" defaultValue={rs.warn}>{rs.warn_choices.map(n => <option key={n} value={n}>{warnText(n)}</option>)}</select></label>
    </div>
    <label className="f"><span>If players are online</span><select id="rs_when" defaultValue={rs.when}><option value="countdown">Restart anyway, after the countdown</option><option value="empty">Wait until nobody is online (up to 2 hours, then skip)</option></select></label>
    {rs.next ? <p className="small muted">Next restart: <b>{clock(rs.next)}</b></p> : null}
    {S().SERVER === "main" && <Toggle id="rs_auto" on={rs.auto_update} title="Install BeamMP updates automatically">At the scheduled restart, if a new BeamMP server version is out. All servers use the same BeamMP program, so the others restart too.{rs.update_available && <> <b>An update is available now.</b></>}</Toggle>}
    <div className="row" style={{ marginTop: 12 }}><button className="btn primary" onClick={save}>Save restarts</button></div>
  </div>);
}

/* ---------------- vehicle rules */
function VehicleRules() {
  const [v, again, ver] = useLoad(() => L.api("/api/vehicles"));
  if (!v) return null;
  const r = v.rules, act = v.activity;
  const blockedSet = new Set(v.blocked.map(b => b.jbm.toLowerCase()));
  const sugg = v.mods.filter(m => (m.heavy || m.kind !== "car") && !blockedSet.has(m.jbm.toLowerCase()));
  const Kind = ({ k }) => k === "unknown" ? null : <span className={"badge " + (/heavy/.test(k) ? "warn" : "")}>{k}</span>;
  const list = id => val(id).split(/[\s,]+/).map(x => x.trim()).filter(Boolean);
  const save = () => post("/api/vehicles", { on: chk("vr_on"), props: chk("vr_props"), heavyprops: chk("vr_hprops"), trailers: chk("vr_trail"), heavymods: chk("vr_hmods"), exempt: chk("vr_exempt"), only: chk("vr_only"), cooldown: val("vr_cd"), spam: val("vr_spam"), cars: list("vr_cars"), allow: list("vr_allow") }, 7000, again);
  const block = (jbm, on) => post("/api/vehicles/block", { jbm, block: on }, 6000, again);
  return (<div className="card" style={{ marginTop: 16 }} key={ver}>
    <Head title="Vehicle rules: block props, heavy cars & spawn spam" on={r.on} pill={r.on ? `${v.blocked.length} blocked` : "Off"} />
    <p className="small muted">The server refuses a blocked car or prop before anyone sees it, and tells the player why. Works within 10 seconds, no restart, no extra mod for players.</p>
    <div className="grid g2" style={{ gap: 10 }}>{v.presets.map(p => <div key={p.id} className="card tight" style={{ padding: "12px 14px", ...(p.id === v.preset ? { borderColor: "var(--accent)" } : {}) }}>
      <div className="row"><b>{p.label}</b><span className="spacer" /><button className="btn sm" disabled={p.id === v.preset} onClick={() => post("/api/vehicles/preset", { preset: p.id }, 6000, again)}>{p.id === v.preset ? "In use" : "Use"}</button></div><div className="small muted">{p.about}</div></div>)}</div>
    <Toggle id="vr_on" on={r.on} title="Vehicle rules on" style={{ marginTop: 12 }}>Turn off to allow everything without losing your choices</Toggle>
    <Toggle id="vr_props" on={r.props} title="Block props">{`Cones, barrels, balls, ramps, walls … (${v.base.props.length} game props + prop mods)`}</Toggle>
    <Toggle id="vr_hprops" on={r.heavyprops} title="Block big physics props">Crushers, spinners, giant rollers, shipping containers, bridges - the usual cause of sudden server-wide lag</Toggle>
    <Toggle id="vr_trail" on={r.trailers} title="Block trailers">Caravans, flatbeds, tankers, dry vans …</Toggle>
    <Toggle id="vr_hmods" on={r.heavymods} title="Block heavy mod cars (auto-detected)">{`EasyServer looks inside your car mods and counts how complex they are (over ${v.heavy_limits.nodes.toLocaleString()} nodes or ${v.heavy_limits.beams.toLocaleString()} beams). Very complex cars make everyone's game slower.`}</Toggle>
    <Toggle id="vr_exempt" on={r.exempt} title="Admins may spawn anything">Admins are set under Moderation</Toggle>
    <div className="grid g2" style={{ gap: 12 }}>
      <label className="f" style={{ margin: 0 }}><span>Seconds between spawns</span><input type="number" id="vr_cd" min={0} max={3600} defaultValue={r.cooldown} /><small>0 = no wait</small></label>
      <label className="f" style={{ margin: 0 }}><span>Max spawns per minute</span><input type="number" id="vr_spam" min={0} max={120} defaultValue={r.spam} /><small>Stops spawn spam. 0 = no limit</small></label></div>
    <label className="f"><span>Also block these cars (model names)</span><input type="text" id="vr_cars" defaultValue={r.cars.join(", ")} placeholder="e.g. bolide, sbr" spellCheck={false} /><small>Use the Block buttons below, or type model names separated by commas</small></label>
    <Toggle id="vr_only" on={r.only} title="Only allow these cars">One-make racing: everything else is refused</Toggle>
    <label className="f"><span>Allowed cars (when "only" is on)</span><input type="text" id="vr_allow" defaultValue={r.allow.join(", ")} placeholder="e.g. covet" spellCheck={false} /></label>
    <div className="row"><button className="btn primary sm" onClick={save}>Save rules</button></div>
    {sugg.length > 0 && <><h3 style={{ marginTop: 16 }}>Found in your mods</h3><p className="small muted">Auto-detected props, trailers and heavy cars that are still allowed.</p>
      <table><tbody>{sugg.slice(0, 20).map(m => <tr key={m.jbm + m.mod}><td><b>{m.name || m.jbm}</b> <span className="small muted mono">{m.jbm}</span> <Kind k={(m.heavy && m.kind === "car" ? "heavy " : "") + m.kind} />
        <div className="small muted">{`${m.mod} · ${m.nodes.toLocaleString()} nodes, ${m.beams.toLocaleString()} beams`}</div></td><td className="num"><button className="btn sm" onClick={() => block(m.jbm, true)}>Block</button></td></tr>)}</tbody></table></>}
    <h3 style={{ marginTop: 16 }}>{`Spawned on this server (last ${act.days} days)`}</h3>
    {act.seen.length ? <table><tbody>{act.seen.slice(0, 25).map(s => <tr key={s.jbm}><td><span className="mono">{s.jbm}</span> <Kind k={s.kind} />{s.blocked && <span className="badge bad">blocked</span>}
      <div className="small muted">{`${s.count}× by ${s.players} player${s.players === 1 ? "" : "s"} · last ${L.fmtTime(s.last)}`}</div></td>
      <td className="num">{r.cars.some(c => c.toLowerCase() === s.jbm.toLowerCase()) ? <button className="btn sm" onClick={() => block(s.jbm, false)}>Allow</button> : s.blocked ? null : <button className="btn sm" onClick={() => block(s.jbm, true)}>Block</button>}</td></tr>)}</tbody></table>
      : <p className="small muted">Nothing yet - the list fills up as players spawn cars.</p>}
    {(act.blocked.length > 0 || act.spam.length > 0) && <><h3 style={{ marginTop: 16 }}>Refused lately</h3><ul className="small">
      {act.blocked.slice(0, 10).map((b, i) => <li key={"b" + i}>{L.fmtTime(b.t) + ": "}<b>{b.name}</b> tried <span className="mono">{b.jbm}</span>{` (${b.why})`}</li>)}
      {act.spam.slice(0, 5).map((b, i) => <li key={"s" + i}>{L.fmtTime(b.t) + ": "}<b>{b.name}</b> spawned too many cars in a minute</li>)}</ul></>}
  </div>);
}

/* ---------------- in-game tools */
function Tools() {
  const [tl, again, v] = useLoad(() => L.api("/api/tools").catch(() => null));
  if (!tl) return null;
  const save = () => post("/api/tools", { suggest: chk("tl_sug"), tp: chk("tl_tp"), tp_cd: val("tl_tpcd"), repair: val("tl_rep"), repair_cd: val("tl_repcd") }, 8000, again);
  return (<div className="card" style={{ marginTop: 16 }} key={v}>
    <Head title="In-game tools: commands, teleport & repair" on={tl.installed} pill={tl.installed ? "On" : "Off"} />
    <p className="small muted">{`Chat commands players can use. They need a tiny helper mod (${L.fmtSize(tl.size)}) that players download automatically when they join - EasyServer adds and removes it for you. It only shows this server's commands, and moves or repairs the player's own car when the server allows it.`}</p>
    <Toggle id="tl_sug" on={tl.suggest} title="Command suggestions in the chat">When players type "/" in the chat they see the commands of this server and can press Tab to complete them. A mistyped command gets a "did you mean ...?" answer either way.</Toggle>
    <Toggle id="tl_tp" on={tl.tp} title="/tp name - teleport to another player">The other player has to type /tpaccept, so nobody can be followed against their will</Toggle>
    <label className="f" style={{ maxWidth: 260 }}><span>Wait between teleports (seconds)</span><input type="number" id="tl_tpcd" min={0} max={3600} defaultValue={tl.tp_cd} /></label>
    <label className="f" style={{ maxWidth: 420 }}><span>Repairing cars</span><select id="tl_rep" defaultValue={tl.repair}>
      <option value="free">Normal - reset keys work (and /repair)</option>
      <option value="cooldown">Realism - reset keys off, /repair every few minutes</option>
      <option value="off">Hardcore - no resets, no repairs</option></select>
      <small>Realism and Hardcore turn off the reset / recover / teleport keys for everyone on this server (good for roleplay and realism servers)</small></label>
    <label className="f" style={{ maxWidth: 260 }}><span>Minutes between repairs (Realism)</span><input type="number" id="tl_repcd" min={1} max={120} defaultValue={tl.repair_cd} /></label>
    <div className="row"><button className="btn primary sm" onClick={save}>Save</button></div>
  </div>);
}

/* ---------------- security presets */
function Presets({ reloadPage }) {
  const [pr] = useLoad(() => L.api("/api/preset"));
  if (!pr) return null;
  const use = p => {
    if (!confirm("Use the \"" + p.label + "\" preset?\n\n" + p.about + "\n\nYou can change every setting afterwards.")) return;
    post("/api/preset", { id: p.id, preset: p.label }, 8000, reloadPage);
  };
  const cur = pr.current && pr.presets.find(x => x.id === pr.current);
  return (<div className="card" style={{ marginTop: 16 }}><h2>Security presets</h2>
    <p className="small muted">{"One click sets who can join, guests, anti-bot checks, the chat filter and flood protection together. "}{cur ? <>Right now this server matches <b>{cur.label}</b>.</> : "Your current settings are a custom mix."}</p>
    <div className="grid g2" style={{ gap: 10 }}>{pr.presets.map(p => <div key={p.id} className="card tight" style={{ padding: "12px 14px", ...(p.id === pr.current ? { borderColor: "var(--accent)" } : {}) }}>
      <div className="row"><b>{p.label}</b>{p.id === "most_secure" && <> <span className="badge">recommended</span></>}<span className="spacer" /><button className="btn sm" disabled={p.id === pr.current} onClick={() => use(p)}>{p.id === pr.current ? "In use" : "Use"}</button></div>
      <div className="small muted">{p.about}</div></div>)}</div>
  </div>);
}

/* ---------------- announcements at set times */
function Timed() {
  const [tm, again, v] = useLoad(() => L.api("/api/timed"));
  const [rows, setRows] = useState([]);
  useEffect(() => { if (tm) setRows(tm.items.map((x, i) => ({ ...x, _k: i }))); }, [tm, v]);
  if (!tm) return null;
  const set = (i, patch) => setRows(rs => rs.map((r, j) => j === i ? { ...r, ...patch } : r));
  const add = () => { if (rows.length >= 20) return L.toast("At most 20"); setRows([...rows, { at: "20:00", days: [4, 5], text: "", discord: false, on: true, _k: Date.now() }]); };
  const save = () => post("/api/timed", { items: rows.map(({ _k, ...x }) => x) }, undefined, again);
  return (<div className="card" style={{ marginTop: 16 }}><h2>Announcements at set times</h2>
    <p className="small muted">{`Say something in the game chat at a fixed time, e.g. "Race night starts at 21:00!" every Friday at 20:30. Only sent when someone is online${tm.discord ? "; tick Discord to post it there too (and to Telegram / the webhook if set up)" : ""}.`}</p>
    <div>{rows.length ? rows.map((x, i) => <div key={x._k} className="card tight" style={{ padding: "10px 12px", marginTop: 8 }}>
      <div className="row" style={{ flexWrap: "wrap", gap: 8 }}><input type="time" value={x.at || "20:00"} onChange={e => set(i, { at: e.target.value })} style={{ width: "auto", ...TIME }} />
        {DAYS.map((d, j) => <label key={d} className="badge" style={{ cursor: "pointer" }}><input type="checkbox" checked={(x.days || []).includes(j)} onChange={e => set(i, { days: e.target.checked ? [...(x.days || []), j].sort() : (x.days || []).filter(k => k !== j) })} /> {d}</label>)}
        <span className="spacer" /><label className="small"><input type="checkbox" checked={!!x.discord} onChange={e => set(i, { discord: e.target.checked })} /> Discord</label>
        <label className="small"><input type="checkbox" checked={x.on !== false} onChange={e => set(i, { on: e.target.checked })} /> On</label>
        <button className="btn sm danger" onClick={() => setRows(rows.filter((_, j) => j !== i))}>✕</button></div>
      <textarea rows={2} maxLength={600} style={{ minHeight: 44, marginTop: 6 }} placeholder="Up to 3 lines" value={x.text || ""} onChange={e => set(i, { text: e.target.value })} /></div>)
      : <p className="small muted">None yet.</p>}</div>
    <div className="row" style={{ marginTop: 8, gap: 6 }}><button className="btn sm" onClick={add}>+ Add</button><button className="btn sm primary" onClick={save}>Save</button></div>
  </div>);
}

/* ---------------- config history */
function History({ reloadPage }) {
  const [hi] = useLoad(() => L.api("/api/config/history"));
  const [diff, setDiff] = useState(null), other = useRef(null);
  if (!hi) return null;
  const others = S().SERVERS.filter(x => x.id !== S().SERVER);
  const show = async q => { try { setDiff(await L.api("/api/config/diff?" + q)); } catch (e) { L.toast(e.message); } };
  const cmp = (v, i) => show(i === 0 && hi.items[1] ? "v=" + encodeURIComponent(hi.items[1].id) + "&w=" + encodeURIComponent(hi.items[0].id) : "v=" + encodeURIComponent(v.id));
  const restore = v => { if (confirm("Go back to this version of the config? The current one is kept in the history too.")) post("/api/config/restore", { v: v.id }, 7000, reloadPage); };
  const fmt = v => v === undefined || v === null ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v);
  return (<div className="card" style={{ marginTop: 16 }}>
    <div className="row"><h2 style={{ margin: 0 }}>What changed?</h2><span className="spacer" /><span className="small muted">{`Last ${hi.keep} versions are kept`}</span></div>
    <p className="small muted">Every time the config is saved - here, by a template, a preset or a map switch - the old version is kept. Compare and go back with one click.</p>
    {hi.items.length ? <table style={{ marginTop: 6 }}><tbody>{hi.items.slice(0, 15).map((v, i) => <tr key={v.id}><td>{L.fmtTime(v.t)}</td><td>{v.who}</td><td className="small muted">{v.why || ""}</td>
      <td className="num"><div className="row" style={{ justifyContent: "flex-end", gap: 6 }}><button className="btn sm" onClick={() => cmp(v, i)}>{i === 0 ? "Show change" : "Compare with now"}</button>
        {i > 0 && <button className="btn sm" onClick={() => restore(v)}>Restore</button>}</div></td></tr>)}</tbody></table>
      : <p className="small muted">No changes saved yet.</p>}
    {others.length > 0 && <div className="row" style={{ marginTop: 10, gap: 8 }}><span className="small">Compare with another server:</span>
      <select ref={other} style={{ maxWidth: 220 }}>{others.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
      <button className="btn sm" onClick={() => show("other=" + encodeURIComponent(other.current.value))}>Compare</button></div>}
    {diff && <div style={{ marginTop: 12, borderTop: "1px solid var(--line)", paddingTop: 12 }}><p className="small"><b>{diff.a}</b> → <b>{diff.b}</b></p>
      {diff.changes.length ? <table><thead><tr><th>Setting</th><th>Before</th><th>After</th></tr></thead><tbody>{diff.changes.map(c => <tr key={c.key}><td className="mono">{c.key}</td><td>{fmt(c.old)}</td><td><b>{fmt(c.new)}</b></td></tr>)}</tbody></table>
        : <p className="small muted">No setting changed (only spacing or comments).</p>}
      {diff.lines.length > 0 && <details style={{ marginTop: 8 }}><summary className="small">Show the exact lines</summary><pre className="mono small" style={{ whiteSpace: "pre-wrap" }}>
        {diff.lines.map((l, i) => <span key={i} style={{ color: l[0] === "+" ? "var(--good-ink)" : l[0] === "-" ? "var(--crit-ink)" : "inherit" }}>{l + "\n"}</span>)}</pre></details>}</div>}
  </div>);
}

/* ---------------- templates, map rotation, welcome & announcements */
function Templates({ reloadPage }) {
  const [tp] = useLoad(() => L.api("/api/templates"));
  if (!tp) return null;
  const use = t => {
    const map = chk("tpl_map");
    if (!confirm(`Use the ${t.label} template? It changes the player limit, car cleanup, AFK removal, chat tags, chat rules and the welcome message${map ? ", and switches the map to " + t.map : ""}.`)) return;
    post("/api/template", { id: t.id, map }, 6000, reloadPage);
  };
  return (<div className="card" style={{ marginTop: 16 }}><h2>Quick setup: server templates</h2>
    <p className="small muted">One click sets the player limit, car cleanup, AFK removal, chat tags, chat rules, a welcome message and tips for the kind of server you want. You can change everything afterwards.</p>
    <div className="grid g2" style={{ gap: 10 }}>{tp.templates.map(t => <div key={t.id} className="card tight" style={{ padding: "12px 14px" }}>
      <div className="row"><b>{t.label}</b><span className="spacer" /><button className="btn sm" onClick={() => use(t)}>Use</button></div>
      <div className="small muted">{t.about}</div><div className="small" style={{ marginTop: 4 }}>{`Map ${t.map} · ${t.max_players} players · tags ${t.tags.join(", ")}`}</div></div>)}</div>
    <Toggle id="tpl_map" on title="Also switch to the template's map" style={{ marginTop: 8 }}>Restarts the server if it's running</Toggle>
  </div>);
}
const everyOpt = (list, day) => list.map(n => <option key={n} value={n}>{n === 24 && day ? "Once a day" : `Every ${n}` + (day ? ` hour${n === 1 ? "" : "s"}` : " minutes")}</option>);
function Rotation() {
  const [ro, again, v] = useLoad(() => L.api("/api/rotation"));
  if (!ro) return null;
  const save = () => post("/api/rotation", { on: chk("ro_on"), maps: [...document.querySelectorAll("[data-rm]")].filter(x => x.checked).map(x => x.dataset.rm), every: Number(val("ro_every")), at: val("ro_at"), warn: Number(val("ro_warn")), empty_only: chk("ro_empty") }, 6000, again);
  return (<div className="card" style={{ marginTop: 16 }} key={v}>
    <Head title="Map rotation" on={ro.on} pill={ro.on ? "On" : "Off"} />
    <p className="small muted">Switch to the next map in the list every few hours, so the server doesn't get boring. Players get a countdown in the chat. Now playing: <b>{ro.current || "?"}</b>{(ro.next ? ` · next change ${L.fmtTime(ro.next)}` : "") + "."}</p>
    <Toggle id="ro_on" on={ro.on} title="Rotate the map">Off by default. Pick at least two maps, in order</Toggle>
    <div className="row" style={{ flexWrap: "wrap", gap: 6, margin: "8px 0" }}>{ro.available.map(x => <label key={x} className="badge" style={{ cursor: "pointer" }}><input type="checkbox" data-rm={x} defaultChecked={ro.maps.includes(x)} /> {x}</label>)}</div>
    <div className="grid g3" style={{ gap: 12, margin: "4px 0 8px" }}>
      <label className="f" style={{ margin: 0 }}><span>How often</span><select id="ro_every" defaultValue={ro.every}>{everyOpt(ro.every_choices, true)}</select></label>
      <label className="f" style={{ margin: 0 }}><span>Starting at</span><input type="time" id="ro_at" defaultValue={ro.at} style={TIME} /></label>
      <label className="f" style={{ margin: 0 }}><span>Countdown in chat</span><select id="ro_warn" defaultValue={ro.warn}>{ro.warn_choices.map(n => <option key={n} value={n}>{warnText(n)}</option>)}</select></label>
    </div>
    <Toggle id="ro_empty" on={ro.empty_only} title="Only change the map when nobody is online">Waits up to 2 hours, then skips that change</Toggle>
    <div className="row" style={{ marginTop: 12 }}><button className="btn primary" onClick={save}>Save rotation</button></div>
  </div>);
}
function Messages() {
  const [ms, again, v] = useLoad(() => L.api("/api/messages"));
  if (!ms) return null;
  const save = () => post("/api/messages", { welcome: chk("ms_welcome"), welcome_text: val("ms_wtext"), announce: chk("ms_announce"), every: Number(val("ms_every")), messages: val("ms_list") }, undefined, again);
  return (<div className="card" style={{ marginTop: 16 }} key={v}>
    <Head title="Welcome message & announcements" on={ms.welcome || ms.announce} pill={ms.welcome && ms.announce ? "Both on" : ms.welcome ? "Welcome on" : ms.announce ? "Announcements on" : "Off"} />
    <p className="small muted">Use <Mono>{"{name}"}</Mono> for the player's name and <Mono>{"{players}"}</Mono> for how many are online. Works right away, no restart needed.{!ms.plugin && <> <b>Start the server once</b> so the stats plugin is installed.</>}</p>
    <Toggle id="ms_welcome" on={ms.welcome} title="Greet players when they join">Only the new player sees it. One line per chat message (up to 5)</Toggle>
    <textarea id="ms_wtext" rows={2} spellCheck={false} style={{ minHeight: 60 }} defaultValue={ms.welcome_text.join("\n")} />
    <Toggle id="ms_announce" on={ms.announce} title="Post announcements in the chat" style={{ marginTop: 10 }}>One message to everyone, in turn - only while someone is online</Toggle>
    <label className="f"><span>Every</span><select id="ms_every" style={{ maxWidth: 220 }} defaultValue={ms.every}>{everyOpt(ms.every_choices, false)}</select></label>
    <label className="f"><span>Announcements (one per line, up to 30)</span><textarea id="ms_list" rows={4} spellCheck={false} placeholder={"Join our Discord: discord.gg/...\nType /help for the commands\nNo ramming - be nice!"} style={{ minHeight: 90 }} defaultValue={ms.messages.join("\n")} /></label>
    <div className="row" style={{ marginTop: 12 }}><button className="btn primary" onClick={save}>Save messages</button></div>
  </div>);
}

/* ---------------- scheduled events */
const LASTS = [30, 60, 90, 120, 180, 240, 360], ANNOUNCE = [[0, "Only when it starts"], [10, "10 min before"], [30, "30 min before"], [60, "1 hour before"], [120, "2 hours before"], [1440, "1 day before"]];
function Events() {
  const [d, again, v] = useLoad(() => L.api("/api/events"));
  const [list, setList] = useState([]);
  useEffect(() => { if (d) setList(d.events.map((e, i) => ({ ...e, _k: i }))); }, [d, v]);
  if (!d) return null;
  const set = (i, patch) => setList(xs => xs.map((x, j) => j === i ? { ...x, ...patch } : x));
  const flip = (arr, x, on) => on ? [...(arr || []), x] : (arr || []).filter(y => y !== x);
  const save = () => post("/api/events", { events: list.map(({ _k, ...e }) => ({ ...e, map: e.map || d.maps[0] })) }, undefined, again);
  const stop = async () => { try { const r = await L.api("/api/events/stop", { method: "POST" }); L.toast(r.note); setTimeout(again, 4000); } catch (e) { L.toast(e.message); } };
  return (<div className="card" style={{ marginTop: 16 }}>
    <Head title="Events" on={list.some(e => e.on !== false)} pill={list.length ? `${list.length} planned` : "None"} />
    <p className="small muted">{`Weekly events like "Friday 20:00 drift night": announced in Discord${d.has_webhook ? "" : " (add a webhook in Settings)"} and the game chat, then the server switches to the event's map and mods, and back to your normal map when it's over. Players can type `}<Mono>/events</Mono> in Discord to see what's coming.</p>
    {d.active && <div className="issue info"><span className="ic">★</span><span><b>{d.active.name}</b>{` is running until ${L.fmtTime(d.active.end)}.`}</span><button className="btn sm" style={{ marginLeft: "auto" }} onClick={stop}>End now</button></div>}
    <div>{list.map((e, i) => <div key={e._k} className="card tight" style={{ padding: "12px 14px", marginTop: 10 }}>
      <div className="row"><input type="text" value={e.name || ""} onChange={x => set(i, { name: x.target.value })} placeholder="Friday drift night" style={{ flex: 1, fontWeight: 600 }} />
        <label className="toggle" style={{ margin: "0 0 0 10px" }}><input type="checkbox" checked={e.on !== false} onChange={x => set(i, { on: x.target.checked })} /><span><b>On</b></span></label>
        <button className="btn sm danger" style={{ marginLeft: 8 }} onClick={() => setList(list.filter((_, j) => j !== i))}>Remove</button></div>
      <div className="row" style={{ flexWrap: "wrap", gap: 6, margin: "8px 0" }}>{d.days.map((n, k) => <label key={k} className="badge" style={{ cursor: "pointer" }}><input type="checkbox" checked={(e.days || []).includes(k)} onChange={x => set(i, { days: flip(e.days, k, x.target.checked).sort() })} /> {n}</label>)}</div>
      <div className="grid g3" style={{ gap: 10 }}>
        <label className="f" style={{ margin: 0 }}><span>Starts at</span><input type="time" value={e.at || "20:00"} onChange={x => set(i, { at: x.target.value })} style={TIME} /></label>
        <label className="f" style={{ margin: 0 }}><span>Lasts</span><select value={e.minutes || 120} onChange={x => set(i, { minutes: Number(x.target.value) })}>{LASTS.map(m => <option key={m} value={m}>{m < 60 ? m + " min" : m / 60 + " h"}</option>)}</select></label>
        <label className="f" style={{ margin: 0 }}><span>Map</span><select value={e.map || d.maps[0]} onChange={x => set(i, { map: x.target.value })}>{d.maps.map(m => <option key={m}>{m}</option>)}</select></label>
      </div>
      {d.mods.length > 0 && <><div className="small" style={{ margin: "8px 0 2px" }}>Turn these mods on during the event (they're turned off again after):</div>
        <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>{d.mods.map(m => <label key={m} className="badge" style={{ cursor: "pointer" }}><input type="checkbox" checked={(e.mods || []).includes(m)} onChange={x => set(i, { mods: flip(e.mods, m, x.target.checked) })} /> {m}</label>)}</div></>}
      <div className="grid g2" style={{ gap: 10, marginTop: 8 }}>
        <label className="f" style={{ margin: 0 }}><span>Announce in Discord and the game</span><select value={e.announce ?? 30} onChange={x => set(i, { announce: Number(x.target.value) })}>{ANNOUNCE.map(([n, l]) => <option key={n} value={n}>{l}</option>)}</select></label>
        <label className="f" style={{ margin: 0 }}><span>Extra text (optional)</span><input type="text" value={e.text || ""} onChange={x => set(i, { text: x.target.value })} placeholder="Bring your best drift car!" /></label>
      </div>
      <label className="toggle"><input type="checkbox" checked={!!e.ping} onChange={x => set(i, { ping: x.target.checked })} /><span><b>Ping @everyone in Discord</b><small>Only in the announcement</small></span></label>
      {e.next ? <div className="small muted">{`Next: ${L.fmtTime(e.next)}`}</div> : null}
    </div>)}</div>
    <div className="row" style={{ marginTop: 12 }}><button className="btn" onClick={() => setList([...list, { name: "", days: [4], at: "20:00", minutes: 120, map: d.maps[0], announce: 30, on: true, _k: Date.now() }])}>Add event</button>
      <button className="btn primary" onClick={save}>Save events</button></div>
  </div>);
}

/* ---------------- moderation & anti-bot */
const KICK_ACTIONS = [["kick", "Kick them (they can rejoin)"], ["ban60", "Ban for 1 hour"], ["ban1440", "Ban for 1 day"], ["ban10080", "Ban for 7 days"], ["banperm", "Ban forever"]];
function Moderation() {
  const [md, again, v] = useLoad(() => L.api("/api/moderation"));
  if (!md) return null;
  const save = () => post("/api/moderation", {
    admins: commas("md_admins"), words: commas("md_words"), filter: chk("md_filter"), spam: chk("md_spam"), spam_limit: Number(val("md_spamlimit")),
    antibot: chk("md_antibot"), verify: chk("md_verify"), guests: !chk("md_guests"), per_ip: Number(val("md_perip")), join_flood: Number(val("md_flood")),
    kickwords: commas("md_kwords"), kickwords_action: val("md_kact"), report: chk("md_report"), votekick: chk("md_votekick"), votekick_min: Number(val("md_vkmin")), chatlog: chk("md_chatlog") }, 5000, again);
  return (<div className="card" style={{ marginTop: 16 }} key={v}>
    <Head title="Moderation & anti-bot" on={md.antibot} pill={md.antibot ? "Anti-bot on" : "Anti-bot off"} />
    <p className="small muted">Kick, mute and ban players on the Players page. Everything here works right away, no restart needed.</p>
    <label className="f"><span>Admins (comma-separated BeamMP names)</span><input type="text" id="md_admins" defaultValue={md.admins.join(", ")} placeholder="e.g. Bazsi, Dani" /><small>Admins can use <Mono>/kick name</Mono>, <Mono>/ban name 1d reason</Mono>, <Mono>/mute name 10</Mono>, <Mono>/unmute</Mono> and <Mono>/unban</Mono> in the game chat</small></label>
    <Toggle id="md_filter" on={md.filter} title="Chat filter">Hides messages with the words below, @everyone and Discord invite links, and refuses player names with links or those words. 3 blocked messages in 10 minutes = 5 minute mute. Off by default</Toggle>
    <label className="f"><span>Blocked words (comma-separated)</span><input type="text" id="md_words" defaultValue={md.words.join(", ")} placeholder="words you don't want in chat" /></label>
    <label className="f"><span>Kick words (comma-separated)</span><input type="text" id="md_kwords" defaultValue={(md.kickwords || []).join(", ")} placeholder="words that get a player removed at once" /><small>A player who writes one of these is removed straight away - even with the chat filter off. Whole words only ("ass" doesn't match "class"), capitals don't matter. Admins are never removed. Empty = off</small></label>
    <label className="f" style={{ maxWidth: 260 }}><span>When someone uses a kick word</span><select id="md_kact" defaultValue={md.kickwords_action}>{KICK_ACTIONS.map(o => <option key={o[0]} value={o[0]}>{o[1]}</option>)}</select></label>
    <Toggle id="md_spam" on={md.spam} title="Anti-spam">More than the number below of messages in 10 seconds = 2 minute mute. Admins are never muted. Off by default</Toggle>
    <label className="f" style={{ maxWidth: 220 }}><span>Messages per 10 seconds</span><input type="number" id="md_spamlimit" min={2} max={30} defaultValue={md.spam_limit} /></label>
    <h2 style={{ marginTop: 16 }}>Reports, vote kick &amp; chat history</h2>
    <Toggle id="md_report" on={md.report} title="Player reports">Players type <Mono>/report name what happened</Mono>. You get an alert (dashboard, Discord, phone - whatever is set up under Notifications) with the chat just before it, and admins in the game see it too. A player can send one report a minute. On by default</Toggle>
    <Toggle id="md_votekick" on={md.votekick} title="Vote kick">When no admin is online, players can type <Mono>/votekick name reason</Mono>. If more than half of the others type <Mono>/yes</Mono> within 90 seconds, that player is kicked and can't rejoin for 10 minutes. Admins can't be voted out, players who just joined can't vote, and nobody can start more than one vote every 5 minutes. Off by default</Toggle>
    <label className="f" style={{ maxWidth: 260 }}><span>Players needed online for a vote kick</span><input type="number" id="md_vkmin" min={3} max={20} defaultValue={md.votekick_min} /><small>So two friends can't kick the third</small></label>
    <Toggle id="md_chatlog" on={md.chatlog} title="Keep a chat history">Saves the game chat on this computer so you can search it on the Players page (about the last few weeks, up to 10 MB). It never leaves this computer. On by default</Toggle>
    <h2 style={{ marginTop: 16 }}>Anti-bot</h2>
    <p className="small muted">{`Stops bots from filling your server. Cloudflare can't protect a game server, so this works inside the game instead. Players who passed the check: ${md.verified}.`}</p>
    <Toggle id="md_antibot" on={md.antibot} title="Turn on anti-bot">Off by default. Turns on the checks below</Toggle>
    <Toggle id="md_verify" on={md.verify} title="Join check">New players must type a code shown in the chat (like <Mono>/verify 4821</Mono>) within 2 minutes, or they're kicked. Each player only does this once</Toggle>
    <Toggle id="md_guests" on={!md.guests} title="Block guests">Players without a BeamMP account can't join - bots usually use guest accounts</Toggle>
    <div className="grid g2" style={{ gap: 12 }}>
      <label className="f" style={{ margin: 0 }}><span>Max players from one internet connection</span><input type="number" id="md_perip" min={0} max={20} defaultValue={md.per_ip} /><small>0 = no limit. Your home network is never limited</small></label>
      <label className="f" style={{ margin: 0 }}><span>Max new players per minute</span><input type="number" id="md_flood" min={0} max={100} defaultValue={md.join_flood} /><small>More than this pauses new joins for 2 minutes and alerts you. 0 = no limit</small></label>
    </div>
    <div className="row" style={{ marginTop: 14 }}><button className="btn primary" onClick={save}>Save moderation</button></div>
  </div>);
}

/* ---------------- cars & chat */
function CarsChat() {
  const [ex, again, v] = useLoad(() => L.api("/api/extras"));
  const [every, setEvery] = useState(null);
  if (!ex) return null;
  const ev = every ?? ex.every;
  const save = () => post("/api/extras", { clear: chk("ex_clear"), every: Number(val("ex_every")), at: val("ex_at"), warn: Number(val("ex_warn")), afk: chk("ex_afk"), afk_minutes: Number(val("ex_afkmin")),
    countdown: chk("ex_countdown"), tag: chk("ex_tag"), top: chk("ex_top"), tags: commas("ex_tags") }, 6000, () => { setEvery(null); again(); });
  return (<div className="card" style={{ marginTop: 16 }} key={v}>
    <Head title="Cars & chat" on={ex.clear} pill={ex.clear ? "Cleanup " + (ex.every === 24 ? "daily " + ex.at : "every " + ex.every + " h") : "Cleanup off"} />
    <p className="small muted">Keeps the map tidy and adds a few chat commands. Everything here works right away - no restart, and players don't need to install anything.</p>
    {!ex.plugin && <Warn>The EasyServerStats plugin is missing on this server, so these can't work. Run the installer again once.</Warn>}
    <Toggle id="ex_clear" on={ex.clear} title="Remove all cars on a schedule">Clears wrecks and forgotten cars. Players get a countdown in the chat first, then can spawn a fresh car right away. On by default.</Toggle>
    <div className="grid g3" style={{ gap: 12, margin: "4px 0 8px" }}>
      <label className="f" style={{ margin: 0 }}><span>How often</span><select id="ex_every" defaultValue={ex.every} onChange={e => setEvery(Number(e.target.value))}>{ex.every_choices.map(n => <option key={n} value={n}>{everyText(n)}</option>)}</select><small>Busy server? Clear more often.</small></label>
      <label className="f" style={{ margin: 0 }}><span>{ev === 24 ? "At" : "Starting at"}</span><input type="time" id="ex_at" defaultValue={ex.at} style={TIME} /><small>This computer's time</small></label>
      <label className="f" style={{ margin: 0 }}><span>Countdown in chat</span><select id="ex_warn" defaultValue={ex.warn}>{ex.warn_choices.map(n => <option key={n} value={n}>{warnText(n)}</option>)}</select><small>Then reminders at 15, 10, 5, 2, 1 min, 30 s and 10…1</small></label>
    </div>
    <p className="small muted">{ex.next_clear ? <>Next cleanup: <b>{clock(ex.next_clear)}</b></> : null}</p>
    <Toggle id="ex_afk" on={ex.afk} title="Remove abandoned cars">A car that hasn't moved for the time below is removed (its owner gets a warning 1 minute before). Covers AFK players and spare cars left at intersections. Cars of players who leave are removed by BeamMP itself.</Toggle>
    <label className="f" style={{ maxWidth: 220 }}><span>After (minutes)</span><input type="number" id="ex_afkmin" min={2} max={120} defaultValue={ex.afk_minutes} /></label>
    <h2 style={{ marginTop: 16 }}>Chat commands</h2>
    <Toggle id="ex_countdown" on={ex.countdown} title="/countdown">Anyone can type <Mono>/countdown 5</Mono> for a "3… 2… 1… GO!" in the chat - for drag races and touge runs</Toggle>
    <Toggle id="ex_tag" on={ex.tag} title="/tag">Players pick a tag that shows in front of their chat messages, like <Mono>[DRIFT] Dani: anyone tandem?</Mono>. <Mono>/tag off</Mono> removes it</Toggle>
    <label className="f"><span>Tags players can choose (comma-separated)</span><input type="text" id="ex_tags" defaultValue={ex.tags.join(", ")} maxLength={300} /><small>Letters, numbers and - only, up to 12 characters each</small></label>
    <Toggle id="ex_top" on={ex.top} title="/top server records">Tracks top speed, distance driven and the longest drive without a reset. <Mono>/top</Mono> shows the leaders, <Mono>/top me</Mono> your own. Also shown on the Players page</Toggle>
    <p className="small muted">Players can type <Mono>/help</Mono> to see the commands that are on.</p>
    <div className="row" style={{ marginTop: 14 }}><button className="btn primary" onClick={save}>Save cars &amp; chat</button></div>
  </div>);
}

/* ---------------- join alerts (Discord) */
function JoinAlerts() {
  const [ja, again, v] = useLoad(() => L.api("/api/joinalerts"));
  if (!ja) return null;
  const save = test => post("/api/joinalerts", { enabled: chk("ja_on"), players: lines("ja_players"), mention: val("ja_mention"), address: chk("ja_addr"), test }, undefined, test ? null : again);
  return (<div className="card" style={{ marginTop: 16 }} key={v}>
    <Head title="Join alerts (Discord)" on={ja.enabled} pill={ja.enabled ? "On" : "Off"} />
    <p className="small muted">Invite your friends automatically: when one of the players below joins this server, a message goes to your Discord channel ("Dani just joined - 3/8 online, come and play!"). Leave the list empty to announce everyone. When someone who isn't on the allow-list tries to join, you also get a Discord message with a one-click <b>Approve</b> link (turn on "Refused players" under Settings → Notifications).</p>
    {!ja.discord && <Warn>Add your Discord webhook under Settings → Notifications first.</Warn>}
    <Toggle id="ja_on" on={ja.enabled} title="Send join alerts">Uses your Discord webhook from Settings</Toggle>
    <label className="f"><span>Players to announce (one per line, empty = everyone)</span><textarea id="ja_players" rows={4} spellCheck={false} placeholder={"Dani\nZoli"} style={{ minHeight: 90 }} defaultValue={ja.players.join("\n")} /></label>
    <label className="f"><span>Who to ping (optional)</span><input id="ja_mention" type="text" defaultValue={ja.mention} placeholder="@here, <@123456789012345678> or <@&role id>" /><small>In Discord: Settings → Advanced → Developer Mode, then right-click a person or role → Copy ID</small></label>
    <Toggle id="ja_addr" on={ja.address} title="Include the server address">Your public IP and port, so friends can direct-connect. Only do this in a private channel.</Toggle>
    <div className="row" style={{ marginTop: 14 }}><button className="btn primary" onClick={() => save(false)}>Save join alerts</button><button className="btn" onClick={() => save(true)}>Save + send test</button></div>
  </div>);
}

/* ---------------- the page */
export function Config({ reload }) {
  const [page, setPage] = useState(0);
  const [d, , v, err] = useLoad(() => L.api("/api/config"), [reload, page]);
  const [mode, setMode] = useState(() => L.store.get("es-config-mode", "form"));
  const [issues, setIssues] = useState(null);
  const tmr = useRef(null);
  useEffect(() => { setIssues(null); }, [v]);
  if (!d) return err ? <div className="banner bad">{err}</div> : <p className="muted">Loading…</p>;
  const reloadPage = () => setPage(p => p + 1);
  const pick = m => { L.store.set("es-config-mode", m); setMode(m); };
  const basic = d.fields.filter(f => !f.advanced && f.type !== "bool"), toggles = d.fields.filter(f => !f.advanced && f.type === "bool"), adv = d.fields.filter(f => f.advanced);
  const portOk = newPort => {
    const oldPort = String(d.fields.find(f => f.key === "Port")?.value ?? "");
    if (!newPort || String(newPort) === oldPort) return true;
    return confirm("This changes your network settings:\n\n" +
      "• Server port " + oldPort + " → " + newPort + "\n" +
      "• This computer's firewall: port " + newPort + " is opened (TCP + UDP) and " + oldPort + " is closed\n" +
      "• Your router is NOT changed - forward port " + newPort + " there yourself for internet play\n" +
      "• Players who saved your server must use the new port\n\nContinue?");
  };
  const saved = r => { setIssues(r.issues || []); L.toast(r.note); if (r.network) setTimeout(() => L.toast("🌐 " + r.network, 9000), 2600); };
  const failed = e => { setIssues((e.data && e.data.issues) || []); L.toast(e.message); };
  const saveForm = async () => {
    const fields = d.fields.map(f => { const el = $("f_" + f.section + "_" + f.key); return { section: f.section, key: f.key, value: f.type === "bool" ? el.checked : el.value }; });
    if (!portOk((fields.find(f => f.key === "Port") || {}).value)) return;
    try { saved(await L.api("/api/config/save", { json: { fields } })); } catch (e) { failed(e); }
  };
  const validate = async () => { try { setIssues((await L.api("/api/config/validate", { json: { raw: val("raw") } })).issues); } catch (e) {} };
  const saveRaw = async () => {
    const m2 = val("raw").match(/^\s*Port\s*=\s*(\d+)/m);
    if (!portOk(m2 && m2[1])) return;
    try { saved(await L.api("/api/config/save", { json: { raw: val("raw") } })); } catch (e) { failed(e); }
  };
  const saveKey = async () => {
    try { const r = await L.api("/api/authkey", { json: { key: val("ak") } }); $("ak").value = ""; L.toast(r.note); reloadPage(); } catch (e) { L.toast(e.message); }
  };
  return (<>
    <div className="row"><div><h1>Server config</h1><p className="sub">Change settings without touching files. Everything is checked before saving.</p></div><span className="spacer" />
      <div className="seg"><button className={mode === "form" ? "on" : ""} onClick={() => pick("form")}>Simple</button><button className={mode === "raw" ? "on" : ""} onClick={() => pick("raw")}>Text (TOML)</button></div></div>
    <div><Issues list={issues || d.issues} /></div>
    <div className={mode === "form" ? "" : "hidden"} key={"f" + v}>
      <div className="grid g2" style={{ marginTop: 12 }}>
        <div className="card"><h2>Basics</h2>{basic.map(f => <Field key={f.key} f={f} maps={d.maps} />)}</div>
        <div className="grid" style={{ alignContent: "start" }}>
          <div className="card"><h2>Options</h2>{toggles.map(f => <Field key={f.key} f={f} maps={d.maps} />)}</div>
          <div className="card"><h2>AuthKey</h2><p className="small muted">{d.has_authkey ? "✓ An AuthKey is saved (encrypted). Paste a new one to replace it." : "No AuthKey yet. Get one free at keymaster.beammp.com (Keys → +)."}</p>
            <div className="row"><input type="password" id="ak" placeholder="Paste AuthKey" autoComplete="off" /><button className="btn" onClick={saveKey}>Save key</button></div></div>
          <details className="card"><summary><b>Advanced</b></summary><div style={{ marginTop: 14 }}>{adv.map(f => <Field key={f.key} f={f} maps={d.maps} />)}</div></details>
        </div>
      </div>
      <div className="row" style={{ marginTop: 16 }}><button className="btn primary" onClick={saveForm}>Save changes</button><span className="muted small" /></div>
    </div>
    <div key={"c" + page + ":" + reload}>
      <WhoCanJoin />
      <MapVote />
      <Restarts />
      <VehicleRules />
      <Tools />
      <Presets reloadPage={reloadPage} />
      <Timed />
      <History reloadPage={reloadPage} />
      <Templates reloadPage={reloadPage} />
      <Rotation />
      <Messages />
      <Events />
      <Moderation />
      <CarsChat />
      <JoinAlerts />
    </div>
    <div className={mode === "raw" ? "" : "hidden"} style={{ marginTop: 12 }} key={"r" + v}>
      <div className="card"><textarea id="raw" spellCheck={false} defaultValue={d.raw} onInput={() => { clearTimeout(tmr.current); tmr.current = setTimeout(validate, 500); }} />
        <div className="row" style={{ marginTop: 12 }}><button className="btn primary" onClick={saveRaw}>Save</button><button className="btn" onClick={validate}>Check</button><span className="muted small">Your AuthKey isn't shown here - it's stored encrypted.</span></div></div>
    </div>
  </>);
}
