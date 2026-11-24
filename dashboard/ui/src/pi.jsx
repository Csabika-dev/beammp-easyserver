// "Other computers" card (Servers page): find a Raspberry Pi, a Linux mini PC or NAS, or a Windows PC on the home
// network and install or update EasyServer on it from here. On Windows it can also make a ready-to-go Pi SD card.
import { useEffect, useState } from "react";
import * as L from "./legacy.js";
import { CardWait, Empty, Pill, useLoad } from "./ui.jsx";

export const canSetUpPi = () => ((L.state().SESSION || {}).role || "owner") === "owner";

const STEPS = [
  ["Make the SD card", "In Raspberry Pi Imager pick Raspberry Pi OS (64-bit). Before writing, open the settings (the gear, or Edit settings): set your Wi-Fi, a user name and password, and under Services turn on Enable SSH."],
  ["Start the Raspberry Pi", "Put the card in, plug in the power and wait about 2 minutes. No screen or keyboard needed."],
  ["Install from here", "It shows up below - type the user name and password you set, and press Install."],
];
const KIND = { pi: "Raspberry Pi", windows: "Windows PC", nas: "NAS", pc: "Linux computer" };
const gb = n => Math.round(n / 1e9) + " GB";

function Log({ job }) {
  const ref = (el) => { if (el) el.scrollTop = el.scrollHeight; };
  return <pre ref={ref} className="small mono" style={{ maxHeight: 220, overflow: "auto", whiteSpace: "pre-wrap", margin: "8px 0 0", padding: "8px 10px",
    background: "var(--bg-2, rgba(127,127,127,.08))", borderRadius: 8 }}>{job.lines.join("\n")}</pre>;
}

function JobBox({ job }) {
  const card = job.kind === "card";
  const title = job.state === "failed" ? `Didn't work: ${job.error}`
    : card ? (job.state === "waiting" ? "Waiting for the Raspberry Pi to start…" : job.state === "done" ? `Found the Raspberry Pi at ${job.ip}` : "Making the SD card…")
    : job.kind === "move" ? (job.state === "running" ? `Moving the server to ${job.ip}…` : `The server is now on ${job.ip}`)
    : job.state === "running" ? (job.kind === "install" ? `Installing EasyServer on ${job.ip}…` : `Updating ${job.ip}…`)
    : job.kind === "install" ? `EasyServer is installed on ${job.ip}` : `${job.ip} is up to date`;
  return <div className={"issue " + (job.state === "failed" ? "error" : "info")} style={{ display: "block" }}>
    <b>{title}</b>
    {card && job.state === "running" && <div className="bar" style={{ margin: "8px 0 0" }} role="progressbar" aria-valuenow={job.progress} aria-valuemin={0} aria-valuemax={100} aria-label="Progress"><i style={{ width: (job.progress || 0) + "%" }} /></div>}
    {job.state === "done" && job.password && <div style={{ marginTop: 6 }}>{"Its dashboard password: "}<b className="mono">{job.password}</b>
      <span className="small muted">{" - write it down (on a Windows PC it's shown only now)."}</span></div>}
    {job.state === "done" && job.kind === "install" && <div className="small" style={{ marginTop: 6 }}>{"Next: open its dashboard, log in, and paste your AuthKey under Config so players can find the server."}
      {job.web && <> <a href={job.web} target="_blank" rel="noopener noreferrer">{"Open it"}</a></>}</div>}
    {job.state === "done" && job.kind === "move" && job.web && <div className="small" style={{ marginTop: 6 }}>
      <a href={job.web} target="_blank" rel="noopener noreferrer">{"Open its dashboard"}</a></div>}
    <Log job={job} /></div>;
}

