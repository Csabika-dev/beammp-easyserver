import { Md, useSite } from "./i18n.jsx";
import { DownloadButton, Footer, Nav, Words, useScrollSpy } from "./shared.jsx";
import { Tour } from "./Home.jsx";
import { useNews } from "./news.jsx";

function Jump() {
  const { t } = useSite();
  const f = t.features;
  const news = useNews();
  const parts = [["online", f.online], ["running", f.running], ...(news ? [["new", news.title]] : [])];
  const active = useScrollSpy(parts.map(p => p[0]));
  return (
    <div className="jump" aria-label={f.onPage}>
      <span>{f.onPage}</span>
      {parts.map(([id, label]) => <a key={id} href={"#" + id} aria-current={active === id ? "location" : undefined}>{label}</a>)}
    </div>
  );
}

const Rows = ({ rows, children }) => (
  <div className="rows" data-reveal="stagger">
    {children}
    {rows.map(([h, ps]) => <div className="row" key={h}><h3>{h}</h3><div>{ps.map((p, i) => <p key={i}><Md s={p} /></p>)}</div></div>)}
  </div>
);
const Head = ({ title, sub }) => <h2><span className="sweep">{title}</span><small>{sub}</small></h2>;

export function Features() {
  const { t, root } = useSite();
  const f = t.features;
  const news = useNews();
  return (
    <>
      <Nav page="features" />
      <main className="wrap">
        <div className="hero">
          <div className="hero-words">
            <h1 className="hop"><Words text={f.h1} /></h1>
            <span className="lane" aria-hidden="true" />
            <p>{f.lead}</p>
            <div className="btns">
              <DownloadButton home="./" />
              <a className="btn" href="./#start">{f.howInstall}</a>
            </div>
          </div>
          <div className="shot"><Tour /></div>
        </div>

        <Jump />

        <section id="online" data-reveal="">
          <Head title={f.online} sub={f.onlineSub} />
          <Rows rows={f.onlineRows} />
        </section>

        <section id="running" data-reveal="">
          <Head title={f.running} sub={f.runningSub} />
          <Rows rows={f.runningRows}>
            <div className="pair">
              <figure><img src={root + "img/players-dark.webp"} width="820" height="519" alt={f.playersAlt} loading="lazy" /><figcaption>{f.playersCap}</figcaption></figure>
              <figure><img className="phone" src={root + "img/phone.webp"} width="320" height="693" alt={f.phoneAlt} loading="lazy" /><figcaption>{f.phoneCap}</figcaption></figure>
            </div>
          </Rows>
        </section>

        {news && <section className="new" id="new" data-reveal="">
          <Head title={news.title} sub={news.sub} />
          <Rows rows={news.items.map(([h, p]) => [h, [p]])} />
        </section>}

        <div className="closing" data-reveal="">
          <h2 className="hop"><Words text={t.common.tryTitle} /></h2>
          <p>{f.closing}</p>
          <div className="btns">
            <DownloadButton home="./" />
            <a className="btn" href="help.html">{t.nav.help}</a>
          </div>
        </div>
      </main>
      <Footer note={f.footnote} />
    </>
  );
}
