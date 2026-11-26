import { Blocks, useSite } from "./i18n.jsx";
import { Footer, Nav, Words } from "./shared.jsx";

// The privacy policy. All text is in the language files under "privacy".
export function Privacy() {
  const { t } = useSite();
  const p = t.privacy;
  return (
    <>
      <Nav page="privacy" />
      <main className="wrap">
        <header className="help-head">
          <h1 className="hop"><Words text={p.h1} /></h1>
          <span className="lane" aria-hidden="true" />
          <p>{p.lead}</p>
          <p className="legal-date">{p.updated}</p>
        </header>
        <nav className="legal-toc" aria-label={p.contents}>
          <b>{p.contents}</b>
          <ol>{p.sections.map(([id, title]) => <li key={id}><a href={"#" + id}>{title}</a></li>)}</ol>
        </nav>
        <div className="legal">
          {p.sections.map(([id, title, blocks]) => (
            <section key={id} id={id}>
              <h2>{title}</h2>
              <div><Blocks blocks={blocks} /></div>
            </section>
          ))}
        </div>
      </main>
      <Footer />
    </>
  );
}
