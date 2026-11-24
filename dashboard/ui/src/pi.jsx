// Raspberry Pi card (Servers page): find a Raspberry Pi on the same Wi-Fi and install or update EasyServer on
// it from here. The Pi needs only the SD card from Raspberry Pi Imager with Wi-Fi, a user and "Enable SSH".
import { useEffect, useState } from "react";
import * as L from "./legacy.js";
import { CardWait, Empty, Pill, useLoad } from "./ui.jsx";

export const canSetUpPi = () => ((L.state().SESSION || {}).role || "owner") === "owner";

const STEPS = [
  ["Make the SD card", "In Raspberry Pi Imager pick Raspberry Pi OS (64-bit). Before writing, open the settings (the gear, or Edit settings): set your Wi-Fi, a user name and password, and under Services turn on Enable SSH."],
  ["Start the Raspberry Pi", "Put the card in, plug in the power and wait about 2 minutes. No screen or keyboard needed."],
  ["Install from here", "It shows up below - type the user name and password you set, and press Install."],
];

function Log({ job }) {
  const ref = (el) => { if (el) el.scrollTop = el.scrollHeight; };
  return <pre ref={ref} className="small mono" style={{ maxHeight: 220, overflow: "auto", whiteSpace: "pre-wrap", margin: "8px 0 0", padding: "8px 10px",
    background: "var(--bg-2, rgba(127,127,127,.08))", borderRadius: 8 }}>{job.lines.join("\n")}</pre>;
}

function Setup({ f, busy, act }) {
  const [user, setUser] = useState(() => { try { return localStorage.getItem("es_pi_user") || ""; } catch (e) { return ""; } });
  const [pw, setPw] = useState(""), [name, setName] = useState("Raspberry Pi BeamMP Server");
  const go = () => {
    try { localStorage.setItem("es_pi_user", user.trim()); } catch (e) {}
    act({ action: "install", ip: f.ip, user: user.trim(), password: pw, name }).then(ok => ok && setPw(""));
  };
  if (!f.ssh) return <p className="small" style={{ margin: "6px 0 0" }}>{"SSH is off on this Raspberry Pi, so it can't be set up from here. In Raspberry Pi Imager's settings turn on Enable SSH (under Services), write the card again and start the Pi with it."}</p>;
  return <div className="grid g2" style={{ marginTop: 10 }}>
    <label className="f"><span>{"User name"}</span><input type="text" value={user} onChange={e => setUser(e.target.value)} placeholder="pi" autoCapitalize="none" autoComplete="off" /><small>{"The one you set in Raspberry Pi Imager"}</small></label>
    <label className="f"><span>{"Password"}</span><input type="password" value={pw} onChange={e => setPw(e.target.value)} autoComplete="off" onKeyDown={e => e.key === "Enter" && go()} /><small>{"Used once to log in, not saved"}</small></label>
    <label className="f"><span>{"Server name"}</span><input type="text" value={name} maxLength={60} onChange={e => setName(e.target.value)} /></label>
    <div className="row" style={{ alignItems: "end" }}><button className="btn primary" disabled={busy || !user.trim() || !pw} onClick={go}>{busy ? "Connecting…" : "Install EasyServer"}</button></div>
    <p className="small muted" style={{ gridColumn: "1 / -1", margin: 0 }}>{"This computer leaves its own key on the Pi, so updates later are one click."}</p>
  </div>;
}

function Known({ p, busy, act, running }) {
  const [shown, setShown] = useState("");
  const [pw, setPw] = useState("");
  const show = async () => { try { const r = await L.api("/api/pi", { json: { action: "password", ip: p.ip } }); setShown(r.password); } catch (e) { L.toast(e.message, 7000); } };
  return <div className="card tight" style={{ marginBottom: 10 }}>
    <div className="row" style={{ padding: "12px 14px", gap: 8, flexWrap: "wrap" }}>
      <div><b>{p.host || "Raspberry Pi"}</b><div className="small muted">{`${p.ip}${p.version ? " · EasyServer " + p.version : ""}${p.updated ? " · updated " + L.ago(p.updated) : ""}`}</div></div>
      <span className="spacer" />
      <Pill on={p.online}>{p.online ? "Dashboard running" : "Not answering"}</Pill>
      {p.online && <a className="btn sm" href={p.web || `https://${p.ip}:30815/`} target="_blank" rel="noopener noreferrer">{"Open its dashboard"}</a>}
      {!p.sudo && <input type="password" placeholder="Pi password" value={pw} onChange={e => setPw(e.target.value)} style={{ width: 140 }} aria-label="Raspberry Pi password" />}
      <button className="btn sm primary" disabled={busy || running || (!p.sudo && !pw)} onClick={() => act({ action: "update", ip: p.ip, password: pw || undefined }).then(ok => ok && setPw(""))}>{"Update"}</button>
      {p.sudo && p.version && <button className="btn sm ghost" onClick={show}>{"Show its password"}</button>}
      <button className="btn sm ghost" onClick={() => { if (confirm(`Forget ${p.ip}? EasyServer stays on the Raspberry Pi; you can find and add it again.`)) act({ action: "forget", ip: p.ip }); }}>{"Forget"}</button>
    </div>
    {shown && <div className="small" style={{ padding: "0 14px 12px" }}>{"Dashboard password: "}<b className="mono">{shown}</b>{" "}
      <button className="btn sm ghost" onClick={async () => L.toast(await L.copyText(shown) ? "Copied" : "Select it and press Ctrl+C")}>{"Copy"}</button></div>}
  </div>;
}

