import { Fragment, useEffect, useId, useRef, useState } from "react";
import { LANGS, Md, pageHref, useSite } from "./i18n.jsx";
import { GH, LATEST } from "./links.js";

export { GH, LATEST, ASK } from "./links.js";

export function useReducedMotion() {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    const m = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setReduce(m.matches);
    on(); m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return reduce;
}

// Which of these section ids is on screen now.
export function useScrollSpy(ids) {
  const [active, setActive] = useState(null);
  useEffect(() => {
    const els = ids.map(id => document.getElementById(id)).filter(Boolean);
    if (!els.length) return;
    const seen = new Map();
    const io = new IntersectionObserver(entries => {
      entries.forEach(e => seen.set(e.target.id, e.isIntersecting ? e.intersectionRatio : 0));
      let best = null, top = Infinity;
      els.forEach(el => { if (seen.get(el.id) > 0) { const y = el.getBoundingClientRect().top; if (y < top) { top = y; best = el.id; } } });
      setActive(best);
    }, { rootMargin: "-80px 0px -45% 0px", threshold: [0, 0.01] });
    els.forEach(el => io.observe(el));
    return () => io.disconnect();
  }, [ids.join()]);
  return active;
}

// The words of a headline, each in its own box so they can hop when you point at them.
export function Words({ text }) {
  return text.split(" ").map((w, i) => (
    <Fragment key={i}>{i > 0 && " "}<span className="w" style={{ "--i": i }}>{w}</span></Fragment>
  ));
}

// Light/dark switch. The page starts in the computer's setting; a click picks the other one and
// remembers it. The boot script in build.mjs applies the saved choice before anything is drawn.
function ThemeButton() {
  const { t } = useSite();
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const d = document.documentElement.dataset.theme;
    setDark(d ? d === "dark" : matchMedia("(prefers-color-scheme: dark)").matches);
  }, []);
  const flip = () => {
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("es-site-theme", next); } catch {}
    setDark(!dark);
  };
  const label = dark ? t.common.themeLight : t.common.themeDark;
  return (
    <button type="button" className="themebtn js-only" onClick={flip} aria-label={label} title={label}>
      <svg className="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
      <svg className="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" /></svg>
    </button>
  );
}

// Which computer this is: "win", "mac", "linux" or "phone"; null until the page is running.
export function useOs() {
  const [os, setOs] = useState(null);
  useEffect(() => {
    const ua = navigator.userAgent, p = navigator.userAgentData?.platform || navigator.platform || "";
    if (/Android|iPhone|iPad|iPod/.test(ua) || (/Mac/.test(p) && navigator.maxTouchPoints > 1)) setOs("phone");
    else if (/Win/.test(p)) setOs("win");
    else if (/Mac/.test(p)) setOs("mac");
    else if (/Linux|X11|CrOS/.test(p)) setOs("linux");
    else setOs("win");
  }, []);
  return os;
}

// The newest Stable version from GitHub ("v1.14.0"), remembered for an hour. null if GitHub can't be reached.
const RELEASE_API = "https://api.github.com/repos/Csabika-dev/beammp-easyserver/releases/latest";
export function useLatestVersion() {
  const [v, setV] = useState(null);
  useEffect(() => {
    try {
      const c = JSON.parse(sessionStorage.getItem("es-latest") || "null");
      if (c && Date.now() - c.t < 3600e3) { setV(c.v); return; }
    } catch {}
    let live = true;
    fetch(RELEASE_API).then(r => (r.ok ? r.json() : null)).then(d => {
      if (!live || !d?.tag_name) return;
      setV(d.tag_name);
      try { sessionStorage.setItem("es-latest", JSON.stringify({ v: d.tag_name, t: Date.now() })); } catch {}
    }).catch(() => {});
    return () => { live = false; };
  }, []);
  return v;
}

export const WIN_ZIP = GH + "/releases/latest/download/BeamMP-EasyServer-Windows.zip";

// The main download button. Windows gets the ZIP straight away (with the version on the button),
// Linux goes to the one-line install, Mac to the Rolling version (it's experimental, never Stable),
// and a phone is told it's for a PC. Before the page knows the computer it's a plain "Download".
export function DownloadButton({ home = "" }) {
  const versions = home + "#versions", start = home + "#start";
  const { t } = useSite();
  const os = useOs(), v = useLatestVersion();
  const c = t.common, fill = (s, o) => s.replace("{os}", o).replace("{v}", v || "");
  const pick = {
    win: [WIN_ZIP, v ? fill(c.downloadVFor, "Windows") : fill(c.downloadFor, "Windows")],
    linux: [start, fill(c.setupFor, "Linux")],
    mac: [versions, c.macRolling],
    phone: [start, c.onPhone],
  }[os] || [LATEST, c.download];
  return (
    <span className="dlbox">
      <a className="btn go" href={pick[0]} data-goatcounter-click={"download-" + (os || "stable")}>{pick[1]}</a>
      <small><a href={versions}>{c.otherSystems}</a></small>
    </span>
  );
}

