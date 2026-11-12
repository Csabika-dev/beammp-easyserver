#!/usr/bin/env python3
"""BeamMP EasyServer - management dashboard.

A web dashboard for the BeamMP server, reachable from any PC or phone:
server control, config editor + validator, mods (with virus check), player
analytics, port checker, update manager, notifications (page, Discord,
email), import/export, logs, dark/light mode and secure remote access
(HTTPS + two-step login).

Standard library only. Runs on Linux (systemd service, as the unprivileged
"beammp-dash" user) and on Windows (portable Python, as the logged-in user).
Not affiliated with the BeamMP team.
"""
import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import shutil
import smtplib
import socket
import ssl
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EASY_VERSION = "1.6.0"
REPO = "Csabika-dev/beammp-easyserver"
BEAMMP_REPO = "BeamMP/BeamMP-Server"
IS_WIN = os.name == "nt"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modscan  # noqa: E402
import tlsgen   # noqa: E402

# ----------------------------------------------------------------------------- paths
if IS_WIN:
    SERVER_DIR = os.environ.get("BEAMMP_DIR") or os.path.abspath(os.path.join(HERE, "..", ".."))
    ES_DIR = os.path.join(SERVER_DIR, "EasyServer")
    DATA_DIR = os.path.join(ES_DIR, "data")
    EXE = os.path.join(SERVER_DIR, "BeamMP-Server.exe")
else:
    SERVER_DIR = os.environ.get("BEAMMP_DIR", "/opt/beammp-server")
    ES_DIR = DATA_DIR = os.path.join(SERVER_DIR, ".easyserver")
    EXE = os.path.join(SERVER_DIR, "BeamMP-Server")
SERVERS_DIR = os.path.join(SERVER_DIR, "servers")   # extra servers live in servers/<id>/
UPLOAD_TMP = os.path.join(DATA_DIR, "uploading")
TLS_DIR = os.path.join(DATA_DIR, "tls")
SETTINGS_FILE = os.path.join(DATA_DIR, "dashboard.json")
NOTIF_FILE = os.path.join(DATA_DIR, "notifications.json")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
os.environ.setdefault("MODSCAN_CACHE", os.path.join(DATA_DIR, "scancache.json"))
modscan.CACHE_FILE = os.environ["MODSCAN_CACHE"]

CTL_IN = "/run/beammp-easyserver-ctl"         # Linux: requests to the root helper
CTL_OUT = "/run/beammp-easyserver-ctl-out"    # Linux: its answers

BUILTIN_MAPS = ["gridmap_v2", "west_coast_usa", "east_coast_usa", "utah", "italy",
                "jungle_rock_island", "industrial", "small_island", "automation_test_track",
                "hirochi_raceway", "johnson_valley", "derby", "driver_training"]

SECRET_NAMES = ("MODS_PASSWORD", "VT_API_KEY", "DISCORD_WEBHOOK", "SMTP_PASSWORD", "TOTP_SECRET",
                "BEAMMP_AUTH_KEY", "DISCORD_BOT_TOKEN")

DEFAULT_SETTINGS = {
    "port": 30815,
    "https": False,
    "remote_enabled": False,
    "notify": {"crash": True, "stopped": True, "update": True, "mod_blocked": True,
               "login_failed": True, "player_join": False, "player_denied": True,
               "moderation": True, "network": True, "restart": False},
    "discord_enabled": False,
    "email_enabled": False,
    "smtp_host": "", "smtp_port": 587, "smtp_security": "starttls",
    "smtp_user": "", "smtp_from": "", "smtp_to": "",
    "auto_restart": True,
    "update_check": True,
    "security_alerts": True,       # attacks: alert on every channel that is set up
    "security_reminders": True,    # ...and repeat every 15 minutes until "Stop alerts" is clicked
    # Hide my IP: players join through a relay (playit.gg, a VPN with port
    # forwarding, your own VPS) instead of your home address. Off by default:
    # it makes DDoS attacks on your home much harder, but adds lag.
    "relay_enabled": False,
    "relay_host": "",
    "relay_ports": {},             # server id -> port players use on the relay
    "flood_protect": False,        # Linux: per-address limits on the game ports (nftables)
    "auto_update": False,          # install BeamMP updates at a scheduled restart
    "discord_bot": False,          # slash commands (/status, /start, /stop, /restart) - needs a bot token
    "discord_bot_guild": "",       # the one Discord server the bot answers in
    "discord_bot_users": [],       # Discord user IDs that may start/stop besides "Manage Server" people
}
SECURITY_FILE = os.path.join(DATA_DIR, "security.json")
SECURITY_REPEAT = 15 * 60

LOCK = threading.RLock()


def now():
    return int(time.time())


# ----------------------------------------------------------------------------- servers (instances)
# One dashboard manages several BeamMP servers on this computer. "main" is the
# server the installer set up; extra ones live in <main>/servers/<id>/ and
# share the BeamMP program, the dashboard login and the notification settings.
SERVERS_FILE = os.path.join(DATA_DIR, "servers.json")
ID_RE = re.compile(r"[a-z0-9]{1,12}")
_TL = threading.local()


class Instance:
    def __init__(self, iid, meta=None):
        self.id = iid
        self.meta = meta or {}
        self.SERVER_DIR = SERVER_DIR if iid == "main" else os.path.join(SERVERS_DIR, iid)
        self.RES = os.path.join(self.SERVER_DIR, "Resources")
        self.CLIENT_DIR = os.path.join(self.RES, "Client")
        self.DISABLED_DIR = os.path.join(self.RES, "Client-disabled")
        self.QUAR_DIR = os.path.join(self.RES, "Quarantine")
        self.STATS_DIR = os.path.join(self.RES, "Server", "EasyServerStats")
        self.ALLOW_FILE = os.path.join(self.STATS_DIR, "allowlist.txt")
        self.VOTE_FILE = os.path.join(self.STATS_DIR, "mapvote.txt")
        self.EXTRAS_FILE = os.path.join(self.STATS_DIR, "extras.txt")
        self.RECORDS_FILE = os.path.join(self.STATS_DIR, "records.tsv")
        self.MOD_FILE = os.path.join(self.STATS_DIR, "moderation.txt")
        self.BANS_FILE = os.path.join(self.STATS_DIR, "bans.txt")
        self.ACTIONS_FILE = os.path.join(self.STATS_DIR, "actions.txt")
        self.VERIFIED_FILE = os.path.join(self.STATS_DIR, "verified.txt")
        self.CONFIG = os.path.join(self.SERVER_DIR, "ServerConfig.toml")
        self.SERVER_LOG = os.path.join(self.SERVER_DIR, "Server.log")
        self.authkey_name = "BEAMMP_AUTH_KEY" if iid == "main" else "BEAMMP_AUTH_KEY_" + iid.upper()
        self.unit = "beammp-server" if iid == "main" else "beammp-server@%s" % iid
        self._server = None

    @property
    def server(self):
        if self._server is None:
            self._server = ServerManager(self)
        return self._server

    @property
    def name(self):
        if self.meta.get("name"):
            return self.meta["name"]
        try:
            with open_shared(self.CONFIG) as f:
                n = toml_parse(f.read(262144))[0].get("General", {}).get("Name")
            if isinstance(n, str) and n.strip():
                return re.sub(r"\^.", "", n).strip()[:60]
        except OSError:
            pass
        return "Main server" if self.id == "main" else "Server " + self.id

    def port(self):
        try:
            with open_shared(self.CONFIG) as f:
                v = toml_parse(f.read(262144))[0].get("General", {}).get("Port")
            return v if isinstance(v, int) else None
        except OSError:
            return None

    def has_authkey(self):
        return bool(APP and (APP.secrets.has(self.authkey_name) or self.meta.get("has_authkey")))

    def set_authkey(self, key):
        APP.secrets.set(self.authkey_name, key)
        set_server_meta(self.id, has_authkey=bool(key))


INSTANCES = {}


def load_servers():
    data = read_json(SERVERS_FILE, {})
    metas = data.get("servers") if isinstance(data, dict) else None
    metas = metas if isinstance(metas, list) else []
    found = {"main": {}}
    for m in metas:
        if isinstance(m, dict) and ID_RE.fullmatch(str(m.get("id", ""))):
            found[m["id"]] = m
    with LOCK:
        for iid, meta in found.items():
            if iid != "main" and not os.path.isdir(os.path.join(SERVERS_DIR, iid)):
                continue
            if iid in INSTANCES:
                INSTANCES[iid].meta = meta
            else:
                INSTANCES[iid] = Instance(iid, meta)
        for iid in list(INSTANCES):
            if iid not in found:
                del INSTANCES[iid]


def save_servers():
    with LOCK:
        metas = [dict(INSTANCES[i].meta, id=i) for i in sorted(INSTANCES, key=lambda x: (x != "main", x))]
    write_json(SERVERS_FILE, {"servers": metas})


def set_server_meta(iid, **kw):
    with LOCK:
        inst = INSTANCES.get(iid)
        if not inst:
            return
        for k, v in kw.items():
            if v is None:
                inst.meta.pop(k, None)
            else:
                inst.meta[k] = v
    save_servers()


def I():
    """The server the current request (or monitor loop) is about."""
    inst = getattr(_TL, "inst", None)
    return inst if inst is not None else INSTANCES["main"]


def use_server(iid):
    _TL.inst = INSTANCES.get(iid) or INSTANCES["main"]
    return _TL.inst


def other_ports():
    me = I().id
    with LOCK:
        insts = [i for k, i in INSTANCES.items() if k != me]
    return {p: i.name for i in insts for p in [i.port()] if p}


def ensure_dirs():
    for d in (DATA_DIR, UPLOAD_TMP, I().CLIENT_DIR, I().DISABLED_DIR, I().QUAR_DIR):
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
    try:
        os.makedirs(TLS_DIR, exist_ok=True)
        if not IS_WIN:
            os.chmod(TLS_DIR, 0o700)
    except OSError:
        pass


def open_shared(path, mode="r"):
    """Open a file in a folder the game server can also write to.

    Never follows links (a hacked game server could point them at the
    dashboard's own files) and never blocks on FIFOs. Text mode is UTF-8."""
    flags = {"r": os.O_RDONLY, "rb": os.O_RDONLY, "w": os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
             "a": os.O_WRONLY | os.O_CREAT | os.O_APPEND}[mode]
    flags |= (getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0) |
              getattr(os, "O_BINARY", 0))
    fd = os.open(path, flags, 0o664)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file: %s" % path)
        if "b" in mode:
            return os.fdopen(fd, mode)
        return os.fdopen(fd, mode, encoding="utf-8", errors="replace", newline="\n" if mode != "r" else None)
    except BaseException:
        os.close(fd)
        raise


def read_json(path, default):
    try:
        with open_shared(path) as f:
            return json.loads(f.read(4 * 1024 * 1024))
    except (OSError, ValueError):
        return default


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


# ----------------------------------------------------------------------------- settings
class Settings:
    def __init__(self):
        data = read_json(SETTINGS_FILE, {})
        if not data and not IS_WIN:
            # first run after upgrading from the older mod page: keep its port
            try:
                with open("/etc/beammp-easyserver/modmanager.conf", encoding="utf-8") as f:
                    m = re.search(r"(?m)^\s*port\s*=\s*(\d+)", f.read())
                    if m:
                        data["port"] = int(m.group(1))
            except OSError:
                pass
        self.data = json.loads(json.dumps(DEFAULT_SETTINGS))
        for k, v in data.items():
            if k == "notify" and isinstance(v, dict):
                self.data["notify"].update({a: bool(b) for a, b in v.items() if a in self.data["notify"]})
            elif k in DEFAULT_SETTINGS:
                self.data[k] = v

    def get(self, k):
        with LOCK:
            return self.data.get(k)

    def update(self, values):
        with LOCK:
            self.data.update(values)
            write_json(SETTINGS_FILE, self.data)

    def public(self):
        with LOCK:
            return json.loads(json.dumps(self.data))


# ----------------------------------------------------------------------------- Windows DPAPI
if IS_WIN:
    import ctypes
    from ctypes import wintypes

    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    _ENTROPY = b"BeamMP-EasyServer-v1"

    def _dpapi(data, protect):
        buf = ctypes.create_string_buffer(data, len(data))
        inb = _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        ebuf = ctypes.create_string_buffer(_ENTROPY, len(_ENTROPY))
        ent = _BLOB(len(_ENTROPY), ctypes.cast(ebuf, ctypes.POINTER(ctypes.c_char)))
        out = _BLOB()
        fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
        if not fn(ctypes.byref(inb), None, ctypes.byref(ent), None, None, 0x1, ctypes.byref(out)):
            raise OSError("DPAPI failed")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out.pbData)