function Setup({ f, busy, blocked, act }) {
  const win = f.kind === "windows";
  const [user, setUser] = useState(() => { try { return localStorage.getItem("es_pi_user" + (win ? "_win" : "")) || ""; } catch (e) { return ""; } });
  const [pw, setPw] = useState(""), [name, setName] = useState(f.kind === "pi" ? "Raspberry Pi BeamMP Server" : f.name ? `${f.name} BeamMP Server` : "BeamMP Server");
  const go = () => {
    try { localStorage.setItem("es_pi_user" + (win ? "_win" : ""), user.trim()); } catch (e) {}
    act({ action: "install", ip: f.ip, user: user.trim(), password: pw, name }).then(ok => ok && setPw(""));
  };
  if (!f.ssh) return <p className="small" style={{ margin: "6px 0 0" }}>{"SSH is off on this Raspberry Pi, so it can't be set up from here. In Raspberry Pi Imager's settings turn on Enable SSH (under Services), write the card again and start the Pi with it."}</p>;
  return <div className="grid g2" style={{ marginTop: 10 }}>
    <label className="f"><span>{"User name"}</span><input type="text" value={user} onChange={e => setUser(e.target.value)} placeholder={win ? "" : "pi"} autoCapitalize="none" autoComplete="off" />
      <small>{win ? "That PC's Windows user (an administrator) - its folder name in C:\\Users" : f.kind === "pi" ? "The one you set in Raspberry Pi Imager" : "A user that may use sudo, or root"}</small></label>
    <label className="f"><span>{"Password"}</span><input type="password" value={pw} onChange={e => setPw(e.target.value)} autoComplete="off" onKeyDown={e => e.key === "Enter" && go()} />
      <small>{win ? "Its Windows password - used for the install, not saved" : "Used once to log in, not saved"}</small></label>
    <label className="f"><span>{"Server name"}</span><input type="text" value={name} maxLength={60} onChange={e => setName(e.target.value)} /></label>
    <div className="row" style={{ alignItems: "end" }}><button className="btn primary" disabled={busy || blocked || !user.trim() || !pw} onClick={go}>{busy ? "Connecting…" : "Install EasyServer"}</button></div>
    <p className="small muted" style={{ gridColumn: "1 / -1", margin: 0 }}>{"This dashboard leaves its own key there, so updates later are one click."}</p>
  </div>;
}

function Known({ p, busy, act, running }) {
  const [shown, setShown] = useState("");
  const [pw, setPw] = useState("");
  const win = p.os === "windows";
  const needPw = (!p.sudo && !p.root) || (win && !p.version);
  const show = async () => { try { const r = await L.api("/api/pi", { json: { action: "password", ip: p.ip } }); setShown(r.password); } catch (e) { L.toast(e.message, 9000); } };
  const what = p.model || (p.omv ? "OpenMediaVault NAS" : KIND[p.kind] || "Computer");
  return <div className="card tight" style={{ marginBottom: 10 }}>
    <div className="row" style={{ padding: "12px 14px", gap: 8, flexWrap: "wrap" }}>
      <div><b>{p.host || what}</b><div className="small muted">{`${what} · ${p.ip}${p.version ? " · EasyServer " + p.version : ""}${p.updated ? " · updated " + L.ago(p.updated) : ""}`}</div></div>
      <span className="spacer" />
      <Pill on={p.online}>{p.online ? "Dashboard running" : "Not answering"}</Pill>
      {p.online && <a className="btn sm" href={p.web || `https://${p.ip}:30815/`} target="_blank" rel="noopener noreferrer">{"Open its dashboard"}</a>}
      {!p.problem && needPw && <input type="password" placeholder={win ? "Windows password" : "Its password"} value={pw} onChange={e => setPw(e.target.value)} style={{ width: 150 }} aria-label="Password of that computer" />}
      {!p.problem && <button className="btn sm primary" disabled={busy || running || (needPw && !pw)}
        onClick={() => act({ action: p.version ? "update" : "install", ip: p.ip, password: pw || undefined }).then(ok => ok && setPw(""))}>{p.version ? "Update" : "Install EasyServer"}</button>}
      {!win && p.version && (p.sudo || p.root) && <button className="btn sm ghost" onClick={show}>{"Show its password"}</button>}
      <button className="btn sm ghost" onClick={() => { if (confirm(`Forget ${p.ip}? EasyServer stays on that computer; you can find and add it again.`)) act({ action: "forget", ip: p.ip }); }}>{"Forget"}</button>
    </div>
    {p.problem && <div className="small" style={{ padding: "0 14px 12px", color: "var(--warning)" }}>{p.problem}</div>}
    {shown && <div className="small" style={{ padding: "0 14px 12px" }}>{"Dashboard password: "}<b className="mono">{shown}</b>{" "}
      <button className="btn sm ghost" onClick={async () => L.toast(await L.copyText(shown) ? "Copied" : "Select it and press Ctrl+C")}>{"Copy"}</button></div>}
  </div>;
}

