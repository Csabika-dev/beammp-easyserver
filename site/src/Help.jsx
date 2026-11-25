import { useEffect, useMemo, useState } from "react";
import { Blocks, blocksText, Md, useSite } from "./i18n.jsx";
import { ASK, Fold, Footer, GH, Nav, Words, useOpenSet } from "./shared.jsx";

const CAT_ORDER = ["start", "join", "mods", "dash", "discord", "trouble"];
const escape = w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function Marked({ text, words }) {
  if (!words.length) return text;
  const re = new RegExp("(" + words.map(escape).join("|") + ")", "gi");
  return text.split(re).map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : part));
}

function CopyLink({ id }) {
  const { t } = useSite();
  const [done, setDone] = useState(false);
  const copy = () => {
    const url = location.href.split("#")[0] + "#" + id;
    (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(
      () => { setDone(true); setTimeout(() => setDone(false), 1800); },
      () => history.replaceState(null, "", "#" + id));
  };
  return <button type="button" className="link js-only" onClick={copy}>{done ? t.help.linkCopied : t.help.copyLink}</button>;
}

export function Help() {
  const { t, lang } = useSite();
  const h = t.help;
  const QA = useMemo(() => h.qa.map(([id, cat, q, a, top]) => ({ id, cat, q, a, top: !!top, text: (q + " " + blocksText(a)).toLocaleLowerCase(lang) })), [h, lang]);
  const [query, setQuery] = useState("");
  const [cat, setCat] = useState("all");
  const [open, toggle, setOpen] = useOpenSet();

  // Open the answer a shared link points to.
  useEffect(() => {
    const go = () => {
      const id = decodeURIComponent(location.hash.slice(1));
      if (!QA.some(x => x.id === id)) return;
      setCat("all"); setQuery("");
      setOpen(s => new Set(s).add(id));
      requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ block: "start" }));
    };
    go(); addEventListener("hashchange", go);
    return () => removeEventListener("hashchange", go);
  }, []);

  const words = useMemo(() => query.toLocaleLowerCase(lang).split(/\s+/).filter(w => w.length > 1), [query]);
  const shown = QA.filter(x => (cat === "all" || x.cat === cat) && words.every(w => x.text.includes(w)));
  // A short list of matches opens by itself, so the answers are right there.
  useEffect(() => { if (words.length && shown.length <= 3) setOpen(new Set(shown.map(x => x.id))); }, [words.join(" "), cat]);
  const flip = id => { toggle(id); if (!open.has(id)) history.replaceState(null, "", "#" + id); };
  // "question" / "questions"; a language with more plural forms can give an object (see pl.js).
  const n = k => {
    const form = new Intl.PluralRules(lang).select(k);
    if (form === "one") return h.question;
    return typeof h.questions === "string" ? h.questions : h.questions[form] || h.questions.other;
  };

  // Grouped by topic when nothing is searched, one flat list of matches otherwise.
  const groups = words.length ? [[null, shown]] : CAT_ORDER.map(k => [h.cats[k], shown.filter(x => x.cat === k)]).filter(g => g[1].length);

  return (
    <>
      <Nav page="help" />
      <main className="wrap">
        <header className="help-head">
          <h1 className="hop"><Words text={h.h1} /></h1>
          <span className="lane" aria-hidden="true" />
          <p>{h.lead}</p>
          <div className="search js-only">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
            <input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder={h.search} autoComplete="off" aria-label={h.searchLabel} />
          </div>
          <div className="chips js-only" role="group" aria-label={h.topicsLabel}>
            {[["all", h.all], ...CAT_ORDER.map(k => [k, h.cats[k]])].map(([k, label]) => (
              <button key={k} type="button" aria-pressed={cat === k} onClick={() => setCat(k)}>
                {label}<span>{k === "all" ? QA.length : QA.filter(x => x.cat === k).length}</span>
              </button>
            ))}
          </div>
        </header>

        <div className="answers">
          <p className="count js-only" aria-live="polite">{shown.length} {n(shown.length)}{words.length ? " · " + h.match : ""}</p>
          {groups.map(([label, list]) => (
            <section key={label || "results"} className="topic">
              <h2><span className="sweep">{label || h.results}</span><small>{label ? list.length + " " + n(list.length) : h.marked}</small></h2>
              <div className="folds">
                {list.map(x => (
                  <Fold key={x.id} id={x.id} open={open.has(x.id)} onToggle={() => flip(x.id)}
                    title={<><Marked text={x.q} words={words} />{x.top && <span className="badge">{h.mostAsked}</span>}</>}>
                    <div className="answer"><Blocks blocks={x.a} /><CopyLink id={x.id} /></div>
                  </Fold>
                ))}
              </div>
            </section>
          ))}
          {!shown.length && <p className="empty"><Md s={h.empty} /></p>}
        </div>

        <div className="closing" data-reveal="">
          <h2 className="hop"><Words text={h.askTitle} /></h2>
          <p>{h.askText}</p>
          <div className="btns">
            <a className="btn go" href={ASK}>{h.askButton}</a>
            <a className="btn" href={GH + "/discussions"}>{h.forumButton}</a>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
