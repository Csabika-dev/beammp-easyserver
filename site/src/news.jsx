import { LANGS, useSite } from "./i18n.jsx";

// Filled in at build time from CHANGELOG.md (see news.mjs): { version, status, items: [[title, text]] }.
const NEWS = typeof __NEWS__ !== "undefined" ? __NEWS__ : null;

// The "What's new" heading, note and cards in the page's language.
export function useNews() {
  const { lang, t } = useSite();
  if (!NEWS || !NEWS.items.length) return null;
  const own = LANGS.find(l => l.code === lang)?.text?.whatsNew?.[NEWS.version];
  return {
    title: t.common.newTitle.replace("{v}", NEWS.version),
    sub: NEWS.status === "rolling" ? t.common.newRolling : t.common.newStable,
    items: lang !== "en" && own?.length ? own : NEWS.items,
  };
}
