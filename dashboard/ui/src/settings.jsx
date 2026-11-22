// Settings page: notifications, security, internet access, hiding the IP, guard, password, two-step login, import/export.
// The bigger cards live in settings-cards.jsx and power.jsx.
import { useEffect, useRef, useState } from "react";
import * as L from "./legacy.js";
import { Ip } from "./pages.jsx";
import { $, S, val, chk, Toggle, useLoad, SkelPage } from "./ui.jsx";
import { Supporter, Phone, DiscordBot, Integrations, StatusPage, Devices, Users, Backups, KeyQR } from "./settings-cards.jsx";
import { Power } from "./power.jsx";

const NEW_TAB = { target: "_blank", rel: "noopener noreferrer" };
const NOTIFY = [["crash", "Crashes", "The server crashed or keeps crashing"], ["stopped", "Unexpected stops", "The server stopped without you stopping it"],
  ["update", "Updates", "New BeamMP or EasyServer versions"], ["mod_blocked", "Blocked mods", "A mod failed the virus check"],
  ["player_join", "Player joins", "Every time someone joins (can be a lot)"], ["player_denied", "Refused players", "Someone not on the allow-list tried to join"],
  ["moderation", "Moderation", "Bans, kicks and mutes made in game by your admins"], ["report", "Player reports", "A player used /report in the game - with the chat just before it"],
  ["network", "Address changes", "This computer's home address or your public IP changed"], ["restart", "Scheduled restarts", "A scheduled restart or update ran"],
  ["rotation", "Map rotation", "The map was changed by the rotation"], ["resources", "Computer overloaded", "Out of memory, processor maxed out, or upload almost used up"],
  ["backup", "Backup problems", "A nightly backup failed"], ["mod_update", "Mod updates", "A newer version of a repository mod is out"],
  ["sleep", "Sleep and wake-up", "The server computer went to sleep or woke up"]];

/* ---------------- pop-ups on this device */
function PopupButton() {
  const note = () => !window.Notification ? (window.isSecureContext ? "This browser has no pop-ups" : "Pop-ups need HTTPS (turn it on below) or http://localhost")
    : Notification.permission === "granted" ? "On for this browser" : Notification.permission === "denied" ? "Blocked - allow notifications for this site in the browser settings" : "";
  const [txt, setTxt] = useState(note);
  const ask = async () => {
    if (window.Notification) { await Notification.requestPermission(); if (Notification.permission === "granted") new Notification("BeamMP dashboard", { body: "Security alerts will pop up here while the dashboard is open." }); }
    setTxt(note());
  };
  return <div className="row" style={{ marginTop: 8 }}><button className="btn sm" onClick={ask}>Show pop-ups on this device</button><span className="small muted">{txt}</span></div>;
}

/* ---------------- two-step login (owner) */
function TwoStep({ s, reloadPage }) {
  const [setup, setSetup] = useState(null);
  const begin = async () => { try { setSetup(await L.api("/api/2fa/begin", { method: "POST" })); } catch (e) { L.toast(e.message); } };
  const confirmCode = async () => { try { await L.api("/api/2fa/confirm", { json: { code: val("tfacode") } }); L.toast("Two-step login is on"); reloadPage(); } catch (e) { L.toast(e.message); } };
  const off = async () => { const p = prompt("Enter your password to turn off two-step login"); if (!p) return; try { await L.api("/api/2fa/disable", { json: { password: p } }); L.toast("Two-step login turned off"); reloadPage(); } catch (e) { L.toast(e.message); } };
  return (<div className="card" style={{ marginTop: 16 }}><h2>Two-step login</h2>
    <p className="small muted">Ask for a 6-digit code from an app like Google Authenticator, Microsoft Authenticator or Aegis on every login. Required for access from the internet.</p>
    <div>{s.totp ? <><span className="pill good"><span className="dot" />On</span> <button className="btn sm danger" style={{ marginLeft: 8 }} onClick={off}>Turn off</button></>
      : setup ? <><p className="small">Scan this with your authenticator app (Google Authenticator, Microsoft Authenticator, Aegis...):</p><KeyQR r={setup} px={220} label="QR code for the two-step login key" />
        <p className="small muted">Can't scan? In the app choose <b>"Enter a setup key"</b>, account name <b>BeamMP</b>, and type this key:</p>
        <div className="secret">{setup.secret}</div><p className="small muted">On a phone you can also <a href={setup.uri}>tap here</a> to add it directly. Clicking "Set up" again makes a new key - only the one shown here works.</p>
        <label className="f"><span>Enter the 6-digit code the app shows</span><input type="text" id="tfacode" inputMode="numeric" maxLength={7} style={{ maxWidth: 180 }} /></label><button className="btn primary" onClick={confirmCode}>Turn on</button></>
        : <button className="btn" onClick={begin}>Set up two-step login</button>}</div>
  </div>);
}