function CardMaker({ d, busy, act }) {
  const [f, setF] = useState(() => ({ ssid: d.wifi || "", wifi_password: "", country: d.country || "", user: "beammp", password: "", name: "Raspberry Pi BeamMP Server", disk: null, erase_ok: false }));
  const [disks, setDisks] = useState(null);
  const set = k => e => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const look = async () => {
    setDisks(null);
    try { const r = await L.api("/api/pi", { json: { action: "disks" } }); setDisks(r.disks); setF(x => ({ ...x, disk: r.disks.length === 1 ? r.disks[0].n : (r.disks.some(y => y.n === x.disk) ? x.disk : null) })); }
    catch (e) { L.toast(e.message); setDisks([]); }
  };
  useEffect(() => { look(); }, []);
  const ready = f.user && f.password.length >= 8 && f.disk !== null && f.erase_ok && (!f.ssid || f.country.length === 2);
  const go = () => {
    const disk = disks.find(x => x.n === f.disk);
    if (!confirm(`Erase everything on ${disk.model} (${gb(disk.size)}${disk.letters.length ? ", " + disk.letters.join(" ") : ""}) and put Raspberry Pi OS on it?`)) return;
    act({ action: "card", ...f, country: f.country.toUpperCase() }).then(ok => ok && setF(x => ({ ...x, password: "", wifi_password: "", erase_ok: false })));
  };
  return <div style={{ marginTop: 10 }}>
    <p className="small" style={{ marginTop: 0 }}>{"Put a microSD card (8 GB or more) in this computer's card reader. This downloads Raspberry Pi OS (64-bit) and writes it to the card with your Wi-Fi and a user for the Pi. Start the Pi with it and it shows up here by itself, and EasyServer gets installed - nothing else to do."}</p>
    <div className="grid g2">
      <label className="f"><span>{"Wi-Fi name"}</span><input type="text" value={f.ssid} maxLength={32} onChange={set("ssid")} autoComplete="off" /><small>{"Leave it empty when the Pi is plugged into the router with a cable"}</small></label>
      <label className="f"><span>{"Wi-Fi password"}</span><input type="password" value={f.wifi_password} maxLength={63} onChange={set("wifi_password")} autoComplete="off" disabled={!f.ssid} />
        <small>{"Only the Wi-Fi key made from it goes on the card, not the password itself"}</small></label>
      <label className="f"><span>{"Country"}</span><input type="text" value={f.country} maxLength={2} onChange={set("country")} placeholder="HU" style={{ width: 80 }} autoComplete="off" /><small>{"Two letters - the Wi-Fi rules depend on it"}</small></label>
      <label className="f"><span>{"Server name"}</span><input type="text" value={f.name} maxLength={60} onChange={set("name")} /></label>
      <label className="f"><span>{"User name for the Pi"}</span><input type="text" value={f.user} maxLength={32} onChange={e => setF({ ...f, user: e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "") })} autoCapitalize="none" autoComplete="off" /></label>
      <label className="f"><span>{"Password for the Pi"}</span><input type="password" value={f.password} maxLength={128} onChange={set("password")} autoComplete="new-password" />
        <small>{"At least 8 characters. It goes on the card only as a one-way hash."}</small></label>
    </div>
    <div className="row" style={{ gap: 8, marginTop: 6, flexWrap: "wrap" }}>
      <label className="f" style={{ minWidth: 260, flex: 1 }}><span>{"SD card"}</span>
        <select value={f.disk === null ? "" : f.disk} onChange={e => setF({ ...f, disk: e.target.value === "" ? null : +e.target.value })} disabled={!disks || !disks.length}>
          <option value="">{disks === null ? "Looking…" : disks.length ? "Pick the card" : "No card found - put one in"}</option>
          {(disks || []).map(x => <option key={x.n} value={x.n}>{`${x.letters.join(" ") || "-"} · ${x.model} · ${gb(x.size)}`}</option>)}
        </select></label>
      <button className="btn sm" onClick={look} style={{ alignSelf: "end" }}>{"Look for cards"}</button>
    </div>
    <label className="toggle" style={{ marginTop: 8 }}><input type="checkbox" checked={f.erase_ok} onChange={set("erase_ok")} />
      <span><b>{"Everything on this card may be erased"}</b><small>{"Only removable cards and sticks are listed - never this computer's own disks."}</small></span></label>
    <div className="row" style={{ marginTop: 10, gap: 10, flexWrap: "wrap" }}>
      <button className="btn primary" disabled={busy || !ready} onClick={go}>{"Make the card"}</button>
      <span className="small muted">{"Windows asks for permission on this computer's screen - press Yes. Wi-Fi set to WPA3 only won't work; WPA2 or WPA2/WPA3 does."}</span>
    </div>
  </div>;
}

