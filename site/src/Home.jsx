import { useEffect, useState } from "react";
import { Command, Fold, Footer, GH, LATEST, Nav, useOpenSet, useReducedMotion } from "./shared.jsx";

const LINUX_STABLE = "curl -fsSL https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/stable/linux/install.sh | sudo bash";
const LINUX_ROLLING = "curl -fsSL https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/main/linux/install.sh | sudo bash";
const MAC_ROLLING = "curl -fsSL https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/main/mac/install.sh | bash";

export const HOME_SPY = [
  { id: "start", label: "Get started", opt: true },
  { id: "features", label: "What it does", opt: true },
  { id: "versions", label: "Downloads", opt: true },
  { id: "faq", label: "FAQ", opt: true },
];

/* ---------- Hero: the dashboard, one page at a time ---------- */

const TOUR = [
  { key: "overview", label: "Overview", img: "img/overview-dark.webp", w: 820, h: 519,
    alt: "The EasyServer dashboard: server running, 7 of 16 players online, map, uptime and who's online" },
  { key: "mods", label: "Mods", img: "img/mods-dark.webp", w: 820, h: 519,
    alt: "Mods page with virus check results and light mode saving 380 MB" },
  { key: "players", label: "Players", img: "img/players-dark.webp", w: 820, h: 519,
    alt: "Player statistics: players per day, busiest hours and week overview" },
  { key: "status", label: "Status page", img: "img/status.webp", w: 820, h: 401,
    alt: "Public status page with 30-day uptime" },
];

