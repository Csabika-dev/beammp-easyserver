// Small pieces shared by the React pages (forms keep their values in the inputs; Save reads them by id).
import { useEffect, useState } from "react";
import * as L from "./legacy.js";

export const S = () => L.state();
export const $ = id => document.getElementById(id);
export const val = id => $(id).value, chk = id => $(id).checked;
export const lines = id => val(id).split("\n").map(x => x.trim()).filter(Boolean);
export const commas = id => val(id).split(",").map(x => x.trim()).filter(Boolean);
export const TIME = { colorScheme: "light dark", color: "inherit" };
export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const clock = t => new Date(t * 1000).toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" });
export const Pill = ({ on, children }) => <span className={"pill " + (on ? "good" : "")}><span className="dot" />{children}</span>;
export const Mono = ({ children }) => <span className="mono">{children}</span>;
export const Toggle = ({ id, on, title, children, style }) => <label className="toggle" style={style}><input type="checkbox" id={id} defaultChecked={!!on} /><span><b>{title}</b>{children !== undefined && <small>{children}</small>}</span></label>;
export const Warn = ({ children }) => <div className="issue warning"><span className="ic">⚠</span><span>{children}</span></div>;
export const Head = ({ title, pill, on }) => <div className="row"><h2 style={{ margin: 0 }}>{title}</h2><span className="spacer" /><Pill on={on}>{pill}</Pill></div>;
export const everyText = n => n === 24 ? "Once a day" : n === 1 ? "Every hour" : `Every ${n} hours`;
export const warnText = n => n ? `${n} min before` : "No countdown";

/* ---------------- remembered answers: pages open instantly with what they showed last time,
   then update quietly. Kept per server, only while this tab is open. */
const CACHE = new Map();
const ckey = path => (L.state().SERVER || "") + "|" + path;
export const cacheGet = path => CACHE.get(ckey(path));
export const cacheClear = () => CACHE.clear();
export async function cachedApi(path) { const d = await L.api(path); CACHE.set(ckey(path), d); return d; }
const fetchSrc = src => typeof src === "string" ? cachedApi(src) : Array.isArray(src) ? Promise.all(src.map(cachedApi)) : src();
const fromCache = src => {
  if (typeof src === "string") return cacheGet(src) ?? null;
  if (Array.isArray(src)) { const xs = src.map(cacheGet); return xs.every(x => x !== undefined) ? xs : null; }
  return null;
};
// Fetch a few answers in the background (one at a time, so the dashboard stays quick), so the pages are ready.
export async function prefetch(paths) {
  for (const p of paths) {
    if (CACHE.has(ckey(p))) continue;
    try { await cachedApi(p); } catch (e) {}
    await new Promise(r => setTimeout(r, 60));
  }
}

// Load data for one card: a path, a list of paths, or a function. `again()` loads it again; the card's inputs
// are drawn again (v goes up) only when the answer changed, so typing isn't lost when a fresh copy arrives.
export function useLoad(src, deps = []) {
  const [st, setSt] = useState(() => { const d = fromCache(src); return { d, v: d ? 1 : 0, err: "", j: d ? JSON.stringify(d) : "" }; });
  const again = async () => {
    try {
      const d = await fetchSrc(src), j = JSON.stringify(d);
      setSt(s => s.j === j ? { ...s, err: "" } : { d, v: s.v + 1, err: "", j });
    } catch (e) { if (e.message !== "Please log in") setSt(s => ({ ...s, err: e.message })); }
  };
  useEffect(() => { again(); }, deps);
  return [st.d, again, st.v, st.err];
}

/* ---------------- placeholders while a page loads (grey shapes that shimmer, then the page rises in) */
const W = [100, 92, 78, 96, 64, 88];
export const Skel = ({ w = "100%", h = 12, style }) => <div className="skel" style={{ width: w, height: h, ...style }} />;
export const SkelCard = ({ lines = 3, style }) => <div className="card skelcard" aria-hidden="true" style={style}>
  <Skel w="38%" h={16} style={{ marginBottom: 16 }} />{Array.from({ length: lines }, (_, i) => <Skel key={i} w={W[i % W.length] + "%"} style={{ marginTop: 10 }} />)}</div>;
export const SkelPage = ({ cards = 4 }) => <div aria-busy="true" aria-label="Loading">
  <Skel w={220} h={28} /><Skel w="48%" h={13} style={{ margin: "12px 0 22px" }} />
  <div className="grid g2">{Array.from({ length: cards }, (_, i) => <SkelCard key={i} lines={i % 2 ? 4 : 3} />)}</div></div>;

export const post = async (path, body, ms, after) => {
  try { const r = await L.api(path, { json: body }); L.toast(r.note, ms); if (after) after(r); return r; } catch (e) { L.toast(e.message, 6000); }
};
