// Settings page cards: supporter, phone app, Discord bot, other apps, status page, sleep & wake-up, users, devices,
// backups, DuckDNS and computer load.
import { useEffect, useState } from "react";
import * as L from "./legacy.js";
import { Blur, Ip } from "./pages.jsx";
import { $, S, val, chk, TIME, Pill, Mono, Toggle, Warn, useLoad, post, SkelCard, Oops } from "./ui.jsx";
import { Modal } from "./mods.jsx";

const NEW_TAB = { target: "_blank", rel: "noopener noreferrer" };
const isOwner = () => { const r = S().SESSION.role; return r === "owner" || !r; };

// A card that couldn't load: its name, why, and a Try again button.
const Failed = ({ title, err, retry }) => <><h2>{title}</h2><p className="small muted">{err}</p>{retry && <button className="btn sm primary" onClick={retry}>Try again</button>}</>;
const QR = ({ q, px }) => q ? <svg viewBox={`-4 -4 ${q[0] + 8} ${q[0] + 8}`} width={px} height={px} style={{ background: "#fff", borderRadius: 8, display: "block" }} role="img" aria-label="QR code"><path d={q[1]} fill="#000" /></svg> : null;
// A QR code drawn from a path the server sent (only path letters and numbers are allowed through)
export const KeyQR = ({ r, px, label }) => {
  const n = Number(r.qr_size) || 0, qp = /^[MhvzZ0-9 -]*$/.test(r.qr_path || "") ? r.qr_path : "";
  if (!n || !qp) return null;
  return <div style={{ background: "#fff", padding: 12, borderRadius: 8, display: "inline-block", margin: "6px 0" }}><svg width={px} height={px} viewBox={`-4 -4 ${n + 8} ${n + 8}`} shapeRendering="crispEdges" role="img" aria-label={label}><rect x={-4} y={-4} width={n + 8} height={n + 8} fill="#fff" /><path d={qp} fill="#000" /></svg></div>;
};

/* ---------------- supporter */
export function Supporter() {
  const [d, again, v, err] = useLoad("/api/supporter");
  const [busy, setBusy] = useState(false);
  if (err || (d && d.off)) return null;
  if (!d) return <SkelCard lines={2} style={{ marginBottom: 16 }} />;
  const owner = (S().SESSION.role || "owner") === "owner";
  const activate = async () => { setBusy(true); try { const r = await L.api("/api/supporter", { json: { key: val("sup_key").trim() } }); L.toast(r.note, 7000); L.bridge.refreshShell(); L.bridge.show("settings"); } catch (e) { L.toast(e.message, 8000); setBusy(false); } };
  const remove = async () => { if (!confirm("Remove the supporter licence from this computer? You can activate it again here or on another computer.")) return; try { const r = await L.api("/api/supporter", { json: { action: "remove" } }); L.toast(r.note, 6000); L.bridge.show("settings"); } catch (e) { L.toast(e.message); } };
  const early = async e => { try { await L.api("/api/supporter", { json: { early_access: e.target.checked } }); L.toast("Saved"); } catch (x) { L.toast(x.message); } };
  return (<div className="card" style={{ marginBottom: 16 }} key={v}>{d.active ? <>
    <div className="row"><h2 style={{ margin: 0 }}>Supporter <span className="badge good">Active</span></h2><span className="spacer" />{owner && <button className="btn sm" onClick={remove}>Remove from this computer</button>}</div>
    <p className="small" style={{ margin: "8px 0" }}>{"Thank you for supporting EasyServer! " + (d.plan ? d.plan + " · " : "") + (d.email ? d.email + " · " : "") + (d.expires_at ? "renews/ends " + String(d.expires_at).slice(0, 10) : "no end date")}</p>
    <label className="toggle"><input type="checkbox" defaultChecked={!!d.early_access} disabled={!owner} onChange={early} /><span><b>Experimental versions</b><small>{"Get the newest features first, before they're fully tested" + (d.early ? " - " + d.early + " is ready now" : "")}</small></span></label>
    {d.early && d.early_url && <p className="small"><a href={d.early_url} target="_blank" rel="noopener">{`Download EasyServer ${d.early} (preview)`}</a></p>}
  </> : <>
    <div className="row"><h2 style={{ margin: 0 }}>Support EasyServer</h2><span className="spacer" /><a className="btn sm" href={d.url} target="_blank" rel="noopener">{d.shop_open ? "Become a supporter" : "Coming soon"}</a></div>
    <p className="small muted" style={{ margin: "8px 0" }}>EasyServer is free and stays free - every feature works without paying. Supporters get early access to new versions and a bigger say in what gets built next.</p>
    {d.status && d.status !== "active" && <div className="banner warn"><span className="small">{`Your licence isn't active (${d.status}). Supporter extras are off - everything else keeps working.`}</span></div>}
    {owner && <div className="row"><input type="text" id="sup_key" placeholder="Licence key from your email" maxLength={80} spellCheck={false} autoComplete="off" style={{ flex: 1 }} /><button className="btn primary" disabled={busy} onClick={activate}>Activate</button></div>}
  </>}</div>);
}

