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

EASY_VERSION = "1.1.0"
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
                "BEAMMP_AUTH_KEY")

DEFAULT_SETTINGS = {
    "port": 30815,
    "https": False,
    "remote_enabled": False,
    "notify": {"crash": True, "stopped": True, "update": True, "mod_blocked": True,
               "login_failed": True, "player_join": False, "player_denied": True},
    "discord_enabled": False,
    "email_enabled": False,
    "smtp_host": "", "smtp_port": 587, "smtp_security": "starttls",
    "smtp_user": "", "smtp_from": "", "smtp_to": "",
    "auto_restart": True,
    "update_check": True,
}

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
            with open(self.CONFIG, encoding="utf-8") as f:
                n = toml_parse(f.read())[0].get("General", {}).get("Name")
            if isinstance(n, str) and n.strip():
                return re.sub(r"\^.", "", n).strip()[:60]
        except OSError:
            pass
        return "Main server" if self.id == "main" else "Server " + self.id

    def port(self):
        try:
            with open(self.CONFIG, encoding="utf-8") as f:
                v = toml_parse(f.read())[0].get("General", {}).get("Port")
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


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
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
    name = os.path.basename(urllib.parse.unquote(name or "")).strip()
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
            if n.lower().endswith(".zip") and os.path.isfile(p):
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
class Notifier:
    COLORS = {"error": 0xE5484D, "warning": 0xF5A524, "info": 0x3B82F6, "success": 0x30A46C}

    def __init__(self, settings, secrets_):
        self.s, self.sec = settings, secrets_
        self.items = read_json(NOTIF_FILE, [])

    def add(self, kind, title, message, level="info", send=True):
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
        if send and self.s.get("notify").get(kind, False):
            threading.Thread(target=self._deliver, args=(item,), daemon=True).start()
        return item

    def _save(self):
        try:
            write_json(NOTIF_FILE, self.items)
        except OSError:
            pass

    def _deliver(self, item):
        notes = []
        if self.s.get("discord_enabled") and self.sec.has("DISCORD_WEBHOOK"):
            try:
                self.send_discord(item["title"], item["message"], item["level"], footer=item.get("server_name"))
                notes.append("Discord")
            except Exception as e:
                notes.append("Discord failed: %s" % short_err(e))
        if self.s.get("email_enabled") and self.s.get("smtp_host"):
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
        with open(I().CONFIG, encoding="utf-8") as f:
            data, _, _ = toml_parse(f.read())
        return str(data.get("General", {}).get("Name", ""))
    except OSError:
        return ""


# ----------------------------------------------------------------------------- allow-list
ALLOW_NAME = re.compile(r"[^\x00-\x1f\x7f#]{1,40}")
ALLOW_MAX = 1000


def read_allowlist():
    on, names = False, []
    try:
        with open(I().ALLOW_FILE, encoding="utf-8", errors="replace") as f:
            for line in f:
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
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Managed by the BeamMP EasyServer dashboard (Config -> Who can join).\n")
        f.write("# mode=on: only the names below can join. Names are not case-sensitive.\n")
        f.write("mode=%s\n" % ("on" if on else "off"))
        for n in names:
            f.write(n + "\n")
    try:
        os.chmod(tmp, 0o664)
    except OSError:
        pass
    os.replace(tmp, I().ALLOW_FILE)


def recent_denied(days=7):
    seen, out = set(), []
    for e in reversed(read_events(now() - days * 86400)):
        if e.get("ev") == "denied":
            n = str(e.get("name", ""))[:40]
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
        with open(I().VOTE_FILE, encoding="utf-8", errors="replace") as f:
            for line in f:
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
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Managed by the BeamMP EasyServer dashboard (Config -> Map vote).\n")
        f.write("mode=%s\n" % ("on" if on else "off"))
        for m in maps:
            f.write(m + "\n")
    try:
        os.chmod(tmp, 0o664)
    except OSError:
        pass
    os.replace(tmp, I().VOTE_FILE)


# ----------------------------------------------------------------------------- analytics
def read_events(since=0):
    evs = []
    for name in ("events.log.1", "events.log"):
        try:
            with open(os.path.join(I().STATS_DIR, name), encoding="utf-8", errors="replace") as f:
                for line in f:
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
    if pip:
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
    if deep and pip:
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
    if pip and ipaddress.ip_address(pip) in ipaddress.ip_network("100.64.0.0/10"):
        tips.append("Your provider uses CGNAT (shared IP) - port forwarding won't work. Ask them for a public IPv4 address.")
    return {"port": port, "lan_ip": lip, "public_ip": pip, "checks": checks, "tips": tips}


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