/* ---------------- BeamMP-only guard */
function Guard({ on }) {
  const [g, again, v, err] = useLoad("/api/guard");
  if (err && !g) return <div className="small">{err}</div>;
  if (!g) return <div className="small" />;
  if (g.mac) return <div className="small"><p className="muted">Not available on a Mac yet: players reach the server through the Mac, so they all look like the same address.</p></div>;
  const un = async body => { try { const r = await L.api("/api/guard", { json: body }); L.toast(r.note, 6000); } catch (e) { L.toast(e.message); } again(); };
  const warn = g.on && !g.relay && !g.enforced;
  return (<div className="small" key={v}>{g.relay ? <p className="muted">Not needed while "Hide my IP" is on.</p> : !g.on ? null : <>
    <p className="muted" style={{ margin: "6px 0 0" }}>{"Watching. "}{g.count ? <><b>{g.count}</b> blocked right now</> : "Nobody blocked right now"}{` · ${g.total} blocked so far · ${g.players_known} addresses known as players.`}</p>
    {warn && <div className="banner warn" style={{ margin: "8px 0 0" }}><span className="small">{g.error ? g.error : g.platform === "windows" ? "The firewall task isn't running yet, so nothing is actually blocked. Run Update-BeamMP-Server.bat once (it sets it up)." : "The server helper didn't answer."}</span></div>}
    {g.blocked.length > 0 && <><div style={{ marginTop: 6 }}>{g.blocked.map(x => <div key={x.ip} className="check"><span className="mark bad">✕</span><div><b><Ip>{x.ip}</Ip></b> <span className="muted">{`until ${L.fmtTime(x.until)} - ${x.why}`}</span> <button className="btn sm" onClick={() => un({ unblock: x.ip })}>Unblock</button></div></div>)}</div>
      <button className="btn sm" style={{ marginTop: 6 }} onClick={() => un({ unblock_all: true })}>Unblock everyone</button></>}
    <div className="row" style={{ marginTop: 8 }}><input type="text" id="guard_ip" placeholder="A friend can't join? Paste their IP" style={{ maxWidth: 260 }} /><button className="btn sm" onClick={() => un({ unblock: val("guard_ip").trim() })}>Never block</button></div></>}
  </div>);
}