/* ---------------- phone app + push notifications */
export function Phone() {
  const [d, again, v, err] = useLoad(["/api/phoneapp", "/api/ntfy"]);
  if (err && !d) return <div className="card" style={{ margin: "0 0 16px" }}><Failed title="Phone app" err={err} retry={again} /></div>;
  if (!d) return <SkelCard style={{ margin: "0 0 16px" }} />;
  const [pa, nt] = d;
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  const topic = nt.subscribe ? nt.subscribe.split("/").pop() : "";
  const save = async () => { try { await L.api("/api/ntfy", { json: { enabled: chk("nt_on") } }); L.toast("Saved"); again(); } catch (e) { L.toast(e.message); } };
  const test = async () => { try { await L.api("/api/ntfy", { json: { test: true } }); L.toast("Test sent - check your phone"); } catch (e) { L.toast(e.message, 6000); } };
  const fresh = async () => { if (!confirm("Make a new topic? Phones subscribed to the old one stop getting notifications.")) return; try { await L.api("/api/ntfy", { json: { new_topic: true } }); again(); } catch (e) { L.toast(e.message); } };
  return (<div className="card" style={{ margin: "0 0 16px" }} key={v}><h2>Phone app</h2>
    <p className="small muted">Manage your servers from your phone like a normal app - with its own icon, full screen, no browser bar.{standalone && <> <b>You're using it as an app right now.</b></>}</p>
    <div className="grid g2" style={{ gap: 12, marginTop: 6 }}>
      <div className="card tight" style={{ padding: "12px 14px" }}><b>Android</b>
        <ol className="small" style={{ margin: "6px 0" }}>
          <li>On the phone, download <b>BeamMP-EasyServer.apk</b> from <a href={pa.apk} {...NEW_TAB}>the latest release</a> and open it (allow "install unknown apps" for your browser when asked).</li>
          <li>{"Open the app and scan this code with the phone's camera - the app connects to this dashboard" + (pa.https ? " and remembers its certificate, so nobody can pretend to be your server" : "") + "."}</li></ol>
        {pa.https ? <QR q={pa.qr} px={170} /> : <Warn>Turn on <b>HTTPS</b> (Settings → Access from the internet) first - the app only connects over an encrypted connection.</Warn>}
        {pa.https && <div className="small muted" style={{ marginTop: 6 }}>Address: <span className="mono"><Blur text={pa.url} /></span></div>}
      </div>
      <div className="card tight" style={{ padding: "12px 14px" }}><b>iPhone</b>
        <ol className="small" style={{ margin: "6px 0" }}>
          <li>Open this dashboard in <b>Safari</b> on the iPhone (same address as on this computer).</li>
          <li>Tap the <b>Share</b> button, then <b>Add to Home Screen</b> → Add.</li>
          <li>Open it from the new <b>BeamMP</b> icon - it opens full screen like an app.</li></ol>
        <p className="small muted">Apple only allows apps from the App Store, so on iPhone it's a home-screen app. Android phones can do the same in Chrome (⋮ → Add to Home screen) instead of the .apk.</p>
      </div>
    </div>
    <h3 style={{ margin: "16px 0 4px" }}>Push notifications on the phone</h3>
    <p className="small muted">Get crashes, security alerts, joins and everything else you picked under "Notify me about" as real phone notifications - through the free <b>ntfy</b> app (Android and iPhone), even when the dashboard isn't open.</p>
    <Toggle id="nt_on" on={nt.enabled} title="Send notifications to my phone">Off by default</Toggle>
    {nt.has_topic && <><div className="row" style={{ alignItems: "flex-start", gap: 14, margin: "8px 0", flexWrap: "wrap" }}><QR q={nt.qr} px={150} />
      <ol className="small" style={{ margin: 0, flex: 1, minWidth: 220 }}><li>Install <b>ntfy</b> from the Play Store / App Store.</li>
        <li>In ntfy tap <b>+</b> (subscribe to topic), paste this topic and subscribe:<br /><span className="mono" style={{ wordBreak: "break-all" }}>{topic}</span> <button className="btn sm" onClick={() => navigator.clipboard && navigator.clipboard.writeText(topic).then(() => L.toast("Copied"))}>Copy</button></li>
        <li>Or on the phone just open: <a href={nt.app_link}>{nt.app_link}</a></li>
        <li>Press <b>Send test</b> below.</li></ol></div>
      <p className="small muted">Keep the topic secret - anyone who knows it can read your notifications. "New topic" makes a new one (subscribe again on the phone).</p></>}
    <div className="row"><button className="btn primary" onClick={save}>Save</button>{nt.has_topic && <><button className="btn" onClick={test}>Send test</button><button className="btn" onClick={fresh}>New topic</button></>}</div>
  </div>);
}

/* ---------------- Discord bot */
export function DiscordBot() {
  const [keepOpen, setKeepOpen] = useState(false);
  const [b, again, v, err] = useLoad("/api/discordbot");
  if (err && !b) return <div className="card" style={{ margin: "0 0 16px" }}><Failed title="Discord bot" err={err} retry={again} /></div>;
  if (!b) return <SkelCard style={{ margin: "0 0 16px" }} />;
  const pill = !b.enabled ? <span className="badge">Off</span> : !b.has_token ? <span className="badge warn">No token yet</span> : b.state === "online" ? <span className="badge good">{"Online" + (b.bot_name ? " as " + b.bot_name : "")}</span>
    : b.state === "error" ? <span className="badge bad">Problem</span> : <span className="badge warn">Connecting…</span>;
  const g = b.guilds.find(x => x.id === b.guild);
  const refresh = () => { setKeepOpen(true); again(); };
  const save = async () => {
    const body = { enabled: chk("bot_on"), users: val("bot_users"), status_msg: chk("bot_status"), bridge: chk("bot_bridge") };
    if ($("bot_bserver")) body.bridge_server = val("bot_bserver");
    const t = val("bot_token").trim(); if (t) body.token = t;
    if ($("bot_guild")) body.guild = val("bot_guild");
    try { await L.api("/api/discordbot", { json: body }); L.toast(body.enabled ? "Saved - connecting to Discord…" : "Saved"); setTimeout(refresh, body.enabled ? 4000 : 0); }
    catch (e) { L.toast(e.message, 6000); }
  };
  return (<div className="card" style={{ margin: "0 0 16px" }} key={v}><h2>Discord bot {pill}</h2>
    <p className="small muted">Control your servers from Discord with slash commands. Anyone in your Discord can use <b>/status</b> (players, map, CPU, memory), <b>/top</b> (who played most) and <b>/events</b>. <b>/start</b>, <b>/stop</b>, <b>/restart</b> and <b>/whitelist</b> (add, remove, list, on, off) only work for people with <b>Manage Server</b> in your Discord, or the people you list below. A server has to be started from the dashboard once (to check its settings) before Discord can start it.</p>
    {b.error && b.enabled && <div className="issue error"><span className="ic">✕</span><span>{b.error}</span></div>}
    <details style={{ margin: "8px 0" }} open={!(b.has_token && !keepOpen)}><summary className="small"><b>How to set it up (5 minutes)</b></summary><ol className="small">
      <li>Open <a href="https://discord.com/developers/applications" {...NEW_TAB}>discord.com/developers/applications</a> → <b>New Application</b> → give it a name (for example "BeamMP server").</li>
      <li>Open <b>Bot</b> on the left → <b>Reset Token</b> → <b>Copy</b>. On the same page turn <b>Public Bot</b> off, so only you can add it to a Discord server.</li>
      <li>Paste the token below, turn the bot on and press Save.</li>
      <li>When it says <b>Online</b>, click <b>Add the bot to your Discord</b> and pick your Discord server.</li>
      <li>Type <b>/status</b> in any channel. (New commands can take a minute to show up - restart Discord if they don't.)</li></ol></details>
    <Toggle id="bot_on" on={b.enabled} title="Turn on the Discord bot">Off by default. The bot connects out to Discord - no port forwarding needed</Toggle>
    <label className="f" style={{ marginTop: 10 }}><span>Bot token</span><input type="password" id="bot_token" placeholder={b.has_token ? "Saved (encrypted) - paste a new one to replace" : "Paste the bot token"} autoComplete="off" spellCheck={false} /><small>Keep it secret - anyone with the token can control the bot. Stored encrypted.</small></label>
    {b.invite && <p><a className="btn sm" href={b.invite} {...NEW_TAB}>Add the bot to your Discord</a></p>}
    {b.guilds.length ? <label className="f"><span>Discord server the bot answers in</span><select id="bot_guild" defaultValue={b.guild || ""}><option value="">- pick one -</option>{b.guilds.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select><small>Commands only appear and only work there. If someone else adds your bot to another Discord, it ignores them.</small></label>
      : b.enabled && b.state === "online" ? <p className="small muted">The bot isn't in any Discord server yet - use the button above.</p> : null}
    {b.guild && !g && b.guilds.length > 0 && <p className="small" style={{ color: "var(--warn-ink)" }}>The bot is no longer in the Discord server it was set up for - pick another one.</p>}
    <label className="f"><span>Also allow these people to start/stop (optional)</span><textarea id="bot_users" rows={2} spellCheck={false} placeholder="123456789012345678" style={{ minHeight: 60 }} defaultValue={b.users.join("\n")} /><small>Discord user IDs, one per line. In Discord: Settings → Advanced → Developer Mode, then right-click a person → Copy User ID. People with Manage Server can always use the commands.</small></label>
    <h3 style={{ margin: "16px 0 4px" }}>In your Discord channel</h3>
    <p className="small muted">These use the channel of your Discord webhook (Settings → Notifications).{!b.has_webhook && <> <b>Add the webhook first.</b></>}</p>
    <Toggle id="bot_status" on={b.status_msg} title="Live status message">One message that shows every server, its players, CPU and memory and the next events - updated every minute. Pin it in the channel. Works without the bot</Toggle>
    <Toggle id="bot_bridge" on={b.bridge} title="Chat bridge">The game chat shows up in the channel, and messages written there appear in the game as [Discord] name: text. Needs the bot, and MESSAGE CONTENT INTENT turned on (Developer Portal → Bot). Commands, muted players and filtered words are never sent</Toggle>
    {b.servers.length > 1 && <label className="f"><span>Bridge which server</span><select id="bot_bserver" style={{ maxWidth: 260 }} defaultValue={b.bridge_server}>{b.servers.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>}
    <div className="row"><button className="btn primary" onClick={save}>Save</button><button className="btn" onClick={refresh}>Refresh</button></div>
  </div>);
}

/* ---------------- Telegram, Slack & other apps */
export function Integrations() {
  const [d, again, v, err] = useLoad("/api/integrations");
  const T_ = "Telegram, Slack & other apps";
  if (err && !d) return <div className="card" style={{ margin: "0 0 16px" }}><Failed title={T_} err={err} retry={again} /></div>;
  if (!d) return <SkelCard style={{ margin: "0 0 16px" }} />;
  const T = d.telegram, W = d.webhook;
  const send = async (body, re = true) => { try { const r = await L.api("/api/integrations", { json: body }); L.toast(r.note, 6000); if (re) again(); } catch (e) { L.toast(e.message, 8000); } };
  const tgSave = () => { const b = { telegram_enabled: chk("tg_on"), telegram_chat: val("tg_chat") }; if (val("tg_token").trim()) b.telegram_token = val("tg_token").trim(); send(b); };
  const whSave = () => { const b = { webhook_enabled: chk("wh_on") }; if (val("wh_url").trim()) b.webhook_url = val("wh_url").trim(); send(b); };
  return (<div className="card" style={{ margin: "0 0 16px" }} key={v}><h2>{T_}</h2>
    <p className="small muted">The same alerts as Discord and email (the switches under Notifications decide which), sent to more places. Security alerts always go to every channel that is set up.</p>
    <div className="grid g2" style={{ gap: 16 }}>
      <div><h3 style={{ margin: "0 0 6px", fontSize: 15 }}>Telegram</h3>
        <ol className="small muted" style={{ margin: "0 0 8px", paddingLeft: 18 }}><li>In Telegram, open <b>@BotFather</b>, send <Mono>/newbot</Mono> and copy the token.</li><li>Paste it below and save.</li><li>Send your new bot a message (or add it to a group), then click <b>Find my chat</b>.</li></ol>
        <label className="f"><span>Bot token</span><input type="password" id="tg_token" autoComplete="off" placeholder={T.has_token ? "Saved (encrypted) - paste a new one to replace" : "123456789:ABC…"} /></label>
        <label className="f"><span>Chat ID</span><div className="row" style={{ gap: 6 }}><input type="text" id="tg_chat" defaultValue={T.chat} placeholder="found automatically" /><button className="btn sm" disabled={!T.has_token} onClick={() => send({ telegram_find: true })}>Find my chat</button></div></label>
        <label className="toggle"><input type="checkbox" id="tg_on" defaultChecked={!!T.enabled} /><span><b>Send alerts to Telegram</b></span></label>
        <div className="row" style={{ gap: 6 }}><button className="btn sm primary" onClick={tgSave}>Save</button><button className="btn sm" disabled={!(T.has_token && T.chat)} onClick={() => send({ test: "telegram" }, false)}>Send test</button>
          {T.has_token && <button className="btn sm" onClick={() => confirm("Remove the Telegram bot token?") && send({ telegram_token: "" })}>Remove</button>}</div></div>
      <div><h3 style={{ margin: "0 0 6px", fontSize: 15 }}>Any app with a webhook</h3>
        <p className="small muted" style={{ margin: "0 0 8px" }}>Slack, Mattermost, Rocket.Chat, Google Chat, Microsoft Teams (Workflows), Home Assistant, n8n, Zapier… Paste the incoming-webhook address the app gives you.</p>
        <label className="f"><span>Webhook address</span><input type="password" id="wh_url" autoComplete="off" placeholder={W.has_url ? `Saved: ${W.host} - paste a new one to replace` : "https://hooks.slack.com/services/…"} /></label>
        <label className="toggle"><input type="checkbox" id="wh_on" defaultChecked={!!W.enabled} /><span><b>Send alerts to the webhook</b></span></label>
        <div className="row" style={{ gap: 6 }}><button className="btn sm primary" onClick={whSave}>Save</button><button className="btn sm" disabled={!W.has_url} onClick={() => send({ test: "webhook" }, false)}>Send test</button>
          {W.has_url && <button className="btn sm" onClick={() => confirm("Remove the webhook?") && send({ webhook_url: "" })}>Remove</button>}</div></div>
    </div>
    <div style={{ borderTop: "1px solid var(--line)", marginTop: 14, paddingTop: 12 }}>
      <label className="toggle"><input type="checkbox" defaultChecked={!!d.event_ads} onChange={e => send({ event_ads: e.target.checked })} /><span><b>Advertise events automatically</b><small>{`Posts to ${d.discord ? "Discord" : "Discord (once the webhook is set)"}, Telegram and the webhook when you plan a new event and the day before it, and reminds players in the game chat every 30 minutes in the 3 hours before. Events are set up in Config → Events`}</small></span></label></div>
  </div>);
}

/* ---------------- public status page */
export function StatusPage() {
  const [d, again, v, err] = useLoad("/api/statuspage");
  if (err && !d) return <div className="card" style={{ margin: "0 0 16px" }}><Failed title="Public status page" err={err} retry={again} /></div>;
  if (!d) return <SkelCard style={{ margin: "0 0 16px" }} />;
  const P = d.preview;
  const save = () => {
    if (chk("sp_on") && !d.on && !confirm("Turn on the public status page? Anyone who can reach your dashboard address can see it without logging in.")) return;
    post("/api/statuspage", { on: chk("sp_on"), players: chk("sp_players"), mods: chk("sp_mods"), address: chk("sp_addr"), credit: chk("sp_credit"), title: val("sp_title"), about: val("sp_about"), discord: val("sp_discord") }, 6000, again);
  };
  return (<div className="card" style={{ margin: "0 0 16px" }} key={v}>
    <div className="row"><h2 style={{ margin: 0 }}>Public status page</h2><span className="spacer" /><Pill on={d.on}>{d.on ? "On" : "Off"}</Pill></div>
    <p className="small muted">A simple page anyone can open without logging in: is the server up, how many players, the map, how to join and how long the first join takes, the coming events, lap times, drift and championship standings, and the uptime of the last 30 days. No settings or admin buttons, and no address unless you turn it on below. Also as JSON for bots and websites (<Mono>/status.json</Mono>).</p>
    <label className="toggle"><input type="checkbox" id="sp_on" defaultChecked={!!d.on} /><span><b>Turn on the status page</b></span></label>
    <Toggle id="sp_players" on={d.players} title="Show the names of online players">Off = only the number</Toggle>
    <Toggle id="sp_mods" on={d.mods} title="Show the mods and the download size">So players know what they'll download before they launch the game</Toggle>
    <Toggle id="sp_addr" on={d.address} title="Show the address to join with">{d.relay ? "Your relay's address - your home IP stays hidden" : "BeamMP has no join links, so players copy the address into Direct Connect. This shows your home IP to anyone with the link - turn on Hide my IP first if that matters to you"}</Toggle>
    <Toggle id="sp_credit" on={d.credit} title={"\"Hosted with BeamMP EasyServer\" at the bottom"}>A small link, so players who want their own server can find it</Toggle>
    <label className="f"><span>Page title</span><input type="text" id="sp_title" maxLength={80} defaultValue={d.title} placeholder={P.title} /></label>
    <label className="f"><span>About your server (optional)</span><textarea id="sp_about" rows={3} maxLength={500} defaultValue={d.about} placeholder="Friendly drift and racing server. Race night every Friday at 20:00!" /></label>
    <label className="f"><span>Discord invite link (optional)</span><input type="text" id="sp_discord" maxLength={80} defaultValue={d.discord} placeholder="https://discord.gg/abc123" /><small className="muted">Shows a Join our Discord button. Shared links show the title, players and map as a preview.</small></label>
    {d.on && <p className="small">On your network: <a href={d.lan_url} target="_blank" rel="noopener">{d.lan_url}</a>{d.remote ? <><br />On the internet: <a href={d.url} target="_blank" rel="noopener">{d.url}</a></>
      : <><br /><span className="muted">Players outside your network can only open it once internet access to the dashboard is on (Network). Or share the Discord status message instead.</span></>}</p>}
    <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>{P.servers.map((x, i) => <span key={i} className="badge">{`${x.name}: ${x.state}` + (x.history.d30 != null ? ` · ${x.history.d30}% (30 d)` : "")}</span>)}</div>
    <div className="row" style={{ marginTop: 10 }}><button className="btn sm primary" onClick={save}>Save</button></div>
  </div>);
}

/* ---------------- remembered devices */
export function Devices({ tick }) {
  const [d, again, v, err] = useLoad("/api/devices", [tick]);
  if (err && !d) return <div className="card" style={{ marginTop: 16 }}><Failed title="Remembered devices" err={err} retry={again} /></div>;
  if (!d) return <SkelCard style={{ marginTop: 16 }} />;
  const owner = S().SESSION.role === "owner";
  const call = async body => { try { await L.api("/api/devices", { json: body }); L.toast("Forgotten"); again(); } catch (e) { L.toast(e.message); } };
  return (<div className="card" style={{ marginTop: 16 }} key={v}><h2>Remembered devices</h2>
    <p className="small muted">{`Phones and browsers where "Stay logged in" was turned on. They log in by themselves for ${d.days} days after the last visit. Forget a device you lost or don't recognise - changing the password forgets all of them.`}</p>
    {d.devices.length ? <><table><tbody>{d.devices.map(x => <tr key={x.id}>
      <td>{x.name || "Browser"}{x.this && <> <span className="pill good">this device</span></>}{owner && x.user !== "owner" && <> <span className="muted small">{"· " + x.user}</span></>}</td>
      <td className="small muted">{L.ago(x.last)}<br />{x.ip}</td><td className="small muted">{"since " + L.fmtTime(x.created)}</td>
      <td className="num"><button className="btn sm" onClick={() => call({ action: "forget", id: x.id })}>Forget</button></td></tr>)}</tbody></table>
      <div className="row" style={{ marginTop: 10 }}><button className="btn sm danger" onClick={() => { if (confirm("Forget every remembered device? They'll have to log in again.")) call({ action: "forget_all" }); }}>Forget all</button></div></>
      : <p className="small muted">None yet.</p>}
  </div>);
}

/* ---------------- users & roles (owner only) */
const RL = { admin: "Admin - everything except accounts, passwords, internet access and plugins", moderator: "Moderator - players: kick, mute, ban, allow-list, chat, start/restart", viewer: "Viewer - can look, can't change anything" };
function UserServers({ u, d, allRoles, rname, onSave, onClose }) {
  const [all, setAll] = useState(u.servers === "all");
  const save = () => {
    const map = {}; document.querySelectorAll("[data-sv]").forEach(s => { if (s.value) map[s.dataset.sv] = s.value; });
    onClose(); onSave(all ? "all" : map);
  };
  return (<Modal onClose={onClose}><h2 style={{ marginTop: 0 }}>{`Servers for ${u.name}`}</h2>
    <label className="toggle"><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)} /><span><b>All servers, same role</b><small>{`${rname(u.role)} everywhere - change it in the list`}</small></span></label>
    <div style={{ opacity: all ? .4 : 1 }}>{d.servers.map(s => <div key={s.id} className="row small" style={{ gap: 8, padding: "4px 0" }}><b style={{ minWidth: 140 }}>{s.name}</b>
      <select data-sv={s.id} style={{ width: "auto" }} defaultValue={u.servers === "all" ? "" : (u.servers[s.id] || "")}><option value="">No access</option>{allRoles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></div>)}</div>
    <p className="small muted">With only some servers, the account can't change dashboard-wide settings.</p>
    <div className="row"><button className="btn primary" onClick={save}>Save</button><button className="btn" onClick={onClose}>Cancel</button></div>
  </Modal>);
}
export function Users() {
  const [d, again, v, err] = useLoad("/api/users");
  const [srvFor, setSrvFor] = useState(null), [invite, setInvite] = useState(null);
  if (err && !d) return <div className="card" style={{ margin: "0 0 16px" }}><Failed title="Users & roles" err={err} retry={again} /></div>;
  if (!d) return <SkelCard style={{ margin: "0 0 16px" }} />;
  const allRoles = [...d.roles.map(r => ({ id: r, name: r })), ...d.custom_roles.map(r => ({ id: r.id, name: r.name }))];
  const rname = id => (allRoles.find(r => r.id === id) || { name: "deleted role" }).name;
  const RoleSel = props => <select style={{ width: "auto" }} {...props}>{allRoles.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select>;
  const many = d.servers.length > 1;
  const svName = sid => (d.servers.find(s => s.id === sid) || { name: sid }).name;
  const svText = u => u.servers === "all" ? (many ? "all servers" : "") : Object.entries(u.servers).map(([sid, r]) => `${svName(sid)}: ${rname(r)}`).join(", ");
  const call = async (body, msg) => { try { const r = await L.api("/api/users", { json: body }); again(); L.toast(r.note || msg || "Saved", 8000); } catch (e) { L.toast(e.message, 6000); } };
  const roleCall = async body => { try { await L.api("/api/roles", { json: body }); again(); L.toast("Saved"); } catch (e) { L.toast(e.message, 7000); } };
  const makeInvite = async () => {
    const srv = $("iv_srv") ? val("iv_srv") : "all", role = val("iv_role");
    try { setInvite(await L.api("/api/teaminvite", { json: { role, servers: srv === "all" ? "all" : { [srv]: role }, remote: chk("iv_remote") } })); } catch (e) { L.toast(e.message, 6000); }
  };
  const discordLogin = async e => { const on = e.target.checked; try { await L.api("/api/discordlogin", { json: { on } }); L.toast(on ? "Discord sign-in is on" : "Discord sign-in is off"); } catch (x) { L.toast(x.message, 7000); again(); } };
  const saveRole = id => { const c = document.querySelector(`[data-crole="${CSS.escape(id)}"]`); roleCall({ action: "save", id, name: c.querySelector('[data-k="name"]').value, perms: [...c.querySelectorAll("[data-perm]:checked")].map(x => x.dataset.perm) }); };
  return (<div className="card" style={{ margin: "0 0 16px" }} key={v}><h2>Users &amp; roles</h2>
    <p className="small muted">Give friends their own login with only the rights they need. You (the owner) log in with the main password and an empty name. Everything they do shows up in Logs → Activity log.</p>
    {d.users.length ? d.users.map(u => <div key={u.name} className="small" style={{ padding: "8px 0", borderTop: "1px solid var(--line)" }}>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}><b>{u.name}</b>{u.disabled && <span className="badge warn">disabled</span>}{u.totp && <span className="badge good">two-step on</span>}
        {u.remote && <span className={"badge " + (u.totp ? "good" : "warn")}>{u.totp ? "can log in from the internet" : "internet: needs two-step"}</span>}{u.discord && <span className="badge">{`Discord: ${u.discord}`}</span>}
        {u.servers === "all" ? <RoleSel defaultValue={u.role} onChange={e => call({ action: "role", name: u.name, role: e.target.value })} /> : <span className="muted">{svText(u)}</span>}
        <span className="muted">{(u.last_login ? `last login ${L.ago(u.last_login)}` : "never logged in") + (u.invited_by ? " · invited" : "")}</span><span className="spacer" /></div>
      <div className="row" style={{ gap: 6, flexWrap: "wrap", marginTop: 6 }}>{many && <button className="btn sm" onClick={() => setSrvFor(u)}>Servers…</button>}
        <label className="small" style={{ display: "flex", gap: 4, alignItems: "center" }}><input type="checkbox" defaultChecked={!!u.remote} onChange={e => call({ action: "remote", name: u.name, remote: e.target.checked })} /> From the internet</label>
        {u.totp && <button className="btn sm" onClick={() => { if (confirm("Turn off two-step login for " + u.name + "? They'll be logged out and can set it up again (at home).")) call({ action: "reset_2fa", name: u.name }); }}>Reset two-step</button>}
        {u.discord && <button className="btn sm" onClick={() => { if (confirm("Unlink Discord from " + u.name + "? They'll be logged out.")) call({ action: "discord_unlink", name: u.name }); }}>Unlink Discord</button>}
        <button className="btn sm" onClick={() => { const pw = prompt("New password for " + u.name + " (at least 10 characters):"); if (pw) call({ action: "password", name: u.name, password: pw }); }}>New password</button>
        <button className="btn sm" onClick={() => call({ action: "disable", name: u.name })}>{u.disabled ? "Enable" : "Disable"}</button>
        <button className="btn sm danger" onClick={() => { if (confirm("Delete the account " + u.name + "?")) call({ action: "delete", name: u.name }); }}>Delete</button></div></div>)
      : <p className="small muted">No extra accounts yet.</p>}
    {d.discord_login.available && <label className="toggle" style={{ marginTop: 12 }}><input type="checkbox" defaultChecked={!!d.discord_login.on} onChange={discordLogin} /><span><b>Let team members sign in with Discord</b><small>They link their Discord once under My account, then sign in with one click instead of typing a password. Two-step login and the internet rules stay the same. You (the owner) always use your password. It goes through a small EasyServer sign-in service, which stores nothing.</small></span></label>}
    <h3 style={{ marginTop: 16 }}>Invite someone</h3>
    <p className="small muted">{`Easiest: send a link. They pick their own name and password${d.remote_enabled ? " (and set up two-step login if they may log in from the internet)" : ""} - you never handle their password. The link works once and stops working after 1 hour, so send it right away.`}</p>
    <div className="row" style={{ gap: 8, flexWrap: "wrap" }}><label className="small">Role <RoleSel id="iv_role" defaultValue="moderator" /></label>
      {many && <label className="small">Servers <select id="iv_srv" style={{ width: "auto" }}><option value="all">All servers</option>{d.servers.map(s => <option key={s.id} value={s.id}>{`Only ${s.name}`}</option>)}</select></label>}
      <label className="small" style={{ display: "flex", gap: 4, alignItems: "center" }}><input type="checkbox" id="iv_remote" disabled={!d.remote_enabled} />{d.remote_enabled ? " May log in from the internet" : " May log in from the internet (turn on Internet access first)"}</label>
      <button className="btn sm primary" onClick={makeInvite}>Make invite link</button></div>
    {invite && <div className="card tight" style={{ padding: "10px 12px", marginTop: 8 }}><div className="small">{invite.note}</div><textarea readOnly rows={2} className="mono" style={{ marginTop: 6 }} value={invite.link} />
      <div className="row" style={{ marginTop: 6 }}><button className="btn sm primary" onClick={async () => L.toast(await L.copyText(invite.link) ? "Link copied" : "Select the link and press Ctrl+C")}>Copy link</button>
        {invite.internet_link && invite.link !== invite.internet_link && <span className="small muted">Home network link. They need to be on your Wi-Fi to use it.</span>}</div></div>}
    {d.invites.length > 0 && <div className="small" style={{ marginTop: 8 }}>{d.invites.map(x => <div key={x.id} className="row" style={{ gap: 8, padding: "4px 0" }}>Open invite: <b>{rname(x.role)}</b>
      {(x.servers ? " · " + Object.keys(x.servers).map(svName).join(", ") : "") + (x.remote ? " · internet" : "")} <span className="muted">{`until ${L.fmtTime(x.expires)}`}</span><span className="spacer" />
      <button className="btn sm" onClick={async () => { try { await L.api("/api/teaminvite", { json: { action: "revoke", id: x.id } }); again(); } catch (e) { L.toast(e.message); } }}>Revoke</button></div>)}</div>}
    <details style={{ marginTop: 12 }}><summary className="small">Or add an account yourself (you set the password)</summary>
      <div className="grid g2" style={{ gap: "0 12px", marginTop: 10 }}>
        <label className="f"><span>Name</span><input id="nu_name" maxLength={24} autoComplete="off" spellCheck={false} placeholder="e.g. dani" /></label>
        <label className="f"><span>Role</span><RoleSel id="nu_role" defaultValue="moderator" /></label>
        <label className="f"><span>Password</span><input id="nu_pw" type="password" autoComplete="new-password" placeholder="at least 10 characters" /></label>
        <div className="small muted" style={{ alignSelf: "center" }}>{Object.entries(RL).map(([k, t]) => <div key={k}>{t}</div>)}</div></div>
      <button className="btn" onClick={() => call({ action: "add", name: val("nu_name").trim(), role: val("nu_role"), password: val("nu_pw") })}>Add account</button></details>
    <h3 style={{ marginTop: 16 }}>Custom roles</h3>
    <p className="small muted">Make your own role by ticking what it may do, e.g. "Map master": maps &amp; events plus mods, but no banning.</p>
    {d.custom_roles.map(r => <div key={r.id} className="card tight" style={{ padding: "10px 12px", marginTop: 8 }} data-crole={r.id}>
      <div className="row"><input type="text" data-k="name" defaultValue={r.name} maxLength={40} style={{ maxWidth: 220 }} /><span className="spacer" />
        <button className="btn sm" onClick={() => saveRole(r.id)}>Save</button><button className="btn sm danger" onClick={() => { if (confirm("Delete this role?")) roleCall({ action: "delete", id: r.id }); }}>Delete</button></div>
      <div className="row small" style={{ flexWrap: "wrap", gap: 10, marginTop: 6 }}>{d.perm_groups.map(g => <label key={g.id} title={g.about} style={{ display: "flex", gap: 4, alignItems: "center" }}><input type="checkbox" data-perm={g.id} defaultChecked={r.perms.includes(g.id)} /> {g.name}</label>)}</div></div>)}
    <div className="row" style={{ marginTop: 8, gap: 8 }}><input type="text" id="cr_name" maxLength={40} placeholder="New role name" style={{ maxWidth: 220 }} /><button className="btn sm" onClick={() => roleCall({ action: "save", name: val("cr_name"), perms: ["map"] })}>Add role</button></div>
    <p className="small muted">{"Every role can look at everything. Only you can manage accounts, passwords, internet access and server plugins. "}{d.perm_groups.map((g, i) => <span key={g.id}>{i > 0 && " · "}<b>{g.name}</b>{": " + g.about}</span>)}</p>
    {srvFor && <UserServers u={srvFor} d={d} allRoles={allRoles} rname={rname} onClose={() => setSrvFor(null)} onSave={servers => call({ action: "servers", name: srvFor.name, servers })} />}
  </div>);
}

/* ---------------- backups, DuckDNS, computer load */
function LoadGraphs({ upMbit }) {
  const [r, setR] = useState(null);
  useEffect(() => { L.api("/api/resources?n=1440").then(setR, () => {}); }, []);
  if (!r) return <div style={{ margin: "8px 0 12px" }} />;
  const h = r.history || [];
  if (h.length < 3) return <div style={{ margin: "8px 0 12px" }}><p className="small muted">Graphs appear after a few minutes - one point per minute, last 24 hours (kept while the dashboard runs).</p></div>;
  const W = 560, H = 90, t0 = h[0].t, t1 = h[h.length - 1].t || t0 + 1;
  const Chart = ({ title, k, max, fmt, note }) => {
    const pts = h.filter(p => p[k] != null);
    if (!pts.length) return null;
    const top = Math.max(max || 0, ...pts.map(p => p[k])) || 1;
    const xy = p => [((p.t - t0) / Math.max(1, t1 - t0)) * W, H - (p[k] / top) * (H - 6) - 2];
    const line = pts.map(p => xy(p).map(n => n.toFixed(1)).join(",")).join(" ");
    return (<div className="card tight" style={{ padding: "10px 12px" }}><div className="row small"><b>{title}</b><span className="spacer" /><span>{"now " + fmt(pts[pts.length - 1][k])}</span></div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: 70, display: "block", marginTop: 4 }} role="img" aria-label={`${title} over the last ${Math.round((t1 - t0) / 3600) || 1} hours`}>
        <line x1={0} y1={H - 1} x2={W} y2={H - 1} stroke="currentColor" strokeOpacity=".15" />
        <polyline points={line} fill="none" stroke="var(--accent)" strokeWidth={2} vectorEffect="non-scaling-stroke" strokeLinejoin="round" /></svg>
      <div className="row small muted"><span>{L.fmtTime(t0)}</span><span className="spacer" /><span>{note || "max " + fmt(top)}</span></div></div>);
  };
  const mb = v => L.fmtSize(v * 1048576);
  const up = k => k >= 1000 ? (k / 1000).toFixed(1) + " Mbit/s" : Math.round(k) + " kbit/s";
  return (<div style={{ margin: "8px 0 12px" }}><div className="grid g2" style={{ gap: 10 }}>
    <Chart title="Processor" k="cpu" max={100} fmt={v => Math.round(v) + "%"} note="0-100%" />
    <Chart title="Free memory" k="mem_free" max={0} fmt={mb} />
    <Chart title="Upload" k="up_kbps" max={upMbit ? upMbit * 1000 : 0} fmt={up} note={upMbit ? `line top = your ${upMbit} Mbit/s` : ""} />
    <Chart title="Players online" k="players" max={1} fmt={v => String(v)} /></div></div>);
}
function BackupCopy({ bk, again }) {
  const [kind, setKind] = useState(bk.copy || "");
  const [path, setPath] = useState(bk.copy_path || "");
  const [ip, setIp] = useState(bk.copy_ip || (bk.computers[0] || {}).ip || "");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try { const r = await L.api("/api/backups", { json: { copy: kind, copy_path: path, copy_ip: ip } }); L.toast(r.note); again(); }
    catch (e) { L.toast(e.message, 9000); }
    setBusy(false);
  };
  const last = bk.copy_last;
  return <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--line)" }}>
    <b>{"Keep a copy somewhere else"}</b>
    <p className="small muted" style={{ margin: "4px 0 8px" }}>{`If this computer's disk dies, the backups on it are gone too. After every backup a copy goes to a USB drive or another computer at home, and the last ${bk.keep} are kept there.`}</p>
    <label className="f"><span>{"Copy to"}</span><select value={kind} onChange={e => setKind(e.target.value)}>
      <option value="">{"Nowhere - only this computer"}</option>
      <option value="folder">{"A USB drive or folder"}</option>
      {(bk.computers.length > 0 || kind === "computer") && <option value="computer">{"Another computer at home"}</option>}</select></label>
    {kind === "folder" && <>
      <label className="f"><span>{"Folder"}</span><input type="text" value={path} onChange={e => setPath(e.target.value)} placeholder={bk.folder.includes("\\") ? "E:\\" : "/media/usb"} spellCheck={false} autoComplete="off" />
        <small>{`A "${bk.copy_dir}" folder is made in it.`}</small></label>
      {bk.drives.length > 0 && <div className="row small" style={{ gap: 6, flexWrap: "wrap", margin: "-4px 0 10px" }}>
        <span className="muted">{"Drives:"}</span>{bk.drives.map(x => <button key={x.path} className="btn sm ghost" onClick={() => setPath(x.path)}>{x.usb ? `${x.path} (USB)` : x.path}</button>)}</div>}</>}
    {kind === "computer" && <label className="f"><span>{"Computer"}</span><select value={ip} onChange={e => setIp(e.target.value)}>
      {bk.computers.map(c => <option key={c.ip} value={c.ip}>{`${c.name} (${c.ip})`}</option>)}</select>
      <small>{"Saved in the easyserver-backups folder of the user it was set up with. Set computers up under Servers → Other computers at home."}</small></label>}
    <button className="btn" disabled={busy} onClick={save}>{"Save"}</button>
    {last && <p className="small" style={{ marginTop: 8, color: last.ok ? "var(--good-ink)" : "var(--warning)" }}>{`${last.ok ? "Last copy" : "The last copy failed"} (${L.fmtTime(last.t)}): ${last.note}`}</p>}
  </div>;
}

