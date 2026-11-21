// BeamMP EasyServer - "Sign in with Discord" helper (a Cloudflare Worker).
//
// Every EasyServer dashboard runs on someone's own computer, at an address Discord can't know in advance,
// and the Discord app's secret can't go into open-source code. This small service holds that secret and does
// the Discord part of the login, then sends the browser back to the dashboard with a signed note saying
// "this is Discord user X". It keeps nothing: no database, no logs of who signed in.
//
// How a dashboard and this service trust each other, without storing anything here:
//   POST /register  -> a new dashboard gets an id ("inst") and a key = HMAC(MASTER_KEY, "inst:" + inst).
//                      Only this service (which has MASTER_KEY) and that dashboard know the key.
//   GET  /start     -> the dashboard signs (inst, nonce, return address, expiry) with its key. Only an address the
//                      dashboard itself signed is ever used, so a stranger can't send someone's login somewhere else.
//   GET  /cb        -> Discord comes back here; we ask Discord who it is, then send the browser to the signed
//                      address with  #dc=<note>.<signature>  - signed with the same key, valid for 5 minutes.
//
// Settings (Cloudflare dashboard -> this Worker -> Settings -> Variables and secrets):
//   DISCORD_CLIENT_ID      (text)   the Discord application's ID
//   DISCORD_CLIENT_SECRET  (secret) the Discord application's Client Secret
//   MASTER_KEY             (secret) a long random string - changing it signs every dashboard out of this feature

const enc = new TextEncoder();
const b64url = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const fromB64url = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), (c) => c.charCodeAt(0));
const now = () => Math.floor(Date.now() / 1000);