/* ---------------- hide your IP (relay), flood protection, guard */
function Relay({ s, reloadPage }) {
  const [res, setRes] = useState(null), [testing, setTesting] = useState(false), [flood, setFlood] = useState(""), [guardTick, setGuardTick] = useState(0);
  const body = () => { const ports = {}; document.querySelectorAll("[data-rp]").forEach(i => ports[i.dataset.rp] = i.value === "" ? null : Number(i.value)); return { relay_enabled: chk("relay_enabled"), relay_host: val("relay_host").trim(), relay_ports: ports }; };
  const splitHost = () => {   // pasted "host:port"? split it
    const el = $("relay_host"), v = el.value.trim().replace(/^[a-z]+:\/\//i, "").replace(/\/.*$/, ""), m = v.match(/^([^:\s]+):(\d{1,5})$/);
    el.value = m ? m[1] : v;
    const first = document.querySelector("[data-rp]");
    if (m && first && !first.value) first.value = m[2];
  };
  const save = async () => { try { await L.api("/api/settings", { json: body() }); L.toast(chk("relay_enabled") ? "Hide my IP is on - players now get the relay address" : "Saved"); reloadPage(); } catch (e) { L.toast(e.message); } };
  const test = async () => {
    setTesting(true);
    try { const b = body(); delete b.relay_enabled; await L.api("/api/settings", { json: b }); setRes((await L.api("/api/relay-check")).results); } catch (e) { L.toast(e.message); }
    setTesting(false);
  };
  const floodStatus = async () => { try { const f = await L.api("/api/flood-status"); setFlood(f.active ? "Active - blocked " + f.dropped + " packets since it was turned on" : ($("flood_protect") && chk("flood_protect") ? "Starting…" : "")); } catch (e) {} };
  useEffect(() => { if (s.platform === "linux") floodStatus(); }, []);
  const toggle = (key, onMsg, offMsg, after) => async e => {
    const el = e.target;
    try { await L.api("/api/settings", { json: { [key]: el.checked } }); L.toast(el.checked ? onMsg : offMsg); setTimeout(after, key === "guard_on" ? 1200 : 1500); } catch (x) { L.toast(x.message); el.checked = !el.checked; }
  };
  return (<div className="card" style={{ marginTop: 16 }}><h2>Hide your IP (DDoS protection) <span className={"badge " + (s.relay_enabled ? "good" : "")}>{s.relay_enabled ? "On" : "Off"}</span></h2>
    <p className="small muted">Normally players connect straight to your home internet address. Everyone who plays on your server can see it, and someone could use it to flood (DDoS) your connection so your whole home loses internet. With this on, players join through a relay instead.</p>
    <div className="grid g2" style={{ margin: "10px 0" }}>
      <div className="card tight" style={{ padding: "10px 14px" }}><b style={{ color: "var(--good-ink)" }}>✓ Much less chance of DDoS</b><div className="small muted">Your home address stays hidden. Attacks hit the relay, which is built to take them - not your home.</div></div>
      <div className="card tight" style={{ padding: "10px 14px" }}><b style={{ color: "var(--warn-ink)" }}>✕ Higher latency (more lag)</b><div className="small muted">Every packet makes a detour through the relay: usually +10-40 ms with a relay in your country, more if it's far away. Pick one close to you and your players.</div></div>
    </div>
    <Toggle id="relay_enabled" on={s.relay_enabled} title="Hide my IP - players join through a relay">Off by default. You need a relay first (see below)</Toggle>
    <details style={{ margin: "8px 0" }}><summary className="small"><b>How do I get a relay?</b></summary><ul className="small">
      <li><b>playit.gg</b>{` - easiest: install their app on this computer and make a tunnel to port ${(s.relay_servers[0] || {}).port || 30814}. BeamMP needs TCP and UDP, which needs playit Premium.`}</li>
      <li><b>A VPN with port forwarding</b> (for example Proton VPN or PIA - many big VPNs don't offer it). The forwarded port can change when the VPN reconnects.</li>
      <li><b>Your own VPS</b> (about €4/month) with WireGuard - most work to set up, but you control it and the address never changes.</li>
      <li>Step-by-step: <a href="https://github.com/Csabika-dev/beammp-easyserver/blob/main/PROTECT-YOUR-IP.md" {...NEW_TAB}>PROTECT-YOUR-IP guide</a></li></ul></details>
    <label className="f"><span>Relay address</span><input type="text" id="relay_host" defaultValue={s.relay_host || ""} placeholder="e.g. your-name.playit.gg or 203.0.113.5" autoComplete="off" spellCheck={false} onBlur={splitHost} /><small>The host name or IP address the relay gave you, without the port</small></label>
    {s.relay_servers.map(r => <label key={r.id} className="f"><span>{"Port on the relay" + (s.relay_servers.length > 1 ? " for " + r.name : "")}</span><input type="number" min={1} max={65535} data-rp={r.id} defaultValue={r.relay_port ?? ""} placeholder={String(r.port ?? "")} style={{ maxWidth: 220 }} /><small>{`Leave empty if the relay uses the same port as the server (${r.port ?? "?"})`}</small></label>)}
    <div className="small" style={{ margin: "8px 0 12px" }}><b>When it's on:</b><ul style={{ margin: "4px 0" }}>
      <li>Remove the port forward for the game port from your router - otherwise your home address is still reachable.</li>
      <li>Make the server private (Config → Private server) and share the relay address. The public server list shows the address the server reports from, which is usually your home IP.</li>
      <li>If your home IP was already shared, restart your router - most providers then give you a new address.</li>
      {s.remote_enabled && <li>"Access from the internet" is on, so the dashboard is still reachable at your home address.</li>}</ul></div>
    <div className="row"><button className="btn primary" onClick={save}>Save</button><button className="btn" disabled={testing} onClick={test}>{testing ? "Testing…" : "Test the relay"}</button></div>
    {res && <div className="card tight" style={{ marginTop: 12 }}>{res.length ? res.map((x, i) => <div key={i} className="check"><span className={"mark " + (x.ok ? "ok" : "bad")}>{x.ok ? "✓" : "✕"}</span><div><b>{x.name + " - "}<Ip>{x.address}</Ip></b>
      <div className="small muted">{x.ok ? `Reachable (about ${x.ms} ms from here to the relay and back). UDP can't be tested from here - join once to be sure.` : "Nothing answers. Is the relay running, and does it forward TCP and UDP to this computer?"}</div></div></div>) : <p className="small muted">No servers to test.</p>}</div>}
    <hr style={{ border: 0, borderTop: "1px solid var(--line)", margin: "16px 0" }} />
    {s.platform === "linux" ? <><label className="toggle"><input type="checkbox" id="flood_protect" defaultChecked={!!s.flood_protect} onChange={toggle("flood_protect", "Flood protection is on", "Flood protection is off", floodStatus)} /><span><b>Flood protection</b><small>Off by default. Limits how fast one address can connect to and send to your game server. Stops floods from single computers; it can't stop a big DDoS - only hiding your IP can. Your home network is never limited.</small></span></label><div className="small muted">{flood}</div></>
      : <p className="small muted"><b>Flood protection</b> (per-address limits on the game port) is only available on Linux. On Windows, hiding your IP is the protection that matters.</p>}
    <hr style={{ border: 0, borderTop: "1px solid var(--line)", margin: "16px 0" }} />
    <label className="toggle"><input type="checkbox" id="guard_on" defaultChecked={!!s.guard_on} onChange={toggle("guard_on", "BeamMP-only guard is on", "BeamMP-only guard is off - nothing is blocked while it is off", () => setGuardTick(t => t + 1))} /><span><b>BeamMP-only guard</b><small>Off by default. Port scanners and bots knock on any open port, get nothing and hang up. Real players stay connected. An address that keeps knocking (lots of short connections in 10 minutes) without ever staying to play is blocked by the firewall - for an hour, longer if it comes back. Your home network and anyone who has played here are never blocked.</small></span></label>
    <Guard key={guardTick} />
  </div>);
}

/* ---------------- export / import */
function ExportImport() {
  const [res, setRes] = useState(null), file = useRef(null);
  const srv = encodeURIComponent(S().SERVER);
  const pick = async e => {
    const f = e.target.files[0]; e.target.value = ""; if (!f) return;
    if (!confirm("Import " + f.name + "? Your current server config will be replaced (mods in the file are added and virus-checked).")) return;
    setRes({ busy: true });
    const { CSRF, SERVER } = S();
    const r = await fetch("/api/import", { method: "PUT", headers: { "X-ES-CSRF": CSRF, "X-ES-Server": SERVER }, body: f });
    let j = {}; try { j = await r.json(); } catch (x) {}
    setRes(r.ok ? { ok: j } : { err: j });
  };
  return (<div className="card" style={{ marginTop: 16 }}><h2>Backup / move to another computer</h2>
    <p className="small muted">Export your server settings (and optionally all mods) into one file, then import it on another server. Keys and passwords are never exported.</p>
    <div className="row"><a className="btn" href={"/api/export?srv=" + srv} download>Export settings</a><a className="btn" href={"/api/export?mods=1&srv=" + srv} download>Export settings + mods</a>
      <span className="spacer" /><button className="btn" onClick={() => file.current.click()}>Import…</button><input ref={file} type="file" accept=".zip" hidden onChange={pick} /></div>
    <div>{res && (res.busy ? <p className="muted">Importing…</p>
      : res.err ? <><div className="banner bad">{res.err.error || "Import failed"}</div>{(res.err.issues || []).map((i, k) => <div key={k} className={"issue " + i.level}><span className="ic">!</span><span>{i.message}</span></div>)}</>
        : <div className="banner info"><span>{`✓ Imported. ${res.ok.report.mods_added.length} mod(s) added${res.ok.report.mods_blocked.length ? ", " + res.ok.report.mods_blocked.length + " blocked by the virus check" : ""}. ${res.ok.note}`}</span></div>)}</div>
  </div>);
}

/* ---------------- the page */
export function Settings({ reload }) {
  const [page, setPage] = useState(0), [pwTick, setPwTick] = useState(0);
  const [s, , v, err] = useLoad("/api/settings", [reload, page]);
  if (!s) return err ? <div className="banner bad">{err}</div> : <SkelPage cards={6} />;
  const reloadPage = () => setPage(p => p + 1);
  const { SESSION } = S(), owner = SESSION.role === "owner" || !SESSION.role, N = s.notify;
  const saveNotif = async quiet => {
    const body = { notify: {} };
    NOTIFY.forEach(([k]) => body.notify[k] = chk("n_" + k));
    ["discord_enabled", "email_enabled", "update_check", "security_alerts", "security_reminders"].forEach(k => body[k] = chk(k));
    if ($("auto_restart")) body.auto_restart = chk("auto_restart");
    ["smtp_host", "smtp_port", "smtp_user", "smtp_to", "smtp_security"].forEach(k => body[k] = val(k));
    body.smtp_from = val("smtp_user").includes("@") ? val("smtp_user") : val("smtp_to");
    if (val("webhook")) body.discord_webhook = val("webhook");
    if (val("smtp_password")) body.smtp_password = val("smtp_password");
    await L.api("/api/settings", { json: body });
    $("webhook").value = ""; $("smtp_password").value = "";
    if (!quiet) L.toast("Saved");
  };
  const test = ch => async e => { const b = e.currentTarget; b.disabled = true; try { await saveNotif(true); await L.api("/api/notifications/test", { json: { channel: ch } }); L.toast("Test sent"); } catch (x) { L.toast(x.message); } b.disabled = false; };
  const saveVt = async () => { const x = val("vt").trim(); try { await L.api("/api/settings", { json: { vt_key: x === "off" ? "" : x } }); L.toast(x === "off" ? "VirusTotal turned off" : "Saved"); reloadPage(); } catch (e) { L.toast(e.message); } };
  const savePw = async () => { try { await L.api("/api/password", { json: { current: val("pw_cur"), new: val("pw_new") } }); L.toast("Password changed - remembered devices have to log in again"); $("pw_cur").value = $("pw_new").value = ""; setPwTick(t => t + 1); } catch (e) { L.toast(e.message); } };
  const saveRemote = async () => {
    const wantRemote = chk("remote_enabled"), wantHttps = chk("https") || wantRemote, lines = [];
    if (wantRemote !== !!s.remote_enabled) lines.push(wantRemote
      ? "• Internet access ON: this computer's firewall opens port " + s.port + " (TCP) for the dashboard\n• Your router is NOT changed - forward port " + s.port + " there yourself"
      : "• Internet access OFF: this computer's firewall closes port " + s.port + " again");
    if (wantHttps !== !!s.https) lines.push("• The dashboard restarts on " + (wantHttps ? "https://" : "http://") + " - your browser reconnects by itself" + (wantHttps ? "\n• The first time, your browser warns about the self-made certificate" : ""));
    if (!lines.length) return L.toast("Nothing changed");
    if (!confirm("This changes your network settings:\n\n" + lines.join("\n") + "\n\nContinue?")) return;
    try {
      L.toast("Applying… (creating a certificate can take a few seconds)", 8000);
      const r = await L.api("/api/remote", { json: { https: chk("https"), remote_enabled: chk("remote_enabled") } });
      if (r.network) L.toast("🌐 " + r.network, 7000);
      if (r.restart) { setTimeout(() => L.toast("Restarting the dashboard - you'll be taken to the new address", 6000), r.network ? 1500 : 0); setTimeout(() => location.href = r.url.replace(/\/\/[^:/]+/, "//" + location.hostname), 4500); }
      else { L.toast("Saved"); reloadPage(); }
    } catch (e) { L.toast(e.message); }
  };
  const security = e => saveNotif(false).catch(x => L.toast(x.message));
  return (<div key={v}>
    <h1>Settings</h1><p className="sub">Notifications, security, remote access and backups.</p>
    <Supporter />
    <div className="grid g2">
      <div className="card"><h2>Security alerts</h2>
        <label className="toggle"><input type="checkbox" id="security_alerts" defaultChecked={!!s.security_alerts} onChange={security} /><span><b>Alert me about attacks</b><small>Password guessing, websites probing the dashboard, mods with viruses, tampered server files, zip bombs, connection floods. Sent to every channel that is set up (here, Discord, email) - even if its switch below is off</small></span></label>
        <label className="toggle"><input type="checkbox" id="security_reminders" defaultChecked={!!s.security_reminders} onChange={security} /><span><b>Repeat every 15 minutes</b><small>Until you click "Got it - stop alerts" (or the link/pop-up in the message)</small></span></label>
        <PopupButton />
      </div>
      <div className="card"><h2>Notify me about</h2>
        {NOTIFY.map(([k, t, h]) => <Toggle key={k} id={"n_" + k} on={k === "report" ? N.report !== false : N[k]} title={t}>{h}</Toggle>)}
        {s.platform === "windows" && <Toggle id="auto_restart" on={s.auto_restart} title="Restart after a crash">Start the server again automatically</Toggle>}
        <Toggle id="update_check" on={s.update_check} title="Check for updates">Every 6 hours</Toggle>
        <p className="small muted" style={{ marginTop: 12 }}>Notifications always appear on the Notifications page. Also send them to:</p>
      </div>
      <div className="grid" style={{ alignContent: "start" }}>
        <div className="card"><h2>Discord</h2><Toggle id="discord_enabled" on={s.discord_enabled} title="Send to Discord">Posts to a channel via a webhook</Toggle>
          <label className="f" style={{ marginTop: 10 }}><span>Webhook URL</span><input type="password" id="webhook" placeholder={s.has_discord ? "Saved (encrypted) - paste a new one to replace" : "https://discord.com/api/webhooks/…"} autoComplete="off" /><small>Discord channel → Edit channel → Integrations → Webhooks → New webhook → Copy URL</small></label>
          <button className="btn sm" onClick={test("discord")}>Send test</button></div>
        <div className="card"><h2>Email</h2><Toggle id="email_enabled" on={s.email_enabled} title="Send emails">Uses your email provider's SMTP server</Toggle>
          <div className="grid g2" style={{ marginTop: 10, gap: "0 12px" }}>
            <label className="f"><span>SMTP server</span><input type="text" id="smtp_host" defaultValue={s.smtp_host} placeholder="smtp.gmail.com" /></label>
            <label className="f"><span>Port</span><input type="number" id="smtp_port" defaultValue={s.smtp_port} /></label>
            <label className="f"><span>Username</span><input type="text" id="smtp_user" defaultValue={s.smtp_user} autoComplete="off" /></label>
            <label className="f"><span>Password</span><input type="password" id="smtp_password" placeholder={s.has_smtp_password ? "Saved (encrypted)" : "App password"} autoComplete="new-password" /></label>
            <label className="f"><span>Security</span><select id="smtp_security" defaultValue={s.smtp_security}><option value="starttls">STARTTLS (port 587)</option><option value="ssl">SSL (port 465)</option><option value="none">None</option></select></label>
            <label className="f"><span>Send to</span><input type="email" id="smtp_to" defaultValue={s.smtp_to} placeholder="you@example.com" /></label>
          </div>
          <small className="muted">Gmail/Outlook: create an "app password" in your account security settings.</small>
          <div className="row" style={{ marginTop: 10 }}><button className="btn sm" onClick={test("email")}>Send test</button></div></div>
      </div>
    </div>
    <div className="row" style={{ margin: "16px 0 30px" }}><button className="btn primary" onClick={() => saveNotif(false).catch(e => L.toast(e.message))}>Save notification settings</button></div>

    <Phone />
    <DiscordBot />
    <Integrations />
    {owner && <StatusPage />}
    <Power />
    {SESSION.role === "owner" && <Users />}

    <div className="grid g2">
      <div className="card"><h2>Mod virus check</h2><p className="small muted">Optional VirusTotal key (free account at virustotal.com → your name → API key). Stored encrypted.</p>
        <div className="row"><input type="password" id="vt" placeholder={s.has_vt ? "Saved - paste a new key or type off" : "VirusTotal API key"} autoComplete="off" /><button className="btn" onClick={saveVt}>Save</button></div></div>
      <div className="card"><h2>Password</h2>
        <label className="f"><span>Current password</span><input type="password" id="pw_cur" autoComplete="current-password" /></label>
        <label className="f"><span>New password</span><input type="password" id="pw_new" autoComplete="new-password" /><small>{s.remote_enabled ? "At least 12 characters" : "At least 8 characters (12 for internet access)"}</small></label>
        <button className="btn" onClick={savePw}>Change password</button></div>
    </div>

    <Devices tick={pwTick} />
    <TwoStep s={s} reloadPage={reloadPage} />

    <div className="card" style={{ marginTop: 16 }}><h2>Access from the internet</h2>
      <p className="small muted">{`Manage the server from anywhere: needs HTTPS, two-step login and a 12+ character password. You also have to forward port ${s.port} (TCP) on your router. Leave this off if you only use the dashboard at home.`}</p>
      <Toggle id="https" on={s.https} title="HTTPS (encrypted connection)">Uses a self-made certificate - your browser shows a warning the first time; check the fingerprint below and continue</Toggle>
      <Toggle id="remote_enabled" on={s.remote_enabled} title="Allow access from the internet">Only with HTTPS + two-step login</Toggle>
      {s.cert_fingerprint && <p className="small">Certificate fingerprint (SHA-256): <span className="mono">{s.cert_fingerprint}</span></p>}
      <button className="btn" onClick={saveRemote}>Apply</button></div>

    <Relay s={s} reloadPage={reloadPage} />
    <Backups />
    <ExportImport />
    <p className="small muted" style={{ marginTop: 24 }}>{`BeamMP EasyServer ${SESSION.version} · ${s.platform} · not affiliated with the BeamMP team`}</p>
  </div>);
}
