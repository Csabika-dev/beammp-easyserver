// Settings → Sleep & wake-up: Wake-on-LAN check, auto-sleep, router guides and the wake helper.
import { useRef, useState } from "react";
import * as L from "./legacy.js";
import { Blur, Ip } from "./pages.jsx";
import { chk, val, TIME, Mono, Toggle, Warn, useLoad, SkelCard } from "./ui.jsx";

const NEW_TAB = { target: "_blank", rel: "noopener noreferrer" };
const Guide = ({ children }) => <div className="card tight" style={{ padding: "10px 14px" }}>{children}</div>;
const ROUTERS = [
  ["fritz", "FRITZ!Box", m => <><ol className="small"><li>Open <b>fritz.box</b> → <b>Home Network</b> → <b>Network</b> → <b>Network Connections</b>.</li>
    <li>Click the pencil next to this computer (MAC <Mono>{m}</Mono>).</li>
    <li>Turn on <b>"Start this computer automatically as soon as it is accessed from the internet"</b> → OK. <b>Start Computer</b> on the same page wakes it right now.</li></ol>
    <p className="small muted">Then friends who join with your address (or DuckDNS name) wake the computer up just by trying to connect - the first try fails, joining again after about 30 seconds works. Away from home you can press <b>Start Computer</b> through MyFRITZ! or the FRITZ!Box VPN. The FRITZ!Box only does this if the computer was idle for at least 15 minutes.</p></>],
  ["asus", "ASUS", m => <><ol className="small"><li>Open <b>router.asus.com</b> → <b>Advanced Settings</b> → <b>Network Tools</b> → <b>Wake on LAN</b>.</li>
    <li>Enter the MAC <Mono>{m}</Mono> (or pick the computer from the list and press <b>+</b>), then <b>Wake up</b>.</li></ol>
    <p className="small muted">Away from home: the <b>ASUS Router</b> app (Android/iPhone) has <b>WOL</b> too, when remote access is on in the app.</p></>],
  ["tplink", "TP-Link (Deco, Archer)", m => <><ol className="small"><li><b>Deco app</b>: More → Advanced → <b>WOL</b> → Add WOL Device. <b>Tether app</b> (Archer routers): More → Advanced Settings → <b>WOL</b> → Add WOL Device.</li>
    <li>Pick this computer (MAC <Mono>{m}</Mono>) while it's on, then tap the alarm icon to wake it.</li></ol>
    <p className="small muted">Only on models with recent firmware - if you don't see WOL, update the firmware in the app or use the wake helper.</p></>],
  ["unifi", "Ubiquiti (UniFi, EdgeRouter)", m => <><p className="small">UniFi gateways and EdgeRouters have no Wake-on-LAN button, and a wake-up signal doesn't travel through the UniFi VPN (Teleport / WireGuard) either. Use the <b>wake helper</b> below on any device that's always on - it works with every UniFi setup, needs no port forwarding and adds <b>/start</b> in Discord.</p>
    <p className="small muted">At home, any Wake-on-LAN phone app on your Wi-Fi works too (MAC <Mono>{m}</Mono>). Wired and wireless clients must be in the same network (VLAN) as this computer.</p></>],
  ["mikrotik", "MikroTik", m => <><p className="small">WinBox / WebFig: <b>Tools → WoL</b> → MAC <Mono>{m}</Mono>, interface <b>bridge</b> → Wake. In the terminal:</p>
    <pre className="mono small" style={{ whiteSpace: "pre-wrap" }}>{`/tool/wol mac=${m.toUpperCase()} interface=bridge`}</pre><p className="small muted">From outside, connect with the MikroTik app or your VPN first.</p></>],
  ["openwrt", "OpenWrt / GL.iNet", m => <ol className="small"><li>LuCI → <b>System → Software</b> → install <b>luci-app-wol</b> (GL.iNet: open LuCI from Advanced first).</li>
    <li><b>Services → Wake on LAN</b> → interface <b>br-lan</b>, host MAC <Mono>{m}</Mono> → Wake up.</li></ol>],
  ["netgear", "Netgear (Nighthawk, Orbi)", m => <p className="small">Netgear's own firmware has no Wake-on-LAN button. Use the <b>wake helper</b> below, or a Wake-on-LAN phone app while you're on the home Wi-Fi (MAC <Mono>{m}</Mono>).</p>],
  ["other", "Something else / don't know", m => <p className="small">Look for <b>Wake on LAN</b> or <b>WOL</b> in your router's web page or app (often under Tools, Advanced or the device list). Many provider routers, Google/Nest Wifi, eero and Linksys don't have it - then use the <b>wake helper</b> below. At home, any Wake-on-LAN app on your phone works with the MAC <Mono>{m}</Mono>.</p>],
];
const WB = { on: ["good", "On"], off: ["warn", "Off"], unsupported: ["bad", "Not supported"], wifi: ["", "Wi-Fi - can't wake"], unknown: ["", "Unknown"], "no-ethtool": ["warn", "Off?"] };
const IC = { pass: ["✓", "var(--good-ink)"], warn: ["!", "var(--warn-ink)"], fail: ["✕", "var(--crit-ink)"], unknown: ["?", "var(--text-2)"] };
const ORDER = { fail: 0, warn: 1, unknown: 2, pass: 3 };

// lets the "server is asleep" page offer a Wake button (needs HTTPS)
async function cacheWake() {
  if (!("caches" in window) || !window.isSecureContext) return;
  try { const d = await L.api("/api/power/offline"); const c = await caches.open("es-shell-v2"); if (d.topic) await c.put("/__wake.json", new Response(JSON.stringify(d))); else await c.delete("/__wake.json"); } catch (e) {}
}

function Score({ W }) {
  const col = W.blocking ? "var(--crit-ink)" : W.score >= 90 ? "var(--good-ink)" : "var(--warn-ink)";
  return (<div className="card tight" style={{ padding: "12px 14px", margin: "8px 0" }}><div className="row" style={{ gap: 14, alignItems: "center" }}>
    <div style={{ fontSize: 30, fontWeight: 700, color: col, minWidth: 64 }}>{W.score}<span className="small muted" style={{ fontWeight: 400 }}>/100</span></div>
    <div><b>{`Compatibility: ${W.verdict}`}</b><div className="small muted">{W.blocking > 1 ? `${W.blocking} things must be changed before it can wake up.` : W.blocking ? "1 thing must be changed before it can wake up.": "Nothing is blocking it."}</div></div></div>
    <div style={{ marginTop: 8 }}>{W.checks.slice().sort((x, y) => ORDER[x.state] - ORDER[y.state]).map((c, i) => <div key={i} className="row small" style={{ alignItems: "flex-start", gap: 8, padding: "4px 0", borderTop: "1px solid var(--line)" }}>
      <b style={{ color: IC[c.state][1], width: 14, flex: "none", textAlign: "center" }}>{IC[c.state][0]}</b>
      <div style={{ flex: 1 }}><b>{c.title}</b>{" - " + c.why}{c.fix && c.state !== "pass" && <div style={{ marginTop: 2 }}><b>What to change:</b> {c.fix}</div>}</div></div>)}</div></div>);
}

export function Power() {
  const fresh = useRef(false), [checking, setChecking] = useState(false), [asleep, setAsleep] = useState(false), [busy, setBusy] = useState("");
  const [router, setRouter] = useState(() => L.store.get("es-router", "")), [code, setCode] = useState(null);
  const [p, again, v, err] = useLoad(async () => {
    try { const r = await L.api("/api/power" + (fresh.current ? "?refresh=1" : "")); cacheWake(); return r; } finally { fresh.current = false; setChecking(false); }
  }, []);
  const reload = full => { fresh.current = !!full; setChecking(!!full); again(); };
  if (asleep) return <div className="card" style={{ margin: "0 0 16px" }}><h2>Sleep &amp; wake-up</h2><p>💤 Going to sleep in a few seconds…</p></div>;
  if (err && !p) return <div className="card" style={{ margin: "0 0 16px" }}><h2>Sleep &amp; wake-up</h2><p className="small muted">{err}</p><button className="btn sm primary" onClick={() => reload(false)}>Try again</button></div>;
  if (!p) return <SkelCard lines={6} style={{ margin: "0 0 16px" }} />;
  const St = p.settings, wired = p.adapters.filter(a => !a.wifi), main = p.adapters.find(a => a.name === p.main);
  const wolOk = main && main.wol === "on";
  const mins = [15, 30, 45, 60, 120, 240, 480]; if (!mins.includes(St.sleep_idle)) mins.push(St.sleep_idle); mins.sort((a, b) => a - b);
  const status = !St.sleep_on ? "" : p.busy ? `Staying awake: ${p.busy}.` : !p.in_window ? "Outside the sleep hours - staying awake." : p.sleeps_at ? `Nobody's around - goes to sleep in about ${L.fmtDur(p.sleeps_at - Date.now() / 1000)}.` : "";
  const m = p.mac || "aa:bb:cc:dd:ee:ff";
  const R = ROUTERS.find(x => x[0] === router);
  const save = async () => {
    try { await L.api("/api/power", { json: { sleep_on: chk("pw_on"), sleep_idle: +val("pw_idle"), sleep_from: val("pw_from"), sleep_to: val("pw_to"), sleep_wake_at: val("pw_wake"), sleep_wake_events: chk("pw_ev") } }); L.toast("Saved"); reload(); }
    catch (e) { L.toast(e.message, 6000); }
  };
  const sleep = async () => { if (await L.sleepComputer(wolOk ? "" : "Wake-on-LAN isn't ready yet - you may have to press the power button to wake it up.")) setAsleep(true); };
  const wol = async a => { setBusy("wol:" + a); try { const r = await L.api("/api/power/wol", { json: { adapter: a } }); L.toast(r.msg, 7000); reload(true); } catch (e) { L.toast(e.message, 8000); } setBusy(""); };
  const helper = body => L.api("/api/power/helper", { json: body });
  const showCode = async neu => { try { setCode((await helper({ action: "pair", new: !!neu })).code); } catch (e) { L.toast(e.message, 6000); } };
  const pair = async () => { try { await helper({ action: "pair" }); } catch (e) { return L.toast(e.message, 6000); } await again(); showCode(false); };
  const forget = async () => { if (!confirm("Remove the wake helper? It stops answering right away.")) return; try { await helper({ action: "forget" }); setCode(null); again(); } catch (e) { L.toast(e.message); } };
  const test = async () => {
    setBusy("test");
    try { const r = await helper({ action: "test" }); L.toast(r.found ? "The helper answered (version " + r.version + ") - it's ready." : "No answer. Is the helper running and connected to the internet?", 7000); if (r.found) again(); } catch (e) { L.toast(e.message, 6000); }
    setBusy("");
  };
  const pickRouter = e => { setRouter(e.target.value); L.store.set("es-router", e.target.value); };
  return (<div className="card" style={{ margin: "0 0 16px" }} key={v}>
    <h2>Sleep &amp; wake-up <span className={"badge " + (St.sleep_on ? "good" : "")}>{St.sleep_on ? "Auto-sleep on" : "Auto-sleep off"}</span>{checking && <> <span className="small muted">checking…</span></>}</h2>
    <p className="small muted">Don't run the computer 24/7: it can go to sleep when nobody plays and wake up again when someone wants to play - from your router, your phone, Discord, or by itself before an event. Sleeping uses about as little power as switched off.</p>
    {p.error && <Warn>{p.error}</Warn>}
    <h3 style={{ margin: "14px 0 4px" }}>1. Wake-on-LAN {wolOk ? <span className="badge good">Ready</span> : <span className="badge warn">Not ready</span>}</h3>
    <p className="small muted">Lets another device wake this computer with a "magic packet". Needs a <b>network cable</b> - it doesn't work over Wi-Fi - and laptops must stay plugged in.</p>
    {p.wol_score && <Score W={p.wol_score} />}
    {p.on_wifi && <Warn>This computer is on <b>Wi-Fi</b>. Connect it to the router with a network cable, then press Refresh.</Warn>}
    {!wired.length && <Warn>No network cable adapter found. Wake-on-LAN needs one (a USB network adapter usually can't wake a computer).</Warn>}
    <div style={{ margin: "6px 0" }}>{p.adapters.length ? p.adapters.map(a => { const w = WB[a.wol] || WB.unknown; return <div key={a.name} className="row small" style={{ padding: "4px 0", gap: 8, flexWrap: "wrap" }}>
      <b>{a.name}</b>{a.desc && <span className="muted">{a.desc}</span>}<span className="mono">{a.mac}</span>{a.ip && <span className="mono"><Blur text={a.ip} /></span>}
      <span className="muted">{a.wifi ? "Wi-Fi" : a.cable ? "cable plugged in" : "no cable"}</span><span className={"badge " + w[0]}>{w[1]}</span><span className="spacer" />
      {!a.wifi && a.wol !== "on" && a.wol !== "unsupported" && <button className="btn sm" disabled={busy === "wol:" + a.name} onClick={() => wol(a.name)}>{busy === "wol:" + a.name ? "Working…" : "Turn on"}</button>}</div>; })
      : <p className="small muted">No network adapters found.</p>}</div>
    <details style={{ margin: "6px 0" }}><summary className="small"><b>It still doesn't wake up? Check the BIOS</b></summary><div className="small">
      <p>Wake-on-LAN must also be allowed in the computer's BIOS/UEFI setup (press F2, F10, F12 or Del while it starts). Look for:</p><ul>
        <li><b>Wake on LAN</b>, <b>Power On By PCI-E</b>, <b>Resume by LAN</b> or <b>PME Event Wake Up</b> → Enabled</li>
        <li><b>ErP</b> / <b>EuP</b> / <b>Deep Sleep</b> → Disabled (they cut power to the network chip)</li>
        <li>HP: <b>Built-In Device Options → Wake on LAN</b>. Dell: <b>Power Management → Wake on LAN</b>. Lenovo ThinkPad: <b>Config → Network → Wake On LAN</b> (AC only).</li></ul>
      <p>Test it: press <b>Sleep now</b>, wait a minute, then wake it from your router or phone. The network light on the computer should stay on while it sleeps.</p></div></details>

    <h3 style={{ margin: "16px 0 4px" }}>2. Auto-sleep</h3>
    {!p.can_sleep && <Warn>This computer can't go to sleep (no sleep support found).</Warn>}
    <Toggle id="pw_on" on={St.sleep_on} title="Go to sleep when nobody plays">Off by default. Never while someone is online, an event runs or starts soon, or the dashboard is in use</Toggle>
    <div className="grid g2" style={{ gap: "0 12px", marginTop: 8 }}>
      <label className="f"><span>After nobody played for</span><select id="pw_idle" defaultValue={St.sleep_idle}>{mins.map(x => <option key={x} value={x}>{x < 60 ? x + " minutes" : x / 60 + (x === 60 ? " hour" : " hours")}</option>)}</select></label>
      <label className="f"><span>Only between (optional)</span><span className="row" style={{ gap: 6 }}><input type="time" id="pw_from" defaultValue={St.sleep_from} style={{ maxWidth: 130, ...TIME }} /> and <input type="time" id="pw_to" defaultValue={St.sleep_to} style={{ maxWidth: 130, ...TIME }} /></span><small>For example 01:00 and 15:00. Empty = any time</small></label>
      <label className="f"><span>Wake up by itself every day at (optional)</span><input type="time" id="pw_wake" defaultValue={St.sleep_wake_at} style={{ maxWidth: 160, ...TIME }} /><small>{p.rtc ? "Uses the computer's built-in alarm clock - no other device needed" : "This computer has no wake-up alarm, so this may not work"}</small></label>
      <Toggle id="pw_ev" on={St.sleep_wake_events} title="Wake up before events" style={{ alignSelf: "center" }}>10 minutes before every scheduled event (Config → Events)</Toggle>
    </div>
    {status && <p className="small" style={{ margin: "4px 0" }}>{status}</p>}
    {p.next_wake ? <p className="small muted" style={{ margin: "4px 0" }}>{`Next wake-up by itself: ${L.fmtTime(p.next_wake)}.`}</p> : null}
    {p.woke_at ? <p className="small muted" style={{ margin: "4px 0" }}>{`Last woke up: ${L.ago(p.woke_at)}.`}</p> : null}
    <div className="row"><button className="btn primary" onClick={save}>Save</button><button className="btn" disabled={!p.can_sleep} onClick={sleep}>Sleep now</button><button className="btn" onClick={() => reload(true)}>Refresh</button></div>

    <h3 style={{ margin: "16px 0 4px" }}>3. How to wake it up</h3>
    <p className="small muted">The address to wake: MAC <Mono>{m}</Mono>{p.brd && p.brd.length > 0 && <>, network <span className="mono"><Blur text={p.brd[0]} /></span></>}. Pick what you have:</p>
    <label className="f"><span>Your router</span><select style={{ maxWidth: 320 }} value={router} onChange={pickRouter}><option value="">- pick your router -</option>{ROUTERS.map(r => <option key={r[0]} value={r[0]}>{r[1]}</option>)}</select></label>
    {R && <Guide>{R[2](m)}</Guide>}
    <div className="card tight" style={{ padding: "12px 14px", marginTop: 10 }}><b>Wake helper</b>{" "}
      {p.helper.paired ? (p.helper.last_seen ? <span className="badge good">{`Answered ${L.ago(p.helper.last_seen)}`}</span> : <span className="badge warn">Set up - not tested yet</span>) : <span className="badge">Not set up</span>}
      <p className="small muted" style={{ margin: "4px 0" }}>A tiny program for any device at home that's always on - a Raspberry Pi, a NAS, another PC. While this computer sleeps it answers <b>/start</b> in Discord{p.helper.bot ? "" : " (needs the Discord bot)"} and the <b>Wake up</b> button in the phone app or on this page - from anywhere, without port forwarding. It can only send wake-up signals; it gets no access to this computer.</p>
      {p.helper.paired ? <>
        {code && <><label className="f"><span>Pairing code</span><textarea readOnly rows={3} className="mono" style={{ minHeight: 70, wordBreak: "break-all" }} value={code} /><small>Treat it like a password: anyone with it can wake this computer. "New code" makes the old one stop working.</small></label>
          <button className="btn sm" onClick={() => navigator.clipboard && navigator.clipboard.writeText(code).then(() => L.toast("Copied"))}>Copy</button></>}
        <details style={{ margin: "6px 0" }}><summary className="small"><b>Install it</b></summary><div className="small">
          <p><b>Raspberry Pi / Linux</b> - in a terminal on that device:</p>
          <pre className="mono small" style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}>{"curl -fsSLO https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/main/wake/install-wake-helper.sh\nsudo bash install-wake-helper.sh"}</pre>
          <p><b>Windows</b> - download <b>BeamMP-EasyServer-WakeHelper.zip</b> from the <a href="https://github.com/Csabika-dev/beammp-easyserver/releases/latest" {...NEW_TAB}>latest release</a>, unzip it and double-click <b>Install-Wake-Helper.bat</b>.</p>
          <p>Paste the pairing code when it asks. For <b>/start</b> in Discord it also asks for your bot token (Developer Portal → Bot → Reset Token - then paste the new token here in Settings → Discord bot too). The device must stay on and be in your home network, ideally with a cable.</p></div></details>
        <div className="row"><button className="btn" onClick={() => showCode(false)}>Show pairing code</button><button className="btn" disabled={busy === "test"} onClick={test}>{busy === "test" ? "Asking…" : "Test the helper"}</button>
          <button className="btn" onClick={() => { if (confirm("Make a new pairing code? The helper (and phones) set up with the old one stop working until you set them up again.")) showCode(true); }}>New code</button>
          <button className="btn danger" onClick={forget}>Remove</button></div></>
        : <button className="btn" disabled={!p.mac} onClick={pair}>Set up a wake helper</button>}
    </div>
    <p className="small muted" style={{ marginTop: 10 }}><b>Phone:</b> the Android app shows a <b>Wake up</b> button when the server doesn't answer - scan the QR code under Phone app again after setting up the helper. At home it wakes the computer even without the helper. The home-screen app on iPhone shows the same button (with the helper).</p>
  </div>);
}