function LangPicker() {
  const { lang, file, t, root } = useSite();
  const here = LANGS.find(l => l.code === lang);
  const ref = useRef(null);
  useEffect(() => {   // close when clicking elsewhere
    const off = e => { if (ref.current && !ref.current.contains(e.target)) ref.current.open = false; };
    document.addEventListener("click", off);
    return () => document.removeEventListener("click", off);
  }, []);
  const remember = code => { try { localStorage.setItem("es-site-lang", code); } catch {} };
  return (
    <details className="langpick" ref={ref}>
      <summary aria-label={t.nav.language}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c2.5 3 2.5 15 0 18M12 3c-2.5 3-2.5 15 0 18" /></svg>
        {here.code.toUpperCase()}
      </summary>
      <ul>
        {LANGS.map(l => (
          <li key={l.code}>
            <a href={pageHref(root, l.code, file)} hrefLang={l.code} lang={l.code}
              aria-current={l.code === lang ? "true" : undefined} onClick={() => remember(l.code)}>{l.name}</a>
          </li>
        ))}
      </ul>
    </details>
  );
}

export function Nav({ page, spy = [] }) {
  const { t, root } = useSite();
  const active = useScrollSpy(spy.map(s => s.id));
  const [scrolled, setScrolled] = useState(false);
  const bar = useRef(null);
  useEffect(() => {
    const on = () => {
      setScrolled(window.scrollY > 8);
      const h = document.documentElement.scrollHeight - innerHeight;
      if (bar.current) bar.current.style.transform = `scaleX(${h > 0 ? Math.min(1, scrollY / h) : 0})`;
    };
    on(); addEventListener("scroll", on, { passive: true });
    return () => removeEventListener("scroll", on);
  }, []);
  const link = (href, label, here, opt) => (
    <a key={href} className={opt ? "opt" : undefined} href={href} aria-current={here ? (page === "home" ? "location" : "page") : undefined}>{label}</a>
  );
  return (
    <nav className={"top" + (scrolled ? " scrolled" : "")}>
      <div className="wrap">
        <a className="logo" href="./"><img src={root + "img/logo.svg"} alt="" width="28" height="28" /><span><span className="long">BeamMP </span>EasyServer</span></a>
        <div className="links">
          {page === "home"
            ? spy.map(s => link("#" + s.id, t.nav[s.key], active === s.id, true))
            : link("./#start", t.nav.start, false, true)}
          {link("features.html", t.nav.features, page === "features")}
          {link("help.html", t.nav.help, page === "help")}
          <a className="opt" href={GH} data-goatcounter-click="github">GitHub</a>
        </div>
        <ThemeButton />
        <LangPicker />
      </div>
      <span className="progress" ref={bar} aria-hidden="true" />
    </nav>
  );
}

export function Footer({ note }) {
  const { t } = useSite();
  return (
    <footer><div className="wrap">
      {note && <p>{note}</p>}
      <p><Md s={t.common.license} /> <a href="privacy.html">{t.nav.privacy}</a></p>
    </div></footer>
  );
}

// A command with a copy button next to it.
export function Command({ children }) {
  const { t } = useSite();
  const [state, setState] = useState("idle");
  const pre = useRef(null);
  const copy = async () => {
    try { await navigator.clipboard.writeText(children); setState("done"); }
    catch {
      const r = document.createRange(); r.selectNodeContents(pre.current);
      const s = getSelection(); s.removeAllRanges(); s.addRange(r); setState("select");
    }
    setTimeout(() => setState("idle"), 1800);
  };
  return (
    <div className="cmd">
      <pre ref={pre} translate="no">{children}</pre>
      <button type="button" className={"copy js-only" + (state === "done" ? " done" : "")} onClick={copy} aria-live="polite">
        {state === "done" ? t.common.copied : state === "select" ? t.common.pressCtrlC : t.common.copy}
      </button>
    </div>
  );
}

// Something that opens and closes with its height animated. The content is
// always in the page, so search engines and people without JavaScript see it.
export function Fold({ title, children, open, onToggle, id, head = "h3", className = "" }) {
  const uid = useId();
  const H = head;
  return (
    <div className={"fold " + className + (open ? " open" : "")} id={id}>
      <H className="fold-head">
        <button type="button" aria-expanded={open} aria-controls={uid} onClick={onToggle}>
          <span className="fold-title">{title}</span><span className="fold-mark" aria-hidden="true" />
        </button>
      </H>
      <div className="fold-body" id={uid} role="region"><div>{children}</div></div>
    </div>
  );
}

// A list of Folds where any number can be open.
export function useOpenSet() {
  const [open, setOpen] = useState(() => new Set());
  const toggle = k => setOpen(s => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n; });
  return [open, toggle, setOpen];
}