# ----------------------------------------------------------------------------- secrets
class Secrets:
    """Linux: values arrive in memory from launch.sh (decrypted by root) and
    changes go to the root helper. Windows: DPAPI-encrypted secrets.dat."""

    def __init__(self):
        self.cache = {}
        if IS_WIN:
            self.file = os.path.join(ES_DIR, "secrets.dat")
            for n in list(SECRET_NAMES) + [k for k in self._win_lines() if k.startswith("BEAMMP_AUTH_KEY_")]:
                v = self._win_read(n)
                if v:
                    self.cache[n] = v
        else:
            for n in SECRET_NAMES:
                if n == "BEAMMP_AUTH_KEY":
                    continue
                v = os.environ.pop(n, "")
                if v:
                    self.cache[n] = v
            if os.environ.pop("HAS_AUTH_KEY", "") == "1":
                self.cache["BEAMMP_AUTH_KEY"] = "(set)"   # value itself never reaches the dashboard

    # -- Windows file format shared with easyserver-common.ps1
    def _win_lines(self):
        m = {}
        try:
            with open(self.file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        m[k] = v
        except OSError:
            pass
        return m

    def _win_read(self, name):
        v = self._win_lines().get(name)
        if not v:
            return ""
        try:
            return _dpapi(base64.b64decode(v), False).decode("utf-8")
        except Exception:
            return ""

    def _win_write(self, name, value):
        m = self._win_lines()
        if value:
            m[name] = base64.b64encode(_dpapi(value.encode("utf-8"), True)).decode()
        else:
            m.pop(name, None)
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        lines = ["# BeamMP EasyServer - encrypted with Windows DPAPI. Useless on any other PC/account."]
        lines += ["%s=%s" % (k, m[k]) for k in sorted(m)]
        with open(self.file + ".tmp", "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(self.file + ".tmp", self.file)

    def get(self, name):
        return self.cache.get(name, "")

    def has(self, name):
        return bool(self.cache.get(name))

    def set(self, name, value):
        if name not in SECRET_NAMES and not re.fullmatch(r"BEAMMP_AUTH_KEY_[A-Z0-9]{1,12}", name):
            raise ValueError("unknown secret")
        value = (value or "").strip()
        if "\n" in value or len(value) > 2048:
            raise ValueError("invalid value")
        if IS_WIN:
            self._win_write(name, value)
        else:
            r = control("set-secret" if value else "unset-secret", name=name, value=value)
            if not r.get("ok"):
                raise RuntimeError(r.get("msg") or "could not save")
        with LOCK:
            if value:
                self.cache[name] = "(set)" if (name.startswith("BEAMMP_AUTH_KEY") and not IS_WIN) else value
            else:
                self.cache.pop(name, None)


# ----------------------------------------------------------------------------- Linux root helper
def control(action, timeout=240, **kw):
    """Ask the root helper (Linux) to do a whitelisted job. Returns its answer."""
    if IS_WIN:
        return {"ok": False, "msg": "not available on Windows"}
    rid = uuid.uuid4().hex
    req = dict(kw, id=rid, action=action)
    path = os.path.join(CTL_IN, rid)
    try:
        fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(req, f)
        os.replace(path + ".tmp", path + ".req")
    except OSError as e:
        return {"ok": False, "msg": "control channel unavailable (%s)" % e.__class__.__name__}
    out = os.path.join(CTL_OUT, rid + ".json")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(out):
            time.sleep(0.05)
            r = read_json(out, None)
            if r is not None:
                return r
        time.sleep(0.25)
    return {"ok": False, "msg": "timed out waiting for the server helper"}


# ----------------------------------------------------------------------------- server control
class ServerManager:
    def __init__(self, inst):
        self.inst = inst
        self.expected_stop = False
        self.started_at = None
        self.version_cache = (None, None)
        self.restart_needed = False
        self._usage_prev = None

    # ---------- status
    def status(self):
        if IS_WIN:
            pid = win_server_pids().get(self.inst.id, {}).get("pid", 0)
            with LOCK:
                if pid and not self.started_at:
                    self.started_at = now()
                if not pid:
                    self.started_at = None
            return {"state": "running" if pid else "stopped", "pid": pid,
                    "uptime": (now() - self.started_at) if (pid and self.started_at) else 0,
                    "restarts": 0}
        try:
            out = subprocess.run(["systemctl", "show", self.inst.unit, "-p",
                                  "ActiveState,SubState,NRestarts,MainPID,ActiveEnterTimestampMonotonic,LoadState"],
                                 capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.TimeoutExpired):
            return {"state": "unknown", "pid": 0, "uptime": 0, "restarts": 0}
        v = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
        active = v.get("ActiveState", "unknown")
        state = {"active": "running", "inactive": "stopped", "failed": "failed",
                 "activating": "starting", "deactivating": "stopping"}.get(active, active)
        if v.get("SubState") == "auto-restart":
            state = "restarting"
        uptime = 0
        try:
            mono = int(v.get("ActiveEnterTimestampMonotonic", "0")) / 1e6
            if state == "running" and mono:
                with open("/proc/uptime") as f:
                    uptime = int(float(f.read().split()[0]) - mono)
        except (OSError, ValueError):
            pass
        return {"state": state, "pid": int(v.get("MainPID", "0") or 0), "uptime": max(0, uptime),
                "restarts": int(v.get("NRestarts", "0") or 0)}

    def usage(self):
        """CPU (in cores, e.g. 0.5) and memory (MB) the server uses right now."""
        cpu_ns = mem = None
        if IS_WIN:
            p = win_server_pids(max_age=2).get(self.inst.id)
            if p:
                cpu_ns, mem = p.get("cpu_ns"), p.get("mem")
        else:
            try:
                out = subprocess.run(["systemctl", "show", self.inst.unit, "-p", "CPUUsageNSec,MemoryCurrent"],
                                     capture_output=True, text=True, timeout=10).stdout
                v = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
                cpu_ns = int(v["CPUUsageNSec"]) if v.get("CPUUsageNSec", "").isdigit() else None
                mem = int(v["MemoryCurrent"]) if v.get("MemoryCurrent", "").isdigit() else None
            except (OSError, subprocess.TimeoutExpired, ValueError):
                pass
        cores = None
        t = time.time()
        if cpu_ns is not None:
            prev, self._usage_prev = self._usage_prev, (t, cpu_ns)
            if prev and t > prev[0] and cpu_ns >= prev[1]:
                cores = round((cpu_ns - prev[1]) / 1e9 / (t - prev[0]), 2)
        return {"cpu_cores": cores, "mem_mb": round(mem / 1048576) if mem else None}

    # ---------- actions
    def action(self, what):
        if what not in ("start", "stop", "restart"):
            raise ValueError("bad action")
        with LOCK:
            self.expected_stop = what in ("stop", "restart")
            self.restart_needed = False
        if not IS_WIN:
            return control(what, server=self.inst.id, timeout=60)
        if what in ("stop", "restart"):
            pid = win_server_pids(max_age=0).get(self.inst.id, {}).get("pid")
            if pid:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                time.sleep(1.5)
        if what in ("start", "restart"):
            self._win_start()
        return {"ok": True, "msg": "done"}

    def _win_start(self):
        ps1 = os.path.join(ES_DIR, "start-server.ps1")
        subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, "-Auto",
                          "-Server", self.inst.id],
                         cwd=self.inst.SERVER_DIR, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        with LOCK:
            self.started_at = now()
            self.expected_stop = False
        if self.inst.meta.get("limits"):
            threading.Thread(target=win_apply_limits_later, args=(self.inst,), daemon=True).start()

    # ---------- versions
    def installed_version(self):
        try:
            mtime = os.path.getmtime(EXE)
        except OSError:
            return None
        if self.version_cache[0] == mtime:
            return self.version_cache[1]
        try:
            out = subprocess.run([EXE, "--version"], capture_output=True, text=True, timeout=15,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WIN else 0)
            m = re.search(r"v?(\d+\.\d+\.\d+)", out.stdout + out.stderr)
            ver = m.group(1) if m else None
        except (OSError, subprocess.TimeoutExpired):
            ver = None
        self.version_cache = (mtime, ver)
        return ver

    def update(self):
        """Update the shared BeamMP program. All servers use it, so all running ones restart."""
        if not IS_WIN:
            return control("update-server", timeout=600)
        tmp = EXE + ".download"
        req = urllib.request.Request("https://github.com/%s/releases/latest/download/BeamMP-Server.exe" % BEAMMP_REPO,
                                     headers={"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        with open(tmp, "rb") as f:
            if f.read(2) != b"MZ":
                os.remove(tmp)
                return {"ok": False, "msg": "download was not a Windows program"}
        with LOCK:
            insts = list(INSTANCES.values())
        running = [i for i in insts if i.server.status()["state"] == "running"]
        for i in running:
            i.server.action("stop")
        os.replace(tmp, EXE)
        for i in running:
            i.server.action("start")
        return {"ok": True, "msg": "updated"}


# ----------------------------------------------------------------------------- Windows: processes + limits
_WIN_PIDS = {"t": 0, "data": {}}
RUNCFG_RE = re.compile(r"ServerConfig\.run(?:\.([a-z0-9]{1,12}))?\.toml", re.I)


def win_server_pids(max_age=3):
    """{server id: {pid, cpu_ns, mem}} for every running BeamMP-Server.exe, matched by
    the temporary config file start-server.ps1 gives it (ServerConfig.run[.<id>].toml)."""
    if not IS_WIN:
        return {}
    with LOCK:
        if time.time() - _WIN_PIDS["t"] <= max_age:
            return _WIN_PIDS["data"]
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='BeamMP-Server.exe'\" | ForEach-Object { "
          "'{0}|{1}|{2}|{3}' -f $_.ProcessId, ($_.KernelModeTime + $_.UserModeTime), $_.WorkingSetSize, $_.CommandLine }")
    data = {}
    try:
        out = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        for line in out.splitlines():
            parts = line.strip().split("|", 3)
            if len(parts) < 4 or not parts[0].isdigit():
                continue
            m = RUNCFG_RE.search(parts[3])
            iid = (m.group(1) or "main").lower() if m else "main"
            data.setdefault(iid, {"pid": int(parts[0]),
                                  "cpu_ns": int(parts[1]) * 100 if parts[1].isdigit() else None,
                                  "mem": int(parts[2]) if parts[2].isdigit() else None})
    except (OSError, subprocess.TimeoutExpired):
        pass
    with LOCK:
        _WIN_PIDS.update(t=time.time(), data=data)
    return data


_WIN_JOBS = {}


def win_apply_limits(inst):
    """Put the server process in a Windows job object with a CPU cap and a memory limit."""
    lim = inst.meta.get("limits") or {}
    pid = win_server_pids(max_age=0).get(inst.id, {}).get("pid")
    if not pid:
        return "not running"
    cores, ram = float(lim.get("cpu_cores") or 0), int(lim.get("ram_mb") or 0)
    if not cores and not ram:
        return "no limits"
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.OpenProcess.restype = wintypes.HANDLE

    class CPU_RATE(ctypes.Structure):
        _fields_ = [("ControlFlags", wintypes.DWORD), ("CpuRate", wintypes.DWORD)]

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class IOC(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in ("r", "w", "o", "rb", "wb", "ob")]

    class EXT(ctypes.Structure):
        _fields_ = [("Basic", BASIC), ("Io", IOC), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    job = k32.CreateJobObjectW(None, None)
    if not job:
        return "could not create a job object"
    if cores:
        rate = max(1, min(10000, int(cores / (os.cpu_count() or 1) * 10000)))
        info = CPU_RATE(0x1 | 0x4, rate)                    # ENABLE | HARD_CAP
        k32.SetInformationJobObject(job, 15, ctypes.byref(info), ctypes.sizeof(info))
    if ram:
        ext = EXT()
        ext.Basic.LimitFlags = 0x100                         # JOB_OBJECT_LIMIT_PROCESS_MEMORY
        ext.ProcessMemoryLimit = ram * 1048576
        k32.SetInformationJobObject(job, 9, ctypes.byref(ext), ctypes.sizeof(ext))
    h = k32.OpenProcess(0x0100 | 0x0001, False, pid)        # PROCESS_SET_QUOTA | PROCESS_TERMINATE
    ok = bool(h) and bool(k32.AssignProcessToJobObject(job, h))
    if h:
        k32.CloseHandle(h)
    old = _WIN_JOBS.pop(inst.id, None)
    if old:
        k32.CloseHandle(old)
    _WIN_JOBS[inst.id] = job
    return "applied" if ok else "could not attach the limits (error %d)" % ctypes.get_last_error()


def win_apply_limits_later(inst):
    for _ in range(20):                 # wait for start-server.ps1 to launch the server
        time.sleep(2)
        if win_server_pids(max_age=0).get(inst.id):
            win_apply_limits(inst)
            return


def win_upload_limit(inst):
    """Mod download speed cap via a Windows QoS policy. Needs admin rights, so Windows
    shows a permission prompt on the server PC."""
    lim = inst.meta.get("limits") or {}
    kbps, port = int(lim.get("upload_kbps") or 0), inst.port()
    name = "BeamMP EasyServer %s" % inst.id
    cmd = "Get-NetQosPolicy -Name '%s' -ErrorAction SilentlyContinue | Remove-NetQosPolicy -Confirm:$false" % name
    if kbps and port:
        cmd += ("; New-NetQosPolicy -Name '%s' -IPProtocolMatchCondition TCP -IPSrcPortMatchCondition %d "
                "-ThrottleRateActionBitsPerSecond %d | Out-Null" % (name, port, kbps * 1000))
    enc = base64.b64encode(cmd.encode("utf-16-le")).decode()
    subprocess.Popen(["powershell.exe", "-NoProfile", "-Command",
                      "Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList '-NoProfile','-EncodedCommand','%s'" % enc],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return "Windows asks for permission on the server PC - click Yes there to apply the speed limit."


# ----------------------------------------------------------------------------- TOML (flat BeamMP config)
_KEYLINE = re.compile(r'^(\s*)([A-Za-z0-9_\-]+)(\s*=\s*)(.*)$')


def _split_value(rest):
    """Split 'value   # comment' -> (value, comment) respecting quotes."""
    in_q, esc = False, False
    for i, c in enumerate(rest):
        if esc:
            esc = False
            continue
        if c == "\\" and in_q:
            esc = True
        elif c == '"':
            in_q = not in_q
        elif c == "#" and not in_q:
            return rest[:i].rstrip(), rest[i:]
    return rest.rstrip(), ""


def _parse_value(raw):
    if raw.startswith('"'):
        if len(raw) < 2 or not raw.endswith('"'):
            raise ValueError("text value is missing its closing quote")
        body = raw[1:-1]
        out, i = [], 0
        while i < len(body):
            c = body[i]
            if c == "\\" and i + 1 < len(body):
                n = body[i + 1]
                out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(n, n))
                i += 2
                continue
            if c == '"':
                raise ValueError("unexpected quote inside text value")
            out.append(c)
            i += 1
        return "".join(out)
    if raw in ("true", "false"):
        return raw == "true"
    if re.fullmatch(r"[+-]?\d+", raw):
        return int(raw)
    if re.fullmatch(r"[+-]?\d+\.\d+", raw):
        return float(raw)
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1]
    raise ValueError("can't read the value %r (text needs \"quotes\")" % raw[:40])


def toml_parse(text):
    """Returns (data, positions, issues). data = {section: {key: value}}."""
    data, pos, issues = {}, {}, []
    section = ""
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.fullmatch(r"\[\s*([A-Za-z0-9_\-.]+)\s*\]\s*(#.*)?", s)
        if m:
            section = m.group(1)
            if section in data:
                issues.append({"level": "error", "line": n, "field": section,
                               "message": "Section [%s] appears twice" % section})
            data.setdefault(section, {})
            continue
        m = _KEYLINE.match(line)
        if not m:
            issues.append({"level": "error", "line": n, "field": None,
                           "message": "Line %d isn't a valid setting (expected: Name = value)" % n})
            continue
        key = m.group(2)
        raw, _ = _split_value(m.group(4))
        try:
            val = _parse_value(raw)
        except ValueError as e:
            issues.append({"level": "error", "line": n, "field": key, "message": "%s: %s" % (key, e)})
            continue
        sec = data.setdefault(section, {})
        if key in sec:
            issues.append({"level": "error", "line": n, "field": key,
                           "message": "%s is set twice in [%s]" % (key, section or "top")})
        sec[key] = val
        pos[(section, key)] = n
    return data, pos, issues


def toml_format(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return '"%s"' % s


def toml_set(text, section, key, value):
    lines = text.splitlines()
    cur, last_in_section, sec_line = "", None, None
    for i, line in enumerate(lines):
        s = line.strip()
        m = re.fullmatch(r"\[\s*([A-Za-z0-9_\-.]+)\s*\]\s*(#.*)?", s)
        if m:
            cur = m.group(1)
            if cur == section:
                sec_line = i
                last_in_section = i
            continue
        if cur != section:
            continue
        if s:
            last_in_section = i
        km = _KEYLINE.match(line)
        if km and km.group(2) == key and not s.startswith("#"):
            _, comment = _split_value(km.group(4))
            lines[i] = "%s%s%s%s%s" % (km.group(1), key, km.group(3), toml_format(value),
                                       (" " + comment) if comment else "")
            return "\n".join(lines) + "\n"
    new = "%s = %s" % (key, toml_format(value))
    if sec_line is None:
        lines += ["", "[%s]" % section, new]
    else:
        lines.insert(last_in_section + 1, new)
    return "\n".join(lines) + "\n"


CONFIG_SCHEMA = [
    # section, key, type, label, help, options
    ("General", "Name", "str", "Server name", "Shown in the server list", {"max": 120, "required": True}),
    ("General", "Description", "str", "Description", "Shown when players look at the server", {"max": 500}),
    ("General", "Map", "map", "Map", "Built-in map or a map mod", {}),
    ("General", "MaxPlayers", "int", "Max players", "", {"min": 1, "max": 100}),
    ("General", "MaxCars", "int", "Cars per player", "", {"min": 1, "max": 50}),
    ("General", "Port", "int", "Port", "Forward this port (TCP + UDP) for internet play", {"min": 1024, "max": 65535}),
    ("General", "Private", "bool", "Private server", "Hide it from the public server list", {}),
    ("General", "AllowGuests", "bool", "Allow guests", "Players without a BeamMP account", {}),
    ("General", "Tags", "str", "Tags", "Comma separated, e.g. Freeroam,Racing", {"max": 200}),
    ("General", "LogChat", "bool", "Log chat", "Write chat messages to the server log", {}),
    ("General", "InformationPacket", "bool", "Information packet", "Answer server info requests from the launcher", {}),
    ("General", "Debug", "bool", "Debug logging", "Very detailed log - only for troubleshooting", {}),
    ("General", "IP", "ip", "Listen address", ":: = all addresses (recommended)", {"advanced": True}),
    ("General", "ResourceFolder", "str", "Resource folder", "Leave as Resources", {"advanced": True, "max": 200}),
    ("Misc", "ImScaredOfUpdates", "bool", "Hide update reminders", "The dashboard tells you about updates anyway", {"advanced": True}),
    ("Misc", "UpdateReminderTime", "str", "Update reminder interval", "e.g. 30s, 5min", {"advanced": True, "max": 20}),
]
KNOWN_KEYS = {(s, k) for s, k, *_ in CONFIG_SCHEMA} | {("General", "AuthKey")}


def map_name(v):
    m = re.fullmatch(r"/levels/([^/]+)/info\.json", str(v or ""))
    return m.group(1) if m else ""


def enabled_mod_maps():
    found = set()
    try:
        for n in os.listdir(I().CLIENT_DIR):
            if n.lower().endswith(".zip"):
                found.update(zip_maps(os.path.join(I().CLIENT_DIR, n)) or [])
    except OSError:
        pass
    return sorted(found)


def validate_config(text, dashboard_port, has_authkey):
    data, pos, issues = toml_parse(text)

    def add(level, field, msg, section="General"):
        issues.append({"level": level, "field": field, "line": pos.get((section, field)), "message": msg})

    for sec, keys in data.items():
        for k in keys:
            if (sec, k) not in KNOWN_KEYS:
                add("warning", k, "Unknown setting %s in [%s] - BeamMP will ignore it" % (k, sec or "top"), sec)
    if "General" not in data:
        issues.append({"level": "error", "field": None, "line": None, "message": "The [General] section is missing"})
        return data, issues
    g = data.get("General", {})
    for sec, key, typ, label, _h, opt in CONFIG_SCHEMA:
        v = data.get(sec, {}).get(key)
        if v is None:
            if opt.get("required"):
                add("error", key, "%s is missing" % label, sec)
            continue
        if typ == "int":
            if isinstance(v, bool) or not isinstance(v, int):
                add("error", key, "%s must be a whole number" % label, sec)
                continue
            if v < opt.get("min", v) or v > opt.get("max", v):
                add("error", key, "%s must be between %d and %d" % (label, opt["min"], opt["max"]), sec)
        elif typ == "bool":
            if not isinstance(v, bool):
                add("error", key, "%s must be true or false" % label, sec)
        elif typ in ("str", "map", "ip"):
            if not isinstance(v, str):
                add("error", key, "%s must be text in \"quotes\"" % label, sec)
                continue
            if opt.get("required") and not v.strip():
                add("error", key, "%s can't be empty" % label, sec)
            if len(v) > opt.get("max", 10 ** 6):
                add("error", key, "%s is too long (max %d characters)" % (label, opt["max"]), sec)
            if typ == "ip":
                try:
                    ipaddress.ip_address(v)
                except ValueError:
                    add("error", key, "%s must be an IP address like :: or 0.0.0.0" % label, sec)
            if typ == "map":
                name = map_name(v)
                if not name:
                    add("error", key, 'Map must look like "/levels/NAME/info.json"', sec)
                elif name not in BUILTIN_MAPS and name not in enabled_mod_maps():
                    add("warning", key, "Map '%s' isn't a built-in map and no enabled mod contains it" % name, sec)
            if key == "ResourceFolder" and isinstance(v, str) and not re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", v):
                add("error", key, "Resource folder must be a simple folder name next to the server (normally Resources)", sec)
            if key == "UpdateReminderTime" and v and not re.fullmatch(r"\d+\s*(s|min|h|d)?", v.strip()):
                add("warning", key, "Update reminder interval should look like 30s or 5min", sec)
    port = g.get("Port")
    if isinstance(port, int) and port == dashboard_port:
        add("error", "Port", "Port %d is already used by this dashboard - pick another" % port)
    elif isinstance(port, int) and INSTANCES and port in other_ports():
        add("error", "Port", "Port %d is already used by your server \"%s\" - every server needs its own port"
            % (port, other_ports()[port]))
    ak = g.get("AuthKey")
    if isinstance(ak, str) and ak.strip():
        add("warning", "AuthKey", "Your AuthKey is in the file as plain text - saving here moves it to encrypted storage")
    elif g.get("Private") is False and not has_authkey:
        add("warning", "Private", "Without an AuthKey the server won't appear in the public list")
    mp = g.get("MaxPlayers")
    if isinstance(mp, int) and not isinstance(mp, bool) and mp > 24:
        add("info", "MaxPlayers", "More than 24 players needs a strong PC and fast upload speed")
    return data, issues


# ----------------------------------------------------------------------------- mods
def safe_zip_name(name):
    if not isinstance(name, str):
        return None
    name = os.path.basename(urllib.parse.unquote(name)).strip()
    name = re.sub(r"[^A-Za-z0-9._\- ()\[\]+]", "_", name)
    if not name.lower().endswith(".zip") or name.startswith(".") or len(name) > 180:
        return None
    return name


def zip_maps(path):
    try:
        with zipfile.ZipFile(path) as z:
            return sorted({m.group(1) for n in z.namelist()
                           for m in [re.match(r"^levels/([^/]+)/(info\.json|main\.level\.json|[^/]+\.mis)$", n, re.I)] if m})
    except (zipfile.BadZipFile, OSError):
        return None


def list_mods():
    out = []
    for folder, enabled in ((I().CLIENT_DIR, True), (I().DISABLED_DIR, False)):
        try:
            names = sorted(os.listdir(folder), key=str.lower)
        except OSError:
            continue
        for n in names:
            p = os.path.join(folder, n)
            if n.lower().endswith(".zip") and os.path.isfile(p) and not os.path.islink(p):
                r = modscan.cached_result(p)
                out.append({"name": n, "size": os.path.getsize(p), "enabled": enabled,
                            "maps": zip_maps(p) or [], "safety": r["verdict"] if r else "unchecked",
                            "reasons": r["reasons"] if r else []})
    return out


def list_quarantine():
    out = []
    try:
        for n in sorted(os.listdir(I().QUAR_DIR), key=str.lower):
            if n.lower().endswith(".zip"):
                why = ""
                try:
                    with open(os.path.join(I().QUAR_DIR, n + ".why.txt"), encoding="utf-8") as f:
                        why = f.read()[:2000]
                except OSError:
                    pass
                out.append({"name": n, "why": why})
    except OSError:
        pass
    return out


# ----------------------------------------------------------------------------- notifications
class SecurityAlerts:
    """Possible attacks. Each kind of attack is one alert: it is sent at once
    to every channel that is set up (dashboard, Discord, email) and repeated
    every 15 minutes until someone clicks "Stop alerts" in the dashboard (or
    opens the link in the message). Both can be turned off in Settings."""

    def __init__(self, settings, notifier):
        self.s, self.n = settings, notifier
        items = read_json(SECURITY_FILE, [])
        self.items = [a for a in items if isinstance(a, dict) and a.get("id")] if isinstance(items, list) else []
        self.counters = {}

    def _save(self):
        try:
            write_json(SECURITY_FILE, self.items[:100])
        except OSError:
            pass

    def active(self):
        with LOCK:
            return [dict(a) for a in self.items if not a.get("acked")]

    def seen(self, key, limit, window, title, message):
        """Count an event; raise the alert once it happened `limit` times within `window` seconds."""
        t = now()
        with LOCK:
            c = [x for x in self.counters.get(key, []) if x > t - window] + [t]
            self.counters[key] = c[-200:]
            if len(self.counters) > 500:
                self.counters = {k: v for k, v in self.counters.items() if v and v[-1] > t - 3600}
        if len(c) >= limit:
            self.raise_(key, title, message)

    def raise_(self, key, title, message, sig=None):
        """sig: for problems that stay until fixed (like a planted link) - once
        you stopped the alert it stays quiet until something new is found."""
        t = now()
        with LOCK:
            if sig is not None and any(a["key"] == key and a.get("acked") and a.get("sig") == sig for a in self.items):
                return None
            cur = next((a for a in self.items if a["key"] == key and not a.get("acked")), None)
            if cur:                      # still open: just count it, the reminder reports it
                cur["count"] += 1
                cur["last"] = t
                cur["message"] = message
                self._save()
                return cur
            a = {"id": uuid.uuid4().hex[:16], "key": key, "title": title, "message": message,
                 "first": t, "last": t, "count": 1, "acked": False, "sent": 0,
                 "next": t + SECURITY_REPEAT, "server": I().id, "sig": sig}
            self.items.insert(0, a)
            del self.items[100:]
            self._save()
        self._send(a, first=True)
        return a

    def _send(self, a, first):
        on = bool(self.s.get("security_alerts"))
        link = dashboard_url(a.get("server")) + "#ack=" + a["id"]
        if first:
            title = "⚠️ Security alert: " + a["title"]
            msg = a["message"]
        else:
            title = "⚠️ Reminder: " + a["title"]
            msg = "%s\n\nHappened %d time%s, last at %s." % (a["message"], a["count"], "" if a["count"] == 1 else "s",
                                                         time.strftime("%H:%M", time.localtime(a["last"])))
        if on and self.s.get("security_reminders"):
            msg += "\n\nYou'll get this every 15 minutes until you click \"Stop alerts\" in the dashboard: " + link
        else:
            msg += "\n\nDashboard: " + link
        prev = getattr(_TL, "inst", None)
        use_server(a.get("server") or "main")
        try:
            self.n.add("security", title, msg, "error", send=on, everywhere=True)
        finally:
            _TL.inst = prev
        with LOCK:
            a["sent"] = a.get("sent", 0) + 1

    def tick(self):
        """Called by the monitor: sends the 15-minute reminders."""
        if not (self.s.get("security_alerts") and self.s.get("security_reminders")):
            return
        t = now()
        with LOCK:
            due = [a for a in self.items if not a.get("acked") and a.get("next", 0) <= t]
            for a in due:
                a["next"] = t + SECURITY_REPEAT
            if due:
                self._save()
        for a in due:
            self._send(a, first=False)

    def ack(self, aid=None):
        with LOCK:
            n = 0
            for a in self.items:
                if not a.get("acked") and (aid is None or a["id"] == aid):
                    a["acked"] = True
                    a["acked_at"] = now()
                    n += 1
            self._save()
        return n


def dashboard_url(server_id=None):
    if not APP:
        return ""
    st = APP.settings
    proto = "https" if st.get("https") else "http"
    host = (public_ip() if st.get("remote_enabled") else None) or lan_ip()
    return "%s://%s:%s/%s" % (proto, host, st.get("port"), ("?srv=%s" % server_id) if server_id and server_id != "main" else "")


class Notifier:
    COLORS = {"error": 0xE5484D, "warning": 0xF5A524, "info": 0x3B82F6, "success": 0x30A46C}

    def __init__(self, settings, secrets_):
        self.s, self.sec = settings, secrets_
        self.items = read_json(NOTIF_FILE, [])

    def add(self, kind, title, message, level="info", send=True, everywhere=False):
        inst = I()
        with LOCK:
            many = len(INSTANCES) > 1
        item = {"id": uuid.uuid4().hex[:12], "t": now(), "kind": kind,
                "title": ("[%s] %s" % (inst.name, title)) if many else title,
                "message": message, "level": level, "read": False, "delivery": [],
                "server": inst.id, "server_name": inst.name}
        with LOCK:
            self.items.insert(0, item)
            del self.items[300:]
            self._save()
        if send and (everywhere or self.s.get("notify").get(kind, False)):
            threading.Thread(target=self._deliver, args=(item, everywhere), daemon=True).start()
        return item

    def _save(self):
        try:
            write_json(NOTIF_FILE, self.items)
        except OSError:
            pass

    def _deliver(self, item, everywhere=False):
        """everywhere=True (security alerts): every channel that is set up, even
        if its "send to ..." switch is off."""
        notes = []
        if (self.s.get("discord_enabled") or everywhere) and self.sec.has("DISCORD_WEBHOOK"):
            try:
                self.send_discord(item["title"], item["message"], item["level"], footer=item.get("server_name"))
                notes.append("Discord")
            except Exception as e:
                notes.append("Discord failed: %s" % short_err(e))
        if (self.s.get("email_enabled") or everywhere) and self.s.get("smtp_host") and self.s.get("smtp_to"):
            try:
                self.send_email(item["title"], item["message"])
                notes.append("email")
            except Exception as e:
                notes.append("email failed: %s" % short_err(e))
        with LOCK:
            item["delivery"] = notes
            self._save()

    def send_discord(self, title, message, level="info", footer=None, content=None):
        url = self.sec.get("DISCORD_WEBHOOK")
        if not valid_webhook(url):
            raise ValueError("webhook URL is not a Discord webhook")
        payload = {"username": "BeamMP EasyServer",
                   "embeds": [{"title": title[:250], "description": message[:3900],
                               "color": self.COLORS.get(level, 0x3B82F6),
                               "footer": {"text": footer or server_name() or "BeamMP server"}}],
                   "allowed_mentions": {"parse": []}}
        if content:
            payload["content"] = content[:1800]
            payload["allowed_mentions"] = {"parse": ["users", "roles", "everyone"]}
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()

    def send_email(self, title, message):
        host, port = self.s.get("smtp_host"), int(self.s.get("smtp_port") or 587)
        sec = self.s.get("smtp_security")
        to = [a.strip() for a in (self.s.get("smtp_to") or "").split(",") if a.strip()]
        if not to:
            raise ValueError("no recipient address")
        msg = EmailMessage()
        msg["Subject"] = "[BeamMP] " + title
        msg["From"] = self.s.get("smtp_from") or self.s.get("smtp_user") or to[0]
        msg["To"] = ", ".join(to)
        msg.set_content("%s\n\n%s\n\n-- BeamMP EasyServer on %s" % (title, message, socket.gethostname()))
        ctx = ssl.create_default_context()
        if sec == "ssl":
            smtp = smtplib.SMTP_SSL(host, port, timeout=25, context=ctx)
        else:
            smtp = smtplib.SMTP(host, port, timeout=25)
        with smtp:
            if sec == "starttls":
                smtp.starttls(context=ctx)
            if self.s.get("smtp_user"):
                smtp.login(self.s.get("smtp_user"), self.sec.get("SMTP_PASSWORD"))
            smtp.send_message(msg)


def valid_webhook(url):
    return bool(re.fullmatch(r"https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+", url or ""))


def short_err(e):
    return ("%s: %s" % (e.__class__.__name__, e))[:160]


def server_name():
    try:
        with open_shared(I().CONFIG) as f:
            data, _, _ = toml_parse(f.read(262144))
        return str(data.get("General", {}).get("Name", ""))
    except OSError:
        return ""


# ----------------------------------------------------------------------------- allow-list
ALLOW_NAME = re.compile(r"[^\x00-\x1f\x7f#]{1,40}")
ALLOW_MAX = 1000


def read_allowlist():
    on, names = False, []
    try:
        with open_shared(I().ALLOW_FILE) as f:
            for line in f.read(1024 * 1024).splitlines():
                line = line.strip()
                m = re.fullmatch(r"mode\s*=\s*(\w+)", line)
                if m:
                    on = m.group(1).lower() == "on"
                elif line and not line.startswith("#"):
                    names.append(line)
    except OSError:
        pass
    return on, names


def clean_allow_names(raw):
    out, seen = [], set()
    for n in raw if isinstance(raw, list) else str(raw or "").splitlines():
        n = str(n).strip()
        if not n:
            continue
        if not ALLOW_NAME.fullmatch(n) or n.lower().startswith("mode"):
            raise ValueError("\"%s\" is not a valid player name" % n[:40])
        if n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    if len(out) > ALLOW_MAX:
        raise ValueError("The list can hold at most %d names" % ALLOW_MAX)
    return out


def write_allowlist(on, names):
    os.makedirs(I().STATS_DIR, exist_ok=True)
    tmp = I().ALLOW_FILE + ".tmp"
    try:
        os.unlink(tmp)
    except OSError:
        pass
    with open_shared(tmp, "w") as f:
        f.write("# Managed by the BeamMP EasyServer dashboard (Config -> Who can join).\n")
        f.write("# mode=on: only the names below can join. Names are not case-sensitive.\n")
        f.write("mode=%s\n" % ("on" if on else "off"))
        for n in names:
            f.write(n + "\n")
    os.replace(tmp, I().ALLOW_FILE)


def clean_player_name(n):
    """Player names come from the game server's log. BeamMP names only use
    letters, digits, _ . - and spaces - anything else (Discord formatting,
    links, mentions, control characters) is removed before it is shown or sent."""
    n = re.sub(r"[^\w .\-]", "", str(n or ""))
    n = re.sub(r"\s+", " ", n).strip()[:40]
    return n or "?"


def recent_denied(days=7):
    seen, out = set(), []
    for e in reversed(read_events(now() - days * 86400)):
        if e.get("ev") == "denied":
            n = clean_player_name(e.get("name"))
            if n.lower() in seen:
                continue
            seen.add(n.lower())
            out.append({"name": n, "t": e["t"], "guest": bool(e.get("guest"))})
            if len(out) >= 20:
                break
    return out


def approve_url(inst):
    """Link to the dashboard page that adds a refused player to the allow-list."""
    if not APP:
        return ""
    st = APP.settings
    proto = "https" if st.get("https") else "http"
    host = (public_ip() if st.get("remote_enabled") else None) or lan_ip()
    return "%s://%s:%s/?srv=%s#approve=" % (proto, host, st.get("port"), inst.id)


def system_info():
    total = None
    try:
        if IS_WIN:
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                total = m.ullTotalPhys // 1048576
        else:
            with open("/proc/meminfo") as f:
                mm = re.search(r"MemTotal:\s+(\d+)", f.read())
            total = int(mm.group(1)) // 1024 if mm else None
    except Exception:
        pass
    return {"cpu_cores": os.cpu_count() or 1, "ram_mb": total}


# ----------------------------------------------------------------------------- map vote
def read_mapvote():
    on, maps = False, []
    try:
        with open_shared(I().VOTE_FILE) as f:
            for line in f.read(256 * 1024).splitlines():
                line = line.strip()
                m = re.fullmatch(r"mode\s*=\s*(\w+)", line)
                if m:
                    on = m.group(1).lower() == "on"
                elif line and not line.startswith("#"):
                    maps.append(line)
    except OSError:
        pass
    return on, maps


def write_mapvote(on, maps):
    os.makedirs(I().STATS_DIR, exist_ok=True)
    tmp = I().VOTE_FILE + ".tmp"
    try:
        os.unlink(tmp)
    except OSError:
        pass
    with open_shared(tmp, "w") as f:
        f.write("# Managed by the BeamMP EasyServer dashboard (Config -> Map vote).\n")
        f.write("mode=%s\n" % ("on" if on else "off"))
        for m in maps:
            f.write(m + "\n")
    os.replace(tmp, I().VOTE_FILE)


# Cars & chat (Config page): read by the EasyServerStats plugin every 10 s.
# Without the file the plugin uses these same defaults - the scheduled car
# cleanup is on (every day at 04:00), everything else is off.
EXTRAS_DEFAULTS = {"clear": True, "every": 24, "at": "04:00", "warn": 30,
                   "afk": False, "afk_minutes": 5, "countdown": False, "tag": False, "top": False,
                   "tags": ["DRIFT", "COP", "CRUISE", "RACE", "CHILL", "AFK"]}
CLEAR_EVERY = (1, 2, 3, 4, 6, 8, 12, 24)
WARN_CHOICES = (0, 1, 2, 5, 10, 15, 30, 60)


def read_extras():
    d = json.loads(json.dumps(EXTRAS_DEFAULTS))
    try:
        with open_shared(I().EXTRAS_FILE) as f:
            lines = f.read(64 * 1024).splitlines()
    except OSError:
        return d
    for line in lines:
        m = re.fullmatch(r"\s*([\w]+)\s*=\s*(.*?)\s*", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        if k in ("clear", "afk", "countdown", "tag", "top"):
            d[k] = v.lower() == "on"
        elif k == "every" and v.isdigit() and int(v) in CLEAR_EVERY:
            d["every"] = int(v)
        elif k == "at" and re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", v):
            d["at"] = "%02d:%s" % (int(v.split(":")[0]), v.split(":")[1])
        elif k == "warn" and v.isdigit() and int(v) <= 60:
            d["warn"] = int(v)
        elif k == "afk_minutes" and v.isdigit() and 2 <= int(v) <= 120:
            d["afk_minutes"] = int(v)
        elif k == "tags":
            t = clean_tags(v.split(","))
            if t:
                d["tags"] = t
    return d


def clean_tags(items):
    out = []
    for t in items:
        t = re.sub(r"[^A-Za-z0-9-]", "", str(t)).upper()[:12]
        if t and t not in out and len(out) < 20:
            out.append(t)
    return out


def write_extras(d):
    os.makedirs(I().STATS_DIR, exist_ok=True)
    tmp = I().EXTRAS_FILE + ".tmp"
    try:
        os.unlink(tmp)
    except OSError:
        pass
    onoff = lambda b: "on" if b else "off"
    with open_shared(tmp, "w") as f:
        f.write("# Managed by the BeamMP EasyServer dashboard (Config -> Cars & chat).\n")
        f.write("clear=%s\nevery=%d\nat=%s\nwarn=%d\nafk=%s\nafk_minutes=%d\ncountdown=%s\ntag=%s\ntop=%s\ntags=%s\n" % (
            onoff(d["clear"]), d["every"], d["at"], d["warn"], onoff(d["afk"]), d["afk_minutes"],
            onoff(d["countdown"]), onoff(d["tag"]), onoff(d["top"]), ",".join(d["tags"])))
    os.replace(tmp, I().EXTRAS_FILE)


def next_clear(d, t=None):
    """When the plugin removes all cars next (same rule as in main.lua)."""
    t = time.localtime(t or time.time())
    h, m = map(int, d["at"].split(":"))
    base = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, h, m, 0, 0, 0, -1)) - 86400
    step = d["every"] * 3600
    nowt = time.mktime(t)
    return int(base + (int((nowt - base) // step) + 1) * step)


def read_records(limit=10):
    rows = []
    try:
        with open_shared(I().RECORDS_FILE) as f:
            for line in f.read(2 * 1024 * 1024).splitlines():
                p = line.split("\t")
                if len(p) == 4:
                    try:
                        rows.append({"name": p[0][:64], "speed": float(p[1]), "dist": float(p[2]), "streak": int(float(p[3]))})
                    except ValueError:
                        continue
    except OSError:
        return {}
    top = lambda k: [r for r in sorted(rows, key=lambda r: -r[k]) if r[k] > 0][:limit]
    return {"speed": top("speed"), "dist": top("dist"), "streak": top("streak")}


MOD_DESC_RE = re.compile(r"\s*\|\s*(Mods: [\d.]+ [KMGT]?B|No mods to download)$")


def fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return ("%d %s" if unit in ("B", "KB") else "%.1f %s") % (n, unit)
        n /= 1024.0


def refresh_mod_desc():
    """Keep "| Mods: 1.2 GB" at the end of the server description up to date
    (when that's turned on), so players see the download size before joining."""
    on = bool(I().meta.get("desc_modsize"))
    text = APP.read_config_text()
    desc = toml_parse(text)[0].get("General", {}).get("Description", "")
    desc = desc if isinstance(desc, str) else ""
    base = MOD_DESC_RE.sub("", desc)
    if on:
        total = sum(m["size"] for m in list_mods() if m["enabled"])
        base += " | " + ("Mods: " + fmt_bytes(total) if total else "No mods to download")
    if base != desc:
        APP.write_config_text(toml_set(text, "General", "Description", base[:1000]))
        return True
    return False



# ----------------------------------------------------------------------------- moderation
MOD_DEFAULTS = {"admins": [], "filter": False, "words": [], "spam": False, "spam_limit": 5,
                "antibot": False, "verify": True, "per_ip": 3, "join_flood": 8, "guests": True}
NAME_RE = re.compile(r"[^\t\r\n,]{1,64}")


def clean_name(n):
    n = str(n or "").strip()
    if not NAME_RE.fullmatch(n):
        raise ValueError("Enter a player name (no tabs or commas)")
    return n


def shared_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    try:
        os.unlink(tmp)
    except OSError:
        pass
    with open_shared(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def shared_read(path, limit=1024 * 1024):
    try:
        with open_shared(path) as f:
            return f.read(limit)
    except OSError:
        return ""


def read_mod():
    d = json.loads(json.dumps(MOD_DEFAULTS))
    for line in shared_read(I().MOD_FILE, 256 * 1024).splitlines():
        m = re.fullmatch(r"\s*(\w+)\s*=\s*(.*?)\s*", line)
        if not m:
            continue
        k, v = m.groups()
        if k in ("admins", "words"):
            d[k] = [x.strip() for x in v.split(",") if x.strip()][:500]
        elif k in ("filter", "spam", "antibot", "verify"):
            d[k] = v.lower() == "on"
        elif k == "guests":
            d["guests"] = v.lower() != "block"
        elif k in ("spam_limit", "per_ip", "join_flood") and v.isdigit() and int(v) <= 100:
            d[k] = int(v)
    return d


def write_mod(d):
    onoff = lambda b: "on" if b else "off"
    shared_write(I().MOD_FILE,
                 "# Managed by the BeamMP EasyServer dashboard (Config -> Moderation).\n"
                 "admins=%s\nfilter=%s\nwords=%s\nspam=%s\nspam_limit=%d\nantibot=%s\nverify=%s\nper_ip=%d\njoin_flood=%d\nguests=%s\n" % (
                     ",".join(d["admins"]), onoff(d["filter"]), ",".join(d["words"]), onoff(d["spam"]), d["spam_limit"],
                     onoff(d["antibot"]), onoff(d["verify"]), d["per_ip"], d["join_flood"],
                     "allow" if d["guests"] else "block"))


def read_bans():
    out, t = [], now()
    for line in shared_read(I().BANS_FILE).splitlines():
        p = line.split("\t")
        if len(p) >= 2 and p[1].isdigit():
            u = int(p[1])
            if u == 0 or u > t:
                out.append({"name": p[0][:64], "until": u, "reason": (p[2] if len(p) > 2 else "")[:200],
                            "by": (p[3] if len(p) > 3 else "")[:64], "at": int(p[4]) if len(p) > 4 and p[4].isdigit() else 0})
    return out


def write_bans(bans):
    clean = lambda x: re.sub(r"[\t\r\n]", " ", str(x))
    shared_write(I().BANS_FILE, "".join("%s\t%d\t%s\t%s\t%d\n" % (clean(b["name"]), b["until"], clean(b["reason"]), clean(b["by"]), b["at"])
                                        for b in bans[:5000]))


def ban_player(name, until, reason, by):
    bans = [b for b in read_bans() if b["name"].lower() != name.lower()]
    bans.insert(0, {"name": name, "until": until, "reason": reason, "by": by, "at": now()})
    write_bans(bans)


def unban_player(name):
    bans = read_bans()
    hit = [b["name"] for b in bans if b["name"].lower() == name.lower()]
    write_bans([b for b in bans if b["name"].lower() != name.lower()])
    return hit[0] if hit else None


_ACTION_LOCK = threading.Lock()


def queue_action(action, name="", num="", text=""):
    """Tell the plugin to do something now (kick, mute, chat message). It reads
    the file every second; old lines are dropped after a while."""
    clean = lambda x: re.sub(r"[\t\r\n]", " ", str(x))
    with _ACTION_LOCK:
        lines = [l for l in shared_read(I().ACTIONS_FILE, 256 * 1024).splitlines() if re.match(r"\d+\t\d+\t", l)]
        seq = max([int(l.split("\t")[0]) for l in lines] or [0]) + 1
        lines = lines[-40:] + ["%d\t%d\t%s\t%s\t%s\t%s" % (seq, now(), action, clean(name), num, clean(text)[:300])]
        shared_write(I().ACTIONS_FILE, "\n".join(lines) + "\n")


RESTART_DEFAULTS = {"on": False, "every": 24, "at": "05:00", "warn": 10, "when": "countdown"}


def restart_cfg(inst):
    r = dict(RESTART_DEFAULTS)
    m = inst.meta.get("restart")
    if isinstance(m, dict):
        r.update({k: m[k] for k in RESTART_DEFAULTS if k in m})
    return r


def fmt_secs(sec):
    if sec >= 120:
        return "%d minutes" % round(sec / 60.0)
    if sec >= 60:
        return "1 minute"
    return "%d seconds" % sec


def online_names():
    o = read_json(os.path.join(I().STATS_DIR, "online.json"), None)
    if isinstance(o, dict) and now() - int(o.get("t", 0)) < 120:
        return [str(p)[:64] for p in o.get("players", [])][:200]
    return []


def chat_say(text):
    queue_action("say", text=text)


# ----------------------------------------------------------------------------- analytics
def read_events(since=0):
    evs = []
    for name in ("events.log.1", "events.log"):
        try:
            with open_shared(os.path.join(I().STATS_DIR, name), "rb") as f:
                size = os.fstat(f.fileno()).st_size
                if size > 32 * 1024 ** 2:           # only the newest part of a huge log
                    f.seek(size - 32 * 1024 ** 2)
                for line in f.read(32 * 1024 ** 2).decode("utf-8", "replace").splitlines():
                    try:
                        e = json.loads(line)
                        if isinstance(e, dict) and isinstance(e.get("t"), int) and e["t"] >= since:
                            evs.append(e)
                    except ValueError:
                        continue
        except OSError:
            continue
    evs.sort(key=lambda e: e["t"])
    return evs


def analytics(max_players):
    t_now = now()
    since = t_now - 90 * 86400
    evs = read_events(since)
    sessions, open_s, samples = [], {}, []
    last_t = None
    for e in evs:
        ev, t = e.get("ev"), e["t"]
        if ev == "start":
            for name, st in open_s.items():
                sessions.append((name, st, last_t or st))
            open_s = {}
        elif ev == "join" and e.get("name"):
            name = str(e["name"])[:64]
            if name in open_s:
                sessions.append((name, open_s[name], t))
            open_s[name] = t
        elif ev == "leave" and e.get("name"):
            name = str(e["name"])[:64]
            if name in open_s:
                sessions.append((name, open_s.pop(name), t))
        elif ev == "count" and isinstance(e.get("n"), int):
            samples.append((t, e["n"]))
        last_t = t
    for name, st in open_s.items():
        sessions.append((name, st, t_now))
    sessions = [(n, a, max(a, b)) for n, a, b in sessions]

    online = {"fresh": False, "players": []}
    o = read_json(os.path.join(I().STATS_DIR, "online.json"), None)
    if isinstance(o, dict) and t_now - int(o.get("t", 0)) < 120:
        online = {"fresh": True, "players": [str(p)[:64] for p in o.get("players", [])][:200]}

    def window(days):
        lim = t_now - days * 86400
        return [s for s in sessions if s[2] >= lim]

    s30 = window(30)
    play = {}
    for n, a, b in s30:
        p = play.setdefault(n, {"name": n, "seconds": 0, "sessions": 0, "last_seen": 0})
        p["seconds"] += b - a
        p["sessions"] += 1
        p["last_seen"] = max(p["last_seen"], b)
    top = sorted(play.values(), key=lambda p: -p["seconds"])[:10]

    lt = time.localtime
    days = []
    for d in range(29, -1, -1):
        day_start = time.mktime(time.struct_time(lt(t_now - d * 86400)[:3] + (0, 0, 0, 0, 0, -1)))
        day_end = day_start + 86400
        uniq = {n for n, a, b in sessions if a < day_end and b >= day_start}
        peak = max([n for t, n in samples if day_start <= t < day_end] or [0])
        hours = sum(max(0, min(b, day_end) - max(a, day_start)) for _, a, b in sessions) / 3600
        days.append({"date": time.strftime("%Y-%m-%d", lt(day_start)), "players": len(uniq),
                     "peak": peak, "hours": round(hours, 1)})

    heat = [[[0, 0] for _ in range(24)] for _ in range(7)]
    s30_samples = [(t, n) for t, n in samples if t >= t_now - 30 * 86400]
    for t, n in s30_samples:
        tm = lt(t)
        cell = heat[tm.tm_wday][tm.tm_hour]
        cell[0] += n
        cell[1] += 1
    heatmap = [[round(c[0] / c[1], 2) if c[1] else None for c in row] for row in heat]
    hourly = []
    for h in range(24):
        vals = [n for t, n in s30_samples if lt(t).tm_hour == h]
        hourly.append(round(sum(vals) / len(vals), 2) if vals else 0)
    peak_sample = max(s30_samples, key=lambda x: x[1]) if s30_samples else None
    avg = sum(n for _, n in s30_samples) / len(s30_samples) if s30_samples else 0
    busiest = max(range(24), key=lambda h: hourly[h]) if any(hourly) else None
    total_secs = sum(b - a for _, a, b in s30)
    recent = sorted(sessions, key=lambda s: -s[1])[:25]
    return {
        "online": online,
        "summary": {
            "unique_7d": len({n for n, *_ in window(7)}),
            "unique_30d": len({n for n, *_ in s30}),
            "sessions_30d": len(s30),
            "hours_30d": round(total_secs / 3600, 1),
            "avg_session_min": round(total_secs / len(s30) / 60, 1) if s30 else 0,
            "peak": peak_sample[1] if peak_sample else 0,
            "peak_at": peak_sample[0] if peak_sample else None,
            "utilization": round(100 * avg / max_players, 1) if max_players else 0,
            "avg_players": round(avg, 2),
            "busiest_hour": busiest,
        },
        "days": days, "heatmap": heatmap, "hourly": hourly, "top": top,
        "recent": [{"name": n, "start": a, "end": b, "minutes": round((b - a) / 60)} for n, a, b in recent],
        "has_data": bool(evs),
    }


# ----------------------------------------------------------------------------- network checks
def lan_ip():
    ips = [i for i in tlsgen.local_ips() if i != "127.0.0.1"]
    return ips[0] if ips else "127.0.0.1"


_PUBLIC_IP = {"t": 0, "ip": None}


def public_ip():
    if time.time() - _PUBLIC_IP["t"] < 3600:
        return _PUBLIC_IP["ip"]
    ip = _public_ip()
    _PUBLIC_IP.update(t=time.time() if ip else time.time() - 3300, ip=ip)
    return ip


def _public_ip():
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BeamMP-EasyServer"})
            with urllib.request.urlopen(req, timeout=6) as r:
                ip = r.read(64).decode().strip()
                ipaddress.ip_address(ip)
                return ip
        except Exception:
            continue
    return None


def relay_ports():
    rp = APP.settings.get("relay_ports") if APP else None
    return rp if isinstance(rp, dict) else {}


def relay_servers():
    with LOCK:
        insts = sorted(INSTANCES.values(), key=lambda i: (i.id != "main", i.id))
    rp = relay_ports()
    return [{"id": i.id, "name": i.name, "port": i.port(), "relay_port": rp.get(i.id)} for i in insts]


def game_ports():
    with LOCK:
        insts = list(INSTANCES.values())
    return sorted({p for p in (i.port() for i in insts) if isinstance(p, int) and 1024 <= p <= 65535})


def relay_on():
    return bool(APP and APP.settings.get("relay_enabled") and APP.settings.get("relay_host"))


def game_address(inst=None):
    """(host, port, via_relay): the address players should use to join a server.
    With "Hide my IP" on it's the relay, never the home address."""
    inst = inst or I()
    port = inst.port() or 30814
    if relay_on():
        rp = relay_ports().get(inst.id)
        return APP.settings.get("relay_host"), (rp if isinstance(rp, int) else port), True
    return public_ip() or lan_ip(), port, False


def fmt_addr(host, port):
    return ("[%s]:%s" if ":" in str(host) else "%s:%s") % (host, port)


def tcp_open(host, port, timeout=3.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def listening(port):
    """Is something listening on this port (TCP) / bound (UDP)? Returns (tcp, udp)."""
    tcp = udp = False
    if IS_WIN:
        try:
            out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=15,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            for line in out.splitlines():
                p = line.split()
                if len(p) >= 2 and p[1].endswith(":%d" % port):
                    if p[0] == "TCP" and "LISTENING" in line:
                        tcp = True
                    if p[0] == "UDP":
                        udp = True
        except (OSError, subprocess.TimeoutExpired):
            pass
        return tcp, udp
    hexport = ":%04X" % port
    for name in ("tcp", "tcp6", "udp", "udp6"):
        try:
            with open("/proc/net/" + name) as f:
                next(f)
                for line in f:
                    p = line.split()
                    if len(p) > 3 and p[1].endswith(hexport):
                        if name.startswith("tcp") and p[3] == "0A":
                            tcp = True
                        if name.startswith("udp"):
                            udp = True
        except OSError:
            continue
    return tcp, udp


def server_list_lookup(ip, port):
    req = urllib.request.Request("https://backend.beammp.com/servers-info",
                                 headers={"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
    with urllib.request.urlopen(req, timeout=30) as r:
        servers = json.loads(r.read(20 * 1024 * 1024))
    for s in servers if isinstance(servers, list) else []:
        try:
            if str(s.get("ip")) == ip and int(s.get("port")) == int(port):
                return {"listed": True, "players": s.get("players"), "maxplayers": s.get("maxplayers"),
                        "name": re.sub(r"\^.", "", str(s.get("sname", "")))[:120]}
        except (TypeError, ValueError):
            continue
    return {"listed": False}


def network_check(cfg, status, deep):
    g = cfg.get("General", {})
    port = g.get("Port") if isinstance(g.get("Port"), int) else 30814
    private = g.get("Private") is True
    running = status.get("state") == "running"
    tcp, udp = listening(port)
    if status.get("state") == "unknown" and tcp and udp:
        running = True      # service manager unavailable, but the server answers
    checks, tips = [], []

    def c(name, state, detail):
        checks.append({"name": name, "state": state, "detail": detail})

    c("Server running", "ok" if running else "bad",
      "The BeamMP server is running" if running else "The server isn't running - start it first")
    if running:
        c("Listening on port %d" % port, "ok" if (tcp and udp) else "bad",
          "TCP and UDP are open on this computer" if (tcp and udp) else
          "TCP %s, UDP %s - check the server log" % ("open" if tcp else "closed", "open" if udp else "closed"))
    elif tcp or udp:
        c("Port %d free" % port, "bad", "Another program is using port %d - change the port or close it" % port)
    else:
        c("Port %d free" % port, "ok", "Nothing else is using the port")
    lip = lan_ip()
    if running and tcp:
        ok = tcp_open(lip, port)
        c("Reachable on your home network", "ok" if ok else "warn",
          ("Friends on your Wi-Fi can connect to %s:%d" % (lip, port)) if ok else
          "Couldn't connect via %s - a firewall may be blocking it" % lip)
    pip = public_ip()
    if relay_on():
        rhost, rport, _ = game_address()
        c("Hide my IP", "ok", "On - players join through the relay at %s instead of your home address" % fmt_addr(rhost, rport))
        if running and tcp:
            ok = tcp_open(rhost, rport, timeout=5)
            c("Reachable through the relay (quick test)", "ok" if ok else "bad",
              "The relay forwards to this server" if ok else
              "Nothing answers at %s. Check that the relay (playit.gg, VPN or your VPS tunnel) is running "
              "and forwards TCP and UDP to port %d on this computer." % (fmt_addr(rhost, rport), port))
            if pip:
                direct = tcp_open(pip, port, timeout=4)
                c("Direct access to your home", "warn" if direct else "ok",
                  ("Port %d is still open on your home IP %s - remove the port forward on your router, "
                   "otherwise attackers can still find and hit you directly." % (port, pip)) if direct else
                  "Closed (or your router blocks this test) - players can only come in through the relay")
        if not private:
            c("Public server list", "warn",
              "Your server is on the public list. The list shows the address the server reports from - with "
              "playit.gg and most relays that's your home IP. Make the server private (Config → Private server) "
              "and give players the relay address, unless all of this computer's traffic goes through the relay.")
        if deep and pip and not private:
            try:
                if server_list_lookup(pip, port)["listed"]:
                    c("Server list leak", "bad", "The server list shows your HOME address (%s). Make the server "
                      "private, or send the server's internet traffic through the relay as well." % pip)
                    tips.append("If your home IP has already been shared, restart your router - most providers "
                                "then give you a new IP address.")
                else:
                    c("Server list leak", "ok", "Your home address isn't in the server list")
            except Exception as e:
                c("Server list leak", "warn", "Couldn't download the server list (%s)" % e.__class__.__name__)
    elif pip:
        c("Public IP address", "ok", "Friends over the internet connect to %s:%d" % (pip, port))
        if running and tcp:
            ok = tcp_open(pip, port, timeout=4)
            c("Reachable from the internet (quick test)", "ok" if ok else "warn",
              "Your router forwards port %d" % port if ok else
              "Not reachable via your public IP from here. Many routers block this test even when port "
              "forwarding works - use the server list check below to be sure.")
            if not ok:
                tips.append("Forward port %d (TCP and UDP) on your router to %s. Search for "
                            "\"<your router model> port forwarding\"." % (port, lip))
    else:
        c("Public IP address", "warn", "Couldn't find your public IP (no internet?)")
    if deep and pip and not relay_on():
        if private:
            c("Public server list", "info", "Your server is private, so it's hidden from the list on purpose")
        else:
            try:
                r = server_list_lookup(pip, port)
                if r["listed"]:
                    c("Public server list", "ok", "Listed as \"%s\" (%s/%s players) - players can find and join it" %
                      (r["name"], r.get("players"), r.get("maxplayers")))
                else:
                    c("Public server list", "bad", "Not in the BeamMP server list. Check your AuthKey and port forwarding.")
                    tips.append("If you just started the server, wait 1-2 minutes and check again.")
            except Exception as e:
                c("Public server list", "warn", "Couldn't download the server list (%s)" % e.__class__.__name__)
    if not IS_WIN:
        fw = control("firewall-status", timeout=20)
        if fw.get("ok") and fw.get("data"):
            c("Firewall", "info", fw["data"])
    if pip and not relay_on() and ipaddress.ip_address(pip) in ipaddress.ip_network("100.64.0.0/10"):
        tips.append("Your provider uses CGNAT (shared IP) - port forwarding won't work. Ask them for a public IPv4 address.")
    if relay_on():
        pip = None      # don't show the home address on a page that's about the relay
    return {"port": port, "lan_ip": lip, "public_ip": pip, "checks": checks, "tips": tips,
            "relay": fmt_addr(*game_address()[:2]) if relay_on() else None}


# ----------------------------------------------------------------------------- updates
def github_latest(repo):
    req = urllib.request.Request("https://api.github.com/repos/%s/releases/latest" % repo,
                                 headers={"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION,
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        tag = json.loads(r.read(2 * 1024 * 1024)).get("tag_name", "")
    m = re.search(r"(\d+\.\d+\.\d+)", tag)
    return m.group(1) if m else None


def newer(a, b):
    try:
        return tuple(map(int, a.split("."))) > tuple(map(int, b.split(".")))
    except (AttributeError, ValueError):
        return False


# ----------------------------------------------------------------------------- logs + hints
LOG_HINTS = [
    (r"(?i)authkey.*(invalid|wrong|not|length)|invalid.*auth", "AuthKey problem",
     "Your AuthKey looks wrong. Get a new one at keymaster.beammp.com and set it under Config → AuthKey."),
    (r"(?i)address already in use|failed to bind|bind failed", "Port already in use",
     "Another program uses the server port. Change the port under Config or close the other program."),
    (r"(?i)backend\.beammp\.com.*(failed|error)|heartbeat failed", "Can't reach BeamMP servers",
     "The server can't talk to BeamMP's backend (internet or firewall problem). LAN play still works."),
    (r"(?i)IP_V6ONLY", "IPv6 notice", "Harmless: your system can't share one socket for IPv4 and IPv6."),
    (r"(?i)\[LUA\].*error|lua error", "Plugin error", "A server plugin (Resources/Server) has a Lua error. Check or remove it."),
    (r"(?i)permission denied", "Permission problem", "The server couldn't read or write a file. Re-run the installer to fix permissions."),
    (r"(?i)failed to load|could not load|not a valid zip|corrupt", "Broken mod",
     "A mod file may be damaged. Re-download it or turn it off on the Mods page."),
]


def tail_log(lines=300):
    try:
        with open(I().SERVER_LOG, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 256 * 1024))
            data = f.read().decode("utf-8", "replace")
    except OSError:
        return [], []
    out = data.splitlines()[-lines:]
    hints, seen = [], set()
    for line in out:
        for pat, title, text in LOG_HINTS:
            if title not in seen and re.search(pat, line):
                seen.add(title)
                hints.append({"title": title, "text": text, "line": line[-300:]})
    return out, hints


# ----------------------------------------------------------------------------- QR code (for two-step setup)
# Small QR encoder: byte mode, error correction level M, versions 1-15.
# Only used to show the two-step login key as a QR code; no extra packages needed.
_QR_M = {  # version: (ec codewords per block, [(blocks, data codewords per block), ...])
    1: (10, [(1, 16)]), 2: (16, [(1, 28)]), 3: (26, [(1, 44)]), 4: (18, [(2, 32)]),
    5: (24, [(2, 43)]), 6: (16, [(4, 27)]), 7: (18, [(4, 31)]), 8: (22, [(2, 38), (2, 39)]),
    9: (22, [(3, 36), (2, 37)]), 10: (26, [(4, 43), (1, 44)]), 11: (30, [(1, 50), (4, 51)]),
    12: (22, [(6, 36), (2, 37)]), 13: (22, [(8, 37), (1, 38)]), 14: (24, [(4, 40), (5, 41)]),
    15: (24, [(5, 41), (5, 42)]),
}
_QR_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38],
             8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50], 11: [6, 30, 54], 12: [6, 32, 58],
             13: [6, 34, 62], 14: [6, 26, 46, 66], 15: [6, 26, 48, 70]}


def _qr_gf_mul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a <<= 1
        if a & 0x100:
            a ^= 0x11D
        b >>= 1
    return r


def _qr_ecc(data, n):
    gen = [1]
    root = 1
    for _ in range(n):
        nxt = [0] * (len(gen) + 1)
        for i, g in enumerate(gen):
            nxt[i] ^= g
            nxt[i + 1] ^= _qr_gf_mul(g, root)
        gen = nxt
        root = _qr_gf_mul(root, 2)
    rem = [0] * n
    for byte in data:
        f = byte ^ rem[0]
        rem = rem[1:] + [0]
        for i in range(n):
            rem[i] ^= _qr_gf_mul(gen[i + 1], f)
    return rem


def qr_matrix(text):
    """Return the QR code for text as a list of rows of booleans (True = dark)."""
    data = text.encode("utf-8")
    for ver in range(1, 16):
        ec, groups = _QR_M[ver]
        cap = sum(b * d for b, d in groups)
        lenbits = 8 if ver < 10 else 16
        if 4 + lenbits + 8 * len(data) <= cap * 8:
            break
    else:
        raise ValueError("text too long for a QR code")
    bits = [0, 1, 0, 0] + [(len(data) >> i) & 1 for i in range(lenbits - 1, -1, -1)]
    for byte in data:
        bits += [(byte >> i) & 1 for i in range(7, -1, -1)]
    bits += [0] * min(4, cap * 8 - len(bits))
    bits += [0] * (-len(bits) % 8)
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(words) < cap:
        words.append(pad)
        pad ^= 0xEC ^ 0x11
    blocks, k = [], 0
    for count, size in groups:
        for _ in range(count):
            blocks.append(words[k:k + size])
            k += size
    eccs = [_qr_ecc(b, ec) for b in blocks]
    final = []
    for i in range(max(len(b) for b in blocks)):
        final += [b[i] for b in blocks if i < len(b)]
    for i in range(ec):
        final += [e[i] for e in eccs]

    size = ver * 4 + 17
    mod = [[False] * size for _ in range(size)]
    fixed = [[False] * size for _ in range(size)]

    def put(x, y, dark):
        mod[y][x] = dark
        fixed[y][x] = True

    for i in range(size):  # timing patterns
        put(6, i, i % 2 == 0)
        put(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):  # finder patterns + separators
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < size and 0 <= y < size:
                    d = max(abs(dx), abs(dy))
                    put(x, y, d not in (2, 4))
    al = _QR_ALIGN[ver]
    for i, ax in enumerate(al):
        for j, ay in enumerate(al):
            if (i == 0 and j == 0) or (i == 0 and j == len(al) - 1) or (i == len(al) - 1 and j == 0):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    put(ax + dx, ay + dy, max(abs(dx), abs(dy)) != 1)

    def draw_format(mask):
        val = (0 << 3) | mask  # level M = 00
        rem = val
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        fb = ((val << 10) | rem) ^ 0x5412
        b = [(fb >> i) & 1 == 1 for i in range(15)]
        for i in range(6):
            put(8, i, b[i])
        put(8, 7, b[6])
        put(8, 8, b[7])
        put(7, 8, b[8])
        for i in range(9, 15):
            put(14 - i, 8, b[i])
        for i in range(8):
            put(size - 1 - i, 8, b[i])
        for i in range(8, 15):
            put(8, size - 15 + i, b[i])
        put(8, size - 8, True)

    draw_format(0)  # reserve the format areas
    if ver >= 7:
        rem = ver
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        vb = (ver << 12) | rem
        for i in range(18):
            dark = (vb >> i) & 1 == 1
            a, b = size - 11 + i % 3, i // 3
            put(a, b, dark)
            put(b, a, dark)

    allbits = [(w >> i) & 1 for w in final for i in range(7, -1, -1)]
    i = 0
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                x = right - j
                upward = ((right + 1) & 2) == 0
                y = size - 1 - vert if upward else vert
                if not fixed[y][x]:
                    if i < len(allbits):
                        mod[y][x] = allbits[i] == 1
                    i += 1
        right -= 2

    masks = [
        lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
        lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
        lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
        lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
    ]

    def penalty(m):
        p = 0
        lines = m + [list(c) for c in zip(*m)]
        for row in lines:
            run, prev = 0, None
            for v in row:
                if v == prev:
                    run += 1
                else:
                    if run >= 5:
                        p += run - 2
                    run, prev = 1, v
            if run >= 5:
                p += run - 2
            s = "".join("1" if v else "0" for v in row)
            p += 40 * (s.count("10111010000") + s.count("00001011101"))
        for y in range(size - 1):
            for x in range(size - 1):
                if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    p += 3
        dark = sum(sum(r) for r in m)
        p += 10 * (abs(dark * 20 - size * size * 10) // (size * size))
        return p

    base = [r[:] for r in mod]
    best = None
    for mi, fn in enumerate(masks):
        for y in range(size):
            for x in range(size):
                mod[y][x] = base[y][x] ^ (not fixed[y][x] and fn(x, y))
        draw_format(mi)
        score = penalty(mod)
        if best is None or score < best[0]:
            best = (score, [r[:] for r in mod])
    return best[1]


def qr_svg_path(text):
    """QR code as (size, SVG path data) - one 1x1 square per dark module."""
    m = qr_matrix(text)
    d = []
    for y, row in enumerate(m):
        x = 0
        while x < len(row):
            if row[x]:
                start = x
                while x < len(row) and row[x]:
                    x += 1
                d.append("M%d %dh%dv1h-%dz" % (start, y, x - start, x - start))
            else:
                x += 1
    return len(m), "".join(d)


# ----------------------------------------------------------------------------- auth helpers
def totp_code(secret_b32, counter):
    key = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8), casefold=True)
    h = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    return "%06d" % ((struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000)


def ip_is_lan(ip):
    try:
        a = ipaddress.ip_address(ip)
        if a.version == 6 and a.ipv4_mapped:
            a = a.ipv4_mapped
        return a.is_private or a.is_loopback or a.is_link_local
    except ValueError:
        return False


def fail_key(ip):
    """Address used for login lockouts. IPv6 users can pick any address in their
    /64 network, so the whole /64 counts as one address."""
    try:
        a = ipaddress.ip_address(ip)
        if a.version == 6 and a.ipv4_mapped:
            return str(a.ipv4_mapped)
        if a.version == 6:
            return str(ipaddress.ip_network(str(a) + "/64", strict=False))
        return str(a)
    except ValueError:
        return str(ip)


LOCAL_SUFFIXES = (".local", ".lan", ".home", ".home.arpa", ".internal", ".localdomain", ".box",
                  ".router", ".intranet", ".private", ".corp", ".localnet", ".gateway")


def host_name(host_header):
    """The host part of a Host header ('[::1]:30815' -> '::1'), lower case."""
    h = (host_header or "").strip().lower()
    if h.startswith("["):
        return h[1:h.find("]")] if "]" in h else ""
    return h.rsplit(":", 1)[0] if h.count(":") == 1 else h


def host_is_local_name(host):
    if host in ("localhost",) or host.endswith(".localhost"):
        return True
    try:
        ipaddress.ip_address(host)
        return True                 # a plain address can't be used for DNS rebinding
    except ValueError:
        pass
    return bool(re.fullmatch(r"[a-z0-9-]{1,63}", host)) or host.endswith(LOCAL_SUFFIXES)


def ip_is_loopback(ip):
    try:
        a = ipaddress.ip_address(ip)
        if a.version == 6 and a.ipv4_mapped:
            a = a.ipv4_mapped
        return a.is_loopback
    except ValueError:
        return False


# ============================================================================= the app
# ----------------------------------------------------------------------------- Discord bot (slash commands)
# /status for everyone; /start, /stop and /restart for people with "Manage
# Server" in your Discord (or the user IDs you list). The bot connects out to
# Discord (no port forwarding needed) and only answers in the one Discord
# server you pick in Settings, so a stranger who adds it elsewhere gets nothing.
DISCORD_API = os.environ.get("ES_DISCORD_API") or "https://discord.com/api/v10"          # override: tests only
DISCORD_GATEWAY = os.environ.get("ES_DISCORD_GATEWAY") or "wss://gateway.discord.gg/?v=10&encoding=json"
DISCORD_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]{20,100}\.[A-Za-z0-9_\-]{4,20}\.[A-Za-z0-9_\-]{20,100}")
PERM_ADMIN, PERM_MANAGE_GUILD = 0x8, 0x20
STATE_EMOJI = {"running": "🟢", "stopped": "🔴", "failed": "🔴", "starting": "🟡", "restarting": "🟡", "stopping": "🟡"}


def discord_api(method, path, token=None, body=None, timeout=20):
    headers = {"User-Agent": "DiscordBot (https://github.com/Csabika-dev/beammp-easyserver, %s)" % EASY_VERSION}
    if token:
        headers["Authorization"] = "Bot " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(DISCORD_API + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


class WSClosed(Exception):
    def __init__(self, code):
        super().__init__("Discord closed the connection (%s)" % code)
        self.code = code


class MiniWebSocket:
    """Just enough of a WebSocket client (RFC 6455) for the Discord gateway."""

    def __init__(self, url, timeout=90):
        u = urllib.parse.urlsplit(url)
        raw = socket.create_connection((u.hostname, u.port or (80 if u.scheme == "ws" else 443)), timeout=30)
        self.s = raw if u.scheme == "ws" else ssl.create_default_context().wrap_socket(raw, server_hostname=u.hostname)
        key = base64.b64encode(os.urandom(16)).decode()
        path = (u.path or "/") + ("?" + u.query if u.query else "")
        self.s.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nUser-Agent: BeamMP-EasyServer/%s\r\n\r\n"
                        % (path, u.hostname, key, EASY_VERSION)).encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.s.recv(4096)
            if not chunk or len(resp) > 65536:
                raise OSError("Discord didn't accept the connection")
            resp += chunk
        head, self.buf = resp.split(b"\r\n\r\n", 1)
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        if b" 101 " not in head.split(b"\r\n", 1)[0] + b" " or accept not in head:
            raise OSError("Discord didn't accept the connection")
        self.s.settimeout(timeout)
        self.lock = threading.Lock()

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(65536)
            if not chunk:
                raise WSClosed("connection lost")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, data, op=1):
        data = data.encode() if isinstance(data, str) else data
        n, mask = len(data), os.urandom(4)
        head = bytes([0x80 | op])
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", n)
        body = bytes(b ^ mask[i & 3] for i, b in enumerate(data))
        with self.lock:
            self.s.sendall(head + mask + body)

    def recv(self):
        msg = b""
        while True:
            b1, b2 = self._read(2)
            op, n = b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            if n > 16 * 1048576:
                raise WSClosed("message too big")
            mask = self._read(4) if b2 & 0x80 else None
            data = self._read(n)
            if mask:
                data = bytes(b ^ mask[i & 3] for i, b in enumerate(data))
            if op == 8:
                raise WSClosed(struct.unpack(">H", data[:2])[0] if len(data) >= 2 else 1000)
            if op == 9:
                self.send(data, 10)
                continue
            if op == 10:
                continue
            msg += data
            if b1 & 0x80:
                return msg.decode("utf-8", "replace")

    def close(self):
        try:
            self.send(struct.pack(">H", 1000), 8)
        except Exception:
            pass
        try:
            self.s.shutdown(socket.SHUT_RDWR)     # wakes up a recv() waiting in the other thread
        except Exception:
            pass
        try:
            self.s.close()
        except Exception:
            pass


def discord_server_status():
    """One embed field per server: state, players, map, CPU and memory."""
    with LOCK:
        insts = sorted(INSTANCES.values(), key=lambda i: (i.id != "main", i.id))
    cpus = os.cpu_count() or 1
    fields = []
    for inst in insts:
        use_server(inst.id)
        st = inst.server.status()["state"]
        data, _, _ = toml_parse(APP.read_config_text())
        g = data.get("General", {})
        lines = []
        if st == "running":
            players = analytics_online()
            u = inst.server.usage()
            if u.get("cpu_cores") is None:
                time.sleep(1)
                u = inst.server.usage()
            lines.append("👥 **%d/%s** players" % (len(players), APP.max_players()))
            if players:
                lines.append(", ".join(discord_escape(p) for p in players[:20]) + (" …" if len(players) > 20 else ""))
            lines.append("🗺️ %s" % discord_escape(map_name(g.get("Map")) or "?"))
            use = []
            if u.get("cpu_cores") is not None:
                use.append("CPU %d%%" % round(u["cpu_cores"] * 100 / cpus))
            if u.get("mem_mb") is not None:
                use.append("RAM %s MB" % u["mem_mb"])
            if use:
                lines.append("⚙️ " + " · ".join(use))
            up = inst.server.status().get("uptime") or 0
            if up:
                lines.append("⏱️ up %s" % fmt_uptime(up))
        else:
            lines.append(st.capitalize())
        fields.append({"name": "%s %s" % (STATE_EMOJI.get(st, "⚪"), discord_escape(inst.name))[:250],
                       "value": "\n".join(lines)[:1000], "inline": False})
    return fields


def fmt_uptime(sec):
    d, h, m = sec // 86400, sec % 86400 // 3600, sec % 3600 // 60
    return ("%dd %dh" % (d, h)) if d else ("%dh %dm" % (h, m)) if h else "%d min" % max(m, 1)


def discord_escape(s):
    return re.sub(r"([\\*_~`|>@#<])", r"\\\1", str(s))


class DiscordBot:
    def __init__(self, app):
        self.app = app
        self.state, self.error = "off", ""
        self.app_id = self.user = None
        self.guilds = {}              # id -> name, the Discord servers the bot is in
        self.ws = None
        self.wake = threading.Event()
        self.registered = {}          # guild id -> commands json we last sent
        self.busy = set()

    def info(self):
        s = self.app.settings
        with LOCK:
            guilds = [{"id": k, "name": v} for k, v in sorted(self.guilds.items(), key=lambda x: x[1].lower())]
        return {"enabled": bool(s.get("discord_bot")), "has_token": self.app.secrets.has("DISCORD_BOT_TOKEN"),
                "state": self.state, "error": self.error, "bot_name": self.user, "app_id": self.app_id,
                "guild": s.get("discord_bot_guild") or "", "guilds": guilds,
                "users": s.get("discord_bot_users") or [],
                "invite": ("https://discord.com/oauth2/authorize?client_id=%s&scope=bot%%20applications.commands&permissions=0"
                           % self.app_id) if self.app_id else None}

    def reconnect(self):
        ws, self.ws = self.ws, None
        if ws:
            ws.close()
        self.wake.set()

    # ---------- connection loop
    def run(self):
        backoff = 5
        while True:
            token = self.app.secrets.get("DISCORD_BOT_TOKEN")
            if not (self.app.settings.get("discord_bot") and token):
                self.state, self.error, self.guilds = "off", "", {}
                self.wake.wait(60)
                self.wake.clear()
                continue
            self.state, self.error = "connecting", ""
            try:
                self.session(token)
                backoff = 5
            except WSClosed as e:
                self.state = "error"
                if e.code == 4004:
                    self.error = "Discord rejected the bot token. Copy a new one (Developer Portal → Bot → Reset Token)."
                    backoff = 3600
                else:
                    self.error = str(e)
            except (OSError, ValueError) as e:
                self.state = "error"
                self.error = "Can't reach Discord right now (%s) - trying again in a moment." % short_err(e)
            except Exception as e:
                self.state, self.error = "error", short_err(e)
            finally:
                ws, self.ws = self.ws, None
                if ws:
                    ws.close()
            if self.wake.wait(backoff):
                backoff = 5
            else:
                backoff = min(backoff * 2, 300)
            self.wake.clear()

    def session(self, token):
        ws = self.ws = MiniWebSocket(DISCORD_GATEWAY)
        hello = json.loads(ws.recv())
        interval = hello["d"]["heartbeat_interval"] / 1000.0
        ws.s.settimeout(interval * 2 + 10)
        st = {"seq": None, "acked": True}

        def beat():
            time.sleep(interval * 0.5)
            while self.ws is ws:
                if not st["acked"]:
                    ws.close()
                    return
                st["acked"] = False
                try:
                    ws.send(json.dumps({"op": 1, "d": st["seq"]}))
                    self.sync_commands(token)
                except Exception:
                    ws.close()
                    return
                time.sleep(interval)

        threading.Thread(target=beat, daemon=True).start()
        ws.send(json.dumps({"op": 2, "d": {"token": token, "intents": 1,      # GUILDS: names of the Discord servers
                                           "properties": {"os": sys.platform, "browser": "beammp-easyserver",
                                                          "device": "beammp-easyserver"}}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("s") is not None:
                st["seq"] = m["s"]
            op, t, d = m.get("op"), m.get("t"), m.get("d") or {}
            if op == 11:
                st["acked"] = True
            elif op == 1:
                ws.send(json.dumps({"op": 1, "d": st["seq"]}))
            elif op in (7, 9):
                raise WSClosed("Discord asked to reconnect")
            elif op == 0 and t == "READY":
                self.app_id = str(d.get("application", {}).get("id") or "")
                u = d.get("user") or {}
                self.user = u.get("username")
                with LOCK:
                    self.guilds = {str(g["id"]): self.guilds.get(str(g["id"]), "Discord server " + str(g["id"]))
                                   for g in d.get("guilds", [])}
                self.registered = {}
                self.state = "online"
                threading.Thread(target=self.sync_commands, args=(token,), daemon=True).start()
            elif op == 0 and t in ("GUILD_CREATE", "GUILD_UPDATE") and d.get("id"):
                with LOCK:
                    self.guilds[str(d["id"])] = str(d.get("name") or d["id"])[:100]
                self.pick_guild()
            elif op == 0 and t == "GUILD_DELETE" and d.get("id") and not d.get("unavailable"):
                with LOCK:
                    self.guilds.pop(str(d["id"]), None)
            elif op == 0 and t == "INTERACTION_CREATE":
                threading.Thread(target=self.on_interaction, args=(d,), daemon=True).start()

    def pick_guild(self):
        """The first Discord server the bot joins becomes the one it answers in."""
        s = self.app.settings
        if s.get("discord_bot_guild"):
            return
        with LOCK:
            if len(self.guilds) != 1:
                return
            gid, name = next(iter(self.guilds.items()))
        s.update({"discord_bot_guild": gid})
        self.app.notifier.add("network", "Discord bot connected",
                              "The bot now answers commands in the Discord server \"%s\". You can change this under "
                              "Settings → Discord bot." % name, "success", send=False)

    # ---------- slash commands
    def commands(self):
        with LOCK:
            insts = sorted(INSTANCES.values(), key=lambda i: (i.id != "main", i.id))
        opts = []
        if len(insts) > 1:
            opts = [{"type": 3, "name": "server", "description": "Which server (default: the main one)", "required": False,
                     "choices": [{"name": i.name[:100], "value": i.id} for i in insts[:25]]}]
        admin = {"default_member_permissions": str(PERM_MANAGE_GUILD), "contexts": [0], "options": opts}
        return [
            {"name": "status", "description": "Show the BeamMP servers: online players, map, CPU and memory",
             "type": 1, "contexts": [0]},
            dict(admin, name="start", type=1, description="Start the BeamMP server"),
            dict(admin, name="stop", type=1, description="Stop the BeamMP server (kicks everyone)"),
            dict(admin, name="restart", type=1, description="Restart the BeamMP server"),
        ]

    def sync_commands(self, token):
        if not self.app_id:
            return
        gid = self.app.settings.get("discord_bot_guild") or ""
        want = {gid: json.dumps(self.commands(), sort_keys=True)} if gid else {}
        for old in [g for g in self.registered if g not in want]:
            try:
                discord_api("PUT", "/applications/%s/guilds/%s/commands" % (self.app_id, old), token, [])
            except Exception:
                pass
            self.registered.pop(old, None)
        for g, body in want.items():
            if self.registered.get(g) != body:
                discord_api("PUT", "/applications/%s/guilds/%s/commands" % (self.app_id, g), token, json.loads(body))
                self.registered[g] = body

    def on_interaction(self, d):
        if d.get("type") != 2:
            return
        iid, itok = d.get("id"), d.get("token")
        name = (d.get("data") or {}).get("name")
        cb = "/interactions/%s/%s/callback" % (iid, itok)
        edit = "/webhooks/%s/%s/messages/@original" % (self.app_id, itok)
        try:
            if str(d.get("guild_id") or "") != (self.app.settings.get("discord_bot_guild") or "x"):
                return discord_api("POST", cb, body={"type": 4, "data": {
                    "content": "This bot isn't set up for this Discord server.", "flags": 64}})
            member = d.get("member") or {}
            uid = str((member.get("user") or {}).get("id") or "")
            who = (member.get("user") or {}).get("global_name") or (member.get("user") or {}).get("username") or "someone"
            if name == "status":
                discord_api("POST", cb, body={"type": 5})
                return discord_api("PATCH", edit, body={"embeds": [{
                    "title": "BeamMP servers", "color": 0x3B82F6, "fields": discord_server_status(),
                    "footer": {"text": "BeamMP EasyServer"}}], "allowed_mentions": {"parse": []}})
            if name not in ("start", "stop", "restart"):
                return
            perms = int(member.get("permissions") or 0)
            if not (perms & (PERM_ADMIN | PERM_MANAGE_GUILD)) and uid not in (self.app.settings.get("discord_bot_users") or []):
                return discord_api("POST", cb, body={"type": 4, "data": {
                    "content": "Only people with **Manage Server** (or who are allowed in the dashboard) can do that.",
                    "flags": 64}})
            opts = {o.get("name"): o.get("value") for o in (d.get("data") or {}).get("options") or []}
            with LOCK:
                inst = INSTANCES.get(str(opts.get("server") or "main"))
            if not inst:
                return discord_api("POST", cb, body={"type": 4, "data": {"content": "That server doesn't exist any more.", "flags": 64}})
            discord_api("POST", cb, body={"type": 5})
            discord_api("PATCH", edit, body={"content": self.do_action(inst, name, who), "allowed_mentions": {"parse": []}})
        except Exception as e:
            sys.stderr.write("discord command: %s\n" % short_err(e))

    def do_action(self, inst, what, who):
        use_server(inst.id)
        label = "**%s**" % discord_escape(inst.name)
        if inst.id in self.busy:
            return "⏳ %s is already being started or stopped - try again in a minute." % label
        st = inst.server.status()["state"]
        if what == "start":
            if not inst.meta.get("reviewed"):
                return ("⚠️ %s has never been started. Open the dashboard once, check its settings and press Start there "
                        "- after that you can start it from Discord." % label)
            if st == "running":
                return "🟢 %s is already running." % label
        if what == "stop" and st in ("stopped", "failed"):
            return "🔴 %s is already stopped." % label
        self.busy.add(inst.id)
        try:
            if what in ("stop", "restart") and st == "running" and online_names():
                chat_say("Server %s requested from Discord by %s" % ("stop" if what == "stop" else "restart", who[:40]))
                time.sleep(3)
            r = inst.server.action(what)
        finally:
            self.busy.discard(inst.id)
        if not r.get("ok"):
            return "❌ Couldn't %s %s: %s" % (what, label, discord_escape(r.get("msg") or "unknown error"))
        self.app.notifier.add("restart", "Server %s from Discord" % {"start": "started", "stop": "stopped",
                                                                      "restart": "restarted"}[what],
                              "%s used /%s in Discord." % (who[:60], what), "info", send=False)
        if what == "stop":
            return "🔴 %s stopped (by %s)." % (label, discord_escape(who))
        for _ in range(20):
            time.sleep(1.5)
            if inst.server.status()["state"] == "running":
                where = (" - join at `%s`" % fmt_addr(*game_address(inst)[:2])) if relay_on() else ""
                return "🟢 %s is %s (by %s)%s." % (label, "running" if what == "start" else "back up",
                                                   discord_escape(who), where)
        return "🟡 %s is starting (by %s) - it can take a minute. Check with /status." % (label, discord_escape(who))


class App:
    def __init__(self):
        ensure_dirs()
        self.settings = Settings()
        self.secrets = Secrets()
        if self.secrets.has("VT_API_KEY"):
            os.environ["VT_API_KEY"] = self.secrets.get("VT_API_KEY")   # used by modscan
        self.notifier = Notifier(self.settings, self.secrets)
        self.alerts = SecurityAlerts(self.settings, self.notifier)
        self.bot = DiscordBot(self)
        self.sessions = {}
        self.fails = {}
        self.locked = {}
        self.global_fails = []
        self.totp_last = 0
        self.flood_applied = None      # (on, ports) last sent to the root helper
        self.flood_dropped = None
        self.flood_next = 0
        self.flood_lock = threading.Lock()
        self.state = read_json(STATE_FILE, {})
        self.updates = self.state.get("updates", {})
        with open(os.path.join(HERE, "webui.html"), encoding="utf-8") as f:
            self.page = f.read()

    @property
    def server(self):
        return I().server

    def save_state(self):
        with LOCK:
            self.state["updates"] = self.updates
            try:
                write_json(STATE_FILE, self.state)
            except OSError:
                pass

    # ---------- config helpers
    def read_config_text(self):
        try:
            with open_shared(I().CONFIG) as f:
                return f.read(262144)
        except OSError:
            return "[General]\n"

    def write_config_text(self, text):
        text = text if text.endswith("\n") else text + "\n"
        if IS_WIN:
            tmp = I().CONFIG + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="\r\n") as f:
                f.write(text)
            os.replace(tmp, I().CONFIG)
        else:
            # in place: the dashboard user may write the file but not the server folder
            with open_shared(I().CONFIG, "w") as f:
                f.write(text)
        self.config_changed()

    def config_changed(self):
        if IS_WIN:
            with LOCK:
                self.server.restart_needed = self.server.status()["state"] == "running"

    def move_plaintext_authkey(self, text):
        data, _, _ = toml_parse(text)
        ak = data.get("General", {}).get("AuthKey")
        if isinstance(ak, str) and ak.strip():
            key = ak.strip()
            if not re.fullmatch(r"[A-Za-z0-9-]+", key):
                raise ValueError("The AuthKey in the file has unexpected characters")
            I().set_authkey(key)
            text = toml_set(text, "General", "AuthKey", "")
        return text

    def max_players(self):
        data, _, _ = toml_parse(self.read_config_text())
        v = data.get("General", {}).get("MaxPlayers")
        return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else 8

    def switch_map(self, name):
        """Change the map and restart the server if it is running. Returns (ok, note)."""
        if not re.fullmatch(r"[A-Za-z0-9_\-.]{1,80}", name or ""):
            return False, "Pick a valid map"
        if name not in BUILTIN_MAPS and name not in enabled_mod_maps():
            return False, "Map '%s' is not built in and no enabled mod contains it" % name
        self.write_config_text(toml_set(self.read_config_text(), "General", "Map", "/levels/%s/info.json" % name))
        if self.server.status()["state"] in ("running", "starting", "restarting"):
            r = self.server.action("restart")
            if not r.get("ok"):
                return False, r.get("msg") or "Map saved, but the restart failed"
            return True, "Switching to %s - the server is restarting." % name
        return True, "Map set to %s. It's used the next time the server starts." % name

    def applied_note(self):
        if IS_WIN:
            return "Saved. Restart the server to apply." if self.server.status()["state"] == "running" else "Saved."
        return "Saved. The server restarts by itself in about 15 seconds."

    # ---------- background monitor
    def monitor(self):
        """Background loop: watches every server for crashes, blocked mods, joins,
        refused players and map votes, and checks for updates."""
        states = {}
        next_update = now() + 120
        if IS_WIN:                              # extra servers marked "start with the dashboard"
            with LOCK:
                extra = [i for k, i in INSTANCES.items() if k != "main" and i.meta.get("autostart")]
            for inst in extra:
                use_server(inst.id)
                if inst.server.status()["state"] != "running":
                    inst.server._win_start()
        while True:
            time.sleep(10)
            try:
                load_servers()
            except Exception as e:
                sys.stderr.write("servers: %s\n" % short_err(e))
            with LOCK:
                insts = list(INSTANCES.values())
            for k in [k for k in states if k not in {i.id for i in insts}]:
                del states[k]                   # server was deleted
            for inst in insts:
                use_server(inst.id)
                try:
                    if inst.id not in states or states[inst.id]["inst"] is not inst:
                        states[inst.id] = self._monitor_init(inst)   # new (or re-created) server
                    self._monitor_one(inst, states[inst.id])
                except Exception as e:  # never let the monitor die
                    sys.stderr.write("monitor %s: %s\n" % (inst.id, short_err(e)))
            use_server("main")
            try:
                self.alerts.tick()
            except Exception as e:
                sys.stderr.write("security alerts: %s\n" % short_err(e))
            try:
                self.flood_tick()
            except Exception as e:
                sys.stderr.write("flood protection: %s\n" % short_err(e))
            try:
                self.addr_tick()
            except Exception as e:
                sys.stderr.write("address check: %s\n" % short_err(e))
            try:
                if self.settings.get("update_check") and now() >= next_update:
                    next_update = now() + 6 * 3600
                    self.check_updates(notify=True)
            except Exception as e:
                sys.stderr.write("updates: %s\n" % short_err(e))

    def flood_tick(self):
        """Keep the flood rules in place (they're gone after a reboot and must
        follow port changes) and raise an alert when they block a flood."""
        if IS_WIN:
            return
        with self.flood_lock:      # the monitor and a settings change can call this at the same time
            self._flood_tick()

    def _flood_tick(self):
        want = bool(self.settings.get("flood_protect"))
        ports = game_ports() if want else []
        key = (want and bool(ports), tuple(ports))
        if key != self.flood_applied:
            if want or self.flood_applied is not None:
                r = control("flood-protect", state="on" if key[0] else "off", ports=ports, timeout=30)
                if want and not r.get("ok"):
                    self.notifier.add("network", "Flood protection couldn't be turned on", r.get("msg", ""), "warning")
            self.flood_applied = key
            self.flood_dropped = None
            self.flood_next = now() + 60
        if not key[0] or now() < self.flood_next:
            return
        self.flood_next = now() + 60
        st = control("flood-status", timeout=20)
        if not st.get("active"):
            self.flood_applied = None          # rules were removed (another firewall tool?) - put them back
            return
        d = int(st.get("dropped") or 0)
        if self.flood_dropped is not None and d - self.flood_dropped >= 2000:
            self.alerts.raise_("gameflood", "Your game server is being flooded",
                               "Flood protection blocked %d packets in the last minute. Players should still be "
                               "able to play. If your whole internet slows down or drops, it's a bigger attack "
                               "that only a relay can stop: restart your router (most providers then give you "
                               "a new IP address) and turn on Settings → Hide my IP before sharing your server "
                               "again." % (d - self.flood_dropped))
        self.flood_dropped = d

    def _monitor_init(self, inst):
        st = inst.server.status()
        try:
            ev_pos = os.path.getsize(os.path.join(inst.STATS_DIR, "events.log"))
        except OSError:
            ev_pos = 0
        return {"inst": inst, "last": st, "restarts": st.get("restarts", 0), "seen_q": set(n["name"] for n in list_quarantine()),
                "ev_pos": ev_pos, "last_t": now(), "pending_map": None}

    def _check_tampering(self, inst, S):
        """Links where the server's own files should be are a sign that the game
        server (or a Lua plugin) was hacked and is trying to reach other files."""
        if S.get("tamper_t", 0) > now() - 60:
            return
        S["tamper_t"] = now()
        paths = [inst.CONFIG, inst.ALLOW_FILE, inst.VOTE_FILE, os.path.join(inst.STATS_DIR, "events.log"),
                 os.path.join(inst.STATS_DIR, "online.json"), inst.STATS_DIR, inst.CLIENT_DIR, inst.DISABLED_DIR]
        for folder in (inst.CLIENT_DIR, inst.DISABLED_DIR):
            try:
                paths += [os.path.join(folder, n) for n in os.listdir(folder)[:2000]]
            except OSError:
                pass
        found = []
        for p in paths:
            try:
                if os.path.islink(p):
                    found.append("%s -> %s" % (p, os.readlink(p)[:120]))
                elif p == inst.CONFIG and not stat.S_ISREG(os.lstat(p).st_mode):
                    found.append(p + " is not a normal file")
            except OSError:
                continue
        if found:
            self.alerts.raise_("tamper:" + inst.id, "Files of the game server were tampered with",
                               "Links to other files were found where %s keeps its own files:\n%s\n"
                               "The dashboard ignores them, but this usually means the game server or a Lua "
                               "plugin was hacked. Remove unknown plugins from Resources/Server, delete the links "
                               "and check the mods." % (inst.name, "\n".join(found[:10])), sig="\n".join(sorted(found)))

    def _restart_tick(self, inst, S):
        """Scheduled restarts (Config -> Restarts & updates): countdown in the chat,
        optional BeamMP update, or wait until nobody is online."""
        r = restart_cfg(inst)
        if not r["on"]:
            S.pop("rs", None)
            return
        t = now()
        key = json.dumps(r, sort_keys=True)
        rs = S.get("rs")
        if not rs or rs["key"] != key:
            nxt = next_clear(r, t)
            rs = S["rs"] = {"key": key, "at": nxt, "last_left": nxt - t}
        left = rs["at"] - t
        running = inst.server.status()["state"] == "running"
        online = online_names() if running else []
        if r["when"] == "countdown" and online and left > 0:
            warn = r["warn"] * 60
            for p in sorted({1800, 900, 600, 300, 120, 60, 30, 10, warn}, reverse=True):
                if 0 < p <= warn and rs["last_left"] > p >= left:
                    chat_say("Scheduled restart: the server restarts in %s. You can rejoin right after." % fmt_secs(p))
                    break
        rs["last_left"] = left
        if left > 0:
            return
        if r["when"] == "empty" and online:
            if t - rs["at"] < 7200:
                return                              # wait for an empty server (up to 2 hours)
            self.notifier.add("restart", "Scheduled restart skipped",
                              "Players were online for 2 hours after the restart time of %s." % inst.name, "info")
        elif running:
            did = "restarted"
            if self.settings.get("auto_update") and inst.id == "main":
                up = self.check_updates(notify=False)
                if up.get("latest") and up.get("installed") and newer(up["latest"], up["installed"]):
                    if online:
                        chat_say("Updating the server now - rejoin in a minute.")
                    res = inst.server.update()
                    did = ("updated to BeamMP %s and restarted" % up["latest"]) if res.get("ok") else \
                          "couldn't be updated (%s) - restarted instead" % res.get("msg", "error")
                    if res.get("ok"):
                        inst.server.version_cache = (None, None)
                    else:
                        inst.server.action("restart")
                else:
                    inst.server.action("restart")
            else:
                inst.server.action("restart")
            self.notifier.add("restart", "Scheduled restart: %s %s" % (inst.name, did),
                              "Next one: %s." % time.strftime("%a %H:%M", time.localtime(next_clear(r, t + 61))), "info")
        rs["at"] = next_clear(r, t + 61)
        rs["last_left"] = rs["at"] - t

    def addr_tick(self):
        """Warn when this computer's address on the home network or the public
        IP changes - links, bookmarks and port forwards stop working then."""
        if now() < getattr(self, "addr_next", 0):
            return
        self.addr_next = now() + 300
        ips = [i for i in tlsgen.local_ips() if i != "127.0.0.1"]
        old_l, old_p = self.state.get("addr_lan"), self.state.get("addr_pub")
        changed = False
        if ips:
            if old_l and old_l not in ips:
                new = lan_ip()
                self.notifier.add("network", "This computer's home network address changed",
                                  "It was %s, now it's %s. Links and bookmarks with the old address (like the dashboard "
                                  "on your phone) stop working - use %s now.\n"
                                  "To stop this happening: in your router, set a DHCP reservation (also called a static "
                                  "lease) for this computer. Search for \"<your router model> DHCP reservation\". "
                                  "If you forward the game port, point the forward at %s too."
                                  % (old_l, new, dashboard_url(), new), "warning")
            if old_l not in ips:
                self.state["addr_lan"], changed = lan_ip(), True
        pip = public_ip()
        if pip and pip != old_p:
            if old_p and not relay_on():
                self.notifier.add("network", "Your public IP address changed",
                                  "It was %s, now it's %s. Friends who join from outside your home need the new "
                                  "address: %s:%s. Most home internet gets a new IP now and then." %
                                  (old_p, pip, pip, (INSTANCES["main"].port() if "main" in INSTANCES else None) or 30814), "warning")
            self.state["addr_pub"], changed = pip, True
        if changed:
            self.save_state()

    def _monitor_one(self, inst, S):
        self._check_tampering(inst, S)
        try:
            self._restart_tick(inst, S)
        except Exception as e:
            sys.stderr.write("scheduled restart %s: %s\n" % (inst.id, short_err(e)))
        srv = inst.server
        st = srv.status()
        last = S["last"]
        with LOCK:
            expected = srv.expected_stop
        if not IS_WIN:
            if st["restarts"] > S["restarts"]:
                self.notifier.add("crash", "Server crashed",
                                  "The BeamMP server crashed and was restarted automatically. "
                                  "Check the Logs page for the reason.", "error")
            if st["state"] == "failed" and last["state"] != "failed":
                self.notifier.add("crash", "Server crashed and is down",
                                  "The server keeps crashing and was stopped. Check the Logs page.", "error")
            S["restarts"] = st["restarts"]
        if last["state"] == "running" and st["state"] in ("stopped", "failed"):
            if expected:
                with LOCK:
                    srv.expected_stop = False
            elif IS_WIN:
                self.notifier.add("crash", "Server crashed",
                                  "The BeamMP server closed unexpectedly." +
                                  (" Restarting it..." if self.settings.get("auto_restart") else ""), "error")
                if self.settings.get("auto_restart"):
                    srv._win_start()
            elif st["state"] == "stopped":
                self.notifier.add("stopped", "Server stopped",
                                  "The BeamMP server stopped (not from the dashboard).", "warning")
        if st["state"] == "running":
            with LOCK:
                srv.expected_stop = False
        S["last"] = st
        # new quarantined mods
        q = list_quarantine()
        for item in q:
            if item["name"] not in S["seen_q"]:
                self.alerts.raise_("mod:%s:%s" % (inst.id, item["name"]), "A mod failed the virus check: %s" % item["name"],
                                   (item["why"] or "It failed the virus check.") +
                                   "\nIt was moved to quarantine, so players can't download it.")
        S["seen_q"] = set(i["name"] for i in q)
        # events from the EasyServerStats plugin
        path = os.path.join(inst.STATS_DIR, "events.log")
        try:
            size = os.path.getsize(path)
            if size < S["ev_pos"]:
                S["ev_pos"] = 0
            if size > S["ev_pos"]:
                with open_shared(path, "rb") as f:
                    f.seek(S["ev_pos"])
                    raw = f.read(256 * 1024)
                    if len(raw) == 256 * 1024 and b"\n" in raw:
                        raw = raw[:raw.rindex(b"\n") + 1]     # never cut a line in half
                    S["ev_pos"] += len(raw)
                    chunk = raw.decode("utf-8", "replace")
                joined, denied, modmsgs, bots, refused = [], [], [], 0, []
                for line in chunk.splitlines():
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(e, dict) or not isinstance(e.get("t"), int) or e["t"] < S["last_t"]:
                        continue
                    if e.get("ev") == "join":
                        joined.append(clean_player_name(e.get("name")))
                    elif e.get("ev") == "mapvote" and isinstance(e.get("map"), str):
                        S["pending_map"] = (now() + 30, e["map"][:80], clean_player_name(e.get("by")))
                    elif e.get("ev") == "denied":
                        n = clean_player_name(e.get("name"))
                        if not any(d[0] == n for d in denied):
                            denied.append((n, bool(e.get("guest"))))
                    elif e.get("ev") in ("ban", "unban", "kick", "mute"):
                        n, by = clean_player_name(e.get("name")), clean_player_name(e.get("by") or "?")
                        reason = re.sub(r"[\t\r\n]", " ", str(e.get("reason") or ""))[:200]
                        if e["ev"] == "ban" and isinstance(e.get("until"), int):
                            try:
                                ban_player(n, e["until"], reason, "in game: " + by)
                            except OSError:
                                pass
                            modmsgs.append("%s banned %s %s%s" % (by, n, "forever" if not e["until"] else "until " +
                                           time.strftime("%a %H:%M", time.localtime(e["until"])), (" - " + reason) if reason else ""))
                        elif e["ev"] == "unban":
                            try:
                                unban_player(n)
                            except OSError:
                                pass
                            modmsgs.append("%s unbanned %s" % (by, n))
                        elif e["ev"] == "kick":
                            modmsgs.append("%s kicked %s%s" % (by, n, (" - " + reason) if reason else ""))
                        elif isinstance(e.get("minutes"), int):
                            modmsgs.append("%s muted %s for %d min" % (by, n, e["minutes"]))
                    elif e.get("ev") == "botkick":
                        bots += 1
                    elif e.get("ev") == "refused" and e.get("why") in ("banned", "guest", "name", "per_ip"):
                        refused.append("%s (%s)" % (clean_player_name(e.get("name")), {"banned": "banned", "guest": "guest",
                                       "name": "name not allowed", "per_ip": "too many from one IP"}[e["why"]]))
                    elif e.get("ev") == "joinflood":
                        self.alerts.raise_("joinflood:" + inst.id, "Lots of new players are joining %s at once" % inst.name,
                                           "More than %s new players tried to join within a minute - that's usually bots "
                                           "trying to fill the server. Anti-bot paused new joins for 2 minutes; players "
                                           "who joined before can still come in." % e.get("count"))
                    S["last_t"] = max(S["last_t"], e["t"])
                if modmsgs:
                    self.notifier.add("moderation", modmsgs[0] if len(modmsgs) == 1 else "%d moderation actions" % len(modmsgs),
                                      "\n".join(modmsgs[:20]), "info")
                if bots or refused:
                    parts = (["%d player%s kicked for not verifying (anti-bot)" % (bots, "" if bots == 1 else "s")] if bots else []) + \
                            (["Refused: " + ", ".join(refused[:15])] if refused else [])
                    self.notifier.add("moderation", "Anti-bot / bans blocked %d join%s" % (bots + len(refused), "" if bots + len(refused) == 1 else "s"),
                                      "\n".join(parts), "info", send=False)
                if denied:
                    names = [n + (" (guest)" if g else "") for n, g in denied]
                    links = [n for n, g in denied if not g]
                    url = approve_url(inst)
                    msg = "Not on the allow-list: %s." % ", ".join(names[:20])
                    if links and url:
                        msg += "\nApprove: " + " · ".join("[%s](%s)" % (n, url + urllib.parse.quote(n)) for n in links[:10])
                    else:
                        msg += " Add them under Config -> Who can join."
                    self.notifier.add("player_denied",
                                      ("%s was refused" % names[0]) if len(names) == 1 else "%d players were refused" % len(names),
                                      msg, "info")
                if len(joined) == 1:
                    self.notifier.add("player_join", "%s joined" % joined[0], "A player joined your server.", "info")
                elif joined:
                    self.notifier.add("player_join", "%d players joined" % len(joined), ", ".join(joined[:20]), "info")
                if joined:
                    self.join_alert(inst, joined)
        except OSError:
            pass
        # a map vote passed in game: switch ~30 s later (players were told)
        if S["pending_map"] and now() >= S["pending_map"][0]:
            _, mp, by = S["pending_map"]
            S["pending_map"] = None
            on, allowed = read_mapvote()
            if on and mp in allowed:
                ok, note = self.switch_map(mp)
                self.notifier.add("network" if ok else "crash", "Map vote: %s" % mp,
                                  "Players voted for %s (started by %s). %s" % (mp, by or "?", note),
                                  "info" if ok else "error", send=False)

    def join_alert(self, inst, joined):
        """Discord ping to your friends when chosen players join ("Join alerts")."""
        ja = inst.meta.get("join_alerts") or {}
        if not ja.get("enabled") or not self.secrets.has("DISCORD_WEBHOOK"):
            return
        watch = [w.lower() for w in ja.get("players") or []]
        hits = [n for n in joined if not watch or n.lower() in watch]
        if not hits:
            return
        online = analytics_online()
        g = toml_parse(self.read_config_text())[0].get("General", {})
        where = ""
        if ja.get("address"):
            host, gport, _ = game_address(inst)
            where = "\nAddress: `%s`" % fmt_addr(host, gport)
        if not g.get("Private"):
            where += "\nFind **%s** in the BeamMP server list." % inst.name
        who = hits[0] if len(hits) == 1 else ", ".join(hits[:-1]) + " and " + hits[-1]
        text = "%s just joined - %d/%s online on %s (map: %s). Come and play!%s" % (
            who, len(online), g.get("MaxPlayers", "?"), inst.name, map_name(g.get("Map")) or "?", where)
        try:
            self.notifier.send_discord("🎮 %s %s online" % (who, "is" if len(hits) == 1 else "are"), text, "success",
                                       footer=inst.name, content=(ja.get("mention") or "").strip() or None)
        except Exception as e:
            sys.stderr.write("join alert: %s\n" % short_err(e))

    def check_updates(self, notify=False):
        res = {"checked_at": now(), "installed": self.server.installed_version(), "easy_installed": EASY_VERSION}
        try:
            res["latest"] = github_latest(BEAMMP_REPO)
        except Exception as e:
            res["latest"], res["error"] = None, "Couldn't check BeamMP (%s)" % e.__class__.__name__
        try:
            res["easy_latest"] = github_latest(REPO)
        except Exception:
            res["easy_latest"] = None
        with LOCK:
            prev = self.updates
            self.updates = res
        if notify:
            if res.get("latest") and res.get("installed") and newer(res["latest"], res["installed"]) \
                    and prev.get("notified_server") != res["latest"]:
                self.notifier.add("update", "BeamMP server %s is available" % res["latest"],
                                  "You have %s. Open the dashboard → Updates to install it." % res["installed"], "info")
                res["notified_server"] = res["latest"]
            else:
                res["notified_server"] = prev.get("notified_server")
            if res.get("easy_latest") and newer(res["easy_latest"], EASY_VERSION) \
                    and prev.get("notified_easy") != res["easy_latest"]:
                self.notifier.add("update", "BeamMP EasyServer %s is available" % res["easy_latest"],
                                  "You have %s. Download it from github.com/%s" % (EASY_VERSION, REPO), "info")
                res["notified_easy"] = res["easy_latest"]
            else:
                res["notified_easy"] = prev.get("notified_easy")
        self.save_state()
        return res

    # ---------- login protection
    def is_locked(self, ip):
        t = now()
        key = fail_key(ip)
        with LOCK:
            if self.locked.get(key, 0) > t:
                return True
            if ip_is_loopback(ip):
                return False            # someone sitting at the server itself
            if not ip_is_lan(ip):
                self.global_fails = [x for x in self.global_fails if x > t - 600]
                if len(self.global_fails) >= 30:
                    self.alerts.raise_("login-internet", "Password guessing from the internet",
                                       "More than 30 wrong logins from the internet in 10 minutes - logins from the "
                                       "internet are paused. Consider turning internet access off in Settings.")
                    return True
            else:
                # many addresses on the network guessing together (or one device
                # changing its address) - pause logins from the network for a while
                self.lan_fails = [x for x in getattr(self, "lan_fails", []) if x > t - 600]
                if len(self.lan_fails) >= 60:
                    self.alerts.raise_("login-lan", "Password guessing on your network",
                                       "More than 60 wrong logins from devices on your network in 10 minutes - "
                                       "logins are paused for a while. A device on your Wi-Fi may be compromised.")
                    return True
        return False

    def login_failed(self, ip):
        t = now()
        key = fail_key(ip)
        with LOCK:
            if len(self.fails) > 5000:      # don't let random addresses fill the memory
                self.fails = {k: v for k, v in self.fails.items() if v and v[-1] > t - 900}
                self.locked = {k: v for k, v in self.locked.items() if v > t}
            f = [x for x in self.fails.get(key, []) if x > t - 900] + [t]
            self.fails[key] = f
            if not ip_is_lan(ip):
                self.global_fails.append(t)
            elif not ip_is_loopback(ip):
                self.lan_fails = getattr(self, "lan_fails", []) + [t]
            if len(f) >= 5:
                self.locked[key] = t + 900
                self.fails[key] = []
                lock = True
            else:
                lock = False
        if lock:
            where = "from the internet" if not ip_is_lan(ip) else "from your own network"
            self.alerts.raise_("login", "Someone is guessing your dashboard password",
                               "5 wrong passwords in a row %s (address %s). That address is blocked for 15 minutes. "
                               "If this wasn't you, use a long password and turn on two-step login." % (where, ip))

    def verify_totp(self, code):
        secret = self.secrets.get("TOTP_SECRET")
        if not secret:
            return True
        code = re.sub(r"\s", "", code or "")
        if not re.fullmatch(r"\d{6}", code):
            return False
        step = now() // 30
        for c in (step - 1, step, step + 1):
            if hmac.compare_digest(totp_code(secret, c), code):
                with LOCK:
                    if c <= self.totp_last:
                        return False   # code already used
                    self.totp_last = c
                return True
        return False

    def new_session(self, ip):
        tok = secrets.token_urlsafe(32)
        with LOCK:
            t = now()
            self.sessions = {k: v for k, v in self.sessions.items() if v["last"] > t - 7200 and v["created"] > t - 43200}
            self.sessions[tok] = {"created": t, "last": t, "ip": ip, "csrf": secrets.token_urlsafe(24)}
        return tok

    def session(self, tok):
        if not tok:
            return None
        with LOCK:
            s = self.sessions.get(tok)
            t = now()
            if not s or s["last"] < t - 7200 or s["created"] < t - 43200:
                self.sessions.pop(tok, None)
                return None
            s["last"] = t
            return s


APP = None


# ============================================================================= HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "BeamMP-EasyServer"
    sys_version = ""
    timeout = 60
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # only the method and path - never query strings, request bodies or
        # garbled request lines (those could contain a password)
        line = getattr(self, "requestline", "") or ""
        parts = line.split(" ")
        if len(parts) == 3 and parts[0] in ("GET", "POST", "PUT", "HEAD") and parts[1].startswith("/"):
            what = "%s %s" % (parts[0], parts[1].split("?")[0][:120])
        else:
            what = "(malformed request)"
        code = args[1] if fmt.startswith('"%s" %s') and len(args) > 1 else ""
        sys.stderr.write("%s %s %s\n" % (self.client_address[0], what, code))

    def log_error(self, fmt, *args):
        sys.stderr.write("%s request error (details not logged)\n" % self.client_address[0])

    def send_error(self, code, message=None, explain=None):
        # the standard error page repeats the request line, which can contain
        # leftover data - answer with a plain message instead
        self.close_connection = True
        try:
            self.send_response(code)
            data = ("Error %d\n" % code).encode()
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            if self.command != "HEAD" and code >= 200 and code not in (204, 304):
                self.wfile.write(data)
        except OSError:
            pass

    # ---------- plumbing
    @property
    def ip(self):
        return self.client_address[0]

    @property
    def https(self):
        return isinstance(self.connection, ssl.SSLSocket)

    def headers_common(self, ctype, length, extra=None):
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        if self.https:
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def send(self, code, obj=None, ctype="application/json", extra=None):
        # An answer sent before the request body was read (a refusal, an error)
        # must close the connection: otherwise the unread body (which may hold
        # a password) would be taken as the start of the next request.
        try:
            pending = int(self.headers.get("Content-Length") or 0) > 0 and not getattr(self, "_body_done", False)
        except ValueError:
            pending = True
        if pending or self.headers.get("Transfer-Encoding"):
            self.close_connection = True
            extra = dict(extra or {}, Connection="close")
        if isinstance(obj, (bytes, bytearray)):
            data = bytes(obj)
        elif ctype == "application/json":
            data = json.dumps(obj if obj is not None else {}).encode()
        else:
            data = str(obj).encode()
        self.send_response(code)
        self.headers_common(ctype + ("; charset=utf-8" if not ctype.startswith(("application/zip", "application/octet")) else ""),
                            len(data), extra)
        if self.command != "HEAD":
            self.wfile.write(data)

    def fail(self, code, msg, **extra):
        self.send(code, dict({"ok": False, "error": msg}, **extra))

    def content_length(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError("bad Content-Length")
        if n < 0:
            raise ValueError("bad Content-Length")
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("chunked uploads are not supported")
        return n

    def body_json(self, limit=1024 * 1024):
        n = self.content_length()
        if n > limit:
            raise ValueError("request too large")
        raw = self.rfile.read(n) if n else b"{}"
        self._body_done = True
        try:
            v = json.loads(raw or b"{}")
            return v if isinstance(v, dict) else {}
        except ValueError:
            raise ValueError("bad JSON")

    def body_to_file(self, path, limit):
        n = self.content_length()
        if n <= 0:
            raise ValueError("empty upload")
        if n > limit:
            raise ValueError("file too large")
        left = n
        with open(path, "wb") as f:
            while left > 0:
                chunk = self.rfile.read(min(1 << 20, left))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        if left:
            os.remove(path)
            raise ValueError("upload interrupted")
        self._body_done = True

    def cookie(self, name):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == name:
                return v
        return None

    def route(self):
        u = urllib.parse.urlparse(self.path)
        return u.path.rstrip("/") or "/", {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}

    # ---------- gatekeeping
    def gate(self):
        """Network-level access rules. Returns True if the request may continue."""
        app = APP
        if not ip_is_lan(self.ip):
            if not (app.settings.get("remote_enabled") and self.https and app.secrets.has("TOTP_SECRET")):
                self.send(403, "Remote access to this dashboard is turned off.", "text/plain")
                return False
        # DNS rebinding: a web page on some other site could point its own name
        # at this computer and talk to the dashboard through a friend's browser.
        # Only addresses and local names are accepted (any name once internet
        # access is set up, because then you use your own domain).
        host = host_name(self.headers.get("Host"))
        if not host or not (host_is_local_name(host) or app.settings.get("remote_enabled")):
            app.alerts.seen("rebind", 3, 600, "A website tried to reach your dashboard",
                            "Requests for the dashboard arrived under a foreign web address (%s) from %s. This is how "
                            "malicious websites try to reach devices on your home network (\"DNS rebinding\"). "
                            "They were blocked." % (re.sub(r"[^\w.:\-\[\]]", "?", host)[:80] or "none", self.ip))
            self.send(421, "Open the dashboard by its address (for example http://192.168.1.20:30815).", "text/plain")
            return False
        if not app.secrets.has("MODS_PASSWORD") and not ip_is_loopback(self.ip):
            path, _ = self.route()
            if path.startswith("/api/") and path not in ("/api/session",):
                self.send(403, {"ok": False, "error": "Set a password first - open the dashboard on the server computer itself."})
                return False
        return True

    def csrf_ok(self, sess):
        if not hmac.compare_digest((self.headers.get("X-ES-CSRF") or "").encode(), sess["csrf"].encode()):
            return False
        origin = self.headers.get("Origin")
        if origin:
            host = self.headers.get("Host", "")
            if urllib.parse.urlparse(origin).netloc != host:
                return False
        return True

    def authed(self, mutating):
        sess = APP.session(self.cookie("es_session"))
        if not sess:
            self.fail(401, "Please log in")
            return None
        if mutating and not self.csrf_ok(sess):
            self.fail(403, "Security check failed - reload the page")
            return None
        return sess

    # ---------- HTTP verbs
    def do_GET(self):
        self.dispatch("GET")

    def do_HEAD(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_PUT(self):
        self.dispatch("PUT")

    def dispatch(self, method):
        self._body_done = False
        try:
            if not self.gate():
                return
            path, q = self.route()
            if method == "GET" and path == "/":
                return self.page()
            public = {("GET", "/api/session"), ("POST", "/api/login"), ("POST", "/api/setup")}
            if (method, path) in public:
                return getattr(self, "api_" + path[5:].replace("/", "_"))(q)
            if not path.startswith("/api/"):
                return self.fail(404, "not found")
            sess = self.authed(method != "GET")
            if not sess:
                return
            fn = getattr(self, "%s_%s" % (method.lower(), path[5:].replace("/", "_").replace("-", "_")), None)
            if not fn:
                return self.fail(404, "not found")
            self.sess = sess
            want = self.headers.get("X-ES-Server") or q.get("srv") or "main"
            with LOCK:
                known = want in INSTANCES
            if not known:
                return self.fail(404, "That server doesn't exist (any more)")
            use_server(want)
            fn(q)
        except ValueError as e:
            self.fail(400, str(e))
        except (TypeError, AttributeError, KeyError):
            # a field had the wrong type (a list where text belongs ...): the
            # request is broken, not the dashboard
            self.fail(400, "Bad request")
        except RuntimeError as e:
            self.fail(500, str(e))
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
            pass
        except Exception as e:
            sys.stderr.write("error: %s\n" % short_err(e))
            try:
                self.fail(500, "Something went wrong: %s" % e.__class__.__name__)
            except Exception:
                pass
        finally:
            _TL.inst = None

    def page(self):
        nonce = secrets.token_urlsafe(16)
        html_ = APP.page.replace("__NONCE__", nonce).replace("__VERSION__", EASY_VERSION)
        csp = ("default-src 'none'; script-src 'nonce-%s'; style-src 'unsafe-inline'; img-src 'self' data:; "
               "connect-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'") % nonce
        self.send(200, html_.encode(), "text/html", {"Content-Security-Policy": csp})

    # ---------- public endpoints
    def api_session(self, q):
        app = APP
        sess = app.session(self.cookie("es_session"))
        self.send(200, {
            "logged_in": bool(sess), "csrf": sess["csrf"] if sess else None,
            "needs_setup": not app.secrets.has("MODS_PASSWORD"),
            "setup_allowed": ip_is_loopback(self.ip) and host_name(self.headers.get("Host")) in ("localhost", "127.0.0.1", "::1"),
            "totp": app.secrets.has("TOTP_SECRET"),
            "version": EASY_VERSION, "platform": "windows" if IS_WIN else "linux",
            "https": self.https,
        })

    def api_setup(self, q):
        app = APP
        if app.secrets.has("MODS_PASSWORD") or not ip_is_loopback(self.ip):
            return self.fail(403, "Setup is only possible once, on the server computer itself")
        host = host_name(self.headers.get("Host"))
        origin = self.headers.get("Origin")
        if host not in ("localhost", "127.0.0.1", "::1") or (
                origin and host_name(urllib.parse.urlparse(origin).netloc) != host):
            return self.fail(403, "Open http://localhost:%s on this computer to set the password" % (
                self.server.server_address[1]))
        b = self.body_json(4096)
        pw = str(b.get("password", ""))
        if len(pw) < 8:
            return self.fail(400, "Use at least 8 characters")
        app.secrets.set("MODS_PASSWORD", pw)
        tok = app.new_session(self.ip)
        self.send(200, {"ok": True}, extra={"Set-Cookie": self.cookie_header(tok)})

    def cookie_header(self, tok, clear=False):
        c = "es_session=%s; Path=/; HttpOnly; SameSite=Strict" % ("" if clear else tok)
        if self.https:
            c += "; Secure"
        if clear:
            c += "; Max-Age=0"
        return c

    def api_login(self, q):
        app = APP
        if app.is_locked(self.ip):
            return self.fail(429, "Too many wrong attempts. Try again in 15 minutes.")
        b = self.body_json(4096)
        pw = str(b.get("password", ""))
        good = app.secrets.get("MODS_PASSWORD")
        ok_pw = bool(good) and hmac.compare_digest(pw.encode(), good.encode())
        has_totp = app.secrets.has("TOTP_SECRET")
        # the code is only checked (and used up) when the password is right, but
        # the answer is the same either way - so it never tells a guesser that
        # the password part was correct
        ok_code = (not has_totp) or (ok_pw and app.verify_totp(str(b.get("code", ""))))
        if not (ok_pw and ok_code):
            time.sleep(0.7)
            app.login_failed(self.ip)
            return self.fail(401, "Wrong password or two-step code" if has_totp else "Wrong password",
                             need_code=has_totp)
        tok = app.new_session(self.ip)
        self.send(200, {"ok": True}, extra={"Set-Cookie": self.cookie_header(tok)})

    def post_logout(self, q):
        with LOCK:
            APP.sessions.pop(self.cookie("es_session"), None)
        self.send(200, {"ok": True}, extra={"Set-Cookie": self.cookie_header("", clear=True)})

    # ---------- overview
    # ---------- several servers
    def get_servers(self, q):
        with LOCK:
            insts = list(INSTANCES.values())
        out = []
        for inst in insts:
            use_server(inst.id)
            g = toml_parse(APP.read_config_text())[0].get("General", {})
            out.append({"id": inst.id, "name": inst.name, "port": g.get("Port"), "map": map_name(g.get("Map")),
                        "max_players": g.get("MaxPlayers"), "status": inst.server.status(),
                        "online": len(analytics_online()), "usage": inst.server.usage(),
                        "limits": inst.meta.get("limits") or {}, "autostart": bool(inst.meta.get("autostart", True)),
                        "has_authkey": inst.has_authkey()})
        self.send(200, {"servers": out, "system": system_info(), "platform": "windows" if IS_WIN else "linux"})

    def post_servers_create(self, q):
        b = self.body_json()
        name = re.sub(r"\s+", " ", str(b.get("name", "")).strip())[:60]
        if not name:
            return self.fail(400, "Give the new server a name")
        with LOCK:
            used = set(INSTANCES)
            ports = {i.port() for i in INSTANCES.values()}
        if len(used) >= 20:
            return self.fail(400, "That's a lot of servers - 20 is the limit")
        n = 2
        while "s%d" % n in used or os.path.exists(os.path.join(SERVERS_DIR, "s%d" % n)):
            n += 1
        iid = "s%d" % n
        try:
            port = int(b.get("port") or 0)
            maxp = int(b.get("max_players") or 8)
        except (TypeError, ValueError):
            return self.fail(400, "Port and max players must be numbers")
        if not 1024 <= port <= 65535:
            return self.fail(400, "Pick a port between 1024 and 65535")
        if port in ports or port == APP.settings.get("port"):
            return self.fail(400, "Port %d is already used - every server needs its own port" % port)
        if not 1 <= maxp <= 100:
            return self.fail(400, "Max players must be between 1 and 100")
        mp = str(b.get("map") or "gridmap_v2")
        if mp not in BUILTIN_MAPS:
            return self.fail(400, "Pick a built-in map (map mods can be added after the server is created)")
        use_server("main")
        text = APP.read_config_text()
        for k, v in (("Name", name), ("Port", port), ("MaxPlayers", maxp), ("Map", "/levels/%s/info.json" % mp),
                     ("AuthKey", ""), ("Description", str(b.get("description") or "")[:300]),
                     ("Private", bool(b.get("private", False)))):
            text = toml_set(text, "General", k, v)
        start = bool(b.get("start", True))
        if IS_WIN:
            d = os.path.join(SERVERS_DIR, iid)
            for sub in ("Resources/Client", "Resources/Client-disabled", "Resources/Quarantine",
                        "Resources/Server/EasyServerStats"):
                os.makedirs(os.path.join(d, sub), exist_ok=True)
            with open(os.path.join(d, "ServerConfig.toml"), "w", encoding="utf-8", newline="\r\n") as f:
                f.write(text)
            src = os.path.join(SERVER_DIR, "Resources", "Server", "EasyServerStats", "main.lua")
            if os.path.isfile(src):
                shutil.copyfile(src, os.path.join(d, "Resources", "Server", "EasyServerStats", "main.lua"))
            note = "Server created."
        else:
            r = control("create-server", server=iid, config=text, start=start, timeout=120)
            if not r.get("ok") and not os.path.isdir(os.path.join(SERVERS_DIR, iid)):
                return self.fail(500, r.get("msg") or "Could not create the server")
            note = "Server created. " + (r.get("msg") or "").replace("created. ", "").replace("created, but", "But")
        with LOCK:
            INSTANCES[iid] = Instance(iid, {"name": name, "autostart": True})
        save_servers()
        if IS_WIN and start:
            use_server(iid)
            INSTANCES[iid].server._win_start()
        key = str(b.get("authkey") or "").strip()
        if key:
            if not re.fullmatch(r"[A-Za-z0-9-]{8,80}", key):
                return self.send(200, {"ok": True, "id": iid, "note": note + " The AuthKey looked wrong, so it wasn't saved."})
            use_server(iid)
            INSTANCES[iid].set_authkey(key)
            if start:
                INSTANCES[iid].server.action("restart")
        self.send(200, {"ok": True, "id": iid, "note": note.strip() + " Remember to forward port %d (TCP + UDP) on your router for internet play." % port})

    def post_servers_delete(self, q):
        b = self.body_json()
        iid = str(b.get("id", ""))
        with LOCK:
            inst = INSTANCES.get(iid)
        if not inst or iid == "main":
            return self.fail(400, "This server can't be deleted here")
        if str(b.get("confirm", "")).strip().lower() != inst.name.strip().lower():
            return self.fail(400, "Type the server's name to confirm")
        use_server(iid)
        if IS_WIN:
            inst.server.action("stop")
            if (inst.meta.get("limits") or {}).get("upload_kbps"):
                inst.meta["limits"]["upload_kbps"] = 0
                win_upload_limit(inst)
            try:
                APP.secrets.set(inst.authkey_name, "")
            except Exception:
                pass
            shutil.rmtree(inst.SERVER_DIR, ignore_errors=True)
        else:
            r = control("delete-server", server=iid, timeout=180)
            if not r.get("ok"):
                return self.fail(500, r.get("msg") or "Could not delete the server")
        with LOCK:
            INSTANCES.pop(iid, None)
        save_servers()
        self.send(200, {"ok": True, "note": "%s was deleted." % inst.name})

    def post_servers_limits(self, q):
        b = self.body_json()
        iid = str(b.get("id", ""))
        with LOCK:
            inst = INSTANCES.get(iid)
        if not inst:
            return self.fail(404, "No such server")
        try:
            cpu = round(float(b.get("cpu_cores") or 0), 2)
            ram = int(b.get("ram_mb") or 0)
            up = int(b.get("upload_kbps") or 0)
        except (TypeError, ValueError):
            return self.fail(400, "Limits must be numbers")
        cores = os.cpu_count() or 1
        if not 0 <= cpu <= cores:
            return self.fail(400, "CPU limit must be between 0 (no limit) and %d cores" % cores)
        if ram and ram < 256:
            return self.fail(400, "Give the server at least 256 MB of RAM (or 0 for no limit)")
        if up and up < 256:
            return self.fail(400, "Set at least 256 kbit/s for mod downloads (or 0 for no limit)")
        old_up = int((inst.meta.get("limits") or {}).get("upload_kbps") or 0)
        set_server_meta(iid, limits={"cpu_cores": cpu, "ram_mb": ram, "upload_kbps": up})
        use_server(iid)
        if IS_WIN:
            notes = []
            if inst.server.status()["state"] == "running":
                notes.append("CPU/RAM: " + win_apply_limits(inst) + ("" if cpu or ram else " (takes effect after a restart)"))
            if up != old_up:
                notes.append(win_upload_limit(inst))
            msg = " ".join(notes) or "Saved - used the next time the server starts."
        else:
            r = control("set-limits", server=iid, cpu_cores=cpu, ram_mb=ram, upload_kbps=up, timeout=90)
            if not r.get("ok"):
                return self.fail(500, r.get("msg") or "Could not apply the limits")
            msg = "Applied right away. " + (r.get("msg") or "")
        self.send(200, {"ok": True, "note": msg.strip()})

    def post_servers_settings(self, q):
        b = self.body_json()
        iid = str(b.get("id", ""))
        with LOCK:
            inst = INSTANCES.get(iid)
        if not inst:
            return self.fail(404, "No such server")
        kw = {}
        if "name" in b:
            kw["name"] = re.sub(r"\s+", " ", str(b["name"]).strip())[:60] or None
        if "autostart" in b:
            kw["autostart"] = bool(b["autostart"])
        set_server_meta(iid, **kw)
        self.send(200, {"ok": True})

    def get_joinalerts(self, q):
        ja = I().meta.get("join_alerts") or {}
        self.send(200, {"enabled": bool(ja.get("enabled")), "players": ja.get("players") or [],
                        "mention": ja.get("mention") or "", "address": bool(ja.get("address")),
                        "discord": APP.secrets.has("DISCORD_WEBHOOK")})

    def post_joinalerts(self, q):
        b = self.body_json()
        players = clean_allow_names(b.get("players", []))
        mention = str(b.get("mention") or "").strip()[:300]
        if mention and not re.fullmatch(r"(?:\s*(?:<@[!&]?\d{5,25}>|@everyone|@here)\s*)+", mention):
            return self.fail(400, "Mentions must look like <@123456789> (a person), <@&123456789> (a role), @here or @everyone")
        on = bool(b.get("enabled"))
        if on and not APP.secrets.has("DISCORD_WEBHOOK"):
            return self.fail(400, "Add your Discord webhook in Settings -> Notifications first")
        set_server_meta(I().id, join_alerts={"enabled": on, "players": players, "mention": mention,
                                            "address": bool(b.get("address"))})
        if b.get("test"):
            try:
                APP.notifier.send_discord("🎮 Test: someone just joined", "This is how join alerts look for %s." % I().name,
                                          "success", footer=I().name, content=mention or None)
            except Exception as e:
                return self.fail(500, "Saved, but the test message failed: %s" % short_err(e))
            return self.send(200, {"ok": True, "note": "Saved and test message sent to Discord."})
        self.send(200, {"ok": True, "note": "Saved."})

    def get_overview(self, q):
        app = APP
        st = app.server.status()
        text = app.read_config_text()
        data, issues = validate_config(text, app.settings.get("port"), I().has_authkey())
        g = data.get("General", {})
        online = analytics_online()
        up = app.updates
        self.send(200, {
            "status": st, "name": re.sub(r"\^.", "", str(g.get("Name", ""))),
            "map": map_name(g.get("Map")), "port": g.get("Port"), "max_players": g.get("MaxPlayers"),
            "private": g.get("Private"), "online": online, "lan_ip": lan_ip(),
            "relay": fmt_addr(*game_address()[:2]) if relay_on() else None,
            "reviewed": bool(I().meta.get("reviewed")),
            "config_errors": sum(1 for i in issues if i["level"] == "error"),
            "config_warnings": sum(1 for i in issues if i["level"] == "warning"),
            "has_authkey": I().has_authkey(),
            "mods": sum(1 for m in list_mods() if m["enabled"]), "quarantined": len(list_quarantine()),
            "update_available": bool(up.get("latest") and up.get("installed") and newer(up["latest"], up["installed"])),
            "unread": sum(1 for n in app.notifier.items if not n["read"]),
            "restart_needed": app.server.restart_needed, "platform": "windows" if IS_WIN else "linux",
            "installed_version": up.get("installed") or app.server.installed_version(),
            "maps": {"builtin": BUILTIN_MAPS, "mods": enabled_mod_maps()},
        })

    def post_map(self, q):
        """Quick map switch from the Overview page: change the map and restart right away."""
        app = APP
        ok, note = app.switch_map(str(self.body_json().get("map", "")).strip())
        if not ok:
            return self.fail(400, note)
        self.send(200, {"ok": True, "note": note})

    def get_mapvote(self, q):
        on, maps = read_mapvote()
        self.send(200, {"enabled": on, "maps": maps, "available": BUILTIN_MAPS + [m for m in enabled_mod_maps() if m not in BUILTIN_MAPS]})

    def post_mapvote(self, q):
        b = self.body_json()
        avail = set(BUILTIN_MAPS) | set(enabled_mod_maps())
        maps = []
        raw = b.get("maps")
        for m in (raw if isinstance(raw, list) else [])[:100]:
            m = str(m).strip()
            if m in avail and m not in maps:
                maps.append(m)
        on = bool(b.get("enabled"))
        if on and len(maps) < 2:
            return self.fail(400, "Pick at least two maps to vote between")
        write_mapvote(on, maps)
        self.send(200, {"ok": True, "note": "Saved - players can type /vote in chat right away." if on else "Saved - map voting is off."})

    def get_extras(self, q):
        d = read_extras()
        d.update({"next_clear": next_clear(d) if d["clear"] else None, "every_choices": list(CLEAR_EVERY),
                  "warn_choices": list(WARN_CHOICES), "file": os.path.exists(I().EXTRAS_FILE),
                  "plugin": os.path.exists(os.path.join(I().STATS_DIR, "main.lua"))})
        self.send(200, d)

    def post_extras(self, q):
        b = self.body_json()
        d = read_extras()
        for k in ("clear", "afk", "countdown", "tag", "top"):
            if k in b:
                d[k] = bool(b[k])
        if "every" in b:
            if int(b["every"]) not in CLEAR_EVERY:
                return self.fail(400, "Pick how often from the list")
            d["every"] = int(b["every"])
        if "at" in b:
            at = str(b["at"]).strip()
            if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", at):
                return self.fail(400, "Enter the time like 04:00")
            d["at"] = "%02d:%s" % (int(at.split(":")[0]), at.split(":")[1])
        if "warn" in b:
            if int(b["warn"]) not in WARN_CHOICES:
                return self.fail(400, "Pick the countdown length from the list")
            d["warn"] = int(b["warn"])
        if d["warn"] * 60 >= d["every"] * 3600:
            return self.fail(400, "The countdown must be shorter than the time between cleanups")
        if "afk_minutes" in b:
            n = int(b["afk_minutes"])
            if not 2 <= n <= 120:
                return self.fail(400, "Abandoned cars: use 2 to 120 minutes")
            d["afk_minutes"] = n
        if "tags" in b:
            if not isinstance(b["tags"], list):
                return self.fail(400, "bad tags")
            t = clean_tags(b["tags"])
            if d["tag"] and not t:
                return self.fail(400, "Add at least one tag")
            d["tags"] = t or EXTRAS_DEFAULTS["tags"]
        write_extras(d)
        nxt = next_clear(d) if d["clear"] else None
        self.send(200, {"ok": True, "next_clear": nxt,
                        "note": "Saved - works right away, no restart needed." +
                                (" Next car cleanup: %s." % time.strftime("%a %H:%M", time.localtime(nxt)) if nxt else "")})

    def get_moderation(self, q):
        d = read_mod()
        d["verified"] = len([l for l in shared_read(I().VERIFIED_FILE).splitlines() if l.strip()])
        self.send(200, d)

    def post_moderation(self, q):
        b = self.body_json()
        d = read_mod()
        for k in ("filter", "spam", "antibot", "verify", "guests"):
            if k in b:
                d[k] = bool(b[k])
        for k in ("admins", "words"):
            if k in b:
                if not isinstance(b[k], list):
                    return self.fail(400, "bad list")
                items = []
                for x in b[k][:500]:
                    x = re.sub(r"[\t\r\n,]", "", str(x)).strip()[:64]
                    if k == "words":
                        x = x.lower()
                    if x and x not in items:
                        items.append(x)
                d[k] = items
        for k, lo, hi in (("spam_limit", 2, 30), ("per_ip", 0, 20), ("join_flood", 0, 100)):
            if k in b:
                v = int(b[k])
                if not lo <= v <= hi:
                    return self.fail(400, "%s must be between %d and %d" % (k.replace("_", " "), lo, hi))
                d[k] = v
        write_mod(d)
        self.send(200, {"ok": True, "note": "Saved - works right away, no restart needed."})

    def get_bans(self, q):
        self.send(200, {"bans": read_bans(), "online": online_names()})

    def post_bans_add(self, q):
        b = self.body_json()
        name = clean_name(b.get("name"))
        minutes = int(b.get("minutes") or 0)
        if minutes < 0 or minutes > 10 * 365 * 1440:
            return self.fail(400, "bad duration")
        reason = re.sub(r"[\t\r\n]", " ", str(b.get("reason") or ""))[:200]
        until = now() + minutes * 60 if minutes else 0
        ban_player(name, until, reason, "dashboard")
        queue_action("ban", name, "", "Banned" + ((": " + reason) if reason else ""))
        self.send(200, {"ok": True, "note": "%s is banned%s." % (name, "" if minutes else " forever")})

    def post_bans_remove(self, q):
        name = clean_name(self.body_json().get("name"))
        name = unban_player(name) or name
        queue_action("unban", name)
        self.send(200, {"ok": True, "note": "%s can join again." % name})

    def post_players_act(self, q):
        b = self.body_json()
        act = b.get("action")
        name = clean_name(b.get("name"))
        if act == "kick":
            queue_action("kick", name, "", "Kicked by an admin" + ((": " + str(b.get("reason"))[:150]) if b.get("reason") else ""))
            note = "%s will be kicked in a second." % name
        elif act == "mute":
            mins = int(b.get("minutes") or 10)
            if not 1 <= mins <= 1440:
                return self.fail(400, "Mute for 1 to 1440 minutes")
            queue_action("mute", name, str(mins))
            note = "%s is muted for %d minutes." % (name, mins)
        elif act == "unmute":
            queue_action("unmute", name)
            note = "%s can chat again." % name
        elif act == "say":
            text = re.sub(r"[\r\n\t]", " ", str(b.get("text") or "")).strip()[:300]
            if not text:
                return self.fail(400, "Type a message")
            chat_say(text)
            note = "Sent to the chat."
        else:
            return self.fail(400, "bad action")
        self.send(200, {"ok": True, "note": note})

    def get_restarts(self, q):
        r = restart_cfg(I())
        up = APP.updates
        self.send(200, dict(r, next=next_clear(r) if r["on"] else None, auto_update=bool(APP.settings.get("auto_update")),
                            update_available=bool(up.get("latest") and up.get("installed") and newer(up["latest"], up["installed"])),
                            every_choices=list(CLEAR_EVERY), warn_choices=[0, 1, 2, 5, 10, 15, 30]))

    def post_restarts(self, q):
        b = self.body_json()
        r = restart_cfg(I())
        if "on" in b:
            r["on"] = bool(b["on"])
        if "every" in b:
            if int(b["every"]) not in CLEAR_EVERY:
                return self.fail(400, "Pick how often from the list")
            r["every"] = int(b["every"])
        if "at" in b:
            at = str(b["at"]).strip()
            if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", at):
                return self.fail(400, "Enter the time like 05:00")
            r["at"] = "%02d:%s" % (int(at.split(":")[0]), at.split(":")[1])
        if "warn" in b:
            if int(b["warn"]) not in (0, 1, 2, 5, 10, 15, 30):
                return self.fail(400, "Pick the countdown length from the list")
            r["warn"] = int(b["warn"])
        if "when" in b:
            if b["when"] not in ("countdown", "empty"):
                return self.fail(400, "bad option")
            r["when"] = b["when"]
        if r["warn"] * 60 >= r["every"] * 3600:
            return self.fail(400, "The countdown must be shorter than the time between restarts")
        set_server_meta(I().id, restart=r)
        if "auto_update" in b:
            APP.settings.update({"auto_update": bool(b["auto_update"])})
        self.send(200, {"ok": True, "next": next_clear(r) if r["on"] else None,
                        "note": "Saved." + (" Next restart: %s." % time.strftime("%a %H:%M", time.localtime(next_clear(r))) if r["on"] else "")})

    def post_mods_desc(self, q):
        on = bool(self.body_json().get("enabled"))
        set_server_meta(I().id, desc_modsize=True if on else None)
        changed = refresh_mod_desc()
        self.send(200, {"ok": True, "note": ("The download size is now at the end of the server description. " if on else
                                             "Removed the download size from the description. ") +
                                            (APP.applied_note() if changed else "")})

    def get_review(self, q):
        """Everything worth a look before a server goes live for the first time."""
        app = APP
        g = toml_parse(app.read_config_text())[0].get("General", {})
        ex, md, rs = read_extras(), read_mod(), restart_cfg(I())
        al_on, _ = read_allowlist()
        self.send(200, {
            "reviewed": bool(I().meta.get("reviewed")), "server": I().name,
            "game": {"name": g.get("Name"), "map": map_name(g.get("Map")), "max_players": g.get("MaxPlayers"),
                     "max_cars": g.get("MaxCars"), "private": bool(g.get("Private")), "port": g.get("Port"),
                     "description": g.get("Description"), "authkey": I().has_authkey(), "allowlist": bool(al_on)},
            "security": {"totp": app.secrets.has("TOTP_SECRET"), "remote": bool(app.settings.get("remote_enabled")),
                         "https": bool(app.settings.get("https")), "alerts": bool(app.settings.get("security_alerts")),
                         "discord": bool(app.settings.get("discord_enabled"))},
            "protection": {"antibot": md["antibot"], "filter": md["filter"], "admins": md["admins"],
                           "relay": relay_on(), "flood": bool(app.settings.get("flood_protect"))},
            "cars": {"clear": ex["clear"], "every": ex["every"], "at": ex["at"], "afk": ex["afk"]},
            "restarts": {"on": rs["on"], "every": rs["every"], "at": rs["at"]},
        })

    def post_review_ok(self, q):
        set_server_meta(I().id, reviewed=True)
        self.send(200, {"ok": True})

    def post_server_action(self, q):
        what = self.body_json().get("action")
        if what == "start" and not I().meta.get("reviewed"):
            return self.fail(409, "Look over the settings first - open the dashboard and press Start again.")
        r = APP.server.action(what)
        if r.get("ok"):
            self.send(200, {"ok": True})
        else:
            self.fail(500, r.get("msg") or "failed")

    # ---------- config
    def get_config(self, q):
        app = APP
        text = app.read_config_text()
        data, issues = validate_config(text, app.settings.get("port"), I().has_authkey())
        fields = []
        for sec, key, typ, label, help_, opt in CONFIG_SCHEMA:
            v = data.get(sec, {}).get(key)
            if typ == "map":
                v = map_name(v)
            fields.append({"section": sec, "key": key, "type": typ, "label": label, "help": help_,
                           "value": v, "min": opt.get("min"), "max": opt.get("max"),
                           "advanced": bool(opt.get("advanced"))})
        self.send(200, {"fields": fields, "raw": text, "issues": issues,
                        "has_authkey": I().has_authkey(),
                        "maps": {"builtin": BUILTIN_MAPS, "mods": enabled_mod_maps()}})

    def post_config_validate(self, q):
        text = str(self.body_json().get("raw", ""))
        _, issues = validate_config(text, APP.settings.get("port"), I().has_authkey())
        self.send(200, {"issues": issues})

    def post_config_save(self, q):
        app = APP
        b = self.body_json()
        if "raw" in b:
            text = str(b["raw"])
        else:
            text = app.read_config_text()
            schema = {(s, k): (t, o) for s, k, t, _l, _h, o in CONFIG_SCHEMA}
            for item in b.get("fields", []):
                sk = (item.get("section"), item.get("key"))
                if sk not in schema:
                    continue
                typ, _o = schema[sk]
                v = item.get("value")
                if typ == "int":
                    try:
                        v = int(v)
                    except (TypeError, ValueError):
                        return self.fail(400, "%s must be a whole number" % sk[1])
                elif typ == "bool":
                    v = bool(v)
                elif typ == "map":
                    name = str(v or "").strip()
                    if not re.fullmatch(r"[A-Za-z0-9_\-.]+", name):
                        return self.fail(400, "Pick a valid map")
                    v = "/levels/%s/info.json" % name
                else:
                    v = str(v if v is not None else "")
                text = toml_set(text, sk[0], sk[1], v)
        if len(text) > 200000:
            return self.fail(400, "Config is too large")
        _, issues = validate_config(text, app.settings.get("port"), I().has_authkey())
        errors = [i for i in issues if i["level"] == "error"]
        if errors:
            return self.send(400, {"ok": False, "error": "Fix the errors first", "issues": issues})
        old_port = (toml_parse(app.read_config_text())[0].get("General") or {}).get("Port")
        text = app.move_plaintext_authkey(text)
        app.write_config_text(text)
        data, issues = validate_config(text, app.settings.get("port"), I().has_authkey())
        new_port = (toml_parse(text)[0].get("General") or {}).get("Port")
        network = ""
        if isinstance(new_port, int) and new_port != old_port:
            if IS_WIN:
                network = "Windows firewall: the BeamMP server program is already allowed on any port."
            else:
                network = control("firewall-game", old=old_port if isinstance(old_port, int) else None,
                                  new=new_port, timeout=30).get("msg", "")
            network = (network.rstrip(". ") + ". " if network else "") + \
                "Remember to forward port %d (TCP + UDP) on your router instead of %s." % (new_port, old_port)
            app.notifier.add("network", "Server port changed", "Port %s -> %d. %s" % (old_port, new_port, network.strip()))
        self.send(200, {"ok": True, "issues": issues, "note": app.applied_note(), "network": network.strip()})

    def get_allowlist(self, q):
        on, names = read_allowlist()
        self.send(200, {"enabled": on, "names": names, "denied": recent_denied(),
                        "plugin": os.path.exists(os.path.join(I().STATS_DIR, "main.lua"))})

    def post_allowlist(self, q):
        b = self.body_json()
        names = clean_allow_names(b.get("names", []))
        on = bool(b.get("enabled"))
        if on and not names:
            return self.fail(400, "Add at least one player name before turning the list on")
        was_on, _ = read_allowlist()
        write_allowlist(on, names)
        if on != was_on:
            APP.notifier.add("player_denied", "Allow-list turned " + ("on" if on else "off"),
                             ("Only these %d players can join now." % len(names)) if on else "Everyone can join again.", "info", send=False)
        self.send(200, {"ok": True, "enabled": on, "names": names,
                        "note": "Saved - works right away, no restart needed." + (" Players already online stay connected." if on else "")})

    def post_authkey(self, q):
        key = re.sub(r"\s", "", str(self.body_json().get("key", "")))
        if key and not re.fullmatch(r"[A-Za-z0-9-]{8,128}", key):
            return self.fail(400, "That doesn't look like an AuthKey")
        I().set_authkey(key)
        if APP.server.status()["state"] == "running":
            APP.server.action("restart")
        self.send(200, {"ok": True, "note": "AuthKey saved encrypted. The server was restarted."})

    # ---------- mods
    def get_mods(self, q):
        mods = list_mods()
        self.send(200, {"mods": mods, "quarantine": list_quarantine(),
                        "checks": active_checks(), "auto_apply": not IS_WIN,
                        "download": sum(m["size"] for m in mods if m["enabled"]),
                        "maps_size": sum(m["size"] for m in mods if m["enabled"] and m["maps"]),
                        "desc_modsize": bool(I().meta.get("desc_modsize"))})

    def put_mods_upload(self, q):
        name = safe_zip_name(q.get("name"))
        if not name:
            return self.fail(400, "Only .zip files can be uploaded")
        tdir = tempfile.mkdtemp(dir=UPLOAD_TMP, prefix=".up-")   # own folder: parallel uploads can't mix
        try:
            return self._mods_upload(name, os.path.join(tdir, name))
        finally:
            shutil.rmtree(tdir, ignore_errors=True)

    def _mods_upload(self, name, tmp):
        self.body_to_file(tmp, 4 * 1024 ** 3)
        result = modscan.scan(tmp)
        if result["verdict"] == "blocked":
            os.remove(tmp)
            APP.alerts.raise_("mod:%s:%s" % (I().id, name), "A mod failed the virus check: %s" % name,
                              "\n".join(result["reasons"]) + "\nThe upload was refused.")
            return self.send(422, {"ok": False, "blocked": True, "reasons": result["reasons"]})
        try:
            os.remove(os.path.join(I().DISABLED_DIR, name))
        except OSError:
            pass
        dest = os.path.join(I().CLIENT_DIR, name)
        maps = zip_maps(tmp) or []
        if not IS_WIN:
            os.chmod(tmp, 0o664)      # set while it is still in our private folder
        shutil.move(tmp, dest)
        modscan.remember(dest, result.get("sha256"))
        refresh_mod_desc()
        APP.config_changed()
        self.send(200, {"ok": True, "name": name, "maps": maps,
                        "safety": result["verdict"], "reasons": result["reasons"], "checks": result["checks"]})

    def post_mods_action(self, q):
        b = self.body_json()
        act, name = b.get("action"), safe_zip_name(b.get("name"))
        if not name:
            return self.fail(400, "bad name")
        on, off = os.path.join(I().CLIENT_DIR, name), os.path.join(I().DISABLED_DIR, name)
        if act == "delete":
            for p in (on, off):
                if os.path.exists(p):
                    os.remove(p)
        elif act == "toggle":
            if os.path.exists(on):
                src, dst = on, off
            elif os.path.exists(off):
                src, dst = off, on
            else:
                return self.fail(404, "not found")
            r = modscan.cached_result(src)
            shutil.move(src, dst)
            if r:
                modscan.remember(dst, r.get("sha256"))
        elif act == "qdelete":
            for p in (os.path.join(I().QUAR_DIR, name), os.path.join(I().QUAR_DIR, name + ".why.txt")):
                if os.path.exists(p):
                    os.remove(p)
        else:
            return self.fail(400, "bad action")
        refresh_mod_desc()
        APP.config_changed()
        self.send(200, {"ok": True, "note": APP.applied_note()})

    def post_mods_rescan(self, q):
        res = []
        for m in list_mods():
            folder = I().CLIENT_DIR if m["enabled"] else I().DISABLED_DIR
            r = modscan.scan(os.path.join(folder, m["name"]), force=True)
            if r["verdict"] == "blocked":
                os.makedirs(I().QUAR_DIR, exist_ok=True)
                dest = os.path.join(I().QUAR_DIR, m["name"])
                shutil.move(os.path.join(folder, m["name"]), dest)
                modscan.write_note(dest + ".why.txt", modscan.why_text(r["reasons"]))
            res.append({"name": m["name"], "verdict": r["verdict"], "reasons": r["reasons"]})
        self.send(200, {"ok": True, "results": res})

    # ---------- players
    def get_players(self, q):
        a = analytics(APP.max_players())
        a["records"] = read_records()
        a["records_on"] = read_extras()["top"]
        self.send(200, a)

    def post_players_clear(self, q):
        for n in ("events.log", "events.log.1"):
            try:
                os.remove(os.path.join(I().STATS_DIR, n))
            except OSError:
                pass
        self.send(200, {"ok": True})

    # ---------- hide my IP
    def get_relay_check(self, q):
        """Test every server through the relay (TCP; UDP can't be tested from here)."""
        if not APP.settings.get("relay_host"):
            return self.fail(400, "Enter the relay address first")
        out = []
        for r in relay_servers():
            host = APP.settings.get("relay_host")
            port = r["relay_port"] or r["port"]
            if not port:
                continue
            t0 = time.time()
            ok = tcp_open(host, port, timeout=5)
            out.append({"id": r["id"], "name": r["name"], "address": fmt_addr(host, port), "ok": ok,
                        "ms": int((time.time() - t0) * 1000) if ok else None})
        self.send(200, {"results": out})

    def get_flood_status(self, q):
        if IS_WIN:
            return self.send(200, {"available": False})
        r = control("flood-status", timeout=20)
        self.send(200, {"available": True, "active": bool(r.get("active")), "dropped": int(r.get("dropped") or 0)})

    # ---------- network
    def get_network(self, q):
        data, _, _ = toml_parse(APP.read_config_text())
        self.send(200, network_check(data, APP.server.status(), q.get("deep") == "1"))

    # ---------- updates
    def get_updates(self, q):
        up = dict(APP.updates)
        up.setdefault("installed", APP.server.installed_version())
        up["easy_installed"] = EASY_VERSION
        up["repo"] = REPO
        self.send(200, up)

    def post_updates_check(self, q):
        self.send(200, APP.check_updates(notify=False))

    def post_updates_install(self, q):
        r = APP.server.update()
        if not r.get("ok"):
            return self.fail(500, r.get("msg") or "update failed")
        APP.server.version_cache = (None, None)
        APP.check_updates(notify=False)
        APP.notifier.add("update", "BeamMP server updated", "Now running %s." % (APP.server.installed_version() or "the newest version"),
                         "success", send=False)
        self.send(200, {"ok": True, "installed": APP.server.installed_version()})

    # ---------- logs
    def get_logs(self, q):
        try:
            n = max(50, min(2000, int(q.get("lines", 300))))
        except ValueError:
            n = 300
        lines, hints = tail_log(n)
        self.send(200, {"lines": lines, "hints": hints})

    # ---------- notifications
    def get_notifications(self, q):
        with LOCK:
            items = list(APP.notifier.items[:200])
        self.send(200, {"items": items})

    def post_notifications_read(self, q):
        with LOCK:
            for n in APP.notifier.items:
                n["read"] = True
            APP.notifier._save()
        self.send(200, {"ok": True})

    # ---------- security alerts
    def get_security(self, q):
        self.send(200, {"active": APP.alerts.active(), "enabled": bool(APP.settings.get("security_alerts")),
                        "reminders": bool(APP.settings.get("security_reminders"))})

    def post_security_ack(self, q):
        b = self.body_json(4096)
        aid = b.get("id")
        if aid is None or aid == "all":
            n = APP.alerts.ack(None)
        elif isinstance(aid, str) and re.fullmatch(r"[a-f0-9]{16}", aid):
            n = APP.alerts.ack(aid)
        else:
            n = 0
        self.send(200, {"ok": True, "stopped": n})

    def post_notifications_clear(self, q):
        with LOCK:
            APP.notifier.items = []
            APP.notifier._save()
        self.send(200, {"ok": True})

    def post_notifications_test(self, q):
        ch = self.body_json().get("channel")
        n = APP.notifier
        try:
            if ch == "discord":
                n.send_discord("Test notification", "Your BeamMP dashboard can post to this channel.", "success")
            elif ch == "email":
                n.send_email("Test notification", "Your BeamMP dashboard can send you emails.")
            else:
                n.add("test", "Test notification", "Notifications work.", "success", send=False)
        except Exception as e:
            return self.fail(400, short_err(e))
        self.send(200, {"ok": True})

    # ---------- Discord bot
    def get_discordbot(self, q):
        self.send(200, APP.bot.info())

    def post_discordbot(self, q):
        app = APP
        b = self.body_json()
        upd = {}
        if "token" in b and b["token"] is not None:
            tok = str(b["token"]).strip()
            if tok.lower().startswith("bot "):
                tok = tok[4:].strip()
            if tok and not DISCORD_TOKEN_RE.fullmatch(tok):
                return self.fail(400, "That isn't a bot token. Developer Portal → your app → Bot → Reset Token → Copy.")
            if tok:
                try:
                    discord_api("GET", "/users/@me", tok, timeout=15)
                except urllib.error.HTTPError as e:
                    if e.code == 401:
                        return self.fail(400, "Discord says this token is wrong or was reset. Copy a new one.")
                except Exception:
                    pass            # offline right now - the bot keeps retrying
            if tok != app.secrets.get("DISCORD_BOT_TOKEN"):
                app.secrets.set("DISCORD_BOT_TOKEN", tok)
                app.bot.app_id = None
                upd["discord_bot_guild"] = ""
        if "enabled" in b:
            upd["discord_bot"] = bool(b["enabled"])
            if upd["discord_bot"] and not app.secrets.has("DISCORD_BOT_TOKEN"):
                return self.fail(400, "Paste the bot token first")
        if "guild" in b:
            g = str(b["guild"] or "").strip()
            if g and not re.fullmatch(r"\d{15,22}", g):
                return self.fail(400, "Pick a Discord server")
            upd["discord_bot_guild"] = g
        if "users" in b:
            raw = b["users"] if isinstance(b["users"], list) else re.split(r"[\s,;]+", str(b["users"] or ""))
            ids = []
            for u in raw[:50]:
                u = str(u).strip().strip("<@!>")
                if not u:
                    continue
                if not re.fullmatch(r"\d{15,22}", u):
                    return self.fail(400, "User IDs are long numbers (Discord: Developer Mode → right-click a person → Copy User ID)")
                if u not in ids:
                    ids.append(u)
            upd["discord_bot_users"] = ids
        if upd:
            app.settings.update(upd)
        if "token" in b or "enabled" in b:
            app.bot.reconnect()
        elif "guild" in b:
            threading.Thread(target=lambda: app.bot.sync_commands(app.secrets.get("DISCORD_BOT_TOKEN")),
                             daemon=True).start()
        self.send(200, dict(app.bot.info(), ok=True))

    # ---------- settings
    def get_settings(self, q):
        app = APP
        s = app.settings.public()
        s.update({
            "has_discord": app.secrets.has("DISCORD_WEBHOOK"), "has_smtp_password": app.secrets.has("SMTP_PASSWORD"),
            "has_vt": app.secrets.has("VT_API_KEY"), "totp": app.secrets.has("TOTP_SECRET"),
            "platform": "windows" if IS_WIN else "linux", "lan_ip": lan_ip(),
            "cert_fingerprint": cert_fingerprint(), "https_now": self.https,
            "relay_servers": relay_servers(),
        })
        self.send(200, s)

    def post_settings(self, q):
        app = APP
        b = self.body_json()
        upd = clean_settings(b)
        # The saved email password only ever goes to the mail server it was
        # typed in for: changing the server or login without typing the
        # password again forgets it (so a stolen login can't redirect it).
        if smtp_target_changed(upd) and b.get("smtp_password") is None:
            app.secrets.set("SMTP_PASSWORD", "")
        if "discord_webhook" in b:
            url = str(b["discord_webhook"]).strip()
            if url and not valid_webhook(url):
                return self.fail(400, "That isn't a Discord webhook URL (https://discord.com/api/webhooks/...)")
            app.secrets.set("DISCORD_WEBHOOK", url)
        if "smtp_password" in b and b["smtp_password"] is not None:
            app.secrets.set("SMTP_PASSWORD", str(b["smtp_password"]))
        if "vt_key" in b:
            k = str(b["vt_key"]).strip().lower()
            if k and not re.fullmatch(r"[a-f0-9]{64}", k):
                return self.fail(400, "That doesn't look like a VirusTotal key")
            app.secrets.set("VT_API_KEY", k)
            if k:
                os.environ["VT_API_KEY"] = k
            else:
                os.environ.pop("VT_API_KEY", None)
        if upd:
            app.settings.update(upd)
        if "flood_protect" in upd:
            threading.Thread(target=app.flood_tick, daemon=True).start()
        self.send(200, {"ok": True})

    def post_password(self, q):
        app = APP
        b = self.body_json()
        if not hmac.compare_digest(str(b.get("current", "")).encode(), app.secrets.get("MODS_PASSWORD").encode()):
            return self.fail(400, "Current password is wrong")
        new = str(b.get("new", ""))
        minlen = 12 if app.settings.get("remote_enabled") else 8
        if len(new) < minlen:
            return self.fail(400, "Use at least %d characters" % minlen)
        app.secrets.set("MODS_PASSWORD", new)
        with LOCK:
            mine = self.cookie("es_session")
            app.sessions = {k: v for k, v in app.sessions.items() if k == mine}
        self.send(200, {"ok": True})

    # ---------- two-step login
    def post_2fa_begin(self, q):
        secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
        self.sess["pending_totp"] = secret
        label = urllib.parse.quote("BeamMP EasyServer:%s" % (server_name() or socket.gethostname())[:40])
        uri = "otpauth://totp/%s?secret=%s&issuer=BeamMP%%20EasyServer" % (label, secret)
        try:
            qr_size, qr_path = qr_svg_path(uri)
        except ValueError:
            qr_size, qr_path = 0, ""
        self.send(200, {"secret": " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)), "uri": uri,
                        "qr_size": qr_size, "qr_path": qr_path})

    def post_2fa_confirm(self, q):
        secret = self.sess.get("pending_totp")
        code = re.sub(r"\s", "", str(self.body_json().get("code", "")))
        if not secret:
            return self.fail(400, "Start the setup again")
        step = now() // 30
        if not any(hmac.compare_digest(totp_code(secret, c), code) for c in (step - 1, step, step + 1)):
            return self.fail(400, "That code is wrong - check the time on your phone and try again")
        APP.secrets.set("TOTP_SECRET", secret)
        with LOCK:
            APP.totp_last = step + 1
        self.sess.pop("pending_totp", None)
        self.send(200, {"ok": True})

    def post_2fa_disable(self, q):
        app = APP
        if app.settings.get("remote_enabled"):
            return self.fail(400, "Turn off internet access first")
        if not hmac.compare_digest(str(self.body_json().get("password", "")).encode(), app.secrets.get("MODS_PASSWORD").encode()):
            return self.fail(400, "Wrong password")
        app.secrets.set("TOTP_SECRET", "")
        self.send(200, {"ok": True})

    # ---------- remote access + HTTPS
    def post_remote(self, q):
        app = APP
        b = self.body_json()
        want_https = bool(b.get("https", app.settings.get("https")))
        want_remote = bool(b.get("remote_enabled", app.settings.get("remote_enabled")))
        if want_remote:
            want_https = True
            if not app.secrets.has("TOTP_SECRET"):
                return self.fail(400, "Set up two-step login first")
            if len(app.secrets.get("MODS_PASSWORD")) < 12:
                return self.fail(400, "Change your password to at least 12 characters first")
        if want_https and not os.path.exists(os.path.join(TLS_DIR, "cert.pem")):
            extra = [x for x in (public_ip(),) if x]
            tlsgen.generate(TLS_DIR, extra)
        https_changed = want_https != app.settings.get("https")
        was_remote = app.settings.get("remote_enabled")
        app.settings.update({"https": want_https, "remote_enabled": want_remote})
        network = ""
        if want_remote != bool(was_remote):
            if IS_WIN:
                network = "Windows firewall: the dashboard port was already allowed by the installer."
            else:
                network = control("firewall-remote", state="on" if want_remote else "off",
                                  port=app.settings.get("port"), timeout=30).get("msg", "")
            app.notifier.add("network", "Internet access turned " + ("on" if want_remote else "off"), network)
        self.send(200, {"ok": True, "restart": https_changed, "network": network,
                        "url": "%s://%s:%d" % ("https" if want_https else "http", lan_ip(), app.settings.get("port"))})
        if https_changed:
            threading.Thread(target=restart_dashboard, daemon=True).start()

    # ---------- import / export
    def get_export(self, q):
        app = APP
        include_mods = q.get("mods") == "1"
        fd, tmp = tempfile.mkstemp(suffix=".zip", dir=DATA_DIR)
        os.close(fd)
        try:
            text = app.read_config_text()
            text = toml_set(text, "General", "AuthKey", "") if "AuthKey" in text else text
            mods = list_mods()
            meta = {"format": "beammp-easyserver-export", "version": 1, "easy_version": EASY_VERSION,
                    "exported_at": now(), "server_name": server_name(),
                    "settings": {k: v for k, v in app.settings.public().items()
                                 if k in ("notify", "smtp_host", "smtp_port", "smtp_security", "smtp_user",
                                          "smtp_from", "smtp_to", "auto_restart", "update_check",
                                          "discord_enabled", "email_enabled")},
                    "mods": [{"name": m["name"], "enabled": m["enabled"], "size": m["size"]} for m in mods],
                    "includes_mods": include_mods}
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("ServerConfig.toml", text)
                z.writestr("easyserver-export.json", json.dumps(meta, indent=1))
                # files from the server's folders are opened without following
                # links, so a hacked game server can't slip the dashboard's own
                # files (like its HTTPS key) into your backup
                try:
                    with open_shared(I().ALLOW_FILE) as f:
                        z.writestr("allowlist.txt", f.read(256 * 1024))
                except OSError:
                    pass
                if include_mods:
                    for m in mods:
                        src = os.path.join(I().CLIENT_DIR if m["enabled"] else I().DISABLED_DIR, m["name"])
                        try:
                            with open_shared(src, "rb") as f, z.open(
                                    zipfile.ZipInfo(("mods/" if m["enabled"] else "mods-disabled/") + m["name"],
                                                    time.localtime()[:6]), "w", force_zip64=True) as dst:
                                shutil.copyfileobj(f, dst)
                        except OSError:
                            continue
            size = os.path.getsize(tmp)
            fname = "beammp-server-%s.zip" % time.strftime("%Y%m%d-%H%M")
            self.send_response(200)
            self.headers_common("application/zip", size, {"Content-Disposition": 'attachment; filename="%s"' % fname})
            with open(tmp, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
        finally:
            os.remove(tmp)

    def put_import(self, q):
        app = APP
        fd, tmp = tempfile.mkstemp(suffix=".zip", dir=DATA_DIR)
        os.close(fd)
        report = {"config": False, "settings": False, "mods_added": [], "mods_blocked": [], "skipped": []}
        try:
            self.body_to_file(tmp, 20 * 1024 ** 3)
            try:
                z = zipfile.ZipFile(tmp)
            except zipfile.BadZipFile:
                return self.fail(400, "That isn't an export file (.zip)")
            with z:
                names = z.namelist()
                if "ServerConfig.toml" not in names:
                    return self.fail(400, "No ServerConfig.toml in this file")
                info = z.getinfo("ServerConfig.toml")
                if info.file_size > 200000:
                    return self.fail(400, "ServerConfig.toml is too large")
                text = z.read(info).decode("utf-8", "replace")
                _, issues = validate_config(text, app.settings.get("port"), I().has_authkey())
                if any(i["level"] == "error" for i in issues):
                    return self.send(400, {"ok": False, "error": "The imported config has errors", "issues": issues})
                if q.get("settings", "1") == "1" and "easyserver-export.json" in names:
                    if z.getinfo("easyserver-export.json").file_size > 1024 * 1024:
                        return self.fail(400, "easyserver-export.json is too large")
                    try:
                        meta = json.loads(z.read("easyserver-export.json") or b"{}")
                    except ValueError:
                        meta = None
                    s = meta.get("settings") if isinstance(meta, dict) else None
                    if isinstance(s, dict):
                        try:
                            allowed = clean_settings(s)
                        except ValueError as e:
                            return self.fail(400, "Imported settings: %s" % e)
                        if smtp_target_changed(allowed) and app.secrets.has("SMTP_PASSWORD"):
                            # never send the saved email password to a mail server from a file
                            for k in ("smtp_host", "smtp_user", "smtp_port", "smtp_security"):
                                allowed.pop(k, None)
                            report["skipped"].append("email server settings (keeps your current mail server)")
                        app.settings.update(allowed)
                        report["settings"] = True
                if "allowlist.txt" in names and z.getinfo("allowlist.txt").file_size < 256 * 1024:
                    lines = z.read("allowlist.txt").decode("utf-8", "replace").splitlines()
                    on = any(re.fullmatch(r"mode\s*=\s*on", l.strip(), re.I) for l in lines)
                    try:
                        listed = clean_allow_names([l for l in lines if l.strip() and not l.strip().startswith("#")
                                                    and not re.fullmatch(r"mode\s*=\s*\w+", l.strip())])
                        write_allowlist(on and bool(listed), listed)
                        report["allowlist"] = len(listed)
                    except ValueError:
                        report["skipped"].append("allowlist.txt")
                if q.get("mods", "1") == "1":
                    total = 0
                    for n in names:
                        m = re.fullmatch(r"(mods|mods-disabled)/([^/]+)", n)
                        if not m:
                            if n not in ("ServerConfig.toml", "easyserver-export.json", "allowlist.txt") and not n.endswith("/"):
                                report["skipped"].append(n[:120])
                            continue
                        name = safe_zip_name(m.group(2))
                        if not name:
                            report["skipped"].append(n[:120])
                            continue
                        zi = z.getinfo(n)
                        # zip bombs: a tiny entry that unpacks to many GB fills the disk
                        total += zi.file_size
                        if (zi.file_size > 4 * 1024 ** 3 or total > 40 * 1024 ** 3 or
                                (zi.file_size > 50 * 1024 ** 2 and zi.file_size > 200 * max(zi.compress_size, 1)) or
                                shutil.disk_usage(UPLOAD_TMP).free < zi.file_size + 1024 ** 3):
                            report["skipped"].append(n[:120] + " (too large)")
                            if zi.file_size > 200 * max(zi.compress_size, 1):
                                app.alerts.raise_("import-bomb", "An imported backup contained a zip bomb",
                                                  "%s unpacks to %d MB from %d KB. It was skipped. Only import backups "
                                                  "you made yourself." % (n[:80], zi.file_size // 2 ** 20, zi.compress_size // 1024))
                            continue
                        tdir = tempfile.mkdtemp(dir=UPLOAD_TMP, prefix=".imp-")
                        try:
                            dest_tmp = os.path.join(tdir, name)
                            with z.open(zi) as src, open(dest_tmp, "wb") as dst:
                                shutil.copyfileobj(src, dst)   # stops at the size listed above
                            r = modscan.scan(dest_tmp)
                            if r["verdict"] == "blocked":
                                report["mods_blocked"].append({"name": name, "reasons": r["reasons"]})
                                continue
                            if not IS_WIN:
                                os.chmod(dest_tmp, 0o664)
                            final = os.path.join(I().CLIENT_DIR if m.group(1) == "mods" else I().DISABLED_DIR, name)
                            shutil.move(dest_tmp, final)
                            modscan.remember(final, r.get("sha256"))
                            report["mods_added"].append(name)
                        finally:
                            shutil.rmtree(tdir, ignore_errors=True)
            old_port = (toml_parse(app.read_config_text())[0].get("General") or {}).get("Port")
            text = app.move_plaintext_authkey(text)
            app.write_config_text(text)
            report["config"] = True
            new_port = (toml_parse(text)[0].get("General") or {}).get("Port")
            if isinstance(new_port, int) and new_port != old_port and not IS_WIN:
                control("firewall-game", old=old_port if isinstance(old_port, int) else None, new=new_port, timeout=30)
                app.notifier.add("network", "Server port changed", "Import changed the port %s -> %d. "
                                 "Remember to forward the new port on your router." % (old_port, new_port))
            self.send(200, {"ok": True, "report": report, "note": app.applied_note()})
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass


def clean_settings(b):
    """Checked copy of the user-changeable notification settings in b (raises ValueError)."""
    upd = {}
    if isinstance(b.get("notify"), dict):
        cur = APP.settings.get("notify")
        cur.update({k: bool(v) for k, v in b["notify"].items() if k in DEFAULT_SETTINGS["notify"]})
        upd["notify"] = cur
    for k in ("discord_enabled", "email_enabled", "auto_restart", "update_check", "security_alerts", "security_reminders",
              "relay_enabled", "flood_protect"):
        if k in b:
            upd[k] = bool(b[k])
    if "relay_host" in b:
        h = str(b["relay_host"]).strip().strip("[]")
        if h:
            try:
                ipaddress.ip_address(h)
            except ValueError:
                if not re.fullmatch(r"(?=.{1,253}$)[A-Za-z0-9]([A-Za-z0-9-]{0,62}[A-Za-z0-9])?"
                                    r"(\.[A-Za-z0-9]([A-Za-z0-9-]{0,62}[A-Za-z0-9])?)*", h):
                    raise ValueError("The relay address must be a host name (like name.playit.gg) or an IP address, "
                                     "without http:// and without the port")
        upd["relay_host"] = h
    if "relay_ports" in b:
        if not isinstance(b["relay_ports"], dict):
            raise ValueError("bad relay ports")
        with LOCK:
            known = set(INSTANCES)
        ports = {}
        for sid, v in b["relay_ports"].items():
            if sid not in known or v in (None, ""):
                continue
            try:
                v = int(v)
                assert 1 <= v <= 65535
            except (TypeError, ValueError, AssertionError):
                raise ValueError("Relay ports must be numbers from 1 to 65535")
            ports[sid] = v
        upd["relay_ports"] = ports
    if upd.get("relay_enabled") and not upd.get("relay_host", APP.settings.get("relay_host")):
        raise ValueError("Enter the relay address first")
    if upd.get("flood_protect") and IS_WIN:
        raise ValueError("Flood protection is only available on Linux")
    for k in ("smtp_host", "smtp_user", "smtp_from", "smtp_to"):
        if k in b:
            v = str(b[k]).strip()
            if len(v) > 300 or any(c in v for c in "\r\n\x00"):
                raise ValueError("%s is invalid" % k)
            upd[k] = v
    if upd.get("smtp_host") and not re.fullmatch(r"[A-Za-z0-9.\-]{1,253}|\[?[0-9A-Fa-f:.]+\]?", upd["smtp_host"]):
        raise ValueError("SMTP server must be a host name like smtp.gmail.com")
    if "smtp_port" in b:
        try:
            p = int(b["smtp_port"])
            assert 1 <= p <= 65535
            upd["smtp_port"] = p
        except (TypeError, ValueError, AssertionError):
            raise ValueError("SMTP port must be a number")
    if "smtp_security" in b:
        if b["smtp_security"] not in ("starttls", "ssl", "none"):
            raise ValueError("bad SMTP security")
        upd["smtp_security"] = b["smtp_security"]
    return upd


def smtp_target_changed(upd):
    cur = APP.settings
    return any(k in upd and str(upd[k]) != str(cur.get(k)) for k in ("smtp_host", "smtp_user", "smtp_port", "smtp_security"))


def analytics_online():
    o = read_json(os.path.join(I().STATS_DIR, "online.json"), None)
    if isinstance(o, dict) and now() - int(o.get("t", 0)) < 120:
        return [str(p)[:64] for p in o.get("players", [])][:200]
    return []


def active_checks():
    c = ["built-in checks"]
    if shutil.which("clamdscan") or shutil.which("clamscan"):
        c.append("ClamAV")
    if IS_WIN:
        c.append("Microsoft Defender")
    if os.environ.get("VT_API_KEY") or (APP and APP.secrets.has("VT_API_KEY")):
        c.append("VirusTotal")
    return c


def cert_fingerprint():
    p = os.path.join(TLS_DIR, "cert.pem")
    try:
        return tlsgen.fingerprint(p)
    except (OSError, ValueError):
        return None


def restart_dashboard():
    time.sleep(1.5)
    if IS_WIN:
        subprocess.Popen([sys.executable, os.path.abspath(__file__)], cwd=HERE,
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) |
                         getattr(subprocess, "CREATE_NO_WINDOW", 0))
        os._exit(0)
    else:
        control("restart-dashboard", timeout=10)


# ----------------------------------------------------------------------------- server
class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 64

    MAX_CONN = 96          # at once, in total
    MAX_CONN_PER_IP = 24

    def __init__(self, addr, tls_ctx=None):
        self.tls_ctx = tls_ctx
        self.conn_lock = threading.Lock()
        self.conns = {}
        super().__init__(addr, Handler)

    def process_request(self, request, client_address):
        ip = fail_key(client_address[0])
        with self.conn_lock:
            total = sum(self.conns.values())
            if total >= self.MAX_CONN or self.conns.get(ip, 0) >= self.MAX_CONN_PER_IP:
                busy = True
            else:
                busy = False
                self.conns[ip] = self.conns.get(ip, 0) + 1
        if busy:            # too many open connections: drop instead of piling up threads
            self.shutdown_request(request)
            if APP:
                APP.alerts.seen("flood", 20, 60, "The dashboard is being flooded with connections",
                                "Hundreds of connections at once (last from %s). Extra ones are being dropped so the "
                                "dashboard keeps working. If it keeps happening, turn internet access off; if your whole "
                                "internet drops, restart your router to get a new IP address." % client_address[0])
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            ip = fail_key(client_address[0])
            with self.conn_lock:
                n = self.conns.get(ip, 1) - 1
                if n > 0:
                    self.conns[ip] = n
                else:
                    self.conns.pop(ip, None)

    def get_request(self):
        sock, addr = self.socket.accept()
        if self.tls_ctx:
            sock = self.tls_ctx.wrap_socket(sock, server_side=True, do_handshake_on_connect=False)
        return sock, addr

    def finish_request(self, request, client_address):
        request.settimeout(30)
        if isinstance(request, ssl.SSLSocket):
            try:
                request.do_handshake()
            except (ssl.SSLError, OSError):
                return
        super().finish_request(request, client_address)

    def handle_error(self, request, client_address):
        pass


def main():
    global APP
    load_servers()
    APP = App()
    if not IS_WIN:
        os.umask(0o002)
    port = int(os.environ.get("DASHBOARD_PORT") or APP.settings.get("port") or 30815)
    ctx = None
    if APP.settings.get("https"):
        if not os.path.exists(os.path.join(TLS_DIR, "cert.pem")):
            tlsgen.generate(TLS_DIR)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(os.path.join(TLS_DIR, "cert.pem"), os.path.join(TLS_DIR, "key.pem"))
    httpd = None
    for _ in range(30):     # the previous instance may still be closing
        try:
            httpd = Server(("0.0.0.0", port), ctx)
            break
        except OSError:
            time.sleep(1)
    if not httpd:
        sys.exit("Port %d is busy - is the dashboard already running?" % port)
    threading.Thread(target=APP.monitor, daemon=True).start()
    threading.Thread(target=APP.bot.run, daemon=True).start()
    if not APP.updates:
        threading.Thread(target=APP.check_updates, kwargs={"notify": True}, daemon=True).start()
    print("BeamMP EasyServer dashboard %s on %s://0.0.0.0:%d" % (EASY_VERSION, "https" if ctx else "http", port), flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    if IS_WIN and (sys.stderr is None or sys.stdout is None):
        # started hidden (pythonw): keep messages and crashes in a log file
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            _log = open(os.path.join(DATA_DIR, "dashboard.log"), "a", encoding="utf-8", buffering=1)
            sys.stdout = sys.stderr = _log
        except OSError:
            pass
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        if sys.stderr:
            sys.stderr.write(time.strftime("%Y-%m-%d %H:%M:%S ") + "dashboard crashed:\n" + traceback.format_exc())
            sys.stderr.flush()
        raise