async function hmacKey(raw) {
  return crypto.subtle.importKey("raw", typeof raw === "string" ? enc.encode(raw) : raw, { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}
async function sign(key, text) {
  return b64url(await crypto.subtle.sign("HMAC", key, enc.encode(text)));
}
async function verify(key, text, sig) {
  try {
    return await crypto.subtle.verify("HMAC", key, fromB64url(sig), enc.encode(text));   // constant time
  } catch {
    return false;
  }
}
async function instKey(env, inst) {
  const master = await hmacKey(env.MASTER_KEY);
  return hmacKey(new Uint8Array(await crypto.subtle.sign("HMAC", master, enc.encode("inst:" + inst))));
}

const INST_RE = /^[A-Za-z0-9_-]{24}$/;
const NONCE_RE = /^[A-Za-z0-9_-]{20,64}$/;
const SIG_RE = /^[A-Za-z0-9_-]{43}$/;

// The return address: the dashboard's own page, nothing else (no paths, no query, no login details).
function cleanReturn(ret) {
  if (typeof ret !== "string" || ret.length > 200) return null;
  let u;
  try { u = new URL(ret); } catch { return null; }
  if (!["http:", "https:"].includes(u.protocol) || u.username || u.password || u.pathname !== "/" || u.search || u.hash) return null;
  return u.origin + "/" === ret ? ret : null;
}

const headers = { "Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff" };
function page(status, title, text) {
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
  return new Response(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)}</title>
<body style="font:16px/1.5 system-ui,sans-serif;max-width:560px;margin:60px auto;padding:0 20px"><h1 style="font-size:22px">${esc(title)}</h1><p>${esc(text)}</p></body>`,
    { status, headers: { ...headers, "Content-Type": "text/html; charset=utf-8", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'" } });
}
const json = (status, body) => new Response(JSON.stringify(body), { status, headers: { ...headers, "Content-Type": "application/json" } });
const redirect = (to) => new Response(null, { status: 302, headers: { ...headers, Location: to } });

async function register(env) {
  const inst = b64url(crypto.getRandomValues(new Uint8Array(18)));
  const master = await hmacKey(env.MASTER_KEY);
  const key = b64url(await crypto.subtle.sign("HMAC", master, enc.encode("inst:" + inst)));
  return json(200, { inst, key });
}

async function start(env, url) {
  const p = url.searchParams;
  const inst = p.get("inst") || "", nonce = p.get("nonce") || "", sig = p.get("sig") || "";
  const ret = cleanReturn(p.get("ret")), exp = parseInt(p.get("exp") || "0", 10);
  if (!INST_RE.test(inst) || !NONCE_RE.test(nonce) || !SIG_RE.test(sig) || !ret || !(exp > now() && exp <= now() + 900)) {
    return page(400, "This sign-in link doesn't work", "Go back to the dashboard and press \"Sign in with Discord\" again.");
  }
  if (!(await verify(await instKey(env, inst), `start|${inst}|${nonce}|${ret}|${exp}`, sig))) {
    return page(400, "This sign-in link doesn't work", "It wasn't made by an EasyServer dashboard. Go back to the dashboard and try again.");
  }
  const payload = b64url(enc.encode(JSON.stringify({ inst, nonce, ret, exp })));
  const state = payload + "." + (await sign(await hmacKey(env.MASTER_KEY), "state|" + payload));
  const q = new URLSearchParams({ client_id: env.DISCORD_CLIENT_ID, response_type: "code", redirect_uri: url.origin + "/cb",
                                  scope: "identify", state, prompt: "consent" });
  return redirect("https://discord.com/oauth2/authorize?" + q);
}

async function callback(env, url) {
  const p = url.searchParams;
  const [payload, ssig] = (p.get("state") || "").split(".");
  if (!payload || !ssig || !(await verify(await hmacKey(env.MASTER_KEY), "state|" + payload, ssig))) {
    return page(400, "Sign-in didn't work", "Go back to the dashboard and press \"Sign in with Discord\" again.");
  }
  let st;
  try { st = JSON.parse(new TextDecoder().decode(fromB64url(payload))); } catch { return page(400, "Sign-in didn't work", "Try again."); }
  if (!(st.exp > now())) return page(400, "That took too long", "Go back to the dashboard and press \"Sign in with Discord\" again.");
  if (p.get("error")) return redirect(st.ret + "#dc_err=denied");
  const code = p.get("code");
  if (!code) return redirect(st.ret + "#dc_err=failed");

  const tok = await fetch("https://discord.com/api/oauth2/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", Authorization: "Basic " + btoa(env.DISCORD_CLIENT_ID + ":" + env.DISCORD_CLIENT_SECRET) },
    body: new URLSearchParams({ grant_type: "authorization_code", code, redirect_uri: url.origin + "/cb" }),
  }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (!tok || !tok.access_token) return redirect(st.ret + "#dc_err=failed");
  const me = await fetch("https://discord.com/api/v10/users/@me", { headers: { Authorization: "Bearer " + tok.access_token } })
    .then((r) => (r.ok ? r.json() : null)).catch(() => null);
  // we only needed to know who it is: give the access back straight away
  fetch("https://discord.com/api/oauth2/token/revoke", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", Authorization: "Basic " + btoa(env.DISCORD_CLIENT_ID + ":" + env.DISCORD_CLIENT_SECRET) },
    body: new URLSearchParams({ token: tok.access_token, token_type_hint: "access_token" }),
  }).catch(() => {});
  if (!me || !/^\d{5,25}$/.test(String(me.id || ""))) return redirect(st.ret + "#dc_err=failed");

  const note = b64url(enc.encode(JSON.stringify({
    v: 1, inst: st.inst, nonce: st.nonce, aud: st.ret, sub: String(me.id),
    user: String(me.username || "").slice(0, 40), name: String(me.global_name || me.username || "").slice(0, 40), exp: now() + 300,
  })));
  return redirect(st.ret + "#dc=" + note + "." + (await sign(await instKey(env, st.inst), "assert|" + note)));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!env.MASTER_KEY || !env.DISCORD_CLIENT_ID || !env.DISCORD_CLIENT_SECRET) {
      return page(503, "Not set up yet", "This sign-in service is missing its settings.");
    }
    if (request.method === "POST" && url.pathname === "/register") return register(env);
    if (request.method === "GET" && url.pathname === "/start") return start(env, url);
    if (request.method === "GET" && url.pathname === "/cb") return callback(env, url);
    if (request.method === "GET" && url.pathname === "/") {
      return page(200, "EasyServer sign-in", "This service lets team members of a BeamMP EasyServer dashboard sign in with Discord. It stores nothing. Source: github.com/Csabika-dev/beammp-easyserver (login-service).");
    }
    return page(404, "Not found", "Nothing here.");
  },
};