/* ---------------- Google Drive copies + rescue */
function GoogleDrive() {
  const [d, setD] = useState(null), [err, setErr] = useState(""), [busy, setBusy] = useState(""), [tick, setTick] = useState(0);
  const load = () => L.api("/api/gdrive?details=1").then(x => { setD(x); setErr(""); }).catch(e => setErr(e.message));
  useEffect(() => { load(); }, [tick]);
  const waiting = d && d.flow && d.flow.state === "waiting";
  useEffect(() => {
    if (!waiting) return;
    const t = setInterval(() => L.api("/api/gdrive").then(x => { if (!x.flow || x.flow.state !== "waiting") setTick(n => n + 1); else setD(o => ({ ...o, flow: x.flow })); }).catch(() => {}), 3000);
    return () => clearInterval(t);
  }, [waiting]);
  if (!d) return err ? <Oops err={err} retry={load} style={{ marginTop: 16 }} /> : <SkelCard lines={3} style={{ marginTop: 16 }} />;
  const act = async (action, extra, msg) => {
    if (msg && !confirm(msg)) return;
    setBusy(action);
    try { const r = await L.api("/api/gdrive", { json: { action, ...extra } }); if (r.note) L.toast(r.note, 8000); if (r.flow) setD(o => ({ ...o, flow: r.flow })); else setTick(n => n + 1); }
    catch (e) { L.toast(e.message, 9000); }
    setBusy("");
  };
  const est = d.estimate, dr = d.drive, f = d.flow;
  const tooBig = dr && dr.free != null && est.known && est.total - (d.used_by_us || 0) > dr.free;
  const restore = x => {
    const from = x.computer === d.computer ? "" : ` (from the computer ${x.computer})`;
    if (!confirm(`Restore the backup from ${L.fmtTime(x.t)}${from} onto this server? Its config, allow-list, bans, moderation, messages and game records go back to how they were then. How things are right now is saved as a backup first.`)) return;
    const mods = x.mods && confirm(["This backup has the mods in it too. Put those mods back as well?", "", "OK = settings and mods, Cancel = only the settings."].join("\n"));
    act("restore", { id: x.id, mods });
  };
  const useText = est.known ? `About ${L.fmtSize(est.total)} of your Google Drive: the last ${est.keep} nightly backups, ${L.fmtSize(est.per_night)} each. Older ones are deleted by themselves.`
    : `It keeps the last ${est.keep} nightly backups there. They're usually small (settings only) - the exact size shows after the first backup.`;
  return (<div className="card" style={{ marginTop: 16 }}>
    <div className="row"><h2 style={{ margin: 0 }}>Google Drive</h2><span className="spacer" /><Pill on={d.connected && d.on}>{d.connected ? (d.on ? "Copying nightly" : "Paused") : "Not connected"}</Pill></div>
    <p className="small muted">{"A copy of every nightly backup in your own Google Drive, so nothing is lost even if this computer breaks or is stolen. On a new computer, connect the same Google account and press Restore - your server is back as it was. EasyServer only sees the files it makes itself, nothing else in your Drive. Keys and passwords are never in a backup."}</p>
    {!d.connected && <p className="small"><b>{"Space it needs: "}</b>{useText}{" A free Google account has 15 GB."}</p>}
    {!d.backups_on && <Warn>{"Nightly backups are off - turn them on above, otherwise nothing new goes to the Drive."}</Warn>}
    {d.connected ? <>
      <p className="small" style={{ margin: "6px 0" }}>{"Connected to "}<b>{d.account || "your Google account"}</b>{` · folder "${d.folder}"`}</p>
      {dr && <div style={{ margin: "8px 0" }}>
        <div className="row small"><span>{`EasyServer's copies use ${L.fmtSize(d.used_by_us || 0)}${est.known ? ` (about ${L.fmtSize(est.total)} once ${est.keep} are kept)` : ""}`}</span><span className="spacer" />
          {dr.limit ? <span className={tooBig ? "" : "muted"} style={tooBig ? { color: "var(--warn-ink)", fontWeight: 600 } : undefined}>{`${L.fmtSize(dr.free)} free of ${L.fmtSize(dr.limit)}`}</span> : <span className="muted">{"Unlimited storage"}</span>}</div>
        {dr.limit ? <div className="bar" role="img" aria-label={`Google Drive: ${L.fmtSize(dr.used)} used of ${L.fmtSize(dr.limit)}`}><i style={{ width: Math.min(100, Math.round(dr.used / dr.limit * 100)) + "%", ...(tooBig ? { background: "var(--warning)" } : {}) }} /></div> : null}
        {tooBig && <Warn>{"Your Drive is almost full - the next copies may not fit. Free up space in Google Drive or turn off Include the mods."}</Warn>}</div>}
      {d.error && <Warn>{d.error}</Warn>}
      <label className="toggle"><input type="checkbox" checked={d.on} disabled={busy === "on"} onChange={e => act("on", { on: e.target.checked })} /><span><b>{"Copy every nightly backup to Google Drive"}</b><small>{`The last ${est.keep} of each server are kept there`}</small></span></label>
      {d.last && <p className="small" style={{ marginTop: 4, color: d.last.ok ? "var(--good-ink)" : "var(--warning)" }}>{`${d.last.ok ? "Last copy" : "The last copy failed"} (${L.fmtTime(d.last.t)}): ${d.last.note}`}</p>}
      <div className="row" style={{ gap: 8 }}><button className="btn" disabled={busy === "now"} onClick={() => act("now")}>{"Copy now"}</button>
        <button className="btn ghost" disabled={busy === "disconnect"} onClick={() => act("disconnect", {}, "Disconnect Google Drive? No more copies go there. The copies already in your Drive stay - delete the folder there if you don't want them.")}>{"Disconnect"}</button></div>
      {d.files.length > 0 && <details style={{ marginTop: 12 }}><summary className="small"><b>{`Backups in your Drive (${d.files.length})`}</b>{" - restore one onto this server"}</summary>
        {d.files.map(x => <div key={x.id} className="row small" style={{ padding: "3px 0" }}><span>{L.fmtTime(x.t) + (x.computer !== d.computer ? ` · from ${x.computer}` : "") + ` · server ${x.server}` + (x.mods ? " · with mods" : "") + " · " + L.fmtSize(x.size)}</span><span className="spacer" />
          <button className="btn sm" disabled={busy === "restore"} onClick={() => restore(x)}>{"Restore"}</button></div>)}</details>}
    </> : f && f.state === "waiting" ? <div className="card tight" style={{ padding: "14px 16px", margin: "8px 0" }}>
      <div className="small">{"1. Open "}<a href={f.url} {...NEW_TAB}><b>{f.url.replace(/^https:\/\//, "")}</b></a>{" on your phone or this computer"}</div>
      <div className="small" style={{ marginTop: 4 }}>{"2. Sign in to Google and type this code:"}</div>
      <div className="mono" style={{ fontSize: 28, fontWeight: 700, letterSpacing: 3, margin: "6px 0", userSelect: "all" }}>{f.code}</div>
      <div className="small">{"3. Press Allow. This page notices by itself."}</div>
      <div className="row small muted" style={{ marginTop: 8 }}><span>{`Waiting… the code works until ${L.fmtTime(f.until)}`}</span><span className="spacer" /><button className="btn sm ghost" onClick={() => act("cancel")}>{"Cancel"}</button></div>
    </div> : <>
      {f && f.state === "failed" && <Warn>{f.note}</Warn>}
      {d.ready ? <button className="btn primary" disabled={busy === "connect"} onClick={() => act("connect")}>{"Connect Google Drive"}</button>
        : <p className="small">{"Google Drive needs a one-time setup in this version: use your own Google app below (free, about 5 minutes)."}</p>}
    </>}
    <details style={{ marginTop: 12 }} open={!d.ready && !d.connected}><summary className="small muted">{d.own_app ? "Using your own Google app" : "Use your own Google app (advanced)"}</summary>
      <ol className="small" style={{ margin: "6px 0 10px" }}>
        <li>{"Open "}<a href="https://console.cloud.google.com/projectcreate" {...NEW_TAB}>{"console.cloud.google.com"}</a>{" and make a new project (any name)."}</li>
        <li>{"APIs & Services → Library: search for "}<b>{"Google Drive API"}</b>{" and press Enable."}</li>
        <li>{"Google Auth Platform → Branding: give the app a name and your email. Audience: pick External, then press "}<b>{"Publish app"}</b>{" - otherwise Google cuts the connection after 7 days."}</li>
        <li>{"Clients → Create client → type "}<b>{"TVs and Limited Input devices"}</b>{". Paste the Client ID and Client secret here."}</li></ol>
      <label className="f"><span>{"Client ID"}</span><input type="text" id="gd_cid" defaultValue={d.own_client_id} placeholder="1234567890-abc….apps.googleusercontent.com" autoComplete="off" spellCheck={false} /></label>
      <label className="f"><span>{"Client secret"}</span><input type="password" id="gd_sec" placeholder={d.own_app ? "Saved (encrypted) - paste a new one to replace" : "GOCSPX-…"} autoComplete="off" /></label>
      <button className="btn" disabled={busy === "own_app"} onClick={() => act("own_app", { client_id: val("gd_cid"), client_secret: val("gd_sec") }, d.connected ? "Switching the Google app disconnects Google Drive - you connect it again after. Go on?" : "")}>{"Save"}</button>
    </details>
  </div>);
}

export function Backups() {
  const [d, again, v, err] = useLoad(["/api/backups", "/api/settings", "/api/resources"]);
  const [busy, setBusy] = useState("");
  if (err && !d) return <Oops err={err} retry={again} style={{ marginTop: 16 }} />;
  if (!d) return <div className="grid g2" style={{ marginTop: 16 }}><SkelCard lines={5} /><SkelCard lines={5} /></div>;
  const [bk, st, rs] = d, n = rs.now || {}, owner = isOwner();
  const fmtUp = k => k == null ? "-" : k >= 1000 ? (k / 1000).toFixed(1) + " Mbit/s" : Math.round(k) + " kbit/s";
  const restore = async b => {
    const when = L.fmtTime(b.t);
    if (!confirm("Restore the backup from " + when + "? The server's config, allow-list, bans, moderation and messages go back to how they were then. How things are right now is saved as a backup first.")) return;
    const mods = !!b.mods && confirm("This backup has the mods in it too. Put those mods back as well?\n\nOK = settings and mods, Cancel = only the settings.");
    setBusy(b.file); L.toast("Restoring…", 20000);
    try { const r = await L.api("/api/backups/restore", { json: { file: b.file, mods } }); L.toast(r.note, 9000); again(); } catch (e) { L.toast(e.message, 8000); }
    setBusy("");
  };
  const now = async () => { setBusy("now"); try { const r = await L.api("/api/backups/now", { json: { mods: chk("bk_mods") } }); L.toast(r.note); again(); } catch (e) { L.toast(e.message, 6000); } setBusy(""); };
  const duck = async () => { setBusy("duck"); try { const r = await L.api("/api/duckdns", { json: { domain: val("dk_dom"), token: val("dk_tok") } }); L.toast(r.note, 7000); again(); } catch (e) { L.toast(e.message, 7000); } setBusy(""); };
  return (<div key={v}>
    <div className="grid g2" style={{ marginTop: 16 }}>
      <div className="card"><div className="row"><h2 style={{ margin: 0 }}>Automatic backups</h2><span className="spacer" /><Pill on={bk.on}>{bk.on ? "Nightly " + bk.at : "Off"}</Pill></div>
        <p className="small muted">{`Every night the settings of all servers (config, allow-list, bans, moderation, messages, rotation) are saved. The last ${bk.keep} are kept. ` + (owner ? "Click Restore to put one back - how things are right now is saved first, so you can undo it." : "The owner can restore one.")}</p>
        <Toggle id="bk_on" on={bk.on} title="Back up every night">On by default. Keys and passwords are never in a backup</Toggle>
        <Toggle id="bk_mods" on={bk.mods} title="Include the mods">Can use a lot of disk space</Toggle>
        <label className="f"><span>At</span><input type="time" id="bk_at" defaultValue={bk.at} style={{ maxWidth: 160, ...TIME }} /></label>
        <div className="row"><button className="btn primary" onClick={() => post("/api/backups", { on: chk("bk_on"), mods: chk("bk_mods"), at: val("bk_at") }, undefined, again)}>Save</button><button className="btn" disabled={busy === "now"} onClick={now}>Back up now</button></div>
        {bk.items.length ? <div style={{ marginTop: 10 }}>{bk.items.map(b => <div key={b.file} className="row small" style={{ padding: "3px 0" }}><span>{L.fmtTime(b.t) + (b.mods ? " · with mods" : "") + " · " + L.fmtSize(b.size)}</span><span className="spacer" />
          {owner && <button className="btn sm" disabled={busy === b.file} onClick={() => restore(b)}>Restore</button>}<a href={"/api/backups/download?file=" + encodeURIComponent(b.file) + "&srv=" + encodeURIComponent(S().SERVER)} download>Download</a></div>)}</div>
          : <p className="small muted" style={{ marginTop: 8 }}>No backups of this server yet.</p>}
        {owner && <BackupCopy bk={bk} again={again} />}
      </div>
      <div className="card"><div className="row"><h2 style={{ margin: 0 }}>Fixed address (DuckDNS)</h2><span className="spacer" /><span className={"pill " + (st.duckdns_domain ? (st.duck_err ? "warn" : "good") : "")}><span className="dot" />{st.duckdns_domain ? st.duckdns_domain + ".duckdns.org" : "Off"}</span></div>
        <p className="small muted">Most home internet gets a new IP address now and then, and your friends' saved address stops working. With a free DuckDNS name they always use <b>yourname.duckdns.org</b> - the dashboard keeps it pointing at your home.</p>
        {st.duck_err && <Warn>{`Last update failed: ${st.duck_err}`}</Warn>}
        <ol className="small" style={{ margin: "6px 0 10px" }}><li>Sign in at <a href="https://www.duckdns.org" {...NEW_TAB}>duckdns.org</a> (free, with Google, GitHub, Reddit...).</li><li>Type a name under "sub domain" and click <b>add domain</b>.</li><li>Copy the <b>token</b> from the top of the page and paste both below.</li></ol>
        <label className="f"><span>DuckDNS name</span><input type="text" id="dk_dom" defaultValue={st.duckdns_domain || ""} placeholder="myserver" autoComplete="off" spellCheck={false} /><small>Just the name - .duckdns.org is added. Empty + Save turns it off</small></label>
        <label className="f"><span>Token</span><input type="password" id="dk_tok" placeholder={st.has_duck ? "Saved (encrypted) - paste a new one to replace" : "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"} autoComplete="off" /></label>
        <button className="btn primary" disabled={busy === "duck"} onClick={duck}>Save</button>
        {st.duckdns_domain && <p className="small" style={{ marginTop: 8 }}>Friends join at <span className="mono">{`${st.duckdns_domain}.duckdns.org:${st.port_main || 30814}`}</span> (the game port still has to be forwarded on your router).</p>}
      </div>
    </div>
    {owner && <GoogleDrive />}
    <div className="card" style={{ marginTop: 16 }}><h2>Computer load</h2>
      <p className="small muted">You get a warning when this computer runs out of memory, the processor is maxed out for 5 minutes, or the server uses almost all of your upload - with a suggested player limit.</p>
      <div className="grid g3" style={{ gap: 10, margin: "8px 0" }}>
        <div className="card tight stat" style={{ padding: "10px 14px" }}><div className="label">Processor</div><div className="value">{n.cpu == null ? "-" : Math.round(n.cpu) + "%"}</div><div className="note">{`${rs.cpus} cores`}</div></div>
        <div className="card tight stat" style={{ padding: "10px 14px" }}><div className="label">Free memory</div><div className="value">{n.mem_free == null ? "-" : L.fmtSize(n.mem_free * 1048576)}</div><div className="note">{"of " + (n.mem_total == null ? "?" : L.fmtSize(n.mem_total * 1048576))}</div></div>
        <div className="card tight stat" style={{ padding: "10px 14px" }}><div className="label">Upload used</div><div className="value">{fmtUp(n.up_kbps)}</div><div className="note">{rs.upload_mbit ? `of ${rs.upload_mbit} Mbit/s` : "set your speed below"}</div></div>
      </div>
      <LoadGraphs upMbit={rs.upload_mbit} />
      <label className="f"><span>Your upload speed (Mbit/s)</span><div className="row"><input type="number" id="up_mbit" min={0} step={0.1} defaultValue={rs.upload_mbit || ""} placeholder="e.g. 20" style={{ maxWidth: 160 }} />
        <button className="btn" onClick={() => post("/api/resources", { upload_mbit: val("up_mbit") }, undefined, again)}>Save</button></div>
        <small>Run a speed test (for example speedtest.net) on this computer and enter the <b>upload</b> number. Without it you only get memory and processor warnings.</small></label>
    </div>
  </div>);
}
