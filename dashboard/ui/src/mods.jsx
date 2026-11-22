// Mods page: upload, download size and disk space, light mode, mod sets, the mod list, modpack, server plugins, quarantine.
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import * as L from "./legacy.js";
import { cacheGet, cachedApi, Empty, Oops, PageWait, SkelCard } from "./ui.jsx";

const S = () => L.state();
const NEW_TAB = { target: "_blank", rel: "noopener noreferrer" };
const SAFETY = { clean: ["good", "✓ safe"], warning: ["warn", "⚠ check"], unchecked: ["", "not checked yet"] };
const Lines = ({ items, pre = "" }) => items.map((t, i) => <span key={i}>{i > 0 && <br />}{pre + t}</span>);

// A dialog drawn by React (same look as the old ones)
export function Modal({ children, onClose, width }) {
  return createPortal(<div className="modalbg" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
    <div className="card" style={width ? { width } : undefined}>{children}</div></div>, document.body);
}

/* ---------------- uploads (drag & drop) */
function Uploads({ roomLeft, onDone }) {
  const [items, setItems] = useState([]), [over, setOver] = useState(false);
  const file = useRef(null), room = useRef(roomLeft);
  useEffect(() => { room.current = roomLeft; }, [roomLeft]);
  const set = (id, patch) => setItems(xs => xs.map(x => x.id === id ? { ...x, ...patch } : x));
  const one = (f, id) => new Promise(res => {
    if (!/\.zip$/i.test(f.name)) { set(id, { msg: "Only .zip files" }); return res(); }
    if (room.current != null && f.size > room.current) { set(id, { bad: `Not enough space: this mod is ${L.fmtSize(f.size)} and only ${L.fmtSize(room.current)} is free. Delete or turn off mods you don't play, or use a bigger drive.` }); return res(); }
    const { CSRF, SERVER } = S(), x = new XMLHttpRequest();
    x.open("PUT", "/api/mods/upload?name=" + encodeURIComponent(f.name));
    x.setRequestHeader("X-ES-CSRF", CSRF); x.setRequestHeader("X-ES-Server", SERVER);
    x.upload.onprogress = e => { if (e.lengthComputable) set(id, { pct: e.loaded / e.total * 100 }); };
    x.upload.onload = () => set(id, { msg: "Checking for viruses…" });
    x.onload = () => {
      let j = {}; try { j = JSON.parse(x.responseText); } catch (e) {}
      if (x.status === 422) set(id, { msg: null, blocked: j.reasons || [] });
      else if (x.status !== 200) set(id, { msg: j.error || "Upload failed" });
      else { if (room.current != null) room.current = Math.max(0, room.current - f.size); set(id, { msg: null, ok: j }); }
      res();
    };
    x.onerror = () => { set(id, { msg: "Upload failed" }); res(); };
    x.send(f);
  });
  const upload = async files => {
    const added = files.map((f, i) => ({ id: Date.now() + ":" + i, name: f.name, pct: 0, msg: "Uploading…" }));
    setItems(xs => [...xs, ...added]);
    for (let i = 0; i < files.length; i++) await one(files[i], added[i].id);
    onDone();
  };
  const drag = on => e => { e.preventDefault(); setOver(on); };
  return (<>
    <div className={"drop" + (over ? " over" : "")} onClick={() => file.current.click()} onDragEnter={drag(true)} onDragOver={drag(true)} onDragLeave={drag(false)}
      onDrop={e => { e.preventDefault(); setOver(false); upload([...e.dataTransfer.files]); }}>
      <b>Drag &amp; drop mods here</b><br /><span className="muted">or click to choose files</span>
      <input ref={file} id="mod_files" type="file" accept=".zip" multiple hidden onChange={e => { upload([...e.target.files]); e.target.value = ""; }} /></div>
    <div>{items.map(u => <div key={u.id} className="card" style={{ marginTop: 10 }}><b>{u.name}</b><div className="bar"><i style={{ width: u.pct + "%" }} /></div>
      <div className="small muted">{u.msg ? u.msg
        : u.bad ? <span style={{ color: "var(--crit-ink)" }}>{u.bad}</span>
          : u.blocked ? <><b style={{ color: "var(--crit-ink)" }}>Blocked - not uploaded.</b><br /><Lines items={u.blocked} /></>
            : u.ok ? <><span style={{ color: "var(--good-ink)" }}>{`✓ Uploaded and checked (${(u.ok.checks || []).join(" + ")})`}</span>{u.ok.maps && u.ok.maps.length ? ` · contains map ${u.ok.maps.join(", ")}` : ""}
              {u.ok.safety === "warning" && <div style={{ color: "var(--warn-ink)" }}><Lines items={u.ok.reasons} pre="⚠ " /></div>}</> : null}</div></div>)}</div>
  </>);
}