export function Tour() {
  const [i, setI] = useState(0);
  const [held, setHeld] = useState(false);   // the person picked a page: stop turning pages
  const [hover, setHover] = useState(false);
  const reduce = useReducedMotion();
  const pick = n => { setI(n); setHeld(true); };
  const onKey = e => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const n = (i + (e.key === "ArrowRight" ? 1 : TOUR.length - 1)) % TOUR.length;
    pick(n); e.currentTarget.querySelectorAll("button")[n].focus();
  };
  const running = !held && !reduce;
  return (
    <div className="tour" onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      <div className="tour-frame">
        {TOUR.map((t, n) => (
          <img key={t.key} id={"tour-" + t.key} role="tabpanel" aria-label={t.label} src={t.img} width={t.w} height={t.h} alt={t.alt}
            className={n === i ? "on" : undefined} aria-hidden={n === i ? undefined : true}
            loading={n === 0 ? "eager" : "lazy"} fetchPriority={n === 0 ? "high" : undefined} />
        ))}
      </div>
      <div className={"tour-tabs js-only" + (running ? " auto" : "")} role="tablist" aria-label="Dashboard pages" onKeyDown={onKey}>
        {TOUR.map((t, n) => (
          <button key={t.key} type="button" role="tab" aria-selected={n === i} aria-controls={"tour-" + t.key}
            tabIndex={n === i ? 0 : -1} onClick={() => pick(n)}>
            {t.label}
            {n === i && running && (
              <span className={"tour-time" + (hover ? " paused" : "")} key={"t" + i}
                onAnimationEnd={() => setI((i + 1) % TOUR.length)} aria-hidden="true" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

function Hero() {
  return (
    <div className="hero">
      <div className="hero-words">
        <h1>Your own BeamNG.drive multiplayer server, set up in one click</h1>
        <span className="lane" aria-hidden="true" />
        <p>EasyServer installs the official BeamMP server and gives you a dashboard for it on your PC or phone. Add mods, see who's playing and keep trolls out, without config files or a command line. It's free and open source, for Windows and Linux.</p>
        <div className="btns">
          <a className="btn go" href={LATEST} data-goatcounter-click="download-stable">Download</a>
          <a className="btn" href="#start">How it works</a>
        </div>
      </div>
      <div className="shot"><Tour /></div>
    </div>
  );
}

/* ---------- Get started: four stops on a road ---------- */

function OsSwitch() {
  const [os, setOs] = useState("win");
  useEffect(() => { if (/Linux/.test(navigator.platform) && !/Android/.test(navigator.userAgent)) setOs("linux"); }, []);
  return (
    <>
      <div className={"os js-only os-" + os} role="tablist" aria-label="Your system">
        <span className="os-pill" aria-hidden="true" />
        <button type="button" role="tab" aria-selected={os === "win"} onClick={() => setOs("win")}>Windows</button>
        <button type="button" role="tab" aria-selected={os === "linux"} onClick={() => setOs("linux")}>Linux</button>
      </div>
      <div className="tabpanel" hidden={os !== "win"}>
        <p><span className="nojs-label">Windows: </span>Download <b>BeamMP-EasyServer-Windows.zip</b> from the <a href={LATEST} data-goatcounter-click="download-stable">latest release</a>, extract it and double-click <b>Install-BeamMP-Server.bat</b>.</p>
      </div>
      <div className="tabpanel" hidden={os !== "linux"}>
        <p><span className="nojs-label">Linux: </span>Paste this into a terminal:</p>
        <Command>{LINUX_STABLE}</Command>
      </div>
    </>
  );
}

const STEPS = [
  { title: "Get a free AuthKey", short: "AuthKey",
    body: <p>Log in at <a href="https://keymaster.beammp.com">keymaster.beammp.com</a> with Discord, click <b>Keys</b>, then <b>+</b>, and copy the key. It puts your server in the public BeamMP list.</p> },
  { title: "Install", short: "Install",
    body: <><OsSwitch /><p>This installs the tested <b>Stable</b> version. For the newest features, see <a href="#versions">Rolling</a>.</p></> },
  { title: "Open the dashboard", short: "Dashboard",
    body: <p>On the server computer, go to <b>http://localhost:30815</b> and choose a password. From your phone or another PC at home, use <b>http://&lt;server-ip&gt;:30815</b>.</p> },
  { title: "Let friends in", short: "Friends",
    body: <><p>On the Health page, click <b>Open port automatically</b>. Most routers accept it. If yours doesn't, forward port 30814 (TCP and UDP) yourself, and the Health page tells you when it works.</p>
      <p>Then click <b>Copy invite</b> and paste it in Discord. <a href={GH + "#-guides"}>Step-by-step guides</a></p></> },
];

function Road() {
  const [i, setI] = useState(0);
  return (
    <div className="road" style={{ "--at": i, "--n": STEPS.length }}>
      <ol className="road-stops js-only" role="tablist" aria-label="Setup steps">
        {STEPS.map((s, n) => (
          <li key={n}>
            <button type="button" role="tab" aria-selected={n === i} aria-controls={"step-" + n}
              className={n < i ? "done" : undefined} onClick={() => setI(n)}>
              <span className="stop-num">{n + 1}</span><span className="stop-name">{s.short}</span>
            </button>
          </li>
        ))}
      </ol>
      {STEPS.map((s, n) => (
        <div key={n} id={"step-" + n} className="tabpanel step" role="tabpanel" hidden={n !== i}>
          <h3>{n + 1}. {s.title}</h3>
          {s.body}
          <div className="step-nav js-only">
            {n > 0 && <button type="button" className="link" onClick={() => setI(n - 1)}>Back</button>}
            {n < STEPS.length - 1 && <button type="button" className="btn small" onClick={() => setI(n + 1)}>Next: {STEPS[n + 1].title}</button>}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ---------- What it does: pick a feature, see the real screen ---------- */

const FEATURES = [
  { key: "mods", title: "Mods without the worry", img: "img/mods-dark.webp", w: 820, h: 519,
    alt: "Mods page with virus check results and light mode saving 380 MB",
    text: "Drag mod zips onto the page. Each one is checked for hidden programs, disguised files and zip bombs with Microsoft Defender or ClamAV, and VirusTotal if you like, before players can download it.",
    list: [["Mod browser:", "install from the BeamNG repository in one click, and update the same way"],
      ["Light mode:", "players only download the map being played, so joining is faster"],
      ["Modpacks:", "move or share all your mods as one file"]] },
  { key: "players", title: "See who plays, and when", img: "img/players-dark.webp", w: 820, h: 519,
    alt: "Player statistics: players per day, busiest hours and week overview",
    text: "Players per day, the busiest hours, a week heatmap, top players, server records and the maps people actually stay on.",
    list: [["Kick, mute and ban", "from the dashboard, Discord or game chat"],
      ["Maintenance mode", "closes the server while you work on it"],
      ["Team accounts", "for friends who help, with only the permissions you give them"]] },
  { key: "security", title: "Choose how open it is", img: "img/presets.webp", w: 820, h: 331,
    alt: "Security presets: Most secure, Public but safe, Friends only, Open to everyone, Weak computer",
    text: <>One click sets your server anywhere from <b>Most secure</b> (invite-only, anti-bot, flood protection) to <b>Open to everyone</b>. Every config change is saved, so you can see what changed and undo it.</>,
    list: [["Invite list,", "because BeamMP has no join password"],
      ["Anti-bot:", "join codes, guest blocking and connection limits"]] },
  { key: "phone", title: "Run it from your phone", img: "img/phone.webp", w: 320, h: 693, phone: true,
    alt: "The dashboard on a phone",
    text: "The dashboard works in any phone browser. There's an Android app, and on iPhone you can add it to the home screen.",
    list: [["Alerts", "for crashes, joins and updates on your phone, Discord, Telegram, Slack or email"],
      ["Discord bot", "with /status, /start, /restart, /whitelist and a chat bridge"],
      ["Sleep and Wake-on-LAN,", "so the PC doesn't have to run all day"]] },
  { key: "status", title: "A status page for players", img: "img/status.webp", w: 820, h: 401,
    alt: "Public status page with 30-day uptime",
    text: "One link shows whether the server is up, who's online, which mods to download and the next event. No login, and no addresses or settings on show." },
];

function Explorer() {
  const [i, setI] = useState(0);
  const onKey = e => {
    const k = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
    if (!k) return;
    e.preventDefault();
    const n = (i + k + FEATURES.length) % FEATURES.length;
    setI(n); e.currentTarget.querySelectorAll("button")[n].focus();
  };
  return (
    <div className="explorer">
      <div className="ex-list js-only" role="tablist" aria-label="Features" aria-orientation="vertical" onKeyDown={onKey}>
        {FEATURES.map((f, n) => (
          <button key={f.key} type="button" role="tab" aria-selected={n === i} aria-controls={"feat-" + f.key}
            tabIndex={n === i ? 0 : -1} onClick={() => setI(n)}>{f.title}</button>
        ))}
      </div>
      <div className="ex-panels">
        {FEATURES.map((f, n) => (
          <div key={f.key} id={"feat-" + f.key} role="tabpanel" className={"tabpanel ex-panel" + (f.phone ? " is-phone" : "")} hidden={n !== i}>
            <img src={f.img} width={f.w} height={f.h} alt={f.alt} loading="lazy" className={f.phone ? "phone" : undefined} />
            <div>
              <h3>{f.title}</h3>
              <p>{f.text}</p>
              {f.list && <ul>{f.list.map(([b, t]) => <li key={b}><b>{b}</b> {t}</li>)}</ul>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------- The rest ---------- */

const ALSO = [
  ["Copy invite", "A ready-to-paste Discord message with the address and port."],
  ["Map vote and rotation", "Players type /vote, or the map changes on a schedule."],
  ["Weekly events", "\"Friday drift night\" switches map and mods and is announced in Discord."],
  ["/tp and /repair", "Teleport to friends once they accept, with realism or hardcore repair rules."],
  ["Car cleanup", "Abandoned cars are removed, with a countdown before the nightly cleanup."],
  ["Chat tools", "Welcome message, timed announcements, a chat filter, anti-spam and /countdown."],
  ["Several servers", "Run more than one server on one PC, each with its own CPU, RAM and download limits."],
  ["Nightly backups", "Restore, or move to a new computer, with one file."],
  ["Hide your IP", "An optional relay and flood protection against DDoS."],
  ["Log explainer", "Server errors in plain English, with what to do about them."],
];

const FAQ = [
  ["Is it free?", <>Yes. It's free and open source (MIT license), with every feature and no ads. BeamMP and its server are free too. You need your own copy of BeamNG.drive to play.</>],
  ["Is this the official BeamMP server?", <>EasyServer installs the <b>official</b> BeamMP server and keeps it updated. EasyServer itself is a community project, not made or endorsed by the BeamMP team.</>],
  ["What computer do I need?", <>Any 64-bit Windows 10 or 11 PC, or Linux (Ubuntu, Linux Mint, Debian and others, including a Raspberry Pi 4 or 5 with a 64-bit OS). An old laptop is enough for a group of friends. Upload speed matters more than the processor.</>],
  ["Does it change my router?", <>Only if you click <b>Open port automatically</b>, which asks your router to open the game port. Otherwise it just opens the port in the computer's own firewall, and asks first.</>],
  ["Can I use it from my phone?", <>Yes. The dashboard works in any phone browser, there's an Android app, and you can add it to the iPhone home screen. Managing it from outside your home works once HTTPS and two-step login are on.</>],
  ["I found a bug or have an idea", <><a href={GH + "/issues/new/choose"}>Open an issue on GitHub</a>. For security problems, please use private reporting instead.</>],
];

function Faq() {
  const [open, toggle] = useOpenSet();
  return <div className="folds">{FAQ.map(([q, a], n) => <Fold key={n} title={q} open={open.has(n)} onToggle={() => toggle(n)}><p>{a}</p></Fold>)}</div>;
}

export function Home() {
  return (
    <>
      <Nav page="home" spy={HOME_SPY} />
      <main className="wrap">
        <Hero />

        <section id="start">
          <h2>Get started<small>About ten minutes, most of it waiting for downloads.</small></h2>
          <div>
            <Road />
            <div className="video"><iframe src="https://www.youtube-nocookie.com/embed/DWD9HcW1OIc" title="How to make a BeamMP server in 5 minutes - setup video" loading="lazy" allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; web-share" referrerPolicy="strict-origin-when-cross-origin" allowFullScreen /></div>
            <p className="note">Rather watch? The whole setup takes about 2 minutes. <a href="https://youtu.be/DWD9HcW1OIc">Open on YouTube</a></p>
          </div>
        </section>

        <section id="features">
          <h2>What it does<small>Made for people who want to play with friends, not learn server admin. <a href="features.html">All features</a></small></h2>
          <Explorer />
        </section>

        <section className="new">
          <h2>New in 1.15<small>In Rolling now. They come to Stable once they've been tested.</small></h2>
          <div className="rows">
            <div className="row"><h3>Vehicle rules</h3><p>Block props, trailers or any car, and stop spawn spam. Mod cars heavy enough to lag everyone are found automatically.</p></div>
            <div className="row"><h3>Server plugins</h3><p>Install community game modes like CareerMP, freeRoamMP and BeamJoy, straight from each author's page.</p></div>
            <div className="row"><h3>Run it as a team</h3><p>Invite friends with a link that works once and expires after an hour, and choose what each one can do on each server. They can sign in with Discord.</p></div>
          </div>
        </section>

        <section>
          <h2>Also included<small>All optional. Turn on what you need.</small></h2>
          <div className="also">{ALSO.map(([h, p]) => <div key={h}><h3>{h}</h3><p>{p}</p></div>)}</div>
        </section>

        <section>
          <h2>Security<small>Your server is a computer on your home network, so this matters.</small></h2>
          <div className="rows">
            <div className="row"><h3>Keys are encrypted</h3><p>Your AuthKey, tokens and passwords are never stored in plain text.</p></div>
            <div className="row"><h3>Separate users on Linux</h3><p>The game server and the dashboard each run as their own limited user.</p></div>
            <div className="row"><h3>Two-step login</h3><p>Required before the dashboard can be reached from the internet.</p></div>
            <div className="row"><h3>Tested on every change</h3><p>Automated tests try to break into every dashboard page and the game plugin on each update.</p></div>
          </div>
        </section>

        <section id="versions">
          <h2>Downloads<small>Both are free. Not sure? Take Stable.</small></h2>
          <div>
            <div className="dl">
              <div><h3>Stable</h3><p className="what">Tested. It's the release marked "Latest" on GitHub.</p>
                <ul><li><b>Windows:</b> download <b>BeamMP-EasyServer-Windows.zip</b>, extract it and double-click <b>Install-BeamMP-Server.bat</b></li>
                  <li><b>Linux:</b><Command>{LINUX_STABLE}</Command></li></ul>
                <a className="btn go" href={LATEST} data-goatcounter-click="download-stable">Download Stable</a></div>
              <div><h3>Rolling</h3><p className="what">New features as soon as they're made. May have bugs.</p>
                <ul><li><b>Windows:</b> download the ZIP, extract it, open the <b>windows</b> folder and double-click <b>Install-BeamMP-Server.bat</b></li>
                  <li><b>Linux:</b><Command>{LINUX_ROLLING}</Command></li>
                  <li><b>Mac (experimental, Rolling only):</b> paste this into Terminal. It runs the server in a small Linux VM that starts with your Mac (<a href={GH + "#mac-experimental"}>how it works</a>).<Command>{MAC_ROLLING}</Command></li>
                  <li>Something broken? Install Stable over it. Your settings and mods stay.</li></ul>
                <a className="btn" href={GH + "/archive/refs/heads/main.zip"} data-goatcounter-click="download-rolling">Download Rolling (ZIP)</a></div>
            </div>
            <p className="note">What changed in each version: <a href={GH + "/blob/main/CHANGELOG.md"}>changelog</a>, <a href={GH + "/releases"} data-goatcounter-click="all-releases">all releases</a></p>
          </div>
        </section>

        <section id="faq">
          <h2>Questions<small><a href="help.html">More answers and the community</a></small></h2>
          <Faq />
        </section>

        <div className="closing">
          <h2>Try it on your PC</h2>
          <p>Download it, run it and follow the steps. If you get stuck, the Help page and the community can help.</p>
          <div className="btns">
            <a className="btn go" href={LATEST} data-goatcounter-click="download-stable">Download</a>
            <a className="btn" href={GH} data-goatcounter-click="github">View on GitHub</a>
          </div>
        </div>
      </main>
      <Footer><p>Screenshots show a demo server with invented players.</p></Footer>
    </>
  );
}
