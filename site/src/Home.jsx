import { useEffect, useState } from "react";
import { Md, useSite } from "./i18n.jsx";
import { useNews } from "./news.jsx";
import { Command, DownloadButton, Fold, Footer, GH, LATEST, Nav, Words, useLatestVersion, useOpenSet, useReducedMotion } from "./shared.jsx";

const LINUX_STABLE = "curl -fsSL https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/stable/linux/install.sh | sudo bash";
const LINUX_ROLLING = "curl -fsSL https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/main/linux/install.sh | sudo bash";
const MAC_ROLLING = "curl -fsSL https://raw.githubusercontent.com/Csabika-dev/beammp-easyserver/main/mac/install.sh | bash";

export const HOME_SPY = [
  { id: "start", key: "start" },
  { id: "features", key: "what" },
  { id: "versions", key: "downloads" },
  { id: "faq", key: "faq" },
];

/* ---------- Hero: the dashboard, one page at a time ---------- */

const TOUR = [
  { key: "overview", img: "img/overview-dark.webp", w: 820, h: 519 },
  { key: "mods", img: "img/mods-dark.webp", w: 820, h: 519 },
  { key: "players", img: "img/players-dark.webp", w: 820, h: 519 },
  { key: "status", img: "img/status.webp", w: 820, h: 401 },
];