/* ---------------- plugin install review */
function PluginReview({ j, onClose }) {
  const pl = j.plan, [trust, setTrust] = useState(false);
  const ok = async () => {
    try { const r = await L.api("/api/plugins/install", { json: { job: j.job, trust } }); L.toast(r.note, 9000); onClose(true); }
    catch (e) { L.toast(e.message, 8000); }
  };
  return (<Modal onClose={() => onClose(false)}>
    <h2 style={{ marginTop: 0 }}>{`Install ${j.name}?`}</h2>
    <p className="small muted">{`${j.version || ""} · ${L.fmtSize(j.size || 0)} · SHA-256 `}<span className="mono">{(j.sha256 || "").slice(0, 16) + "…"}</span></p>
    <p className="small"><b>Goes on the server</b> (Resources/Server):</p>
    <ul className="small">{pl.server.length ? pl.server.map(s => <li key={s.folder}><span className="mono">{s.folder}</span>{` - ${s.files} files, ${s.lua} Lua script${s.lua === 1 ? "" : "s"}`}</li>) : <li>nothing</li>}</ul>
    <p className="small"><b>Players download</b> (Resources/Client, virus-checked):</p>
    <ul className="small">{pl.client.length ? pl.client.map(c => <li key={c} className="mono">{c}</li>) : <li>nothing</li>}</ul>
    {pl.skipped > 0 && <p className="small muted">{`${pl.skipped} other file(s) (readme, licence …) are left out.`}</p>}
    {!j.entry && <label className="toggle"><input type="checkbox" checked={trust} onChange={e => setTrust(e.target.checked)} /><span><b>I trust this plugin's author</b><small>It isn't on the list. A server plugin can read and change files the server can reach.</small></span></label>}
    <div className="row" style={{ marginTop: 12 }}><button className="btn primary" onClick={ok}>Install</button><button className="btn" onClick={() => onClose(false)}>Cancel</button></div>
  </Modal>);
}