export function RaspberryPi() {
  const [d, again, , err] = useLoad("/api/pi");
  const [busy, setBusy] = useState(false);
  const [manual, setManual] = useState("");
  const running = !!(d && ((d.job && d.job.state === "running") || d.scanning));
  useEffect(() => { if (!running) return; const t = setInterval(again, 2000); return () => clearInterval(t); }, [running]);
  useEffect(() => { if (d && !d.scan && !d.scanning) scan(); }, [!!d]);
  if (!d) return <CardWait err={err} retry={again} />;
  async function scan() { try { await L.api("/api/pi", { json: { action: "scan" } }); } catch (e) { L.toast(e.message); } again(); }
  const act = async body => {
    setBusy(true);
    try { const r = await L.api("/api/pi", { json: body }); if (r.note) L.toast(r.note, 6000); await again(); return true; }
    catch (e) { L.toast(e.message, 9000); return false; }
    finally { setBusy(false); }
  };
  const known = new Set(d.pis.map(p => p.ip));
  const found = ((d.scan && d.scan.found) || []).filter(f => !known.has(f.ip));
  const job = d.job;
  return (<div className="card" style={{ marginTop: 16 }}>
    <div className="row"><h2 style={{ margin: 0 }}>{"Raspberry Pi"}</h2><span className="spacer" />
      <button className="btn sm" disabled={d.scanning} onClick={scan}>{d.scanning ? "Looking…" : "Look again"}</button></div>
    <p className="small muted">{"Run a server on a Raspberry Pi 4 or 5 on the same Wi-Fi: this dashboard finds it, installs EasyServer on it and updates it - no screen, keyboard or commands on the Pi."}</p>
    {!d.ssh && <div className="issue warning"><span className="ic">⚠</span><span>{"This computer has no SSH client. On Windows: Settings → System → Optional features → add OpenSSH Client."}</span></div>}
    {job && <div className={"issue " + (job.state === "failed" ? "error" : "info")} style={{ display: "block" }}>
      <b>{job.state === "running" ? (job.kind === "install" ? `Installing EasyServer on ${job.ip}…` : `Updating ${job.ip}…`)
        : job.state === "done" ? (job.kind === "install" ? `EasyServer is installed on ${job.ip}` : `${job.ip} is up to date`) : `Didn't work: ${job.error}`}</b>
      {job.state === "done" && job.password && <div style={{ marginTop: 6 }}>{"Its dashboard password: "}<b className="mono">{job.password}</b>
        <span className="small muted">{" - keep it; Show its password brings it back."}</span></div>}
      {job.state === "done" && job.kind === "install" && <div className="small" style={{ marginTop: 6 }}>{"Next: open its dashboard, log in, and paste your AuthKey under Config so players can find the server."}
        {job.web && <> <a href={job.web} target="_blank" rel="noopener noreferrer">{"Open it"}</a></>}</div>}
      <Log job={job} /></div>}
    {d.pis.map(p => <Known key={p.ip} p={p} busy={busy} act={act} running={running} />)}
    {found.map(f => <div key={f.ip} className="card tight" style={{ marginBottom: 10, padding: "12px 14px" }}>
      <div className="row"><b>{f.pi ? `Raspberry Pi found at ${f.ip}` : `Device at ${f.ip}`}</b><span className="spacer" />
        {f.easyserver && <Pill on>{"EasyServer already on it"}</Pill>}</div>
      <Setup f={f} busy={busy || running} act={act} /></div>)}
    {!d.pis.length && !found.length && (d.scanning ? <p className="small muted">{"Looking through your network…"}</p>
      : <Empty title={d.scan && d.scan.error ? d.scan.error : "No Raspberry Pi found on your network"}>
        <ol className="small" style={{ textAlign: "left", margin: "6px auto 0", maxWidth: 560 }}>{STEPS.map(([t, x]) => <li key={t} style={{ marginBottom: 6 }}><b>{t}:</b> {x}</li>)}</ol>
      </Empty>)}
    <details className="small" style={{ marginTop: 10 }}><summary>{"It's there but not found? Enter its address"}</summary>
      <div className="row" style={{ gap: 8, marginTop: 8 }}>
        <input type="text" value={manual} onChange={e => setManual(e.target.value.trim())} placeholder="192.168.0.23" style={{ width: 170 }} aria-label="Raspberry Pi address" />
        <span className="muted">{"Your router's page lists it, often as raspberrypi."}</span></div>
      {/^\d{1,3}(\.\d{1,3}){3}$/.test(manual) && !known.has(manual) && <Setup f={{ ip: manual, ssh: true }} busy={busy || running} act={act} />}
    </details>
  </div>);
}