export function Tour() {
  const { t, root } = useSite();
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
  // Tilt the screenshot a few degrees toward the mouse.
  const tilt = e => {
    if (reduce) return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
    e.currentTarget.style.setProperty("--ry", (x * 7).toFixed(2) + "deg");
    e.currentTarget.style.setProperty("--rx", (-y * 6).toFixed(2) + "deg");
  };
  const untilt = e => { e.currentTarget.style.removeProperty("--rx"); e.currentTarget.style.removeProperty("--ry"); };
  return (
    <div className="tour" onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      <div className="tour-frame" onMouseMove={tilt} onMouseLeave={untilt}>
        {TOUR.map((s, n) => (
          <img key={s.key} id={"tour-" + s.key} role="tabpanel" aria-label={t.tour.tabs[n]} src={root + s.img} width={s.w} height={s.h} alt={t.tour.alts[n]}
            className={n === i ? "on" : undefined} aria-hidden={n === i ? undefined : true}
            loading={n === 0 ? "eager" : "lazy"} fetchPriority={n === 0 ? "high" : undefined} />
        ))}
      </div>
      <div className={"tour-tabs js-only" + (running ? " auto" : "")} role="tablist" aria-label={t.tour.label} onKeyDown={onKey}>
        {TOUR.map((s, n) => (
          <button key={s.key} type="button" role="tab" aria-selected={n === i} aria-controls={"tour-" + s.key}
            tabIndex={n === i ? 0 : -1} onClick={() => pick(n)}>
            {t.tour.tabs[n]}
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
  const { t } = useSite();
  return (
    <div className="hero">
      <div className="hero-words">
        <h1 className="hop"><Words text={t.home.h1} /></h1>
        <span className="lane" aria-hidden="true" />
        <p>{t.home.lead}</p>
        <div className="btns">
          <DownloadButton />
          <a className="btn" href="#start">{t.home.how}</a>
        </div>
      </div>
      <div className="shot"><Tour /></div>
    </div>
  );
}

/* ---------- Get started: four stops on a road ---------- */

function OsSwitch() {
  const { t } = useSite();
  const [os, setOs] = useState("win");
  useEffect(() => { if (/Linux/.test(navigator.platform) && !/Android/.test(navigator.userAgent)) setOs("linux"); }, []);
  return (
    <>
      <div className={"os js-only os-" + os} role="tablist" aria-label={t.home.osLabel}>
        <span className="os-pill" aria-hidden="true" />
        <button type="button" role="tab" aria-selected={os === "win"} onClick={() => setOs("win")}>{t.home.windows}</button>
        <button type="button" role="tab" aria-selected={os === "linux"} onClick={() => setOs("linux")}>{t.home.linux}</button>
      </div>
      <div className="tabpanel" hidden={os !== "win"}>
        <p><span className="nojs-label">{t.home.windows}: </span><Md s={t.home.winInstall} /></p>
      </div>
      <div className="tabpanel" hidden={os !== "linux"}>
        <p><span className="nojs-label">{t.home.linux}: </span>{t.home.linuxInstall}</p>
        <Command>{LINUX_STABLE}</Command>
      </div>
    </>
  );
}

function Road() {
  const { t } = useSite();
  const steps = t.home.steps;
  const [i, setI] = useState(0);
  return (
    <div className="road" style={{ "--at": i, "--n": steps.length }}>
      <ol className="road-stops js-only" role="tablist" aria-label={t.home.stepsLabel}>
        {steps.map((s, n) => (
          <li key={n}>
            <button type="button" role="tab" aria-selected={n === i} aria-controls={"step-" + n}
              className={n < i ? "done" : undefined} onClick={() => setI(n)}>
              <span className="stop-num">{n + 1}</span><span className="stop-name">{s.short}</span>
            </button>
          </li>
        ))}
      </ol>
      {steps.map((s, n) => (
        <div key={n} id={"step-" + n} className="tabpanel step" role="tabpanel" hidden={n !== i}>
          <h3>{n + 1}. {s.title}</h3>
          {n === 1 && <OsSwitch />}
          {s.text.map((p, k) => <p key={k}><Md s={p} /></p>)}
          <div className="step-nav js-only">
            {n > 0 && <button type="button" className="link" onClick={() => setI(n - 1)}>{t.home.back}</button>}
            {n < steps.length - 1 && <button type="button" className="btn small" onClick={() => setI(n + 1)}>{t.home.next} {steps[n + 1].title}</button>}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ---------- What it does: pick a feature, see the real screen ---------- */

const SHOTS = [
  { key: "mods", img: "img/mods-dark.webp", w: 820, h: 519 },
  { key: "players", img: "img/players-dark.webp", w: 820, h: 519 },
  { key: "security", img: "img/presets.webp", w: 820, h: 331 },
  { key: "phone", img: "img/phone.webp", w: 320, h: 693, phone: true },
  { key: "status", img: "img/status.webp", w: 820, h: 401 },
];

function Explorer() {
  const { t, root } = useSite();
  const feats = t.home.features;
  const [i, setI] = useState(0);
  const onKey = e => {
    const k = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
    if (!k) return;
    e.preventDefault();
    const n = (i + k + feats.length) % feats.length;
    setI(n); e.currentTarget.querySelectorAll("button")[n].focus();
  };
  return (
    <div className="explorer">
      <div className="ex-list js-only" role="tablist" aria-label={t.home.featuresLabel} aria-orientation="vertical" onKeyDown={onKey}>
        {feats.map((f, n) => (
          <button key={n} type="button" role="tab" aria-selected={n === i} aria-controls={"feat-" + SHOTS[n].key}
            tabIndex={n === i ? 0 : -1} onClick={() => setI(n)} onMouseEnter={() => setI(n)}>{f.title}</button>
        ))}
      </div>
      <div className="ex-panels">
        {feats.map((f, n) => {
          const s = SHOTS[n];
          return (
            <div key={n} id={"feat-" + s.key} role="tabpanel" className={"tabpanel ex-panel" + (s.phone ? " is-phone" : "")} hidden={n !== i}>
              <img src={root + s.img} width={s.w} height={s.h} alt={f.alt} loading="lazy" className={s.phone ? "phone" : undefined} />
              <div>
                <h3>{f.title}</h3>
                <p><Md s={f.text} /></p>
                {f.list && <ul>{f.list.map((x, k) => <li key={k}><Md s={x} /></li>)}</ul>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ---------- The rest ---------- */

// The Stable download in the Downloads section, with the version number once GitHub tells us.
function StableButton() {
  const { t } = useSite();
  const v = useLatestVersion();
  return <a className="btn go" href={LATEST} data-goatcounter-click="download-stable">{t.home.stableButton}{v ? " (" + v + ")" : ""}</a>;
}

function Faq() {
  const { t } = useSite();
  const [open, toggle] = useOpenSet();
  return <div className="folds" data-reveal="stagger">{t.home.faq.map(([q, a], n) => <Fold key={n} title={q} open={open.has(n)} onToggle={() => toggle(n)}><p><Md s={a} /></p></Fold>)}</div>;
}

const Rows = ({ rows }) => (
  <div className="rows" data-reveal="stagger">{rows.map(([h, p]) => <div className="row" key={h}><h3>{h}</h3><p><Md s={p} /></p></div>)}</div>
);
const Head = ({ title, sub }) => <h2><span className="sweep">{title}</span><small><Md s={sub} /></small></h2>;

export function Home() {
  const { t } = useSite();
  const h = t.home;
  const news = useNews();
  return (
    <>
      <Nav page="home" spy={HOME_SPY} />
      <main className="wrap">
        <Hero />

        <section id="start" data-reveal="">
          <Head title={h.startTitle} sub={h.startSub} />
          <div>
            <Road />
            <div className="video"><iframe src="https://www.youtube-nocookie.com/embed/DWD9HcW1OIc" title={h.videoTitle} loading="lazy" allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; web-share" referrerPolicy="strict-origin-when-cross-origin" allowFullScreen /></div>
            <p className="note"><Md s={h.videoNote} /></p>
          </div>
        </section>

        <section id="features" data-reveal="">
          <Head title={h.whatTitle} sub={h.whatSub} />
          <Explorer />
        </section>

        {news && <section className="new" data-reveal="">
          <Head title={news.title} sub={news.sub} />
          <Rows rows={news.items} />
        </section>}

        <section data-reveal="">
          <Head title={h.alsoTitle} sub={h.alsoSub} />
          <div className="also" data-reveal="stagger">{h.also.map(([a, b]) => <div key={a}><h3>{a}</h3><p>{b}</p></div>)}</div>
        </section>

        <section data-reveal="">
          <Head title={h.secTitle} sub={h.secSub} />
          <Rows rows={h.security} />
        </section>

        <section id="versions" data-reveal="">
          <Head title={h.dlTitle} sub={h.dlSub} />
          <div>
            <div className="dl" data-reveal="stagger">
              <div><h3>{h.stable}</h3><p className="what">{h.stableWhat}</p>
                <ul><li><Md s={h.stableWin} /></li>
                  <li><Md s={h.linuxLabel} /><Command>{LINUX_STABLE}</Command></li></ul>
                <StableButton /></div>
              <div><h3>{h.rolling}</h3><p className="what">{h.rollingWhat}</p>
                <ul><li><Md s={h.rollingWin} /></li>
                  <li><Md s={h.linuxLabel} /><Command>{LINUX_ROLLING}</Command></li>
                  <li><Md s={h.mac} /><Command>{MAC_ROLLING}</Command></li>
                  <li>{h.broken}</li></ul>
                <a className="btn" href={GH + "/archive/refs/heads/main.zip"} data-goatcounter-click="download-rolling">{h.rollingButton}</a></div>
            </div>
            <p className="note"><Md s={h.changes} /></p>
          </div>
        </section>

        <section id="faq" data-reveal="">
          <Head title={h.faqTitle} sub={h.faqSub} />
          <Faq />
        </section>

        <div className="closing" data-reveal="">
          <h2 className="hop"><Words text={t.common.tryTitle} /></h2>
          <p>{h.closing}</p>
          <div className="btns">
            <DownloadButton />
            <a className="btn" href={GH} data-goatcounter-click="github">{t.common.viewOnGithub}</a>
          </div>
        </div>
      </main>
      <Footer note={h.footnote} />
    </>
  );
}