/* ---------------- server plugins */
function Plugins() {
  const [d, setD] = useState(() => cacheGet("/api/plugins") ?? null), [busy, setBusy] = useState({}), [review, setReview] = useState(null);
  const [gone, setGone] = useState(() => new Set()), [err, setErr] = useState("");
  const file = useRef(null);
  const load = async () => { try { setD(await cachedApi("/api/plugins")); setErr(""); } catch (e) { if (e.message !== "Please log in") setErr(e.message); } };
  useEffect(() => { load(); }, []);
  if (!d) return err ? <Oops err={err} retry={load} style={{ marginTop: 16 }} /> : <SkelCard lines={5} style={{ marginTop: 16 }} />;
  const inst = Object.fromEntries(d.installed.filter(p => !p.id.startsWith("file-") && !p.id.startsWith("manual-")).map(p => [p.id, p]));
  const Errs = ({ p }) => p.errors ? <div className="small" style={{ color: "var(--crit-ink)" }}>{`${p.errors} Lua error${p.errors === 1 ? "" : "s"} in the log: `}<span className="mono">{p.last_error}</span></div> : null;
  const call = async (path, body) => { try { const r = await L.api(path, { json: body }); if (r.note) L.toast(r.note, 7000); load(); } catch (e) { L.toast(e.message, 7000); } };
  const ask = j => new Promise(res => setReview({ j, res }));
  const get = async id => {
    setBusy(b => ({ ...b, [id]: "Starting…" }));
    let r; try { r = await L.api("/api/plugins/fetch", { json: { id } }); } catch (e) { setBusy(b => ({ ...b, [id]: null })); return L.toast(e.message, 7000); }
    const tick = async () => {
      let j; try { j = await L.api("/api/plugins/job?job=" + r.job); } catch (e) { setBusy(b => ({ ...b, [id]: null })); return L.toast(e.message); }
      if (!j.finished) { setBusy(b => ({ ...b, [id]: j.total ? Math.round(100 * j.done / j.total) + "%" : j.done ? L.fmtSize(j.done) : j.state })); return setTimeout(tick, 800); }
      setBusy(b => ({ ...b, [id]: null }));
      if (!j.ok) return L.toast(j.error, 10000);
      if (await ask(j)) load();
    };
    tick();
  };
  const upload = async e => {
    const f = e.target.files[0]; if (!f) return;
    const { CSRF, SERVER } = S();
    const r = await fetch("/api/plugins/upload?name=" + encodeURIComponent(f.name), { method: "PUT", headers: { "X-ES-CSRF": CSRF, "X-ES-Server": SERVER }, body: f });
    let j = {}; try { j = await r.json(); } catch (x) {}
    e.target.value = "";
    if (!r.ok) return L.toast(j.error || "Upload failed", 9000);
    if (await ask(j)) load();
  };
  // Removed with Undo: its files (and any data it keeps in its folder) are deleted after a few seconds.
  const remove = p => {
    const hide = on => setGone(g => { const n = new Set(g); on ? n.add(p.id) : n.delete(p.id); return n; });
    hide(true);
    L.undoable(`${p.name} removed.`, "/api/plugins/remove", { id: p.id }, { onUndo: () => hide(false), after: r => { if (r && r.note) L.toast(r.note, 7000); load(); } });
  };
  const installed = d.installed.filter(p => !gone.has(p.id));
  return (<div className="card" style={{ marginTop: 16 }}><h2>Server plugins</h2>
    <p className="small muted">Plugins add game modes and tools that run on the server (Lua scripts in Resources/Server). EasyServer downloads each one from its author's own GitHub page, shows you what goes where, and installs it only when you say so. <b>A plugin can do anything the server can</b> - only install ones you trust. Restart the server after a change.</p>
    {!d.writable && <div className="banner warn">EasyServer can't write to Resources/Server yet. Run the installer once more - it updates the folder permissions.</div>}
    {installed.length > 0 && <><h3>Installed</h3><table><tbody>{installed.map(p => <tr key={p.id}><td><b className={p.on ? "" : "muted"}>{p.name}</b> {!p.on && <span className="badge">off</span>}{!p.catalog && <span className="badge warn">not from the list</span>}
      <div className="small muted">{(p.author ? `By ${p.author} · ` : "") + (p.version || "") + (p.client.length ? ` · players download: ${p.client.join(", ")}` : "")}{p.page && <>{" · "}<a href={p.page} {...NEW_TAB}>page</a></>}</div><Errs p={p} /></td>
      <td className="num">{d.owner && <div className="row" style={{ justifyContent: "flex-end", gap: 6 }}><button className="btn sm" onClick={() => call("/api/plugins/toggle", { id: p.id, on: !p.on })}>{p.on ? "Turn off" : "Turn on"}</button>
        <button className="btn sm danger" onClick={() => remove(p)}>Remove</button></div>}</td></tr>)}</tbody></table></>}
    {d.other.length > 0 && <><h3>Copied in by hand</h3><table><tbody>{d.other.map(p => <tr key={p.folder}><td><b>{p.folder}</b><Errs p={p} /></td>
      <td className="num">{d.owner && <button className="btn sm" onClick={() => call("/api/plugins/adopt", { folder: p.folder })}>Manage</button>}</td></tr>)}</tbody></table></>}
    {d.own_errors > 0 && <div className="banner warn">{`EasyServer's own plugin has ${d.own_errors} Lua error(s) in the log - another plugin may be interfering. Check Logs.`}</div>}
    <h3>Community plugins</h3>
    <div className="grid g2" style={{ gap: 10 }}>{d.catalog.map(p => <div key={p.id} className="card tight" style={{ padding: "12px 14px" }}>
      <div className="row"><b>{p.name}</b><span className="spacer" />{inst[p.id] && <span className="badge good">installed</span>}</div>
      <div className="small">{p.about}</div>
      <div className="small muted" style={{ marginTop: 4 }}>By <b>{p.author}</b>{" · "}<a href={p.page} {...NEW_TAB}>{p.repo}</a>{p.license ? ` · License: ${p.license}` : ""}</div>
      {p.notes.length > 0 && <ul className="small" style={{ margin: "6px 0 0 16px", padding: 0 }}>{p.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
      {d.owner && <div className="row" style={{ marginTop: 8 }}><button className={"btn sm " + (inst[p.id] ? "" : "primary")} disabled={!!busy[p.id]} onClick={() => get(p.id)}>{busy[p.id] || (inst[p.id] ? "Update" : "Install…")}</button></div>}
    </div>)}</div>
    <p className="small muted" style={{ marginTop: 8 }}>Plugins belong to their authors - thank them on their pages! Missing one? It can be added to the list on GitHub.</p>
    {d.owner && <div className="row" style={{ marginTop: 6 }}><button className="btn sm" onClick={() => file.current.click()}>Install a plugin from a .zip file…</button><input ref={file} type="file" accept=".zip" hidden onChange={upload} /></div>}
    {review && <PluginReview j={review.j} onClose={ok => { review.res(ok); setReview(null); }} />}
  </div>);
}

/* ---------------- one row of the mod list */
function ModRow({ x, u, act, useMap, update }) {
  const [b, setB] = useState(false);
  return (<tr><td><b className={x.enabled ? "" : "muted"}>{x.name}</b>
    {x.builtin ? <span className="badge good">EasyServer tools</span> : <span className={"badge " + SAFETY[x.safety][0]}>{SAFETY[x.safety][1]}</span>}
    {x.enabled ? null : x.parked ? <span className="badge">waiting - light mode</span> : <span className="badge">off</span>}
    {x.maps.map(mp => <span key={mp} className="badge">{`map: ${mp}`}</span>)}
    {(x.needs || []).length > 0 && <span className="badge warn" title="This mod adds parts to a vehicle that isn't in the game or in your other mods, so it does nothing on its own. Add the mod that has this vehicle.">{`needs the mod for: ${x.needs.join(", ")}`}</span>}
    {u ? (u.update ? <span className="badge warn">{`update ${u.have || "?"} → ${u.latest || "new"}`}</span> : <span className="badge good">{u.have ? `up to date (${u.have})` : "up to date"}</span>) : null}
    {x.reasons.length > 0 && <div className="small" style={{ color: "var(--warn-ink)", marginTop: 4 }}><Lines items={x.reasons} /></div>}</td>
    <td className="num muted">{L.fmtSize(x.size)}</td>
    <td className="num"><div className="row" style={{ justifyContent: "flex-end" }}>
      {u && u.update && <><button className="btn sm primary" disabled={b} onClick={async () => { setB(true); if (!(await update(x.name))) setB(false); }}>Update</button><a className="btn sm" href={u.page} {...NEW_TAB}>Page</a></>}
      {x.maps.length > 0 && (x.enabled || x.parked) && <button className="btn sm" onClick={() => useMap(x.maps[0])}>Use map</button>}
      {x.builtin ? <span className="small muted">Config → In-game tools</span>
        : <>{!x.parked && <button className="btn sm" onClick={() => act("toggle", x.name)}>{x.enabled ? "Turn off" : "Turn on"}</button>}<button className="btn sm danger" onClick={() => act("delete", x.name)}>Delete</button></>}
    </div></td></tr>);
}

/* ---------------- the page */
export function Mods({ reload }) {
  const [tick, setTick] = useState(0), [err, setErr] = useState("");
  const [data, setData] = useState(() => cacheGet("/api/mods") && cacheGet("/api/mods/updates") ? { d: cacheGet("/api/mods"), mu: cacheGet("/api/mods/updates") } : null);
  const [sort, setSort] = useState(() => L.store.get("es-modsort", "name"));
  const [scan, setScan] = useState(false), [mpres, setMpres] = useState(""), [updBusy, setUpdBusy] = useState(false);
  const [gone, setGone] = useState(() => new Set());   // deleted, waiting for the Undo time to pass
  const mpfile = useRef(null);
  const again = () => setTick(t => t + 1);
  useEffect(() => {
    let live = true;
    Promise.all([cachedApi("/api/mods"), cachedApi("/api/mods/updates").catch(() => ({ mods: {} }))])
      .then(([d, mu]) => { if (live) { setData({ d, mu }); setErr(""); } }, e => { if (live && e.message !== "Please log in") setErr(e.message); });
    return () => { live = false; };
  }, [reload, tick]);
  if (!data) return <PageWait err={err} retry={async () => again()} />;
  const { d, mu } = data, U = mu.mods || {}, ST = d.storage || {}, SETS = (d.sets || []).filter(x => !gone.has("set:" + x.name));
  const roomLeft = ST.free == null ? null : Math.max(0, ST.free - (ST.spare || 0));
  const mods = (sort === "size" ? [...d.mods].sort((a, b) => b.size - a.size) : d.mods).filter(x => !gone.has(x.name));
  const hide = (k, on) => setGone(g => { const n = new Set(g); on ? n.add(k) : n.delete(k); return n; });
  // Delete with Undo: it disappears now and is really deleted a few seconds later.
  const later = (k, msg, path, json) => { hide(k, true); L.undoable(msg, path, json, { onUndo: () => hide(k, false), after: r => { if (r && r.note) L.toast(r.note); again(); } }); };
  const { SESSION } = S();

  const toggleSetting = (path, on, ms = 8000, refresh = true) => async e => {
    const el = e.target;
    try { const r = await L.api(path, { json: { [on]: el.checked } }); L.toast(r.note, ms); if (refresh) again(); } catch (x) { L.toast(x.message, 6000); el.checked = !el.checked; }
  };
  const setAct = async (action, name) => { try { const r = await L.api("/api/mods/sets", { json: { action, name } }); L.toast(r.note, 8000); again(); } catch (e) { L.toast(e.message, 6000); } };
  const saveSet = () => {
    const n = (prompt("Name for this mod set (for example Drift night). It saves the mods that are on now.") || "").trim();
    if (!n) return;
    if (SETS.some(x => x.name.toLowerCase() === n.toLowerCase()) && !confirm("There's already a set called " + n + ". Replace it with the mods that are on now?")) return;
    setAct("save", n);
  };
  const setBtn = (a, n) => {
    if (a === "delete") return later("set:" + n, `Mod set ${n} deleted.`, "/api/mods/sets", { action: "delete", name: n });
    if (a === "save" && !confirm("Replace " + n + " with the mods that are on now?")) return;
    if (a === "apply" && !confirm("Switch to " + n + "? Mods that aren't in this set are turned off (not deleted).")) return;
    setAct(a, n);
  };
  const act = async (action, name) => {
    if (action.includes("delete")) return later(name, `${name} deleted.`, "/api/mods/action", { action, name });
    try { const r = await L.api("/api/mods/action", { json: { action, name } }); L.toast(r.note || "Done"); again(); } catch (e) { L.toast(e.message); }
  };
  const useMap = async map => {
    try { const r = await L.api("/api/config/save", { json: { fields: [{ section: "General", key: "Map", value: map }] } }); L.toast("Map set to " + map + ". " + r.note); } catch (e) { L.toast(e.message); }
  };
  const update = async name => {
    L.toast("Downloading and checking " + name + "…", 60000);
    try { const r = await L.api("/api/mods/update", { json: { name } }); L.toast(r.note, 7000); again(); return true; }
    catch (e) { L.toast(e.data && e.data.blocked ? "The update failed the virus check - the old version stays." : e.message, 9000); return false; }
  };
  const checkUpdates = async () => {
    setUpdBusy(true); L.toast("Asking beamng.com…", 15000);
    try { const r = await L.api("/api/mods/updates", { json: {} }); L.toast(r.note, 6000); again(); } catch (e) { L.toast(e.message, 6000); }
    setUpdBusy(false);
  };
  const rescan = async all => {
    if (all && !confirm("Check every mod again? Big mod folders can take a few minutes.")) return;
    setScan(true); L.toast(all ? "Checking every mod again…" : "Checking new mods…");
    try {
      const r = await L.api("/api/mods/rescan", { json: { all } });
      const bad = r.results.filter(x => x.verdict === "blocked" && !x.skipped).length;
      L.toast(bad ? bad + " mod(s) blocked" : !r.checked ? "Nothing new to check - all " + r.skipped + " mods were checked before"
        : r.checked + " mod(s) checked, all passed" + (r.skipped ? " (" + r.skipped + " already checked)" : ""), 6000);
    } catch (e) { L.toast(e.message); }
    setScan(false); again();
  };
  const importPack = async e => {
    const f = e.target.files[0]; if (!f) return;
    setMpres("Importing and virus-checking…");
    const { CSRF, SERVER } = S();
    const r = await fetch("/api/import?settings=0", { method: "PUT", headers: { "X-ES-CSRF": CSRF, "X-ES-Server": SERVER }, body: f });
    let j = {}; try { j = await r.json(); } catch (x) {}
    e.target.value = "";
    if (!r.ok) return setMpres(j.error || "Import failed");
    if (!j.report.modpack) return setMpres("That was a full server export - it was imported as one.");
    setMpres(""); L.toast(j.note + (j.report.mods_blocked.length ? " " + j.report.mods_blocked.length + " blocked by the virus check." : ""), 8000); again();
  };
  const anyOn = d.mods.some(x => x.enabled);

  return (<>
    <div className="row"><div><h1>Mods</h1><p className="sub">Drop mod .zip files here, or find mods in the BeamNG repository. Every mod is virus-checked before players can download it.</p></div><span className="spacer" /><button className="btn primary" onClick={() => L.modBrowser()}>Browse mods</button></div>
    <Uploads roomLeft={roomLeft} onDone={again} />
    <p className="small muted" style={{ margin: "10px 0 16px" }}>{`🛡 Active checks: ${d.checks.join(" + ")}. ${d.auto_apply ? "The server restarts by itself ~15 s after a change." : "Restart the server after changes."}`}</p>
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="row"><div><div className="small muted">Players download before they can join</div><div style={{ fontSize: 22, fontWeight: 650 }}>{d.download ? L.fmtSize(d.download) : "Nothing - vanilla"}</div>
        {d.maps_size > 0 && !d.light && <div className="small muted">{`${L.fmtSize(d.maps_size)} of that is map mods. Light mode (below) sends only the map being played.`}</div>}
        {d.light && d.all_maps_size > d.maps_size && <div className="small" style={{ color: "var(--good-ink)" }}>{`Light mode saves players ${L.fmtSize(d.all_maps_size - d.maps_size)} of map downloads.`}</div>}</div></div>
      {ST.free != null && <div style={{ marginTop: 12 }}>
        <div className="row small"><span>Mods take <b>{L.fmtSize(ST.mods)}</b> on this drive</span><span className="spacer" />
          <span className={ST.low ? "" : "muted"} style={ST.low ? { color: "var(--warn-ink)", fontWeight: 600 } : undefined}>{`${L.fmtSize(ST.free)} free of ${L.fmtSize(ST.total)}`}</span></div>
        <div className="bar" role="img" aria-label={`Disk space: ${L.fmtSize(ST.total - ST.free)} used of ${L.fmtSize(ST.total)}`}><i style={{ width: Math.min(100, Math.round((ST.total - ST.free) / ST.total * 100)) + "%", ...(ST.low ? { background: "var(--warning)" } : {}) }} /></div>
        {ST.low && <p className="small" style={{ color: "var(--warn-ink)", margin: "6px 0 0" }}>This drive is almost full. Turn off or delete mods you don't play (sort by size below), or move the server to a bigger drive. On a Raspberry Pi, a USB 3 stick or SSD is faster and bigger than the SD card.</p>}
      </div>}
      <label className="toggle" style={{ marginTop: 10 }}><input type="checkbox" defaultChecked={!!d.light} key={"l" + !!d.light} onChange={toggleSetting("/api/mods/light", "on")} /><span><b>Light mode: only send the map being played</b><small>Map mods for other maps wait and come back by themselves when you switch to their map (Config, map vote, rotation or events). Mods that aren't maps are always sent. Players join much faster on servers with several map mods</small></span></label>
      <label className="toggle" style={{ marginTop: 10 }}><input type="checkbox" defaultChecked={!!d.desc_modsize} key={"d" + !!d.desc_modsize} onChange={toggleSetting("/api/mods/desc", "enabled", 7000, false)} /><span><b>Show the download size in the server description</b><small>{`Adds "| Mods: ${d.download ? L.fmtSize(d.download) : "0"}" to the end of the description in the BeamMP server list and keeps it up to date. Takes effect after the server restarts`}</small></span></label>
    </div>
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="row"><div style={{ flex: 1, minWidth: 240 }}><h2 style={{ margin: 0 }}>Mod sets</h2><p className="small muted" style={{ margin: "4px 0 0" }}>Save the mods that are on now under a name, like "Drift night", and switch between sets in one click. Mods outside the set are turned off, not deleted.</p></div>
        <button className="btn sm" onClick={saveSet}>Save as a set…</button></div>
      {SETS.length ? <table style={{ marginTop: 10 }}><tbody>{SETS.map(x => <tr key={x.name}><td><b>{x.name}</b>{x.active && <span className="badge good">on now</span>}
        <div className="small muted">{x.mods.length === 1 ? "1 mod" : `${x.mods.length} mods`}{" · " + L.fmtSize(x.size)}{x.missing.length > 0 && <>{" · "}<span style={{ color: "var(--warn-ink)" }}>{`${x.missing.length} no longer on the server`}</span></>}</div></td>
        <td className="num"><div className="row" style={{ justifyContent: "flex-end" }}>{!x.active && <button className="btn sm primary" onClick={() => setBtn("apply", x.name)}>Switch to this set</button>}
          <button className="btn sm" title="Replace this set with the mods that are on now" onClick={() => setBtn("save", x.name)}>Update</button>
          <button className="btn sm danger" onClick={() => setBtn("delete", x.name)}>Delete</button></div></td></tr>)}</tbody></table>
        : <p className="small muted" style={{ margin: "10px 0 0" }}>{d.mods.some(x => x.enabled) ? "No sets yet. Turn on the mods for one kind of night, then press Save as a set." : "No sets yet. Add some mods first, then save them as a set."}</p>}
    </div>
    <div className="row" style={{ marginBottom: 6 }}><span className="spacer" /><label className="small muted" htmlFor="modsort">Sort</label>
      <select id="modsort" style={{ width: "auto" }} value={sort} onChange={e => { setSort(e.target.value); L.store.set("es-modsort", e.target.value); }}><option value="name">By name</option><option value="size">Biggest first</option></select></div>
    {mods.length ? <div className="card tight"><table><thead><tr><th>Mod</th><th className="num">Size</th><th></th></tr></thead><tbody>
      {mods.map(x => <ModRow key={x.name} x={x} u={U[x.name]} act={act} useMap={useMap} update={update} />)}
    </tbody></table></div>
      : <div className="card"><Empty title="No mods yet" actions={<><button className="btn primary" onClick={() => L.modBrowser()}>Browse mods</button>
          <button className="btn" onClick={() => document.getElementById("mod_files")?.click()}>Upload a .zip</button></>}>
          Drag a mod .zip onto this page, or pick one from the BeamNG repository. Each one is virus-checked before players can download it.</Empty></div>}
    <div className="card" style={{ marginTop: 16 }}><h2>Modpack</h2><p className="small muted">One .zip with every mod that's turned on, plus a list with checksums. Share it with another server owner, move mods to another server, or give it to players with slow internet so they can copy the mods before joining.</p>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <a className="btn sm" href={"/api/modpack?srv=" + encodeURIComponent(S().SERVER)} download {...(anyOn ? {} : { "aria-disabled": "true", style: { pointerEvents: "none", opacity: .5 } })}>Download modpack</a>
        {(SESSION.role === "owner" || !SESSION.role) && <><button className="btn sm" onClick={() => mpfile.current.click()}>Import a modpack…</button><input ref={mpfile} type="file" accept=".zip" hidden onChange={importPack} /></>}
        <button className="btn sm" onClick={() => L.modpackCode()}>Share code…</button><span className="small muted">{mpres}</span></div></div>
    <Plugins key={"p" + reload + ":" + tick} />
    <div className="row" style={{ marginTop: 12, flexWrap: "wrap" }}>
      <button className="btn sm" disabled={scan} title="Checks only mods that are new or changed since their last check" onClick={() => rescan(false)}>Check new mods</button>
      <button className="btn sm ghost" disabled={scan} title="Checks every mod again, e.g. after your antivirus got new virus definitions" onClick={() => rescan(true)}>Check all again</button>
      <button className="btn sm" disabled={updBusy} onClick={checkUpdates}>Check for updates</button>
      <label className="toggle" style={{ margin: "0 0 0 8px" }}><input type="checkbox" defaultChecked={mu.on !== false} onChange={async e => { try { await L.api("/api/mods/updates", { json: { on: e.target.checked } }); L.toast("Saved"); } catch (x) { L.toast(x.message); } }} />
        <span><b>Check every day</b><small>{mu.checked ? `Mods from the BeamNG repository · last check ${L.ago(mu.checked)}` : "Mods from the BeamNG repository"}</small></span></label></div>
    {d.quarantine.length > 0 && <><h2 style={{ marginTop: 26 }}>⛔ Blocked mods (quarantine)</h2><div className="card tight"><table><tbody>{d.quarantine.map(q => <tr key={q.name}>
      <td><b>{q.name}</b><div className="small" style={{ color: "var(--crit-ink)", whiteSpace: "pre-wrap" }}>{q.why}</div></td>
      <td className="num"><button className="btn sm danger" onClick={() => act("qdelete", q.name)}>Delete</button></td></tr>)}</tbody></table></div></>}
  </>);
}
