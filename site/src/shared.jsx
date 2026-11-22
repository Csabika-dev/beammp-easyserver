import { Fragment, useEffect, useId, useRef, useState } from "react";
import { LANGS, Md, pageHref, useSite } from "./i18n.jsx";
import { GH } from "./links.js";

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
      <p><Md s={t.common.license} /></p>
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
