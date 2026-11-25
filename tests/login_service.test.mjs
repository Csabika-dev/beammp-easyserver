// The Discord sign-in service (login-service/worker.js) with a fake Discord: run with  node tests/login_service.test.mjs
import worker from "../login-service/worker.js";
const env = { MASTER_KEY: "m".repeat(40), DISCORD_CLIENT_ID: "1573599592535298089", DISCORD_CLIENT_SECRET: "s3cret" };
const enc = new TextEncoder();
const b64url = (buf) => Buffer.from(buf).toString("base64url");
const hk = (raw) => crypto.subtle.importKey("raw", typeof raw === "string" ? enc.encode(raw) : raw, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
const sign = async (k, t) => b64url(await crypto.subtle.sign("HMAC", k, enc.encode(t)));
let calls = [];
globalThis.fetch = async (url, o) => { calls.push(String(url)); 
  if (String(url).endsWith("/oauth2/token")) { if (!o.headers.Authorization.includes(btoa("1573599592535298089:s3cret"))) return new Response("", {status:401}); return new Response(JSON.stringify({access_token:"AT"})); }
  if (String(url).endsWith("/users/@me")) return new Response(JSON.stringify({id:"123456789012345678", username:"dani", global_name:"Dani"}));
  return new Response("{}"); };
const W = "https://login.example";
const req = (path, method="GET") => worker.fetch(new Request(W + path, { method }), env);
let fails = 0; const ok = (c, m) => { if (!c) { fails++; console.log("FAIL", m); } else console.log("ok", m); };

const reg = await (await req("/register", "POST")).json();
ok(/^[A-Za-z0-9_-]{24}$/.test(reg.inst) && reg.key.length === 43, "register");
const key = await hk(Buffer.from(reg.key, "base64url"));
const nonce = "N".repeat(32), ret = "http://192.168.1.20:30815/", exp = Math.floor(Date.now()/1000) + 600;
const sig = await sign(key, `start|${reg.inst}|${nonce}|${ret}|${exp}`);
const qs = (o) => "?" + new URLSearchParams(o);
let r = await req("/start" + qs({ inst: reg.inst, nonce, ret, exp, sig }));
ok(r.status === 302 && r.headers.get("Location").startsWith("https://discord.com/oauth2/authorize?"), "start redirects to Discord");
const loc = new URL(r.headers.get("Location"));
ok(loc.searchParams.get("redirect_uri") === W + "/cb" && loc.searchParams.get("scope") === "identify" && loc.searchParams.get("prompt") === "consent", "authorize params");
const state = loc.searchParams.get("state");
// tampering with the return address breaks the signature
r = await req("/start" + qs({ inst: reg.inst, nonce, ret: "http://evil.example/", exp, sig }));
ok(r.status === 400, "foreign return address refused");
r = await req("/start" + qs({ inst: reg.inst, nonce, ret: "http://192.168.1.20:30815/x", exp, sig }));
ok(r.status === 400, "path refused");
const reg2 = await (await req("/register", "POST")).json();
r = await req("/start" + qs({ inst: reg2.inst, nonce, ret, exp, sig }));
ok(r.status === 400, "signature from another dashboard refused");
// callback
r = await req("/cb" + qs({ code: "C", state }));
const to = r.headers.get("Location");
ok(r.status === 302 && to.startsWith(ret + "#dc="), "callback back to the dashboard");
const [note, nsig] = to.split("#dc=")[1].split(".");
ok(nsig === await sign(key, "assert|" + note), "note signed with the dashboard key");
const d = JSON.parse(Buffer.from(note, "base64url"));
ok(d.sub === "123456789012345678" && d.nonce === nonce && d.aud === ret && d.inst === reg.inst && d.name === "Dani", "note contents");
ok(calls.some(u => u.endsWith("/revoke")), "token revoked");
// state tampering
const [p, s] = state.split(".");
const evil = Buffer.from(JSON.stringify({ ...JSON.parse(Buffer.from(p, "base64url")), ret: "http://evil.example/" })).toString("base64url");
r = await req("/cb" + qs({ code: "C", state: evil + "." + s }));
ok(r.status === 400, "changed state refused");
r = await req("/cb" + qs({ error: "access_denied", state }));
ok(r.headers.get("Location") === ret + "#dc_err=denied", "cancel goes back");
r = await worker.fetch(new Request(W + "/"), {});
ok(r.status === 503, "no settings -> not set up");
process.exit(fails ? 1 : 0);
