import { Children, isValidElement, useEffect, useId, useRef, useState } from "react";

export const GH = "https://github.com/Csabika-dev/beammp-easyserver";
export const LATEST = GH + "/releases/latest";
export const ASK = GH + "/discussions/new?category=q-a";

// Plain text of a piece of JSX, for search. Works the same on the server and in the browser.
export function textOf(node) {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join(" ");
  if (isValidElement(node)) return textOf(node.props.children);
  return "";
}

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

export function Nav({ page, spy = [] }) {
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
  const home = page === "home" ? "" : "./";
  const link = (href, label, here, opt) => (
    <a key={href} className={opt ? "opt" : undefined} href={href} aria-current={here ? (page === "home" ? "location" : "page") : undefined}>{label}</a>
  );
  return (
    <nav className={"top" + (scrolled ? " scrolled" : "")}>
      <div className="wrap">
        <a className="logo" href="./"><img src="img/logo.svg" alt="" width="28" height="28" /><span><span className="long">BeamMP </span>EasyServer</span></a>
        <div className="links">
          {page === "home"
            ? spy.map(s => link("#" + s.id, s.label, active === s.id, s.opt))
            : link(home + "#start", "Get started", false, true)}
          {link("features.html", "Features", page === "features")}
          {link("help.html", "Help", page === "help")}
          <a href={GH} data-goatcounter-click="github">GitHub</a>
        </div>
      </div>
      <span className="progress" ref={bar} aria-hidden="true" />
    </nav>
  );
}

export function Footer({ children }) {
  return (
    <footer><div className="wrap">
      {children}
      <p>MIT license. Not made by or affiliated with the BeamMP team or BeamNG GmbH. EasyServer builds on their work and on many mod and plugin authors: <a href={GH + "#-credits"}>see the credits</a>.</p>
    </div></footer>
  );
}

// A command with a copy button next to it.
export function Command({ children }) {
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
      <pre ref={pre}>{children}</pre>
      <button type="button" className={"copy js-only" + (state === "done" ? " done" : "")} onClick={copy} aria-live="polite">
        {state === "done" ? "Copied" : state === "select" ? "Press Ctrl+C" : "Copy"}
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

export const count = (arr, f) => arr.filter(f).length;
export const kids = c => Children.toArray(c);
