import { useEffect, useMemo, useState } from "react";
import { ASK, Fold, Footer, GH, LATEST, Nav, textOf, useOpenSet } from "./shared.jsx";

const CATS = [
  ["start", "Getting started"],
  ["join", "Joining & network"],
  ["mods", "Mods & maps"],
  ["dash", "Dashboard & login"],
  ["discord", "Discord & alerts"],
  ["trouble", "Problems"],
];

// [id, category, question, answer, most asked]
const QA = [
  ["what-do-i-need", "start", "What do I need to host a server?", <>
    <ul><li>A computer that stays on while you play: any 64-bit Windows 10/11 PC, or Linux (Ubuntu, Linux Mint, Debian, also a Raspberry Pi 4/5 with a 64-bit system). An old laptop is fine for a group of friends.</li>
      <li>A free BeamMP <b>AuthKey</b> (see the next question).</li>
      <li>Your own copy of BeamNG.drive to play. The server itself is free.</li></ul>
    <p>Upload speed matters more than the processor: every player downloads your mods from you.</p></>],
  ["authkey", "start", "Where do I get the AuthKey?", <>
    <ol><li>Go to <a href="https://keymaster.beammp.com">keymaster.beammp.com</a> and log in with Discord.</li>
      <li>Click <b>Keys</b>, then <b>+</b>, and give it any name.</li>
      <li>Copy the key and paste it into the installer, or later under <b>Config → AuthKey</b>.</li></ol>
    <p>Without a key the server still works on your home network, it just isn't in the public server list. One key per public server.</p></>],
  ["windows-or-linux", "start", "Should I use Windows or Linux?", <>
    <p><b>Playing on the same PC you host on?</b> Windows is the easiest: download the zip, double-click <b>Install-BeamMP-Server.bat</b>.</p>
    <p><b>A spare computer just for the server?</b> Linux is better. The server runs in the background, starts by itself when the computer boots, restarts after a crash, and with <b>laptop mode</b> keeps running with the lid closed. One command installs everything.</p></>],
  ["update", "start", "How do I update EasyServer and the BeamMP server?", <>
    <ul><li><b>EasyServer itself:</b> the dashboard's <b>Updates</b> page. On Windows you can also run the newest installer over the old one; your settings are kept.</li>
      <li><b>The BeamMP server:</b> <b>Config → Restarts &amp; updates → install BeamMP updates</b> updates it automatically at the scheduled restart. By hand: <code>beammp update</code> on Linux, <b>Update-BeamMP-Server.bat</b> on Windows.</li></ul></>],

  ["not-in-server-list", "join", "My server doesn't show up in the BeamMP server list", <>
    <ol><li><b>Config → AuthKey</b> must be filled in.</li>
      <li><b>Config → Private</b> must be off. The "Most secure" and "Friends only" presets hide the server on purpose.</li>
      <li>The port must be reachable from the internet (see the next question).</li>
      <li>Give it a minute or two after starting.</li></ol>
    <p><b>Health → Check again</b> checks all of this and says which one is wrong.</p></>],
  ["friends-cant-join", "join", "Friends on my Wi-Fi can join, but friends outside my home can't", <>
    <p>Your router has to let them in. This is a one-time setting:</p>
    <ol><li>In your router, give the server computer a fixed address (often called <i>DHCP reservation</i> or <i>static lease</i>).</li>
      <li><b>Forward port 30814, TCP and UDP</b>, to that computer. Search for "<i>your router model</i> port forwarding" for the exact menu.</li>
      <li>In the dashboard: <b>Health → Full check</b>. "Reachable from the internet" should be green.</li></ol>
    <p>Still red? Some internet providers share one address between many homes (CGNAT), so port forwarding can't work. The Health page tells you when that's the case: ask your provider for a public IPv4 address, or use a relay (<b>Settings → Hide your IP</b>).</p></>, true],
  ["one-player-cant-join", "join", "One specific player can't join", <>
    <p><b>Health → Someone can't join?</b> → type their BeamMP name → <b>Check</b>. It reads their last attempt and says why it failed: banned, not on the invite list, maintenance, guests blocked, anti-bot code, too many players from one connection, server full, and so on, with the fix.</p>
    <p>Refused players also show up under <b>Config → Who can join → Recently refused</b> with a <b>+ allow</b> button.</p></>],
  ["password", "join", "How do I put a password on my server / make it friends-only?", <>
    <p>BeamMP has no join password, so EasyServer uses an <b>invite list</b> instead:</p>
    <ol><li><b>Config → Who can join</b>: turn on the list and type your friends' BeamMP usernames, one per line.</li>
      <li><b>Save list</b>. It works right away, no restart.</li></ol>
    <p>Everyone else gets an "invite-only" message. The quickest way is the <b>Most secure</b> or <b>Friends only</b> preset under <b>Config → Security presets</b>. With the Discord bot: <code>/whitelist add name</code>.</p></>],
  ["ip-changes", "join", "My home IP address keeps changing", <>
    <p>Set up a free fixed name: <b>Settings → Fixed address (DuckDNS)</b>. Friends then connect to <code>yourname.duckdns.org</code>, and it keeps working when the address changes. Public servers don't need this: the server list always has the current address.</p></>],
  ["hide-ip", "join", "Can players see my home IP? What about DDoS?", <>
    <p>Players connect to your server, so yes, they can find the address, like with any self-hosted game server. If that worries you, <b>Settings → Hide your IP</b> sends players through a relay, and flood protection is part of the <b>Most secure</b> and <b>Public but safe</b> presets. See <a href={GH + "/blob/main/PROTECT-YOUR-IP.md"}>Protect your IP</a>.</p></>],

  ["add-mods", "mods", "How do I add mods?", <>
    <ol><li>Open <b>Mods</b> in the dashboard and drag the mod <b>.zip</b> files onto the page.</li>
      <li>Each one is virus-checked first. The server restarts about 15 seconds later (on Windows, press Restart). That disconnects players, so add mods when it's quiet.</li>
      <li>Map mods get a <b>map:</b> badge. Click <b>Use map</b> to play it.</li></ol>
    <p>Players don't install anything: BeamMP downloads the mods for them when they join. Also possible: the <b>Drop BeamMP Mods Here</b> desktop icon (Windows), the <code>BeamMP-Mods</code> folder or <code>beammp addmod file.zip</code> (Linux).</p></>],
  ["slow-joining", "mods", "Joining takes forever because of the mod download", <>
    <ul><li>Turn on <b>Light mode</b> on the Mods page: players only download the map that's being played. Other map mods come back by themselves when you switch to their map.</li>
      <li>Remove mods nobody uses. The card at the top of the Mods page shows the total download.</li>
      <li>Friends on slow internet can get a <b>modpack</b> (Mods → Modpack) and copy the files into <code>Documents\BeamNG.drive\mods\multiplayer</code> before joining.</li></ul>
    <p>Your upload speed is the limit here, so a big modpack is slow on any home connection.</p></>],
  ["mod-blocked", "mods", "A mod was blocked by the virus check. Is it really dangerous?", <>
    <p>EasyServer blocks mods that contain programs, disguised files or zip bombs, or that Microsoft Defender, ClamAV or VirusTotal flag. A normal BeamNG mod is only car, map and script files, so a blocked mod contains something a mod shouldn't. The reason is shown next to it.</p>
    <p>Blocked files never reach the server or your players. Download the mod again from the official BeamNG repository instead of a reupload site.</p></>],
  ["change-map", "mods", "How do I change the map, or let players vote?", <>
    <ul><li><b>Now:</b> <b>Overview → Map</b>, pick one, confirm. The server restarts on the new map.</li>
      <li><b>Vote:</b> <b>Config → Map vote</b>, tick the allowed maps. Players type <code>/vote</code> in the game chat.</li>
      <li><b>Automatically:</b> <b>Config → Map rotation</b> (every 1-24 hours) or <b>Config → Events</b> ("Friday drift night").</li></ul></>],

  ["forgot-password", "dash", "I forgot the dashboard password / lost my phone for two-step login", <>
    <ul><li><b>Windows:</b> double-click <b>Reset-Dashboard-Login.bat</b> in the EasyServer folder.</li>
      <li><b>Linux:</b> <code>sudo beammp reset-login</code></li></ul>
    <p>Then open the dashboard <b>on the server computer</b> and choose a new password. Two-step login is turned off, so set it up again with your new phone.</p></>],
  ["connection-reset", "dash", "The browser says “connection reset” or “not secure”", <>
    <p><b>"Connection reset":</b> HTTPS is on, but you opened an <code>http://</code> address. Use <code>https://</code>, or update to 1.12.1 or newer, which sends you there automatically.</p>
    <p><b>"Not secure" / certificate warning:</b> normal the first time. Your dashboard makes its own certificate, so the browser doesn't know it yet. Compare the fingerprint shown in <b>Settings</b> with the one in the browser warning, then continue. The Android app remembers it for you.</p></>],
  ["phone", "dash", "Can I manage the server from my phone, or from outside my home?", <>
    <p><b>At home:</b> open <code>http://&lt;server-ip&gt;:30815</code> on your phone, or install the Android app (<b>BeamMP-EasyServer.apk</b> from the <a href={LATEST}>latest release</a>) and scan the QR code under <b>Settings → Phone app</b>. iPhone: Safari → Share → Add to Home Screen.</p>
    <p><b>From anywhere:</b> turn on HTTPS and two-step login, use a password of 12+ characters, then <b>Settings → Access from the internet</b> and forward port <b>30815 (TCP)</b>.</p></>],
  ["stay-logged-in", "dash", "Can it remember my password so I don't log in every time?", <>
    <p>Yes (version 1.12.1 and newer). Turn on <b>Stay logged in on this device</b> on the login page. That device then logs in by itself for 30 days after the last visit, also after restarts. Your browser's password manager also offers to save the password.</p>
    <p>Lost a phone? <b>Settings → Remembered devices → Forget</b>.</p></>],
  ["team", "dash", "How do I give friends access to help moderate?", <>
    <p><b>Settings → Users &amp; roles</b>: name, role, password → <b>Add</b>.</p>
    <ul><li><b>Viewer</b>: look, change nothing</li><li><b>Moderator</b>: kick, mute, ban, invite list, restart, maintenance</li><li><b>Admin</b>: everything except users, passwords and internet access</li></ul>
    <p>For in-game moderation only, add their BeamMP names under <b>Config → Moderation &amp; anti-bot → Admins</b>. They can then use <code>/kick</code>, <code>/ban</code> and <code>/mute</code> in the game chat.</p></>],

  ["discord-bot", "discord", "How do I set up the Discord bot?", <>
    <ol><li><a href="https://discord.com/developers/applications">discord.com/developers/applications</a> → <b>New Application</b>.</li>
      <li><b>Installation</b> → Install Link: <b>None</b> → save.</li>
      <li><b>Bot</b> → turn <b>Public Bot</b> off and <b>Message Content Intent</b> on (for the chat bridge) → <b>Reset Token</b> → copy.</li>
      <li>Dashboard: <b>Settings → Discord bot</b> → paste the token, turn it on, <b>Save</b>. When it says <b>Online</b>, click <b>Add the bot to your Discord</b>.</li>
      <li>Type <code>/status</code> in Discord.</li></ol>
    <p>Never share the bot token with anyone. If it leaks, press Reset Token again.</p></>],
  ["slash-commands", "discord", "The bot is online but the slash commands don't show up", <>
    <ul><li>New commands can take a minute. Restart Discord (Ctrl+R on PC).</li>
      <li>Check <b>Settings → Discord bot → Discord server the bot answers in</b> is set to your server.</li>
      <li><code>/start</code>, <code>/stop</code>, <code>/restart</code> and <code>/whitelist</code> only appear for people with <b>Manage Server</b>, or the Discord users you allowed.</li></ul></>],
  ["alerts", "discord", "Can I get a notification when the server crashes or someone joins?", <>
    <p>Yes, on your phone (free <b>ntfy</b> app, <b>Settings → Phone app</b>), in Discord, Telegram, Slack and other apps, or by email. Choose what you hear about under <b>Notify me about</b>. <b>Config → Join alerts</b> posts when chosen players join.</p></>],

  ["crash-lag", "trouble", "The server keeps crashing or lagging", <>
    <ol><li><b>Logs → Explain the whole log</b> lists every error in plain English, including broken mods and running out of memory.</li>
      <li><b>Health</b> shows memory and disk, and <b>Settings → Computer load</b> has 24-hour graphs.</li>
      <li>On an older computer, use the <b>Weak computer</b> preset, lower Max cars and turn on light mode.</li></ol>
    <p>A crashed server restarts by itself, and you're told if crash notifications are on.</p></>],
  ["undo", "trouble", "I changed a setting and now something is broken", <>
    <p><b>Config → What changed?</b> keeps the last 40 versions of your config, with who changed what. <b>Compare with now</b> shows the difference, and <b>Restore</b> goes back. Your AuthKey is kept, and you can undo the undo.</p></>],
  ["sleep", "trouble", "Do I have to keep the computer on 24/7?", <>
    <p>No. <b>Settings → Sleep &amp; wake-up</b> puts it to sleep when nobody has played for a while and wakes it before events. With <b>Wake-on-LAN</b> (network cable needed) friends can wake it with <code>/start</code> in Discord or the <b>Wake up</b> button in the app. The compatibility score lists what still has to be set.</p></>],
  ["new-computer", "trouble", "How do I move my server to a new computer?", <>
    <ol><li>Old computer: <b>Settings → Backup / move to another computer → Export settings + mods</b>.</li>
      <li>Install EasyServer on the new one, then <b>Import…</b> that file.</li>
      <li>Paste your AuthKey again: keys and passwords are never put in exports.</li></ol>
    <p>Nightly backups are on by default, and the last 7 can be downloaded any time.</p></>],
  ["get-help", "trouble", "My problem isn't here. How do I get help?", <>
    <ol><li><b>Health → Download diagnostic report</b>. Keys, passwords and addresses are removed from it.</li>
      <li><a href={ASK}>Ask in the community forum</a> and attach the report. Bugs go to <a href={GH + "/issues/new/choose"}>issues</a>.</li></ol>
    <p>Found a security problem? Please use <a href={GH + "/security/advisories/new"}>private reporting</a> instead of posting it publicly.</p></>],
].map(([id, cat, q, a, top]) => ({ id, cat, q, a, top: !!top, text: (q + " " + textOf(a)).toLowerCase() }));

const escape = w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
function Marked({ text, words }) {
  if (!words.length) return text;
  const re = new RegExp("(" + words.map(escape).join("|") + ")", "gi");
  return text.split(re).map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : part));
}

function CopyLink({ id }) {
  const [done, setDone] = useState(false);
  const copy = () => {
    const url = location.href.split("#")[0] + "#" + id;
    (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(
      () => { setDone(true); setTimeout(() => setDone(false), 1800); },
      () => history.replaceState(null, "", "#" + id));
  };
  return <button type="button" className="link js-only" onClick={copy}>{done ? "Link copied" : "Copy link to this answer"}</button>;
}

export function Help() {
  const [query, setQuery] = useState("");
  const [cat, setCat] = useState("all");
  const [open, toggle, setOpen] = useOpenSet();

  // Open the answer a shared link points to.
  useEffect(() => {
    const go = () => {
      const id = decodeURIComponent(location.hash.slice(1));
      if (!QA.some(t => t.id === id)) return;
      setCat("all"); setQuery("");
      setOpen(s => new Set(s).add(id));
      requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ block: "start" }));
    };
    go(); addEventListener("hashchange", go);
    return () => removeEventListener("hashchange", go);
  }, []);

  const words = useMemo(() => query.toLowerCase().split(/\s+/).filter(w => w.length > 1), [query]);
  const shown = QA.filter(t => (cat === "all" || t.cat === cat) && words.every(w => t.text.includes(w)));
  // A short list of matches opens by itself, so the answers are right there.
  useEffect(() => { if (words.length && shown.length <= 3) setOpen(new Set(shown.map(t => t.id))); }, [words.join(" "), cat]);
  const flip = id => { toggle(id); if (!open.has(id)) history.replaceState(null, "", "#" + id); };

  // Grouped by topic when nothing is searched, one flat list of matches otherwise.
  const groups = words.length ? [[null, shown]] : CATS.map(([k, label]) => [label, shown.filter(t => t.cat === k)]).filter(g => g[1].length);

  return (
    <>
      <Nav page="help" />
      <main className="wrap">
        <header className="help-head">
          <h1>Help &amp; community</h1>
          <span className="lane" aria-hidden="true" />
          <p>The questions server owners ask most, with answers. Not here? Ask in the community forum.</p>
          <div className="search js-only">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
            <input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder={"Search, e.g. “friends can't join” or “mods”"} autoComplete="off" aria-label="Search questions" />
          </div>
          <div className="chips js-only" role="group" aria-label="Topics">
            {[["all", "All"], ...CATS].map(([k, label]) => (
              <button key={k} type="button" aria-pressed={cat === k} onClick={() => setCat(k)}>
                {label}<span>{k === "all" ? QA.length : QA.filter(t => t.cat === k).length}</span>
              </button>
            ))}
          </div>
        </header>

        <div className="answers">
          <p className="count js-only" aria-live="polite">{shown.length} {shown.length === 1 ? "question" : "questions"}{words.length ? " match" : ""}</p>
          {groups.map(([label, list]) => (
            <section key={label || "results"} className="topic">
              {label ? <h2>{label}<small>{list.length} {list.length === 1 ? "question" : "questions"}</small></h2> : <h2>Results<small>Matching words are marked.</small></h2>}
              <div className="folds">
                {list.map(t => (
                  <Fold key={t.id} id={t.id} open={open.has(t.id)} onToggle={() => flip(t.id)}
                    title={<><Marked text={t.q} words={words} />{t.top && <span className="badge">Most asked</span>}</>}>
                    <div className="answer">{t.a}<CopyLink id={t.id} /></div>
                  </Fold>
                ))}
              </div>
            </section>
          ))}
          {!shown.length && <p className="empty">No answer matches that yet. <a href={ASK}>Ask it in the forum</a> and it may end up here.</p>}
        </div>

        <div className="closing">
          <h2>Didn't find your answer?</h2>
          <p>Ask the community. Search old threads, share ideas, or show off your server. You only need a free GitHub account.</p>
          <div className="btns">
            <a className="btn go" href={ASK}>Ask a question</a>
            <a className="btn" href={GH + "/discussions"}>Open the forum</a>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
