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
export const everyText = n => n === 24 ? "Once a day" : `Every ${n} hour${n === 1 ? "" : "s"}`;
export const warnText = n => n ? `${n} min before` : "No countdown";

// Load data for one card; `again()` loads it again and redraws the card's inputs.
export function useLoad(fn, deps = []) {
  const [st, setSt] = useState({ d: null, v: 0, err: "" });
  const again = async () => {
    try { const d = await fn(); setSt(s => ({ d, v: s.v + 1, err: "" })); }
    catch (e) { setSt(s => ({ ...s, err: e.message })); }
  };
  useEffect(() => { again(); }, deps);
  return [st.d, again, st.v, st.err];
}
export const post = async (path, body, ms, after) => {
  try { const r = await L.api(path, { json: body }); L.toast(r.note, ms); if (after) after(r); return r; } catch (e) { L.toast(e.message, 6000); }
};
