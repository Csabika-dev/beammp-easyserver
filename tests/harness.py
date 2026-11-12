"""Test harness: runs the real dashboard in-process against a throw-away server folder.

Nothing is installed and nothing needs root. The root helper is replaced by a fake that keeps
"encrypted" keys in memory, and the BeamMP server is never started, so the tests run the same
on a laptop and on GitHub's test machines. Import this module before anything else imports
dashboard.py: it sets BEAMMP_DIR first.
"""
import http.cookiejar
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = tempfile.mkdtemp(prefix="es-test-")
SRV = os.path.join(TMP, "srv")
for sub in ("Resources/Client", "Resources/Client-disabled", "Resources/Quarantine", "Resources/Server/EasyServerStats"):
    os.makedirs(os.path.join(SRV, sub), exist_ok=True)
with open(os.path.join(SRV, "ServerConfig.toml"), "w") as f:
    f.write('[General]\nName = "Test server"\nPort = 30814\nAuthKey = ""\nAllowGuests = true\n'
            'MaxPlayers = 8\nMaxCars = 1\nMap = "/levels/gridmap_v2/info.json"\nPrivate = true\n'
            'Description = "test"\nLogChat = true\nDebug = false\n')
shutil.copy(os.path.join(ROOT, "dashboard", "EasyServerStats", "main.lua"),
            os.path.join(SRV, "Resources", "Server", "EasyServerStats", "main.lua"))
os.environ["BEAMMP_DIR"] = SRV
sys.path.insert(0, os.path.join(ROOT, "dashboard"))

import dashboard as D  # noqa: E402

FAKE_SECRETS = {}


def fake_control(action, timeout=240, **kw):
    """Stands in for linux/control.py (the root helper)."""
    if action == "set-secret":
        FAKE_SECRETS[kw["name"]] = kw["value"]
        return {"ok": True, "msg": "saved"}
    if action == "unset-secret":
        FAKE_SECRETS.pop(kw["name"], None)
        return {"ok": True, "msg": "saved"}
    if action == "create-server":
        d = os.path.join(D.SERVERS_DIR, kw["server"])
        for sub in ("Resources/Client", "Resources/Client-disabled", "Resources/Quarantine", "Resources/Server/EasyServerStats"):
            os.makedirs(os.path.join(d, sub), exist_ok=True)
        with open(os.path.join(d, "ServerConfig.toml"), "w") as f:
            f.write(kw["config"])
        return {"ok": True, "msg": "created. "}
    if action == "delete-server":
        shutil.rmtree(os.path.join(D.SERVERS_DIR, kw["server"]), ignore_errors=True)
        return {"ok": True, "msg": "deleted"}
    if action == "power-status":
        return {"ok": True, "adapters": [], "can_sleep": False, "rtc": False}
    return {"ok": True, "msg": "fake"}


D.control = fake_control
D.Handler.log_message = lambda self, *a: None           # keep test output readable
D.ServerManager.status = lambda self: {"state": "stopped", "pid": 0, "uptime": 0, "restarts": 0}
D.ServerManager.action = lambda self, a: {"ok": True, "msg": "fake"}

_started = {}
PASSWORD = "test-owner-password-1"


def start():
    """Start the dashboard once (plain HTTP on a free local port). Returns the base URL."""
    if "url" in _started:
        return _started["url"]
    D.load_servers()
    D.APP = D.App()
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    httpd = D.Server(("127.0.0.1", port), None)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    _started.update(url="http://127.0.0.1:%d" % port, httpd=httpd)
    return _started["url"]


class Client:
    """A browser-like client: keeps the session cookie and sends the CSRF token and Origin."""

    def __init__(self, base, origin=True):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = ""
        self.origin = origin

    def call(self, path, body=None, method=None, headers=None, raw=None):
        h = {}
        if self.origin:
            h["Origin"] = self.base
        if self.csrf:
            h["X-ES-CSRF"] = self.csrf
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        req = urllib.request.Request(self.base + path, data=data, headers=h,
                                     method=method or ("POST" if data is not None else "GET"))
        try:
            with self.op.open(req, timeout=30) as r:
                return r.status, _parse(r.read()), r.headers
        except urllib.error.HTTPError as e:
            return e.code, _parse(e.read()), e.headers

    def refresh(self):
        self.csrf = self.call("/api/session")[1].get("csrf", "")

    def login(self, password=PASSWORD, user=None, remember=False):
        self.refresh()
        body = {"password": password}
        if user:
            body["user"] = user
        if remember:
            body["remember"] = True
        st = self.call("/api/login", body)[0]
        self.refresh()
        return st


def _parse(b):
    try:
        return json.loads(b or b"{}")
    except ValueError:
        return b


def owner():
    """A logged-in owner session (sets the first password if needed)."""
    base = start()
    c = Client(base)
    c.refresh()
    if not D.APP.secrets.has("MODS_PASSWORD"):
        st = c.call("/api/setup", {"password": PASSWORD})[0]
        assert st == 200, st
    assert c.login() == 200
    return c


def routes():
    """Every API route the dashboard answers: (method, path) from the handler names."""
    out = []
    for name in dir(D.Handler):
        for m in ("get", "post", "put", "delete"):
            if name.startswith(m + "_"):
                out.append((m.upper(), "/api/" + name[len(m) + 1:].replace("_", "/")))
    return out