def ip_is_loopback(ip):
    try:
        a = ipaddress.ip_address(ip)
        if a.version == 6 and a.ipv4_mapped:
            a = a.ipv4_mapped
        return a.is_loopback
    except ValueError:
        return False


# ============================================================================= the app
class App:
    def __init__(self):
        ensure_dirs()
        self.settings = Settings()
        self.secrets = Secrets()
        if self.secrets.has("VT_API_KEY"):
            os.environ["VT_API_KEY"] = self.secrets.get("VT_API_KEY")   # used by modscan
        self.notifier = Notifier(self.settings, self.secrets)
        self.sessions = {}
        self.fails = {}
        self.locked = {}
        self.global_fails = []
        self.totp_last = 0
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
            with open(I().CONFIG, encoding="utf-8") as f:
                return f.read()
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
            with open(I().CONFIG, "w", encoding="utf-8") as f:
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
                if self.settings.get("update_check") and now() >= next_update:
                    next_update = now() + 6 * 3600
                    self.check_updates(notify=True)
            except Exception as e:
                sys.stderr.write("updates: %s\n" % short_err(e))

    def _monitor_init(self, inst):
        st = inst.server.status()
        try:
            ev_pos = os.path.getsize(os.path.join(inst.STATS_DIR, "events.log"))
        except OSError:
            ev_pos = 0
        return {"inst": inst, "last": st, "restarts": st.get("restarts", 0), "seen_q": set(n["name"] for n in list_quarantine()),
                "ev_pos": ev_pos, "last_t": now(), "pending_map": None}

    def _monitor_one(self, inst, S):
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
                self.notifier.add("mod_blocked", "Mod blocked: %s" % item["name"],
                                  item["why"] or "It failed the virus check.", "warning")
        S["seen_q"] = set(i["name"] for i in q)
        # events from the EasyServerStats plugin
        path = os.path.join(inst.STATS_DIR, "events.log")
        try:
            size = os.path.getsize(path)
            if size < S["ev_pos"]:
                S["ev_pos"] = 0
            if size > S["ev_pos"]:
                with open(path, encoding="utf-8", errors="replace") as f:
                    f.seek(S["ev_pos"])
                    chunk = f.read(256 * 1024)
                    S["ev_pos"] += len(chunk.encode("utf-8"))
                joined, denied = [], []
                for line in chunk.splitlines():
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(e, dict) or not isinstance(e.get("t"), int) or e["t"] < S["last_t"]:
                        continue
                    if e.get("ev") == "join":
                        joined.append(str(e.get("name", "?"))[:64])
                    elif e.get("ev") == "mapvote" and isinstance(e.get("map"), str):
                        S["pending_map"] = (now() + 30, e["map"][:80], str(e.get("by", ""))[:64])
                    elif e.get("ev") == "denied":
                        n = str(e.get("name", "?"))[:64]
                        if not any(d[0] == n for d in denied):
                            denied.append((n, bool(e.get("guest"))))
                    S["last_t"] = max(S["last_t"], e["t"])
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
            host = public_ip() or lan_ip()
            where = "\nAddress: `%s:%s`" % (host, g.get("Port"))
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
        with LOCK:
            if self.locked.get(ip, 0) > t:
                return True
            if not ip_is_lan(ip):
                self.global_fails = [x for x in self.global_fails if x > t - 600]
                if len(self.global_fails) >= 30:
                    return True
        return False

    def login_failed(self, ip):
        t = now()
        with LOCK:
            f = [x for x in self.fails.get(ip, []) if x > t - 900] + [t]
            self.fails[ip] = f
            if not ip_is_lan(ip):
                self.global_fails.append(t)
            if len(f) >= 5:
                self.locked[ip] = t + 900
                self.fails[ip] = []
                lock = True
            else:
                lock = False
        if lock:
            self.notifier.add("login_failed", "Dashboard login blocked",
                              "5 wrong passwords from %s - that address is blocked for 15 minutes." % ip, "warning")

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
        sys.stderr.write("%s %s\n" % (self.client_address[0], (fmt % args).split("?")[0]))

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

    def body_json(self, limit=1024 * 1024):
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            raise ValueError("request too large")
        raw = self.rfile.read(n) if n else b"{}"
        try:
            v = json.loads(raw or b"{}")
            return v if isinstance(v, dict) else {}
        except ValueError:
            raise ValueError("bad JSON")

    def body_to_file(self, path, limit):
        n = int(self.headers.get("Content-Length") or 0)
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
        if not app.secrets.has("MODS_PASSWORD") and not ip_is_loopback(self.ip):
            path, _ = self.route()
            if path.startswith("/api/") and path not in ("/api/session",):
                self.send(403, {"ok": False, "error": "Set a password first - open the dashboard on the server computer itself."})
                return False
        return True

    def csrf_ok(self, sess):
        if self.headers.get("X-ES-CSRF") != sess["csrf"]:
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
            "setup_allowed": ip_is_loopback(self.ip),
            "totp": app.secrets.has("TOTP_SECRET"),
            "version": EASY_VERSION, "platform": "windows" if IS_WIN else "linux",
            "https": self.https,
        })

    def api_setup(self, q):
        app = APP
        if app.secrets.has("MODS_PASSWORD") or not ip_is_loopback(self.ip):
            return self.fail(403, "Setup is only possible once, on the server computer itself")
        b = self.body_json()
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
        if ok_pw and app.secrets.has("TOTP_SECRET") and not app.verify_totp(str(b.get("code", ""))):
            app.login_failed(self.ip)
            return self.fail(401, "Wrong or expired two-step code", need_code=True)
        if not ok_pw:
            time.sleep(0.7)
            app.login_failed(self.ip)
            return self.fail(401, "Wrong password", need_code=app.secrets.has("TOTP_SECRET"))
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
        for m in b.get("maps", []):
            m = str(m).strip()
            if m in avail and m not in maps:
                maps.append(m)
        on = bool(b.get("enabled"))
        if on and len(maps) < 2:
            return self.fail(400, "Pick at least two maps to vote between")
        write_mapvote(on, maps)
        self.send(200, {"ok": True, "note": "Saved - players can type /vote in chat right away." if on else "Saved - map voting is off."})

    def post_server_action(self, q):
        what = self.body_json().get("action")
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
        self.send(200, {"mods": list_mods(), "quarantine": list_quarantine(),
                        "checks": active_checks(), "auto_apply": not IS_WIN})

    def put_mods_upload(self, q):
        name = safe_zip_name(q.get("name"))
        if not name:
            return self.fail(400, "Only .zip files can be uploaded")
        tmp = os.path.join(UPLOAD_TMP, name)
        self.body_to_file(tmp, 4 * 1024 ** 3)
        result = modscan.scan(tmp)
        if result["verdict"] == "blocked":
            os.remove(tmp)
            APP.notifier.add("mod_blocked", "Mod blocked: %s" % name, "\n".join(result["reasons"]), "warning")
            return self.send(422, {"ok": False, "blocked": True, "reasons": result["reasons"]})
        try:
            os.remove(os.path.join(I().DISABLED_DIR, name))
        except OSError:
            pass
        dest = os.path.join(I().CLIENT_DIR, name)
        shutil.move(tmp, dest)
        if not IS_WIN:
            try:
                os.chmod(dest, 0o664)
            except OSError:
                pass
        APP.config_changed()
        self.send(200, {"ok": True, "name": name, "maps": zip_maps(dest) or [],
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
                shutil.move(on, off)
            elif os.path.exists(off):
                shutil.move(off, on)
            else:
                return self.fail(404, "not found")
        elif act == "qdelete":
            for p in (os.path.join(I().QUAR_DIR, name), os.path.join(I().QUAR_DIR, name + ".why.txt")):
                if os.path.exists(p):
                    os.remove(p)
        else:
            return self.fail(400, "bad action")
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
                with open(dest + ".why.txt", "w", encoding="utf-8") as f:
                    f.write("Blocked by the BeamMP EasyServer mod safety check:\n- " + "\n- ".join(r["reasons"]) + "\n")
            res.append({"name": m["name"], "verdict": r["verdict"], "reasons": r["reasons"]})
        self.send(200, {"ok": True, "results": res})

    # ---------- players
    def get_players(self, q):
        self.send(200, analytics(APP.max_players()))

    def post_players_clear(self, q):
        for n in ("events.log", "events.log.1"):
            try:
                os.remove(os.path.join(I().STATS_DIR, n))
            except OSError:
                pass
        self.send(200, {"ok": True})

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

    # ---------- settings
    def get_settings(self, q):
        app = APP
        s = app.settings.public()
        s.update({
            "has_discord": app.secrets.has("DISCORD_WEBHOOK"), "has_smtp_password": app.secrets.has("SMTP_PASSWORD"),
            "has_vt": app.secrets.has("VT_API_KEY"), "totp": app.secrets.has("TOTP_SECRET"),
            "platform": "windows" if IS_WIN else "linux", "lan_ip": lan_ip(),
            "cert_fingerprint": cert_fingerprint(), "https_now": self.https,
        })
        self.send(200, s)

    def post_settings(self, q):
        app = APP
        b = self.body_json()
        upd = {}
        if isinstance(b.get("notify"), dict):
            cur = app.settings.get("notify")
            cur.update({k: bool(v) for k, v in b["notify"].items() if k in DEFAULT_SETTINGS["notify"]})
            upd["notify"] = cur
        for k in ("discord_enabled", "email_enabled", "auto_restart", "update_check"):
            if k in b:
                upd[k] = bool(b[k])
        for k in ("smtp_host", "smtp_user", "smtp_from", "smtp_to"):
            if k in b:
                v = str(b[k]).strip()
                if len(v) > 300 or "\n" in v:
                    return self.fail(400, "%s is invalid" % k)
                upd[k] = v
        if "smtp_port" in b:
            try:
                p = int(b["smtp_port"])
                assert 1 <= p <= 65535
                upd["smtp_port"] = p
            except (TypeError, ValueError, AssertionError):
                return self.fail(400, "SMTP port must be a number")
        if "smtp_security" in b:
            if b["smtp_security"] not in ("starttls", "ssl", "none"):
                return self.fail(400, "bad SMTP security")
            upd["smtp_security"] = b["smtp_security"]
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
        self.send(200, {"secret": " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)), "uri": uri})

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
                if os.path.exists(I().ALLOW_FILE):
                    z.write(I().ALLOW_FILE, "allowlist.txt")
                if include_mods:
                    for m in mods:
                        src = os.path.join(I().CLIENT_DIR if m["enabled"] else I().DISABLED_DIR, m["name"])
                        z.write(src, ("mods/" if m["enabled"] else "mods-disabled/") + m["name"],
                                compress_type=zipfile.ZIP_STORED)
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
                    meta = json.loads(z.read("easyserver-export.json")[:1024 * 1024] or b"{}")
                    s = meta.get("settings") if isinstance(meta, dict) else None
                    if isinstance(s, dict):
                        allowed = {k: s[k] for k in s if k in ("notify", "smtp_host", "smtp_port", "smtp_security",
                                                               "smtp_user", "smtp_from", "smtp_to", "auto_restart",
                                                               "update_check", "discord_enabled", "email_enabled")}
                        if isinstance(allowed.get("notify"), dict):
                            cur = app.settings.get("notify")
                            cur.update({k: bool(v) for k, v in allowed["notify"].items() if k in cur})
                            allowed["notify"] = cur
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
                        dest_tmp = os.path.join(UPLOAD_TMP, name)
                        with z.open(n) as src, open(dest_tmp, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        r = modscan.scan(dest_tmp)
                        if r["verdict"] == "blocked":
                            os.remove(dest_tmp)
                            report["mods_blocked"].append({"name": name, "reasons": r["reasons"]})
                            continue
                        shutil.move(dest_tmp, os.path.join(I().CLIENT_DIR if m.group(1) == "mods" else I().DISABLED_DIR, name))
                        report["mods_added"].append(name)
            text = app.move_plaintext_authkey(text)
            app.write_config_text(text)
            report["config"] = True
            self.send(200, {"ok": True, "report": report, "note": app.applied_note()})
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass


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

    def __init__(self, addr, tls_ctx=None):
        self.tls_ctx = tls_ctx
        super().__init__(addr, Handler)

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
    if not APP.updates:
        threading.Thread(target=APP.check_updates, kwargs={"notify": True}, daemon=True).start()
    print("BeamMP EasyServer dashboard %s on %s://0.0.0.0:%d" % (EASY_VERSION, "https" if ctx else "http", port), flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