function OtherHelp() {
  return <details className="small" style={{ marginTop: 10 }}><summary>{"A mini PC, NAS or Windows PC? Get it ready"}</summary>
    <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
      <li style={{ marginBottom: 6 }}><b>{"Ubuntu or Debian (64-bit):"}</b> {"turn on SSH on it with"} <span className="mono">sudo apt install openssh-server</span>{" - then it shows up here."}</li>
      <li style={{ marginBottom: 6 }}><b>{"OpenMediaVault:"}</b> {"SSH is on by default (Services → SSH). Log in here with root or a user in the ssh group."}</li>
      <li style={{ marginBottom: 6 }}><b>{"Windows 10 or 11:"}</b> {"on that PC open Settings → System → Optional features → View features, add OpenSSH Server, then in PowerShell as administrator run"} <span className="mono">Start-Service sshd; Set-Service sshd -StartupType Automatic</span>{". Log in here with an administrator account of that PC."}</li>
      <li><b>{"TrueNAS, Unraid, Synology:"}</b> {"these don't allow installing programs, so EasyServer can't go there."}</li>
    </ul></details>;
}

export function RaspberryPi() {
  const [d, again, , err] = useLoad("/api/pi");
  const [busy, setBusy] = useState(false);
  const [manual, setManual] = useState("");
  const [making, setMaking] = useState(false);
  const [open, setOpen] = useState(false);
  const running = !!(d && ((d.job && d.job.state === "running") || d.scanning));
  const watching = !!(d && d.job && d.job.state === "waiting");
  useEffect(() => { if (!running && !watching) return; const t = setInterval(again, running ? 2000 : 8000); return () => clearInterval(t); }, [running, watching]);
  useEffect(() => { if (d && !d.scan && !d.scanning) scan(); }, [!!d]);
  if (!d) return <CardWait err={err} retry={again} />;
  async function scan() { try { await L.api("/api/pi", { json: { action: "scan" } }); } catch (e) { L.toast(e.message); } again(); }
  const act = async body => {
    setBusy(true);
    try { const r = await L.api("/api/pi", { json: body }); if (r.note) L.toast(r.note, 6000); await again(); if (body.action === "card") setMaking(false); return true; }
    catch (e) { L.toast(e.message, 9000); return false; }
    finally { setBusy(false); }
  };
  const known = new Set(d.pis.map(p => p.ip));
  const found = ((d.scan && d.scan.found) || []).filter(f => !known.has(f.ip));
  const job = d.job;
  if (!open && !d.pis.length && !found.length && !job && !d.scanning && d.scan) return (<div className="card" style={{ marginTop: 16 }}>
    <div className="row" style={{ gap: 8 }}><h2 style={{ margin: 0 }}>{"Other computers at home"}</h2><span className="spacer" />
      <button className="btn sm" onClick={() => setOpen(true)}>{"Show"}</button></div>
    <p className="small muted" style={{ margin: "6px 0 0" }}>{"Nothing found on your network. Want a server on a Raspberry Pi, a mini PC, a NAS or another Windows PC? Press Show to set one up."}</p>
  </div>);
  return (<div className="card" style={{ marginTop: 16 }}>
    <div className="row"><h2 style={{ margin: 0 }}>{"Other computers at home"}</h2><span className="spacer" />
      <button className="btn sm" disabled={d.scanning} onClick={scan}>{d.scanning ? "Looking…" : "Look again"}</button></div>
    <p className="small muted">{"Run a server on another computer on your network - a Raspberry Pi 4 or 5, a mini PC or NAS with Ubuntu, Debian or OpenMediaVault, or a Windows PC. This dashboard finds it, installs EasyServer on it and keeps it up to date - no commands on it."}</p>
    {!d.ssh && <div className="issue warning"><span className="ic">⚠</span><span>{"This computer has no SSH client. On Windows: Settings → System → Optional features → add OpenSSH Client."}</span></div>}
    {job && job.kind !== "move" && <JobBox job={job} />}
    {d.pis.map(p => <Known key={p.ip} p={p} busy={busy} act={act} running={running} />)}
    {found.map(f => <div key={f.ip} className="card tight" style={{ marginBottom: 10, padding: "12px 14px" }}>
      <div className="row"><b>{`${KIND[f.kind] || "Computer"} found at ${f.ip}`}{f.name ? ` (${f.name})` : ""}</b><span className="spacer" />
        {f.easyserver && <Pill on>{"EasyServer already on it"}</Pill>}</div>
      <Setup f={f} busy={busy} blocked={running} act={act} /></div>)}
    {!d.pis.length && !found.length && (d.scanning ? <p className="small muted">{"Looking through your network…"}</p>
      : <Empty title={d.scan && d.scan.error ? d.scan.error : "Nothing found on your network yet"}>
        {d.card ? <p className="small" style={{ margin: "6px 0 0" }}>{"New Raspberry Pi? Make its SD card here (below) - it then sets itself up."}</p>
          : <ol className="small" style={{ textAlign: "left", margin: "6px auto 0", maxWidth: 560 }}>{STEPS.map(([t, x]) => <li key={t} style={{ marginBottom: 6 }}><b>{t}:</b> {x}</li>)}</ol>}
      </Empty>)}
    {d.card && <div className="card tight" style={{ marginTop: 10, padding: "12px 14px" }}>
      <div className="row"><b>{"New Raspberry Pi: make its SD card here"}</b><span className="spacer" />
        {!making && <button className="btn sm" disabled={running || watching} onClick={() => setMaking(true)}>{"Make an SD card"}</button>}
        {making && <button className="btn sm ghost" onClick={() => setMaking(false)}>{"Cancel"}</button>}</div>
      {making && <CardMaker d={d} busy={busy || running} act={act} />}
    </div>}
    <OtherHelp />
    <details className="small" style={{ marginTop: 10 }}><summary>{"It's there but not found? Enter its address"}</summary>
      <div className="row" style={{ gap: 8, marginTop: 8 }}>
        <input type="text" value={manual} onChange={e => setManual(e.target.value.trim())} placeholder="192.168.0.23" style={{ width: 170 }} aria-label="Address of that computer" />
        <span className="muted">{"Your router's page lists the devices at home and their addresses."}</span></div>
      {/^\d{1,3}(\.\d{1,3}){3}$/.test(manual) && !known.has(manual) && <Setup f={{ ip: manual, ssh: true, kind: "pc" }} busy={busy} blocked={running} act={act} />}
    </details>
  </div>);
}


