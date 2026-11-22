import { Footer, LATEST, Nav, useScrollSpy } from "./shared.jsx";
import { Tour } from "./Home.jsx";

const PARTS = [
  { id: "online", label: "Getting it online" },
  { id: "running", label: "Running it" },
  { id: "new", label: "New in 1.15" },
];

function Jump() {
  const active = useScrollSpy(PARTS.map(p => p.id));
  return (
    <div className="jump" aria-label="On this page">
      <span>On this page</span>
      {PARTS.map(p => <a key={p.id} href={"#" + p.id} aria-current={active === p.id ? "location" : undefined}>{p.label}</a>)}
    </div>
  );
}

const Row = ({ h, children }) => <div className="row"><h3>{h}</h3><div>{children}</div></div>;

export function Features() {
  return (
    <>
      <Nav page="features" />
      <main className="wrap">
        <div className="hero">
          <div className="hero-words">
            <h1>Host BeamMP for your friends without touching a config file</h1>
            <span className="lane" aria-hidden="true" />
            <p>EasyServer installs the official BeamMP server, then gives you one page to run it from. It's free, open source and works on Windows and Linux.</p>
            <div className="btns">
              <a className="btn go" href={LATEST} data-goatcounter-click="features-download">Download</a>
              <a className="btn" href="./#start">How to install</a>
            </div>
          </div>
          <div className="shot"><Tour /></div>
        </div>

        <Jump />

        <section id="online">
          <h2>Getting it online<small>The part most people get stuck on.</small></h2>
          <div className="rows">
            <Row h="Guided setup"><p>Paste your AuthKey and the installer checks it's valid. It sets the server to start with your PC and restarts it if it crashes.</p></Row>
            <Row h="Opening the port"><p>One click asks your router to open port 30814. If your router doesn't allow that, the Help page explains how to do it by hand.</p></Row>
            <Row h={"“Why can't my friend join?”"}><p>The Health page checks your AuthKey, the port, the firewall and whether your server shows up in the BeamMP list, and tells you which one is wrong.</p></Row>
            <Row h="Old laptops welcome"><p>The Weak computer preset allows fewer players and cars and clears abandoned cars quickly, so a spare laptop can run a small server.</p></Row>
          </div>
        </section>

        <section id="running">
          <h2>Running it<small>From your desk or from the sofa.</small></h2>
          <div className="rows">
            <div className="pair">
              <figure><img src="img/players-dark.webp" width="820" height="519" alt="Players page with a list of online players and kick, mute and ban buttons" loading="lazy" /><figcaption>The Players page</figcaption></figure>
              <figure><img className="phone" src="img/phone.webp" width="320" height="693" alt="The dashboard on a phone" loading="lazy" /><figcaption>Same thing on a phone</figcaption></figure>
            </div>
            <Row h="Start, stop, change map"><p>Change the map from a list instead of editing ServerConfig.toml. Works in any browser, including on your phone.</p></Row>
            <Row h="Players and bans"><p>Kick, mute and ban from the dashboard, from Discord or with a chat command. There's also an invite-only list and maintenance mode.</p></Row>
            <Row h="Mods"><p>Drag a zip onto the page or pick one from the BeamNG repository. Each one is virus-scanned before players download it.</p><p>Share your whole mod list with a short code, and a friend's server can install the same set.</p></Row>
            <Row h="Backups and alerts"><p>Back up and restore your config. Get a message on Discord, email, Telegram or your phone when the server crashes.</p></Row>
          </div>
        </section>

        <section className="new" id="new">
          <h2>New in 1.15<small>In the Rolling version now. They move to Stable once they've been tested.</small></h2>
          <div className="rows">
            <Row h="Vehicle rules"><p>Block props, the huge physics props, trailers or any car you pick. Mod cars heavy enough to lag everyone are spotted automatically.</p><p>There's a spawn cooldown too, and presets for racing and roleplay servers.</p></Row>
            <Row h="Server plugins"><p>Install community game modes like CareerMP, freeRoamMP and BeamJoy. They download from each author's own page, and you can see which files go where before you install.</p></Row>
            <Row h="Run it as a team"><p>Send a friend an invite link that works once and stops working after an hour. Give them a role, like viewer or moderator, for each server.</p><p>They can sign in with Discord instead of a password. Anyone who logs in from outside your home network needs a two-step login code.</p></Row>
          </div>
        </section>

        <div className="closing">
          <h2>Try it on your PC</h2>
          <p>Download it, run it and follow the steps. Most people are online in about five minutes. If you get stuck, the Help page and the community can help.</p>
          <div className="btns">
            <a className="btn go" href={LATEST} data-goatcounter-click="features-download">Download</a>
            <a className="btn" href="help.html">Help</a>
          </div>
        </div>
      </main>
      <Footer><p>The Mac version is experimental and only in Rolling.</p></Footer>
    </>
  );
}
