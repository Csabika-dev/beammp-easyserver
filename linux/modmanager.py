#!/usr/bin/env python3
"""BeamMP EasyServer - Mod Manager web page.

Open http://<server-ip>:30815 from any PC/phone on your network and drag mod
.zip files onto the page. Uses only the Python standard library.
Not affiliated with the BeamMP team.
"""
import base64
import hmac
import shutil
import html
import json
import os
import re
import sys
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modscan  # noqa: E402  (mod safety check, same folder)

SERVER_DIR = os.environ.get("BEAMMP_DIR", "/opt/beammp-server")
CLIENT_DIR = os.path.join(SERVER_DIR, "Resources", "Client")
DISABLED_DIR = os.path.join(SERVER_DIR, "Resources", "Client-disabled")
TMP_DIR = os.path.join(SERVER_DIR, "Resources", ".uploading")
QUARANTINE_DIR = os.path.join(SERVER_DIR, "Resources", "Quarantine")
CONFIG = os.path.join(SERVER_DIR, "ServerConfig.toml")
SETTINGS = os.environ.get("MODS_SETTINGS", "/etc/beammp-easyserver/modmanager.conf")

BUILTIN_MAPS = ["gridmap_v2", "west_coast_usa", "east_coast_usa", "utah", "italy",
                "jungle_rock_island", "industrial", "small_island",
                "automation_test_track", "hirochi_raceway", "johnson_valley",
                "derby", "driver_training"]


def load_settings():
    s = {"port": "30815", "user": "admin", "password": ""}
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    s[k.strip().lower()] = v.strip()
    except FileNotFoundError:
        pass
    # the password is kept encrypted and handed over in memory by launch.sh
    if os.environ.get("MODS_PASSWORD"):
        s["password"] = os.environ["MODS_PASSWORD"]
    return s


SET = load_settings()


def safe_name(name):
    name = os.path.basename(urllib.parse.unquote(name or "")).strip()
    name = re.sub(r"[^A-Za-z0-9._\- ()\[\]+]", "_", name)
    if not name.lower().endswith(".zip") or name.startswith("."):
        return None
    return name


def maps_in_zip(path):
    try:
        with zipfile.ZipFile(path) as z:
            found = set()
            for n in z.namelist():
                m = re.match(r"^levels/([^/]+)/(info\.json|main\.level\.json|[^/]+\.mis)$", n, re.I)
                if m:
                    found.add(m.group(1))
            return sorted(found)
    except (zipfile.BadZipFile, OSError):
        return None  # None = broken zip


def current_map():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            m = re.search(r'(?m)^\s*Map\s*=\s*"/levels/([^/"]+)/', f.read())
            return m.group(1) if m else ""
    except OSError:
        return ""


def set_map(name):
    if not re.fullmatch(r"[A-Za-z0-9_\-.]+", name):
        raise ValueError("bad map name")
    with open(CONFIG, encoding="utf-8") as f:
        txt = f.read()
    new_line = 'Map = "/levels/%s/info.json"' % name
    if re.search(r"(?m)^\s*Map\s*=", txt):
        txt = re.sub(r"(?m)^\s*Map\s*=.*$", new_line, txt, count=1)
    else:
        txt = txt.replace("[General]", "[General]\n" + new_line, 1)
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.write(txt)
    # touching the mods folder triggers the automatic server restart
    os.utime(CLIENT_DIR, None)


def list_mods():
    out = []
    for folder, enabled in ((CLIENT_DIR, True), (DISABLED_DIR, False)):
        if not os.path.isdir(folder):
            continue
        for n in sorted(os.listdir(folder), key=str.lower):
            p = os.path.join(folder, n)
            if n.lower().endswith(".zip") and os.path.isfile(p):
                r = modscan.cached_result(p)
                out.append({"name": n, "size": os.path.getsize(p), "enabled": enabled,
                            "maps": maps_in_zip(p) or [],
                            "safety": r["verdict"] if r else "unchecked",
                            "reasons": r["reasons"] if r else []})
    return out


def list_quarantine():
    out = []
    if os.path.isdir(QUARANTINE_DIR):
        for n in sorted(os.listdir(QUARANTINE_DIR), key=str.lower):
            if n.lower().endswith(".zip"):
                why = ""
                try:
                    with open(os.path.join(QUARANTINE_DIR, n + ".why.txt"), encoding="utf-8") as f:
                        why = f.read()
                except OSError:
                    pass
                out.append({"name": n, "why": why})
    return out


def active_checks():
    c = ["built-in checks"]
    if shutil.which("clamdscan") or shutil.which("clamscan"):
        c.append("ClamAV antivirus")
    if os.environ.get("VT_API_KEY"):
        c.append("VirusTotal")
    return c


PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BeamMP Mods</title>
<style>
:root{--bg:#14161a;--card:#1d2026;--line:#2c313a;--text:#e8eaed;--dim:#9aa0a6;--acc:#f58220;--ok:#3ecf8e;--bad:#ef5350}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--text)}
main{max-width:860px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--dim);margin:0 0 20px}
#drop{border:2px dashed var(--line);border-radius:14px;padding:38px 16px;text-align:center;background:var(--card);cursor:pointer;transition:.15s}
#drop.over{border-color:var(--acc);background:#2a2118}#drop b{color:var(--acc)}
.bar{height:6px;background:var(--line);border-radius:3px;margin-top:6px;overflow:hidden}.bar i{display:block;height:100%;background:var(--acc);width:0}
.up{margin-top:12px;font-size:14px}
.row{display:flex;gap:12px;align-items:center;padding:12px 14px;border-bottom:1px solid var(--line)}
.list{background:var(--card);border-radius:14px;margin-top:22px;overflow:hidden}
.name{flex:1;min-width:0;overflow-wrap:anywhere}.size{color:var(--dim);font-size:13px;white-space:nowrap}
.off .name{color:var(--dim);text-decoration:line-through}
.tag{font-size:12px;padding:2px 8px;border-radius:99px;background:#26303d;color:#8ab4f8;margin-left:6px}
button,select{font:inherit;border:1px solid var(--line);background:#262a31;color:var(--text);border-radius:8px;padding:6px 10px;cursor:pointer}
button:hover{border-color:var(--acc)}button.del:hover{border-color:var(--bad);color:var(--bad)}
.mapbox{background:var(--card);border-radius:14px;margin-top:22px;padding:14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.empty{padding:22px;color:var(--dim);text-align:center}
#toast{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);background:#262a31;border:1px solid var(--line);padding:10px 16px;border-radius:10px;display:none}
.note{color:var(--dim);font-size:13px;margin-top:18px}
.badge{font-size:12px;padding:2px 8px;border-radius:99px;margin-left:6px;white-space:nowrap}
.b-clean{background:#16352a;color:var(--ok)}.b-warning{background:#3a2f12;color:#f6c344}.b-unchecked{background:#2a2d33;color:var(--dim)}
.why{color:#f6c344;font-size:13px;margin-top:3px}.qwhy{color:var(--bad);font-size:13px;white-space:pre-wrap;margin-top:3px}
.shield{background:var(--card);border-radius:14px;padding:10px 14px;margin:16px 0 0;font-size:14px;color:var(--dim)}
h2{font-size:16px;margin:26px 0 0}
</style></head><body><main>
<h1>BeamMP Mods</h1>
<p class="sub">Drop mod <b>.zip</b> files here. The server restarts by itself about 15 seconds after a change, and players download the mods when they join.</p>
<div id="drop"><b>Drag &amp; drop mods here</b><br>or click to choose files
<input id="file" type="file" accept=".zip" multiple hidden></div>
<div id="uploads"></div>
<div class="shield">&#128737; Every mod is checked for viruses before players get it. Active: <span id="checks">...</span></div>
<div class="mapbox">Map: <select id="map"></select><button onclick="applyMap()">Use this map</button><span id="curmap" class="size"></span></div>
<div class="list" id="list"></div>
<div id="qbox" style="display:none"><h2>&#9940; Blocked mods (quarantine)</h2><div class="list" id="qlist" style="margin-top:10px"></div></div>
<p class="note">Mods marked &#9888; passed the virus check but have something unusual (for example a Lua script that can run commands). Only keep them if you trust where they came from. Turning a mod off keeps the file but stops sending it to players. The server restarts automatically after every change, which disconnects anyone who is playing.</p>
</main><div id="toast"></div>
<script>
const $=s=>document.querySelector(s);
const BUILTIN=__BUILTIN__;
function toast(t){const e=$('#toast');e.textContent=t;e.style.display='block';clearTimeout(e._t);e._t=setTimeout(()=>e.style.display='none',3500)}
function fmt(b){return b>1048576?(b/1048576).toFixed(1)+' MB':(b/1024).toFixed(0)+' KB'}
function esc(s){return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function api(path,opt){const r=await fetch(path,opt);if(!r.ok)throw new Error(await r.text()||r.status);return r.json()}
async function load(){
  const d=await api('api/mods');const L=$('#list');
  L.innerHTML=d.mods.length?'':'<div class="empty">No mods yet</div>';
  for(const m of d.mods){
    const row=document.createElement('div');row.className='row'+(m.enabled?'':' off');
    const B={clean:'&#10003; safe',warning:'&#9888; check',unchecked:'not checked yet'};
    row.innerHTML=`<div class="name">${esc(m.name)}<span class="badge b-${m.safety}">${B[m.safety]||''}</span>${m.maps.map(x=>'<span class="tag">map: '+esc(x)+'</span>').join('')}${m.reasons.length?'<div class="why">'+m.reasons.map(esc).join('<br>')+'</div>':''}</div>
      <span class="size">${fmt(m.size)}</span>
      <button data-a="toggle">${m.enabled?'Turn off':'Turn on'}</button><button class="del" data-a="delete">Delete</button>`;
    row.querySelectorAll('button').forEach(b=>b.onclick=async()=>{
      if(b.dataset.a==='delete'&&!confirm('Delete '+m.name+'?'))return;
      try{await api('api/'+b.dataset.a+'?name='+encodeURIComponent(m.name),{method:'POST'});load();toast('Done - server restarts in ~15 s')}catch(e){toast('Error: '+e.message)}
    });
    L.appendChild(row);
  }
  const sel=$('#map');const modMaps=d.mods.filter(m=>m.enabled).flatMap(m=>m.maps);
  sel.innerHTML='';
  for(const [label,list] of [['Mod maps',modMaps],['Built-in maps',BUILTIN]]){
    if(!list.length)continue;const g=document.createElement('optgroup');g.label=label;
    for(const x of list){const o=new Option(x,x);if(x===d.map)o.selected=true;g.appendChild(o)}sel.appendChild(g)}
  $('#curmap').textContent='current: '+(d.map||'?');
  $('#checks').textContent=d.checks.join(' + ');
  const Q=$('#qlist');Q.innerHTML='';$('#qbox').style.display=d.quarantine.length?'block':'none';
  for(const q of d.quarantine){const r=document.createElement('div');r.className='row';
    r.innerHTML=`<div class="name">${esc(q.name)}<div class="qwhy">${esc(q.why)}</div></div><button class="del">Delete</button>`;
    r.querySelector('button').onclick=async()=>{await api('api/qdelete?name='+encodeURIComponent(q.name),{method:'POST'});load()};Q.appendChild(r)}
}
async function applyMap(){try{await api('api/map?name='+encodeURIComponent($('#map').value),{method:'POST'});toast('Map changed - server restarts in ~15 s');load()}catch(e){toast('Error: '+e.message)}}
function upload(f){
  return new Promise(res=>{
    const box=document.createElement('div');box.className='up';box.innerHTML=esc(f.name)+'<div class="bar"><i></i></div>';
    $('#uploads').appendChild(box);
    if(!/\.zip$/i.test(f.name)){box.innerHTML=esc(f.name)+' - <span style="color:var(--bad)">only .zip files</span>';return res()}
    const x=new XMLHttpRequest();x.open('PUT','api/upload?name='+encodeURIComponent(f.name));
    x.upload.onprogress=e=>{if(e.lengthComputable)box.querySelector('i').style.width=(e.loaded/e.total*100)+'%'};
    x.upload.onload=()=>{box.querySelector('.bar').insertAdjacentHTML('afterend','<div class="size">checking for viruses...</div>')};
    x.onload=()=>{let j={};try{j=JSON.parse(x.responseText)}catch(e){}
      if(x.status==422&&j.blocked){box.innerHTML=esc(f.name)+' - <b style="color:var(--bad)">BLOCKED, not uploaded:</b><div class="qwhy">'+j.reasons.map(esc).join('<br>')+'</div>';return res()}
      if(x.status!=200){box.innerHTML=esc(f.name)+' - <span style="color:var(--bad)">'+esc(x.responseText||'failed')+'</span>';return res()}
      let msg='uploaded and checked ('+(j.checks||[]).join(' + ')+')';if(j.maps&&j.maps.length)msg+=' - contains map: '+j.maps.join(', ')+' (pick it below)';
      box.innerHTML=esc(f.name)+' - <span style="color:var(--ok)">'+esc(msg)+'</span>'+(j.safety=='warning'?'<div class="why">&#9888; '+j.reasons.map(esc).join('<br>&#9888; ')+'</div>':'');res()};
    x.onerror=()=>{box.innerHTML=esc(f.name)+' - <span style="color:var(--bad)">failed</span>';res()};
    x.send(f);
  });
}
async function handle(files){for(const f of files)await upload(f);load()}
const D=$('#drop');D.onclick=()=>$('#file').click();$('#file').onchange=e=>handle(e.target.files);
['dragenter','dragover'].forEach(t=>D.addEventListener(t,e=>{e.preventDefault();D.classList.add('over')}));
['dragleave','drop'].forEach(t=>D.addEventListener(t,e=>{e.preventDefault();D.classList.remove('over')}));
D.addEventListener('drop',e=>handle(e.dataTransfer.files));
load().catch(e=>toast('Error: '+e.message));
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "BeamMPEasyMods/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    # ---- helpers ----
    def authed(self):
        if not SET.get("password"):
            return True
        hdr = self.headers.get("Authorization", "")
        if hdr.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(hdr[6:]).decode("utf-8").partition(":")
            except Exception:
                user, pw = "", ""
            if hmac.compare_digest(user, SET["user"]) and hmac.compare_digest(pw, SET["password"]):
                return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="BeamMP Mods"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else (
            json.dumps(body) if ctype == "application/json" else body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def err(self, code, msg):
        self.send(code, msg, "text/plain")

    def route(self):
        u = urllib.parse.urlparse(self.path)
        return u.path.rstrip("/") or "/", urllib.parse.parse_qs(u.query)

    # ---- GET ----
    def do_GET(self):
        if not self.authed():
            return
        path, _ = self.route()
        if path == "/":
            self.send(200, PAGE.replace("__BUILTIN__", json.dumps(BUILTIN_MAPS)), "text/html")
        elif path == "/api/mods":
            self.send(200, {"mods": list_mods(), "map": current_map(),
                            "quarantine": list_quarantine(), "checks": active_checks()})
        else:
            self.err(404, "not found")

    # ---- PUT upload ----
    def do_PUT(self):
        if not self.authed():
            return
        path, q = self.route()
        if path != "/api/upload":
            return self.err(404, "not found")
        name = safe_name(q.get("name", [""])[0])
        if not name:
            return self.err(400, "Only .zip files can be uploaded")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return self.err(411, "empty upload")
        os.makedirs(TMP_DIR, exist_ok=True)
        tmp = os.path.join(TMP_DIR, name)
        left = length
        with open(tmp, "wb") as f:
            while left > 0:
                chunk = self.rfile.read(min(1 << 20, left))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        if left:
            os.remove(tmp)
            return self.err(400, "upload interrupted")
        # ---- safety check BEFORE players can get it ----
        result = modscan.scan(tmp)
        if result["verdict"] == "blocked":
            os.remove(tmp)
            return self.send(422, {"blocked": True, "reasons": result["reasons"]})
        maps = maps_in_zip(tmp) or []
        # remove a disabled copy with the same name, then move into place
        try:
            os.remove(os.path.join(DISABLED_DIR, name))
        except FileNotFoundError:
            pass
        os.replace(tmp, os.path.join(CLIENT_DIR, name))
        self.send(200, {"ok": True, "name": name, "maps": maps,
                        "safety": result["verdict"], "reasons": result["reasons"],
                        "checks": result["checks"]})

    # ---- POST actions ----
    def do_POST(self):
        if not self.authed():
            return
        path, q = self.route()
        if path == "/api/map":
            try:
                set_map(q.get("name", [""])[0])
            except (ValueError, OSError) as e:
                return self.err(400, str(e))
            return self.send(200, {"ok": True})
        name = safe_name(q.get("name", [""])[0])
        if not name:
            return self.err(400, "bad name")
        on, off = os.path.join(CLIENT_DIR, name), os.path.join(DISABLED_DIR, name)
        try:
            if path == "/api/qdelete":
                for p in (os.path.join(QUARANTINE_DIR, name), os.path.join(QUARANTINE_DIR, name + ".why.txt")):
                    if os.path.exists(p):
                        os.remove(p)
                return self.send(200, {"ok": True})
            if path == "/api/delete":
                for p in (on, off):
                    if os.path.exists(p):
                        os.remove(p)
            elif path == "/api/toggle":
                os.makedirs(DISABLED_DIR, exist_ok=True)
                if os.path.exists(on):
                    os.replace(on, off)
                elif os.path.exists(off):
                    os.replace(off, on)
                    return self.send(200, {"ok": True})
                else:
                    return self.err(404, "not found")
                os.utime(CLIENT_DIR, None)  # make sure the restart triggers
            else:
                return self.err(404, "not found")
        except OSError as e:
            return self.err(500, str(e))
        self.send(200, {"ok": True})


def main():
    if not SET.get("password"):
        sys.exit("No mod page password set - refusing to start without one. "
                 "Re-run the installer to create it.")
    os.makedirs(CLIENT_DIR, exist_ok=True)
    port = int(os.environ.get("MODS_PORT", SET.get("port", "30815")))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("BeamMP mod manager on port %d (dir %s)" % (port, CLIENT_DIR), flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