/* ---------------- all computers on one page: this one and every paired computer with EasyServer */
const WHY = {
  off: "Not answering - is it switched on?",
  nokey: "This dashboard can't log in to it with its key, so it can't show or control its server.",
  old: "Its EasyServer is too old to show here - press Update for it under Other computers at home.",
};

function ServerLine({ s, ip, busy, act }) {
  const on = s.state === "running";
  return <div className="row small" style={{ gap: 8, flexWrap: "wrap", marginTop: 8 }}>
    <Pill on={on}>{on ? "Running" : s.state === "stopped" ? "Stopped" : s.state}</Pill>
    <span><b>{s.name}</b>{on ? ` · ${s.players}/${s.max} players` : ""}{on && s.map ? ` · ${s.map}` : ""}</span>
    {act && s.id === "main" && <><span className="spacer" />
      {on ? <><button className="btn sm" disabled={busy} onClick={() => act({ action: "restart", ip })}>{"Restart"}</button>
        <button className="btn sm ghost" disabled={busy} onClick={() => act({ action: "stop", ip })}>{"Stop"}</button></>
        : <button className="btn sm primary" disabled={busy} onClick={() => act({ action: "start", ip })}>{"Start"}</button>}</>}
  </div>;
}

export function AllComputers() {
  const [d, again] = useLoad("/api/machines");
  const [busy, setBusy] = useState(false);
  const moving = !!(d && d.job && d.job.kind === "move" && d.job.state === "running");
  useEffect(() => { const t = setInterval(again, moving ? 3000 : 20000); return () => clearInterval(t); }, [moving]);
  const ms = d ? d.machines.filter(m => m.version) : [];
  if (!ms.length) return null;
  const act = async body => {
    setBusy(true);
    try { const r = await L.api("/api/machines", { json: body }); if (r.note) L.toast(r.note, 6000); await again(); }
    catch (e) { L.toast(e.message, 9000); }
    finally { setBusy(false); }
  };
  const here = d.here.servers.find(s => s.id === (L.state().SERVER || "main")) || d.here.servers[0] || { name: "" };
  const move = m => {
    if (!confirm([`Move "${here.name}" to ${m.host || m.ip}?`, "",
      "Its settings, mods, bans, stats, championships and lap times are copied there and replace the server on that computer (that computer keeps a backup of how it was). Then the server on this computer stops."].join("\n"))) return;
    act({ action: "move", ip: m.ip, stop_here: true });
  };
  return (<div className="card" style={{ marginTop: 16 }}>
    <div className="row"><h2 style={{ margin: 0 }}>{"All your computers"}</h2><span className="spacer" />
      <button className="btn sm" onClick={again}>{"Refresh"}</button></div>
    <p className="small muted">{"The servers on this computer and on the ones set up below. Start, stop or restart them from here, or move this server to another computer in one go."}</p>
    {d.job && d.job.kind === "move" && <JobBox job={d.job} />}
    <div className="card tight" style={{ marginBottom: 10, padding: "12px 14px" }}>
      <b>{`This computer (${d.here.host})`}</b><div className="small muted">{`${d.here.ip} · EasyServer ${d.here.version}`}</div>
      {d.here.servers.map(s => <ServerLine key={s.id} s={s} />)}
    </div>
    {ms.map(m => { const r = m.remote || {}; return <div key={m.ip} className="card tight" style={{ marginBottom: 10, padding: "12px 14px" }}>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <div><b>{m.host || m.ip}</b><div className="small muted">{`${m.ip} · EasyServer ${r.version || m.version}`}</div></div><span className="spacer" />
        {m.online && <a className="btn sm" href={m.web || `https://${m.ip}:30815/`} target="_blank" rel="noopener noreferrer">{"Open its dashboard"}</a>}
        {r.servers && <button className="btn sm" disabled={busy || moving} onClick={() => move(m)}>{"Move this server here"}</button>}</div>
      {r.error ? <div className="small" style={{ marginTop: 6, color: "var(--warning)" }}>{r.detail || WHY[r.error] || ""}</div>
        : <>{r.stale && <div className="small" style={{ marginTop: 6, color: "var(--warning)" }}>{"Its dashboard hasn't reported for a while - it may be stuck. Open it to check."}</div>}
          {(r.servers || []).map(s => <ServerLine key={s.id} s={s} ip={m.ip} busy={busy} act={act} />)}</>}
    </div>; })}
  </div>);
}
