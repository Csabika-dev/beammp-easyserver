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
import binascii
import hashlib
import hmac
from html import escape as html_escape
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
import zlib
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EASY_VERSION = "1.15.2"
# Paid extras (supporter licence, Experimental for supporters only). Off = EasyServer is fully free:
# no supporter box, and everyone can pick the Rolling release (newest code). Turn on again later.
PAID_FEATURES = False
REPO = "Csabika-dev/beammp-easyserver"
BEAMMP_REPO = "BeamMP/BeamMP-Server"
# Supporter licences are sold through Lemon Squeezy. Their licence API needs no
# account key: a key is activated for this install and checked once a day.
# Only keys from this store count (0 = the shop isn't open yet).
UPNP_IDLE = 30 * 60      # "only when needed": close the port this long after the last player / invite
JOIN_OPEN = 2 * 3600      # Discord /join keeps the port open this long
LS_STORE_ID = 0
LS_API = "https://api.lemonsqueezy.com/v1/licenses/"
SUPPORT_URL = "https://csabika-dev.github.io/beammp-easyserver/#support"
SITE_URL = "https://csabika-dev.github.io/beammp-easyserver/"
SUPPORTER_GRACE = 14 * 86400        # keep supporter features when the check can't reach Lemon Squeezy
IS_WIN = os.name == "nt"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modscan  # noqa: E402
import tlsgen   # noqa: E402
import upnp     # noqa: E402
import guard    # noqa: E402

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
HOST_FILE = os.path.join(DATA_DIR, "host.json")   # written by the Mac installer when this Linux runs in a small VM on a Mac
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
                "BEAMMP_AUTH_KEY", "DISCORD_BOT_TOKEN", "DUCKDNS_TOKEN", "NTFY_TOPIC", "WAKE_TOPIC", "USERS_KEY",
                "TELEGRAM_TOKEN", "CUSTOM_WEBHOOK", "SUPPORTER_KEY", "GDRIVE_SECRET", "GDRIVE_REFRESH")

DEFAULT_SETTINGS = {
    "port": 30815,
    "https": False,
    "remote_enabled": False,
    "notify": {"crash": True, "stopped": True, "update": True, "mod_blocked": True,
               "login_failed": True, "player_join": False, "player_denied": True,
               "moderation": True, "network": True, "restart": False,
               "resources": True, "backup": True, "rotation": False, "mod_update": True, "report": True,
               "sleep": False},
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
    "guard_on": False,             # BeamMP-only guard: block addresses that keep knocking on the game port but never play
    "auto_update": False,          # install BeamMP updates at a scheduled restart
    "discord_bot": False,          # slash commands (/status, /start, /stop, /restart) - needs a bot token
    "discord_bot_guild": "",       # the one Discord server the bot answers in
    "discord_bot_users": [],       # Discord user IDs that may start/stop besides "Manage Server" people
    "backup_on": True,             # nightly backup of every server's settings (keeps the last 7)
    "backup_at": "03:30",
    "backup_mods": False,          # ...including the mods (can be big)
    "backup_copy": "",             # also keep a copy: "" (no), "folder" (a USB drive or folder), "computer" (a paired one)
    "backup_copy_path": "",
    "backup_copy_ip": "",
    "duckdns_domain": "",          # name.duckdns.org - a fixed address even when the home IP changes
    "upload_mbit": 0,              # the user's upload speed from a speed test (0 = unknown)
    "discord_status_msg": False,   # a status message in the webhook channel that updates itself every minute
    "discord_bridge": False,       # game chat <-> Discord channel (the webhook's channel)
    "discord_bridge_server": "main",
    "ntfy_enabled": False,         # push notifications to phones through the free ntfy app
    "ntfy_server": "https://ntfy.sh",
    "mod_update_check": True,      # look for newer versions of repository mods once a day
    "mod_auto_update": False,      # ...and install them by themselves while nobody is playing
    "sleep_on": False,             # the computer goes to sleep when nobody has played for sleep_idle minutes
    "sleep_idle": 30,
    "sleep_from": "",              # ...only between these times (HH:MM, empty = any time)
    "sleep_to": "",
    "sleep_wake_at": "",           # wake up by itself every day at this time (HH:MM, empty = no)
    "sleep_wake_events": True,     # ...and 10 minutes before every scheduled event
    "telegram_enabled": False,     # alerts to a Telegram chat through your own bot (token = secret TELEGRAM_TOKEN)
    "telegram_chat": "",
    "webhook_enabled": False,      # alerts to any web address (Slack, Mattermost, Rocket.Chat, Teams workflows, Home Assistant ...)
    "statuspage_on": False,        # public page /status: is the server up, players, uptime - no login
    "statuspage_players": False,   # ...also show the names of online players
    "statuspage_title": "",
    "gdrive_on": False,            # a copy of the nightly backups in the owner's Google Drive (secret GDRIVE_REFRESH)
    "gdrive_client_id": "",        # an own Google app instead of the built-in one (its secret: GDRIVE_SECRET)
    "gdrive_folder": "",
    "gdrive_account": "",
    "statuspage_about": "",
    "statuspage_discord": "",
    "statuspage_mods": True,       # ...and the mod list with the download size
    "statuspage_address": False,   # ...and the address to join with (the relay's when "Hide my IP" is on)
    "event_ads": False,            # advertise events: Discord/Telegram/webhook post when planned + a day before, in-game reminders
    "upnp_on": False,              # ask the router (UPnP) to forward the game ports - no router settings page needed
    "upnp_mapped": [],             # [port, "TCP"/"UDP"] pairs this dashboard opened, so old ones can be closed again
    "upnp_mode": "needed",         # "needed" = only while players are on, after an invite or /join; "always" = keep the port open
    "upnp_open_until": 0,          # "needed" mode: keep the port open until this time
    "invite_note": "",             # an extra line for the "Copy invite" message (rules, Discord link ...)
    "credit_link": True,           # "Hosted with BeamMP EasyServer" on the status page and at the end of the invite
    "supporter": {},               # the supporter licence (key itself is a secret): instance, plan, last check
    "early_access": True,          # supporters: Experimental versions (newest features first, pre-releases) - supporters only
    "rolling": False,              # free mode (PAID_FEATURES off): hear about the Rolling release (newest code) too
}
SECURITY_FILE = os.path.join(DATA_DIR, "security.json")
GUARD_FILE = os.path.join(DATA_DIR, "guard.json")                 # what the guard knows (blocked, good players)
GUARD_BLOCK_FILE = os.path.join(DATA_DIR, "guard-block.txt")      # Windows: read by the firewall task
GUARD_STATUS_FILE = os.path.join(os.environ.get("ProgramData") or "C:\\ProgramData", "BeamMP-EasyServer",
                                 "guard-status.txt")              # Windows: the firewall task notes when it ran
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
        self.MSG_FILE = os.path.join(self.STATS_DIR, "messages.txt")
        self.BRIDGE_FILE = os.path.join(self.STATS_DIR, "bridge.txt")
        self.MAINT_FILE = os.path.join(self.STATS_DIR, "maintenance.txt")
        self.TOOLS_FILE = os.path.join(self.STATS_DIR, "tools.txt")
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
             "wb": os.O_WRONLY | os.O_CREAT | os.O_TRUNC, "a": os.O_WRONLY | os.O_CREAT | os.O_APPEND}[mode]
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

    def update_one(self, k, v):
        self.update({k: v})

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
    """Maps players can play: from enabled mods, and from map mods parked by light mode (they come back with their map)."""
    found = set()
    try:
        for n in os.listdir(I().CLIENT_DIR):
            if n.lower().endswith(".zip"):
                found.update(zip_maps(os.path.join(I().CLIENT_DIR, n)) or [])
    except OSError:
        pass
    for n in parked_maps(I()):
        found.update(zip_maps(os.path.join(I().DISABLED_DIR, n)) or [])
    return sorted(found)


# ----------------------------------------------------------------------------- light mode: only the map being played
def parked_maps(inst):
    v = inst.meta.get("parked_maps")
    return [n for n in v if isinstance(n, str)] if isinstance(v, list) and inst.meta.get("light_maps") else []


def light_sync(inst, cur=None):
    """With light mode on, only the map mod of the map being played is sent to players. The other map mods
    wait in Client-disabled (marked as parked) and come back when their map is picked. Returns what moved."""
    if not inst.meta.get("light_maps"):
        return []
    cur = cur or current_map()
    parked = list(inst.meta.get("parked_maps") or [])
    moved = []
    try:
        names = sorted(os.listdir(inst.CLIENT_DIR))
    except OSError:
        names = []
    for n in names:
        if not n.lower().endswith(".zip") or n == TOOLS_MOD:
            continue
        maps = zip_maps(os.path.join(inst.CLIENT_DIR, n)) or []
        if maps and cur not in maps and set_mod_enabled(n, False):
            parked.append(n)
            moved.append("-" + n)
    keep = []
    for n in parked:
        pth = os.path.join(inst.DISABLED_DIR, n)
        if not os.path.exists(pth):
            continue
        if cur in (zip_maps(pth) or []):
            if set_mod_enabled(n, True):
                moved.append("+" + n)
                continue
        if n not in keep:
            keep.append(n)
    if keep != inst.meta.get("parked_maps"):
        set_server_meta(inst.id, parked_maps=keep)
    return moved


def light_off(inst):
    back = [n for n in (inst.meta.get("parked_maps") or []) if set_mod_enabled(n, True)]
    set_server_meta(inst.id, parked_maps=None, light_maps=None)
    return back


# ----------------------------------------------------------------------------- map history (for per-map statistics)
def _maplog_path(inst):
    return os.path.join(DATA_DIR, "maps-%s.json" % inst.id)


def map_timeline(inst):
    v = read_json(_maplog_path(inst), [])
    return [x for x in v if isinstance(x, list) and len(x) == 2] if isinstance(v, list) else []


def record_map(inst, name, t=None):
    if not name:
        return
    tl = map_timeline(inst)
    if tl and tl[-1][1] == name:
        return
    tl.append([t or now(), name])
    write_json(_maplog_path(inst), tl[-2000:])


def per_map_stats(inst, days=30):
    t_now = now()
    since = t_now - days * 86400
    tl = map_timeline(inst)
    if not tl:
        return {"since": None, "maps": []}
    spans = []
    for i, (t0, m) in enumerate(tl):
        t1 = tl[i + 1][0] if i + 1 < len(tl) else t_now
        a, b = max(t0, since), min(t1, t_now)
        if b > a:
            spans.append((a, b, m))
    sessions, samples = event_sessions(read_events(since), t_now)
    out = {}
    for a, b, m in spans:
        d = out.setdefault(m, {"map": m, "map_hours": 0.0, "player_hours": 0.0, "sessions": 0, "players": set(), "peak": 0,
                               "avg_sum": 0, "avg_n": 0, "last": 0})
        d["map_hours"] += (b - a) / 3600.0
        d["last"] = max(d["last"], b)
        for n, sa, sb in sessions:
            ov = min(sb, b) - max(sa, a)
            if ov > 0:
                d["player_hours"] += ov / 3600.0
                d["players"].add(n)
                if a <= sa < b:
                    d["sessions"] += 1
        for t, n in samples:
            if a <= t < b:
                d["peak"] = max(d["peak"], n)
                d["avg_sum"] += n
                d["avg_n"] += 1
    rows = []
    for d in out.values():
        rows.append({"map": d["map"], "map_hours": round(d["map_hours"], 1), "player_hours": round(d["player_hours"], 1),
                     "sessions": d["sessions"], "players": len(d["players"]), "peak": d["peak"],
                     "avg_players": round(d["avg_sum"] / d["avg_n"], 2) if d["avg_n"] else 0,
                     "avg_session_min": round(d["player_hours"] * 60 / d["sessions"]) if d["sessions"] else 0,
                     "per_hour": round(d["player_hours"] / d["map_hours"], 2) if d["map_hours"] else 0, "last": d["last"]})
    rows.sort(key=lambda r: -r["player_hours"])
    return {"since": max(tl[0][0], since), "maps": rows, "current": tl[-1][1]}


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
    # Windows reserves these names even with an extension - writing "CON.zip" would hang or fail
    if re.fullmatch(r"(?i)(con|prn|aux|nul|com\d|lpt\d)(\..*)?", name.split(".")[0] + ".zip"):
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
    try:
        needs = mod_needs()
    except Exception:
        needs = {}
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
                            "parked": not enabled and n in parked_maps(I()), "builtin": n == TOOLS_MOD,
                            "maps": zip_maps(p) or [], "safety": r["verdict"] if r else "unchecked",
                            "reasons": r["reasons"] if r else [], "needs": needs.get(n, []) if enabled else []})
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
        if (self.s.get("ntfy_enabled") or everywhere) and self.sec.has("NTFY_TOPIC"):
            try:
                ntfy_send(item["title"], item["message"], item["level"], dashboard_url(item.get("server")))
                item["delivery"].append("phone")
            except Exception as e:
                sys.stderr.write("ntfy: %s\n" % short_err(e))
        if (self.s.get("discord_enabled") or everywhere) and self.sec.has("DISCORD_WEBHOOK"):
            try:
                self.send_discord(item["title"], item["message"], item["level"], footer=item.get("server_name"))
                notes.append("Discord")
            except Exception as e:
                notes.append("Discord failed: %s" % short_err(e))
        if (self.s.get("telegram_enabled") or everywhere) and self.sec.has("TELEGRAM_TOKEN") and self.s.get("telegram_chat"):
            try:
                telegram_send("%s\n%s" % (item["title"], item["message"]), level=item["level"])
                notes.append("Telegram")
            except Exception as e:
                notes.append("Telegram failed: %s" % short_err(e))
        if (self.s.get("webhook_enabled") or everywhere) and self.sec.has("CUSTOM_WEBHOOK"):
            try:
                custom_webhook_send(item["title"], item["message"], item["level"], item.get("kind"), item.get("server_name"))
                notes.append("webhook")
            except Exception as e:
                notes.append("webhook failed: %s" % short_err(e))
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


# ----------------------------------------------------------------------------- lap times
# The plugin times laps on tracks admins make in the game (/track) and keeps each player's
# best lap. Here: switch it on and off, rename/delete tracks, clear times, and show them.
LAP_RADII = (8, 10, 15, 20, 30)
TRACK_RE = re.compile(r"^([\w\-]+)\t([^\t]+)\t([^\t]*)\t(\w+)\t([\d.,;\-]+)$")


def laps_file(name):
    return os.path.join(I().STATS_DIR, name)


def read_laps_cfg():
    d = {"on": False, "radius": 15, "public": True}
    for line in shared_read(laps_file("laps.txt"), 4096).splitlines():
        k, _, v = line.partition("=")
        v = v.strip()
        if k == "mode":
            d["on"] = v == "on"
        elif k == "radius" and v.isdigit():
            d["radius"] = int(v) if int(v) in LAP_RADII else 15
        elif k == "public":
            d["public"] = v != "off"
    return d


def write_laps_cfg(d):
    shared_write(laps_file("laps.txt"), "mode=%s\nradius=%d\npublic=%s\n" % (
        "on" if d["on"] else "off", d["radius"], "on" if d["public"] else "off"))


def read_track_lines():
    return [l for l in shared_read(laps_file("tracks.tsv"), 512 * 1024).splitlines() if TRACK_RE.match(l)]


def read_tracks():
    out = []
    for line in read_track_lines():
        tid, name, mp, kind, pts = TRACK_RE.match(line).groups()
        out.append({"id": tid, "name": name[:40], "map": map_name(mp) if mp else "", "kind": "sprint" if kind == "sprint" else "loop",
                    "checkpoints": max(0, pts.count(";") - (1 if kind == "sprint" else 0))})
    return out


def read_laptimes():
    """{track id: [{"name", "ms", "car", "t"}] fastest first}"""
    out = {}
    for line in shared_read(laps_file("laptimes.tsv"), 2 * 1024 * 1024).splitlines():
        p = line.split("\t")
        if len(p) == 5 and p[2].isdigit() and p[4].isdigit():
            out.setdefault(p[0], []).append({"name": p[1][:64], "ms": int(p[2]), "car": p[3][:40], "t": int(p[4])})
    for rows in out.values():
        rows.sort(key=lambda r: r["ms"])
    return out


def write_laptimes(times):
    clean = lambda x: re.sub(r"[\t\r\n]", " ", str(x))
    shared_write(laps_file("laptimes.tsv"), "".join("%s\t%s\t%d\t%s\t%d\n" % (tid, clean(r["name"]), r["ms"], clean(r["car"]), r["t"])
                                                   for tid, rows in times.items() for r in rows))


def fmt_lap(ms):
    m, s = divmod(ms, 60000)
    return ("%d:%06.3f" % (m, s / 1000.0)) if m else ("%.3f" % (s / 1000.0))


def laps_summary(limit=10, only_map=None):
    times = read_laptimes()
    out = []
    for t in read_tracks():
        if only_map is not None and t["map"] and t["map"] != only_map:
            continue
        rows = times.get(t["id"], [])
        t.update({"drivers": len(rows), "top": [dict(r, time=fmt_lap(r["ms"])) for r in rows[:limit]]})
        out.append(t)
    return out


# ----------------------------------------------------------------------------- Raspberry Pi on the same network
# Install EasyServer on a Raspberry Pi from here: no screen, keyboard or commands on the Pi. The owner makes
# the SD card with Raspberry Pi Imager (Wi-Fi, a user name and password, "Enable SSH") and plugs the Pi in.
# This dashboard finds it on the home network by its network chip's maker code, logs in once with the
# password the owner types (handed to ssh through SSH_ASKPASS - never on a command line, never saved),
# leaves its own key there, copies the Linux installer over and runs it. Updates later use the key.
PI_OUIS = ("b8:27:eb", "dc:a6:32", "e4:5f:01", "28:cd:c1", "d8:3a:dd", "2c:cf:67", "88:a2:9e")
PI_DIR = os.path.join(DATA_DIR, "pi")
PI_INSTALLER = "https://raw.githubusercontent.com/%s/main/linux/install.sh" % REPO
PI_USER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_. -]{0,31}")
PI_PORT = 30815
_PI_LOCK = threading.Lock()
_PI = {"scan": None, "scanning": False, "job": None}
_NOWIN = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if IS_WIN else {}


def pi_private(ip):
    try:
        a = ipaddress.ip_address(str(ip))
    except ValueError:
        return False
    return a.version == 4 and a.is_private and not (a.is_loopback or a.is_link_local or a.is_unspecified)


def pi_lan_ip():
    """This computer's address on the home network (no packet is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.254.254.254", 1))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


def pi_mac(m):
    parts = re.split(r"[:-]", m.strip().lower())
    return ":".join(x.zfill(2) for x in parts) if len(parts) == 6 and all(re.fullmatch(r"[0-9a-f]{1,2}", x) for x in parts) else ""


def pi_neighbors():
    """{ip: mac} from this computer's ARP table: the devices it talked to on the network lately."""
    try:
        if IS_WIN:
            txt = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10, **_NOWIN).stdout
        elif os.path.exists("/proc/net/arp"):
            with open("/proc/net/arp") as f:
                txt = f.read()
        else:
            txt = subprocess.run(["arp", "-an"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    out = {}
    for ip, mac in re.findall(r"\(?(\d{1,3}(?:\.\d{1,3}){3})\)?(?:\s+at)?\s+(?:0x\S+\s+0x\S+\s+)?([0-9A-Fa-f]{1,2}(?:[:-][0-9A-Fa-f]{1,2}){5})", txt):
        m = pi_mac(mac)
        if m and m not in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"):
            out[ip] = m
    return out


def pi_open(ip, port, timeout=0.7):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def pi_is_pi(mac):
    return bool(mac) and mac[:8] in PI_OUIS


def pi_banner(ip):
    """The SSH greeting ("SSH-2.0-OpenSSH_9.2p1 Debian-2+deb12u3"): "" when nothing answers on port 22,
    "?" when something does but says nothing."""
    try:
        with socket.create_connection((ip, 22), timeout=0.7) as c:
            c.settimeout(1.5)
            try:
                return c.recv(256).decode("latin-1").split("\n")[0].strip()[:120] or "?"
            except OSError:
                return "?"
    except OSError:
        return ""


def pi_os_from_banner(b):
    b = (b or "").lower()
    for key in ("windows", "raspbian", "ubuntu", "debian"):
        if key in b:
            return key
    return ""


def pi_problem(pi):
    """Why EasyServer can't go on this computer ("" = it can)."""
    if pi.get("os") == "windows":
        return "" if pi.get("admin", True) else ("This Windows account isn't an administrator. Forget it and set it up again "
                                                  "with an administrator account of that PC.")
    if pi.get("truenas"):
        return "TrueNAS doesn't allow installing programs on it, so EasyServer can't go there."
    oses = set(str(pi.get("os_like", "")).split(",")) | {str(pi.get("os", ""))}
    if pi.get("os") and not oses & {"debian", "ubuntu", "raspbian"}:
        return "EasyServer needs Ubuntu, Debian or Raspberry Pi OS - this computer runs %s." % pi.get("os")
    if pi.get("bits") == 32:
        return ("This Raspberry Pi runs the 32-bit Raspberry Pi OS. The BeamMP server needs the 64-bit one - write that to the card "
                "and set it up again.") if pi.get("kind") == "pi" else \
            "This computer runs a 32-bit system. The BeamMP server needs a 64-bit one."
    if pi.get("arch") and pi["arch"] not in ("x86_64", "aarch64", "amd64", "arm64"):
        return "The BeamMP server doesn't run on this kind of processor (%s)." % pi["arch"]
    return ""


def pi_ps(script):
    """A PowerShell script as one command for Windows' SSH (which starts cmd.exe)."""
    return "powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand " + \
        base64.b64encode(script.encode("utf-16-le")).decode()


def pi_saved():
    d = read_json(os.path.join(PI_DIR, "pis.json"), [])
    return [x for x in d if isinstance(x, dict) and pi_private(x.get("ip")) and PI_USER_RE.fullmatch(str(x.get("user", "")))] \
        if isinstance(d, list) else []


def pi_store(pis):
    os.makedirs(PI_DIR, exist_ok=True)
    write_json(os.path.join(PI_DIR, "pis.json"), pis[:20])


def pi_remember(ip, **kw):
    with _PI_LOCK:
        pis = pi_saved()
        me = next((x for x in pis if x["ip"] == ip), None)
        if me is None:
            me = {"ip": ip, "added": now()}
            pis.append(me)
        me.update(kw)
        pi_store(pis)
        return dict(me)


def pi_scan():
    """Look for Raspberry Pis on this computer's network (one /24): who answers, and whose network chip is a Pi's."""
    me = pi_lan_ip()
    if not pi_private(me):
        return {"t": now(), "found": [], "me": me,
                "error": "This computer doesn't seem to be on a home network, so there's nothing to look through."}
    base = me.rsplit(".", 1)[0]
    ips = ["%s.%d" % (base, i) for i in range(1, 255) if "%s.%d" % (base, i) != me]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(64) as ex:
        ban = dict(zip(ips, ex.map(pi_banner, ips)))                    # also fills the ARP table
        named = ex.submit(lambda: socket.gethostbyname("raspberrypi.local"))
        try:
            named_ip = named.result(timeout=4)
        except Exception:
            named_ip = ""
    macs = pi_neighbors()
    saved = pi_saved()
    for x in saved:                     # a known Pi that got a new address from the router
        if x.get("mac") and x["mac"] not in (macs.get(x["ip"]), None):
            moved = next((ip for ip, m in macs.items() if m == x["mac"] and ip.startswith(base + ".")), None)
            if moved:
                pi_remember(x["ip"], ip=moved)
    known = {x["ip"] for x in pi_saved()}
    found = []
    for ip in ips:
        mac, os_ = macs.get(ip, ""), pi_os_from_banner(ban.get(ip))
        is_pi = pi_is_pi(mac) or ip == named_ip or os_ == "raspbian"
        if is_pi or os_ or ip in known:
            found.append({"ip": ip, "mac": mac, "pi": is_pi, "os": os_, "ssh": bool(ban.get(ip)),
                          "kind": "pi" if is_pi else ("windows" if os_ == "windows" else "pc"),
                          "easyserver": pi_open(ip, PI_PORT), "known": ip in known})
    with ThreadPoolExecutor(16) as ex:      # its name on the network, when the router or the computer says it
        names = {f["ip"]: ex.submit(pi_hostname, f["ip"]) for f in found}
        for f in found:
            try:
                f["name"] = names[f["ip"]].result(timeout=3)
            except Exception:
                f["name"] = ""
    return {"t": now(), "me": me, "found": found, "error": ""}


def pi_hostname(ip):
    try:
        n = socket.gethostbyaddr(ip)[0].split(".")[0]
    except (OSError, UnicodeError):
        return ""
    return n[:40] if re.fullmatch(r"[\w-]+", n) and n != ip.split(".")[0] else ""


def pi_ssh_exe(name="ssh"):
    if IS_WIN:
        p = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "OpenSSH", name + ".exe")
        if os.path.exists(p):
            return p
    return shutil.which(name)


def pi_key():
    """This dashboard's own SSH key, made once: (private key path, public key line)."""
    k = os.path.join(PI_DIR, "id_ed25519")
    if not os.path.exists(k):
        kg = pi_ssh_exe("ssh-keygen")
        if not kg:
            raise RuntimeError("This computer has no SSH tools. On Windows: Settings → System → Optional features → OpenSSH Client.")
        os.makedirs(PI_DIR, exist_ok=True)
        subprocess.run([kg, "-q", "-t", "ed25519", "-N", "", "-C", "beammp-easyserver", "-f", k],
                       check=True, capture_output=True, timeout=30, **_NOWIN)
        if not IS_WIN:                  # (on Windows ssh-keygen itself locks the file to this account)
            os.chmod(k, 0o600)
    with open(k + ".pub") as f:
        return k, f.read().strip()


def pi_quote(x):
    return "'" + str(x).replace("'", "'\"'\"'") + "'"


def pi_ssh(pi, cmd, password=None, stdin_data=None, timeout=60, on_line=None):
    """Run a command on the Pi. With password (the first login only) ssh gets it through SSH_ASKPASS; otherwise
    this dashboard's key. Returns (exit code, output); 255 = ssh itself failed."""
    exe = pi_ssh_exe()
    if not exe:
        raise RuntimeError("This computer has no SSH client. On Windows: Settings → System → Optional features → OpenSSH Client.")
    key, _ = pi_key()
    args = [exe, "-T", "-o", "StrictHostKeyChecking=accept-new", "-o", 'UserKnownHostsFile="%s"' % os.path.join(PI_DIR, "known_hosts"),
            "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4", "-o", "LogLevel=ERROR"]
    env, tmp = dict(os.environ), None
    if password is not None:
        tmp = tempfile.mkdtemp(prefix="es-ask-")
        if IS_WIN:
            ask = os.path.join(tmp, "askpass.cmd")
            with open(ask, "w") as f:
                f.write('@powershell.exe -NoProfile -NonInteractive -Command "[Console]::Out.Write($env:ES_SSH_PW)"\r\n')
        else:
            ask = os.path.join(tmp, "askpass.sh")
            with open(ask, "w") as f:
                f.write('#!/bin/sh\nprintf \'%s\\n\' "$ES_SSH_PW"\n')
            os.chmod(ask, 0o700)
        env.update(ES_SSH_PW=password, SSH_ASKPASS=ask, SSH_ASKPASS_REQUIRE="force", DISPLAY=env.get("DISPLAY") or ":0")
        args += ["-o", "PubkeyAuthentication=no", "-o", "PreferredAuthentications=password,keyboard-interactive",
                 "-o", "NumberOfPasswordPrompts=1"]
    else:
        args += ["-i", key, "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes"]
    args += ["%s@%s" % (pi["user"], pi["ip"]), cmd]
    out = []
    try:
        proc = subprocess.Popen(args, env=env, stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **_NOWIN)
        timer = threading.Timer(timeout, proc.kill)
        timer.start()
        try:
            if stdin_data is not None:
                def feed():
                    try:
                        if hasattr(stdin_data, "read"):         # a file: sent in pieces
                            shutil.copyfileobj(stdin_data, proc.stdin, 1024 * 1024)
                        else:
                            proc.stdin.write(stdin_data if isinstance(stdin_data, bytes) else stdin_data.encode("utf-8"))
                        proc.stdin.close()
                    except (OSError, ValueError):
                        pass
                threading.Thread(target=feed, daemon=True, name="ssh-in").start()
            for raw_line in proc.stdout:
                line = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\r", "", raw_line.decode("utf-8", "replace")).rstrip("\n")
                out.append(line)
                if on_line:
                    on_line(line)
            code = proc.wait()
        finally:
            timer.cancel()
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    return code, "\n".join(out)


def pi_ssh_error(out):
    o = out.lower()
    if "permission denied" in o:
        return "It said no - check the user name and password (on a Raspberry Pi: the ones you set in Raspberry Pi Imager)."
    if "connection refused" in o:
        return "SSH is turned off on that computer, so it can't be set up from here - the steps under it say how to turn it on."
    if "host key verification failed" in o or "remote host identification has changed" in o:
        return "This isn't the computer set up here before (its identity changed). If you reinstalled it or put a new card in it, press Forget and set it up again."
    if "timed out" in o or "no route" in o or "unreachable" in o:
        return "Couldn't reach it - is it switched on and on the same network?"
    return "Couldn't connect: " + (out.strip().splitlines() or ["unknown error"])[-1][:200]


PI_PAIR_WIN = r"""$ErrorActionPreference = 'Stop'
$k = '%s'
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($admin) {
    $f = Join-Path $env:ProgramData 'ssh\administrators_authorized_keys'
    if (-not ((Test-Path $f) -and ((Get-Content $f) -contains $k))) { Add-Content -Path $f -Value $k -Encoding ascii }
    icacls.exe $f /inheritance:r /grant '*S-1-5-32-544:F' /grant '*S-1-5-18:F' | Out-Null
}
'ES_BITS=' + $(if ([Environment]::Is64BitOperatingSystem) { 64 } else { 32 })
'ES_HOST=' + $env:COMPUTERNAME
'ES_ADMIN=' + [int]$admin
"""


def pi_pair(ip, user, password):
    """Log in once with the password, leave this dashboard's key there, and learn what the computer is."""
    _, pub = pi_key()
    pi = {"ip": ip, "user": user}
    win = pi_os_from_banner(pi_banner(ip)) == "windows"
    if win:
        cmd = pi_ps(PI_PAIR_WIN % pub.replace("'", ""))
    else:
        cmd = ("umask 077; mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys && "
               "(grep -qxF %s ~/.ssh/authorized_keys || echo %s >> ~/.ssh/authorized_keys) && "
               "echo ES_BITS=$(getconf LONG_BIT) ES_HOST=$(hostname) ES_ARCH=$(uname -m) ES_UID=$(id -u); "
               ". /etc/os-release 2>/dev/null; echo \"ES_OS=$ID ES_LIKE=$(echo $ID_LIKE | tr ' ' ',')\"; "
               "echo ES_MODEL=$(tr -d '\\0' </proc/device-tree/model 2>/dev/null | tr ' ' '_'); "
               "[ -e /usr/bin/midclt ] && echo ES_TRUENAS=1; [ -e /usr/sbin/omv-confdbadm ] && echo ES_OMV=1; "
               "sudo -n true 2>/dev/null && echo ES_SUDO=1; true") % (pi_quote(pub), pi_quote(pub))
    code, out = pi_ssh(pi, cmd, password=password, timeout=60)
    if code == 255 or "ES_BITS=" not in out:
        raise RuntimeError(pi_ssh_error(out))
    code2, out2 = pi_ssh(pi, "echo ES_KEY_OK", timeout=30)
    if "ES_KEY_OK" not in out2 and not win:
        raise RuntimeError("Logged in, but the computer didn't accept this dashboard's key: " + pi_ssh_error(out2))

    def val(k, pat=r"[\w.,-]{1,63}"):
        m = re.search(r"\b%s=(%s)" % (k, pat), out)
        return m.group(1) if m else ""
    bits = val("ES_BITS", r"\d+")
    info = {"user": user, "mac": pi_neighbors().get(ip, ""), "bits": int(bits) if bits else 0, "host": val("ES_HOST")}
    if win:
        admin = val("ES_ADMIN") == "1"
        # Windows only lets an admin's key in through administrators_authorized_keys, so it may still say no to
        # the key; then updates ask for the password again.
        info.update(os="windows", os_like="", arch="", kind="windows", admin=admin, sudo="ES_KEY_OK" in out2, root=False,
                    truenas=False, omv=False, model="")
    else:
        model = val("ES_MODEL", r"[\w.,-]{1,80}").replace("_", " ")
        info.update(os=val("ES_OS"), os_like=val("ES_LIKE"), arch=val("ES_ARCH"), root=val("ES_UID") == "0",
                    sudo="ES_SUDO=1" in out or val("ES_UID") == "0", truenas="ES_TRUENAS=1" in out, omv="ES_OMV=1" in out,
                    model=model, kind="pi" if "Raspberry" in model or val("ES_OS") == "raspbian" else
                    ("nas" if "ES_OMV=1" in out or "ES_TRUENAS=1" in out else "pc"))
    return pi_remember(ip, **info)


def pi_job(kind, pi, name="", sudo_pw=None):
    """Install or update EasyServer on the computer (in the background). Linux: download the installer here, copy it over,
    run it. Windows: it downloads EasyServer itself and runs install.ps1 without the setup window."""
    job = {"kind": kind, "ip": pi["ip"], "state": "running", "t": now(), "lines": [], "password": "", "error": "", "web": ""}

    def add(line):
        m = re.match(r"\s*Password:\s+(\S+)", line)
        if m:
            job["password"] = m.group(1)[:64]
            line = line[:m.start(1)] + "(shown above)"
        job["lines"].append(line[:300])
        del job["lines"][:-300]

    def run():
        try:
            if pi.get("os") == "windows":
                return run_windows()
            add("Downloading the installer…")
            req = urllib.request.Request(PI_INSTALLER, headers={"User-Agent": "BeamMP-EasyServer/%s (Raspberry Pi setup)" % EASY_VERSION})
            with urllib.request.urlopen(req, timeout=30) as r:
                script = r.read(2 * 1024 * 1024)
            if not script.startswith(b"#!") or b"BeamMP EasyServer" not in script:
                raise RuntimeError("The installer that came from GitHub doesn't look right - try again later.")
            add("Copying it to the computer at %s…" % pi["ip"])
            code, out = pi_ssh(pi, "umask 077; cat > ~/.easyserver-install.sh && echo ES_COPIED", stdin_data=script, timeout=60)
            if "ES_COPIED" not in out:
                raise RuntimeError(pi_ssh_error(out))
            args = ["--unattended", "--mod-page", "yes", "--laptop-mode", "no"]
            if kind == "install" and name:
                args += ["--name", name]
            sudo = "" if pi.get("root") else ("sudo -n " if pi.get("sudo") else "sudo -S -p '' ")
            add("Running it - this takes 5 to 15 minutes on a Raspberry Pi, less on a PC…")
            code, out = pi_ssh(pi, "%sbash ~/.easyserver-install.sh %s; c=$?; rm -f ~/.easyserver-install.sh; exit $c"
                               % (sudo, " ".join(pi_quote(a) for a in args)),
                               stdin_data=None if (pi.get("sudo") or pi.get("root")) else (sudo_pw or "") + "\n",
                               timeout=2400, on_line=add)
            finish(code, out)
        except Exception as e:
            job.update(state="failed", error=str(e) if isinstance(e, RuntimeError) else short_err(e))
        finally:
            job["ended"] = now()

    def finish(code, out):
        if code == 255:
            raise RuntimeError(pi_ssh_error(out))
        if code != 0:
            raise RuntimeError("The installer stopped with an error - the last lines above say why.")
        ver = re.search(r"BeamMP EasyServer v([\d.]+)", out)
        web = pi_web(pi["ip"])
        pi_remember(pi["ip"], version=ver.group(1) if ver else "", updated=now(), web=web)
        job.update(state="done", web=web)

    def run_windows():
        """Windows downloads EasyServer itself and runs its installer without the setup window. The first install logs
        in with the password: only then can Windows lock away the keys EasyServer saves (it ties them to the login)."""
        add("Windows PC at %s: downloading EasyServer there and running its installer…" % pi["ip"])
        args = "-Unattended" + (" -Update" if kind == "update" else "")
        if kind == "install" and name:
            args += " -ServerName '%s'" % name.replace("'", "''")
        code, out = pi_ssh(pi, pi_ps(PI_WIN_RUN % (ROLLING_ZIP % REPO, args)), password=sudo_pw,
                           timeout=2400, on_line=add)
        finish(code, out)

    _PI["job"] = job
    threading.Thread(target=run, daemon=True, name="pi-" + kind).start()
    return job


PI_WIN_RUN = r"""$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$d = Join-Path $env:TEMP 'easyserver-setup'
Remove-Item -Recurse -Force $d -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $d | Out-Null
Invoke-WebRequest -Uri '%s' -OutFile (Join-Path $d 'es.zip') -UseBasicParsing
Expand-Archive -Path (Join-Path $d 'es.zip') -DestinationPath $d -Force
$src = Get-ChildItem $d -Directory | Select-Object -First 1
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $src.FullName 'windows\install.ps1') %s
$c = $LASTEXITCODE
Remove-Item -Recurse -Force $d -ErrorAction SilentlyContinue
exit $c
"""


def pi_web(ip):
    """The Pi's dashboard address (it uses https once it has made its certificate)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    try:
        with socket.create_connection((ip, PI_PORT), timeout=3) as raw_sock:
            with ctx.wrap_socket(raw_sock):
                return "https://%s:%d/" % (ip, PI_PORT)
    except (OSError, ssl.SSLError):
        return "http://%s:%d/" % (ip, PI_PORT)


def pi_here():
    """This computer's Wi-Fi name and country, to start the SD card form with (never its Wi-Fi password)."""
    if not IS_WIN:
        return {"wifi": "", "country": ""}
    if "here" not in _PI or time.time() - _PI["here"][0] > 300:
        wifi, country = "", ""
        try:
            out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, timeout=10, **_NOWIN).stdout
            m = re.search(rb"^\s*SSID\s*:\s*(.+?)\s*$", out, re.M)
            wifi = m.group(1).decode("utf-8", "replace")[:32] if m else ""
        except (OSError, subprocess.SubprocessError):
            pass
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                  "[Globalization.RegionInfo]::CurrentRegion.TwoLetterISORegionName"],
                                 capture_output=True, text=True, timeout=20, **_NOWIN).stdout.strip().upper()
            country = out if PI_COUNTRY_RE.fullmatch(out) else ""
        except (OSError, subprocess.SubprocessError):
            pass
        _PI["here"] = (time.time(), wifi, country)
    return {"wifi": _PI["here"][1], "country": _PI["here"][2]}


def pi_status():
    pis = pi_saved()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as ex:
        up = list(ex.map(lambda x: pi_open(x["ip"], PI_PORT, 1.5), pis))
    for x, u in zip(pis, up):
        x["online"] = u
        x["problem"] = pi_problem(x)
    return pis


# ---- paired computers talk through files --------------------------------------------------------------------
# A paired computer (reached over SSH with this dashboard's key) gets files in its dashboard's data folder:
# remote/in/c-<id>.json is a command (start, stop, restart, move-in) and remote/in/move-<id>.zip a server moved
# to it. Its dashboard does them within 10 seconds and keeps remote/status.json up to date, which is read back.
# On Linux the files are written as the dashboard's own user, so the game server can't put commands there.
REMOTE_DIR = os.path.join(DATA_DIR, "remote")
REMOTE_IN = os.path.join(REMOTE_DIR, "in")
REMOTE_LINUX = "/opt/beammp-server/.easyserver/remote"
REMOTE_CMD_RE = re.compile(r"c-[0-9a-f]{8,32}\.json")
REMOTE_ZIP_RE = re.compile(r"move-[0-9a-f]{8,32}\.zip")
REMOTE_STALE = 600                   # status.json is rewritten at least every 5 minutes

PI_WIN_REMOTE = r"""$ErrorActionPreference = 'Stop'
$t = Get-ScheduledTask -TaskName 'BeamMP Dashboard (EasyServer)'
$py = ($t.Actions | Select-Object -First 1).Arguments.Trim().Trim('"')
$r = Join-Path (Split-Path (Split-Path $py)) 'data\remote'
"""
PI_WIN_STATUS = "[Console]::Out.Write([IO.File]::ReadAllText((Join-Path $r 'status.json')))\n"
PI_WIN_PUT = r"""$in = Join-Path $r 'in'
New-Item -ItemType Directory -Force $in | Out-Null
$tmp = Join-Path $in '.%(n)s'
$f = [IO.File]::Create($tmp)
try { [Console]::OpenStandardInput().CopyTo($f) } finally { $f.Close() }
Move-Item -Force $tmp (Join-Path $in '%(n)s')
'ES_PUT_OK'
"""


def pi_key_ok(pi):
    """Can this dashboard log in to it with its key alone? (Windows only lets an admin's key in.)"""
    return pi.get("os") != "windows" or bool(pi.get("sudo"))


def pi_can_remote(pi):
    """Can its status be read and commands be sent? It needs EasyServer, the key, and (Linux) sudo without a password."""
    return bool(pi.get("version")) and pi_key_ok(pi) and (pi.get("os") == "windows" or pi.get("root") or pi.get("sudo"))


def pi_remote(pi, op, name="", data=None, timeout=60):
    """op "status": read its remote/status.json. op "put": data (bytes or a file) becomes remote/in/<name>."""
    if op == "put" and not (REMOTE_CMD_RE.fullmatch(name) or REMOTE_ZIP_RE.fullmatch(name)):
        raise ValueError("bad name")
    if pi.get("os") == "windows":
        ps = PI_WIN_REMOTE + (PI_WIN_STATUS if op == "status" else PI_WIN_PUT % {"n": name})
        return pi_ssh(pi, pi_ps(ps), stdin_data=data, timeout=timeout)
    as_dash = "runuser -u beammp-dash -- " if pi.get("root") else "sudo -n -u beammp-dash "
    if op == "status":
        cmd = as_dash + "cat %s/status.json" % REMOTE_LINUX
    else:
        cmd = as_dash + "sh -c %s sh %s %s" % (pi_quote('cd /; umask 077; mkdir -p "$1/in" && cat > "$1/in/.$2" && '
                                                        'mv -f "$1/in/.$2" "$1/in/$2" && echo ES_PUT_OK'), REMOTE_LINUX, name)
    return pi_ssh(pi, cmd, stdin_data=data if data is not None else b"", timeout=timeout)


def pi_remote_json(out):
    try:
        d = json.loads(out[out.index("{"):])
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


def pi_remote_send(pi, action, **kw):
    """Send a command; returns its id (the answer shows up in its status.json under "done")."""
    cid = uuid.uuid4().hex
    code, out = pi_remote(pi, "put", "c-%s.json" % cid, json.dumps(dict(kw, id=cid, action=action)).encode(), timeout=40)
    if "ES_PUT_OK" not in out:
        raise RuntimeError(pi_ssh_error(out) if code == 255 else
                           "That computer didn't take it: " + (out.strip().splitlines() or ["no answer"])[-1][:200])
    return cid


def pi_overview():
    """Every paired computer with what its EasyServer says about itself (cached for 10 seconds)."""
    c = _PI.get("overview")
    if c and time.time() - c[0] < 10:
        return c[1]
    pis = pi_status()

    def one(x):
        if not x.get("online"):
            return {"error": "off"}
        if not x.get("version"):
            return {"error": "none"}
        if not pi_can_remote(x):
            return {"error": "nokey"}
        try:
            code, out = pi_remote(x, "status", timeout=25)
        except Exception as e:
            return {"error": "ssh", "detail": short_err(e)}
        if code == 255:
            return {"error": "ssh", "detail": pi_ssh_error(out)}
        d = pi_remote_json(out)
        if d is None:
            return {"error": "nokey" if "password is required" in out else "old"}
        servers = [{"id": str(v.get("id"))[:12], "name": str(v.get("name"))[:80], "state": str(v.get("state"))[:20],
                    "players": int(v.get("players") or 0), "max": int(v.get("max") or 0), "map": str(v.get("map") or "")[:60]}
                   for v in (d.get("servers") or [])[:10] if isinstance(v, dict)]
        return {"servers": servers, "version": str(d.get("version") or "")[:20],
                "stale": now() - int(d.get("t") or 0) > REMOTE_STALE}
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(one, pis))
    for x, r in zip(pis, res):
        x["remote"] = r
    _PI["overview"] = (time.time(), pis)
    return pis


def remote_snapshot():
    """This computer's servers, for status.json and the top of the All computers list."""
    with LOCK:
        insts = list(INSTANCES.values())
    prev = getattr(_TL, "inst", None)
    out = []
    try:
        for inst in insts:
            use_server(inst.id)
            try:
                st = inst.server.status()["state"]
            except Exception:
                st = "unknown"
            o = read_json(os.path.join(inst.STATS_DIR, "online.json"), None)
            fresh = isinstance(o, dict) and now() - int(o.get("t", 0) or 0) < 120
            try:
                mx, mp = APP.max_players(), current_map()
            except Exception:
                mx, mp = 0, ""
            out.append({"id": inst.id, "name": inst.name, "state": st, "players": len(o.get("players") or []) if fresh else 0,
                        "max": mx, "map": mp or ""})
    finally:
        _TL.inst = prev
    return out


def moved_note(inst):
    """'' or where this server was moved to."""
    m = inst.meta.get("moved_to")
    if not isinstance(m, dict):
        return ""
    return "%s was moved to %s (%s)" % (inst.name, m.get("host") or m.get("ip"), m.get("ip"))


class _Capture:
    """Stands in for a web request when a server moved here is put in place (Handler._import_zip answers through it)."""
    _restore_undo = None

    def __init__(self):
        self.result = (500, {"ok": False, "error": "nothing happened"})

    def send(self, code, obj):
        self.result = (code, obj)

    def fail(self, code, msg):
        self.result = (code, {"ok": False, "error": msg})


def pi_move_job(pi, iid, stop_here):
    """Move this server to a paired computer: pack everything up, send it, let that computer put it in place,
    then stop it here."""
    job = {"kind": "move", "ip": pi["ip"], "state": "running", "t": now(), "lines": [], "password": "", "error": "", "web": ""}

    def add(line):
        job["lines"].append(line[:400])

    def run():
        tmp = None
        try:
            use_server(iid)
            add("Packing up this server: its settings, mods, bans, stats, championships and lap times…")
            fd, tmp = tempfile.mkstemp(suffix=".zip", dir=DATA_DIR)
            os.close(fd)
            build_export(tmp, True, include_games=True)
            size = os.path.getsize(tmp)
            mid = uuid.uuid4().hex
            add("Sending it to %s (%d MB)…" % (pi.get("host") or pi["ip"], max(1, size // 10 ** 6)))
            with open(tmp, "rb") as f:
                code, out = pi_remote(pi, "put", "move-%s.zip" % mid, f, timeout=max(900, size // 10 ** 6))
            if "ES_PUT_OK" not in out:
                raise RuntimeError(pi_ssh_error(out) if code == 255 else
                                   "Couldn't put it on that computer: " + (out.strip().splitlines() or ["no answer"])[-1][:200])
            cid = pi_remote_send(pi, "move-in", file="move-%s.zip" % mid, source=server_name())
            add("That computer is putting it in place - it checks every mod for viruses first, so this can take a while…")
            deadline, res = time.time() + 1800, None
            while res is None and time.time() < deadline:
                time.sleep(10)
                try:
                    _, out = pi_remote(pi, "status", timeout=30)
                except Exception:
                    continue
                d = pi_remote_json(out) or {}
                res = next((x for x in d.get("done") or [] if isinstance(x, dict) and x.get("id") == cid), None)
            if res is None:
                raise RuntimeError("That computer didn't finish within 30 minutes. Open its dashboard to see where it got to.")
            if not res.get("ok"):
                raise RuntimeError("That computer said: " + str(res.get("note") or "it didn't work")[:300])
            add(str(res.get("note") or "Done.")[:400])
            if stop_here:
                use_server(iid)
                r = I().server.action("stop")
                set_server_meta(iid, moved_to={"ip": pi["ip"], "host": str(pi.get("host") or "")[:40], "t": now()})
                add("Stopped the server on this computer. It stays off here, even after a restart, until you press Start "
                    "on this computer yourself." if r.get("ok") else
                    "Couldn't stop the server on this computer (%s) - stop it yourself." % (r.get("msg") or "failed"))
            _PI.pop("overview", None)
            job.update(state="done", web=pi.get("web") or pi_web(pi["ip"]))
        except Exception as e:
            job.update(state="failed", error=str(e) if isinstance(e, RuntimeError) else short_err(e))
        finally:
            job["ended"] = now()
            if tmp:
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    _PI["job"] = job
    threading.Thread(target=run, daemon=True, name="pi-move").start()
    return job


# ---- a copy of every backup somewhere else ---------------------------------------------------------------------
BACKUP_COPY_DIR = "BeamMP EasyServer backups"


def backup_tag():
    """This computer's name in the copies' file names, so two computers can copy to the same place."""
    return re.sub(r"[^A-Za-z0-9-]", "", socket.gethostname())[:20].strip("-") or "server"


def backup_drives():
    """Folders worth offering: USB drives and other disks."""
    out = []
    if IS_WIN:
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            mask, sysd = k32.GetLogicalDrives(), (os.environ.get("SystemDrive") or "C:").upper()
            for i in range(26):
                if mask >> i & 1:
                    root = "%s:\\" % chr(65 + i)
                    t = k32.GetDriveTypeW(root)
                    if t == 2 or (t == 3 and root[:2] != sysd):
                        out.append({"path": root, "usb": t == 2})
        except Exception:
            pass
        return out
    for base in ("/media", "/run/media", "/mnt"):
        try:
            for a in sorted(os.listdir(base)):
                p = os.path.join(base, a)
                cands = [p] if os.path.ismount(p) else [os.path.join(p, b) for b in sorted(os.listdir(p))] if os.path.isdir(p) else []
                out += [{"path": c, "usb": base != "/mnt"} for c in cands if os.path.ismount(c)]
        except OSError:
            continue
    return out[:12]


def backup_folder_check(path):
    """'' if backups can be copied into the folder, otherwise why not."""
    if not path or not os.path.isabs(path):
        return "Enter the whole path of the folder, like E:\\ or /media/usb"
    if not os.path.isdir(path):
        return "%s isn't there - is the USB drive plugged in?" % path
    test = os.path.join(path, ".easyserver-test")
    try:
        with open(test, "w") as f:
            f.write("ok")
        os.remove(test)
    except OSError:
        return ("The dashboard isn't allowed to write in %s." % path) + ("" if IS_WIN else
                " On Linux it runs as the user beammp-dash - give it a folder it can write to (sudo chown beammp-dash).")
    return ""


def backup_put_cmd(pi, name, prefix):
    """A command that saves stdin as ~/easyserver-backups/<name> on the computer and keeps the newest 7 <prefix>*."""
    if pi.get("os") == "windows":
        return pi_ps(r"""$ErrorActionPreference = 'Stop'
$d = Join-Path $HOME 'easyserver-backups'
New-Item -ItemType Directory -Force $d | Out-Null
$tmp = Join-Path $d '.%(n)s'
$f = [IO.File]::Create($tmp)
try { [Console]::OpenStandardInput().CopyTo($f) } finally { $f.Close() }
Move-Item -Force $tmp (Join-Path $d '%(n)s')
Get-ChildItem $d -Filter '%(p)s*.zip' | Sort-Object Name -Descending | Select-Object -Skip %(k)d | Remove-Item -Force
'ES_PUT_OK'
""" % {"n": name, "p": prefix, "k": BACKUP_KEEP})
    return ("umask 077; mkdir -p ~/easyserver-backups && cd ~/easyserver-backups && cat > .%(n)s && mv -f .%(n)s %(n)s && "
            "echo ES_PUT_OK && ls -1 -- %(p)s*.zip | sort -r | tail -n +%(k)d | xargs -r rm -f --"
            % {"n": name, "p": prefix, "k": BACKUP_KEEP + 1})


def copy_backups(files):
    """Copy the backups just made to the place in Settings → Backups. Returns a note; raises RuntimeError."""
    s = APP.settings
    kind, tag = s.get("backup_copy"), backup_tag()
    if kind == "folder":
        root = s.get("backup_copy_path") or ""
        why = backup_folder_check(root)
        if why:
            raise RuntimeError(why)
        dest = os.path.join(root, BACKUP_COPY_DIR, tag)
        os.makedirs(dest, exist_ok=True)
        for n in files:
            tmp = os.path.join(dest, n + ".tmp")
            shutil.copyfile(os.path.join(BACKUP_DIR, n), tmp)
            os.replace(tmp, os.path.join(dest, n))
        for iid in {n.split("-")[0] for n in files}:
            for old in sorted((x for x in os.listdir(dest) if x.startswith(iid + "-") and x.endswith(".zip")), reverse=True)[BACKUP_KEEP:]:
                try:
                    os.remove(os.path.join(dest, old))
                except OSError:
                    pass
        return "Copied to %s" % dest
    if kind == "computer":
        pi = next((x for x in pi_saved() if x["ip"] == s.get("backup_copy_ip")), None)
        if pi is None:
            raise RuntimeError("The computer the copies go to isn't set up here any more - pick another one.")
        if not pi_key_ok(pi):
            raise RuntimeError("%s doesn't let this dashboard in with its key, so copies can't go there." % (pi.get("host") or pi["ip"]))
        for n in files:
            name = "%s-%s" % (tag, n)
            with open(os.path.join(BACKUP_DIR, n), "rb") as f:
                code, out = pi_ssh(pi, backup_put_cmd(pi, name, "%s-%s-" % (tag, n.split("-")[0])), stdin_data=f,
                                   timeout=max(600, os.path.getsize(os.path.join(BACKUP_DIR, n)) // 10 ** 6))
            if "ES_PUT_OK" not in out:
                raise RuntimeError(pi_ssh_error(out) if code == 255 else
                                   "Couldn't save it there: " + (out.strip().splitlines() or ["no answer"])[-1][:200])
        return "Copied to the easyserver-backups folder on %s" % (pi.get("host") or pi["ip"])
    return ""


# ---- Google Drive: a copy of the backups in the owner's own Drive ----------------------------------------------
# Signing in works like on a TV: the dashboard shows a short code, the owner opens google.com/device on their phone,
# types it and allows access. Only the files EasyServer makes are visible to it (drive.file), nothing else in the Drive.
# The built-in Google app: an OAuth client of type "TVs and Limited Input devices" (Google doesn't treat its secret
# as secret - it's in every copy of the app). Empty = not set up yet; owners can use their own in Settings instead.
GDRIVE_CLIENT_ID = ""
GDRIVE_CLIENT_SECRET = ""
GDRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
GDRIVE_API = "https://www.googleapis.com/drive/v3"
GDRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
GDRIVE_FOLDER_NAME = "BeamMP EasyServer backups"
GDRIVE_MAX = 8 * 1024 ** 3
GDRIVE_MIN_WAIT = 5              # seconds between asking Google whether the owner allowed access
_GD = {"flow": None, "access": "", "exp": 0}


class GDriveError(RuntimeError):
    pass


def gdrive_app():
    """(client id, client secret) - the owner's own Google app if they set one up, otherwise the built-in one."""
    own = (APP.settings.get("gdrive_client_id") or "").strip()
    if own:
        return own, APP.secrets.get("GDRIVE_SECRET")
    return GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET


def gdrive_ready():
    return bool(gdrive_app()[0])


def gdrive_connected():
    return APP.secrets.has("GDRIVE_REFRESH")


def _google(url, fields=None, method=None, body=None, headers=None, timeout=30, want_headers=False):
    h = {"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION}
    h.update(headers or {})
    data = body
    if fields is not None:
        data = urllib.parse.urlencode(fields).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data is not None else "GET"), headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            out = json.loads(raw) if raw else {}
            return (out, r.headers) if want_headers else out
    except urllib.error.HTTPError as e:            # never put a token into a message: only Google's error text
        try:
            j = json.loads(e.read() or b"{}")
        except ValueError:
            j = {}
        err = j.get("error")
        msg = err.get("message") if isinstance(err, dict) else (j.get("error_description") or err)
        ex = GDriveError("Google said %d: %s" % (e.code, str(msg or "error")[:200]))
        ex.code, ex.kind = e.code, err if isinstance(err, str) else ""
        raise ex
    except urllib.error.URLError as e:
        raise GDriveError("can't reach Google (%s)" % short_err(e.reason))


def gdrive_token():
    if _GD["access"] and now() < _GD["exp"] - 60:
        return _GD["access"]
    cid, sec = gdrive_app()
    ref = APP.secrets.get("GDRIVE_REFRESH")
    if not cid or not ref:
        raise GDriveError("Google Drive isn't connected")
    try:
        r = _google("https://oauth2.googleapis.com/token", {"client_id": cid, "client_secret": sec, "refresh_token": ref,
                                                            "grant_type": "refresh_token"})
    except GDriveError as e:
        if getattr(e, "kind", "") == "invalid_grant":
            raise GDriveError("Google Drive was disconnected (access removed in the Google account, or it expired) - "
                              "connect it again under Settings → Automatic backups.")
        raise
    _GD.update(access=r["access_token"], exp=now() + int(r.get("expires_in") or 3600))
    return _GD["access"]


def gdrive_api(method, path, params=None, body=None, base=GDRIVE_API, headers=None, **kw):
    url = base + path + ("?" + urllib.parse.urlencode(params) if params else "")
    h = dict(headers or {}, Authorization="Bearer " + gdrive_token())
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json; charset=UTF-8"
    return _google(url, method=method, body=data, headers=h, **kw)


def gdrive_about():
    """Who is connected and how full the Drive is."""
    a = gdrive_api("GET", "/about", {"fields": "user(displayName,emailAddress),storageQuota(limit,usage)"})
    q = a.get("storageQuota") or {}
    lim = int(q["limit"]) if q.get("limit") else None
    used = int(q.get("usage") or 0)
    return {"account": (a.get("user") or {}).get("emailAddress") or (a.get("user") or {}).get("displayName") or "",
            "limit": lim, "used": used, "free": (lim - used) if lim else None}


def gdrive_folder():
    """The id of the backups folder, made the first time (or again if the owner deleted it)."""
    fid = APP.settings.get("gdrive_folder") or ""
    if fid:
        try:
            f = gdrive_api("GET", "/files/" + urllib.parse.quote(fid), {"fields": "id,trashed"})
            if not f.get("trashed"):
                return fid
        except GDriveError as e:
            if getattr(e, "code", 0) != 404:
                raise
    f = gdrive_api("POST", "/files", {"fields": "id"}, {"name": GDRIVE_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"})
    APP.settings.update({"gdrive_folder": f["id"]})
    return f["id"]


def gdrive_list(folder=None):
    folder = folder or gdrive_folder()
    r = gdrive_api("GET", "/files", {"q": "'%s' in parents and trashed = false" % folder.replace("'", ""),
                                     "fields": "files(id,name,size,createdTime)", "orderBy": "createdTime desc", "pageSize": 300})
    out = []
    for f in r.get("files") or []:
        m = re.fullmatch(r"([A-Za-z0-9-]{1,20})-([a-z0-9]{1,12})-(\d{8}-\d{4}(?:\d{2})?)(-mods)?\.zip", f.get("name") or "")
        if m:
            out.append({"id": f["id"], "name": f["name"], "size": int(f.get("size") or 0), "computer": m.group(1),
                        "server": m.group(2), "when": m.group(3), "mods": bool(m.group(4)),
                        "t": int(time.mktime(time.strptime(m.group(3)[:13], "%Y%m%d-%H%M")))})
    return out


def gdrive_upload(path, name, folder):
    size = os.path.getsize(path)
    if size > GDRIVE_MAX:
        raise GDriveError("%s is too big for the Drive copy (%s)" % (name, fmt_bytes(size)))
    _, hdr = gdrive_api("POST", "", {"uploadType": "resumable", "fields": "id"}, {"name": name, "parents": [folder]},
                        base=GDRIVE_UPLOAD, headers={"X-Upload-Content-Type": "application/zip", "X-Upload-Content-Length": str(size)},
                        want_headers=True)
    loc = hdr.get("Location")
    if not loc or not loc.startswith("https://www.googleapis.com/"):
        raise GDriveError("Google didn't start the upload")
    with open(path, "rb") as f:
        _google(loc, method="PUT", body=f, headers={"Content-Type": "application/zip", "Content-Length": str(size)},
                timeout=max(300, size // 200000))


def gdrive_copy(files):
    """Upload the backups just made and keep the newest BACKUP_KEEP of each server. Returns a note."""
    folder, tag = gdrive_folder(), backup_tag()
    for n in files:
        gdrive_upload(os.path.join(BACKUP_DIR, n), "%s-%s" % (tag, n), folder)
    have = gdrive_list(folder)
    for iid in {n.split("-")[0] for n in files}:
        mine = [f for f in have if f["computer"] == tag and f["server"] == iid]
        for old in mine[BACKUP_KEEP:]:
            try:
                gdrive_api("DELETE", "/files/" + urllib.parse.quote(old["id"]))
            except GDriveError:
                pass
    return "Copied to Google Drive (%s)" % GDRIVE_FOLDER_NAME


def gdrive_download(fid, dest):
    url = GDRIVE_API + "/files/" + urllib.parse.quote(fid) + "?alt=media"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + gdrive_token(), "User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            got = 0
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                got += len(chunk)
                if got > GDRIVE_MAX:
                    raise GDriveError("That file is too big")
                f.write(chunk)
    except urllib.error.HTTPError as e:
        raise GDriveError("Google said %d while downloading" % e.code)
    except urllib.error.URLError as e:
        raise GDriveError("can't reach Google (%s)" % short_err(e.reason))


def gdrive_estimate():
    """How much of the Drive the copies will take: the newest backup of each server x the copies kept."""
    with LOCK:
        ids = list(INSTANCES)
    per = 0
    for iid in ids:
        b = list_backups(iid)
        if b:
            per += b[0]["size"]
    return {"per_night": per, "total": per * BACKUP_KEEP, "keep": BACKUP_KEEP, "known": per > 0}


def gdrive_flow_start():
    """Start the TV-style sign-in: returns the code to type at google.com/device; a thread waits for the answer."""
    cid, sec = gdrive_app()
    if not cid:
        raise GDriveError("Google Drive isn't set up in this version yet")
    r = _google("https://oauth2.googleapis.com/device/code", {"client_id": cid, "scope": GDRIVE_SCOPE})
    flow = {"code": r["user_code"], "url": r.get("verification_url") or r.get("verification_uri") or "https://www.google.com/device",
            "until": now() + int(r.get("expires_in") or 1800), "state": "waiting", "note": ""}
    _GD["flow"] = flow
    dev, wait = r["device_code"], max(GDRIVE_MIN_WAIT, int(r.get("interval", 5)))

    def poll():
        while _GD["flow"] is flow and now() < flow["until"]:
            time.sleep(wait)
            try:
                t = _google("https://oauth2.googleapis.com/token", {"client_id": cid, "client_secret": sec, "device_code": dev,
                                                                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
            except GDriveError as e:
                k = getattr(e, "kind", "")
                if k == "authorization_pending":
                    continue
                if k == "slow_down":
                    time.sleep(5)
                    continue
                flow.update(state="failed", note="You said no on the Google page." if k == "access_denied" else str(e))
                return
            if not t.get("refresh_token"):
                flow.update(state="failed", note="Google didn't give lasting access - try again.")
                return
            try:
                APP.secrets.set("GDRIVE_REFRESH", t["refresh_token"])
            except Exception as e:
                flow.update(state="failed", note="Couldn't save the access: %s" % short_err(e))
                return
            _GD.update(access=t["access_token"], exp=now() + int(t.get("expires_in") or 3600))
            upd = {"gdrive_on": True}
            try:
                upd["gdrive_account"] = gdrive_about()["account"]
                APP.settings.update(upd)
                gdrive_folder()
            except Exception as e:
                APP.settings.update(upd)
                sys.stderr.write("gdrive: %s\n" % short_err(e))
            flow.update(state="done", note="Connected.")
            APP.notifier.add("backup", "Google Drive connected", "Every nightly backup is now also copied to your Google Drive "
                             "(folder %s)." % GDRIVE_FOLDER_NAME, "success", send=False)
            if APP.settings.get("backup_on") and list_backups():
                threading.Thread(target=APP.copy_backups, args=([b["file"] for b in newest_backups()], "gdrive"), daemon=True).start()
            return
        if flow["state"] == "waiting":
            flow.update(state="failed", note="The code ran out - press Connect again.")

    threading.Thread(target=poll, daemon=True, name="gdrive-signin").start()
    return flow


def newest_backups():
    """The newest backup of each server."""
    out = {}
    for b in list_backups():
        out.setdefault(b["server"], b)
    return list(out.values())


def gdrive_disconnect():
    ref = APP.secrets.get("GDRIVE_REFRESH")
    if ref:
        try:
            _google("https://oauth2.googleapis.com/revoke", {"token": ref})
        except GDriveError:
            pass
    APP.secrets.set("GDRIVE_REFRESH", "")
    _GD.update(access="", exp=0, flow=None)
    APP.settings.update({"gdrive_on": False, "gdrive_account": ""})


# ---- a ready-to-go SD card -------------------------------------------------------------------------------------
# Like Raspberry Pi Imager: Raspberry Pi OS Lite (64-bit) plus cloud-init files on its boot partition, so the Pi
# joins the Wi-Fi, makes the user and lets this dashboard's key in on its first start. Then the dashboard finds it
# and installs EasyServer. Windows only (writing a card needs Windows' permission, asked on the screen).
PI_OS_LIST = "https://downloads.raspberrypi.com/os_list_imagingutility_v4.json"
PI_OS_NAME = "Raspberry Pi OS Lite (64-bit)"
PI_CARD_MIN = 4 * 1000 ** 3
PI_CARD_MAX = 520 * 1000 ** 3        # bigger is a USB hard disk, not a card
PI_WIFI_RE = re.compile(r"[^\x00-\x1f]{1,32}")
PI_COUNTRY_RE = re.compile(r"[A-Z]{2}")
_B64CRYPT = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def sha512_crypt(password, salt=None, rounds=5000):
    """The "$6$" password hash Linux keeps in /etc/shadow (Python 3.13 has no crypt module any more)."""
    if salt is None:
        salt = "".join(secrets.choice(_B64CRYPT) for _ in range(16))
    pw, sl = password.encode("utf-8"), salt[:16].encode("ascii")
    b = hashlib.sha512(pw + sl + pw).digest()
    a = hashlib.sha512(pw + sl)
    n = len(pw)
    while n > 64:
        a.update(b)
        n -= 64
    a.update(b[:n])
    n = len(pw)
    while n:
        a.update(b if n & 1 else pw)
        n >>= 1
    a = a.digest()
    dp = hashlib.sha512(pw * len(pw)).digest()
    p_ = (dp * (len(pw) // 64 + 1))[:len(pw)]
    ds = hashlib.sha512(sl * (16 + a[0])).digest()
    s_ = (ds * (len(sl) // 64 + 1))[:len(sl)]
    c = a
    for i in range(rounds):
        h = hashlib.sha512()
        h.update(p_ if i & 1 else c)
        if i % 3:
            h.update(s_)
        if i % 7:
            h.update(p_)
        h.update(c if i & 1 else p_)
        c = h.digest()
    order = [(0, 21, 42), (22, 43, 1), (44, 2, 23), (3, 24, 45), (25, 46, 4), (47, 5, 26), (6, 27, 48), (28, 49, 7),
             (50, 8, 29), (9, 30, 51), (31, 52, 10), (53, 11, 32), (12, 33, 54), (34, 55, 13), (56, 14, 35),
             (15, 36, 57), (37, 58, 16), (59, 17, 38), (18, 39, 60), (40, 61, 19), (62, 20, 41)]
    out = []
    for x, y, z in order:
        v = (c[x] << 16) | (c[y] << 8) | c[z]
        out += [_B64CRYPT[(v >> (6 * k)) & 63] for k in range(4)]
    v = c[63]
    out += [_B64CRYPT[(v >> (6 * k)) & 63] for k in range(2)]
    head = "$6$" if rounds == 5000 else "$6$rounds=%d$" % rounds
    return head + sl.decode() + "$" + "".join(out)


def pi_psk(ssid, password):
    """The Wi-Fi key worked out from the Wi-Fi password (what WPA2 really uses): the card gets this, not the password."""
    return hashlib.pbkdf2_hmac("sha1", password.encode("utf-8"), ssid.encode("utf-8"), 4096, 32).hex()


def pi_yaml(x):
    return json.dumps(str(x), ensure_ascii=False)       # a JSON string is a valid double-quoted YAML string


def pi_card_files(host, user, pw_hash, pub, ssid="", psk="", country=""):
    """The boot partition files that set the Pi up on its first start (cloud-init, the way Raspberry Pi Imager does)."""
    iid = "beammp-easyserver-%d" % int(time.time() * 1000)
    ud = ["#cloud-config", "hostname: " + pi_yaml(host), "manage_etc_hosts: true", "",
          "user:", "  name: " + pi_yaml(user), "  shell: /bin/bash", "  lock_passwd: false", "  passwd: " + pi_yaml(pw_hash),
          "  ssh_authorized_keys:", "    - " + pi_yaml(pub), "  sudo: ALL=(ALL) NOPASSWD:ALL", "",
          "ssh_pwauth: true", "", "runcmd:", "  - [ systemctl, enable, --now, ssh ]", ""]
    files = {"user-data": "\n".join(ud), "meta-data": "instance-id: %s\n" % iid}
    if ssid:
        nc = ["network:", "  version: 2", "  ethernets:", "    eth0:", "      dhcp4: true", "      dhcp6: true",
              "      optional: true", "  wifis:", "    wlan0:", "      dhcp4: true"]
        if country:
            nc.append("      regulatory-domain: " + pi_yaml(country))
        nc += ["      access-points:", "        %s:" % pi_yaml(ssid)]
        nc += ["          password: " + pi_yaml(psk)] if psk else ["          auth:", "            key-management: none"]
        nc += ["      optional: true", ""]
        files["network-config"] = "\n".join(nc)
    return files, " ds=nocloud;i=" + iid


def pi_card_image():
    """Where the newest Raspberry Pi OS Lite (64-bit) is, from the list Raspberry Pi Imager uses."""
    req = urllib.request.Request(PI_OS_LIST, headers={"User-Agent": "BeamMP-EasyServer/%s" % EASY_VERSION})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read(8 * 1024 * 1024))

    def walk(items):
        for it in items or []:
            if isinstance(it, dict):
                if it.get("name") == PI_OS_NAME and it.get("url"):
                    return it
                hit = walk(it.get("subitems"))
                if hit:
                    return hit
        return None
    it = walk(data.get("os_list"))
    if not it:
        raise RuntimeError("Couldn't find Raspberry Pi OS Lite (64-bit) in Raspberry Pi's list - try again later.")
    u = urllib.parse.urlsplit(it["url"])
    if u.scheme != "https" or u.hostname != "downloads.raspberrypi.com" or not u.path.endswith(".img.xz"):
        raise RuntimeError("Raspberry Pi's list points somewhere unexpected - not downloading it.")
    if it.get("init_format") not in ("cloudinit", "cloudinit-rpi"):
        raise RuntimeError("This Raspberry Pi OS version is set up a way this dashboard doesn't know yet - use Raspberry Pi Imager.")
    return {"url": it["url"], "sha256": str(it.get("extract_sha256", "")).lower(), "size": int(it.get("extract_size") or 0),
            "download": int(it.get("image_download_size") or 0), "date": str(it.get("release_date", ""))}


def pi_disks():
    """Removable cards and sticks in this computer (never the one Windows or the server is on)."""
    if not IS_WIN:
        return []
    ps = ("Get-CimInstance Win32_DiskDrive | ForEach-Object { $d = $_; "
          "$l = @(Get-CimAssociatedInstance -InputObject $d -ResultClassName Win32_DiskPartition | "
          "ForEach-Object { Get-CimAssociatedInstance -InputObject $_ -ResultClassName Win32_LogicalDisk } | ForEach-Object { $_.DeviceID }); "
          "[pscustomobject]@{n=[int]$d.Index; model=[string]$d.Model; size=[int64]$d.Size; media=[string]$d.MediaType; "
          "bus=[string]$d.InterfaceType; letters=$l} } | ConvertTo-Json -Compress -Depth 3")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True,
                           timeout=40, **_NOWIN)
        rows = json.loads(r.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    return pi_disk_filter(rows if isinstance(rows, list) else [rows])


def pi_disk_filter(rows):
    keep = (os.environ.get("SystemDrive", "C:").upper(), os.path.splitdrive(os.path.abspath(DATA_DIR))[0].upper())
    out = []
    for d in rows:
        if not isinstance(d, dict):
            continue
        letters = [str(x).upper() for x in (d.get("letters") or []) if x]
        removable = "removable" in str(d.get("media", "")).lower() or str(d.get("bus", "")).upper() == "USB"
        size = int(d.get("size") or 0)
        if removable and PI_CARD_MIN <= size <= PI_CARD_MAX and not set(letters) & set(keep):
            out.append({"n": int(d.get("n", -1)), "model": str(d.get("model", ""))[:60], "size": size, "letters": letters})
    return [d for d in out if d["n"] >= 0]


def pi_card_job(o):
    """Download Raspberry Pi OS, check it, have Windows write it to the card (with permission), then wait for the Pi."""
    job = {"kind": "card", "ip": "", "state": "running", "t": now(), "lines": [], "password": "", "error": "", "web": "",
           "progress": 0, "host": o["host"]}

    def add(line):
        job["lines"].append(line[:300])
        del job["lines"][:-300]

    def run():
        tmp = None
        try:
            img = pi_card_image()
            add("Raspberry Pi OS Lite (64-bit) from %s" % img["date"])
            path = pi_card_download(img, job, add)
            add("Checking the download…")
            pi_card_check(path, img, job)
            tmp = tempfile.mkdtemp(prefix="card-", dir=PI_DIR)
            files, cmdline = pi_card_files(o["host"], o["user"], o["pw_hash"], pi_key()[1], o["ssid"], o["psk"], o["country"])
            spec = {"disk": o["disk"]["n"], "size": o["disk"]["size"], "image": path, "extract_size": img["size"],
                    "sha256": img["sha256"], "files": files, "cmdline": cmdline, "status": os.path.join(tmp, "status.json")}
            write_json(os.path.join(tmp, "card.json"), spec)
            helper = os.path.join(tmp, "cardwriter.py")
            with open(helper, "w", encoding="utf-8") as f:
                f.write(PI_CARD_HELPER)
            add("Windows asks for permission to write the card - press Yes on this computer's screen.")
            job["progress"] = 0
            pi_card_elevate(helper, os.path.join(tmp, "card.json"), spec["status"], job, add)
            add("The card is ready. Take it out, put it in the Raspberry Pi and plug in the power.")
            add("It shows up here by itself in about 3 to 5 minutes, then EasyServer gets installed.")
            job.update(state="waiting", progress=0)
            pi_card_wait(o, job, add)
        except Exception as e:
            job.update(state="failed", error=str(e) if isinstance(e, RuntimeError) else short_err(e))
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)       # it held the Wi-Fi key
            job["ended"] = now()

    _PI["job"] = job
    threading.Thread(target=run, daemon=True, name="pi-card").start()
    return job


def pi_card_download(img, job, add):
    d = os.path.join(PI_DIR, "images")
    os.makedirs(d, exist_ok=True)
    name = os.path.basename(urllib.parse.urlsplit(img["url"]).path)
    path = os.path.join(d, name)
    for old in os.listdir(d):                   # keep only the newest one (about 500 MB each)
        if old != name:
            try:
                os.remove(os.path.join(d, old))
            except OSError:
                pass
    if os.path.isfile(path) and (not img["download"] or os.path.getsize(path) == img["download"]):
        add("Already downloaded")
        return path
    add("Downloading it (about %d MB)…" % ((img["download"] or 500 * 1024 * 1024) // (1024 * 1024)))
    req = urllib.request.Request(img["url"], headers={"User-Agent": "BeamMP-EasyServer/%s" % EASY_VERSION})
    part = path + ".part"
    done, total = 0, img["download"] or 1
    with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            job["progress"] = min(99, done * 100 // total)
    if img["download"] and done != img["download"]:
        os.remove(part)
        raise RuntimeError("The download stopped half way - try again.")
    os.replace(part, path)
    return path


def pi_card_check(path, img, job):
    """Unpack it once without writing anything, to be sure it's whole before the card is erased."""
    import lzma
    h, done, total = hashlib.sha256(), 0, img["size"] or 1
    dec = lzma.LZMADecompressor()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            while chunk:
                out = dec.decompress(chunk)
                h.update(out)
                done += len(out)
                chunk = dec.unused_data if dec.eof else b""
                if dec.eof:
                    dec = lzma.LZMADecompressor()
            job["progress"] = min(99, done * 100 // total)
    if img["sha256"] and h.hexdigest() != img["sha256"]:
        os.remove(path)
        raise RuntimeError("The download was damaged (it doesn't match Raspberry Pi's checksum) and was deleted - try again.")


def pi_card_elevate(helper, spec, status, job, add):
    """Run the card writer with Windows' permission (the UAC question on this computer's screen) and follow it."""
    py = sys.executable
    if py.lower().endswith("python.exe") and os.path.exists(py[:-10] + "pythonw.exe"):
        py = py[:-10] + "pythonw.exe"
    q = lambda x: x.replace("'", "''")
    ps = ("Start-Process -FilePath '%s' -ArgumentList @('\"%s\"', '\"%s\"') -Verb RunAs -Wait -WindowStyle Hidden"
          % (q(py), q(helper), q(spec)))
    proc = subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, **_NOWIN)
    seen = ""
    while proc.poll() is None:
        time.sleep(1)
        st = read_json(status, {})
        if st.get("step") and st["step"] != seen:
            seen = st["step"]
            add({"erase": "Erasing the card…", "write": "Writing Raspberry Pi OS to the card - a few minutes…",
                 "setup": "Adding your Wi-Fi, user and this dashboard's key…"}.get(seen, seen))
        if st.get("progress") is not None:
            job["progress"] = st["progress"]
    out = proc.stdout.read().decode("utf-8", "replace") if proc.stdout else ""
    st = read_json(status, {})
    if st.get("step") == "done":
        return
    if st.get("error"):
        raise RuntimeError(st["error"])
    if proc.returncode or "cancel" in out.lower():
        raise RuntimeError("Windows didn't get permission (No was pressed), so nothing was written. Press the button again and choose Yes.")
    raise RuntimeError("Writing the card stopped without saying why - nothing may have been written. Try again.")


def pi_card_wait(o, job, add):
    """Wait for the new Pi to turn up (its name on the network, or a Pi that lets this dashboard's key in), then
    set it up with the key - no password needed."""
    host, user, end = o["host"], o["user"], time.time() + 40 * 60
    last_scan = 0
    while time.time() < end and _PI["job"] is job:
        cands = []
        try:
            cands.append(socket.gethostbyname(host + ".local"))
        except OSError:
            pass
        if time.time() - last_scan > 60:
            last_scan = time.time()
            try:
                _PI["scan"] = pi_scan()
                cands += [f["ip"] for f in _PI["scan"]["found"] if f["pi"] and f["ssh"] and not f["known"]]
            except Exception:
                pass
        for ip in dict.fromkeys(cands):
            if not pi_private(ip):
                continue
            try:
                code, out = pi_ssh({"ip": ip, "user": user}, "echo ES_KEY_OK", timeout=20)
            except Exception:
                continue
            if "ES_KEY_OK" in out:
                add("Found it at %s - setting it up." % ip)
                pi = pi_pair(ip, user, None)
                job.update(state="done", ip=ip)
                if pi_problem(pi):
                    raise RuntimeError(pi_problem(pi))
                if _PI["job"] is job:
                    pi_job("install", pi, name=o["name"])
                return
        time.sleep(10)
    if _PI["job"] is job:
        raise RuntimeError("The Raspberry Pi didn't show up within 40 minutes. Is it plugged in, and is the Wi-Fi name and "
                           "password right? It might be on the network already: press Look again.")


PI_CARD_HELPER = r"""# BeamMP EasyServer: writes Raspberry Pi OS to an SD card. Started by the dashboard with Windows' permission.
import hashlib, json, lzma, os, subprocess, sys, time

NOWIN = 0x08000000
BLOCK = 4 << 20


def status(path, **k):
    with open(path + ".tmp", "w") as f:
        json.dump(k, f)
    os.replace(path + ".tmp", path)


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True, text=True,
                          timeout=180, creationflags=NOWIN)


def blocks(image):
    dec = lzma.LZMADecompressor()
    buf = bytearray()
    with open(image, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            while chunk:
                buf += dec.decompress(chunk)
                chunk = dec.unused_data if dec.eof else b""
                if dec.eof:
                    dec = lzma.LZMADecompressor()
            while len(buf) >= BLOCK:
                yield bytes(buf[:BLOCK])
                del buf[:BLOCK]
    if buf:
        yield bytes(buf) + b"\0" * (-len(buf) % 512)


def write_image(image, device, total, sha, progress=lambda p: None):
    # The first block (with the partition table) goes on last, so Windows doesn't find the new partitions and
    # get in the way while the rest is written - Raspberry Pi Imager does the same.
    h, done, first = hashlib.sha256(), 0, None
    with open(device, "r+b", buffering=0) as dev:
        for b in blocks(image):
            h.update(b if done + len(b) <= total else b[:max(0, total - done)])
            if first is None:
                first = b
                dev.seek(len(b))
            else:
                dev.write(b)
            done += len(b)
            progress(min(99, done * 100 // max(total, 1)))
        dev.seek(0)
        dev.write(first)
        try:
            os.fsync(dev.fileno())
        except OSError:
            pass
    if sha and h.hexdigest() != sha:
        raise RuntimeError("The card didn't take the data correctly - it may be worn out. Try again or use another card.")


def main(spec_path):
    spec = json.load(open(spec_path, encoding="utf-8"))
    st = spec["status"]
    try:
        n = int(spec["disk"])
        r = ps("$d = Get-Disk -Number %d; @{bus=[string]$d.BusType; boot=[bool]$d.IsBoot; system=[bool]$d.IsSystem; size=[int64]$d.Size} | ConvertTo-Json -Compress" % n)
        d = json.loads(r.stdout or "{}")
        if not d or d.get("boot") or d.get("system") or d.get("bus") not in ("SD", "USB", "MMC") or abs(int(d.get("size", 0)) - int(spec["size"])) > (1 << 20):
            raise RuntimeError("That card was taken out or swapped, or isn't a removable card - nothing was written.")
        if int(spec["size"]) < int(spec["extract_size"]):
            raise RuntimeError("The card is too small for Raspberry Pi OS - use one with 8 GB or more.")
        status(st, step="erase")
        dp = os.path.join(os.path.dirname(spec_path), "erase.txt")
        with open(dp, "w") as f:
            f.write("select disk %d\nclean\n" % n)
        r = subprocess.run(["diskpart", "/s", dp], capture_output=True, text=True, timeout=180, creationflags=NOWIN)
        if r.returncode:
            raise RuntimeError("Windows couldn't erase the card: " + ((r.stdout or "").strip().splitlines() or ["?"])[-1][:200])
        time.sleep(2)
        status(st, step="write", progress=0)
        write_image(spec["image"], r"\\.\PhysicalDrive%d" % n, int(spec["extract_size"]), spec["sha256"],
                    lambda p: status(st, step="write", progress=p))
        status(st, step="setup", progress=100)
        ps("Update-Disk -Number %d" % n)
        letter = ""
        for _ in range(30):
            r = ps("$p = Get-Partition -DiskNumber %d -PartitionNumber 1 -ErrorAction Stop; if (-not $p.DriveLetter) { $p | Add-PartitionAccessPath -AssignDriveLetter -ErrorAction SilentlyContinue; $p = Get-Partition -DiskNumber %d -PartitionNumber 1 }; [string]$p.DriveLetter" % (n, n))
            letter = (r.stdout or "").strip()[:1]
            if letter.isalpha() and os.path.exists(letter + ":\\cmdline.txt"):
                break
            letter = ""
            time.sleep(2)
        if not letter:
            raise RuntimeError("Raspberry Pi OS is on the card, but Windows didn't open its boot part to add your settings. "
                               "Take the card out, put it back in and press the button again.")
        root = letter + ":\\"
        for name, text in spec["files"].items():
            with open(root + name, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        with open(root + "cmdline.txt", encoding="utf-8") as f:
            line = f.read().strip()
        if "ds=nocloud" not in line:
            with open(root + "cmdline.txt", "w", encoding="utf-8", newline="\n") as f:
                f.write(line + spec["cmdline"])
        status(st, step="done", progress=100)
    except Exception as e:
        status(st, step="failed", error=str(e)[:300] if isinstance(e, RuntimeError) else "Writing the card failed: %s" % e)


if __name__ == "__main__":
    main(sys.argv[1])
"""


# ----------------------------------------------------------------------------- games
# The plugin runs races, cops and robbers, speed traps, badges and seasons in the game. Here: which
# are on and their rules (games.txt), the results and leaderboards, the live map, and a weekly recap.
GAME_SWITCHES = ("race", "cnr", "traps", "badges", "seasons", "champ", "drift")
CHAMP_POINTS = {"f1": (25, 18, 15, 12, 10, 8, 6, 4, 2, 1), "simple": (10, 8, 6, 5, 4, 3, 2, 1)}
CNR_MINUTES = (3, 5, 10, 15, 20, 30)
CNR_CATCH = (6, 8, 10, 15, 20)
CNR_HOLD = (2, 3, 5)
GAME_COUNTS = ("laps", "races", "wins", "busts", "escapes", "cnr")
BADGES = [
    ("first_lap", "First lap", "Set a lap time"), ("laps_25", "Lap regular", "Drive 25 timed laps"),
    ("record", "Record breaker", "Set a track record"), ("race_win", "Race winner", "Win a race against other players"),
    ("race_5", "Champion", "Win 5 races"), ("sheriff", "Sheriff", "Bust 5 robbers"),
    ("getaway", "Getaway driver", "Stay free as a robber until the time runs out"), ("speed_demon", "Speed demon", "Set a speed trap record"),
    ("flat_out", "Flat out", "Drive 200 km/h"), ("km_100", "100 km club", "Drive 100 km"), ("km_1000", "Road tripper", "Drive 1000 km"),
    ("night_owl", "Night owl", "Drive between 2 and 5 in the morning"), ("season_champ", "Season champion", "Win a season leaderboard"),
]
TRAP_RE = re.compile(r"^([\w\-]+)\t([^\t]+)\t([^\t]*)\t(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)$")
LIVEMAP_ASK = 20            # the plugin keeps writing positions this long after the last look


def read_games_cfg():
    d = {"race": True, "race_who": "everyone", "cnr": True, "cnr_who": "everyone", "cnr_minutes": 10, "cnr_catch": 10,
         "cnr_hold": 3, "cnr_busted": "out", "traps": True, "badges": True, "seasons": False,
         "champ": False, "champ_name": "", "champ_points": "f1", "champ_started": 0, "drift": False}
    for line in shared_read(laps_file("games.txt"), 4096).splitlines():
        k, _, v = line.partition("=")
        v = v.strip()
        if k in GAME_SWITCHES:
            d[k] = v == "on"
        elif k in ("race_who", "cnr_who"):
            d[k] = "admins" if v == "admins" else "everyone"
        elif k == "cnr_busted":
            d[k] = "cop" if v == "cop" else "out"
        elif k in ("cnr_minutes", "cnr_catch", "cnr_hold", "champ_started") and v.isdigit():
            d[k] = int(v)
        elif k == "champ_name":
            d[k] = v[:60]
        elif k == "champ_points":
            d[k] = "simple" if v == "simple" else "f1"
    return d


def write_games_cfg(d):
    lines = ["%s=%s" % (k, "on" if d[k] else "off") for k in GAME_SWITCHES]
    lines += ["race_who=%s" % d["race_who"], "cnr_who=%s" % d["cnr_who"], "cnr_busted=%s" % d["cnr_busted"],
              "cnr_minutes=%d" % d["cnr_minutes"], "cnr_catch=%d" % d["cnr_catch"], "cnr_hold=%d" % d["cnr_hold"],
              "champ_name=%s" % re.sub(r"[\x00-\x1f]", "", d["champ_name"])[:60], "champ_points=%s" % d["champ_points"],
              "champ_started=%d" % d["champ_started"]]
    shared_write(laps_file("games.txt"), "# Managed by the dashboard (Games page)\n" + "\n".join(lines) + "\n")


def read_champ():
    """The championship standings the plugin keeps (champ.tsv), best first, and how many races counted."""
    rows, rounds = [], 0
    for line in shared_read(laps_file("champ.tsv"), 512 * 1024).splitlines():
        p = line.split("\t")
        if len(p) == 2 and p[0] == "#rounds" and p[1].isdigit():
            rounds = int(p[1])
        elif len(p) == 5 and p[0] and not p[0].startswith("#") and all(x.isdigit() for x in p[1:]):
            rows.append({"name": p[0][:64], "points": int(p[1]), "races": int(p[2]), "wins": int(p[3]), "podiums": int(p[4])})
    rows.sort(key=lambda r: (-r["points"], -r["wins"], r["name"].lower()))
    return rows, rounds


def read_champ_history():
    """Finished championships, newest first: name <TAB> winner <TAB> points <TAB> races <TAB> started <TAB> ended."""
    out = []
    for line in shared_read(laps_file("champs.tsv"), 256 * 1024).splitlines():
        p = line.split("\t")
        if len(p) == 6 and all(x.isdigit() for x in p[2:]):
            out.append({"name": p[0][:60], "winner": p[1][:64], "points": int(p[2]), "races": int(p[3]), "started": int(p[4]), "ended": int(p[5])})
    return out[::-1][:20]


def end_champ(cfg):
    """Keep the finished championship's winner (if it had a race) and empty the standings."""
    rows, rounds = read_champ()
    if rows and rounds:
        clean = lambda x: re.sub(r"[\t\r\n]", " ", str(x))
        old = shared_read(laps_file("champs.tsv"), 256 * 1024)
        shared_write(laps_file("champs.tsv"), old + "%s\t%s\t%d\t%d\t%d\t%d\n" % (
            clean(cfg["champ_name"] or "Championship"), clean(rows[0]["name"]), rows[0]["points"], rounds, cfg["champ_started"], now()))
    shared_write(laps_file("champ.tsv"), "")
    return rows[0]["name"] if rows and rounds else None


def read_drift():
    """Best drift per player per map (drift.tsv, kept by the plugin): [{"raw_map", "name", "score", "car", "t"}]"""
    out = []
    for line in shared_read(laps_file("drift.tsv"), 2 * 1024 * 1024).splitlines():
        p = line.split("\t")
        if len(p) == 5 and p[1] and p[2].isdigit() and p[4].isdigit():
            out.append({"raw_map": p[0], "name": p[1][:64], "score": int(p[2]), "car": p[3][:40], "t": int(p[4])})
    return out


def write_drift(rows):
    clean = lambda x: re.sub(r"[\t\r\n]", " ", str(x))
    shared_write(laps_file("drift.tsv"), "".join("%s\t%s\t%d\t%s\t%d\n" % (clean(r["raw_map"]), clean(r["name"]), r["score"], clean(r["car"]), r["t"])
                                                for r in rows))


def drift_boards():
    """One leaderboard per map, the map with the best drift first."""
    by = {}
    for r in read_drift():
        by.setdefault(r["raw_map"], []).append(r)
    out = [{"id": m, "map": map_name(m) if m else "", "drivers": len(rows),
            "top": [{k: r[k] for k in ("name", "score", "car", "t")} for r in sorted(rows, key=lambda r: -r["score"])[:10]]}
           for m, rows in by.items()]
    return sorted(out, key=lambda b: -b["top"][0]["score"])


def read_game_counts(season=False):
    out = []
    for line in shared_read(laps_file("seasonstats.tsv" if season else "gamestats.tsv"), 2 * 1024 * 1024).splitlines():
        p = line.split("\t")
        if len(p) == 7 and p[0] and all(x.isdigit() for x in p[1:]):
            out.append(dict(zip(("name",) + GAME_COUNTS, [p[0][:64]] + [int(x) for x in p[1:]])))
    return out


def read_badges():
    """{lower-case name: {"name", "badges": {badge id: unix time}}}"""
    out = {}
    for line in shared_read(laps_file("badges.tsv"), 2 * 1024 * 1024).splitlines():
        p = line.split("\t")
        if len(p) == 3 and p[2].isdigit() and re.fullmatch(r"\w+", p[1]):
            me = out.setdefault(p[0].lower(), {"name": p[0][:64], "badges": {}})
            me["badges"].setdefault(p[1], int(p[2]))
    return out


def read_traps():
    out = []
    for line in shared_read(laps_file("traps.tsv"), 256 * 1024).splitlines():
        m = TRAP_RE.match(line)
        if m:
            tid, name, mp, x, y, z = m.groups()
            out.append({"id": tid, "name": name[:40], "map": map_name(mp) if mp else "", "raw_map": mp, "x": float(x), "y": float(y)})
    return out


def read_trap_speeds():
    out = {}
    for line in shared_read(laps_file("trapspeeds.tsv"), 2 * 1024 * 1024).splitlines():
        p = line.split("\t")
        if len(p) == 5 and p[4].isdigit():
            try:
                out.setdefault(p[0], []).append({"name": p[1][:64], "kmh": float(p[2]), "car": p[3][:40], "t": int(p[4])})
            except ValueError:
                continue
    for rows in out.values():
        rows.sort(key=lambda r: -r["kmh"])
    return out


def write_trap_speeds(speeds):
    clean = lambda x: re.sub(r"[\t\r\n]", " ", str(x))
    shared_write(laps_file("trapspeeds.tsv"), "".join("%s\t%s\t%.1f\t%s\t%d\n" % (tid, clean(r["name"]), r["kmh"], clean(r["car"]), r["t"])
                                                      for tid, rows in speeds.items() for r in rows))


SEASON_CATS = {"lap": "Fastest lap", "trap": "Speed trap", "wins": "Most race wins", "busts": "Most busts", "escapes": "Most escapes"}


def read_seasons():
    """Past seasons, newest first: [{"season", "winners": [{"cat", "what", "name", "value", "shown"}]}]"""
    by = {}
    for line in shared_read(laps_file("seasons.tsv"), 512 * 1024).splitlines():
        p = line.split("\t")
        if len(p) != 5 or not re.fullmatch(r"\d{4}-\d\d", p[0]) or p[1] not in SEASON_CATS:
            continue
        try:
            v = float(p[4])
        except ValueError:
            continue
        shown = fmt_lap(int(v)) if p[1] == "lap" else ("%d km/h" % v) if p[1] == "trap" else str(int(v))
        by.setdefault(p[0], []).append({"cat": p[1], "label": SEASON_CATS[p[1]], "what": p[2][:40], "name": p[3][:64], "shown": shown})
    return [{"season": s, "winners": by[s]} for s in sorted(by, reverse=True)]


def season_info():
    cur = shared_read(laps_file("season.txt"), 64).strip()[:7]
    lt = time.localtime()
    nxt = time.mktime((lt.tm_year + (lt.tm_mon == 12), lt.tm_mon % 12 + 1, 1, 0, 0, 0, 0, 0, -1))
    return {"season": cur if re.fullmatch(r"\d{4}-\d\d", cur) else time.strftime("%Y-%m"), "days_left": max(0, int((nxt - now() + 86399) // 86400))}


def track_shapes(only_map):
    """Tracks on this map with their points, for the live map."""
    out = []
    for line in read_track_lines():
        tid, name, mp, kind, pts = TRACK_RE.match(line).groups()
        if mp and only_map and map_name(mp) != only_map:
            continue
        xy = []
        for p in pts.split(";"):
            try:
                x, y, _z = (float(v) for v in p.split(","))
                xy.append([round(x, 1), round(y, 1)])
            except ValueError:
                continue
        if len(xy) >= 2:
            out.append({"name": name[:40], "kind": "sprint" if kind == "sprint" else "loop", "pts": xy})
    return out


def games_summary():
    cfg = read_games_cfg()
    t_now = now()
    evs = [e for e in read_events(t_now - 120 * 86400) if e.get("ev") in ("race", "cnr", "badge", "trap", "season")]
    races, cnr, recent_badges = [], [], []
    for e in reversed(evs):
        ev = e["ev"]
        if ev == "race" and len(races) < 15 and isinstance(e.get("results"), list):
            res = []
            for r in e["results"][:12]:
                if isinstance(r, dict) and isinstance(r.get("ms"), int):
                    item = {"name": str(r.get("name"))[:64], "time": fmt_lap(r["ms"])}
                    if res:
                        item["gap"] = "+%.3f" % ((r["ms"] - res[0]["ms"]) / 1000.0)
                    item["ms"] = r["ms"]
                    res.append(item)
            races.append({"t": e["t"], "track": str(e.get("track"))[:40], "laps": int(e.get("laps") or 1), "results": res,
                          "dnf": [str(x)[:64] for x in (e.get("dnf") or [])[:12]], "by": str(e.get("by") or "")[:64]})
        elif ev == "cnr" and len(cnr) < 10:
            names = lambda k: [str(x)[:64] for x in (e.get(k) or [])[:30] if isinstance(x, str)]
            busts = [{"cop": str(b.get("cop"))[:64], "robber": str(b.get("robber"))[:64]} for b in (e.get("busts") or [])[:40] if isinstance(b, dict)]
            cnr.append({"t": e["t"], "winner": "cops" if e.get("winner") == "cops" else "robbers", "seconds": int(e.get("seconds") or 0),
                        "cops": names("cops"), "robbers": names("robbers"), "escaped": names("escaped"), "busts": busts})
        elif ev == "badge" and len(recent_badges) < 12:
            recent_badges.append({"t": e["t"], "name": str(e.get("name"))[:64], "badge": str(e.get("badge"))[:20]})
    season = read_game_counts(season=True)
    board = lambda k: [{"name": r["name"], "n": r[k]} for r in sorted(season, key=lambda r: -r[k]) if r[k] > 0][:10]
    owners = read_badges()
    badge_list = [{"id": b[0], "title": b[1], "how": b[2], "owners": sum(1 for o in owners.values() if b[0] in o["badges"])} for b in BADGES]
    top_owners = sorted(({"name": o["name"], "n": len(o["badges"])} for o in owners.values()), key=lambda r: -r["n"])[:10]
    speeds = read_trap_speeds()
    g = toml_parse(APP.read_config_text())[0].get("General", {})
    here = map_name(g.get("Map")) or ""
    traps = [dict(t, drivers=len(speeds.get(t["id"], [])), top=[dict(r, shown="%d km/h" % r["kmh"]) for r in speeds.get(t["id"], [])[:10]])
             for t in read_traps()]
    for t in traps:
        t.pop("raw_map", None)
    return dict(cfg, minutes=list(CNR_MINUTES), catches=list(CNR_CATCH), holds=list(CNR_HOLD), map=here,
                plugin=os.path.exists(os.path.join(I().STATS_DIR, "main.lua")), races=races, cnr_games=cnr,
                wins=board("wins"), busts=board("busts"), escapes=board("escapes"), trap_boards=traps, badge_list=badge_list,
                badge_leaders=top_owners, recent_badges=recent_badges, season_archive=read_seasons(), season=season_info(),
                players_with_badges=len(owners), champ_table=read_champ()[0][:50], champ_rounds=read_champ()[1],
                champ_history=read_champ_history(), champ_scales={k: list(v) for k, v in CHAMP_POINTS.items()},
                drift_boards=drift_boards())


def game_counts_for(name):
    lname = name.lower()
    out = {"all": None, "season": None}
    for k, season in (("all", False), ("season", True)):
        out[k] = next((r for r in read_game_counts(season) if r["name"].lower() == lname), None)
    b = read_badges().get(lname)
    titles = dict((x[0], x[1]) for x in BADGES)
    out["badges"] = [{"id": k, "title": titles.get(k, k), "t": v} for k, v in sorted((b or {}).get("badges", {}).items(), key=lambda kv: kv[1])
                     if k in titles]
    return out


def live_map():
    """Ask the plugin for positions (for the next LIVEMAP_ASK seconds) and return the newest it wrote."""
    inst = I()
    t = now()
    if t - getattr(inst, "livemap_asked", 0) >= 5:
        inst.livemap_asked = t
        shared_write(laps_file("livemap.txt"), "until=%d\n" % (t + LIVEMAP_ASK))
    g = toml_parse(APP.read_config_text())[0].get("General", {})
    here = map_name(g.get("Map")) or ""
    d = read_json(laps_file("livemap.json"), None)
    fresh = isinstance(d, dict) and isinstance(d.get("t"), int) and t - d["t"] <= 5
    cars = []
    for c in (d.get("cars") if fresh and isinstance(d.get("cars"), list) else [])[:200]:
        if not isinstance(c, dict):
            continue
        try:
            cars.append({"n": str(c.get("n"))[:64], "x": float(c["x"]), "y": float(c["y"]), "v": int(c.get("v") or 0),
                         "car": str(c.get("car") or "")[:40], "role": c.get("role") if c.get("role") in ("cop", "robber", "out", "race") else ""})
        except (KeyError, TypeError, ValueError):
            continue
    traps = [{"name": x["name"], "x": x["x"], "y": x["y"]} for x in read_traps() if not x["map"] or x["map"] == here]
    game = {}
    if fresh:
        if isinstance(d.get("race"), dict):
            game["race"] = {"track": str(d["race"].get("track"))[:40], "laps": int(d["race"].get("laps") or 1), "state": str(d["race"].get("state"))[:12]}
        if isinstance(d.get("cnr"), dict):
            game["cnr"] = {"state": str(d["cnr"].get("state"))[:8], "left": int(d["cnr"].get("left") or 0)}
    return {"t": t, "fresh": fresh, "map": here, "cars": cars, "tracks": track_shapes(here), "traps": traps, "game": game,
            "running": inst.server.status()["state"] == "running",
            "plugin": os.path.exists(os.path.join(inst.STATS_DIR, "main.lua"))}


# ----------------------------------------------------------------------------- weekly recap
RECAP_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def recap_cfg(inst=None):
    v = (inst or I()).meta.get("recap")
    d = {"on": False, "day": 6, "hour": 19}
    if isinstance(v, dict):
        d["on"] = bool(v.get("on"))
        if isinstance(v.get("day"), int) and 0 <= v["day"] <= 6:
            d["day"] = v["day"]
        if isinstance(v.get("hour"), int) and 0 <= v["hour"] <= 23:
            d["hour"] = v["hour"]
    return d


def fmt_hours(sec):
    h = sec / 3600.0
    return ("%d h" % round(h)) if h >= 10 else ("%.1f h" % h) if h >= 1 else ("%d min" % max(1, round(sec / 60.0)))


def weekly_recap(t_end=None):
    """The week in one Discord post: who played, records, races, chases, badges. None if nobody played."""
    t_end = t_end or now()
    t0 = t_end - 7 * 86400
    evs = read_events(t_end - 365 * 86400)
    sessions, _ = event_sessions(evs, t_end)
    week = [(n, max(a, t0), min(b, t_end)) for n, a, b in sessions if b >= t0 and a <= t_end]
    if not week:
        return None
    esc = discord_escape
    first = {}
    for n, a, b in sessions:
        first[n.lower()] = min(first.get(n.lower(), a), a)
    per = {}
    days = {}
    for n, a, b in week:
        per[n] = per.get(n, 0) + (b - a)
        days.setdefault(time.strftime("%A", time.localtime(a)), set()).add(n.lower())
    new = sum(1 for n in set(x.lower() for x, _, _ in week) if first.get(n, 0) >= t0)
    total = sum(per.values())
    lines = ["👥 %d player%s%s · %s played%s" % (
        len(per), "" if len(per) == 1 else "s", (", %d new" % new) if new else "", fmt_hours(total),
        (" · busiest day: %s" % max(days, key=lambda d: len(days[d]))) if days else "")]
    top = sorted(per.items(), key=lambda kv: -kv[1])[:3]
    lines.append("🏆 Most time on the server: " + ", ".join("%s %s" % (esc(n), fmt_hours(s)) for n, s in top))
    wk = [e for e in evs if e["t"] >= t0]
    recs = {}
    for e in wk:
        if e.get("ev") == "lap" and e.get("record") is True and isinstance(e.get("ms"), int):
            recs[str(e.get("track"))[:40]] = (str(e.get("name"))[:64], e["ms"])
    if recs:
        lines.append("🏁 New lap records: " + "; ".join("%s – %s %s" % (esc(t), esc(n), fmt_lap(ms)) for t, (n, ms) in list(recs.items())[:6]))
    races = [e for e in wk if e.get("ev") == "race" and isinstance(e.get("results"), list) and e["results"]]
    if races:
        wins = {}
        for e in races:
            if len(e["results"]) + len(e.get("dnf") or []) >= 2:
                w = str(e["results"][0].get("name"))[:64]
                wins[w] = wins.get(w, 0) + 1
        lines.append("🏎️ %d race%s%s" % (len(races), "" if len(races) == 1 else "s",
                                        (" – wins: " + ", ".join("%s %d" % (esc(n), k) for n, k in sorted(wins.items(), key=lambda kv: -kv[1])[:4])) if wins else ""))
    chases = [e for e in wk if e.get("ev") == "cnr"]
    if chases:
        busts, gone = {}, {}
        for e in chases:
            for b in e.get("busts") or []:
                if isinstance(b, dict):
                    c = str(b.get("cop"))[:64]
                    busts[c] = busts.get(c, 0) + 1
            for n in e.get("escaped") or []:
                gone[str(n)[:64]] = gone.get(str(n)[:64], 0) + 1
        bits = []
        if busts:
            n, k = max(busts.items(), key=lambda kv: kv[1])
            bits.append("most busts: %s (%d)" % (esc(n), k))
        if gone:
            bits.append("got away: " + ", ".join(esc(n) for n in list(gone)[:4]))
        lines.append("🚓 Cops and robbers: %d game%s%s" % (len(chases), "" if len(chases) == 1 else "s", (" – " + ", ".join(bits)) if bits else ""))
    traps = {}
    for e in wk:
        if e.get("ev") == "trap" and e.get("record") is True:
            traps[str(e.get("trap"))[:40]] = (str(e.get("name"))[:64], e.get("kmh") or 0)
    if traps:
        lines.append("📸 Speed trap records: " + "; ".join("%s – %s %d km/h" % (esc(t), esc(n), v) for t, (n, v) in list(traps.items())[:5]))
    nb = sum(1 for e in wk if e.get("ev") == "badge")
    if nb:
        lines.append("🏅 %d badge%s earned" % (nb, "" if nb == 1 else "s"))
    title = "The week on %s (%s – %s)" % (server_name() or I().name, time.strftime("%d %b", time.localtime(t0 + 1)), time.strftime("%d %b", time.localtime(t_end)))
    return title, "\n".join(lines)


def recap_channels():
    out = []
    if webhook_parts()[0]:
        out.append("Discord")
    if APP.settings.get("telegram_enabled") and APP.secrets.has("TELEGRAM_TOKEN") and APP.settings.get("telegram_chat"):
        out.append("Telegram")
    if APP.settings.get("webhook_enabled") and APP.secrets.has("CUSTOM_WEBHOOK"):
        out.append("webhook")
    return out

# ----------------------------------------------------------------------------- player profiles
NOTES_MAX = 50
PROFILE_EVENTS = ("kick", "ban", "unban", "mute", "report", "votekick", "vehblock", "vehspam", "refused", "denied", "lap",
                  "racepos", "bust", "badge", "trap")


def player_profile(name):
    """Everything known about one player on this server: play time, what happened to them, notes."""
    lname = name.lower()
    t_now = now()
    evs = read_events(t_now - 365 * 86400)
    sessions, _ = event_sessions(evs, t_now)
    mine = [(a, b) for n, a, b in sessions if n.lower() == lname]
    real = next((n for n, a, b in sessions if n.lower() == lname), name)
    hist = []
    reports_by = 0
    for e in evs:
        ev = e.get("ev")
        if ev not in PROFILE_EVENTS:
            continue
        who, target = str(e.get("name") or ""), str(e.get("target") or "")
        if ev == "report":
            if who.lower() == lname:
                reports_by += 1
            if target.lower() != lname:
                continue
        elif ev == "bust":
            if lname not in (who.lower(), target.lower()):
                continue
        elif who.lower() != lname:
            continue
        item = {"t": e["t"], "ev": ev}
        if ev == "bust":
            item.update({"cop": who[:64], "robber": target[:64], "me": "cop" if who.lower() == lname else "robber"})
        for k in ("by", "reason", "minutes", "until", "jbm", "track", "ms", "car", "record", "why", "pos", "of", "title", "trap", "kmh"):
            if k in e:
                item[k] = e[k]
        if ev == "report":
            item["by"] = who
        if ev in ("lap", "racepos") and isinstance(e.get("ms"), int):
            item["time"] = fmt_lap(e["ms"])
        hist.append(item)
    hist.reverse()
    ban = next((b for b in read_bans() if b["name"].lower() == lname), None)
    online = lname in [n.lower() for n in online_names()]
    laps = []
    times = read_laptimes()
    for t in read_tracks():
        rows = times.get(t["id"], [])
        for i, r in enumerate(rows):
            if r["name"].lower() == lname:
                laps.append({"track": t["name"], "time": fmt_lap(r["ms"]), "pos": i + 1, "of": len(rows), "car": r["car"]})
    rec = None
    try:
        with open_shared(I().RECORDS_FILE) as f:
            for line in f.read(2 * 1024 * 1024).splitlines():
                p = line.split("\t")
                if len(p) == 4 and p[0].lower() == lname:
                    rec = {"speed": round(float(p[1])), "dist": round(float(p[2]), 1), "streak": int(float(p[3]))}
    except (OSError, ValueError):
        pass
    d30 = t_now - 30 * 86400
    return {
        "name": real, "online": online, "seen": bool(mine) or bool(hist),
        "first_seen": min((a for a, b in mine), default=None), "last_seen": max((b for a, b in mine), default=None),
        "sessions": len(mine), "seconds": int(sum(b - a for a, b in mine)),
        "seconds_30d": int(sum(b - max(a, d30) for a, b in mine if b >= d30)),
        "ban": ban, "history": hist[:100], "reports_by": reports_by, "laps": laps, "records": rec,
        "notes": player_notes().get(lname, []), "games": game_counts_for(real),
    }


def player_card(name):
    """The public side of a player on this server (no bans, reports or notes): for Discord and the other servers' profiles."""
    lname = name.lower()
    p = player_profile(name)
    laps = sorted(p["laps"], key=lambda x: x["pos"])[:5]
    drift = max((r for r in read_drift() if r["name"].lower() == lname), key=lambda r: r["score"], default=None)
    rows, rounds = read_champ()
    pos = next((i + 1 for i, r in enumerate(rows) if r["name"].lower() == lname), None)
    b = read_badges().get(lname) or {}
    return {"name": p["name"], "online": p["online"], "seen": p["seen"], "seconds": p["seconds"], "seconds_30d": p["seconds_30d"],
            "sessions": p["sessions"], "first_seen": p["first_seen"], "last_seen": p["last_seen"], "laps": laps,
            "drift": {"score": drift["score"], "car": drift["car"]} if drift else None,
            "champ": {"pos": pos, "of": len(rows), "points": rows[pos - 1]["points"]} if pos and rounds else None,
            "badges": len(b.get("badges") or {}), "records": p["records"]}


def player_everywhere(name, ids):
    """player_card() on each of these servers where the player has been. Puts the current server back."""
    here = I().id
    out = []
    try:
        for sid in ids:
            with LOCK:
                inst = INSTANCES.get(sid)
            if not inst:
                continue
            use_server(sid)
            c = player_card(name)
            if c["seen"] or c["online"]:
                out.append(dict(c, server=inst.name, id=sid))
    finally:
        use_server(here)
    return out


def player_notes():
    v = I().meta.get("player_notes")
    return v if isinstance(v, dict) else {}


# ----------------------------------------------------------------------------- first-time setup checklist
def setup_checklist():
    """The steps a new server owner should do once, each ticked off by itself when it's done."""
    inst = I()
    g = toml_parse(APP.read_config_text())[0].get("General", {})
    name = str(g.get("Name") or "")
    private = g.get("Private") is True
    s = APP.settings
    played = any(e.get("ev") == "join" for e in read_events(now() - 365 * 86400)[-5000:])
    reach = (APP.state.get("reach_ok") or {}).get(inst.id)
    items = [
        {"id": "name", "done": bool(name.strip()) and not re.search(r"BeamMP Server$|^BeamMP Server|^My Server$", name.strip()),
         "go": "config"},
        {"id": "authkey", "done": private or inst.has_authkey(), "go": "config"},
        {"id": "mods", "done": any(x["enabled"] for x in list_mods() if x["name"] != TOOLS_MOD), "go": "mods"},
        {"id": "reach", "done": bool(reach) or played, "go": "network"},
        {"id": "invite", "done": played or bool(inst.meta.get("invited")), "go": "invite"},
        {"id": "alerts", "done": any(s.get(k) for k in ("discord_enabled", "email_enabled", "ntfy_enabled", "telegram_enabled", "webhook_enabled"))
                 , "go": "settings"},
    ]
    skipped = inst.meta.get("setup_skipped") if isinstance(inst.meta.get("setup_skipped"), list) else []
    for it in items:
        it["skipped"] = it["id"] in skipped
    return {"items": items, "hidden": bool(inst.meta.get("setup_hidden")),
            "done": sum(1 for it in items if it["done"] or it["skipped"]), "total": len(items)}


# ----------------------------------------------------------------------------- performance history
PERF_FILE = os.path.join(DATA_DIR, "performance.json")
PERF_KEEP = 7 * 1440        # a week of one-minute samples


def perf_series(hist, bucket):
    """[t, cpu %, memory used %, upload Mbit/s, players, ping ms] averaged over `bucket` seconds."""
    out, cur, key = [], [], None
    def flush():
        if not cur:
            return
        avg = lambda k: (lambda v: round(sum(v) / len(v), 1) if v else None)([x[k] for x in cur if x.get(k) is not None])
        mem = [100.0 * (x["mem_total"] - x["mem_free"]) / x["mem_total"] for x in cur
               if x.get("mem_total") and x.get("mem_free") is not None]
        up = avg("up_kbps")
        out.append([key, avg("cpu"), round(sum(mem) / len(mem), 1) if mem else None,
                    round(up / 1000.0, 2) if up is not None else None,
                    max(x.get("players") or 0 for x in cur), avg("ping")])
    for x in hist:
        k = int(x["t"] // bucket * bucket)
        if k != key:
            flush()
            cur, key = [], k
        cur.append(x)
    flush()
    return out


MOD_DESC_RE = re.compile(r"\s*\|\s*(Mods: [\d.]+ [KMGT]?B|No mods to download)$")


def fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return ("%d %s" if unit in ("B", "KB") else "%.1f %s") % (n, unit)
        n /= 1024.0


def refresh_mod_desc():
    """Keep "| Mods: 1.2 GB" at the end of the server description up to date
    (when that's turned on), so players see the download size before joining."""
    try:
        veh_sync()
    except Exception as e:
        print("vehicle rules: couldn't update for the new mods: %s" % short_err(e), file=sys.stderr)
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
                "antibot": False, "verify": True, "per_ip": 3, "join_flood": 8, "guests": True,
                "report": True, "votekick": False, "votekick_min": 4, "chatlog": True,
                "kickwords": [], "kickwords_action": "kick"}
KICKWORD_ACTIONS = ("kick", "ban60", "ban1440", "ban10080", "banperm")
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
        if k in ("admins", "words", "kickwords"):
            d[k] = [x.strip() for x in v.split(",") if x.strip()][:500]
        elif k == "kickwords_action" and v in KICKWORD_ACTIONS:
            d[k] = v
        elif k in ("filter", "spam", "antibot", "verify", "report", "votekick", "chatlog"):
            d[k] = v.lower() == "on"
        elif k == "votekick_min" and v.isdigit() and 3 <= int(v) <= 20:
            d[k] = int(v)
        elif k == "guests":
            d["guests"] = v.lower() != "block"
        elif k in ("spam_limit", "per_ip", "join_flood") and v.isdigit() and int(v) <= 100:
            d[k] = int(v)
    return d


def write_mod(d):
    onoff = lambda b: "on" if b else "off"
    shared_write(I().MOD_FILE,
                 "# Managed by the BeamMP EasyServer dashboard (Config -> Moderation).\n"
                 "admins=%s\nfilter=%s\nwords=%s\nspam=%s\nspam_limit=%d\nantibot=%s\nverify=%s\nper_ip=%d\njoin_flood=%d\nguests=%s\n"
                 "report=%s\nvotekick=%s\nvotekick_min=%d\nchatlog=%s\nkickwords=%s\nkickwords_action=%s\n" % (
                     ",".join(d["admins"]), onoff(d["filter"]), ",".join(d["words"]), onoff(d["spam"]), d["spam_limit"],
                     onoff(d["antibot"]), onoff(d["verify"]), d["per_ip"], d["join_flood"],
                     "allow" if d["guests"] else "block", onoff(d["report"]), onoff(d["votekick"]), d["votekick_min"],
                     onoff(d["chatlog"]), ",".join(d["kickwords"]), d["kickwords_action"]))


# ----------------------------------------------------------------------------- reports + chat history
REPORT_KEEP = 200
_REPORT_LOCK = threading.Lock()
CHAT_FILES = ("chat.log.1", "chat.log")


def _reports_path(inst):
    return os.path.join(DATA_DIR, "reports-%s.json" % inst.id)


def load_reports(inst):
    d = read_json(_reports_path(inst), [])
    return [x for x in d if isinstance(x, dict) and isinstance(x.get("id"), str)] if isinstance(d, list) else []


def chat_text(t):
    """Player chat for alerts: no control characters, no clickable [masked](links) in Discord."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(t if t is not None else "")).replace("[", "(").replace("]", ")").strip()[:300]


def read_chat(inst, since=0, until=None):
    """Chat history (oldest first) from the plugin's chat.log and chat.log.1."""
    out = []
    for name in CHAT_FILES:
        raw = shared_read(os.path.join(inst.STATS_DIR, name), 6 * 1024 * 1024)
        for line in raw.splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if not isinstance(e, dict) or not isinstance(e.get("t"), int) or e["t"] < since or (until and e["t"] > until):
                continue
            out.append({"t": e["t"], "name": clean_player_name(e.get("name")),
                        "msg": re.sub(r"[\x00-\x1f\x7f]", " ", str(e.get("msg") or ""))[:300], "hid": bool(e.get("hid"))})
    out.sort(key=lambda x: x["t"])
    return out


def add_report(inst, e):
    """A /report from the game: kept for the Players page, with the chat just before it."""
    t = e["t"]
    ctx = [c for c in read_chat(inst, t - 180, t + 5) if not c["msg"].lstrip().lower().startswith("/report")][-15:]
    item = {"id": uuid.uuid4().hex[:12], "t": t, "by": clean_player_name(e.get("name")),
            "target": clean_player_name(e.get("target")), "reason": chat_text(e.get("reason"))[:150], "chat": ctx, "open": True}
    with _REPORT_LOCK:
        items = load_reports(inst)
        items.insert(0, item)
        write_json(_reports_path(inst), items[:REPORT_KEEP])
    return item


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


# ----------------------------------------------------------------------------- welcome message + announcements
MSG_DEFAULTS = {"welcome": False, "welcome_text": ["Welcome {name}! Type /help to see the commands. Have fun!"],
                "announce": False, "every": 15, "messages": []}
MSG_EVERY = (5, 10, 15, 20, 30, 45, 60, 90, 120)


def clean_msg(t):
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(t if t is not None else "")).strip()[:200]


def read_messages():
    d = json.loads(json.dumps(MSG_DEFAULTS))
    raw = shared_read(I().MSG_FILE, 128 * 1024)
    if not raw:
        return d
    d["welcome_text"], d["messages"] = [], []
    for line in raw.splitlines():
        m = re.fullmatch(r"\s*(\w+)\s*=\s*(.*?)\s*", line)
        if not m:
            continue
        k, v = m.groups()
        if k in ("welcome", "announce"):
            d[k] = v.lower() == "on"
        elif k == "every" and v.isdigit() and int(v) in MSG_EVERY:
            d["every"] = int(v)
        elif k == "welcome_text" and v and len(d["welcome_text"]) < 5:
            d["welcome_text"].append(clean_msg(v))
        elif k == "msg" and v and len(d["messages"]) < 30:
            d["messages"].append(clean_msg(v))
    return d


def write_messages(d):
    onoff = lambda b: "on" if b else "off"
    lines = ["# Managed by the BeamMP EasyServer dashboard (Config -> Welcome & announcements).",
             "welcome=%s" % onoff(d["welcome"]), "announce=%s" % onoff(d["announce"]), "every=%d" % d["every"]]
    lines += ["welcome_text=%s" % clean_msg(t) for t in d["welcome_text"][:5] if clean_msg(t)]
    lines += ["msg=%s" % clean_msg(t) for t in d["messages"][:30] if clean_msg(t)]
    shared_write(I().MSG_FILE, "\n".join(lines) + "\n")


# ----------------------------------------------------------------------------- map rotation
ROTATION_DEFAULTS = {"on": False, "maps": [], "every": 4, "at": "00:00", "warn": 5, "empty_only": False}


def rotation_cfg(inst):
    r = json.loads(json.dumps(ROTATION_DEFAULTS))
    m = inst.meta.get("rotation")
    if isinstance(m, dict):
        r.update({k: m[k] for k in ROTATION_DEFAULTS if k in m})
    return r


def current_map():
    data, _, _ = toml_parse(APP.read_config_text())
    return map_name(data.get("General", {}).get("Map"))


# ----------------------------------------------------------------------------- server templates
TEMPLATES = {
    "drift": {"label": "Drift", "map": "johnson_valley", "max_players": 12,
              "about": "Open map, short car cleanup, drift tags and countdowns for tandem runs",
              "extras": {"clear": True, "every": 4, "afk": True, "afk_minutes": 10, "countdown": True, "tag": True, "top": True,
                         "tags": ["DRIFT", "TANDEM", "LEAD", "CHASE", "CHILL", "AFK"]},
              "welcome": "Welcome {name}! Drift server - slide sideways for points, /drift for the leaderboard. /countdown 3 for tandems.",
              "messages": ["Want to tandem? Pick a lead driver and use /countdown 3.", "Bigger angle and more speed = more points. /drift shows the best."],
              "games": {"drift": True, "race": False, "cnr": False, "traps": True, "badges": True, "champ": False}, "laps": False,
              "search": "drift"},
    "racing": {"label": "Racing", "map": "hirochi_raceway", "max_players": 10,
               "about": "Race track, countdowns, records, strict anti-spam and no AFK cars on track",
               "extras": {"clear": True, "every": 2, "afk": True, "afk_minutes": 3, "countdown": True, "tag": True, "top": True,
                          "tags": ["RACE", "QUALI", "PIT", "SPECTATE"]},
               "spam": True,
               "welcome": "Welcome {name}! Racing server - /race starts a race, /laps shows the lap records. No ramming, please.",
               "messages": ["Every race counts for the championship - /champ shows the standings.", "Cars that stand still for 3 minutes are removed."],
               "games": {"race": True, "champ": True, "traps": True, "badges": True, "drift": False, "cnr": False}, "laps": True,
               "champ_name": "Season 1", "search": "race car"},
    "cops": {"label": "Cops and robbers", "map": "west_coast_usa", "max_players": 16,
             "about": "City map, cops and robbers rounds, speed traps, COP / ROBBER tags",
             "extras": {"clear": True, "every": 6, "afk": True, "afk_minutes": 10, "countdown": True, "tag": True, "top": True,
                        "tags": ["COP", "ROBBER", "CHILL", "AFK"]},
             "spam": True,
             "welcome": "Welcome {name}! /cnr starts cops and robbers - robbers escape, cops bust them. /traps for the speed traps.",
             "messages": ["Cops: stay close to a robber to bust them.", "Robbers: get away and stay away until the time runs out."],
             "games": {"cnr": True, "race": True, "traps": True, "badges": True, "drift": False, "champ": False}, "laps": False,
             "search": "police"},
    "offroad": {"label": "Off-road", "map": "johnson_valley", "max_players": 10,
                "about": "Desert trails, dunes and rocks, timed trail runs, long AFK time",
                "extras": {"clear": True, "every": 12, "afk": True, "afk_minutes": 15, "countdown": True, "tag": True, "top": True,
                           "tags": ["CRAWL", "TRAIL", "DUNES", "AFK"]},
                "welcome": "Welcome {name}! Off-road server - find a trail, or time a run with /track. Stuck? Ask for a tow.",
                "messages": ["Set up a timed trail run with /track - /laps shows the best times."],
                "games": {"race": True, "traps": False, "badges": True, "cnr": False, "drift": False, "champ": False}, "laps": True,
                "search": "off-road"},
    "roleplay": {"label": "Roleplay", "map": "west_coast_usa", "max_players": 20,
                 "about": "Big city map, role tags, long AFK time, chat filter and anti-spam",
                 "extras": {"clear": True, "every": 24, "afk": True, "afk_minutes": 20, "countdown": False, "tag": True, "top": False,
                            "tags": ["COP", "EMS", "FIRE", "TOW", "TAXI", "CIV", "ROB"]},
                 "spam": True, "filter": True,
                 "welcome": "Welcome {name}! Roleplay server - pick your role with /tag (COP, EMS, TOW, TAXI, CIV...). Stay in character.",
                 "messages": ["Pick your role with /tag - type /tag to see them all.", "Respect other players' roleplay. Admins can mute and kick."],
                 "games": {"cnr": True, "race": False, "traps": True, "badges": False, "drift": False, "champ": False}, "laps": False,
                 "search": "police"},
    "chill": {"label": "Chill", "map": "italy", "max_players": 8,
              "about": "Scenic map for cruising with friends, relaxed rules",
              "extras": {"clear": True, "every": 24, "afk": False, "afk_minutes": 5, "countdown": True, "tag": True, "top": True,
                         "tags": ["CRUISE", "CHILL", "PHOTO", "AFK"]},
              "welcome": "Welcome {name}! Chill cruising server - enjoy the drive. Want a race? /race",
              "messages": ["Type /help to see the chat commands."],
              "games": {"race": True, "traps": True, "badges": True, "cnr": False, "drift": False, "champ": False}, "laps": False,
              "search": "car"},
}


# ----------------------------------------------------------------------------- config history + comparison
HIST_DIR = os.path.join(DATA_DIR, "config-history")
HIST_KEEP = 40


def _hist_dir(inst):
    return os.path.join(HIST_DIR, inst.id)


def save_config_version(inst, old, new, why=""):
    """Keep every version of ServerConfig.toml (the last 40), with who changed it."""
    if old == new:
        return
    d = _hist_dir(inst)
    os.makedirs(d, exist_ok=True)
    names = sorted(n for n in os.listdir(d) if n.endswith(".json"))
    if not names and old:                       # the very first change: keep what was there before
        write_json(os.path.join(d, "%d-0.json" % (now() - 1)), {"t": now() - 1, "who": "before", "why": "original", "text": redact_key(old)})
    who = getattr(_TL, "user", None) or "dashboard"
    write_json(os.path.join(d, "%d-%s.json" % (now(), secrets.token_hex(3))),
               {"t": now(), "who": who, "why": why[:120], "text": redact_key(new)})
    names = sorted(n for n in os.listdir(d) if n.endswith(".json"))
    for n in names[:-HIST_KEEP]:
        try:
            os.remove(os.path.join(d, n))
        except OSError:
            pass


_AUTHKEY_LINE = re.compile(r'''(?im)^(\s*authkey\s*=\s*)(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\n]*"|'[^'\n]*'|[^\s#]+)''')


def redact_key(text):
    """Blank the AuthKey whatever the quoting (\"..\", '..', triple quotes, bare) and the case of the name."""
    return _AUTHKEY_LINE.sub(r'\1""', text or "")


def config_versions(inst):
    d = _hist_dir(inst)
    out = []
    try:
        names = sorted((n for n in os.listdir(d) if n.endswith(".json")), reverse=True)
    except OSError:
        return []
    for n in names:
        v = read_json(os.path.join(d, n), None)
        if isinstance(v, dict) and isinstance(v.get("text"), str):
            out.append({"id": n[:-5], "t": v.get("t", 0), "who": v.get("who", ""), "why": v.get("why", ""), "text": v["text"]})
    return out


def flat_config(text):
    data, _, _ = toml_parse(text or "")
    out = {}
    for sec, vals in data.items():
        if isinstance(vals, dict):
            for k, v in vals.items():
                if k != "AuthKey":
                    out["%s.%s" % (sec, k)] = v
    return out


def config_diff(a_text, b_text):
    """What changed between two configs: setting by setting, plus the raw lines."""
    import difflib
    a, b = flat_config(a_text), flat_config(b_text)
    changes = []
    for k in sorted(set(a) | set(b)):
        if a.get(k, None) != b.get(k, None):
            changes.append({"key": k, "old": a.get(k), "new": b.get(k), "kind": "added" if k not in a else "removed" if k not in b else "changed"})
    lines = list(difflib.unified_diff(redact_key(a_text).splitlines(), redact_key(b_text).splitlines(), "before", "after", lineterm="", n=1))
    return {"changes": changes, "lines": lines[2:400]}


# ----------------------------------------------------------------------------- maintenance mode
def maintenance_cfg(inst):
    m = inst.meta.get("maintenance")
    d = {"on": False, "message": "The server is in maintenance - back soon!", "allow": [], "since": 0, "kick": True}
    if isinstance(m, dict):
        d.update({k: m[k] for k in d if k in m})
    return d


def write_maintenance_file(inst, cfg):
    lines = ["on" if cfg["on"] else "off", "message=" + re.sub(r"[\r\n]", " ", cfg["message"])[:200]]
    lines += [n for n in cfg["allow"]]
    shared_write(inst.MAINT_FILE, "\n".join(lines) + "\n")


def clone_server_files(src, dst):
    """Copy the dashboard-managed plugin files (who can join, moderation, bans, chat messages ...) to another server."""
    n = 0
    for attr in ("ALLOW_FILE", "VOTE_FILE", "EXTRAS_FILE", "MOD_FILE", "BANS_FILE", "MSG_FILE", "BRIDGE_FILE", "VERIFIED_FILE"):
        text = shared_read(getattr(src, attr), 4 * 1024 * 1024)
        if text:
            try:
                shared_write(getattr(dst, attr), text)
                n += 1
            except OSError as e:
                sys.stderr.write("clone %s: %s\n" % (attr, short_err(e)))
    return n


# ----------------------------------------------------------------------------- presets (security / style)
PRESETS = {
    "most_secure": {"label": "Most secure", "about": "Invite-only, hidden from the server list, accounts only, anti-bot with name check, "
                    "chat filter, anti-spam and flood protection. For a server only your friends should ever find.",
                    "config": {"Private": True, "AllowGuests": False},
                    "mod": {"antibot": True, "verify": True, "guests": False, "per_ip": 2, "join_flood": 4, "filter": True, "spam": True},
                    "allowlist": True, "flood": True},
    "public_safe": {"label": "Public but safe", "about": "Listed publicly, but guests can't join, new players must type a code once, "
                    "max 3 per internet connection, chat filter and anti-spam on.",
                    "config": {"Private": False, "AllowGuests": False},
                    "mod": {"antibot": True, "verify": True, "guests": False, "per_ip": 3, "join_flood": 8, "filter": True, "spam": True},
                    "allowlist": False, "flood": True},
    "friends": {"label": "Friends only", "about": "Hidden from the list and invite-only (allow-list), otherwise relaxed: no codes, no filter.",
                "config": {"Private": True, "AllowGuests": False},
                "mod": {"antibot": False, "guests": False, "filter": False, "spam": False},
                "allowlist": True, "flood": False},
    "open": {"label": "Open to everyone", "about": "Public, guests welcome, no extra checks - the most players, the least protection.",
             "config": {"Private": False, "AllowGuests": True},
             "mod": {"antibot": False, "guests": True, "filter": False, "spam": True},
             "allowlist": False, "flood": False},
    "low_end": {"label": "Weak computer", "about": "Fewer players and cars, abandoned cars removed fast - for old laptops and slow internet.",
                "config": {"MaxPlayers": 6, "MaxCars": 1},
                "extras": {"clear": True, "every": 2, "afk": True, "afk_minutes": 5}},
}


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


def event_sessions(evs, t_now):
    """(sessions [(name, start, end)], player-count samples [(t, n)]) from events.log lines."""
    sessions, open_s, samples = [], {}, []
    last_t = None
    t = t_now
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
    return [(n, a, max(a, b)) for n, a, b in sessions], samples


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
_HOST = {"t": 0.0, "v": {}}


def host_info():
    """What the Mac installer tells us when this Linux runs in a small VM on a Mac (host.json, refreshed by the
    Mac's login agent): {"platform": "mac", "lan_ip": "<the Mac's address>", "ports": "auto|manual|later",
    "upnp": "ok|failed|off", "upnp_at": <time>, "upnp_error": "..."}. Empty everywhere else."""
    if time.time() - _HOST["t"] > 30:
        try:
            with open(HOST_FILE, encoding="utf-8") as f:
                v = json.load(f)
            _HOST["v"] = v if isinstance(v, dict) else {}
        except (OSError, ValueError):
            _HOST["v"] = {}
        _HOST["t"] = time.time()
    return _HOST["v"]


def on_mac():
    return host_info().get("platform") == "mac"


# On a Mac every visitor reaches the dashboard through the Mac's port forwarder and looks like a home device,
# so "only from the internet with two-step login" can't be enforced there: internet logins stay off.
MAC_NO_REMOTE = "Logging in from the internet isn't available on a Mac yet - team members can log in from your home network."


def mac_lan_ip():
    ip = str(host_info().get("lan_ip") or "")
    try:
        return ip if ipaddress.ip_address(ip).version == 4 else None
    except ValueError:
        return None


def lan_ip():
    if on_mac() and mac_lan_ip():
        return mac_lan_ip()     # players reach the Mac, which forwards to this VM
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
    return duck_host() or public_ip() or lan_ip(), port, False


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
    if any(x["state"] == "ok" and (x["name"].startswith("Reachable") or x["name"] == "Public server list") for x in checks):
        reach = dict(APP.state.get("reach_ok") or {})
        reach[I().id] = now()
        APP.state.update({"reach_ok": reach})
    if relay_on():
        pip = None      # don't show the home address on a page that's about the relay
    return {"port": port, "lan_ip": lip, "public_ip": pip, "checks": checks, "tips": tips,
            "relay": fmt_addr(*game_address()[:2]) if relay_on() else None}


# ----------------------------------------------------------------------------- health report
HEALTH_ORDER = {"fail": 0, "warn": 1, "info": 2, "pass": 3}


def internet_ok():
    for host, port in (("1.1.1.1", 443), ("8.8.8.8", 53), ("9.9.9.9", 443)):
        if tcp_open(host, port, timeout=3):
            return True
    return False


def beammp_backend_ok():
    try:
        req = urllib.request.Request("https://backend.beammp.com/servers-info", method="HEAD",
                                     headers={"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
        with urllib.request.urlopen(req, timeout=10):
            return True
    except urllib.error.HTTPError as e:
        return e.code < 500                  # it answered
    except Exception:
        return False


HEALTH_GO = {"process": "overview", "port": "logs", "config": "config", "authkey": "config", "plugin": "logs", "mods": "mods",
             "external": "network", "disk": "", "memory": "", "moved": "servers", "backups": "settings", "join": "mods"}


def health_report(deep=False):
    """Plain-language checks for the selected server: pass / warn / fail, each with what to do."""
    inst = I()
    checks = []

    def c(cid, title, state, detail, fix=""):
        checks.append({"id": cid, "title": title, "state": state, "detail": detail, "fix": fix, "go": HEALTH_GO.get(cid, "")})

    st = inst.server.status()
    running = st.get("state") == "running"
    data, _, _ = toml_parse(APP.read_config_text())
    g = data.get("General", {})
    port = g.get("Port") if isinstance(g.get("Port"), int) else 30814
    # 1. internet
    net = internet_ok()
    c("internet", "Internet connectivity", "pass" if net else "fail",
      "This computer is online." if net else "This computer can't reach the internet.",
      "" if net else "Check the network cable / Wi-Fi and the router. Friends on your home network can still play.")
    if net:
        be = beammp_backend_ok()
        c("backend", "BeamMP services", "pass" if be else "warn",
          "BeamMP's server list and login service answer." if be else "BeamMP's servers don't answer right now.",
          "" if be else "Usually a BeamMP outage - check beammp.com or their Discord. Your server keeps running; "
                        "it may be missing from the server list until it's back.")
    # 2. the server process
    if running:
        c("process", "BeamMP server process", "pass", "Running for %s." % fmt_secs(st.get("uptime") or 0) if st.get("uptime") else "Running.")
    elif st.get("state") == "failed":
        c("process", "BeamMP server process", "fail", "The server crashed or couldn't start.",
          "Open Logs - the hints there explain the most common reasons (AuthKey, port in use, broken mod).")
    else:
        c("process", "BeamMP server process", "warn", "The server is stopped.", "Press Start on the Overview page.")
    if running:
        tcp, udp = listening(port)
        c("port", "Game port %d" % port, "pass" if (tcp and udp) else "fail",
          "Open for TCP and UDP." if (tcp and udp) else "TCP %s, UDP %s." % ("open" if tcp else "closed", "open" if udp else "closed"),
          "" if (tcp and udp) else "Another program may use the port, or the server is still starting. Check Logs.")
    # 3. config + key
    _, issues = validate_config(APP.read_config_text(), APP.settings.get("port"), inst.has_authkey())
    errs = [i for i in issues if i.get("level") == "error"]
    c("config", "Server settings", "fail" if errs else "pass",
      ("%d problem%s in the settings: %s" % (len(errs), "" if len(errs) == 1 else "s", "; ".join(i.get("message", "") for i in errs[:3])))
      if errs else "The server settings are valid.", "Open Config - the problems are marked there." if errs else "")
    c("authkey", "AuthKey", "pass" if inst.has_authkey() else "fail",
      "Set (stored encrypted)." if inst.has_authkey() else "No AuthKey - the server can't start or show up in the list.",
      "" if inst.has_authkey() else "Get a free key at keymaster.beammp.com and paste it under Config → AuthKey.")
    # 4. our plugin
    plug = os.path.exists(os.path.join(inst.STATS_DIR, "main.lua"))
    online = read_json(os.path.join(inst.STATS_DIR, "online.json"), None)
    fresh = isinstance(online, dict) and now() - int(online.get("t", 0)) < 120
    lua_errors = []
    lines, _ = tail_log(400)
    for line in lines:
        if re.search(r"(?i)\[LUA\].*error|lua error|\[LUA ERROR\]", line):
            lua_errors.append(line.strip()[-200:])
    if not plug:
        c("plugin", "Plugin loading", "fail", "The EasyServer plugin is missing from Resources/Server/EasyServerStats.",
          "Run the installer again (it puts the plugin back). Statistics, the allow-list, moderation and messages need it.")
    elif running and not fresh:
        c("plugin", "Plugin loading", "warn", "The server is running but the EasyServer plugin isn't reporting.",
          "If the server just started, wait a minute. Otherwise check Logs for Lua errors - another plugin may be breaking it.")
    elif lua_errors:
        c("plugin", "Plugin loading", "warn", "%d Lua error%s in the log, e.g.: %s" % (len(lua_errors), "" if len(lua_errors) == 1 else "s", lua_errors[-1]),
          "A server plugin in Resources/Server has an error. Fix or remove that plugin, then restart.")
    else:
        c("plugin", "Plugin loading", "pass", "The EasyServer plugin is loaded%s." % (" and reporting" if running else ""))
    # 5. mods
    mods = list_mods()
    on = [m for m in mods if m["enabled"]]
    bad = [m for m in on if m["safety"] == "blocked"]
    broken = [m["name"] for m in on if not zipfile.is_zipfile(os.path.join(inst.CLIENT_DIR, m["name"]))]
    mapname = str(g.get("Map") or "").replace("/levels/", "").replace("/info.json", "").strip("/")
    map_ok = (not mapname) or mapname in BUILTIN_MAPS or mapname in enabled_mod_maps()
    total = sum(m["size"] for m in on)
    problems = []
    if bad:
        problems.append("blocked by the virus check: " + ", ".join(m["name"] for m in bad[:3]))
    if broken:
        problems.append("damaged zip files: " + ", ".join(broken[:3]))
    if not map_ok:
        problems.append("the map \"%s\" isn't built in and no enabled mod contains it" % mapname)
    if problems:
        c("mods", "Mod configuration", "fail", "; ".join(problems).capitalize() + ".",
          "Open Mods: remove or replace the listed files, or pick another map under Config.")
    elif total > 2 * 1024 ** 3:
        c("mods", "Mod configuration", "warn", "%d mods, %s to download before joining - slow connections may time out." % (len(on), fmt_bytes(total)),
          "Turn off mods you don't need (Mods page), or tell players to be patient on the first join.")
    else:
        c("mods", "Mod configuration", "pass", "%d mod%s on, %s to download, map OK." % (len(on), "" if len(on) == 1 else "s", fmt_bytes(total)))
    # 6. reachable from outside
    if relay_on():
        rhost, rport, _ = game_address()
        if running:
            ok = tcp_open(rhost, rport, timeout=5)
            c("external", "External connectivity", "pass" if ok else "fail",
              "Players can reach the server through the relay." if ok else "Nothing answers at the relay address.",
              "" if ok else "Check that the relay (playit.gg / VPN / VPS tunnel) is running - Network page has details.")
    elif net and running:
        pip = public_ip()
        reach = bool(pip) and tcp_open(pip, port, timeout=4)
        listed = None
        if deep and pip and g.get("Private") is not True:
            try:
                listed = server_list_lookup(pip, port)["listed"]
            except Exception:
                listed = None
        if reach or listed:
            c("external", "External connectivity", "pass", "The server can be reached from the internet%s." % (
                " and is in the server list" if listed else ""))
        elif listed is False:
            c("external", "External connectivity", "fail", "The server isn't in the BeamMP server list.",
              "Check the port forward (TCP and UDP %d to %s) and the AuthKey. Wait 2 minutes after starting." % (port, lan_ip()))
        else:
            c("external", "External connectivity", "warn",
              "Couldn't confirm from inside your home - many routers block this test even when it works.",
              "Press Full check (it looks for your server in the BeamMP list), or ask a friend to join.")
    # 7. the computer
    try:
        du = shutil.disk_usage(inst.SERVER_DIR)
        free = du.free
        c("disk", "Disk space", "fail" if free < 1024 ** 3 else "warn" if free < 5 * 1024 ** 3 else "pass",
          "%s free." % fmt_bytes(free), "Free up space - logs, backups and mods need room." if free < 5 * 1024 ** 3 else "")
    except OSError:
        pass
    tot, avail = sys_mem()
    if tot and avail is not None:
        pct = 100.0 * avail / tot
        c("memory", "Memory", "warn" if pct < 10 else "pass", "%d%% free (%s of %s)." % (pct, fmt_bytes(avail * 1048576), fmt_bytes(tot * 1048576)),
          "Close other programs or lower the player limit." if pct < 10 else "")
    # 9. moved away, backups, how long joining takes
    if moved_note(inst):
        c("moved", "Moved to another computer", "warn", moved_note(inst) + ". The dashboard keeps it off here.",
          "Nothing to do. To run it on this computer as well, press Start and confirm.")
    s = APP.settings
    last = APP.state.get("backup_copy") or {}
    if not s.get("backup_on"):
        c("backups", "Backups", "warn", "Nightly backups are off.", "Turn on Back up every night under Settings → Automatic backups.")
    elif not s.get("backup_copy") and not (s.get("gdrive_on") and gdrive_connected()):
        c("backups", "Backups", "warn", "The backups are only on this computer - if its disk dies, they're gone too.",
          "Settings → Automatic backups: connect Google Drive, or keep a copy on a USB drive or another computer at home.")
    elif s.get("gdrive_on") and gdrive_connected() and not (APP.state.get("gdrive_last") or {"ok": True}).get("ok"):
        c("backups", "Backups", "warn", "The last copy to Google Drive failed: %s" % APP.state["gdrive_last"].get("note"),
          "Look at Settings → Google Drive - you may need to connect it again.")
    elif s.get("backup_copy") and last and not last.get("ok"):
        c("backups", "Backups", "warn", "The last copy of the backups failed: %s" % last.get("note"),
          "Check the place under Settings → Automatic backups (is the USB drive plugged in?).")
    else:
        c("backups", "Backups", "pass", "Nightly backups, with a copy kept somewhere else.")
    up = float(s.get("upload_mbit") or 0) * 1000
    lim = int((inst.meta.get("limits") or {}).get("upload_kbps") or 0)
    kbps = min(up, lim) if up and lim else up or lim
    if total and kbps:
        secs = total * 8 / (kbps * 1000.0)
        slow = secs > 300
        c("join", "Joining time", "warn" if slow else "pass",
          "A new player waits about %s for the mods (%s at %.1f Mbit/s)." % (fmt_secs(int(secs)), fmt_bytes(total), kbps / 1000.0),
          "Turn off mods you don't need or use light mode (Mods page) - players often give up after a few minutes." if slow else "")
    elif total and not up:
        c("join", "Joining time", "warn", "Your upload speed isn't entered, so joining time and upload warnings are unknown.",
          "Run a speed test on this computer and enter the upload number under Settings → Computer load.")
    checks.sort(key=lambda x: HEALTH_ORDER.get(x["state"], 9))
    worst = checks[0]["state"] if checks else "pass"
    return {"t": now(), "server": inst.name, "overall": worst, "checks": checks, "deep": bool(deep),
            "failed": sum(1 for x in checks if x["state"] == "fail"), "warned": sum(1 for x in checks if x["state"] == "warn")}


DIAG_DIR = os.path.join(DATA_DIR, "diagnostics")


def save_diagnostic_report(inst_id, text):
    os.makedirs(DIAG_DIR, exist_ok=True)
    name = "diagnostics-%s-%s.txt" % (inst_id, time.strftime("%Y%m%d-%H%M%S"))
    with open(os.path.join(DIAG_DIR, name), "w", encoding="utf-8") as f:
        f.write(text)
    old = sorted(n for n in os.listdir(DIAG_DIR) if n.startswith("diagnostics-"))
    for n in old[:-10]:                      # keep the last 10
        try:
            os.remove(os.path.join(DIAG_DIR, n))
        except OSError:
            pass
    return name


def list_diagnostic_reports(inst_id):
    try:
        names = sorted((n for n in os.listdir(DIAG_DIR) if n.startswith("diagnostics-%s-" % inst_id)), reverse=True)
    except OSError:
        return []
    return [{"file": n, "t": int(os.path.getmtime(os.path.join(DIAG_DIR, n)))} for n in names]


_REDACT = [
    (re.compile(r"https://(?:\w+\.)?discord(?:app)?\.com/api/webhooks/\S+"), "[discord webhook]"),
    (re.compile(r"[A-Za-z0-9_\-]{20,100}\.[A-Za-z0-9_\-]{4,20}\.[A-Za-z0-9_\-]{20,100}"), "[token]"),
    (_AUTHKEY_LINE, r'\1"[hidden]"'),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "[key]"),
    (re.compile(r"beammp-(?:wake-)?[A-Za-z0-9_\-]{16,}"), "[topic]"),
]
_IPV4 = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])")


def redact(text):
    for rx, rep in _REDACT:
        text = rx.sub(rep, text)

    def ip(m):
        try:
            a = ipaddress.ip_address(m.group(0))
        except ValueError:
            return m.group(0)
        return m.group(0) if (a.is_private or a.is_loopback or a.is_unspecified) else "[public ip]"
    return _IPV4.sub(ip, text)


def diagnostic_report():
    """A text file to share when asking for help: versions, the health checks, the network test,
    settings and the end of the log - with keys, tokens and public IP addresses removed."""
    inst = I()
    out = []
    w = out.append
    w("BeamMP EasyServer diagnostic report")
    w("Created: %s" % time.strftime("%Y-%m-%d %H:%M:%S %z"))
    w("EasyServer %s, Python %s, %s" % (EASY_VERSION, sys.version.split()[0], sys.platform))
    try:
        import platform
        w("System: %s %s (%s)" % (platform.system(), platform.release(), platform.machine()))
    except Exception:
        pass
    w("Server: %s (id %s), BeamMP %s" % (inst.name, inst.id, inst.server.installed_version() or "?"))
    w("")
    h = health_report(deep=True)
    w("== Health checks ==")
    for x in h["checks"]:
        w("[%s] %s: %s%s" % (x["state"].upper(), x["title"], x["detail"], (" -> " + x["fix"]) if x["fix"] else ""))
    w("")
    try:
        data, _, _ = toml_parse(APP.read_config_text())
        n = network_check(data, inst.server.status(), False)
        w("== Network ==")
        for x in n["checks"]:
            w("[%s] %s: %s" % (x["state"].upper(), x["name"], x["detail"]))
        for t in n["tips"]:
            w("tip: " + t)
        w("")
    except Exception as e:
        w("network check failed: %s" % short_err(e))
    w("== ServerConfig.toml ==")
    w(APP.read_config_text())
    w("")
    w("== Mods ==")
    for m in list_mods():
        w("%s %s %s (%s)%s" % ("ON " if m["enabled"] else "off", m["name"], fmt_bytes(m["size"]), m["safety"],
                               (" maps: " + ", ".join(m["maps"])) if m["maps"] else ""))
    w("")
    s = APP.settings.public()
    keep = ("port", "https", "remote_enabled", "relay_enabled", "flood_protect", "auto_restart", "auto_update",
            "discord_bot", "discord_bridge", "discord_status_msg", "backup_on", "sleep_on", "sleep_idle", "ntfy_enabled")
    w("== Dashboard settings ==")
    w(json.dumps({k: s.get(k) for k in keep}, sort_keys=True))
    w("")
    w("== Recent notifications ==")
    with LOCK:
        items = list(APP.notifier.items[:30])
    for it in items:
        w("%s [%s] %s - %s" % (time.strftime("%m-%d %H:%M", time.localtime(it["t"])), it["level"], it["title"], it["message"][:300]))
    w("")
    w("== Server log (last 500 lines) ==")
    lines, hints = tail_log(500)
    for hnt in hints:
        w("hint: %s - %s" % (hnt["title"], hnt["text"]))
    out.extend(lines)
    return redact("\n".join(out)) + "\n"


def connection_doctor(player):
    """Why can't <player> join? Looks at what the server recorded for that name and the usual causes."""
    inst = I()
    player = clean_player_name(player or "")[:40] if player else ""
    findings = []

    def f(state, title, text):
        findings.append({"state": state, "title": title, "text": text})

    st = inst.server.status()
    data, _, _ = toml_parse(APP.read_config_text())
    g = data.get("General", {})
    port = g.get("Port") if isinstance(g.get("Port"), int) else 30814
    if st.get("state") != "running":
        f("fail", "The server isn't running", "Nobody can join until it's started (Overview → Start).")
    maxp = g.get("MaxPlayers") if isinstance(g.get("MaxPlayers"), int) else 8
    online = online_names()
    if len(online) >= maxp:
        f("fail", "The server is full", "%d of %d players are online. Raise Max players under Config or wait for a free slot." % (len(online), maxp))
    if isinstance(inst.meta.get("maintenance"), dict) and inst.meta["maintenance"].get("on"):
        f("warn", "Maintenance mode is on", "Only admins and the players on the maintenance list can join.")
    reasons = {"banned": ("They're banned", "Unban them under Players → Ban list."),
               "name": ("Their name was blocked by the chat filter", "Their name contains a link, @everyone or a blocked word."),
               "guest": ("Guests aren't allowed", "They have to log in with a BeamMP account (or allow guests under Config → Moderation)."),
               "per_ip": ("Too many players from the same internet connection", "Raise 'players per address' under Config → Moderation."),
               "maintenance": ("Maintenance mode refused them", "Add them to the maintenance list or end maintenance."),
               "denied": ("They're not on the allow-list", "Add them under Config → Who can join (or turn the list off)."),
               "joinflood": ("Join-flood protection was active", "Lots of new players joined at once; it lifts after 2 minutes.")}
    if player:
        evs = [e for e in read_events(now() - 7 * 86400)]
        mine = [e for e in evs if str(e.get("name", "")).lower() == player.lower()]
        tried = [e for e in mine if e.get("ev") in ("refused", "denied")]
        joined = [e for e in mine if e.get("ev") == "join"]
        if tried:
            last = tried[-1]
            why = "denied" if last.get("ev") == "denied" else str(last.get("why") or "")
            title, fix = reasons.get(why, ("The server refused them (%s)" % why, ""))
            f("fail", title, "Last time %s. %s" % (ago_text(last["t"]), fix))
        elif joined:
            f("info", "%s has joined before" % player, "Last join %s - the server lets them in. If they can't now, it's their "
              "connection or game (see the tips below)." % ago_text(joined[-1]["t"]))
        else:
            f("warn", "No attempt from %s reached the server" % player,
              "The server never saw them in the last 7 days. Their connection doesn't arrive - check the address they use "
              "and the port forward (below).")
        hits = []
        lines, _ = tail_log(2000)
        for line in lines:
            if player.lower() in line.lower():
                hits.append(line.strip()[-220:])
        if hits:
            f("info", "Server log lines about %s" % player, "\n".join(hits[-8:]))
    # common network causes
    rhost, rport, _ = game_address()
    if relay_on():
        f("info", "The address to give friends", "%s (through your relay)." % fmt_addr(rhost, rport))
    else:
        pip = public_ip()
        dom = duck_host()
        f("info", "The address to give friends", "%s%s. Friends at your home use %s:%d instead." % (
            fmt_addr(dom or pip or "your public IP", port), (" (or %s)" % fmt_addr(pip, port)) if dom and pip else "", lan_ip(), port))
        if pip and ipaddress.ip_address(pip) in ipaddress.ip_network("100.64.0.0/10"):
            f("fail", "Your internet uses CGNAT", "Port forwarding can't work - ask your provider for a public IPv4 address, or use a relay (Settings → Hide your IP).")
        elif st.get("state") == "running" and pip and not tcp_open(pip, port, timeout=4):
            f("warn", "Port forwarding not confirmed", "Forward TCP and UDP port %d on your router to %s. (Some routers block this test even when it works.)" % (port, lan_ip()))
    total = sum(m["size"] for m in list_mods() if m["enabled"])
    if total > 1024 ** 3:
        f("info", "Big mod download", "Players download %s of mods before joining. On slow internet the first join can time out - "
          "they should simply try again; finished downloads are kept." % fmt_bytes(total))
    f("info", "On their side", "Same BeamMP version as everyone (update the launcher), BeamNG.drive is up to date, and their "
      "antivirus/firewall isn't blocking BeamMP. Restarting the launcher fixes most 'stuck on loading' problems.")
    return {"player": player, "findings": findings}


def ago_text(t):
    d = now() - t
    return "just now" if d < 60 else "%d min ago" % (d // 60) if d < 3600 else "%d h ago" % (d // 3600) if d < 86400 else "%d days ago" % (d // 86400)


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


def update_channel():
    """"experimental" = also hear about newer versions than Stable: the Rolling release (free mode, anyone who
    picks it) or Experimental versions (paid mode, a supporter perk). Everyone else gets Stable."""
    if not PAID_FEATURES:
        return "experimental" if APP.settings.get("rolling") else "stable"
    return "experimental" if supporter_active() and APP.settings.get("early_access") else "stable"


EXPERIMENTAL_INFO = "https://csabika-dev.github.io/beammp-easyserver/experimental.json"
SUPPORTER_DOWNLOADS = "https://app.lemonsqueezy.com/my-orders"


ROLLING_RAW = "https://raw.githubusercontent.com/%s/main/dashboard/dashboard.py"
ROLLING_ZIP = "https://github.com/%s/archive/refs/heads/main.zip"


def rolling_version(repo):
    """The Rolling release (newest code on main, free for everyone), as (version, where to download it)."""
    req = urllib.request.Request(ROLLING_RAW % repo, headers={"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
    with urllib.request.urlopen(req, timeout=20) as r:
        head = r.read(16 * 1024).decode("utf-8", "replace")
    m = re.search(r'^EASY_VERSION = "(\d+\.\d+\.\d+)"', head, re.M)
    return (m.group(1), ROLLING_ZIP % repo) if m else None


def github_prerelease(repo):
    """The newest version past Stable, as (version, where to download it): the Rolling release when
    EasyServer is fully free, otherwise the newest Experimental version (supporters only).
    Experimental builds aren't public on GitHub; the website just says which one is out, and
    supporters download it from their Lemon Squeezy order."""
    if not PAID_FEATURES:
        return rolling_version(repo)
    req = urllib.request.Request(EXPERIMENTAL_INFO, headers={"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
    with urllib.request.urlopen(req, timeout=20) as r:
        info = json.loads(r.read(64 * 1024))
    v = str(info.get("version") or "") if isinstance(info, dict) else ""
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        return None
    return v, SUPPORTER_DOWNLOADS


# ----------------------------------------------------------------------------- supporter licence (Lemon Squeezy)
def ls_call(action, **fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(LS_API + action, data=data, method="POST",
                                 headers={"Accept": "application/json", "User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read(256 * 1024))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read(64 * 1024))
        except ValueError:
            raise RuntimeError("Lemon Squeezy answered %d" % e.code)


def ls_summary(d):
    """What we keep about a licence (no personal data beyond a masked email)."""
    lk, meta = d.get("license_key") or {}, d.get("meta") or {}
    mail = str(meta.get("customer_email") or "")
    if "@" in mail:
        u, _, dom = mail.partition("@")
        mail = u[:2] + "***@" + dom
    return {"status": str(lk.get("status") or ""), "expires_at": lk.get("expires_at"),
            "plan": clean_msg(" - ".join(x for x in (str(meta.get("product_name") or ""), str(meta.get("variant_name") or "")) if x and x != "Default"))[:80],
            "store_id": meta.get("store_id"), "email": mail[:80]}


def supporter_active():
    sup = APP.settings.get("supporter") or {} if APP else {}
    if not sup.get("instance_id") or not APP.secrets.has("SUPPORTER_KEY"):
        return False
    if sup.get("status") not in ("active",):
        return False
    return now() - (sup.get("ok_at") or 0) < SUPPORTER_GRACE


# ----------------------------------------------------------------------------- logs + hints
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
        x = explain_line(line)
        if x and x["id"] not in seen and not x["id"].startswith("unknown") and x["level"] != "info":
            seen.add(x["id"])
            hints.append({"title": x["title"], "text": x["what"] + " " + x["fix"], "line": line[-300:]})
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


def at_server(ip):
    """True when the request really comes from the server computer itself. On a Mac the server runs in a
    small VM and EVERY connection (other devices included) arrives through the Mac's port forwarder as
    127.0.0.1 - so there, a local address proves nothing and gets no special trust."""
    return ip_is_loopback(ip) and not on_mac()


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


# ----------------------------------------------------------------------------- backups
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
BACKUP_KEEP = 7
STATS_EXPORT = ("allowlist.txt", "extras.txt", "moderation.txt", "bans.txt", "messages.txt")
# a move also takes the stats, lap times, championships, drift and race results the plugin keeps
GAMES_RE = re.compile(r"[\w.-]{1,64}\.(?:tsv|txt|log|json)")
GAMES_SKIP = {"bridge.txt", "online.json", "livemap.txt", "livemap.json"}
GAMES_MAX = 64 * 1024 ** 2


def games_name_ok(name):
    return bool(GAMES_RE.fullmatch(name)) and name not in GAMES_SKIP and name not in STATS_EXPORT


def build_export(path, include_mods, include_games=False):
    """A settings (and optionally mods) zip of the current server - used by Export and nightly backups."""
    app = APP
    text = app.read_config_text()
    text = toml_set(text, "General", "AuthKey", "") if "AuthKey" in text else text
    mods = list_mods()
    meta = {"format": "beammp-easyserver-export", "version": 1, "easy_version": EASY_VERSION,
            "exported_at": now(), "server_name": server_name(),
            "settings": {k: v for k, v in app.settings.public().items()
                         if k in ("notify", "smtp_host", "smtp_port", "smtp_security", "smtp_user",
                                  "smtp_from", "smtp_to", "auto_restart", "update_check",
                                  "discord_enabled", "email_enabled")},
            "server_meta": {k: v for k, v in I().meta.items() if k in ("restart", "rotation")},
            "mods": [{"name": m["name"], "enabled": m["enabled"], "size": m["size"]} for m in mods],
            "includes_mods": include_mods, "includes_games": include_games}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("ServerConfig.toml", text)
        z.writestr("easyserver-export.json", json.dumps(meta, indent=1))
        # files from the server's folders are opened without following
        # links, so a hacked game server can't slip the dashboard's own
        # files (like its HTTPS key) into your backup
        for name in STATS_EXPORT:
            try:
                with open_shared(os.path.join(I().STATS_DIR, name)) as f:
                    z.writestr(name, f.read(256 * 1024))
            except OSError:
                pass
        if include_games:
            try:
                names = sorted(os.listdir(I().STATS_DIR))
            except OSError:
                names = []
            for name in names:
                if not games_name_ok(name):
                    continue
                try:
                    with open_shared(os.path.join(I().STATS_DIR, name), "rb") as f:
                        data = f.read(GAMES_MAX + 1)
                except OSError:
                    continue
                if len(data) <= GAMES_MAX:
                    z.writestr("games/" + name, data)
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


def list_backups(iid=None):
    out = []
    try:
        names = os.listdir(BACKUP_DIR)
    except OSError:
        return out
    for n in names:
        m = re.fullmatch(r"([a-z0-9]{1,12})-(\d{8}-\d{4}(?:\d{2})?)(-mods)?\.zip", n)
        if not m or (iid and m.group(1) != iid):
            continue
        try:
            st = os.stat(os.path.join(BACKUP_DIR, n))
        except OSError:
            continue
        out.append({"file": n, "server": m.group(1), "size": st.st_size, "t": int(st.st_mtime), "mods": bool(m.group(3))})
    return sorted(out, key=lambda b: -b["t"])


def make_backup(inst, include_mods):
    use_server(inst.id)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if not IS_WIN:
        os.chmod(BACKUP_DIR, 0o700)
    name = "%s-%s%s.zip" % (inst.id, time.strftime("%Y%m%d-%H%M"), "-mods" if include_mods else "")
    if os.path.exists(os.path.join(BACKUP_DIR, name)):    # two in the same minute (a restore right after a backup)
        name = "%s-%s%s.zip" % (inst.id, time.strftime("%Y%m%d-%H%M%S"), "-mods" if include_mods else "")
    tmp = os.path.join(BACKUP_DIR, name + ".tmp")
    build_export(tmp, include_mods)
    os.replace(tmp, os.path.join(BACKUP_DIR, name))
    for old in list_backups(inst.id)[BACKUP_KEEP:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old["file"]))
        except OSError:
            pass
    return name


# ----------------------------------------------------------------------------- DuckDNS
DUCK_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def duck_host():
    d = (APP.settings.get("duckdns_domain") or "") if APP else ""
    return (d + ".duckdns.org") if d and APP.secrets.has("DUCKDNS_TOKEN") else ""


def duckdns_update(domain, token, ip=""):
    url = "https://www.duckdns.org/update?" + urllib.parse.urlencode({"domains": domain, "token": token, "ip": ip})
    req = urllib.request.Request(url, headers={"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read(64).decode("ascii", "replace").strip() == "OK"


# ----------------------------------------------------------------------------- computer load (low-resource warnings)
_cpu_prev = None


def sys_cpu_percent():
    """Whole-computer CPU use since the last call (None on the first call)."""
    global _cpu_prev
    try:
        if IS_WIN:
            import ctypes
            idle, kern, user = (ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_ulonglong())
            if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
                return None
            cur = (idle.value, kern.value + user.value)        # kernel time includes idle time
        else:
            with open("/proc/stat") as f:
                v = [int(x) for x in f.readline().split()[1:]]
            cur = (v[3] + (v[4] if len(v) > 4 else 0), sum(v[:8]))
    except Exception:
        return None
    prev, _cpu_prev = _cpu_prev, cur
    if not prev or cur[1] <= prev[1]:
        return None
    return round(100.0 * (1 - (cur[0] - prev[0]) / float(cur[1] - prev[1])), 1)


def sys_mem():
    """(total MB, available MB) or (None, None)."""
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
                return m.ullTotalPhys // 1048576, m.ullAvailPhys // 1048576
            return None, None
        with open("/proc/meminfo") as f:
            t = f.read()
        tot = re.search(r"MemTotal:\s+(\d+)", t)
        av = re.search(r"MemAvailable:\s+(\d+)", t)
        return (int(tot.group(1)) // 1024 if tot else None), (int(av.group(1)) // 1024 if av else None)
    except Exception:
        return None, None


_net_prev = None


def sys_upload_kbps():
    """Bytes this computer sent per second (all network cards) since the last call, in kbit/s."""
    global _net_prev
    sent = None
    try:
        if IS_WIN:
            out = subprocess.run(["netstat", "-e"], capture_output=True, text=True, timeout=10,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            for line in out.splitlines():
                nums = re.findall(r"\d+", line)
                if len(nums) == 2 and re.match(r"\s*Bytes", line):
                    sent = int(nums[1])
                    break
        else:
            with open("/proc/net/dev") as f:
                rows = f.read().splitlines()[2:]
            sent = sum(int(r.split(":", 1)[1].split()[8]) for r in rows if ":" in r and r.split(":")[0].strip() != "lo")
    except Exception:
        return None
    if sent is None:
        return None
    t = time.time()
    prev, _net_prev = _net_prev, (t, sent)
    if not prev or t <= prev[0] or sent < prev[1]:
        return None
    return round((sent - prev[1]) * 8 / 1000.0 / (t - prev[0]), 1)


# ----------------------------------------------------------------------------- mod updates (BeamNG repository)
# Mods from the BeamNG repository carry mod_info/<id>/info.json with their
# repository id and version. The public mod page shows the newest version.
REPO_PAGE = "https://www.beamng.com/resources/%d/"
REPO_DL = "https://www.beamng.com/resources/%d/download?version=%d"


def mod_repo_info(path):
    try:
        with zipfile.ZipFile(path) as z:
            for zi in z.infolist()[:20000]:
                m = re.fullmatch(r"/?mod_info/([0-9A-Za-z]{1,24})/info\.json", zi.filename)
                if not m or zi.file_size > 2 * 1024 * 1024:
                    continue
                d = json.loads(z.read(zi).decode("utf-8", "replace"))
                rid = int(d.get("resource_id") or 0)
                vid = int(d.get("resource_version_id") or d.get("current_version_id") or 0)
                if rid > 0 and vid > 0:
                    return {"tagid": m.group(1), "resource_id": rid, "version_id": vid,
                            "version": clean_msg(d.get("version_string"))[:40],
                            "title": clean_msg(re.sub(r"\[/?\w+[^\]]*\]", "", str(d.get("title") or "")))[:120]}
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError):
        pass
    return None


def repo_latest(rid):
    req = urllib.request.Request(REPO_PAGE % rid, headers={"User-Agent": "BeamMP-EasyServer/%s (mod update check)" % EASY_VERSION})
    with urllib.request.urlopen(req, timeout=25) as r:
        html = r.read(3 * 1024 * 1024).decode("utf-8", "replace")
        url = r.geturl()
    vids = [int(v) for v in re.findall(r"/download\?version=(\d+)", html)]
    if not vids:
        return None
    ver = re.search(r"<h1[^>]*>.*?<span class=\"muted\">\s*([^<]{1,40}?)\s*</span>", html, re.S)
    return {"version_id": max(vids), "version": clean_msg(ver.group(1)) if ver else "", "url": url.split("?")[0]}


def mod_updates_for(inst, force=False):
    """{mod name: {...}} for this server's repository mods; cached per file and per mod page."""
    use_server(inst.id)
    cache = APP.state.setdefault("mod_repo", {})
    out, t = {}, now()
    for m in list_mods():
        p = os.path.join(inst.CLIENT_DIR if m["enabled"] else inst.DISABLED_DIR, m["name"])
        try:
            st = os.stat(p)
        except OSError:
            continue
        key = "%s|%d|%d" % (m["name"], st.st_size, int(st.st_mtime))
        info = cache.get("f:" + key)
        if info is None:
            info = mod_repo_info(p) or {}
            cache["f:" + key] = info
        if not info:
            continue
        rk = "r:%d" % info["resource_id"]
        lat = cache.get(rk)
        if force or not lat or t - lat.get("t", 0) > 12 * 3600:
            try:
                lat = dict(repo_latest(info["resource_id"]) or {}, t=t)
            except Exception as e:
                lat = dict(lat or {}, t=t, err=short_err(e))
            cache[rk] = lat
            time.sleep(1)                      # be polite to beamng.com
        newer_v = lat.get("version_id", 0) > info["version_id"]
        out[m["name"]] = {"title": info["title"], "have": info["version"], "have_id": info["version_id"],
                          "latest": lat.get("version") or "", "latest_id": lat.get("version_id"),
                          "update": bool(newer_v), "page": lat.get("url") or REPO_PAGE % info["resource_id"],
                          "resource_id": info["resource_id"], "enabled": m["enabled"], "error": lat.get("err")}
    for k in [k for k in cache if k.startswith("f:") and k[2:].split("|")[0] not in {m["name"] for m in list_mods()}]:
        cache.pop(k, None)
    return out


def apply_mod_update(name, u):
    """Download the newest version of one repository mod of the current server, virus-check it and replace the
    old file. Returns (200, {"version"}) or (an HTTP status, {"error"} / {"blocked", "reasons"})."""
    url = REPO_DL % (u["resource_id"], u["latest_id"])
    tdir = tempfile.mkdtemp(dir=UPLOAD_TMP, prefix=".up-")
    tmp = os.path.join(tdir, name)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BeamMP-EasyServer/%s (mod update)" % EASY_VERSION})
        try:
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
                total = 0
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > 4 * 1024 ** 3:
                        raise ValueError("too big")
                    f.write(chunk)
        except Exception as e:
            return 502, {"error": "Couldn't download it (%s). Get it yourself from %s and upload it here." % (short_err(e), u["page"])}
        if not zipfile.is_zipfile(tmp):
            return 502, {"error": "beamng.com didn't send a zip file (it may want you to log in). Download it from %s and upload it here." % u["page"]}
        got = mod_repo_info(tmp)
        if not got or got["resource_id"] != u["resource_id"]:
            return 502, {"error": "The downloaded file isn't the same mod - not installed."}
        result = modscan.scan(tmp)
        if result["verdict"] == "blocked":
            APP.alerts.raise_("mod:%s:%s" % (I().id, name), "A mod update failed the virus check: %s" % name,
                              "\n".join(result["reasons"]) + "\nThe old version is still installed.")
            return 422, {"ok": False, "blocked": True, "reasons": result["reasons"], "error": "The update failed the virus check - the old version stays."}
        dest = os.path.join(I().CLIENT_DIR if u["enabled"] else I().DISABLED_DIR, name)
        if not IS_WIN:
            os.chmod(tmp, 0o664)
        os.replace(tmp, dest) if os.path.dirname(tmp) == os.path.dirname(dest) else shutil.move(tmp, dest)
        modscan.remember(dest, result.get("sha256"))
        u.update({"update": False, "have": got["version"], "have_id": got["version_id"]})
        return 200, {"version": got["version"]}
    finally:
        shutil.rmtree(tdir, ignore_errors=True)


def update_mods(names, ups):
    """Update several mods of the current server one by one. Returns ([names updated], [(name, error)])."""
    done, failed = [], []
    for i, n in enumerate(names):
        if i:
            time.sleep(1)                      # be polite to beamng.com
        st, r = apply_mod_update(n, ups[n])
        if st == 200:
            done.append(n)
        else:
            failed.append((n, r.get("error") or "failed"))
    return done, failed


# ----------------------------------------------------------------------------- mod browser (BeamNG repository)
# Browse the public mod list on beamng.com and install a mod with one click.
# The site has no search API (its search page is behind a bot check), so the
# browser reads the normal category lists - a few pages, cached - and filters
# them. A link to any mod page works too.
REPO_SITE = "https://www.beamng.com/"
REPO_CATS = [("vehicles.2", "Vehicles"), ("terrains-levels-maps.9", "Maps"), ("skins.12", "Skins"),
             ("mods-of-mods.7", "Mods of mods"), ("props.5", "Props"), ("sounds.13", "Sounds"),
             ("user-interface-apps.10", "UI apps"), ("license-plates.15", "License plates"), ("land.3", "Land")]
REPO_ORDERS = {"download_count": "Most downloaded", "rating_weighted": "Best rated", "last_update": "Recently updated",
               "resource_date": "Newest"}
_REPO_CACHE = {}
_REPO_LOCK = threading.Lock()
MODB_JOBS = {}
REPO_ICON_DIR = os.path.join(DATA_DIR, "repo_icons")


def _repo_get(url, limit=4 * 1024 * 1024, ttl=6 * 3600):
    with _REPO_LOCK:
        c = _REPO_CACHE.get(url)
        if c and time.time() - c[0] < ttl:
            return c[1]
    req = urllib.request.Request(url, headers={"User-Agent": "BeamMP-EasyServer/%s (mod browser)" % EASY_VERSION,
                                               "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=25) as r:
        html = r.read(limit).decode("utf-8", "replace")
    if "CrowdSec" in html[:3000] and "resourceListItem" not in html:
        raise RuntimeError("beamng.com asked for a browser check - try again in a while")
    with _REPO_LOCK:
        if len(_REPO_CACHE) > 300:
            _REPO_CACHE.clear()
        _REPO_CACHE[url] = (time.time(), html)
    return html


def _txt(h):
    return clean_msg(html_unescape(re.sub(r"<[^>]+>", " ", h or "")))


def html_unescape(t):
    import html as _h
    return _h.unescape(t)


def parse_repo_list(html):
    """Mods on a beamng.com list page."""
    out = []
    for m in re.finditer(r'<li class="resourceListItem[^"]*" id="resource-(\d+)">(.*?)</li>\s*(?=<li class="resourceListItem|</ol>|$)', html, re.S):
        rid, b = int(m.group(1)), m.group(2)
        title = re.search(r'<h3 class="title">.*?<a href="[^"]*">(.*?)</a>\s*(?:<span class="version">(.*?)</span>)?', b, re.S)
        if not title:
            continue
        det = re.search(r'<div class="resourceDetails muted">(.*?)</div>', b, re.S)
        links = re.findall(r'<a [^>]*>(.*?)</a>', det.group(1), re.S) if det else []
        dl = re.search(r'Downloads:</dt>\s*<dd>([\d,]+)', b)
        rating = re.search(r'itemprop="average">([\d.]+)', b)
        upd = re.search(r'resourceUpdated.*?data-time="(\d+)"', b, re.S) or re.search(r'data-time="(\d+)"', b)
        icon = re.search(r'class="resourceIcon"><img src="([^"]+)"', b)
        out.append({"id": rid, "title": _txt(title.group(1))[:120], "version": _txt(title.group(2))[:40],
                    "author": _txt(links[0])[:60] if links else "", "category": _txt(links[-1])[:40] if len(links) > 2 else "",
                    "tagline": _txt((re.search(r'<div class="tagLine">(.*?)</div>', b, re.S) or [None, ""])[1])[:220],
                    "downloads": int(dl.group(1).replace(",", "")) if dl else 0,
                    "rating": round(float(rating.group(1)), 1) if rating else None,
                    "updated": int(upd.group(1)) if upd else None,
                    "icon": bool(icon) and "/resource_icons/" in icon.group(1),
                    "page": REPO_PAGE % rid})
    return out


def repo_mod_page(rid):
    """Title, version and newest download for one mod page."""
    html = _repo_get(REPO_PAGE % rid, ttl=1800)
    vids = [int(v) for v in re.findall(r"/download\?version=(\d+)", html)]
    t = re.search(r"<h1[^>]*>(.*?)(?:<span class=\"muted\">\s*([^<]{1,40}?)\s*</span>)?\s*</h1>", html, re.S)
    tag = re.search(r'<p class="tagLine">(.*?)</p>', html, re.S)
    return {"id": rid, "title": _txt(t.group(1))[:120] if t else "Mod %d" % rid, "version": _txt(t.group(2))[:40] if t and t.group(2) else "",
            "tagline": _txt(tag.group(1))[:220] if tag else "", "version_id": max(vids) if vids else None,
            "page": REPO_PAGE % rid, "icon": True, "author": "", "category": "", "downloads": 0, "rating": None, "updated": None}


def repo_id_from(text):
    m = re.search(r"beamng\.com/resources/(?:[^/\s]*\.)?(\d{1,7})", text or "")
    return int(m.group(1)) if m else None


def installed_repo_ids():
    ids = {}
    for m in list_mods():
        p = os.path.join(I().CLIENT_DIR if m["enabled"] else I().DISABLED_DIR, m["name"])
        info = modscan_info_cached(p)
        if info:
            ids[info["resource_id"]] = m["name"]
    return ids


_INFO_CACHE = {}


def modscan_info_cached(p):
    try:
        st = os.stat(p)
    except OSError:
        return None
    key = (p, st.st_size, int(st.st_mtime))
    if key not in _INFO_CACHE:
        if len(_INFO_CACHE) > 2000:
            _INFO_CACHE.clear()
        _INFO_CACHE[key] = mod_repo_info(p)
    return _INFO_CACHE[key]


def modb_install(job, inst_id, rid):
    """Background job: download a repository mod, virus-check it, install it."""
    use_server(inst_id)
    tdir = None
    try:
        job.update(state="Looking up the newest version…")
        info = repo_mod_page(rid)
        if not info.get("version_id"):
            raise RuntimeError("This mod has no download on beamng.com (it may be paid or removed).")
        url = REPO_DL % (rid, info["version_id"])
        tdir = tempfile.mkdtemp(dir=UPLOAD_TMP, prefix=".up-")
        req = urllib.request.Request(url, headers={"User-Agent": "BeamMP-EasyServer/%s (mod browser)" % EASY_VERSION})
        with urllib.request.urlopen(req, timeout=60) as r:
            cd = r.headers.get("Content-Disposition") or ""
            fn = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
            name = safe_zip_name(fn.group(1) if fn else os.path.basename(urllib.parse.urlparse(r.geturl()).path)) \
                or safe_zip_name(re.sub(r"[^A-Za-z0-9]+", "_", info["title"]).strip("_")[:60] + ".zip") or "mod_%d.zip" % rid
            total = int(r.headers.get("Content-Length") or 0)
            job.update(name=name, total=total)
            tmp = os.path.join(tdir, name)
            got = 0
            with open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    got += len(chunk)
                    if got > 4 * 1024 ** 3:
                        raise RuntimeError("too big (over 4 GB)")
                    f.write(chunk)
                    job.update(done=got, state="Downloading…")
        if not zipfile.is_zipfile(tmp):
            raise RuntimeError("beamng.com didn't send a zip file (it may want you to log in). Download it from %s and upload it here." % info["page"])
        mi = mod_repo_info(tmp)
        if mi and mi["resource_id"] != rid:
            raise RuntimeError("The downloaded file isn't the mod you picked - not installed.")
        for folder in (I().CLIENT_DIR, I().DISABLED_DIR):
            if os.path.exists(os.path.join(folder, name)):
                raise RuntimeError("You already have %s installed (Mods page)." % name)
        job.update(state="Virus check…")
        result = modscan.scan(tmp)
        if result["verdict"] == "blocked":
            APP.alerts.raise_("mod:%s:%s" % (inst_id, name), "A mod from the mod browser failed the virus check: %s" % name,
                              "\n".join(result["reasons"]) + "\nIt was not installed.")
            raise RuntimeError("Blocked by the virus check: " + "; ".join(result["reasons"][:3]))
        dest = os.path.join(I().CLIENT_DIR, name)
        if not IS_WIN:
            os.chmod(tmp, 0o664)
        shutil.move(tmp, dest)
        modscan.remember(dest, result.get("sha256"))
        refresh_mod_desc()
        APP.config_changed()
        maps = zip_maps(dest) or []
        job.update(ok=True, finished=True, state="Installed", maps=maps,
                   note="Installed %s%s. %s" % (info["title"], " (" + info["version"] + ")" if info["version"] else "",
                                               ("It's a map - pick it on the Overview page. " if maps else "") + APP.applied_note()))
    except Exception as e:
        job.update(ok=False, finished=True, state="Failed", error=str(e) if isinstance(e, RuntimeError) else short_err(e))
    finally:
        if tdir:
            shutil.rmtree(tdir, ignore_errors=True)


# ----------------------------------------------------------------------------- phone push (ntfy)
NTFY_TOPIC_RE = re.compile(r"[A-Za-z0-9_-]{16,64}")


def ntfy_send(title, message, level="info", click=None):
    s, topic = APP.settings, APP.secrets.get("NTFY_TOPIC")
    if not topic:
        raise ValueError("no ntfy topic")
    server = (s.get("ntfy_server") or "https://ntfy.sh").rstrip("/")
    prio = {"error": "5", "warning": "4", "success": "3", "info": "3"}.get(level, "3")
    tags = {"error": "rotating_light", "warning": "warning", "success": "white_check_mark", "info": "racing_car"}.get(level, "racing_car")
    hdr = {"Title": title.encode("utf-8")[:250].decode("latin-1"), "Priority": prio, "Tags": tags,
           "User-Agent": "BeamMP-EasyServer/" + EASY_VERSION}
    if click:
        hdr["Click"] = click
    req = urllib.request.Request("%s/%s" % (server, topic), data=message[:3900].encode("utf-8"), method="POST", headers=hdr)
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()


# ----------------------------------------------------------------------------- in-game tools: /tp and /repair
TOOLS_MOD = "easyserver_tools.zip"
TOOLS_DEFAULTS = {"tp": False, "tp_cd": 60, "repair": "free", "repair_cd": 5, "suggest": True}
TOOLS_MODSCRIPT = """-- BeamMP EasyServer: in-game tools (/tp, /repair, games on screen). Loaded by BeamNG when you join a server that uses it.
load("easyserverTools")
setExtensionUnloadMode("easyserverTools", "manual")
"""
TOOLS_CLIENT_LUA = r"""-- BeamMP EasyServer in-game tools (client side).
-- The server decides everything (who may teleport where, cooldowns); this
-- only moves or repairs YOUR OWN car when the server tells it to, and turns
-- off the reset keys while the server has "repair with cooldown" or "no
-- repairs" switched on. It also shows the server's chat commands as you type
-- "/" in the chat, and the server's games on screen (race checkpoints, a lap
-- timer, cops and robbers above their cars). It does nothing on other servers
-- or in single player.
local M = {}

-- Command suggestions in the BeamMP chat box: the server sends the commands this
-- player can use; this adds a small list above the chat input (Tab completes).
local SUGGEST_JS = [==[(function (list) {
  var S = window.__esSuggest;
  if (!S) {
    S = window.__esSuggest = { list: [], rows: [], sel: 0, moved: false, input: null, box: null };
    var css = document.createElement("style");
    css.textContent = "#es-suggest{position:fixed;z-index:2147483000;min-width:280px;max-width:560px;background:rgba(18,20,26,.96);" +
      "border:1px solid rgba(255,255,255,.14);border-radius:6px;padding:4px 0;font:14px/1.4 'Noto Sans',sans-serif;color:#e8e8e8;" +
      "box-shadow:0 8px 22px rgba(0,0,0,.55);pointer-events:auto}" +
      "#es-suggest .r{padding:4px 12px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}" +
      "#es-suggest .r.on{background:rgba(255,102,0,.38)}#es-suggest .c{color:#fff;font-weight:700}" +
      "#es-suggest .a{color:#ffb070;margin-left:6px}#es-suggest .d{color:#a9a9a9;margin-left:10px}" +
      "#es-suggest .h{color:#8a8a8a;font-size:11px;padding:3px 12px 1px;border-top:1px solid rgba(255,255,255,.08);margin-top:3px}";
    document.head.appendChild(css);
    var isChat = function (el) {
      return !!el && el.tagName === "INPUT" && (el.id === "chat-input" || (el.classList && el.classList.contains("chat2-message-input")));
    };
    var dist = function (a, b) {          // edit distance, a swapped pair counts as one typo
      if (Math.abs(a.length - b.length) > 2) return 9;
      var d = [], i, j;
      for (i = 0; i <= a.length; i++) { d[i] = [i]; }
      for (j = 0; j <= b.length; j++) { d[0][j] = j; }
      for (i = 1; i <= a.length; i++) for (j = 1; j <= b.length; j++) {
        var c = a[i - 1] === b[j - 1] ? 0 : 1;
        d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c);
        if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
      }
      return d[a.length][b.length];
    };
    S.hide = function () { if (S.box) S.box.style.display = "none"; S.rows = []; S.moved = false; };
    S.match = function (word) {
      var w = word.toLowerCase(), pre = [], mid = [], near = [];
      S.list.forEach(function (x) {
        if (x.c.indexOf(w) === 0) pre.push(x);
        else if (w.length > 1 && x.c.indexOf(w) > 0) mid.push(x);
        else if (w.length > 1) { var k = dist(w, x.c); if (k <= (w.length <= 4 ? 1 : 2)) near.push([k, x]); }
      });
      near.sort(function (p, q) { return p[0] - q[0]; });
      return pre.concat(mid, near.map(function (p) { return p[1]; }));
    };
    S.draw = function (input, rows, hintOnly) {
      if (!S.box) {
        S.box = document.createElement("div");
        S.box.id = "es-suggest";
        S.box.addEventListener("mousedown", function (e) {
          var r = e.target.closest && e.target.closest(".r");
          e.preventDefault();
          if (r && S.input) S.complete(S.input, +r.getAttribute("data-i"));
        });
        document.body.appendChild(S.box);
      }
      S.box.textContent = "";
      rows.forEach(function (x, i) {
        var r = document.createElement("div");
        r.className = "r" + (!hintOnly && i === S.sel ? " on" : "");
        r.setAttribute("data-i", i);
        var c = document.createElement("span"); c.className = "c"; c.textContent = "/" + x.c; r.appendChild(c);
        if (x.a) { var a = document.createElement("span"); a.className = "a"; a.textContent = x.a; r.appendChild(a); }
        if (x.d) { var d = document.createElement("span"); d.className = "d"; d.textContent = x.d; r.appendChild(d); }
        S.box.appendChild(r);
      });
      if (!hintOnly) {
        var h = document.createElement("div"); h.className = "h";
        h.textContent = "Tab to complete · ↑↓ to choose · Esc to close";
        S.box.appendChild(h);
      }
      var b = input.getBoundingClientRect();
      S.box.style.display = "block";
      S.box.style.left = Math.max(4, b.left) + "px";
      S.box.style.minWidth = Math.max(280, b.width) + "px";
      if (b.top > S.box.offsetHeight + 12) { S.box.style.top = ""; S.box.style.bottom = (window.innerHeight - b.top + 6) + "px"; }
      else { S.box.style.bottom = ""; S.box.style.top = (b.bottom + 6) + "px"; }
    };
    S.update = function (input) {
      S.input = input;
      var v = input.value || "";
      var m = /^\/([A-Za-z]*)(\s.*)?$/.exec(v);
      if (!m || !S.list.length) { S.hide(); return; }
      if (m[2] !== undefined) {                       // already typing the rest: show how to use that command
        var hit = S.list.filter(function (x) { return x.c === m[1].toLowerCase(); });
        S.rows = [];
        if (hit.length) S.draw(input, hit, true); else S.hide();
        return;
      }
      var rows = (m[1] ? S.match(m[1]) : S.list).slice(0, 7);
      if (!rows.length) { S.hide(); return; }
      if (rows.length === 1 && rows[0].c === m[1].toLowerCase() && !rows[0].a) { S.hide(); return; }
      if (S.sel >= rows.length || !S.moved) S.sel = 0;
      S.rows = rows;
      S.draw(input, rows, false);
    };
    S.complete = function (input, i) {
      var x = S.rows[i];
      if (!x) return;
      var v = "/" + x.c + (x.a ? " " : "");
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, v);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      try { input.setSelectionRange(v.length, v.length); } catch (e) {}
      input.focus();
      S.moved = false;
      S.update(input);
    };
    document.addEventListener("input", function (e) { if (isChat(e.target)) { S.moved = false; S.update(e.target); } }, true);
    document.addEventListener("focusin", function (e) { if (isChat(e.target)) S.update(e.target); }, true);
    document.addEventListener("focusout", function (e) { if (isChat(e.target)) setTimeout(function () { if (document.activeElement !== e.target) S.hide(); }, 150); }, true);
    document.addEventListener("keydown", function (e) {
      if (!isChat(e.target) || !S.box || S.box.style.display === "none") return;
      var k = e.key;
      if (k === "Escape") { S.hide(); return; }
      if (!S.rows.length) return;
      if (k === "Tab" || (k === "Enter" && S.moved)) {
        e.preventDefault(); e.stopPropagation(); S.complete(e.target, S.sel);
      } else if (k === "ArrowDown" || k === "ArrowUp") {
        e.preventDefault(); e.stopPropagation();
        S.sel = (S.sel + (k === "ArrowDown" ? 1 : S.rows.length - 1)) % S.rows.length;
        S.moved = true;
        S.draw(e.target, S.rows, false);
      }
    }, true);
  }
  S.list = (Array.isArray(list) ? list : []).filter(function (x) { return x && typeof x.c === "string" && /^[a-z]{1,20}$/.test(x.c); })
    .map(function (x) { return { c: x.c, a: String(x.a || "").slice(0, 40), d: String(x.d || "").slice(0, 90) }; });
  if (!S.list.length) S.hide();
  else if (S.input && document.activeElement === S.input) S.update(S.input);
})]==]
local cmdList = "[]"
local function pushCmds()
  pcall(function() be:queueJS(SUGGEST_JS .. "(" .. cmdList .. ")") end)
end
local function onCmds(data)
  local ok, d = pcall(jsonDecode, data or "[]")
  if not ok or type(d) ~= "table" then return end
  local clean = {}
  for _, x in ipairs(d) do
    if type(x) == "table" and type(x.c) == "string" and #x.c <= 20 and x.c:match("^%l+$") then
      clean[#clean + 1] = { c = x.c, a = tostring(x.a or ""):sub(1, 40), d = tostring(x.d or ""):sub(1, 90) }
    end
  end
  cmdList = #clean > 0 and jsonEncode(clean) or "[]"
  pushCmds()
end
local function clearCmds()
  if cmdList ~= "[]" then cmdList = "[]" pushCmds() end
end

-- Games on screen: the server sends this player's race / lap / cops-and-robbers state (esHud)
-- and which cars are cops and robbers (esTags). A small panel at the top shows the timer and
-- position; the next checkpoint is drawn on the road, and COP / ROBBER above those cars.
local HUD_JS = [==[(function (s) {
  var H = window.__esHud;
  if (!H) {
    H = window.__esHud = { s: null, at: 0, dist: -1, box: null, big: null };
    var css = document.createElement("style");
    css.textContent = "#es-hud{position:fixed;top:64px;left:50%;transform:translateX(-50%);z-index:2147482000;min-width:240px;" +
      "max-width:560px;padding:8px 18px 10px;border-radius:10px;background:rgba(14,16,22,.82);border:1px solid rgba(255,255,255,.12);" +
      "color:#eee;font:14px/1.35 'Noto Sans',sans-serif;text-align:center;pointer-events:none;box-shadow:0 6px 20px rgba(0,0,0,.45)}" +
      "#es-hud .t{font-size:30px;font-weight:700;letter-spacing:.5px;font-variant-numeric:tabular-nums;color:#fff}" +
      "#es-hud .l{font-size:15px;font-weight:600;margin-top:1px}#es-hud .s{color:#b8b8b8;margin-top:2px}" +
      "#es-hud .bar{height:6px;border-radius:3px;background:rgba(255,255,255,.15);margin-top:6px;overflow:hidden}" +
      "#es-hud .bar i{display:block;height:100%;width:0}" +
      "#es-hud.cop .t{color:#5aa2ff}#es-hud.robber .t{color:#ff5a5a}#es-hud.out .t{color:#9a9a9a}" +
      "#es-big{position:fixed;top:30%;left:50%;transform:translate(-50%,-50%);z-index:2147482000;pointer-events:none;" +
      "font:800 120px/1 'Noto Sans',sans-serif;color:#fff;text-shadow:0 4px 18px rgba(0,0,0,.7)}";
    document.head.appendChild(css);
    var el = function (id) { var d = document.createElement("div"); d.id = id; d.style.display = "none"; document.body.appendChild(d); return d; };
    H.box = el("es-hud"); H.big = el("es-big");
    var pad = function (n, w) { n = String(n); while (n.length < w) n = "0" + n; return n; };
    H.time = function (ms) {
      ms = Math.max(0, Math.floor(ms));
      var m = Math.floor(ms / 60000), sec = Math.floor(ms / 1000) % 60;
      return m + ":" + pad(sec, 2) + "." + pad(ms % 1000, 3);
    };
    H.clock = function (sec) { sec = Math.max(0, Math.ceil(sec)); return Math.floor(sec / 60) + ":" + pad(sec % 60, 2); };
    H.m = function () { return H.dist >= 0 ? " · " + Math.round(H.dist) + " m" : ""; };
    H.row = function (cls, text) { var d = document.createElement("div"); d.className = cls; d.textContent = text; H.box.appendChild(d); return d; };
    H.t = function (k) {                // the server's language (event esLang); {} and {1} like the chat
      var a = arguments, i = 1, L = window.__esLang || {};
      return String(L[k] || k).replace(/\{(\d*)\}/g, function (_, d) { var v = d ? a[+d] : a[i++]; return v == null ? "" : String(v); });
    };
    H.cp = function (s) {
      if (!s.cp) return "";
      if (s.cpn === 0) return H.t("Start line") + H.m();
      return (s.fin ? H.t(s.last ? "Finish line" : "Lap line") : H.t("Checkpoint {}/{}", s.cpn, s.cps - 1)) + H.m();
    };
    H.draw = function () {
      var s = H.s, now = Date.now(), dt = (now - H.at) / 1000;
      if (!s) { H.big.style.display = "none"; H.box.style.display = "none"; return; }
      H.box.textContent = ""; H.box.className = ""; H.big.style.display = "none";
      var left = Math.max(0, (s.left || 0) - dt), go = (s.go || 0) - dt;
      if (s.k === "race") {
        if (s.st === "join") {
          H.row("l", H.t(s.laps === 1 ? "Race on {} · {} lap" : "Race on {} · {} laps", s.track, s.laps));
          H.row("s", H.t("Starts in {} - drive to the start line", H.clock(left)) + H.m());
        } else if (s.st === "countdown") {
          H.row("l", H.t("Race on {}", s.track));
          H.row("s", H.t("Get ready") + H.m());
          H.big.style.display = "block"; H.big.textContent = go > 0 ? String(Math.ceil(go)) : H.t("GO!");
        } else if (s.st === "done") {
          H.row("t", H.time(s.ms));
          H.row("l", H.t("Finished P{}", s.pos) + (s.of > 1 ? "/" + s.of : "") + " · " + s.track);
        } else {
          H.row("t", H.time((s.ms || 0) + dt * 1000));
          H.row("l", H.t("Lap {}/{}", s.lap, s.laps) + (s.of > 1 ? " · P" + s.pos + "/" + s.of : ""));
          H.row("s", H.cp(s));
          if (dt < 1.2 && s.lap === 1 && (s.ms || 0) < 1500) { H.big.style.display = "block"; H.big.textContent = H.t("GO!"); }
        }
      } else if (s.k === "lap") {
        H.row("t", H.time((s.ms || 0) + dt * 1000));
        H.row("l", s.track + (s.best ? " · " + H.t("Best {}", H.time(s.best)) : ""));
        H.row("s", H.cp(s));
      } else if (s.k === "cnr") {
        if (s.st === "join") {
          H.row("l", H.t("Cops and robbers"));
          H.row("s", H.t("Starts in {}", H.clock(left)));
        } else {
          H.box.className = s.role;
          H.row("t", H.t(s.role === "cop" ? "COP" : s.role === "robber" ? "ROBBER" : "OUT"));
          if (s.role === "out") { H.row("s", H.t("Busted - watch the rest of the game")); }
          else if (s.st === "head") {
            H.row("l", H.t(s.role === "cop" ? "You start in {}" : "Head start: {} - get away!", H.clock(go)));
          } else {
            H.row("l", H.t("{} left", H.clock(left)) + " · " + H.t(s.free === 1 ? "{} robber free" : "{} robbers free", s.free));
            if (s.who) {
              var held = Math.min(s.need || 3, (s.held || 0) + dt);
              H.row("s", s.role === "cop" ? H.t("Stopping {} - {}/{} s", s.who, held.toFixed(1), s.need || 3)
                                          : H.t("{} is stopping you - drive away!", s.who));
              var bar = H.row("bar", ""), fill = document.createElement("i");
              fill.style.width = Math.round(100 * held / (s.need || 3)) + "%";
              fill.style.background = s.role === "cop" ? "#5aa2ff" : "#ff5a5a";
              bar.appendChild(fill);
            }
          }
        }
      }
      H.box.style.display = H.box.childNodes.length ? "block" : "none";
    };
    H.set = function (s) {
      H.s = s; H.at = Date.now();
      if (!s) H.dist = -1;
      H.draw();
    };
    window.__esHudD = function (d) { H.dist = d; };
    setInterval(function () { H.draw(); }, 100);
  }
  H.set(s && typeof s === "object" ? s : null);
})]==]

local hud, hudJson, tags = nil, "null", {}
local function pushHud()
  pcall(function() be:queueJS(HUD_JS .. "(" .. hudJson .. ")") end)
end
local function num(x, lo, hi)
  x = tonumber(x)
  if not x or x ~= x then return nil end
  return math.max(lo, math.min(hi, x))
end
local function str(x, n) return type(x) == "string" and x:sub(1, n) or nil end
local function pt(x)
  if type(x) ~= "table" then return nil end
  local a, b, c = tonumber(x[1]), tonumber(x[2]), tonumber(x[3])
  if a and b and c then return { a, b, c } end
end
local function onHud(data)
  local ok, d = pcall(jsonDecode, data or "")
  if not ok or type(d) ~= "table" or (d.k ~= "race" and d.k ~= "lap" and d.k ~= "cnr") then
    hud, hudJson = nil, "null"
  else
    hud = { k = d.k, st = str(d.st, 12), track = str(d.track, 40), who = str(d.who, 40),
      role = (d.role == "cop" or d.role == "robber" or d.role == "out") and d.role or nil,
      laps = num(d.laps, 1, 99), lap = num(d.lap, 1, 99), pos = num(d.pos, 0, 999), of = num(d.of, 0, 999),
      cpn = num(d.cpn, 0, 999), cps = num(d.cps, 0, 999), ms = num(d.ms, 0, 1e8), best = num(d.best, 0, 1e8),
      left = num(d.left, 0, 7200), go = num(d.go, 0, 600), held = num(d.held, 0, 60), need = num(d.need, 1, 60),
      free = num(d.free, 0, 999), cops = num(d.cops, 0, 999), rad = num(d.rad, 1, 100), fin = d.fin == true, last = d.last == true,
      cp = pt(d.cp), cp2 = pt(d.cp2) }
    hudJson = jsonEncode(hud)
  end
  pushHud()
end
local function onTags(data)
  local ok, d = pcall(jsonDecode, data or "[]")
  tags = {}
  if ok and type(d) == "table" then
    for _, x in ipairs(d) do
      if type(x) == "table" and type(x.v) == "string" and x.v:match("^%d+%-%d+$") and (x.r == "cop" or x.r == "robber") then
        tags[#tags + 1] = { v = x.v, r = x.r }
      end
    end
  end
end
local function clearHud()
  tags = {}
  if hud then hud, hudJson = nil, "null" pushHud() end
end

-- The on-screen words in the server's language: { English = translation }, {} and {1} like the chat.
local lang, langJson = {}, "{}"
local function pushLang()
  pcall(function() be:queueJS("window.__esLang=" .. langJson .. ";window.__esHud&&window.__esHud.draw()") end)
end
local function onLang(data)
  local ok, d = pcall(jsonDecode, data or "{}")
  lang = {}
  if ok and type(d) == "table" then
    local n = 0
    for k, v in pairs(d) do
      if type(k) == "string" and type(v) == "string" and #k <= 120 and #v <= 200 and n < 200 then lang[k] = v n = n + 1 end
    end
  end
  langJson = jsonEncode(lang)
  if langJson == "[]" or langJson == "" then langJson = "{}" end
  pushLang()
end
local function L(key, ...)
  local args, i = { ... }, 0
  return (tostring(lang[key] or key):gsub("{(%d*)}", function(d)
    if d == "" then i = i + 1 d = i else d = tonumber(d) end
    return tostring(args[d] or "")
  end))
end

local COLORS = { next = { 1, 0.78, 0.1 }, fin = { 0.25, 1, 0.45 }, start = { 0.2, 0.75, 1 } }
local function drawMark(p, rgb, rad, strong, label)
  local base = vec3(p[1], p[2], p[3] - 0.6)
  local c = function(a) return ColorF(rgb[1], rgb[2], rgb[3], a) end
  if strong then debugDrawer:drawCylinder(base, base + vec3(0, 0, 0.12), rad, c(0.2)) end
  debugDrawer:drawCylinder(base, base + vec3(0, 0, 30), strong and 0.5 or 0.35, c(strong and 0.6 or 0.25))
  if label then
    debugDrawer:drawTextAdvanced(base + vec3(0, 0, 4), String(label), ColorF(1, 1, 1, 1), true, false,
      ColorI(math.floor(rgb[1] * 160), math.floor(rgb[2] * 160), math.floor(rgb[3] * 160), 210))
  end
end

local drawFailed, distT = false, 0
local function drawGames(dt)
  local mine = be:getPlayerVehicle(0)
  local myPos = mine and vec3(mine:getPosition())
  if hud and hud.cp then
    local rgb = hud.cpn == 0 and COLORS.start or (hud.fin and COLORS.fin or COLORS.next)
    local label = hud.cpn == 0 and L("START") or (hud.fin and L(hud.last and "FINISH" or "LAP") or L("CHECKPOINT {}", hud.cpn))
    drawMark(hud.cp, rgb, hud.rad or 15, true, label)
    if hud.cp2 then drawMark(hud.cp2, COLORS.next, hud.rad or 15, false, nil) end
    distT = distT + (dt or 0)
    if distT >= 0.25 then
      distT = 0
      if myPos then
        local d = (myPos - vec3(hud.cp[1], hud.cp[2], hud.cp[3])):length()
        pcall(function() be:queueJS("window.__esHudD&&window.__esHudD(" .. math.floor(d) .. ")") end)
      end
    end
  end
  if #tags > 0 and MPVehicleGE and MPVehicleGE.getGameVehicleID then
    local cam = core_camera and core_camera.getPosition and core_camera.getPosition()
    for _, t in ipairs(tags) do
      local gid = MPVehicleGE.getGameVehicleID(t.v)
      local obj = gid and gid ~= -1 and be:getObjectByID(gid)
      if obj and not (MPVehicleGE.isOwn and MPVehicleGE.isOwn(gid)) then
        local pos = vec3(obj:getPosition()) + vec3(0, 0, 2.4)
        if not cam or (pos - cam):length() < 400 then
          local cop = t.r == "cop"
          debugDrawer:drawTextAdvanced(pos, String(L(cop and "COP" or "ROBBER")), ColorF(1, 1, 1, 1), true, false,
            cop and ColorI(30, 90, 230, 230) or ColorI(215, 35, 35, 230))
        end
      end
    end
  end
end

-- Drift scoring, when the server has it on (esDriftCfg): points for every second the car slides
-- sideways - more for a bigger angle and more speed. Straighten up for 1.5 s and the drift is banked
-- and sent to the server for the leaderboard; hit something and it's lost.
local DRIFT_JS = [==[(function (st, pts, ang, sec) {
  var D = window.__esDrift;
  if (!D) {
    D = window.__esDrift = { el: null, hideAt: 0 };
    var css = document.createElement("style");
    css.textContent = "#es-drift{position:fixed;bottom:20%;left:50%;transform:translateX(-50%);z-index:2147482000;pointer-events:none;" +
      "text-align:center;font:700 15px/1.2 'Noto Sans',sans-serif;color:#fff;text-shadow:0 2px 10px rgba(0,0,0,.85)}" +
      "#es-drift .p{font-size:46px;font-weight:800;font-variant-numeric:tabular-nums}#es-drift .k{color:#ffb070;letter-spacing:2px}" +
      "#es-drift .s{color:#d0d0d0}#es-drift.done .p{color:#5dff8a}#es-drift.lost .p{color:#ff5a5a;text-decoration:line-through}";
    document.head.appendChild(css);
    D.el = document.createElement("div"); D.el.id = "es-drift"; D.el.style.display = "none"; document.body.appendChild(D.el);
    setInterval(function () { if (D.hideAt && Date.now() > D.hideAt) { D.el.style.display = "none"; D.hideAt = 0; } }, 200);
  }
  var t = function (k) {
    var a = arguments, i = 1, L = window.__esLang || {};
    return String(L[k] || k).replace(/\{(\d*)\}/g, function (_, d) { var v = d ? a[+d] : a[i++]; return v == null ? "" : String(v); });
  };
  if (st === "off") { D.el.style.display = "none"; D.hideAt = 0; return; }
  D.el.className = st; D.el.textContent = "";
  var row = function (c, x) { var d = document.createElement("div"); d.className = c; d.textContent = x; D.el.appendChild(d); };
  row("k", t(st === "lost" ? "DRIFT LOST" : "DRIFT"));
  row("p", (st === "done" ? "+" : "") + Math.floor(pts));
  if (st === "on") row("s", t("Angle {}° · {} s", Math.round(ang), Number(sec).toFixed(1)));
  D.el.style.display = "block";
  D.hideAt = Date.now() + (st === "on" ? 1500 : 2500);
})]==]
local drift = { on = false, active = false, pts = 0, secs = 0, calm = 0, ang = 0, kmh = 0, push = 0, failed = false }
local function driftPush(st)
  pcall(function() be:queueJS(DRIFT_JS .. string.format('("%s",%d,%d,%.2f)', st, math.floor(drift.pts), math.floor(drift.ang), drift.secs)) end)
end
local function driftEnd(lost)
  if drift.pts >= 50 then
    if not lost and TriggerServerEvent then
      TriggerServerEvent("esDrift", string.format('{"s":%d,"t":%.2f}', math.floor(drift.pts), drift.secs))
    end
    driftPush(lost and "lost" or "done")
  end
  drift.active, drift.pts, drift.secs, drift.calm = false, 0, 0, 0
end

-- cfg and myVehicle are set up below; driftStep only runs once the server has said drift is on
local myVehicle
local function driftStep(dt)
  if not dt or dt <= 0 or dt > 0.25 then return end           -- paused, or a hitch: skip the frame
  local v = myVehicle and myVehicle()
  if not v or (hud and (hud.k == "race" or hud.k == "cnr")) then
    if drift.active then driftEnd(true) end
    return
  end
  local vel, dir = vec3(v:getVelocity()), vec3(v:getDirectionVector())
  local kmh = vel:length() * 3.6
  local lv, ld = math.sqrt(vel.x ^ 2 + vel.y ^ 2), math.sqrt(dir.x ^ 2 + dir.y ^ 2)
  local ang = 0
  if lv > 1 and ld > 0.1 then
    ang = math.deg(math.acos(math.max(-1, math.min(1, (vel.x * dir.x + vel.y * dir.y) / (lv * ld)))))
  end
  local braked = (drift.kmh - kmh) / dt                       -- km/h lost per second
  drift.kmh = kmh
  if drift.active and braked > 150 then driftEnd(true) return end  -- that was a wall, not the brakes
  if kmh >= 25 and ang >= 12 and ang <= 120 then
    drift.active, drift.calm, drift.ang = true, 0, ang
    drift.secs = drift.secs + dt
    drift.pts = drift.pts + dt * (math.min(ang, 90) - 10) * math.min(kmh, 200) / 20
  elseif drift.active then
    drift.calm = drift.calm + dt
    if drift.calm >= 1.5 then driftEnd(false) return end
  end
  if drift.active then
    drift.push = drift.push + dt
    if drift.push >= 0.1 then drift.push = 0 driftPush("on") end
  end
end
local function onDriftCfg(data)
  drift.on = data == "1"
  if not drift.on then
    if drift.active then driftEnd(true) end
    driftPush("off")
  end
end

local cfg = { tp = false, repair = "free" }
local FILTER = "easyserver_noreset"
local RESET_ACTIONS = { "reset_physics", "reset_all_physics", "recover_vehicle", "recover_vehicle_alt",
  "recover_to_last_road", "reload_vehicle", "reload_all_vehicles", "loadHome", "saveHome",
  "dropPlayerAtCamera", "dropPlayerAtCameraNoReset", "goto_checkpoint" }
local blocking = false

local function setBlock(on)
  if on == blocking then return end
  blocking = on
  pcall(function()
    core_input_actionFilter.setGroup(FILTER, RESET_ACTIONS)
    core_input_actionFilter.addAction(0, FILTER, on)
  end)
end

function myVehicle()
  local v = be:getPlayerVehicle(0)
  if v and MPVehicleGE and MPVehicleGE.isOwn and not MPVehicleGE.isOwn(v:getID()) then return nil end
  return v
end

local function onCfg(data)
  local ok, d = pcall(jsonDecode, data or "{}")
  if not ok or type(d) ~= "table" then return end
  cfg.tp = d.tp == true
  cfg.repair = (d.repair == "cooldown" or d.repair == "off") and d.repair or "free"
  setBlock(cfg.repair ~= "free")
end

local function onTpTo(serverVehId)
  local mine = myVehicle()
  if not mine then return end
  local gid = MPVehicleGE and MPVehicleGE.getGameVehicleID and MPVehicleGE.getGameVehicleID(serverVehId)
  local target = gid and gid ~= -1 and be:getObjectByID(gid)
  if not target then pcall(guihooks.trigger, "toastrMsg", { type = "warning", title = "Teleport", msg = "Couldn't find their car." }) return end
  local pos = vec3(target:getPosition())
  local dir = vec3(target:getDirectionVector())
  local up = vec3(target:getDirectionVectorUp())
  local rot = quatFromDir(dir, up)
  -- park 8 m behind them, a little above the ground
  local dest = pos - dir:normalized() * 8 + vec3(0, 0, 0.5)
  local ok = false
  if spawn and spawn.safeTeleport then ok = pcall(spawn.safeTeleport, mine, dest, rot) end
  if not ok then
    pcall(function() mine:setPositionRotation(dest.x, dest.y, dest.z, rot.x, rot.y, rot.z, rot.w) end)
  end
end

local function onRepair()
  local mine = myVehicle()
  if not mine then return end
  pcall(function() mine:resetBrokenFlexMesh() end)
  pcall(function() mine:queueLuaCommand("obj:requestReset(RESET_PHYSICS)") end)
end

local registered = false
local function register()
  if registered or not AddEventHandler then return end
  registered = true
  AddEventHandler("esToolsCfg", onCfg)
  AddEventHandler("esTpTo", onTpTo)
  AddEventHandler("esRepair", onRepair)
  AddEventHandler("esCmds", onCmds)
  AddEventHandler("esHud", onHud)
  AddEventHandler("esTags", onTags)
  AddEventHandler("esLang", onLang)
  AddEventHandler("esDriftCfg", onDriftCfg)
end

M.onExtensionLoaded = function() register() end
M.onWorldReadyState = function(state)
  if state == 2 then
    register()
    if TriggerServerEvent then TriggerServerEvent("esToolsHello", "") end
  end
end
M.onPreRender = function(dt, dtSim)
  if drift.on and not drift.failed then
    local ok, err = pcall(driftStep, type(dtSim) == "number" and dtSim or dt)
    if not ok then drift.failed = true log("E", "easyserverTools", "drift scoring failed: " .. tostring(err)) end
  end
  if drawFailed or (not hud and #tags == 0) then return end
  local ok, err = pcall(drawGames, dt)
  if not ok then drawFailed = true log("E", "easyserverTools", "drawing the games failed: " .. tostring(err)) end
end
M.onUiReady = function()
  if cmdList ~= "[]" then pushCmds() end
  if langJson ~= "{}" then pushLang() end
  if hud then pushHud() end
end
M.onExtensionUnloaded = function() setBlock(false) clearCmds() clearHud() onDriftCfg("0") end
M.onClientEndMission = function() setBlock(false) clearCmds() clearHud() onDriftCfg("0") end

return M
"""


def tools_mod_bytes():
    """The client mod, built the same way every time (same bytes -> players only download it once)."""
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in (("scripts/easyserver_tools/modScript.lua", TOOLS_MODSCRIPT),
                           ("lua/ge/extensions/easyserverTools.lua", TOOLS_CLIENT_LUA)):
            zi = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, text)
    return buf.getvalue()


def read_tools(inst=None):
    inst = inst or I()
    d = dict(TOOLS_DEFAULTS)
    for line in shared_read(inst.TOOLS_FILE, 16384).splitlines():
        m = re.fullmatch(r"\s*(\w+)\s*=\s*(.*?)\s*", line)
        if not m:
            continue
        k, v = m.groups()
        if k == "tp":
            d["tp"] = v.lower() == "on"
        elif k == "repair" and v in ("free", "cooldown", "off"):
            d["repair"] = v
        elif k == "suggest":
            d["suggest"] = v.lower() != "off"
        elif k == "tp_cd" and v.isdigit() and int(v) <= 3600:
            d["tp_cd"] = int(v)
        elif k == "repair_cd" and v.isdigit() and 1 <= int(v) <= 120:
            d["repair_cd"] = int(v)
    return d


def write_tools(d, inst=None):
    inst = inst or I()
    shared_write(inst.TOOLS_FILE, "# Managed by the BeamMP EasyServer dashboard (Config -> In-game tools).\n"
                 "tp=%s\ntp_cd=%d\nrepair=%s\nrepair_cd=%d\nsuggest=%s\n" % ("on" if d["tp"] else "off", d["tp_cd"], d["repair"],
                                                                       d["repair_cd"], "on" if d.get("suggest", True) else "off"))


def tools_wanted(d):
    return bool(d["tp"] or d["repair"] != "free" or d.get("suggest", True))


# ----------------------------------------------------------------------------- game chat language
# What the plugin says in the chat (and the helper mod shows on screen), in the language the owner picks
# (Config -> Welcome message & announcements). The translations are the "game" part of lang/xx.json;
# the plugin reads chatlang.tsv: English <TAB> translation [<TAB> hud]. tools/game_i18n.py lists them.
GAME_HUD_TEXT = (
    "Race on {} · {} lap", "Race on {} · {} laps", "Starts in {} - drive to the start line", "Race on {}", "Get ready",
    "Finished P{}", "Lap {}/{}", "Start line", "Finish line", "Lap line", "Checkpoint {}/{}", "Best {}",
    "Cops and robbers", "Starts in {}", "COP", "ROBBER", "OUT", "Busted - watch the rest of the game",
    "You start in {}", "Head start: {} - get away!", "{} left", "{} robber free", "{} robbers free",
    "Stopping {} - {}/{} s", "{} is stopping you - drive away!", "GO!", "START", "FINISH", "LAP", "CHECKPOINT {}",
    "DRIFT", "DRIFT LOST", "Angle {}° · {} s",
)


def chat_lang_text(code):
    """chatlang.tsv for a language code ("" = English: empty)."""
    if not code or not re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", code):
        return ""
    try:
        with open(os.path.join(LANG_DIR, code + ".json"), encoding="utf-8") as f:
            game = json.load(f).get("game") or {}
    except (OSError, ValueError):
        return ""
    clean = lambda x: re.sub(r"[\t\r\n]+", " ", str(x)).strip()
    hud = set(GAME_HUD_TEXT)
    lines = []
    for en, tr in game.items():
        if isinstance(tr, str) and clean(tr) and clean(en):
            lines.append("%s\t%s%s" % (clean(en), clean(tr), "\thud" if en in hud else ""))
    return "".join(l + "\n" for l in lines)


def ensure_chat_lang(inst=None):
    """Keep the plugin's chatlang.tsv in step with the chosen language (and with updated translations)."""
    inst = inst or I()
    path = os.path.join(inst.STATS_DIR, "chatlang.tsv")
    want = chat_lang_text(inst.meta.get("chat_lang") or "")
    if shared_read(path, 1024 * 1024) != want:
        shared_write(path, want)


def games_want_mod(inst):
    """Races, cops and robbers and lap times are drawn on screen by the same mod."""
    sd = inst.STATS_DIR
    if re.search(r"^mode=on\s*$", shared_read(os.path.join(sd, "laps.txt"), 4096), re.M):
        return True
    on = {"race": True, "cnr": True, "drift": False}   # the plugin's defaults when games.txt doesn't say
    for line in shared_read(os.path.join(sd, "games.txt"), 4096).splitlines():
        k, _, v = line.partition("=")
        if k in on:
            on[k] = v.strip() == "on"
    return any(on.values())


def ensure_tools_mod(inst=None):
    """Put the client mod in place when a tool or a game is on, keep it up to date, remove it when everything is off.
    Returns "added", "updated", "removed" or ""."""
    inst = inst or I()
    want = tools_wanted(read_tools(inst)) or games_want_mod(inst)
    path = os.path.join(inst.CLIENT_DIR, TOOLS_MOD)
    if not want:
        if os.path.exists(path):
            os.remove(path)
            return "removed"
        return ""
    data = tools_mod_bytes()
    try:
        with open(path, "rb") as f:
            if f.read(len(data) + 1) == data:
                return ""
        how = "updated"
    except OSError:
        how = "added"
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    if not IS_WIN:
        os.chmod(tmp, 0o664)
    os.replace(tmp, path)
    modscan.remember(path, hashlib.sha256(data).hexdigest())
    try:
        modscan.scan(path)
    except Exception:
        pass
    return how


# ----------------------------------------------------------------------------- vehicle rules (Config -> Vehicle rules)
# Read by the EasyServerStats plugin (vehicles.txt). The plugin cancels a spawn
# or a swap to a blocked model, so the car never appears for anyone.
# Base-game model names ("jbeam" names). A wrong or old name in these lists
# does nothing - it just never matches.
BASE_CARS = ("autobello", "barstow", "bastion", "bluebuck", "bolide", "burnside", "bx", "citybus", "covet", "etk800",
             "etkc", "etki", "fullsize", "hopper", "lansdale", "legran", "md_series", "midsize", "midtruck", "miramar",
             "moonhawk", "pessima", "pickup", "pigeon", "racetruck", "roamer", "rockbouncer", "sbr", "scintilla",
             "sunburst", "us_semi", "van", "vivace", "wendover", "wigeon")
BASE_TRAILERS = ("boxutility", "boxutility_large", "caravan", "cargotrailer", "dolly", "dryvan", "flatbed",
                 "frameless_dump", "tanker", "tiltdeck")
BASE_PROPS = ("ball", "barrels", "barrier", "blockwall", "bollard", "cannon", "chair", "christmas_tree", "cones", "couch",
              "flail", "gate", "haybale", "inflated_mat", "kickplate", "mattress", "metal_box", "metal_ramp", "piano",
              "rocks", "roadsigns", "sawhorse", "streetlight", "tirestacks", "tirewall", "trafficbarrel", "tube", "wall",
              "weightpad", "woodcrate", "woodplanks")
# Big physics props - the usual reason a whole server suddenly lags.
BASE_HEAVY_PROPS = ("large_angletoy", "large_bridge", "large_cannon", "large_crusher", "large_hamster_wheel", "large_roller",
                    "large_spinner", "large_tilt", "large_tire", "shipping_container", "suspensionbridge", "testroller")
JBM_RE = re.compile(r"[A-Za-z0-9_.\-]{1,80}")
VEH_DEFAULTS = {"on": False, "cooldown": 0, "spam": 0, "exempt": True, "only": False, "props": False, "trailers": False,
                "heavyprops": False, "heavymods": False, "cars": [], "allow": []}
VEH_PRESETS = {
    "anything": ("Anything goes", "No limits - every car and prop is allowed.",
                 {"on": False, "props": False, "trailers": False, "heavyprops": False, "heavymods": False, "cooldown": 0, "spam": 0}),
    "chill": ("No chaos", "Props and heavy mod cars off, spawn spam stopped. Good for public servers.",
              {"on": True, "props": True, "trailers": False, "heavyprops": True, "heavymods": True, "cooldown": 5, "spam": 6}),
    "racing": ("Racing", "No props or trailers, no heavy cars, 10 s between spawns.",
               {"on": True, "props": True, "trailers": True, "heavyprops": True, "heavymods": True, "cooldown": 10, "spam": 4}),
    "roleplay": ("Roleplay", "Trailers allowed for jobs, props and heavy cars off, 30 s between spawns.",
                 {"on": True, "props": True, "trailers": False, "heavyprops": True, "heavymods": True, "cooldown": 30, "spam": 4}),
}
# A car mod is "heavy" from these counts (all parts in the mod, so it's an upper estimate).
HEAVY_NODES, HEAVY_BEAMS = 4000, 24000
_MODVEH_CACHE = {}


def clean_jbm(v):
    v = str(v or "").strip()
    return v if JBM_RE.fullmatch(v) else None


def _jbeam_counts(text):
    """Rough node and beam counts of a .jbeam file (rows of the "nodes" and "beams" tables)."""
    nodes = beams = 0
    for m in re.finditer(r'"(nodes|beams)"\s*:\s*\[', text):
        i, depth, start = m.end(), 1, m.end()
        while i < len(text) and depth:
            c = text[i]
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
            i += 1
        body = text[start:i]
        if m.group(1) == "nodes":
            nodes += len(re.findall(r'\[\s*"[^"\n]+"\s*,\s*-?\d', body))
        else:
            beams += len(re.findall(r'\[\s*"(?!id1:")[^"\n]+"\s*,\s*"[^"\n]+"', body))
    return nodes, beams


def mod_vehicles(path):
    """The vehicles in a mod zip: [{jbm, name, type, nodes, beams, heavy}]. Cached per file version."""
    try:
        st = os.stat(path)
    except OSError:
        return []
    key = (path, st.st_size, int(st.st_mtime))
    if key in _MODVEH_CACHE:
        return _MODVEH_CACHE[key]
    found = {}
    try:
        with zipfile.ZipFile(path) as z:
            budget = 96 * 1024 ** 2
            for zi in z.infolist():
                m = re.match(r"^vehicles/([^/]+)/(.+)$", zi.filename, re.I)
                if not m or zi.is_dir() or not JBM_RE.fullmatch(m.group(1)) or m.group(1).lower() == "common":
                    continue
                v = found.setdefault(m.group(1).lower(), {"jbm": m.group(1), "name": "", "type": "", "nodes": 0, "beams": 0,
                                                          "defines": False})
                fn = m.group(2).lower()
                if fn.startswith("info") and fn.endswith(".json") and "/" not in fn and zi.file_size < 256 * 1024 and not v["type"]:
                    v["defines"] = True
                    try:
                        raw = z.read(zi).decode("utf-8", "replace")
                        raw = re.sub(r"(?m)^\s*//.*$", "", raw)
                        raw = re.sub(r",\s*([}\]])", r"\1", raw)
                        info = json.loads(raw)
                        if isinstance(info, dict):
                            v["type"] = str(info.get("Type") or "")[:20]
                            v["name"] = (str(info.get("Brand") or "") + " " + str(info.get("Name") or "")).strip()[:80]
                    except (ValueError, zipfile.BadZipFile, OSError, RuntimeError):
                        pass
                elif fn.endswith(".jbeam") and zi.file_size <= 8 * 1024 ** 2 and budget > 0:
                    budget -= zi.file_size
                    try:
                        n, b = _jbeam_counts(z.read(zi).decode("utf-8", "replace"))
                    except (zipfile.BadZipFile, OSError, RuntimeError):
                        continue
                    v["nodes"] += n
                    v["beams"] += b
    except (zipfile.BadZipFile, OSError):
        return []
    out = []
    for v in found.values():
        t = v["type"].lower()
        v["kind"] = "prop" if t == "prop" else "trailer" if t == "trailer" else "car"
        v["heavy"] = v["nodes"] >= HEAVY_NODES or v["beams"] >= HEAVY_BEAMS
        out.append(v)
    out.sort(key=lambda x: x["jbm"].lower())
    if len(_MODVEH_CACHE) > 400:
        _MODVEH_CACHE.clear()
    _MODVEH_CACHE[key] = out
    return out


BASE_ALL = {j.lower() for j in BASE_CARS + BASE_TRAILERS + BASE_PROPS + BASE_HEAVY_PROPS}


def mod_needs(inst=None):
    """{mod file: [models it adds parts to that neither the game nor another enabled mod has]}.
    A "mod of a mod" (extra parts for someone else's car) does nothing without that car's mod."""
    inst = inst or I()
    per, have = {}, set(BASE_ALL)
    try:
        names = os.listdir(inst.CLIENT_DIR)
    except OSError:
        return {}
    for n in names:
        p = os.path.join(inst.CLIENT_DIR, n)
        if n.lower().endswith(".zip") and n != TOOLS_MOD and os.path.isfile(p) and not os.path.islink(p):
            vs = mod_vehicles(p)
            per[n] = vs
            have.update(v["jbm"].lower() for v in vs if v.get("defines"))
    out = {}
    for n, vs in per.items():
        miss = sorted({v["jbm"] for v in vs if not v.get("defines") and v["jbm"].lower() not in have}, key=str.lower)
        if miss:
            out[n] = miss[:10]
    return out


def server_mod_vehicles(inst=None):
    """{jbm lower: vehicle + "mod"} for the enabled mods of a server (only mods that add the vehicle itself)."""
    inst = inst or I()
    out = {}
    try:
        names = sorted(os.listdir(inst.CLIENT_DIR), key=str.lower)
    except OSError:
        return out
    for n in names:
        p = os.path.join(inst.CLIENT_DIR, n)
        if n.lower().endswith(".zip") and n != TOOLS_MOD and os.path.isfile(p) and not os.path.islink(p):
            for v in mod_vehicles(p):
                if v.get("defines"):
                    out.setdefault(v["jbm"].lower(), dict(v, mod=n))
    return out


def read_veh(inst=None):
    inst = inst or I()
    d = json.loads(json.dumps(VEH_DEFAULTS))
    for line in shared_read(os.path.join(inst.STATS_DIR, "vehicles.txt"), 256 * 1024).splitlines():
        m = re.fullmatch(r"\s*(\w+)\s*=\s*(.*?)\s*", line)
        if not m:
            continue
        k, v = m.groups()
        if k in ("on", "only", "props", "trailers", "heavyprops", "heavymods"):
            d[k] = v.lower() == "on"
        elif k == "exempt":
            d[k] = v.lower() != "off"
        elif k == "cooldown" and v.isdigit() and int(v) <= 3600:
            d[k] = int(v)
        elif k == "spam" and v.isdigit() and int(v) <= 120:
            d[k] = int(v)
        elif k in ("car", "allow") and clean_jbm(v):
            lst = d["cars" if k == "car" else "allow"]
            if v.lower() not in [x.lower() for x in lst] and len(lst) < 500:
                lst.append(v)
    return d


def veh_blocklist(d, inst=None):
    """[(model, reason)] the plugin should refuse, from the settings and the server's mods."""
    out = {}
    if d["props"]:
        for j in BASE_PROPS:
            out[j] = "props are turned off"
    if d["heavyprops"]:
        for j in BASE_HEAVY_PROPS:
            out[j] = "big physics props are turned off"
    if d["trailers"]:
        for j in BASE_TRAILERS:
            out[j] = "trailers are turned off"
    for v in server_mod_vehicles(inst).values():
        if d["props"] and v["kind"] == "prop":
            out.setdefault(v["jbm"], "props are turned off")
        elif d["trailers"] and v["kind"] == "trailer":
            out.setdefault(v["jbm"], "trailers are turned off")
        elif d["heavymods"] and v["heavy"]:
            out.setdefault(v["jbm"], "this car is too heavy for the server")
    for j in d["cars"]:
        out[j] = "the server owner blocked it"
    return sorted(out.items(), key=lambda kv: kv[0].lower())


def write_veh(d, inst=None):
    inst = inst or I()
    lines = ["# Managed by the BeamMP EasyServer dashboard (Config -> Vehicle rules).",
             "on=%s" % ("on" if d["on"] else "off"), "cooldown=%d" % d["cooldown"], "spam=%d" % d["spam"],
             "exempt=%s" % ("on" if d["exempt"] else "off"), "only=%s" % ("on" if d["only"] else "off")]
    for k in ("props", "trailers", "heavyprops", "heavymods"):
        lines.append("%s=%s" % (k, "on" if d[k] else "off"))
    lines += ["car=" + j for j in d["cars"]]
    lines += ["allow=" + j for j in d["allow"]]
    lines += ["block=%s\t%s" % (j, why) for j, why in veh_blocklist(d, inst)]
    shared_write(os.path.join(inst.STATS_DIR, "vehicles.txt"), "\n".join(lines) + "\n")


def veh_sync(inst=None):
    """Rewrite vehicles.txt after mods changed, so new prop / heavy mods are covered."""
    inst = inst or I()
    if os.path.exists(os.path.join(inst.STATS_DIR, "vehicles.txt")):
        write_veh(read_veh(inst), inst)


def veh_preset_match(d):
    for pid, (_, _, vals) in VEH_PRESETS.items():
        if all(d.get(k) == v for k, v in vals.items()) and (pid != "anything" or not d["cars"]):
            return pid
    return None


def mod_advice(inst, days=30):
    """Mods players download but don't use: vehicle mods nobody spawned lately, map mods for maps that aren't
    played, and the same vehicle in two mods. With the size and joining time each one costs."""
    t_now = now()
    mods = [m for m in list_mods() if m["enabled"] and not m["builtin"]]
    evs = read_events(t_now - days * 86400)
    oldest = min((e["t"] for e in evs), default=t_now)
    covered = (t_now - oldest) / 86400.0
    spawned = {}
    for e in evs:
        if e.get("ev") == "spawn":
            j = clean_jbm(e.get("jbm"))
            if j:
                spawned[j.lower()] = max(spawned.get(j.lower(), 0), e["t"])
    cur = (current_map() or "").lower()
    rot = rotation_cfg(inst)
    wanted = {cur} | {str(m).lower() for m in (rot["maps"] if rot["on"] else [])} | {
        str(e.get("map") or "").lower() for e in events_cfg(inst) if e.get("on", True)}
    out, owners = [], {}
    for m in mods:
        path = os.path.join(inst.CLIENT_DIR, m["name"])
        if m["maps"]:
            if not ({x.lower() for x in m["maps"]} & wanted) and not inst.meta.get("light_maps"):
                out.append({"name": m["name"], "size": m["size"], "kind": "map",
                            "why": "A map that isn't being played (not the current map%s) - every player still downloads it." % (
                                ", the map rotation or an event" if rot["on"] or events_cfg(inst) else "")})
            continue
        vehs = [v for v in mod_vehicles(path) if v.get("defines")]
        for v in vehs:
            owners.setdefault(v["jbm"].lower(), []).append(m["name"])
        if vehs and covered >= 7 and not any(v["jbm"].lower() in spawned for v in vehs):
            out.append({"name": m["name"], "size": m["size"], "kind": "unused",
                        "why": "Nobody spawned %s in the last %d days." % (
                            ", ".join(sorted({v["name"] or v["jbm"] for v in vehs})[:3]) + (" …" if len(vehs) > 3 else ""), min(days, int(covered)))})
    seen = {x["name"] for x in out}
    sizes = {m["name"]: m["size"] for m in mods}
    for jbm, names in owners.items():
        names = sorted(set(names), key=lambda n: sizes.get(n, 0))
        if len(names) > 1 and names[-1] not in seen:
            seen.add(names[-1])
            out.append({"name": names[-1], "size": sizes.get(names[-1], 0), "kind": "double",
                        "why": "Has the same vehicle (%s) as %s - players get it twice, and only one of them works." % (jbm, ", ".join(names[:-1]))})
    out.sort(key=lambda x: -x["size"])
    up = float(APP.settings.get("upload_mbit") or 0) * 1000
    lim = int((inst.meta.get("limits") or {}).get("upload_kbps") or 0)
    kbps = min(up, lim) if up and lim else up or lim
    total = sum(m["size"] for m in mods)
    save = sum(x["size"] for x in out)
    return {"items": out[:30], "save": save, "total": total, "days": min(days, int(covered)), "enough": covered >= 7,
            "secs_now": int(total * 8 / (kbps * 1000.0)) if kbps else None,
            "secs_after": int((total - save) * 8 / (kbps * 1000.0)) if kbps else None}


def veh_activity(days=7):
    """What players spawned here lately, and what the rules refused."""
    since = now() - days * 86400
    seen, blocked, spam = {}, [], []
    for e in read_events(since):
        ev = e.get("ev")
        if ev not in ("spawn", "vehblock", "vehspam"):
            continue
        name = clean_player_name(e.get("name"))
        if ev == "vehspam":
            spam.append({"t": e["t"], "name": name, "count": e.get("count") if isinstance(e.get("count"), int) else 0})
            continue
        j = clean_jbm(e.get("jbm"))
        if not j:
            continue
        if ev == "spawn":
            s = seen.setdefault(j.lower(), {"jbm": j, "count": 0, "players": set(), "last": 0})
            s["count"] += 1
            s["players"].add(name)
            s["last"] = e["t"]
        else:
            blocked.append({"t": e["t"], "name": name, "jbm": j, "why": str(e.get("why") or "")[:80]})
    top = sorted(seen.values(), key=lambda s: -s["count"])[:60]
    for s in top:
        s["players"] = len(s["players"])
    return {"seen": top, "blocked": blocked[-30:][::-1], "spam": spam[-20:][::-1], "days": days}


def veh_kind(j, mods):
    lj = j.lower()
    if lj in mods:
        v = mods[lj]
        return ("heavy " if v["heavy"] and v["kind"] == "car" else "") + v["kind"]
    if lj in BASE_HEAVY_PROPS:
        return "heavy prop"
    if lj in BASE_PROPS:
        return "prop"
    if lj in BASE_TRAILERS:
        return "trailer"
    if lj in BASE_CARS:
        return "car"
    return "unknown"


# ----------------------------------------------------------------------------- server plugins (Plugins page)
# A curated list of community plugins (docs/plugins.json on the website, with a
# built-in copy). EasyServer downloads a plugin from its author's own GitHub
# page, shows what will go where, and installs it only after the owner agrees.
# Plugins run with the server's rights, so only the owner may install them.
PLUGIN_CATALOG_URL = "https://csabika-dev.github.io/beammp-easyserver/plugins.json"
PLUGIN_CATALOG = {'format': 'beammp-easyserver-plugins',
 'version': 1,
 'about': 'Server plugins EasyServer can install. Each one belongs to its author - EasyServer only downloads it from '
          "the author's own GitHub page. Want yours listed? Open a pull request that adds it here.",
 'plugins': [{'id': 'careermp',
              'name': 'CareerMP',
              'author': 'StanleyDudek',
              'repo': 'StanleyDudek/CareerMP',
              'source': 'release',
              'about': "BeamNG.drive's own Career Mode on your server. Saves stay on each player's PC.",
              'notes': ['Needs MaxCars 100 or more and the West Coast USA map.',
                        "Its README says it doesn't work with BeamNG.drive 0.39 yet - check before installing."],
              'license': "See the author's page"},
             {'id': 'freeroammp',
              'name': 'freeRoamMP',
              'author': 'StanleyDudek',
              'repo': 'StanleyDudek/freeRoamMP',
              'source': 'release',
              'about': "The game's Freeroam mode with missions: deliveries, police, stunts.",
              'notes': ['Some missions spawn many objects - set a high MaxCars.',
                        "Its README says it doesn't work with BeamNG.drive 0.39 yet - check before installing."],
              'license': "See the author's page"},
             {'id': 'envsync',
              'name': 'BeamMP Environment Sync',
              'author': 'Evan Mulawski',
              'repo': 'EvanMulawski/BeamMP-EnvSync',
              'source': 'release',
              'about': 'Everyone sees the same time of day and weather, set by the server.',
              'notes': ['Work in progress, says its author.'],
              'license': 'MIT'},
             {'id': 'cobaltessentials',
              'name': 'CobaltEssentials',
              'author': 'Preston Elam (CobaltTetra), maintained by StanleyDudek',
              'repo': 'StanleyDudek/CobaltEssentials',
              'source': 'branch',
              'folder': 'CobaltEssentials',
              'about': 'The classic admin toolkit: permission groups, commands, RCON.',
              'notes': ["It has its own admins, bans and commands - they overlap with EasyServer's Moderation page. "
                        'Use one or the other.',
                        'After installing, type "ce setgroup YourName owner" in the server console.'],
              'license': 'All rights reserved by the author - downloaded from their page, not shipped with '
                         'EasyServer'},
             {'id': 'beamjoy',
              'name': 'BeamJoy Sandbox (Revived)',
              'author': 'Samaël (my-name-is-samael), continued by CaptainNugget',
              'repo': 'foodcache3/BeamJoy-Revived',
              'source': 'release',
              'about': 'All-in-one sandbox framework with an in-game admin menu, updated for BeamNG.drive 0.39.',
              'notes': ["Remove any other BeamJoy version first - they don't mix.",
                        "It has its own admin system - it overlaps with EasyServer's Moderation page."],
              'license': "See the author's page"}]}
PLUGIN_REPO_RE = re.compile(r"[A-Za-z0-9_.\-]{1,60}/[A-Za-z0-9_.\-]{1,100}")
PLUGIN_FOLDER_RE = re.compile(r"[A-Za-z0-9_.\-]{1,64}")
PLUGIN_ID_RE = re.compile(r"[a-z0-9_\-]{1,40}")
PLUGIN_HOSTS = ("github.com", "api.github.com", "codeload.github.com", "objects.githubusercontent.com",
                "release-assets.githubusercontent.com")
PLUGIN_MAX = 300 * 1024 ** 2
PLUGINS_FILE = os.path.join(DATA_DIR, "plugins.json")
PLUGIN_JOBS = {}
_PLUGCAT = {"t": 0, "data": None}
OWN_PLUGIN = "EasyServerStats"


def plugin_entry_ok(p):
    if not isinstance(p, dict) or not PLUGIN_ID_RE.fullmatch(str(p.get("id", ""))):
        return None
    if not PLUGIN_REPO_RE.fullmatch(str(p.get("repo", ""))) or p.get("source", "release") not in ("release", "branch"):
        return None
    if p.get("folder") and not PLUGIN_FOLDER_RE.fullmatch(str(p["folder"])):
        return None
    txt = lambda k, n: re.sub(r"[\x00-\x1f]", " ", str(p.get(k) or ""))[:n]
    return {"id": p["id"], "name": txt("name", 60) or p["id"], "author": txt("author", 120), "repo": p["repo"],
            "source": p.get("source", "release"), "folder": p.get("folder") or "", "about": txt("about", 300),
            "license": txt("license", 120), "page": "https://github.com/" + p["repo"],
            "notes": [re.sub(r"[\x00-\x1f]", " ", str(n))[:240] for n in (p.get("notes") or [])[:5] if isinstance(n, str)]}


def plugin_catalog():
    """The catalog from the website (refreshed every 6 hours), or the copy built into this version."""
    if _PLUGCAT["data"] and now() - _PLUGCAT["t"] < 6 * 3600:
        return _PLUGCAT["data"]
    data = PLUGIN_CATALOG
    try:
        req = urllib.request.Request(PLUGIN_CATALOG_URL, headers={"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read(512 * 1024).decode("utf-8"))
        if isinstance(d, dict) and d.get("format") == "beammp-easyserver-plugins" and isinstance(d.get("plugins"), list):
            data = d
    except (OSError, ValueError):
        pass
    out = [e for e in (plugin_entry_ok(p) for p in data.get("plugins", [])[:200]) if e]
    _PLUGCAT.update(t=now(), data=out)
    return out


def _plug_read():
    try:
        with open(PLUGINS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _plug_write(d):
    tmp = PLUGINS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, PLUGINS_FILE)


def plugin_records(inst=None):
    return _plug_read().get((inst or I()).id, {})


def plugin_server_dir(inst=None):
    return os.path.join((inst or I()).RES, "Server")


def plugin_off_dir(inst=None):
    return os.path.join(DATA_DIR, "plugins-off", (inst or I()).id)


WIN_RESERVED_RE = re.compile(r"(?i)(con|prn|aux|nul|com\d|lpt\d)(\..*)?")


def _zip_member_ok(zi):
    n = zi.filename.replace("\\", "/")
    if n.startswith("/") or re.match(r"^[A-Za-z]:", n) or any(p in ("..",) for p in n.split("/")):
        return False
    # ":" would write a hidden NTFS stream on Windows; "CON", "NUL" ... hang or fail there
    if any(c in n for c in ':*?"<>|\x00') or any(WIN_RESERVED_RE.fullmatch(p) for p in n.split("/") if p):
        return False
    if (zi.external_attr >> 16) & 0o170000 == 0o120000:      # symbolic link
        return False
    return True


def plugin_plan(path, folder_hint=""):
    """What a plugin zip would install: {"server": {folder: [files]}, "client": [zip names], "skipped": n}.
    Understands Resources/Server + Resources/Client, Server + Client, and a bare plugin folder."""
    with zipfile.ZipFile(path) as z:
        infos = [zi for zi in z.infolist() if not zi.is_dir()]
        if len(infos) > 5000:
            raise RuntimeError("This file has more than 5000 files - that's not a normal plugin.")
        for zi in infos:
            if not _zip_member_ok(zi):
                raise RuntimeError("The file contains an unsafe path (%s) - not installed." % zi.filename[:120])
        names = [zi.filename.replace("\\", "/") for zi in infos]
    server, client, used = {}, [], set()
    for n in names:
        m = re.match(r"^(?:[^/]+/)*?(?:Resources/)?Server/([^/]+)/(.+)$", n)
        if m and not re.search(r"(^|/)Client/", n.split("Server/")[0]):
            server.setdefault(m.group(1), []).append((n, m.group(2)))
            used.add(n)
            continue
        m = re.match(r"^(?:[^/]+/)*?(?:Resources/)?Client/([^/]+\.zip)$", n, re.I)
        if m:
            client.append((n, m.group(1)))
            used.add(n)
    if not server and not client:
        # a bare plugin: the folder that holds .lua files at its top
        tops = sorted({n.rsplit("/", 1)[0] if "/" in n else "" for n in names if n.lower().endswith(".lua")}, key=len)
        if tops:
            root = tops[0]
            folder = folder_hint or (root.rsplit("/", 1)[-1] if root else "") or os.path.splitext(os.path.basename(path))[0]
            folder = re.sub(r"-(master|main)$", "", folder)
            pre = root + "/" if root else ""
            for n in names:
                if n.startswith(pre) and not re.search(r"(^|/)\.(git|github)(/|$)", n[len(pre):]):
                    server.setdefault(folder, []).append((n, n[len(pre):]))
                    used.add(n)
    for f in list(server):
        if not PLUGIN_FOLDER_RE.fullmatch(f) or WIN_RESERVED_RE.fullmatch(f) or f.strip(".") == "":
            raise RuntimeError("The plugin folder name \"%s\" isn't allowed." % f[:60])
        if f.lower() == OWN_PLUGIN.lower():
            raise RuntimeError("The file tries to replace EasyServer's own plugin - not installed.")
    for _, c in client:
        if not safe_zip_name(c) or c == TOOLS_MOD:
            raise RuntimeError("The client mod name \"%s\" isn't allowed." % c[:60])
    if not server and not client:
        raise RuntimeError("No server plugin found in this file (no .lua files, no Resources/Server folder).")
    return {"server": {f: [m for m in v] for f, v in server.items()}, "client": client, "skipped": len(names) - len(used)}


def plan_public(plan):
    return {"server": [{"folder": f, "files": len(v), "lua": sum(1 for _, r in v if r.lower().endswith(".lua"))} for f, v in plan["server"].items()],
            "client": [c for _, c in plan["client"]], "skipped": plan["skipped"]}


def _move_new(src, dest):
    """Move to a path that must not exist yet. A link or folder that appeared there in the meantime
    (the game server's user can write to Resources/Server) is refused instead of being followed."""
    if os.path.lexists(dest):
        raise RuntimeError("%s appeared while installing - not overwritten. Try again." % os.path.basename(dest))
    try:
        os.rename(src, dest)
    except OSError:
        if os.path.lexists(dest):
            raise
        shutil.move(src, dest)


def plugin_install(path, plan, rec_id, meta, inst=None, replace=False):
    """Unpack a planned plugin. Client mods get the virus check. Returns the record."""
    inst = inst or I()
    sdir = plugin_server_dir(inst)
    recs = plugin_records(inst)
    mine = recs.get(rec_id, {})
    for f in plan["server"]:
        dest = os.path.join(sdir, f)
        if os.path.exists(dest) and not (replace and f in mine.get("server", [])):
            raise RuntimeError("A plugin folder named %s already exists in Resources/Server." % f)
    for _, c in plan["client"]:
        if os.path.exists(os.path.join(inst.CLIENT_DIR, c)) and not (replace and c in mine.get("client", [])):
            raise RuntimeError("A mod named %s already exists (Mods page)." % c)
    tdir = tempfile.mkdtemp(dir=UPLOAD_TMP, prefix=".plug-")
    try:
        scans = {}
        with zipfile.ZipFile(path) as z:
            byname = {zi.filename.replace("\\", "/"): zi for zi in z.infolist()}
            total = 0
            for f, files in plan["server"].items():
                for src, rel in files:
                    zi = byname[src]
                    total += zi.file_size
                    if total > 1024 ** 3:
                        raise RuntimeError("The plugin unpacks to more than 1 GB - not installed.")
                    out = os.path.normpath(os.path.join(tdir, "S", f, rel))
                    if not out.startswith(os.path.join(tdir, "S", f) + os.sep):
                        raise RuntimeError("unsafe path")
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    with z.open(zi) as r, open(out, "wb") as w:
                        shutil.copyfileobj(r, w)
            for src, c in plan["client"]:
                out = os.path.join(tdir, "C", c)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                total += byname[src].file_size
                if total > 4 * 1024 ** 3:
                    raise RuntimeError("The plugin unpacks to more than 4 GB - not installed.")
                with z.open(byname[src]) as r, open(out, "wb") as w:
                    shutil.copyfileobj(r, w)
                res = scans[c] = modscan.scan(out)
                if res["verdict"] == "blocked":
                    APP.alerts.raise_("mod:%s:%s" % (inst.id, c), "A plugin's client mod failed the virus check: %s" % c,
                                      "\n".join(res["reasons"]) + "\nThe plugin was not installed.")
                    raise RuntimeError("The plugin's client mod %s failed the virus check: %s" % (c, "; ".join(res["reasons"][:3])))
        if replace:
            plugin_remove(rec_id, inst, keep_record=True)
        os.makedirs(sdir, exist_ok=True)
        for f in plan["server"]:
            src = os.path.join(tdir, "S", f)
            if not IS_WIN:
                for root, dirs, files in os.walk(src):
                    os.chmod(root, 0o2775)
                    for fn in files:
                        os.chmod(os.path.join(root, fn), 0o664)
            _move_new(src, os.path.join(sdir, f))
        for _, c in plan["client"]:
            src, dest = os.path.join(tdir, "C", c), os.path.join(inst.CLIENT_DIR, c)
            if not IS_WIN:
                os.chmod(src, 0o664)
            _move_new(src, dest)
            modscan.remember(dest, scans[c].get("sha256"))
    except PermissionError:
        raise RuntimeError("EasyServer may not write to Resources/Server yet. Run the installer once more (it updates "
                           "the folder permissions), then try again.")
    finally:
        shutil.rmtree(tdir, ignore_errors=True)
    rec = dict(meta, server=sorted(plan["server"]), client=[c for _, c in plan["client"]], installed=now(), on=True)
    d = _plug_read()
    d.setdefault(inst.id, {})[rec_id] = rec
    _plug_write(d)
    if plan["client"]:
        refresh_mod_desc()
        APP.config_changed()
    return rec


def plugin_set_on(rec_id, on, inst=None):
    inst = inst or I()
    d = _plug_read()
    rec = d.get(inst.id, {}).get(rec_id)
    if not rec:
        raise RuntimeError("Unknown plugin")
    off = plugin_off_dir(inst)
    for f in rec["server"]:
        if not PLUGIN_FOLDER_RE.fullmatch(f) or f.lower() == OWN_PLUGIN.lower():
            continue
        a, b = os.path.join(plugin_server_dir(inst), f), os.path.join(off, f)
        src, dest = (b, a) if on else (a, b)
        if os.path.isdir(src) and not os.path.islink(src) and not os.path.lexists(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            _move_new(src, dest)
    for c in rec["client"]:
        if not safe_zip_name(c):
            continue
        a, b = os.path.join(inst.CLIENT_DIR, c), os.path.join(inst.DISABLED_DIR, c)
        src, dest = (b, a) if on else (a, b)
        if os.path.isfile(src) and not os.path.islink(src) and not os.path.lexists(dest):
            _move_new(src, dest)
    rec["on"] = bool(on)
    _plug_write(d)
    if rec["client"]:
        refresh_mod_desc()
        APP.config_changed()


def plugin_remove(rec_id, inst=None, keep_record=False):
    inst = inst or I()
    d = _plug_read()
    rec = d.get(inst.id, {}).get(rec_id)
    if not rec:
        raise RuntimeError("Unknown plugin")
    for f in rec["server"]:
        if PLUGIN_FOLDER_RE.fullmatch(f) and f.lower() != OWN_PLUGIN.lower():
            for base in (plugin_server_dir(inst), plugin_off_dir(inst)):
                p = os.path.join(base, f)
                if os.path.isdir(p) and not os.path.islink(p):
                    shutil.rmtree(p)
    for c in rec["client"]:
        for base in (inst.CLIENT_DIR, inst.DISABLED_DIR):
            try:
                os.remove(os.path.join(base, c))
            except OSError:
                pass
    if not keep_record:
        d[inst.id].pop(rec_id, None)
        _plug_write(d)
    if rec["client"] and not keep_record:
        refresh_mod_desc()
        APP.config_changed()


def plugin_errors(inst=None):
    """{plugin folder: (count, last line)} of Lua errors in the newest part of Server.log."""
    inst = inst or I()
    out = {}
    try:
        with open_shared(inst.SERVER_LOG, "rb") as f:
            size = os.fstat(f.fileno()).st_size
            f.seek(max(0, size - 512 * 1024))
            text = f.read().decode("utf-8", "replace")
    except OSError:
        return out
    for line in text.splitlines():
        if not re.search(r"(?i)lua error|\[lua\].{0,80}error|threw an error|stack traceback", line):
            continue
        m = re.search(r"Resources[\\/]+Server[\\/]+([A-Za-z0-9_.\-]+)", line)
        if m:
            c, _ = out.get(m.group(1), (0, ""))
            out[m.group(1)] = (c + 1, line.strip()[:300])
    return out


def plugins_overview(inst=None):
    inst = inst or I()
    recs = plugin_records(inst)
    errs = plugin_errors(inst)
    managed = {f for r in recs.values() for f in r["server"]}
    installed = []
    for rid, r in sorted(recs.items()):
        e = [errs[f] for f in r["server"] if f in errs]
        installed.append(dict(r, id=rid, errors=sum(x[0] for x in e), last_error=e[-1][1] if e else ""))
    other = []
    try:
        for n in sorted(os.listdir(plugin_server_dir(inst)), key=str.lower):
            p = os.path.join(plugin_server_dir(inst), n)
            if os.path.isdir(p) and n != OWN_PLUGIN and n not in managed and not n.startswith("."):
                other.append({"folder": n, "errors": errs.get(n, (0, ""))[0], "last_error": errs.get(n, (0, ""))[1]})
    except OSError:
        pass
    return {"installed": installed, "other": other, "own_errors": errs.get(OWN_PLUGIN, (0, ""))[0]}


def _plug_get(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"User-Agent": "BeamMP-EasyServer/%s (plugins)" % EASY_VERSION, "Accept": accept})
    r = urllib.request.urlopen(req, timeout=30)
    if (urllib.parse.urlparse(r.geturl()).hostname or "") not in PLUGIN_HOSTS:
        r.close()
        raise RuntimeError("The download was sent to an unexpected website - stopped.")
    return r


def plugin_fetch(job, inst_id, entry):
    """Background job: download a catalog plugin and work out what it would install. Stops for the owner's OK."""
    use_server(inst_id)
    try:
        job.update(state="Looking up the newest version…")
        repo = entry["repo"]
        if entry["source"] == "release":
            with _plug_get("https://api.github.com/repos/%s/releases/latest" % repo) as r:
                rel = json.loads(r.read(2 * 1024 * 1024).decode("utf-8"))
            assets = [a for a in rel.get("assets") or [] if str(a.get("name", "")).lower().endswith(".zip")]
            url = assets[0]["browser_download_url"] if assets else rel.get("zipball_url")
            version = str(rel.get("tag_name") or "")[:40]
        else:
            with _plug_get("https://api.github.com/repos/%s" % repo) as r:
                info = json.loads(r.read(2 * 1024 * 1024).decode("utf-8"))
            br = str(info.get("default_branch") or "main")
            with _plug_get("https://api.github.com/repos/%s/commits/%s" % (repo, urllib.parse.quote(br))) as r:
                sha = str(json.loads(r.read(4 * 1024 * 1024).decode("utf-8")).get("sha") or "")
            if not re.fullmatch(r"[0-9a-f]{40}", sha):
                raise RuntimeError("Couldn't find the newest version on GitHub.")
            url = "https://codeload.github.com/%s/zip/%s" % (repo, sha)
            version = br + "@" + sha[:7]
        if not url or (urllib.parse.urlparse(url).hostname or "") not in PLUGIN_HOSTS:
            raise RuntimeError("This plugin has no download on GitHub yet.")
        tmp = os.path.join(job["dir"], "plugin.zip")
        h = hashlib.sha256()
        got = 0
        with _plug_get(url, "application/octet-stream") as r, open(tmp, "wb") as f:
            job.update(total=int(r.headers.get("Content-Length") or 0))
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                got += len(chunk)
                if got > PLUGIN_MAX:
                    raise RuntimeError("too big (over 300 MB)")
                h.update(chunk)
                f.write(chunk)
                job.update(done=got, state="Downloading…")
        if not zipfile.is_zipfile(tmp):
            raise RuntimeError("GitHub didn't send a zip file.")
        plan = plugin_plan(tmp, entry.get("folder") or "")
        job.update(ok=True, finished=True, state="Ready to install", review=True, plan=plan_public(plan), version=version,
                   sha256=h.hexdigest(), size=got, _plan=plan, _path=tmp, url=url)
    except Exception as e:
        job.update(ok=False, finished=True, state="Failed", error=str(e) if isinstance(e, RuntimeError) else short_err(e))


# ----------------------------------------------------------------------------- log explainer
# (id, pattern, level, title, what it means, what to do). {1} etc. are filled from the match.
LOG_RULES = [
    ("authkey_missing", r"(?i)no authkey|authkey (is )?empty|authkey.{0,80}not (set|specified)|missing authkey", "error", "No AuthKey",
     "The server has no AuthKey, so it can't log in to BeamMP. It won't show up in the server list and players can only join by IP (if at all).",
     "Get a free key at keymaster.beammp.com (Keys -> +) and paste it under Config -> AuthKey."),
    ("authkey_bad", r"(?i)authkey.{0,80}(invalid|wrong|length|not valid)|invalid.{0,80}auth.?key|auth.{0,80}(rejected|denied)", "error", "The AuthKey was refused",
     "BeamMP didn't accept the AuthKey - it's mistyped, deleted on keymaster, or used by another server at the same time.",
     "Make a new key at keymaster.beammp.com and save it under Config -> AuthKey. Every server needs its own key."),
    ("port_busy", r"(?i)address already in use|failed to bind|bind\(\) failed|bind failed|only one usage of each socket address", "error", "The port is already in use",
     "Another program - often a second copy of the server - already uses the game port, so this server can't start.",
     "Stop the other copy, or pick another port under Config (and forward the new one on your router)."),
    ("backend_down", r"(?i)backend.{0,80}(fail|error|not respond|timed? ?out|unreachable)|heartbeat.{0,80}fail|failed.{0,80}heartbeat", "warning", "Can't reach the BeamMP backend",
     "The server couldn't talk to BeamMP's servers for a while. It may disappear from the public list until the connection is back; direct connect still works.",
     "Usually it fixes itself within minutes. If it keeps happening, check this computer's internet and firewall (Health page -> Check again)."),
    ("proxy", r"(?i)curl error|connect tunnel failed|proxy|couldn't connect to server|connection refused", "warning", "Internet connection problem",
     "The server couldn't open a connection to the internet (a firewall, proxy or the internet itself blocked it). Mostly this affects the public server list.",
     "Check the internet on this computer and any firewall or proxy. Direct connect on your network still works."),
    ("dns", r"(?i)could not resolve|name or service not known|getaddrinfo|temporary failure in name resolution|no such host", "warning", "Internet name lookup failed",
     "The computer couldn't look up an internet address - the internet or DNS was down for a moment.",
     "Check the internet connection. If it lasts, set a DNS server like 1.1.1.1 on the router or the computer."),
    ("ssl", r"(?i)ssl|certificate verify|tls handshake", "warning", "Secure connection problem",
     "A secure (HTTPS) connection to BeamMP failed. Usually the computer's clock is wrong or something on the network intercepts HTTPS.",
     "Check that the date and time on the server computer are correct, then restart the server."),
    ("lua_error", r"(?i)\[lua error\]|lua error|\[lua\].{0,80}error|attempt to (index|call|perform|compare|concatenate)|stack traceback", "error", "A server plugin crashed",
     "A plugin in Resources/Server has a Lua error. The plugin (or part of it) stops working; the server keeps running.",
     "Look at the plugin named in the line. Update or remove it. If it's EasyServerStats, update EasyServer."),
    ("plugin_load", r"(?i)(plugin|lua state).{0,80}(fail|could not|error).{0,80}load|failed to load plugin", "error", "A plugin didn't load",
     "A server plugin couldn't be started (missing file or a syntax error).",
     "Check the plugin's folder in Resources/Server, or remove it."),
    ("mod_bad", r"(?i)not a valid zip|corrupt|crc (check )?fail|bad zip|failed to (open|read).{0,80}\.zip", "error", "A broken mod file",
     "A mod .zip is damaged (often an upload that didn't finish). Players may fail to download it and can't join.",
     "Delete the mod on the Mods page and upload it again."),
    ("mod_big", r"(?i)mod.{0,80}too (big|large)|exceeds.{0,80}(size|limit)", "warning", "A very big mod",
     "Players have to download a very large mod before they can join; slow connections may time out.",
     "Turn off map mods you don't play (or use light mode on the Mods page)."),
    ("perm", r"(?i)permission denied|access is denied|operation not permitted", "error", "Permission problem",
     "The server wasn't allowed to read or write a file.",
     "Run the installer again (it fixes permissions), or check the file named in the line."),
    ("disk", r"(?i)no space left|disk (is )?full|not enough space", "error", "The disk is full",
     "The computer ran out of disk space. Logs, uploads and backups fail.",
     "Delete old mods or backups; the Health page shows the free space."),
    ("oom", r"(?i)out of memory|bad_alloc|cannot allocate memory|killed process", "error", "Out of memory",
     "The computer ran out of memory and a program was stopped.",
     "Lower Max players / Max cars, turn off big map mods, or set a RAM limit on the Servers page."),
    ("crash", r"(?i)segmentation fault|core dumped|terminate called|unhandled exception|access violation|fatal error", "error", "The server crashed",
     "BeamMP-Server stopped with an internal error. EasyServer restarts it automatically.",
     "If it happens again, update BeamMP-Server (Updates page) and remove recently added mods or plugins."),
    ("config", r"(?i)(serverconfig|toml).{0,80}(error|invalid|parse|unexpected)|failed to parse config", "error", "The config file has an error",
     "ServerConfig.toml couldn't be read, so the server may use defaults or not start.",
     "Open Config - it shows the problem. Or restore an earlier version under Config -> What changed?"),
    ("outdated_client", r"(?i)outdated|version mismatch|incompatible (client|version)|wrong version", "info", "A player has an old BeamMP version",
     "Someone tried to join with an outdated BeamMP launcher or game version.",
     "Tell them to update the BeamMP launcher and BeamNG.drive."),
    ("full", r"(?i)server (is )?full|too many players|max ?players", "info", "The server was full",
     "A player couldn't join because all slots were taken.",
     "Raise Max players under Config if the computer and upload can handle it."),
    ("timeout", r"(?i)timed? ?out|connection (reset|lost|closed)|disconnected.{0,80}(error|timeout)|broken pipe", "info", "A player lost the connection",
     "A player's connection dropped (slow internet, Wi-Fi or a mod download that took too long).",
     "Only a problem if it happens to many players: then check your upload speed (Settings -> Computer load) and the mod size."),
    ("car_limit", r"(?i)(too many|max(imum)?) (cars|vehicles)|vehicle.{0,80}(limit|denied|rejected)", "info", "Car limit reached",
     "A player tried to spawn more cars than Max cars allows.",
     "Raise Max cars under Config if you want."),
    ("ipv6", r"(?i)ip_?v6_?only|ipv6.{0,80}(fail|not supported)", "info", "IPv6 notice",
     "Harmless: this system can't share one connection for IPv4 and IPv6.", "Nothing to do."),
    ("update", r"(?i)new (server )?version.{0,80}available|update available|outdated server", "info", "A BeamMP-Server update is out",
     "There's a newer BeamMP-Server.", "Install it on the Updates page."),
]
_LOG_TS = re.compile(r"^\[([^\]]{5,40})\]")


_LOG_RX = None
LOG_LINE_MAX = 400          # longer lines are cut before matching (player chat ends up in the log)


def explain_line(line):
    global _LOG_RX
    if _LOG_RX is None:
        _LOG_RX = [(re.compile(r[1]),) + tuple(r[:1]) + tuple(r[2:]) for r in LOG_RULES]
    line = line[:LOG_LINE_MAX]
    for rx, rid, lvl, title, what, fix in _LOG_RX:
        if rx.search(line):
            return {"id": rid, "level": lvl, "title": title, "what": what, "fix": fix}
    if re.search(r"\[(ERROR|FATAL)\]", line):
        return {"id": "unknown_error", "level": "error", "title": "Unknown error",
                "what": "BeamMP-Server reported an error EasyServer doesn't know yet.",
                "fix": "Copy the line into a search engine or the BeamMP forum/Discord. A diagnostic report (Health page) helps others help you."}
    if re.search(r"\[WARN(ING)?\]", line):
        return {"id": "unknown_warn", "level": "warning", "title": "Warning",
                "what": "A warning from BeamMP-Server - usually not serious on its own.", "fix": "Only worth a look if it repeats a lot."}
    return None


def explain_log(text, budget=4.0):
    groups = {}
    stop = time.monotonic() + budget
    for i, line in enumerate(text.splitlines()):
        if i % 256 == 0 and time.monotonic() > stop:
            groups.setdefault("_partial", {"id": "_partial", "level": "info", "title": "Only part of the log was read",
                                           "what": "The log is very large, so EasyServer stopped after a few seconds.",
                                           "fix": "Restart the server to start a fresh log if you need the whole picture.",
                                           "count": 1, "first": None, "last": None, "example": "", "line_no": i})
            break
        x = explain_line(line)
        if not x:
            continue
        g = groups.setdefault(x["id"], dict(x, count=0, first=None, last=None, example="", line_no=0))
        g["count"] += 1
        m = _LOG_TS.match(line)
        ts = m.group(1) if m else ""
        g["first"] = g["first"] or ts
        g["last"] = ts or g["last"]
        g["example"] = line[-300:]
        g["line_no"] = i + 1
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(groups.values(), key=lambda g: (order.get(g["level"], 3), -g["count"]))


# ----------------------------------------------------------------------------- more alert channels
LEVEL_EMOJI = {"error": "🔴", "warning": "🟠", "success": "🟢", "info": "🔵"}


def telegram_send(text, level="info", chat=None):
    token, chat = APP.secrets.get("TELEGRAM_TOKEN"), chat or APP.settings.get("telegram_chat")
    if not token or not chat:
        raise ValueError("Telegram isn't set up")
    body = urllib.parse.urlencode({"chat_id": chat, "text": (LEVEL_EMOJI.get(level, "") + " " + text).strip()[:4000],
                                   "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % token, data=body, method="POST",
                                 headers={"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
    except urllib.error.HTTPError as e:      # never put the token (it is in the URL) into an error message
        raise ValueError("Telegram said %d: %s" % (e.code, json.loads(e.read() or b"{}").get("description", "")[:120]))
    except urllib.error.URLError as e:
        raise ValueError("can't reach Telegram (%s)" % short_err(e.reason))


def telegram_find_chat(token):
    """The chat of the newest message sent to the bot - the user sends it "hi" once."""
    req = urllib.request.Request("https://api.telegram.org/bot%s/getUpdates" % token,
                                 headers={"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise ValueError("Telegram said %d - check the bot token" % e.code)
    except urllib.error.URLError as e:
        raise ValueError("can't reach Telegram (%s)" % short_err(e.reason))
    for u in reversed(d.get("result") or []):
        m = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
        c = m.get("chat") or {}
        if c.get("id"):
            return str(c["id"]), c.get("title") or c.get("first_name") or c.get("username") or ""
    return None, None


def valid_custom_webhook(url):
    try:
        u = urllib.parse.urlparse(url or "")
        u.port
    except ValueError:
        return False
    return u.scheme == "https" and bool(u.hostname) and not u.username and len(url) < 1000 and not re.search(r"\s", url)


def public_host(host):
    """True if every address the name points to is on the public internet (not this computer, the home
    network, link-local / cloud metadata, multicast or reserved). Stops the webhook from being used
    to probe or poke devices inside the home network."""
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, OSError):
        return False
    if not infos:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0].split("%")[0])
        except ValueError:
            return False
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        if not ip.is_global or ip.is_multicast:
            return False
    return True


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


def custom_webhook_send(title, message, level="info", kind="", server=""):
    """Slack-style JSON ("text") plus the fields on their own - Slack, Mattermost, Rocket.Chat, Google Chat,
    Microsoft Teams workflows, Home Assistant, n8n, Zapier and most others accept it."""
    url = APP.secrets.get("CUSTOM_WEBHOOK")
    if not valid_custom_webhook(url):
        raise ValueError("the webhook address must start with https://")
    if not public_host(urllib.parse.urlparse(url).hostname):
        raise ValueError("the webhook must be an internet address - addresses in your home network are not allowed")
    body = {"text": "%s *%s*\n%s" % (LEVEL_EMOJI.get(level, ""), title, message), "title": title, "message": message,
            "level": level, "kind": kind or "", "server": server or server_name(), "source": "BeamMP EasyServer", "time": now()}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=20) as r:
            r.read(65536)
    except urllib.error.HTTPError as e:
        raise ValueError("the webhook answered %d" % e.code)
    except urllib.error.URLError as e:
        raise ValueError("can't reach the webhook (%s)" % short_err(e.reason))


def broadcast(title, text, discord_content=None):
    """Post an announcement (not an alert) to every community channel that is set up: the Discord webhook channel,
    Telegram and the custom webhook. Returns where it went."""
    out = []
    if webhook_parts()[0]:
        try:
            webhook_call("POST", body={"username": "BeamMP events", "content": (discord_content or ("**%s**\n%s" % (title, text)))[:1900],
                                       "allowed_mentions": {"parse": []}})
            out.append("Discord")
        except Exception as e:
            sys.stderr.write("broadcast discord: %s\n" % short_err(e))
    if APP.settings.get("telegram_enabled") and APP.secrets.has("TELEGRAM_TOKEN") and APP.settings.get("telegram_chat"):
        try:
            telegram_send("%s\n%s" % (title, re.sub(r"<t:(\d+):\w>", lambda m: time.strftime("%a %H:%M", time.localtime(int(m.group(1)))), text)))
            out.append("Telegram")
        except Exception as e:
            sys.stderr.write("broadcast telegram: %s\n" % short_err(e))
    if APP.settings.get("webhook_enabled") and APP.secrets.has("CUSTOM_WEBHOOK"):
        try:
            custom_webhook_send(title, re.sub(r"<t:(\d+):\w>", lambda m: time.strftime("%a %H:%M", time.localtime(int(m.group(1)))), text), "info", "event")
            out.append("webhook")
        except Exception as e:
            sys.stderr.write("broadcast webhook: %s\n" % short_err(e))
    return out


# ----------------------------------------------------------------------------- uptime + public status page
UPTIME_FILE = os.path.join(DATA_DIR, "uptime.json")
UPTIME_DAYS = 90


def uptime_record(states):
    """Called once a minute with {server id: running?}: counts up/total minutes per day."""
    d = read_json(UPTIME_FILE, {})
    d = d if isinstance(d, dict) else {}
    day = time.strftime("%Y-%m-%d")
    for iid, up in states.items():
        srv = d.setdefault(iid, {})
        c = srv.setdefault(day, [0, 0])
        c[0] += 1 if up else 0
        c[1] += 1
        for k in sorted(srv)[:-UPTIME_DAYS]:
            del srv[k]
    for iid in [k for k in d if k not in states]:
        del d[iid]
    write_json(UPTIME_FILE, d)


def uptime_summary(iid, days=30):
    srv = (read_json(UPTIME_FILE, {}) or {}).get(iid) or {}
    out = []
    for i in range(days - 1, -1, -1):
        k = time.strftime("%Y-%m-%d", time.localtime(now() - i * 86400))
        up, tot = srv.get(k, [0, 0])
        out.append({"day": k, "pct": round(up * 100.0 / tot, 1) if tot else None})
    def pct(n):
        ks = [time.strftime("%Y-%m-%d", time.localtime(now() - i * 86400)) for i in range(n)]
        up = sum(srv.get(k, [0, 0])[0] for k in ks)
        tot = sum(srv.get(k, [0, 0])[1] for k in ks)
        return round(up * 100.0 / tot, 2) if tot else None
    return {"days": out, "d1": pct(1), "d7": pct(7), "d30": pct(30)}


_STATUS_CACHE = {"t": 0, "data": None}


def join_info(inst):
    """How to join, for the status page. BeamMP has no links that open the game, so: the name to
    search in the server list, and (only if the owner turned it on) the address for Direct Connect."""
    g = toml_parse(APP.read_config_text())[0].get("General", {})
    name = re.sub(r"\^.", "", str(g.get("Name") or "")).strip()[:80]
    addr = None
    if APP.settings.get("statuspage_address"):
        host, port, via_relay = game_address(inst)
        if host and (via_relay or duck_host() or public_ip()):
            addr = {"host": host, "port": port}
    return {"name": name, "listed": not g.get("Private") and inst.has_authkey(), "address": addr}


DISCORD_INVITE_RE = re.compile(r"https://(discord\.gg|discord\.com/invite)/[A-Za-z0-9-]{2,32}")


def join_estimate(inst):
    """(seconds a new player waits for the mods or None, bytes to download) - from the upload speed the owner entered."""
    total = sum(x["size"] for x in list_mods() if x["enabled"])
    up = float(APP.settings.get("upload_mbit") or 0) * 1000
    lim = int((inst.meta.get("limits") or {}).get("upload_kbps") or 0)
    kbps = min(up, lim) if up and lim else up or lim
    return (int(total * 8 / (kbps * 1000.0)) if total and kbps else None), total


def public_status():
    """What the public status page shows. No addresses, no admin data."""
    if now() - _STATUS_CACHE["t"] < 20 and _STATUS_CACHE["data"]:
        return _STATUS_CACHE["data"]
    with LOCK:
        insts = sorted(INSTANCES.values(), key=lambda i: (i.id != "main", i.id))
    show_names = bool(APP.settings.get("statuspage_players"))
    servers = []
    for inst in insts:
        use_server(inst.id)
        st = inst.server.status()
        g = toml_parse(APP.read_config_text())[0].get("General", {})
        players = analytics_online() if st["state"] == "running" else []
        m = maintenance_cfg(inst)
        state = "maintenance" if m["on"] and st["state"] == "running" else ("up" if st["state"] == "running" else
                 "asleep" if APP.sleeping else "down")
        up = uptime_summary(inst.id)
        upcoming = []
        for e in events_cfg(inst):
            if e.get("on", True):
                t0 = event_next_start(e, now())
                if t0:
                    upcoming.append({"name": e["name"], "t": t0, "map": map_name("/levels/%s/info.json" % e["map"]) if e.get("map") else "",
                                     "game": EVENT_GAMES.get(e.get("game") or "", "").split(" (")[0], "text": e.get("text") or ""})
        upcoming.sort(key=lambda x: x["t"])
        nxt = upcoming[0] if upcoming else None
        lc = read_laps_cfg()
        laps = [{"name": t["name"], "kind": t["kind"], "top": [{"name": r["name"], "time": r["time"], "car": r["car"]}
                                                               for r in t["top"]]}
                for t in laps_summary(10, map_name(g.get("Map")) or None) if t["top"]] if lc["on"] and lc["public"] else []
        drift, champ = [], None
        if lc["public"]:
            gc = read_games_cfg()
            if gc["drift"]:
                best = {}
                for r in read_drift():
                    if r["raw_map"] == str(g.get("Map") or "") and r["score"] > best.get(r["name"], {"score": -1})["score"]:
                        best[r["name"]] = r
                drift = [{"name": r["name"], "score": r["score"], "car": r["car"]} for r in sorted(best.values(), key=lambda r: -r["score"])[:10]]
            if gc["champ"]:
                rows, rounds = read_champ()
                if rows and rounds:
                    champ = {"name": gc["champ_name"] or "Championship", "races": rounds,
                             "top": [{"name": r["name"], "points": r["points"], "wins": r["wins"]} for r in rows[:10]]}
        wait, dl = join_estimate(inst)
        mods = []
        if APP.settings.get("statuspage_mods"):
            mods = [{"name": re.sub(r"\.zip$", "", x["name"], flags=re.I), "size": x["size"], "map": bool(x["maps"])}
                    for x in list_mods() if x["enabled"] and x["name"] != TOOLS_MOD]
        servers.append({"name": inst.name, "state": state, "note": m["message"] if state == "maintenance" else "",
                        "mods": mods, "download": sum(x["size"] for x in mods),
                        "players": len(players), "max": g.get("MaxPlayers"), "names": players[:50] if show_names else [],
                        "map": map_name(g.get("Map")) or "", "uptime": st.get("uptime") or 0, "history": up, "next_event": nxt,
                        "events": upcoming[:5], "drift": drift, "champ": champ, "join_secs": wait, "join_bytes": dl,
                        "laps": laps, "join": join_info(inst) if st["state"] == "running" else None})
    use_server("main")
    data = {"title": APP.settings.get("statuspage_title") or server_name() or "BeamMP server", "servers": servers,
            "about": APP.settings.get("statuspage_about") or "", "discord": APP.settings.get("statuspage_discord") or "",
            "updated": now(), "version": EASY_VERSION}
    _STATUS_CACHE.update(t=now(), data=data)
    return data


STATUS_HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><meta http-equiv="refresh" content="60">
<meta property="og:type" content="website"><meta property="og:title" content="__TITLE__"><meta property="og:description" content="__DESC__">
<meta name="description" content="__DESC__"><meta name="twitter:card" content="summary"><style>
:root{color-scheme:light dark;--bg:#f6f7f9;--card:#fff;--ink:#16181d;--mute:#5d6470;--line:#e3e6ea;--up:#16a34a;--down:#dc2626;--warn:#d97706;--none:#d4d8de}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a20;--ink:#eceff3;--mute:#9aa3ae;--line:#272b33;--none:#30353e}}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:760px;margin:0 auto;padding:28px 16px}h1{font-size:24px;margin:0 0 4px}.mute{color:var(--mute)}.small{font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-top:14px}
.row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.sp{flex:1}
.pill{display:inline-flex;align-items:center;gap:6px;font-weight:600;font-size:13px}.dot{width:10px;height:10px;border-radius:50%;background:var(--none)}
.up .dot{background:var(--up)}.down .dot{background:var(--down)}.maintenance .dot,.asleep .dot{background:var(--warn)}
.bars{display:flex;gap:2px;margin-top:10px;height:28px}.bars i{flex:1;border-radius:2px;background:var(--none)}
.stats{display:flex;gap:18px;margin-top:8px}.stats b{font-size:17px}
.join{margin-top:10px;padding:10px 12px;border-radius:10px;background:var(--bg);border:1px solid var(--line)}
code.sel{user-select:all;-webkit-user-select:all;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:1px 6px}
.laps table{border-collapse:collapse;margin-top:6px;width:100%}.laps td{padding:3px 8px 3px 0;border-top:1px solid var(--line)}
.mono{font-variant-numeric:tabular-nums}
.btn{display:inline-block;padding:8px 14px;border-radius:9px;font-weight:600;text-decoration:none;background:#5865f2;color:#fff}
.ev{padding:6px 0;border-top:1px solid var(--line)}.ev:first-of-type{border-top:0}
</style></head><body><main>__BODY__<p class="small mute" style="margin-top:22px">Updated __UPDATED__ · refreshes every minute · __CREDIT__</p></main></body></html>"""


def render_status_page(d):
    e = html_escape
    label = {"up": "Online", "down": "Offline", "maintenance": "Maintenance", "asleep": "Sleeping - wakes up when someone asks"}
    def bar(p):
        if p is None:
            return '<i title="no data"></i>'
        c = "var(--up)" if p >= 99 else "var(--warn)" if p >= 90 else "var(--down)"
        return '<i style="background:%s" title="%s%%"></i>' % (c, p)
    def pct(p):
        return "-" if p is None else ("%g%%" % p)
    parts = ['<h1>%s</h1>' % e(d["title"])]
    if d.get("about"):
        parts.append('<p style="margin:4px 0 0;white-space:pre-line">%s</p>' % e(d["about"]))
    else:
        parts.append('<p class="mute">Server status</p>')
    if d.get("discord"):
        parts.append('<p style="margin:12px 0 0"><a class="btn" href="%s" rel="noopener">Join our Discord</a></p>' % e(d["discord"]))
    for s in d["servers"]:
        extra = []
        if s["state"] == "up":
            extra.append("%d/%s players" % (s["players"], s["max"] or "?"))
            if s["map"]:
                extra.append("map " + s["map"])
        parts.append('<div class="card"><div class="row"><b style="font-size:17px">%s</b><span class="sp"></span><span class="pill %s"><span class="dot"></span>%s</span></div>'
                     % (e(s["name"]), s["state"], label.get(s["state"], s["state"])))
        if s["note"]:
            parts.append('<p class="small" style="margin:6px 0 0">%s</p>' % e(s["note"]))
        if extra:
            parts.append('<p class="small mute" style="margin:6px 0 0">%s</p>' % e(" · ".join(extra)))
        if s["names"]:
            parts.append('<p class="small" style="margin:4px 0 0">%s</p>' % e(", ".join(s["names"])))
        if s.get("mods"):
            parts.append('<details class="small" style="margin-top:8px"><summary>%d mod%s · %s to download before joining</summary><ul style="margin:6px 0 0;padding-left:18px">%s</ul></details>' % (
                len(s["mods"]), "" if len(s["mods"]) == 1 else "s", e(fmt_bytes(s["download"])),
                "".join('<li>%s <span class="mute">%s%s</span></li>' % (e(x["name"]), e(fmt_bytes(x["size"])), " · map" if x["map"] else "") for x in s["mods"])))
        elif s["state"] == "up" and APP.settings.get("statuspage_mods"):
            parts.append('<p class="small mute" style="margin:6px 0 0">No mods - nothing to download.</p>')
        if s.get("join_secs") is not None and s["state"] == "up":
            parts.append('<p class="small mute" style="margin:6px 0 0">First join: about %s to download %s of mods. After that it\'s quick.</p>'
                         % (e(fmt_secs(max(s["join_secs"], 5))), e(fmt_bytes(s["join_bytes"]))))
        evs = s.get("events") or ([s["next_event"]] if s.get("next_event") else [])
        if evs:
            parts.append('<div class="small" style="margin-top:8px"><b>📅 Coming up</b>%s</div>' % "".join(
                '<div class="ev"><b>%s</b> · %s%s%s%s</div>' % (
                    e(ne["name"]), e(time.strftime("%a %d %b %H:%M", time.localtime(ne["t"]))), (" · " + e(ne["map"])) if ne.get("map") else "",
                    (" · " + e(ne["game"])) if ne.get("game") else "", ('<br><span class="mute">%s</span>' % e(ne["text"])) if ne.get("text") else "")
                for ne in evs))
        j = s.get("join")
        if j and s["state"] == "up" and (j["listed"] or j["address"]):
            how = []
            if j["address"]:
                how.append('In BeamMP: <b>Direct Connect</b> &rarr; IP <code class="sel">%s</code> port <code class="sel">%s</code>'
                           % (e(str(j["address"]["host"])), e(str(j["address"]["port"]))))
            if j["listed"]:
                how.append('%s <b>%s</b> in the BeamMP server list and press Join.' % ("Or search" if how else "In BeamMP: search", e(j["name"])))
            parts.append('<div class="join small"><b>How to join</b><br>%s<br><span class="mute">Need BeamMP? '
                         '<a href="https://beammp.com" rel="noopener" style="color:inherit">beammp.com</a></span></div>' % "<br>".join(how))
        for t in s.get("laps") or []:
            rows = "".join('<tr><td class="mute">%d</td><td>%s</td><td class="mono">%s</td><td class="mute">%s</td></tr>'
                           % (i + 1, e(r["name"]), e(r["time"]), e(r["car"])) for i, r in enumerate(t["top"]))
            parts.append('<details class="small laps" style="margin-top:8px"><summary>🏁 Lap times: <b>%s</b> (%s)</summary>'
                         '<table>%s</table></details>' % (e(t["name"]), "sprint" if t["kind"] == "sprint" else "loop", rows))
        if s.get("champ"):
            c = s["champ"]
            rows = "".join('<tr><td class="mute">%d</td><td>%s</td><td class="mono">%d pts</td><td class="mute">%d win%s</td></tr>'
                           % (i + 1, e(r["name"]), r["points"], r["wins"], "" if r["wins"] == 1 else "s") for i, r in enumerate(c["top"]))
            parts.append('<details class="small laps" style="margin-top:8px"><summary>🏆 <b>%s</b> standings (%d race%s)</summary><table>%s</table></details>'
                         % (e(c["name"]), c["races"], "" if c["races"] == 1 else "s", rows))
        if s.get("drift"):
            rows = "".join('<tr><td class="mute">%d</td><td>%s</td><td class="mono">%d</td><td class="mute">%s</td></tr>'
                           % (i + 1, e(r["name"]), r["score"], e(r["car"])) for i, r in enumerate(s["drift"]))
            parts.append('<details class="small laps" style="margin-top:8px"><summary>💨 Best drifts on this map</summary><table>%s</table></details>' % rows)
        h = s["history"]
        parts.append('<div class="bars">%s</div><div class="row small mute" style="justify-content:space-between"><span>30 days ago</span><span>today</span></div>'
                     % "".join(bar(x["pct"]) for x in h["days"]))
        parts.append('<div class="stats small"><span>Last 24 h <b>%s</b></span><span>7 days <b>%s</b></span><span>30 days <b>%s</b></span></div></div>'
                     % (pct(h["d1"]), pct(h["d7"]), pct(h["d30"])))
    first = d["servers"][0] if d["servers"] else None
    desc = (d.get("about") or "").replace("\n", " ")[:150]
    if first:
        live = label.get(first["state"], first["state"]).split(" - ")[0]
        if first["state"] == "up":
            live += " · %d/%s players%s" % (first["players"], first["max"] or "?", (" · " + first["map"]) if first["map"] else "")
        desc = (live + (" - " + desc if desc else ""))[:200]
    return STATUS_HTML.replace("__DESC__", e(desc or "BeamMP server")).replace("__TITLE__", e(d["title"])).replace("__BODY__", "".join(parts)).replace(
        "__UPDATED__", e(time.strftime("%H:%M", time.localtime(d["updated"])))).replace(
        "__CREDIT__", ('Hosted with <a href="%s" rel="noopener" style="color:inherit">BeamMP EasyServer</a>' % e(SITE_URL))
        if APP.settings.get("credit_link") else "BeamMP EasyServer")


# ----------------------------------------------------------------------------- timed announcements (fixed times)
def timed_msgs(inst):
    v = inst.meta.get("timed_msgs")
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


# ----------------------------------------------------------------------------- phone app (installable web app)
LANG_PATH_RE = re.compile(r"/lang/([a-z]{2}(?:-[a-z]{2})?)\.json")
LANG_DIR = os.path.join(HERE, "lang")


def lang_index():
    """The translations next to the dashboard (lang/xx.json): [{"code", "name"}]. Adding a language = adding a file."""
    out = []
    try:
        names = sorted(os.listdir(LANG_DIR))
    except OSError:
        return out
    for n in names:
        m = LANG_PATH_RE.fullmatch("/lang/" + n)
        if not m:
            continue
        d = read_json(os.path.join(LANG_DIR, n), {})
        name = d.get("language") if isinstance(d, dict) else None
        if isinstance(name, str) and name.strip():
            out.append({"code": m.group(1), "name": name.strip()[:40]})
    return out
APP_FILES = ("/manifest.webmanifest", "/sw.js", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png")
# Network first, so the dashboard is always live; the cached page only shows
# when the server can't be reached. API answers are never cached.
SW_JS = r"""const C = "es-shell-v2";
self.addEventListener("install", e => { self.skipWaiting(); e.waitUntil(caches.open(C).then(c => c.addAll(["/icon-192.png"])).catch(() => {})); });
self.addEventListener("activate", e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== C).map(k => caches.delete(k))))
  .then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.startsWith("/api/")) return;
  if (e.request.mode === "navigate") { e.respondWith(fetch(e.request).catch(() => asleep())); return; }
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
// The server doesn't answer: it's probably asleep. Offer to wake it up through the wake helper.
async function asleep() {
  let w = null;
  try { const r = await (await caches.open(C)).match("/__wake.json"); if (r) w = await r.json(); } catch (x) {}
  const ns = w && /^https:\/\/[A-Za-z0-9.\-]{1,253}(:\d{1,5})?$/.test(w.server || "") ? w.server : "";
  const ok = !!ns && /^beammp-wake-[A-Za-z0-9]{20,40}$/.test(w.topic || "");
  const data = JSON.stringify(ok ? {s: ns, t: w.topic} : null).replace(/</g, "\\u003c");
  const csp = "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'self'; connect-src "
    + (ok ? ns : "'none'") + "; base-uri 'none'; form-action 'none'";
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#2a78d6"><title>BeamMP - asleep?</title><style>
body{margin:0;font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#151514;color:#eee;display:flex;min-height:100vh;align-items:center;justify-content:center}
main{max-width:380px;padding:28px;text-align:center}img{width:72px;height:72px;border-radius:18px}h1{font-size:21px;margin:14px 0 6px}
p{color:#aaa;margin:6px 0 18px}button{font:inherit;font-weight:600;border:0;border-radius:10px;padding:12px 20px;margin:5px;cursor:pointer}
.b{background:#2a78d6;color:#fff}.g{background:#2b2b29;color:#eee}#m{min-height:24px;color:#cfe3ff}</style></head><body><main>
<img src="/icon-192.png" alt=""><h1>The server isn't answering</h1><p>The server computer is probably asleep to save power.</p>
<div id="w"></div><button class="g" id="r">Try again</button><p id="m"></p></main><script>
const W=${data}, m=document.getElementById("m");
document.getElementById("r").onclick=()=>location.reload();
if(W){const b=document.createElement("button");b.className="b";b.textContent="Wake it up";document.getElementById("w").appendChild(b);
b.onclick=async()=>{b.disabled=true;m.textContent="Sending…";try{const r=await fetch(W.s+"/"+W.t,{method:"POST",body:"wake"});
if(!r.ok)throw 0;let n=45;const t=setInterval(()=>{m.textContent="Waking up… trying again in "+n+" s";if(--n<0){clearInterval(t);location.reload();}},1000);}
catch(x){b.disabled=false;m.textContent="Couldn't send the wake-up - check your internet connection.";}};}
else m.textContent="To wake it, use your router's Wake-on-LAN or set up the wake helper (dashboard: Settings, Sleep & wake-up).";
</script></body></html>`;
  return new Response(html, {status: 503, headers: {"Content-Type": "text/html; charset=utf-8", "Content-Security-Policy": csp, "Cache-Control": "no-store"}});
}
"""
_ICONS = {}


def app_icon_png(size):
    """The app icon: the EasyServer steering wheel (its open top + orange bar is a power symbol), drawn in pure Python."""
    if size in _ICONS:
        return _ICONS[size]
    import math
    import zlib
    k = size / 512.0 / 0.8                     # logo units -> pixels, content kept in the round-icon safe zone
    off = size / 2.0 - 256 / 0.8 * size / 512.0 * 0.8

    def seg(px, py, ax, ay, bx, by):           # distance to a line segment
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / float(dx * dx + dy * dy)))
        return math.hypot(px - ax - t * dx, py - ay - t * dy)
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            # back to logo units (512 box, wheel centred)
            u = (x + 0.5 - size / 2.0) / (size / 512.0) * 0.8 + 256
            v = (y + 0.5 - size / 2.0) / (size / 512.0) * 0.8 + 256 - 8
            px = 1.0 / (size / 512.0 / 0.8)    # one pixel in logo units
            g = (x + y) / (2.0 * size)         # background gradient
            bg = (int(47 + (23 - 47) * g), int(140 + (71 - 140) * g), int(255 + (184 - 255) * g))
            # rim: circle (256,268) r 136, open at the top (|angle| < 28 deg), round ends
            d = math.hypot(u - 256, v - 268)
            ang = math.degrees(math.atan2(u - 256, 268 - v))
            if abs(ang) > 28:
                rim = abs(d - 136)
            else:
                rim = min(math.hypot(u - 192, v - 148), math.hypot(u - 320, v - 148))
            white = min(rim - 20, seg(u, v, 124, 300, 388, 300) - 17, seg(u, v, 256, 300, 256, 392) - 17, math.hypot(u - 256, v - 300) - 44)
            hole = 17 - math.hypot(u - 256, v - 300)                          # blue dot in the hub
            bar = seg(u, v, 256, 104, 256, 214) - 20
            cw = max(0.0, min(1.0, 0.5 - white / px))
            ch = max(0.0, min(1.0, 0.5 + hole / px))
            cb = max(0.0, min(1.0, 0.5 - bar / px))
            t = max(0.0, min(1.0, (v - 92) / 130.0))
            orange = (255, int(178 + (101 - 178) * t), int(74 + (22 - 74) * t))
            col = [bg[i] + (255 - bg[i]) * cw for i in range(3)]
            col = [col[i] + ((31, 95, 214)[i] - col[i]) * ch for i in range(3)]
            col = [col[i] + (orange[i] - col[i]) * cb for i in range(3)]
            row += bytes(int(c) for c in col)
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), 9)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", raw) + chunk(b"IEND", b"")
    _ICONS[size] = png
    return png


def cert_sha256():
    """SHA-256 fingerprint of the dashboard's HTTPS certificate (hex, no colons) - the Android app pins it."""
    try:
        with open(os.path.join(TLS_DIR, "cert.pem")) as f:
            pem = f.read()
        der = base64.b64decode("".join(l for l in pem.splitlines() if l and not l.startswith("-----")))
        return hashlib.sha256(der).hexdigest()
    except (OSError, ValueError):
        return ""


# ----------------------------------------------------------------------------- sleep + Wake-on-LAN
# The computer can go to sleep when nobody plays and be woken up again by a
# "magic packet" from the router, the phone app or the always-on wake helper
# (another device at home, e.g. a Raspberry Pi), or by itself before an event.
WAKE_TOPIC_RE = re.compile(r"beammp-wake-[A-Za-z0-9]{20,40}")
HHMM_RE = re.compile(r"([01]\d|2[0-3]):[0-5]\d")
WIN_WAKE_TASK = "BeamMP EasyServer wake-up"
_POWER = {"t": 0, "data": None}


def _ps(cmd, timeout=40):
    return subprocess.run(["powershell.exe", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                          timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def win_power_status():
    ps = ("$r=@(); foreach($a in Get-NetAdapter -Physical -ErrorAction SilentlyContinue){"
          "$pm=Get-NetAdapterPowerManagement -Name $a.Name -ErrorAction SilentlyContinue;"
          "$ip=Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue|Select-Object -First 1;"
          "$r+=[pscustomobject]@{name=$a.Name;desc=$a.InterfaceDescription;mac=$a.MacAddress;up=($a.Status -eq 'Up');"
          "wifi=($a.NdisPhysicalMedium -eq 9 -or \"$($a.PhysicalMediaType)\" -match '802\\.11|Wireless');"
          "magic=\"$($pm.WakeOnMagicPacket)\";ip=\"$($ip.IPAddress)\";prefix=[int]$ip.PrefixLength}};"
          "$armed=(powercfg /devicequery wake_armed) -join \"`n\";"
          "$hib=(powercfg /a) -join \"`n\";"
          "$bat=(Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue|Select-Object -First 1);"
          "[pscustomobject]@{adapters=$r;armed=$armed;sleep=$hib;battery=($null -ne $bat);bstatus=[int]$bat.BatteryStatus}|ConvertTo-Json -Depth 4 -Compress")
    try:
        raw = json.loads(_ps(ps).stdout or "{}")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raw = {}
    armed = str(raw.get("armed") or "")
    ads = raw.get("adapters") or []
    if isinstance(ads, dict):
        ads = [ads]
    out = []
    for a in ads:
        if not isinstance(a, dict):
            continue
        ip, prefix = str(a.get("ip") or ""), int(a.get("prefix") or 0)
        brd = ""
        try:
            if ip and prefix:
                brd = str(ipaddress.ip_network("%s/%d" % (ip, prefix), strict=False).broadcast_address)
        except ValueError:
            pass
        magic = str(a.get("magic") or "")
        if a.get("wifi"):
            wol = "wifi"
        elif magic == "Unsupported":
            wol = "unsupported"
        elif magic == "Enabled" and str(a.get("desc") or "") in armed:
            wol = "on"
        elif magic in ("Enabled", "Disabled"):
            wol = "off"
        else:
            wol = "unknown"
        out.append({"name": str(a.get("name") or "")[:80], "desc": str(a.get("desc") or "")[:120],
                    "mac": str(a.get("mac") or "").replace("-", ":").lower(), "wifi": bool(a.get("wifi")),
                    "cable": bool(a.get("up")), "ip": ip, "prefix": prefix, "brd": brd, "wol": wol})
    sl = str(raw.get("sleep") or "")
    avail = sl.split("not available")[0] if sl else ""
    can = bool(re.search(r"Standby \((S3|S0 Low Power Idle)\)", avail)) if sl else True
    kind = "deep" if "Standby (S3)" in avail else ("s2idle" if "S0 Low Power Idle" in avail else "")
    for a in out:
        a["os_wake"] = "enabled" if a["wol"] == "on" else "unknown"
    laptop = bool(raw.get("battery"))
    return {"ok": True, "adapters": out, "can_sleep": can, "rtc": True, "persist": True, "sleep_kind": kind,
            "deep_available": kind == "deep",
            "power": {"laptop": laptop, "ac": (int(raw.get("bstatus") or 0) == 2) if laptop else None}}


def power_status(force=False):
    """Network adapters, Wake-on-LAN state and whether this computer can sleep (cached for a minute)."""
    with LOCK:
        if not force and _POWER["data"] and time.time() - _POWER["t"] < 60:
            return _POWER["data"]
    if IS_WIN:
        d = win_power_status()
    else:
        d = control("power-status", timeout=45)
        if not d.get("ok"):
            d = {"ok": False, "msg": d.get("msg"), "adapters": [], "can_sleep": False, "rtc": False}
    ads = [a for a in d.get("adapters") or [] if isinstance(a, dict)]
    me = lan_ip()
    main = (next((a for a in ads if a.get("ip") == me and not a.get("wifi")), None)
            or next((a for a in ads if not a.get("wifi") and a.get("cable")), None)
            or next((a for a in ads if not a.get("wifi")), None))
    d["main"] = main["name"] if main else ""
    d["on_wifi"] = bool(next((a for a in ads if a.get("ip") == me and a.get("wifi")), None))
    if main and re.fullmatch(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", main.get("mac") or ""):
        with LOCK:
            st = APP.state
            new = {"wol_mac": main["mac"], "wol_brd": main.get("brd") or "", "wol_ip": main.get("ip") or ""}
            if any(st.get(k) != v for k, v in new.items()):
                st.update(new)
                changed = True
            else:
                changed = False
        if changed:
            APP.save_state()
    with LOCK:
        _POWER.update(t=time.time(), data=d)
    return d


def wol_score(st):
    """How ready this computer is to be woken up over the network: 0-100 with every reason and its fix.
    Checks: [id, title, state (pass/warn/fail/unknown), weight, what it means, what to do]."""
    app = APP
    ads = st.get("adapters") or []
    main = next((a for a in ads if a.get("name") == st.get("main")), None)
    pw = st.get("power") or {}
    win = IS_WIN
    checks = []

    def add(cid, title, state, weight, why, fix=""):
        checks.append({"id": cid, "title": title, "state": state, "weight": weight, "why": why, "fix": fix})

    # 1. a network cable
    if main and main.get("cable"):
        add("cable", "Network cable", "pass", 20, "The computer is connected to the router with a cable (%s)." % main["name"])
    elif main:
        add("cable", "Network cable", "fail", 20, "The cable adapter (%s) has no cable plugged in%s." % (
            main["name"], " - the computer uses Wi-Fi" if st.get("on_wifi") else ""),
            "Plug a network cable into the computer and the router (or a switch), then press Refresh. "
            "Wake-on-LAN doesn't work over Wi-Fi.")
    else:
        add("cable", "Network cable", "fail", 20, "This computer has no built-in network cable port that was found.",
            "Wake-on-LAN needs a built-in network port. Most USB network adapters can't wake a computer up.")
    # 2. the network chip can do it
    if not main:
        add("support", "Network chip supports Wake-on-LAN", "fail", 15, "No cable adapter to check.", "See above.")
    elif main.get("wol") == "unsupported":
        add("support", "Network chip supports Wake-on-LAN", "fail", 15,
            "The network chip (%s) says it can't wake the computer with a magic packet." % main["name"],
            "Check the BIOS first (it can hide the feature). If it's still unsupported, the network port can't do it - "
            "a different (built-in or PCIe) network card is needed.")
    elif main.get("wol") in ("on", "off"):
        add("support", "Network chip supports Wake-on-LAN", "pass", 15, "The network chip can wake the computer up.")
    else:
        add("support", "Network chip supports Wake-on-LAN", "unknown", 15,
            "Couldn't ask the network chip%s." % (" (the ethtool program is missing)" if main.get("wol") == "no-ethtool" else ""),
            "Press Turn on next to the adapter - it installs what's missing and checks again.")
    # 3. switched on in the operating system
    if main and main.get("wol") == "on":
        add("enabled", "Wake-on-LAN switched on", "pass", 20, "Wake-on-LAN is on for %s." % main["name"])
    elif main and main.get("wol") in ("no-ethtool", "unknown"):
        add("enabled", "Wake-on-LAN switched on", "unknown", 20, "Couldn't check whether it's on.",
            "Press Turn on next to the adapter%s." % (" and click Yes on the Windows permission prompt" if win else ""))
    elif main and main.get("wol") != "unsupported":
        add("enabled", "Wake-on-LAN switched on", "fail", 20, "Wake-on-LAN is off for %s." % main["name"],
            "Press Turn on next to the adapter%s." % (" and click Yes on the Windows permission prompt" if win else ""))
    # 4. stays on after a reboot (Linux)
    if not win and main and main.get("wol") == "on":
        if st.get("persist"):
            add("persist", "Stays on after a restart", "pass", 5, "It's switched on again every time the computer starts.")
        else:
            add("persist", "Stays on after a restart", "warn", 5, "Wake-on-LAN is on now but may switch off after a restart.",
                "Press Turn on once more - that also keeps it on after restarts.")
    # 5. the system lets the card wake it
    if main and main.get("os_wake") == "disabled":
        add("oswake", "Allowed to wake the computer", "fail", 10, "The system doesn't let the network card wake the computer.",
            "Press Turn on next to the adapter - it allows this too.")
    # 6. can sleep, and which kind
    if not st.get("can_sleep"):
        add("sleep", "Can go to sleep", "fail", 10, "This computer has no sleep mode that was found.",
            "Turn on sleep (S3 / Suspend to RAM) in the BIOS, and update the graphics/chipset drivers.")
    elif st.get("sleep_kind") == "s2idle":
        add("sleep", "Sleep mode", "warn", 10,
            "The computer uses the modern 'S0 / s2idle' sleep. Many network chips can't wake it from that%s." % (
                " - the classic 'deep' sleep is also available" if st.get("deep_available") else ""),
            ("Switch to deep sleep: in Linux add mem_sleep_default=deep to the kernel options, or" if not win else "If waking doesn't work,") +
            " look in the BIOS for 'Sleep state' / 'S3' / 'Linux sleep' and pick S3.")
    else:
        add("sleep", "Can go to sleep", "pass", 10, "The computer supports sleep%s." % (" (S3 / deep)" if st.get("sleep_kind") == "deep" else ""))
    # 7. laptops on mains power
    if pw.get("laptop"):
        if pw.get("ac") is False:
            add("ac", "Plugged into power", "fail", 10, "This laptop is running on battery. Most laptops only wake up over the network when plugged in.",
                "Plug in the charger and leave it plugged in.")
        else:
            add("ac", "Plugged into power", "pass", 10, "The laptop is plugged in. Keep it plugged in - most laptops only wake up over the network on mains power.")
    # 8. a way to wake it from outside the house
    h = app.secrets.has("WAKE_TOPIC")
    seen = app.state.get("helper_seen") or 0
    if h and now() - seen < 7 * 86400:
        add("remote", "Can be woken from anywhere", "pass", 5, "The wake helper answered %s." % ("today" if now() - seen < 86400 else "this week"))
    elif h:
        add("remote", "Can be woken from anywhere", "warn", 5, "A wake helper is set up but hasn't answered a test recently.",
            "Press Test the helper. If it doesn't answer, check that the helper device is on and online.")
    else:
        add("remote", "Can be woken from anywhere", "warn", 5,
            "Only from home (phone on the Wi-Fi, or your router) - not from Discord or when you're away.",
            "Set up the wake helper below, or check the router guide (a FRITZ!Box can do it by itself).")
    # 9. BIOS - can't be read from here
    proven = (app.state.get("woke_at") or 0) > (app.state.get("slept_at") or 0) > 0 and \
        not (app.state.get("wake_at") and abs((app.state.get("woke_at") or 0) - app.state["wake_at"]) < 600)
    if proven:
        add("bios", "BIOS setting", "pass", 5, "The computer has already woken up from sleep without its alarm clock - the BIOS allows it.")
    else:
        add("bios", "BIOS setting", "unknown", 5, "The BIOS setting can't be read from here.",
            "Test it: Sleep now, then wake it from your phone or router. If nothing happens, turn on 'Wake on LAN' / "
            "'Power On By PCI-E' and turn off 'ErP' / 'Deep Sleep' in the BIOS.")
    total = sum(c["weight"] for c in checks)
    got = sum(c["weight"] * (1 if c["state"] == "pass" else 0.5 if c["state"] in ("warn", "unknown") else 0) for c in checks)
    score = int(round(100 * got / total)) if total else 0
    fails = [c for c in checks if c["state"] == "fail"]
    if fails:
        verdict = "Won't work yet - fix the red items"
    elif score >= 90:
        verdict = "Ready"
    else:
        verdict = "Should work - test it once"
    if fails:
        score = min(score, 40)              # anything red means it won't wake up yet
    return {"score": score, "verdict": verdict, "blocking": len(fails), "checks": checks}


def wol_target():
    """(mac, [broadcast addresses], ip) of the network cable adapter, as last seen."""
    st = APP.state
    brd = [b for b in (st.get("wol_brd"),) if b]
    return st.get("wol_mac") or "", brd, st.get("wol_ip") or ""


def magic_packet(mac):
    m = bytes.fromhex(re.sub(r"[^0-9a-fA-F]", "", mac))
    if len(m) != 6:
        raise ValueError("bad MAC address")
    return b"\xff" * 6 + m * 16


def next_wake_at():
    """When the computer should wake up by itself: 10 minutes before the next event and/or a daily time."""
    s, t = APP.settings, now()
    cands = []
    if s.get("sleep_wake_events"):
        with LOCK:
            insts = list(INSTANCES.values())
        for inst in insts:
            for e in events_cfg(inst):
                if e.get("on", True):
                    st = event_next_start(e, t + 660)
                    if st:
                        cands.append(st - 600)
    w = s.get("sleep_wake_at") or ""
    if HHMM_RE.fullmatch(w):
        h, m = (int(x) for x in w.split(":"))
        lt = time.localtime(t)
        for add in (0, 1):
            c = int(time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + add, h, m, 0, 0, 0, -1)))
            if c > t + 120:
                cands.append(c)
                break
    cands = [c for c in cands if c > t + 120]
    return min(cands) if cands else 0


def set_wake_timer(at):
    """Ask the computer to wake up by itself at `at` (0 = cancel). Returns an error text or ""."""
    try:
        if IS_WIN:
            cmd = "Unregister-ScheduledTask -TaskName '%s' -Confirm:$false -ErrorAction SilentlyContinue" % WIN_WAKE_TASK
            if at:
                cmd += ("; $t=New-ScheduledTaskTrigger -Once -At ([DateTime]::Parse('%s'));"
                        "$a=New-ScheduledTaskAction -Execute 'cmd.exe' -Argument '/c exit';"
                        "$s=New-ScheduledTaskSettingsSet -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries;"
                        "Register-ScheduledTask -TaskName '%s' -Action $a -Trigger $t -Settings $s -RunLevel Limited | Out-Null"
                        % (time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(at)), WIN_WAKE_TASK))
            r = _ps(cmd)
            return "" if r.returncode == 0 else (r.stderr.strip()[-200:] or "failed")
        r = control("rtc-wake", at=int(at or 0), timeout=30)
        return "" if r.get("ok") else (r.get("msg") or "failed")
    except (OSError, subprocess.TimeoutExpired) as e:
        return short_err(e)


def win_sleep():
    """Windows: put the computer to sleep (not hibernate). Raises OSError if Windows refuses."""
    import ctypes
    from ctypes import wintypes
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    pwr = ctypes.WinDLL("powrprof", use_last_error=True)

    class LUID(ctypes.Structure):
        _fields_ = [("Low", wintypes.DWORD), ("High", wintypes.LONG)]

    class TP(ctypes.Structure):
        _fields_ = [("Count", wintypes.DWORD), ("Luid", LUID), ("Attr", wintypes.DWORD)]

    # every handle as a HANDLE: on 64-bit Windows a plain Python int is too big for the default C int
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.GetCurrentProcess.argtypes = []
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    adv.OpenProcessToken.restype = wintypes.BOOL
    adv.LookupPrivilegeValueW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.POINTER(LUID)]
    adv.LookupPrivilegeValueW.restype = wintypes.BOOL
    adv.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL, ctypes.POINTER(TP), wintypes.DWORD,
                                          ctypes.c_void_p, ctypes.c_void_p]
    adv.AdjustTokenPrivileges.restype = wintypes.BOOL
    pwr.SetSuspendState.argtypes = [wintypes.BOOLEAN, wintypes.BOOLEAN, wintypes.BOOLEAN]
    pwr.SetSuspendState.restype = wintypes.BOOLEAN

    tok = wintypes.HANDLE()
    if adv.OpenProcessToken(k32.GetCurrentProcess(), 0x0020 | 0x0008, ctypes.byref(tok)):   # ADJUST_PRIVILEGES | QUERY
        try:
            luid = LUID()
            if adv.LookupPrivilegeValueW(None, "SeShutdownPrivilege", ctypes.byref(luid)):
                adv.AdjustTokenPrivileges(tok, False, ctypes.byref(TP(1, luid, 0x2)), 0, None, None)   # SE_PRIVILEGE_ENABLED
        finally:
            k32.CloseHandle(tok)
    if not pwr.SetSuspendState(False, False, False):
        raise OSError("Windows refused to sleep (error %d) - check that sleep is allowed in Power Options"
                      % ctypes.get_last_error())


def in_time_window(frm, to, t=None):
    """True when the local time is between frm and to (HH:MM, may wrap past midnight). Empty = always."""
    if not (HHMM_RE.fullmatch(frm or "") and HHMM_RE.fullmatch(to or "")):
        return True
    lt = time.localtime(t or now())
    cur = lt.tm_hour * 60 + lt.tm_min
    a = int(frm[:2]) * 60 + int(frm[3:])
    b = int(to[:2]) * 60 + int(to[3:])
    return a <= cur < b if a <= b else (cur >= a or cur < b)


def wake_pairing_code():
    """What the wake helper needs, as one code to paste: where to send the magic packet, the
    private ntfy topic it listens on, and which Discord server it may answer /start in.
    The Discord bot token is NOT in it - the helper asks for that itself."""
    s = APP.settings
    mac, brd, ip = wol_target()
    d = {"v": 1, "mac": mac, "brd": brd, "ip": ip, "port": int(s.get("port") or 30815),
         "ntfy": (s.get("ntfy_server") or "https://ntfy.sh").rstrip("/"), "topic": APP.secrets.get("WAKE_TOPIC"),
         "guild": s.get("discord_bot_guild") or "", "users": list(s.get("discord_bot_users") or [])[:50],
         "name": (re.sub(r"\^[0-9a-fk-or]", "", server_name() or "").strip() or "BeamMP server")[:60]}
    return "ESW1-" + base64.urlsafe_b64encode(json.dumps(d, separators=(",", ":")).encode()).decode().rstrip("=")


def ntfy_wake_post(text, topic_suffix=""):
    s, topic = APP.settings, APP.secrets.get("WAKE_TOPIC")
    if not topic:
        raise ValueError("no wake helper set up")
    server = (s.get("ntfy_server") or "https://ntfy.sh").rstrip("/")
    req = urllib.request.Request("%s/%s%s" % (server, topic, topic_suffix), data=text.encode(), method="POST",
                                 headers={"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION, "Cache": "no"})
    with urllib.request.urlopen(req, timeout=15) as r:
        r.read()


def ntfy_wake_replies(since="30s"):
    s, topic = APP.settings, APP.secrets.get("WAKE_TOPIC")
    server = (s.get("ntfy_server") or "https://ntfy.sh").rstrip("/")
    req = urllib.request.Request("%s/%s-r/json?poll=1&since=%s" % (server, topic, since),
                                 headers={"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION})
    out = []
    with urllib.request.urlopen(req, timeout=15) as r:
        for line in r.read(200000).decode("utf-8", "replace").splitlines():
            try:
                m = json.loads(line)
            except ValueError:
                continue
            if isinstance(m, dict) and m.get("event") == "message":
                out.append(str(m.get("message") or "")[:200])
    return out


# ----------------------------------------------------------------------------- Discord webhook helpers
def webhook_parts():
    url = APP.secrets.get("DISCORD_WEBHOOK") if APP else ""
    m = re.fullmatch(r"https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api/webhooks/(\d+)/([\w-]+)", url or "")
    return (m.group(1), m.group(2)) if m else (None, None)


def webhook_call(method, suffix="", body=None, query=""):
    wid, wtok = webhook_parts()
    if not wid:
        raise ValueError("Add your Discord webhook under Settings -> Notifications first")
    return discord_api(method, "/webhooks/%s/%s%s%s" % (wid, wtok, suffix, query), body=body)


def webhook_channel():
    """The Discord channel the webhook posts to (the chat bridge listens there)."""
    key = APP.secrets.get("DISCORD_WEBHOOK")
    cache = getattr(APP, "_wh_chan", None)
    if cache and cache[0] == key:
        return cache[1]
    chan = str((webhook_call("GET") or {}).get("channel_id") or "")
    APP._wh_chan = (key, chan)
    return chan


def playtime_top(inst, days=30, n=10):
    use_server(inst.id)
    data = analytics(8)
    return data["top"][:n]


def fmt_hours(sec):
    h = sec / 3600.0
    return ("%.1f h" % h) if h >= 1 else ("%d min" % max(1, round(sec / 60)))


def set_mod_enabled(name, on):
    """Move a mod between Client (players download it) and Client-disabled. True if it moved."""
    name = safe_zip_name(name)
    if not name:
        return False
    a, b = os.path.join(I().CLIENT_DIR, name), os.path.join(I().DISABLED_DIR, name)
    src, dst = (b, a) if on else (a, b)
    if not os.path.exists(src) or os.path.exists(dst):
        return False
    r = modscan.cached_result(src)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)
    if r:
        modscan.remember(dst, r.get("sha256"))
    return True


# ----------------------------------------------------------------------------- mod storage + mod sets
UPLOAD_SPARE = 512 * 1024 ** 2     # room left over after an upload (logs, backups, the game server itself)
MODSET_MAX = 30


def mods_storage(inst, mods):
    """How much room the mods take and how much is left on their drive (None when unknown)."""
    free = total = None
    for p in (inst.CLIENT_DIR, inst.RES, inst.SERVER_DIR):
        try:
            u = shutil.disk_usage(p)
            free, total = u.free, u.total
            break
        except OSError:
            continue
    return {"free": free, "total": total, "mods": sum(m["size"] for m in mods),
            "low": free is not None and free < 2 * 1024 ** 3, "spare": UPLOAD_SPARE}


def upload_room_error(size):
    """A message when an upload of size bytes won't fit (both the upload folder and the mods folder need it)."""
    for p in {UPLOAD_TMP, I().CLIENT_DIR}:
        try:
            free = shutil.disk_usage(p).free
        except OSError:
            continue
        if size + UPLOAD_SPARE > free:
            return ("Not enough space on this computer: the mod needs %s and only %s is free. Delete or turn off "
                    "mods you don't play, or use a bigger drive." % (fmt_bytes(size), fmt_bytes(max(0, free - UPLOAD_SPARE))))
    return None


def clean_set_name(n):
    n = re.sub(r"\s+", " ", str(n or "")).strip()
    if not n or len(n) > 40 or not re.fullmatch(r"[\w .,'!&()+#\-]+", n):
        raise ValueError("Give the mod set a short name (up to 40 letters, numbers and spaces)")
    return n


def mod_sets(inst):
    v = inst.meta.get("mod_sets")
    out = []
    for x in v if isinstance(v, list) else []:
        if isinstance(x, dict) and isinstance(x.get("name"), str) and isinstance(x.get("mods"), list):
            out.append({"name": x["name"], "mods": [n for n in x["mods"] if isinstance(n, str) and safe_zip_name(n) == n]})
    return out


def mods_in_use(mods, inst):
    """The mods that are part of the server right now: on, or parked by light mode (they come back with their map)."""
    parked = set(parked_maps(inst))
    return sorted((m["name"] for m in mods if (m["enabled"] or m["name"] in parked) and m["name"] != TOOLS_MOD), key=str.lower)


def mod_sets_view(inst, mods):
    have = {m["name"]: m for m in mods}
    now_on = set(mods_in_use(mods, inst))
    out = []
    for x in mod_sets(inst):
        present = [n for n in x["mods"] if n in have]
        out.append({"name": x["name"], "mods": x["mods"], "missing": [n for n in x["mods"] if n not in have],
                    "size": sum(have[n]["size"] for n in present), "active": set(present) == now_on})
    return out


def apply_mod_set(inst, names):
    """Turn on exactly the mods in names (the tools mod is left alone). Returns (turned on, turned off, missing)."""
    want = set(names)
    mods = list_mods()
    have = {m["name"]: m for m in mods}
    parked = set(parked_maps(inst))
    on, off = [], []
    for n, m in have.items():
        if n == TOOLS_MOD:
            continue
        if n in want and not m["enabled"]:
            if set_mod_enabled(n, True):
                on.append(n)
        elif n not in want and m["enabled"]:
            if set_mod_enabled(n, False):
                off.append(n)
    if inst.meta.get("light_maps"):
        set_server_meta(inst.id, parked_maps=[])
        light_sync(inst)        # map mods of other maps go back to waiting for their map
    elif parked:
        set_server_meta(inst.id, parked_maps=None)
    on = [n for n in on if n not in parked]
    return on, off, sorted(want - set(have), key=str.lower)


# ----------------------------------------------------------------------------- scheduled events
EVENT_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def events_cfg(inst):
    ev = inst.meta.get("events")
    return [e for e in ev if isinstance(e, dict)] if isinstance(ev, list) else []


EVENT_GAMES = {"race": "Races (/race)", "drift": "Drift points (/drift)", "cnr": "Cops and robbers (/cnr)"}


def event_next_start(e, t):
    """The next start time (local) of a weekly event, or of a one-off event (date), at or after t - 1 minute."""
    h, m = (int(x) for x in e["at"].split(":"))
    if e.get("date"):
        try:
            y, mo, d = (int(x) for x in e["date"].split("-"))
            st = int(time.mktime((y, mo, d, h, m, 0, 0, 0, -1)))
        except (ValueError, OverflowError):
            return None
        return st if st >= t - 60 else None
    lt = time.localtime(t)
    for add in range(0, 8):
        day = time.localtime(time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + add, 0, 0, 0, 0, 0, -1)))
        if day.tm_wday not in e["days"]:
            continue
        st = int(time.mktime((day.tm_year, day.tm_mon, day.tm_mday, h, m, 0, 0, 0, -1)))
        if st >= t - 60:
            return st
    return None


def event_results(act, end):
    """What happened during an event (from its start until end): players, best laps, best drifts."""
    start = int(act.get("start") or 0)
    if not start:
        return None
    names = [n for n in (act.get("online") or []) if isinstance(n, str) and n][:50]   # already on when it started
    for ev in read_events(start):
        if ev.get("ev") == "join" and ev["t"] <= end:
            n = str(ev.get("name") or "")[:64]
            if n and n not in names:
                names.append(n)
    laps = []
    for track, rows in read_laptimes().items():
        rows = [r for r in rows if start <= r["t"] <= end]
        if rows:
            laps.append((track, rows[0]))
    laps.sort(key=lambda x: x[1]["ms"])
    drifts = sorted((r for r in read_drift() if start <= r["t"] <= end), key=lambda r: -r["score"])[:5]
    return {"players": names, "laps": [{"track": tr, "name": r["name"], "time": fmt_lap(r["ms"]), "car": r["car"]} for tr, r in laps[:5]],
            "drifts": [{"name": r["name"], "score": r["score"], "car": r["car"]} for r in drifts]}


def event_results_text(name, res):
    lines = ["🏁 **%s** is over - %d player%s joined." % (discord_escape(name), len(res["players"]), "" if len(res["players"]) == 1 else "s")]
    if res["players"]:
        lines.append("Thanks to " + ", ".join(discord_escape(n) for n in res["players"][:25]) + ("..." if len(res["players"]) > 25 else ""))
    if res["laps"]:
        lines.append("**Fastest laps**")
        lines += ["%s **%s** - %s (%s%s)" % (("🥇", "🥈", "🥉", "4.", "5.")[i], discord_escape(r["name"]), r["time"], discord_escape(r["track"]),
                                           (", " + discord_escape(r["car"])) if r["car"] else "") for i, r in enumerate(res["laps"])]
    if res["drifts"]:
        lines.append("**Best drifts**")
        lines += ["%s **%s** - %d points%s" % (("🥇", "🥈", "🥉", "4.", "5.")[i], discord_escape(r["name"]), r["score"],
                                             (" (%s)" % discord_escape(r["car"])) if r["car"] else "") for i, r in enumerate(res["drifts"])]
    return "\n".join(lines)


MEDALS = ("🥇", "🥈", "🥉")


def _medal(i):
    return MEDALS[i] if i < 3 else "%d." % (i + 1)


def discord_player_embed(name):
    name = name.strip()
    if not name:
        return {"description": "Type a BeamMP player name, for example /player Dani", "color": 0x64748B}
    with LOCK:
        ids = sorted(INSTANCES, key=lambda i: (i != "main", i))
    use_server("main")
    cards = player_everywhere(name, ids)
    use_server("main")
    if not cards:
        return {"description": "%s hasn't played here in the last year." % discord_escape(name), "color": 0x64748B}
    real = cards[0]["name"]
    total = sum(c["seconds"] for c in cards)
    last = max((c["last_seen"] or 0 for c in cards), default=0)
    online = [c["server"] for c in cards if c["online"]]
    lines = ["**Time played:** %s (%s in the last 30 days)" % (fmt_hours(total), fmt_hours(sum(c["seconds_30d"] for c in cards))),
             "**Online now** on %s" % ", ".join(discord_escape(x) for x in online) if online else
             ("**Last seen:** <t:%d:R>" % last if last else "")]
    for c in cards:
        bits = []
        if len(cards) > 1 or len(ids) > 1:
            bits.append("__%s__ - %s" % (discord_escape(c["server"]), fmt_hours(c["seconds"])))
        for l in c["laps"][:3]:
            bits.append("🏁 %s: %s (#%d of %d)" % (discord_escape(l["track"]), l["time"], l["pos"], l["of"]))
        if c["drift"]:
            bits.append("💨 Best drift: %d points" % c["drift"]["score"])
        if c["champ"]:
            bits.append("🏆 Championship: #%d of %d, %d points" % (c["champ"]["pos"], c["champ"]["of"], c["champ"]["points"]))
        if c["records"]:
            bits.append("⚡ Top speed %d km/h" % c["records"]["speed"])
        if c["badges"]:
            bits.append("🎖️ %d badge%s" % (c["badges"], "" if c["badges"] == 1 else "s"))
        lines += bits
    return {"title": real, "description": "\n".join(x for x in lines if x)[:3900], "color": 0x22C55E if online else 0x3B82F6}


def discord_leaderboard_embed(inst, what):
    here = I().id
    use_server(inst.id)
    try:
        title, lines = "", []
        suffix = (" (%s)" % inst.name) if len(INSTANCES) > 1 else ""
        if what == "drift":
            best = {}
            for r in read_drift():
                if r["score"] > best.get(r["name"], {"score": -1})["score"]:
                    best[r["name"]] = r
            title = "Best drifts" + suffix
            lines = ["%s **%s** - %d points (%s)" % (_medal(i), discord_escape(r["name"]), r["score"], discord_escape(map_name(r["raw_map"]) or r["raw_map"]))
                     for i, r in enumerate(sorted(best.values(), key=lambda r: -r["score"])[:10])]
        elif what == "champ":
            rows, rounds = read_champ()
            cfg = read_games_cfg()
            title = "%s standings%s" % (cfg["champ_name"] or "Championship", suffix)
            lines = ["%s **%s** - %d points, %d win%s" % (_medal(i), discord_escape(r["name"]), r["points"], r["wins"], "" if r["wins"] == 1 else "s")
                     for i, r in enumerate(rows[:10])] if rounds else []
            if lines:
                lines.append("_%d race%s so far_" % (rounds, "" if rounds == 1 else "s"))
        elif what == "time":
            title = "Most played - last 30 days" + suffix
            lines = ["%s **%s** - %s" % (_medal(i), discord_escape(p["name"]), fmt_hours(p["seconds"])) for i, p in enumerate(playtime_top(inst))]
            use_server(inst.id)
        else:
            title = "Lap records" + suffix
            for t in sorted(laps_summary(3), key=lambda t: -t["drivers"])[:6]:
                if t["top"]:
                    lines.append("**%s**" % discord_escape(t["name"]))
                    lines += ["%s %s - %s" % (_medal(i), discord_escape(r["name"]), r["time"]) for i, r in enumerate(t["top"])]
        return {"title": title, "description": "\n".join(lines)[:3900] or "Nothing here yet - go set some records!", "color": 0xF5A524}
    finally:
        use_server(here)


def upcoming_events_text():
    t = now()
    rows = []
    with LOCK:
        insts = list(INSTANCES.values())
    for inst in insts:
        for e in events_cfg(inst):
            if not e.get("on", True):
                continue
            st = event_next_start(e, t)
            act = inst.meta.get("event_active")
            if isinstance(act, dict) and act.get("id") == e.get("id"):
                rows.append((t, "🔴 **%s** - happening now on %s (map %s), until %s" % (
                    discord_escape(e["name"]), discord_escape(inst.name), discord_escape(e["map"]),
                    time.strftime("%H:%M", time.localtime(act["end"])))))
            elif st:
                rows.append((st, "📅 **%s** - <t:%d:F> (<t:%d:R>), %s, map %s" % (
                    discord_escape(e["name"]), st, st, discord_escape(inst.name), discord_escape(e["map"]))))
    rows.sort()
    return "\n".join(r for _, r in rows[:10]) or "No events planned."


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
        if maintenance_cfg(inst)["on"]:
            lines.insert(0, "🛠️ **Maintenance** - only admins can join")
        fields.append({"name": "%s %s" % (STATE_EMOJI.get(st, "⚪"), discord_escape(inst.name))[:250],
                       "value": "\n".join(lines)[:1000], "inline": False})
    return fields


def fmt_uptime(sec):
    d, h, m = sec // 86400, sec % 86400 // 3600, sec % 3600 // 60
    return ("%dd %dh" % (d, h)) if d else ("%dh %dm" % (h, m)) if h else "%d min" % max(m, 1)


def discord_escape(s):
    """Text from players shown in Discord: no formatting, no pings and no masked links like
    [free mods](https://phishing.example) that hide where they really go."""
    return re.sub(r"([\\*_~`|>@#<\[\]()-])", r"\\\1", str(s))


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
                "status_msg": bool(s.get("discord_status_msg")), "bridge": bool(s.get("discord_bridge")),
                "bridge_server": s.get("discord_bridge_server") or "main", "has_webhook": bool(webhook_parts()[0]),
                "servers": [{"id": i.id, "name": i.name} for i in sorted(INSTANCES.values(), key=lambda i: (i.id != "main", i.id))],
                "invite": ("https://discord.com/oauth2/authorize?client_id=%s&scope=bot%%20applications.commands&permissions=68608"
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
                elif e.code == 4014:
                    self.error = ("The chat bridge needs permission to read messages: Developer Portal → your app → Bot → "
                                  "turn on MESSAGE CONTENT INTENT → Save, then press Save here again.")
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
        # GUILDS (names of the Discord servers); with the chat bridge also GUILD_MESSAGES + MESSAGE_CONTENT
        intents = 1 | ((512 | 32768) if self.app.settings.get("discord_bridge") else 0)
        ws.send(json.dumps({"op": 2, "d": {"token": token, "intents": intents,
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
            elif op == 0 and t == "MESSAGE_CREATE":
                self.on_message(d)
            elif op == 0 and t == "INTERACTION_CREATE":
                threading.Thread(target=self.on_interaction, args=(d,), daemon=True).start()

    def on_message(self, d):
        """Chat bridge, Discord -> game: messages in the webhook's channel go to the game chat."""
        s = self.app.settings
        if not s.get("discord_bridge") or d.get("webhook_id") or (d.get("author") or {}).get("bot"):
            return
        if str(d.get("guild_id") or "") != (s.get("discord_bot_guild") or "x"):
            return
        try:
            if str(d.get("channel_id")) != webhook_channel():
                return
        except Exception:
            return
        a = d.get("author") or {}
        who = clean_player_name((d.get("member") or {}).get("nick") or a.get("global_name") or a.get("username"))
        text = re.sub(r"<a?:(\w+):\d+>", r":\1:", str(d.get("content") or ""))          # custom emoji -> :name:
        text = re.sub(r"<[@#][!&]?\d+>", "@someone", text)
        text = clean_msg(text)[:150]
        if not text:
            return
        with LOCK:
            inst = INSTANCES.get(s.get("discord_bridge_server") or "main") or INSTANCES.get("main")
        use_server(inst.id)
        if inst.server.status()["state"] == "running":
            chat_say("[Discord] %s: %s" % (who, text))

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
            {"name": "top", "description": "Who played the most in the last 30 days", "type": 1, "contexts": [0],
             "options": opts},
            {"name": "whitelist", "description": "Manage who can join (the allow-list)", "type": 1, "contexts": [0],
             "default_member_permissions": str(PERM_MANAGE_GUILD),
             "options": [{"type": 3, "name": "action", "description": "What to do", "required": True,
                          "choices": [{"name": "add", "value": "add"}, {"name": "remove", "value": "remove"},
                                      {"name": "list", "value": "list"}, {"name": "on (invite-only)", "value": "on"},
                                      {"name": "off (anyone can join)", "value": "off"}]},
                         {"type": 3, "name": "player", "description": "BeamMP player name", "required": False,
                          "max_length": 40}] + opts},
            {"name": "events", "description": "Upcoming events on the BeamMP server", "type": 1, "contexts": [0]},
            {"name": "player", "description": "A player's stats: time played, best laps, drifts, championship", "type": 1, "contexts": [0],
             "options": [{"type": 3, "name": "name", "description": "BeamMP player name", "required": True, "max_length": 40}]},
            {"name": "leaderboard", "description": "The best lap times, drifts, championship or most played", "type": 1, "contexts": [0],
             "options": [{"type": 3, "name": "what", "description": "Which leaderboard", "required": True,
                          "choices": [{"name": "lap times", "value": "laps"}, {"name": "drift", "value": "drift"},
                                      {"name": "championship", "value": "champ"}, {"name": "most played", "value": "time"}]}] + opts},
            {"name": "join", "description": "Open the server so you can join (it closes again once nobody plays)", "type": 1,
             "contexts": [0], "options": opts},
            {"name": "sleep", "description": "Put the server computer to sleep to save power (/start wakes it up)",
             "type": 1, "contexts": [0], "default_member_permissions": str(PERM_MANAGE_GUILD)},
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
            opts = {o.get("name"): o.get("value") for o in (d.get("data") or {}).get("options") or []}
            if name == "top":
                with LOCK:
                    inst = INSTANCES.get(str(opts.get("server") or "main")) or INSTANCES["main"]
                discord_api("POST", cb, body={"type": 5})
                top = playtime_top(inst)
                medal = ["🥇", "🥈", "🥉"]
                lines = ["%s **%s** - %s" % (medal[i] if i < 3 else "%d." % (i + 1), discord_escape(p["name"]),
                                             fmt_hours(p["seconds"])) for i, p in enumerate(top)]
                return discord_api("PATCH", edit, body={"embeds": [{
                    "title": "Most played - last 30 days" + (" (%s)" % inst.name if len(INSTANCES) > 1 else ""),
                    "description": "\n".join(lines) or "Nobody has played yet.", "color": 0xF5A524}],
                    "allowed_mentions": {"parse": []}})
            if name == "events":
                discord_api("POST", cb, body={"type": 5})
                return discord_api("PATCH", edit, body={"embeds": [{"title": "Upcoming events", "color": 0x8B5CF6,
                                                                    "description": upcoming_events_text()}],
                                                        "allowed_mentions": {"parse": []}})
            if name == "player":
                discord_api("POST", cb, body={"type": 5})
                return discord_api("PATCH", edit, body={"embeds": [discord_player_embed(str(opts.get("name") or "")[:40])],
                                                        "allowed_mentions": {"parse": []}})
            if name == "leaderboard":
                with LOCK:
                    inst = INSTANCES.get(str(opts.get("server") or "main")) or INSTANCES["main"]
                discord_api("POST", cb, body={"type": 5})
                return discord_api("PATCH", edit, body={"embeds": [discord_leaderboard_embed(inst, str(opts.get("what") or "laps"))],
                                                        "allowed_mentions": {"parse": []}})
            if name == "join":
                with LOCK:
                    inst = INSTANCES.get(str(opts.get("server") or "main")) or INSTANCES["main"]
                discord_api("POST", cb, body={"type": 5})
                return discord_api("PATCH", edit, body={"content": self.do_join(inst, who), "allowed_mentions": {"parse": []}})
            if name not in ("start", "stop", "restart", "whitelist", "sleep"):
                return
            perms = int(member.get("permissions") or 0)
            if not (perms & (PERM_ADMIN | PERM_MANAGE_GUILD)) and uid not in (self.app.settings.get("discord_bot_users") or []):
                return discord_api("POST", cb, body={"type": 4, "data": {
                    "content": "Only people with **Manage Server** (or who are allowed in the dashboard) can do that.",
                    "flags": 64}})
            if name == "sleep":
                return discord_api("POST", cb, body={"type": 4, "data": {"content": self.do_sleep(who),
                                                                         "allowed_mentions": {"parse": []}}})
            with LOCK:
                inst = INSTANCES.get(str(opts.get("server") or "main"))
            if not inst:
                return discord_api("POST", cb, body={"type": 4, "data": {"content": "That server doesn't exist any more.", "flags": 64}})
            if name == "whitelist":
                return discord_api("POST", cb, body={"type": 4, "data": {
                    "content": self.do_whitelist(inst, opts.get("action"), str(opts.get("player") or ""), who),
                    "allowed_mentions": {"parse": []}}})
            discord_api("POST", cb, body={"type": 5})
            discord_api("PATCH", edit, body={"content": self.do_action(inst, name, who), "allowed_mentions": {"parse": []}})
        except Exception as e:
            sys.stderr.write("discord command: %s\n" % short_err(e))

    def do_whitelist(self, inst, action, player, who):
        use_server(inst.id)
        on, names = read_allowlist()
        label = discord_escape(inst.name)
        if action == "list":
            return ("**%s** is %s. On the list (%d): %s" % (label, "invite-only" if on else "open to everyone", len(names),
                                                            ", ".join(discord_escape(n) for n in names[:60]) or "nobody")
                    + (" …" if len(names) > 60 else ""))[:1900]
        if action in ("on", "off"):
            if action == "on" and not names:
                return "Add at least one player first: /whitelist add <name>"
            write_allowlist(action == "on", names)
            activity(who, "/whitelist %s" % action, "discord", server=inst.id)
            self.app.notifier.add("moderation", "Allow-list turned %s from Discord" % action, "By %s." % who[:60], "info", send=False)
            return ("🔒 **%s** is now invite-only (%d players)." % (label, len(names)) if action == "on"
                    else "🔓 Anyone can join **%s** now." % label)
        try:
            clean = clean_allow_names([player])
        except ValueError as e:
            return "❌ %s" % discord_escape(e)
        if not clean:
            return "Type the BeamMP player name too, for example: /whitelist add Dani"
        n = clean[0]
        have = [x.lower() for x in names]
        if action == "add":
            if n.lower() in have:
                return "%s is already on the list." % discord_escape(n)
            try:
                write_allowlist(on, clean_allow_names(names + [n]))
            except ValueError as e:
                return "❌ %s" % discord_escape(e)
            msg = "✅ Added **%s** to the allow-list of %s." % (discord_escape(n), label)
        else:
            if n.lower() not in have:
                return "%s isn't on the list." % discord_escape(n)
            real = next(x for x in names if x.lower() == n.lower())
            write_allowlist(on, [x for x in names if x.lower() != n.lower()])
            msg = "➖ Removed **%s** from the allow-list of %s." % (discord_escape(real), label)
        activity(who, "/whitelist " + msg.replace("*", ""), "discord", server=inst.id)
        self.app.notifier.add("moderation", "Allow-list changed from Discord", "%s by %s." % (msg.replace("*", ""), who[:60]),
                              "info", send=False)
        return msg + ("" if on else " (The list isn't switched on - /whitelist on makes the server invite-only.)")

    def do_join(self, inst, who):
        """/join: anyone in the Discord server can open the port for a while ("Only when needed" mode)."""
        app = self.app
        use_server(inst.id)
        host, port, via_relay = game_address(inst)
        where = "BeamMP -> **Direct Connect** -> IP `%s` port `%s`" % (host, port)
        if inst.server.status().get("state") not in ("running", "starting"):
            return "😴 **%s** isn't running right now. Someone with Manage Server can /start it." % discord_escape(inst.name)
        if via_relay or not app.settings.get("upnp_on") or app.settings.get("upnp_mode") != "needed":
            return "✅ You can join right away: " + where
        last = getattr(self, "_join_t", 0)
        if now() - last < 20:
            return "⏳ Just opened - join now: " + where
        self._join_t = now()
        app.upnp_open_for(JOIN_OPEN)
        st = app.upnp_apply()
        ok = st["ports"] and not st.get("error") and all(r["ok"] for r in st["ports"])
        activity(who, "/join", "discord", server=inst.id)
        if not ok:
            app.notifier.add("network", "/join from Discord couldn't open the port",
                             "%s asked to join, but the router said: %s" % (who[:60], st.get("error") or "; ".join(
                                 "%s %s: %s" % (r["port"], r["proto"], r["error"]) for r in st["ports"] if not r["ok"])), "warning")
            return "❌ The router didn't open the port. The server owner got a message about it."
        app.notifier.add("network", "%s opened the server from Discord" % who[:60],
                         "The port is open for %d minutes, and stays open while anyone plays." % (JOIN_OPEN // 60), "info", send=False)
        return ("🔓 Open for the next %d minutes (and as long as anyone plays). Join now: %s"
                % (JOIN_OPEN // 60, where))

    def do_sleep(self, who):
        app = self.app
        why = app.sleep_blockers()
        if why and why != "the dashboard is being used":
            return "⏳ Not now: %s." % why
        if not power_status().get("can_sleep"):
            return "❌ This computer can't go to sleep."
        activity(who, "/sleep", "discord")
        r = app.go_sleep("Sent to sleep from Discord by %s." % who[:60])
        if not r.get("ok"):
            return "❌ %s" % discord_escape(r.get("msg") or "Couldn't go to sleep")
        msg = "💤 The server computer is going to sleep (by %s)." % discord_escape(who)
        if r.get("wake_at"):
            msg += " It wakes up by itself <t:%d:R>." % r["wake_at"]
        if app.secrets.has("WAKE_TOPIC"):
            msg += " Use **/start** to wake it up sooner."
        else:
            msg += " To wake it up: use your router's Wake-on-LAN, the phone app at home, or the power button."
        return msg

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
            if moved_note(inst):
                return "🚚 %s - start it on this computer from the dashboard if you really want it here too." % moved_note(inst)
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
        activity(who, "/%s %s" % (what, inst.name), "discord", server=inst.id)
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


# ----------------------------------------------------------------------------- dashboard users + roles
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ROLES = {"viewer": 0, "moderator": 1, "admin": 2, "owner": 3}
USER_RE = re.compile(r"[A-Za-z0-9_.\-]{2,24}")
# What each role may change (GET pages are open to every role unless listed in ADMIN_GET).
MOD_GET = {"/api/chat", "/api/reports", "/api/players/profile"}         # what players wrote: not for read-only viewers
MOD_WRITE = {"/api/reports/close", "/api/players/act", "/api/bans/add", "/api/bans/remove", "/api/allowlist", "/api/server/action",
             "/api/notifications/read", "/api/notifications/clear", "/api/security/ack", "/api/logout",
             "/api/events/stop", "/api/map", "/api/maintenance", "/api/players/note"}
VIEWER_WRITE = {"/api/logout", "/api/notifications/read", "/api/logs/explain", "/api/devices",
                "/api/me/password", "/api/me/2fa/begin", "/api/me/2fa/confirm", "/api/me/2fa/disable",
                "/api/me/discord/link", "/api/me/discord/unlink"}
OWNER_WRITE = {"/api/roles", "/api/teaminvite", "/api/discordlogin", "/api/plugins/fetch", "/api/plugins/upload", "/api/plugins/install", "/api/plugins/toggle", "/api/plugins/remove", "/api/plugins/adopt", "/api/users", "/api/password", "/api/2fa/begin", "/api/2fa/confirm", "/api/2fa/disable", "/api/remote",
               "/api/authkey", "/api/import", "/api/backups/restore", "/api/power/helper", "/api/servers/delete", "/api/statuspage", "/api/supporter",
               "/api/pi", "/api/machines", "/api/gdrive"}
ADMIN_GET = {"/api/gdrive", "/api/pi", "/api/machines", "/api/recap", "/api/export", "/api/backups/download", "/api/phoneapp", "/api/ntfy", "/api/power/offline",
             "/api/health/report", "/api/health/saved", "/api/users", "/api/activity", "/api/modpack", "/api/integrations", "/api/statuspage"}


def required_role(method, path):
    if method in ("GET", "HEAD"):
        return "admin" if path in ADMIN_GET else "moderator" if path in MOD_GET else "viewer"
    if path in OWNER_WRITE:
        return "owner"
    if path in VIEWER_WRITE:
        return "viewer"
    if path in MOD_WRITE:
        return "moderator"
    return "admin"


def hash_password(pw, salt=None, rounds=200000):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, rounds)
    return "pbkdf2-sha256$%d$%s$%s" % (rounds, salt.hex(), dk.hex())


def check_password(pw, stored):
    try:
        algo, rounds, salt, want = stored.split("$")
        if algo != "pbkdf2-sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(dk.hex(), want)
    except (ValueError, AttributeError):
        return False


def _users_sig(users):
    key = APP.secrets.get("USERS_KEY") if APP else ""
    if not key:
        return ""
    return hmac.new(key.encode(), json.dumps(users, sort_keys=True).encode(), hashlib.sha256).hexdigest()


def load_users():
    """The extra accounts. The file is signed with a key only the dashboard knows, so a file swapped in
    by someone else (a rogue server plugin, say) can't create accounts."""
    d = read_json(USERS_FILE, {})
    if not isinstance(d, dict) or not isinstance(d.get("users"), list):
        return []
    users = [x for x in d["users"] if isinstance(x, dict) and USER_RE.fullmatch(str(x.get("name", ""))) and role_ok(x.get("role"))]
    want = _users_sig(d["users"])
    if not want or not hmac.compare_digest(want, str(d.get("sig") or "")):
        if users and APP and not getattr(APP, "users_alerted", False):
            APP.users_alerted = True
            try:
                APP.alerts.raise_("users_tamper", "The list of dashboard accounts was changed outside the dashboard",
                                  "users.json doesn't carry the dashboard's signature, so all extra accounts are blocked. "
                                  "If you didn't edit it by hand, something else on this computer did.",
                                  sig=hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16])
            except Exception:
                pass
        return []
    return users


def save_users(users):
    if not APP.secrets.has("USERS_KEY"):
        APP.secrets.set("USERS_KEY", secrets.token_hex(32))
    write_json(USERS_FILE, {"users": users, "sig": _users_sig(users)})
    if not IS_WIN:
        try:
            os.chmod(USERS_FILE, 0o600)
        except OSError:
            pass


def find_user(name):
    name = str(name or "").lower()
    return next((u for u in load_users() if u["name"].lower() == name), None)


# ----------------------------------------------------------------------------- team access: custom roles, per-server access, invites, 2FA per account
# Permission groups a custom role can tick. Built-in roles keep their fixed rules (required_role).
PERM_GROUPS = [
    ("players", "Players", "Kick, mute, ban, unban, who can join"),
    ("server", "Start & stop", "Start, stop, restart, maintenance mode, restart schedule"),
    ("map", "Maps & events", "Switch the map, map rotation, map votes, events"),
    ("mods", "Mods", "Add, update, turn off and delete mods"),
    ("config", "Server config", "Config page: rules, vehicle rules, chat, messages, presets"),
    ("settings", "Dashboard settings", "Notifications, backups, Discord, updates, sleep - for every server on this computer"),
]
PERM_IDS = [g[0] for g in PERM_GROUPS]
_PG_EXACT = {
    "/api/players/act": "players", "/api/players/clear": "players", "/api/bans/add": "players", "/api/bans/remove": "players",
    "/api/allowlist": "players", "/api/chat": "players", "/api/reports": "players", "/api/reports/close": "players",
    "/api/players/profile": "players", "/api/players/note": "players", "/api/laps": "config",
    "/api/games": "config", "/api/recap": "config",
    "/api/server/action": "server", "/api/maintenance": "server", "/api/restarts": "server",
    "/api/map": "map", "/api/rotation": "map", "/api/mapvote": "map", "/api/events": "map", "/api/events/stop": "map",
    "/api/modbrowser/install": "mods", "/api/modpack/code": "mods", "/api/modpack": "mods",
    "/api/config/save": "config", "/api/config/restore": "config", "/api/config/validate": "config", "/api/preset": "config",
    "/api/template": "config", "/api/tools": "config", "/api/vehicles": "config", "/api/vehicles/preset": "config",
    "/api/vehicles/block": "config", "/api/moderation": "config", "/api/messages": "config", "/api/timed": "config",
    "/api/extras": "config", "/api/joinalerts": "config", "/api/invite": "config", "/api/resources": "config",
}
CUSTOM_ROLE_RE = re.compile(r"c_[a-z0-9]{6,12}")
# not about one server: an account limited to some servers may use them whichever server is picked
TEAM_ANY_SERVER = {"/api/servers", "/api/me", "/api/me/password", "/api/me/2fa/begin", "/api/me/2fa/confirm",
                   "/api/me/2fa/disable", "/api/devices", "/api/logout"}
ROLES_FILE = os.path.join(DATA_DIR, "roles.json")
INVITES_FILE = os.path.join(DATA_DIR, "team-invites.json")
INVITE_HOURS = 1        # an invite link only works for a short time: less time for it to leak
_TEAM_LOCK = threading.Lock()


def perm_group(method, path):
    """Which tick-box a request needs (None = anyone logged in, "owner" = never grantable)."""
    need = required_role(method, path)
    if need == "viewer":
        return None
    if need == "owner":
        return "owner"
    if path in _PG_EXACT:
        return _PG_EXACT[path]
    if path.startswith("/api/mods/"):
        return "mods"
    return "settings"


def _team_sig(kind, data):
    base = APP.secrets.get("USERS_KEY") if APP else ""
    if not base:
        return ""
    key = hmac.new(base.encode(), kind.encode(), hashlib.sha256).digest()
    return hmac.new(key, json.dumps(data, sort_keys=True).encode(), hashlib.sha256).hexdigest()


def _team_load(path, kind):
    d = read_json(path, {})
    if not isinstance(d, dict) or not isinstance(d.get("items"), list):
        return []
    want = _team_sig(kind, d["items"])
    if not want or not hmac.compare_digest(want, str(d.get("sig") or "")):
        return []
    return [x for x in d["items"] if isinstance(x, dict)]


def _team_save(path, kind, items):
    if not APP.secrets.has("USERS_KEY"):
        APP.secrets.set("USERS_KEY", secrets.token_hex(32))
    write_json(path, {"items": items, "sig": _team_sig(kind, items)})
    if not IS_WIN:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def load_roles():
    out = []
    for r in _team_load(ROLES_FILE, "custom-roles"):
        if CUSTOM_ROLE_RE.fullmatch(str(r.get("id", ""))) and isinstance(r.get("perms"), list):
            out.append({"id": r["id"], "name": clean_msg(r.get("name"))[:40] or r["id"],
                        "perms": [p for p in r["perms"] if p in PERM_IDS]})
    return out


def save_roles(roles):
    _team_save(ROLES_FILE, "custom-roles", roles)


def role_ok(role):
    return role in ("admin", "moderator", "viewer") or bool(CUSTOM_ROLE_RE.fullmatch(str(role or "")))


def user_role_for(u, server_id):
    """The role an extra account has on one server, or None (no access)."""
    sv = u.get("servers")
    if isinstance(sv, dict):
        r = sv.get(server_id)
        return r if role_ok(r) else None
    return u.get("role")


def team_allows(u, server_id, method, path, roles=None):
    """(ok, message) for an extra account doing method+path on server_id."""
    role = user_role_for(u, server_id)
    if role is None:
        return False, "Your account has no access to this server."
    limited = isinstance(u.get("servers"), dict)
    grp = perm_group(method, path)
    if grp == "owner":
        return False, "Only the owner can do that."
    if limited and grp == "settings":
        return False, "Your account only has access to some servers, so it can't change the dashboard settings."
    if role in ROLES:
        need = required_role(method, path)
        if ROLES[role] < ROLES[need]:
            return False, "Your account (%s) can't do that - ask an admin or the owner." % role
        return True, ""
    if grp is None:
        return True, ""
    cr = next((r for r in (roles if roles is not None else load_roles()) if r["id"] == role), None)
    if not cr or grp not in cr["perms"]:
        return False, "Your role (%s) doesn't include \"%s\" - ask the owner." % (
            cr["name"] if cr else "deleted role", dict((g[0], g[1]) for g in PERM_GROUPS).get(grp, grp))
    return True, ""


# --- two-step login for extra accounts. The key is stored encrypted with the accounts key.
def _seal(plain, kind="totp"):
    base = APP.secrets.get("USERS_KEY")
    nonce = secrets.token_bytes(16)
    key = hmac.new(base.encode(), kind.encode(), hashlib.sha256).digest()
    data = plain.encode()
    stream = b"".join(hmac.new(key, nonce + struct.pack(">I", i), hashlib.sha256).digest() for i in range(len(data) // 32 + 1))
    ct = bytes(a ^ b for a, b in zip(data, stream))
    mac = hmac.new(key, nonce + ct, hashlib.sha256).hexdigest()[:32]
    return "v1:%s:%s:%s" % (nonce.hex(), ct.hex(), mac)


def _unseal(sealed, kind="totp"):
    try:
        v, n, c, mac = str(sealed).split(":")
        nonce, ct = bytes.fromhex(n), bytes.fromhex(c)
        key = hmac.new(APP.secrets.get("USERS_KEY").encode(), kind.encode(), hashlib.sha256).digest()
        if v != "v1" or not hmac.compare_digest(hmac.new(key, nonce + ct, hashlib.sha256).hexdigest()[:32], mac):
            return ""
        stream = b"".join(hmac.new(key, nonce + struct.pack(">I", i), hashlib.sha256).digest() for i in range(len(ct) // 32 + 1))
        return bytes(a ^ b for a, b in zip(ct, stream)).decode()
    except (ValueError, AttributeError, UnicodeDecodeError):
        return ""


_USER_TOTP_LAST = {}


def user_totp_ok(u, code):
    secret = _unseal(u.get("totp", "")) if u.get("totp") else ""
    if not secret:
        return False
    code = re.sub(r"\s", "", str(code or ""))
    if not re.fullmatch(r"\d{6}", code):
        return False
    step = now() // 30
    for c in (step - 1, step, step + 1):
        if hmac.compare_digest(totp_code(secret, c), code):
            with LOCK:
                k = u["name"].lower()
                if c <= _USER_TOTP_LAST.get(k, 0):
                    return False
                _USER_TOTP_LAST[k] = c
            return True
    return False


def new_totp(label):
    secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
    lab = urllib.parse.quote("BeamMP EasyServer:%s" % label[:40])
    uri = "otpauth://totp/%s?secret=%s&issuer=BeamMP%%20EasyServer" % (lab, secret)
    try:
        qr_size, qr_path = qr_svg_path(uri)
    except ValueError:
        qr_size, qr_path = 0, ""
    return secret, {"secret": " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)), "uri": uri,
                    "qr_size": qr_size, "qr_path": qr_path}


def totp_matches(secret, code):
    code = re.sub(r"\s", "", str(code or ""))
    step = now() // 30
    return bool(re.fullmatch(r"\d{6}", code)) and any(hmac.compare_digest(totp_code(secret, c), code) for c in (step - 1, step, step + 1))


def ip_is_remote(ip):
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return True


# --- "Sign in with Discord" for team accounts (owner: password only)
# The Discord app's secret can't live in open-source code and Discord only sends people back to addresses
# registered in advance, so a tiny service (login-service/worker.js, run by the project) does the Discord
# part. It and this dashboard share a key (made when the owner turns the feature on); the dashboard signs
# the address to come back to, the service signs who logged in. Discord only replaces the password: two-step
# login and the "from the internet" rules stay the same.
LOGIN_SERVICE = (os.environ.get("ES_LOGIN_SERVICE") or "https://easyserver-login.easyserver-hq.workers.dev").rstrip("/")
DLOGIN_FILE = os.path.join(DATA_DIR, "discord-login.json")
DLOGIN_NONCE_RE = re.compile(r"[A-Za-z0-9_\-]{20,64}")
DISCORD_ID_RE = re.compile(r"\d{5,25}")


def _b64u(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64u_dec(s):
    s = str(s)
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def dlogin_conf():
    """{"inst": ..., "key": <raw key bytes>} once the owner turned Discord sign-in on, else None."""
    items = _team_load(DLOGIN_FILE, "discord-login")
    if not items or not items[0].get("on"):
        return None
    key = _unseal(items[0].get("key"), "dlogin")
    if not key or not re.fullmatch(r"[A-Za-z0-9_\-]{24}", str(items[0].get("inst") or "")):
        return None
    try:
        return {"inst": items[0]["inst"], "key": _b64u_dec(key)}
    except (ValueError, binascii.Error):
        return None


def dlogin_available():
    return bool(LOGIN_SERVICE)


def dlogin_set(on):
    if not on:
        items = _team_load(DLOGIN_FILE, "discord-login")
        _team_save(DLOGIN_FILE, "discord-login", [dict(items[0], on=False)] if items else [])
        return
    if not dlogin_available():
        raise ValueError("Discord sign-in isn't available yet")
    items = _team_load(DLOGIN_FILE, "discord-login")
    if items and items[0].get("inst") and _unseal(items[0].get("key"), "dlogin"):
        _team_save(DLOGIN_FILE, "discord-login", [dict(items[0], on=True)])
        return
    def ask():
        req = urllib.request.Request(LOGIN_SERVICE + "/register", data=b"{}", method="POST",
                                     headers={"User-Agent": "BeamMP-EasyServer/" + EASY_VERSION, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read(4096))
    try:
        try:
            d = ask()
        except urllib.error.URLError as e:
            d = win_post_json(LOGIN_SERVICE + "/register") if IS_WIN and isinstance(e.reason, ssl.SSLCertVerificationError) else None
            if d is None:
                raise
    except (OSError, ValueError) as e:
        raise ValueError("Couldn't reach the sign-in service (%s) - try again in a minute" % (getattr(e, "reason", None) or e))
    inst, key = str(d.get("inst") or ""), str(d.get("key") or "")
    if not re.fullmatch(r"[A-Za-z0-9_\-]{24}", inst) or not re.fullmatch(r"[A-Za-z0-9_\-]{43}", key):
        raise ValueError("The sign-in service gave an odd answer - try again later")
    if not APP.secrets.has("USERS_KEY"):
        APP.secrets.set("USERS_KEY", secrets.token_hex(32))
    _team_save(DLOGIN_FILE, "discord-login", [{"on": True, "inst": inst, "key": _seal(key, "dlogin"), "t": now()}])


def win_post_json(url):
    """POST {} and read a JSON answer through Windows' own HTTPS (PowerShell). Python on Windows can trip over an
    old expired certificate Windows still keeps in its store, while Windows itself picks the valid one - this
    is still a fully checked connection, just checked by Windows."""
    if not IS_WIN or not re.fullmatch(r"https://[A-Za-z0-9.\-]+(:\d{1,5})?/[a-z]+", url or ""):
        return None
    ps = ("[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; "
          "Invoke-RestMethod -UseBasicParsing -Method Post -TimeoutSec 20 -ContentType 'application/json' -Body '{}' "
          "-Uri '%s' | ConvertTo-Json -Compress" % url)
    try:
        out = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             timeout=40, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        d = json.loads(out.strip() or "null")
        return d if isinstance(d, dict) else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def dlogin_sig(key, text):
    return _b64u(hmac.new(key, text.encode(), hashlib.sha256).digest())


def dlogin_check_note(conf, raw):
    """The signed note the service sends back: {"sub", "name", "user", "nonce", "aud", ...} or None."""
    note, _, sig = str(raw or "").partition(".")
    if not note or len(note) > 2000 or not re.fullmatch(r"[A-Za-z0-9_\-]{43}", sig):
        return None
    if not hmac.compare_digest(dlogin_sig(conf["key"], "assert|" + note), sig):
        return None
    try:
        d = json.loads(_b64u_dec(note))
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return None
    if not isinstance(d, dict) or d.get("v") != 1 or d.get("inst") != conf["inst"] or not isinstance(d.get("exp"), int) or d["exp"] < now():
        return None
    if not DISCORD_ID_RE.fullmatch(str(d.get("sub") or "")) or not DLOGIN_NONCE_RE.fullmatch(str(d.get("nonce") or "")):
        return None
    return d


def find_user_by_discord(did):
    return next((u for u in load_users() if (u.get("discord") or {}).get("id") == did), None)


# --- invite links
def load_invites():
    t = now()
    return [x for x in _team_load(INVITES_FILE, "team-invites")
            if isinstance(x.get("hash"), str) and isinstance(x.get("expires"), int) and x["expires"] > t and not x.get("used")]


def save_invites(items):
    _team_save(INVITES_FILE, "team-invites", items)


def invite_hash(tok):
    return hashlib.sha256(("team-invite:" + str(tok)).encode()).hexdigest()


def find_invite(tok):
    if not re.fullmatch(r"[\w-]{30,60}", str(tok or "")):
        return None
    h = invite_hash(tok)
    return next((x for x in load_invites() if hmac.compare_digest(x["hash"], h)), None)


def clean_servers_map(raw):
    """{server id: role} limited to existing servers, or None for "all servers"."""
    if raw is None or raw == "all":
        return None
    if not isinstance(raw, dict):
        raise ValueError("servers must be \"all\" or a list of servers with a role each")
    with LOCK:
        known = set(INSTANCES)
    out = {}
    for sid, role in raw.items():
        if sid in known and role_ok(role):
            out[sid] = role
    if not out:
        raise ValueError("Pick at least one server")
    return out


def check_role_exists(role, roles=None):
    if role in ("admin", "moderator", "viewer"):
        return
    if not any(r["id"] == role for r in (roles if roles is not None else load_roles())):
        raise ValueError("Pick a role")


# ----------------------------------------------------------------------------- remembered devices ("stay logged in")
# A browser or the phone app can stay logged in for DEVICE_DAYS after the last visit (DEVICE_MAX_DAYS at most).
# Only a hash of each device token is stored, and the file is signed like users.json, so a token can't be read
# back from the file and a file written by something else can't add a device.
DEVICES_FILE = os.path.join(DATA_DIR, "devices.json")
DEVICE_COOKIE = "es_device"
DEVICE_DAYS = 30
DEVICE_MAX_DAYS = 90
DEVICES_PER_USER = 10
_DEV_LOCK = threading.Lock()


def _devices_sig(devs):
    # signed with its own key derived from the accounts key (no extra secret to store)
    base = APP.secrets.get("USERS_KEY") if APP else ""
    if not base:
        return ""
    key = hmac.new(base.encode(), b"remembered-devices", hashlib.sha256).digest()
    return hmac.new(key, json.dumps(devs, sort_keys=True).encode(), hashlib.sha256).hexdigest()


def _device_ok(d, t):
    try:
        return _device_ok_(d, t)
    except (TypeError, ValueError):
        return False


def _device_ok_(d, t):
    return (isinstance(d, dict) and re.fullmatch(r"[0-9a-f]{64}", str(d.get("hash", ""))) and str(d.get("id", ""))
            and float(d.get("last", 0)) > t - DEVICE_DAYS * 86400 and float(d.get("created", 0)) > t - DEVICE_MAX_DAYS * 86400)


def load_devices():
    d = read_json(DEVICES_FILE, {})
    if not isinstance(d, dict) or not isinstance(d.get("devices"), list):
        return []
    want = _devices_sig(d["devices"])
    if not want or not hmac.compare_digest(want, str(d.get("sig") or "")):
        return []                       # not written by the dashboard: trust none of it
    t = now()
    return [x for x in d["devices"] if _device_ok(x, t)]


def save_devices(devs):
    if not APP.secrets.has("USERS_KEY"):
        APP.secrets.set("USERS_KEY", secrets.token_hex(32))
    write_json(DEVICES_FILE, {"devices": devs, "sig": _devices_sig(devs)})
    if not IS_WIN:
        try:
            os.chmod(DEVICES_FILE, 0o600)
        except OSError:
            pass


def device_label(ua):
    """'Firefox on Windows', 'EasyServer app on Android' ... from the User-Agent (only for the list)."""
    ua = str(ua or "")
    if "EasyServerApp" in ua:
        return "EasyServer app on Android"
    osn = next((n for k, n in (("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Windows", "Windows"),
                                ("Mac OS", "Mac"), ("CrOS", "Chromebook"), ("Linux", "Linux")) if k in ua), "")
    br = next((n for k, n in (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("SamsungBrowser", "Samsung Internet"),
                               ("Chrome/", "Chrome"), ("Safari/", "Safari")) if k in ua), "Browser")
    return br + (" on " + osn if osn else "")


def _dev_hash(tok):
    return hashlib.sha256(str(tok).encode()).hexdigest()


def remember_device(user, ip, ua):
    tok = secrets.token_urlsafe(32)
    t = now()
    with _DEV_LOCK:
        devs = load_devices()
        mine = sorted([d for d in devs if d.get("user", "owner").lower() == user.lower()], key=lambda d: d["last"])
        drop = {id(d) for d in mine[:max(0, len(mine) - DEVICES_PER_USER + 1)]}
        devs = [d for d in devs if id(d) not in drop]
        devs.append({"id": secrets.token_hex(6), "hash": _dev_hash(tok), "user": user, "name": device_label(ua)[:60],
                     "created": t, "last": t, "ip": str(ip)[:45]})
        save_devices(devs)
    return tok


def device_login(tok, ip):
    """The account a remembered-device token belongs to, or None. Extra accounts only from the home network."""
    if not tok or not re.fullmatch(r"[\w-]{20,100}", tok):
        return None
    h = _dev_hash(tok)
    with _DEV_LOCK:
        devs = load_devices()
        d = next((x for x in devs if hmac.compare_digest(x["hash"], h)), None)
        if not d:
            return None
        user = d.get("user", "owner")
        role = "owner"
        if user.lower() != "owner":
            u = find_user(user)
            try:
                local = not ipaddress.ip_address(ip).is_global
            except ValueError:
                local = False
            if not u or u.get("disabled") or (not local and not (u.get("remote") and u.get("totp"))):
                return None
            user, role = u["name"], u["role"]
        t = now()
        if t - d["last"] > 3600 or d.get("ip") != ip:     # don't rewrite the file on every page load
            d["last"], d["ip"] = t, str(ip)[:45]
            save_devices(devs)
        return {"user": user, "role": role, "device": d["id"]}


def forget_devices(user=None, dev_id=None):
    """Forget one device (dev_id), every device of one account (user) or all of them (neither)."""
    with _DEV_LOCK:
        devs = load_devices()
        keep = [d for d in devs if not ((dev_id is None or d["id"] == dev_id) and
                                        (user is None or d.get("user", "owner").lower() == user.lower()))]
        if len(keep) != len(devs):
            save_devices(keep)
        return len(devs) - len(keep)


# ----------------------------------------------------------------------------- activity log
ACTIVITY_FILE = os.path.join(DATA_DIR, "activity.jsonl")
_ACT_LOCK = threading.Lock()
ACTION_LABELS = {
    "/api/server/action": "Server: {action}", "/api/config/save": "Changed the server settings",
    "/api/mods/upload": "Uploaded a mod", "/api/mods/action": "Mod {action}: {name}", "/api/mods/update": "Updated mod {name}",
    "/api/mods/rescan": "Re-checked mods", "/api/bans/add": "Banned {name}", "/api/bans/remove": "Unbanned {name}",
    "/api/players/act": "Player {action}: {name}", "/api/allowlist": "Changed the allow-list", "/api/settings": "Changed settings",
    "/api/password": "Changed the password", "/api/devices": "Forgot remembered devices", "/api/remote": "Changed internet access / HTTPS", "/api/authkey": "Changed the AuthKey",
    "/api/import": "Imported a backup", "/api/reports/close": "Marked a player report as handled", "/api/chat/clear": "Deleted the chat history", "/api/backups/restore": "Restored a nightly backup", "/api/mods/sets": "Mod set {action}: {name}", "/api/upnp": "Automatic port forwarding: {on}", "/api/modbrowser/install": "Installed a mod from the mod browser", "/api/supporter": "Changed the supporter licence", "/api/guard": "Unblocked an address in the BeamMP-only guard", "/api/invite": "Changed the invite message", "/api/map": "Switched the map to {map}", "/api/restarts": "Changed scheduled restarts",
    "/api/moderation": "Changed moderation settings", "/api/extras": "Changed cars & chat settings",
    "/api/messages": "Changed chat messages", "/api/rotation": "Changed map rotation", "/api/template": "Applied a template",
    "/api/backups/now": "Made a backup", "/api/events": "Changed events", "/api/events/stop": "Ended an event early",
    "/api/discordbot": "Changed the Discord bot", "/api/ntfy": "Changed phone notifications", "/api/power": "Changed sleep settings",
    "/api/power/sleep": "Put the computer to sleep", "/api/power/wol": "Turned on Wake-on-LAN", "/api/servers/create": "Created a server",
    "/api/servers/delete": "Deleted a server", "/api/servers/limits": "Changed server limits", "/api/users": "Users: {action} {name}",
    "/api/2fa/confirm": "Turned on two-step login", "/api/2fa/disable": "Turned off two-step login",
    "/api/timed": "Changed timed announcements", "/api/tools": "Changed the in-game tools (/tp, /repair)", "/api/vehicles": "Changed the vehicle rules", "/api/vehicles/preset": "Vehicle rules preset: {preset}", "/api/vehicles/block": "Blocked/allowed vehicle {jbm}", "/api/plugins/install": "Installed a server plugin", "/api/plugins/toggle": "Turned a server plugin on/off: {id}", "/api/plugins/remove": "Removed the server plugin {id}", "/api/modpack/code": "Installed mods from a mod pack code", "/api/mods/light": "Light mode for map mods: {on}", "/api/maintenance": "Maintenance mode {state}", "/api/preset": "Applied the preset {preset}", "/api/servers/clone": "Cloned a server",
    "/api/config/restore": "Restored an older config", "/api/statuspage": "Changed the status page", "/api/joinalerts": "Changed join alerts",
    "/api/laps": "Lap times: {action}", "/api/players/note": "Wrote a note about {name}",
    "/api/games": "Games: {action}", "/api/recap": "Changed the weekly recap",
    "/api/updates/install": "Installed a BeamMP update", "/api/duckdns": "Changed DuckDNS", "/api/integrations": "Changed notification integrations",
}
SAFE_FIELDS = ("action", "name", "player", "map", "state", "preset", "minutes", "reason", "enabled", "role", "on")


def activity(who, action, via="dashboard", ip="", server=None, ok=True):
    """One line in the admin activity log: who did what, from where, and when."""
    try:
        srv = server or (I().id if getattr(_TL, "inst", None) else "main")
    except Exception:
        srv = "main"
    line = json.dumps({"t": now(), "who": str(who)[:60], "via": via, "ip": ip, "server": srv,
                       "action": str(action)[:300], "ok": bool(ok)}, ensure_ascii=False)
    with _ACT_LOCK:
        try:
            if os.path.exists(ACTIVITY_FILE) and os.path.getsize(ACTIVITY_FILE) > 2 * 1024 ** 2:
                os.replace(ACTIVITY_FILE, ACTIVITY_FILE + ".1")
            with open(ACTIVITY_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def read_activity(limit=300, who="", via=""):
    rows = []
    for name in (ACTIVITY_FILE + ".1", ACTIVITY_FILE):
        try:
            with open(name, encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(r, dict) and (not who or str(r.get("who", "")).lower() == who.lower()) and (not via or r.get("via") == via):
                        rows.append(r)
        except OSError:
            continue
    return rows[-limit:][::-1]


def describe_action(path, body):
    label = ACTION_LABELS.get(path)
    vals = {}
    for k in SAFE_FIELDS:
        v = body.get(k) if isinstance(body, dict) else None
        if isinstance(v, (str, int, float, bool)):
            vals[k] = re.sub(r"[\r\n\t]", " ", str(v))[:60]
    if label:
        try:
            return re.sub(r"\s+", " ", label.format_map(type("D", (dict,), {"__missing__": lambda self, k: ""})(vals))).strip(" :")
        except (ValueError, KeyError):
            return label
    return path


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
        self.upnp_lock = threading.Lock()
        self.upnp_state = None
        self.sessions = {}
        self.fails = {}
        self.locked = {}
        self.global_fails = []
        self.totp_last = 0
        self.flood_applied = None      # (on, ports) last sent to the root helper
        self.flood_dropped = None
        self.flood_next = 0
        self.flood_lock = threading.Lock()
        self.guard = guard.Guard(read_json(GUARD_FILE, {}))
        self.guard_lock = threading.Lock()
        self.guard_applied = None      # (ports, ips) last handed to the firewall
        self.guard_err = ""
        self.idle_since = now()        # auto-sleep: nobody has played (or used the dashboard) since
        self.sleep_busy_why = ""
        self.last_use = 0              # last click in the dashboard (keeps the computer awake)
        self.sleeping = False
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

    def write_config_text(self, text, why=""):
        text = text if text.endswith("\n") else text + "\n"
        try:
            save_config_version(I(), self.read_config_text(), text, why)
        except Exception as e:
            sys.stderr.write("config history: %s\n" % short_err(e))
        if IS_WIN:
            tmp = I().CONFIG + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="\r\n") as f:
                f.write(text)
            os.replace(tmp, I().CONFIG)
        else:
            # in place: the dashboard user may write the file but not the server folder
            with open_shared(I().CONFIG, "w") as f:
                f.write(text)
        try:
            m = map_name(toml_parse(text)[0].get("General", {}).get("Map"))
            record_map(I(), m)
            light_sync(I(), m)
        except Exception as e:
            sys.stderr.write("map change: %s\n" % short_err(e))
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
        last = time.time()
        while True:
            time.sleep(10)
            gap, last = time.time() - last, time.time()
            if gap > 90:                        # the loop stood still: the computer was asleep
                try:
                    self.on_resume(gap)
                except Exception as e:
                    sys.stderr.write("resume: %s\n" % short_err(e))
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
            for name, fn in (("address check", self.addr_tick), ("backup", self.backup_tick),
                             ("duckdns", self.duck_tick), ("resources", self.resource_tick),
                             ("discord status", self.status_msg_tick), ("mod updates", self.mod_update_tick),
                             ("sleep", self.sleep_tick), ("health", self.health_tick), ("community", self.community_tick),
                             ("upnp", self.upnp_tick), ("supporter", self.supporter_tick), ("other computers", self.remote_tick)):
                try:
                    fn()
                except Exception as e:
                    sys.stderr.write("%s: %s\n" % (name, short_err(e)))
                use_server("main")
            try:
                if self.settings.get("update_check") and now() >= next_update:
                    next_update = now() + 6 * 3600
                    self.check_updates(notify=True)
            except Exception as e:
                sys.stderr.write("updates: %s\n" % short_err(e))

    # ---------- automatic port forwarding (UPnP)
    def upnp_ports(self):
        """[(port, proto)] for every server's game port."""
        with LOCK:
            ports = sorted({i.port() or 30814 for i in INSTANCES.values()})
        return [(p, pr) for p in ports for pr in ("TCP", "UDP")]

    def upnp_players(self):
        """How many players are on any of the servers right now."""
        with LOCK:
            dirs = [i.STATS_DIR for i in INSTANCES.values()]
        n = 0
        for d in dirs:
            o = read_json(os.path.join(d, "online.json"), None)
            if isinstance(o, dict) and now() - int(o.get("t", 0)) < 120:
                n += len(o.get("players") or [])
        return n

    def upnp_needed(self):
        """'Only when needed' mode: open while someone is playing, and for a while after an invite.
        The router drops knocks on a closed port, so an invite (or the Open button) is what opens it."""
        if self.settings.get("upnp_mode") != "needed":
            return True
        if self.upnp_players():
            until = now() + UPNP_IDLE
            if until - int(self.settings.get("upnp_open_until") or 0) > 60:
                self.settings.update_one("upnp_open_until", until)    # closes UPNP_IDLE after the last player leaves
            return True
        return now() < int(self.settings.get("upnp_open_until") or 0)

    def upnp_open_for(self, secs):
        self.settings.update_one("upnp_open_until", max(int(self.settings.get("upnp_open_until") or 0), now() + int(secs)))

    def upnp_wanted(self):
        return self.upnp_ports() if self.upnp_needed() else []

    def upnp_gateway(self, fresh=False):
        g = getattr(self, "_upnp_gw", None)
        if g and not fresh and time.time() - g[0] < 900:
            return g[1]
        gw = upnp.find_gateway()
        self._upnp_gw = (time.time(), gw)
        return gw

    def upnp_apply(self, fresh=False):
        """Open every game port on the router and close ones we opened that aren't needed any more."""
        with self.upnp_lock:
            st = {"t": now(), "ports": [], "error": None, "router": None, "external_ip": None, "local_ip": None}
            try:
                gw = self.upnp_gateway(fresh)
            except Exception as e:
                gw, st["error"] = None, "Couldn't look for the router: %s" % short_err(e)
            if not gw:
                st["error"] = st["error"] or ("Your router didn't answer. UPnP is probably switched off in its settings "
                                              "(look for \"UPnP\" and turn it on), or the router doesn't have it - then forward the port by hand.")
                self.upnp_state = st
                return st
            st.update(router=gw.name or gw.host, local_ip=gw.local_ip)
            try:
                st["external_ip"] = gw.external_ip()
            except Exception:
                pass
            want = self.upnp_wanted()
            done = []
            for port, proto in want:
                row = {"port": port, "proto": proto, "ok": False, "error": None, "lease": 0}
                try:
                    cur = gw.get(port, proto)
                    if cur and cur["client"] and cur["client"] != gw.local_ip:
                        row["error"] = "the router already forwards this port to another device (%s)" % cur["client"]
                    else:
                        if cur:                          # ours from last time: refresh it
                            try:
                                gw.delete(port, proto)
                            except upnp.UPnPError:
                                pass
                        row["lease"] = gw.add(port, proto)
                        row["ok"] = True
                        done.append([port, proto])
                except upnp.UPnPError as e:
                    row["error"] = str(e)
                except Exception as e:
                    row["error"] = short_err(e)
                st["ports"].append(row)
            # close what we opened earlier for a port that's no longer used
            for port, proto in [tuple(x) for x in (self.settings.get("upnp_mapped") or []) if isinstance(x, list) and len(x) == 2]:
                if (port, proto) not in want:
                    try:
                        gw.delete(port, proto)
                    except Exception:
                        pass
            self.settings.update_one("upnp_mapped", done)
            self.upnp_state = st
            return st

    def upnp_close(self):
        with self.upnp_lock:
            mapped = [tuple(x) for x in (self.settings.get("upnp_mapped") or []) if isinstance(x, list) and len(x) == 2]
            closed, err = 0, None
            if mapped:
                try:
                    gw = self.upnp_gateway()
                    for port, proto in mapped:
                        if gw and gw.delete(port, proto):
                            closed += 1
                except Exception as e:
                    err = short_err(e)
            self.settings.update_one("upnp_mapped", [])
            self.upnp_state = {"t": now(), "ports": [], "error": err, "router": None, "external_ip": None, "local_ip": None}
            return closed, err

    def supporter_tick(self):
        """Check the supporter licence once a day (it may have been refunded or the subscription ended)."""
        sup = dict(self.settings.get("supporter") or {})
        if not sup.get("instance_id") or not self.secrets.has("SUPPORTER_KEY") or now() - sup.get("checked", 0) < 86400:
            return
        sup["checked"] = now()
        try:
            d = ls_call("validate", license_key=self.secrets.get("SUPPORTER_KEY"), instance_id=sup["instance_id"])
        except Exception:
            self.settings.update_one("supporter", sup)          # offline: keep it for the grace period
            return
        info = ls_summary(d)
        was = sup.get("status")
        if d.get("valid") and (not LS_STORE_ID or info["store_id"] == LS_STORE_ID):
            sup.update(info, ok_at=now())
        else:
            sup.update(status=info["status"] or "invalid")
        self.settings.update_one("supporter", sup)
        if was == "active" and sup["status"] != "active":
            self.notifier.add("update", "Your supporter licence isn't active any more",
                              "Status: %s. Everything keeps working - only the supporter extras (early access) are off. "
                              "Thanks for supporting EasyServer!" % sup["status"], "info")

    def upnp_tick(self):
        """Keep the forwards in place: routers forget them after a reboot, and day-long ones need renewing."""
        if not self.settings.get("upnp_on") or relay_on():
            return
        st = getattr(self, "upnp_state", None) or {}
        if self.settings.get("upnp_mode") == "needed":
            is_open = bool(self.settings.get("upnp_mapped"))
            if self.upnp_needed() != is_open:              # time to open or close: do it now, not in 20 minutes
                self.upnp_apply()
                return
        every = 20 * 60 if not st.get("error") and all(r["ok"] for r in st.get("ports", [])) else 5 * 60
        if now() - st.get("t", 0) >= every:
            was_ok = bool(st) and not st.get("error") and all(r["ok"] for r in st.get("ports", []))
            new = self.upnp_apply(fresh=not was_ok)
            ok = not new.get("error") and all(r["ok"] for r in new.get("ports", []))
            if was_ok and not ok:
                self.notifier.add("network", "Automatic port forwarding stopped working",
                                  "The router no longer accepts the forward (%s). Friends outside your home may not be able to join. "
                                  "Health page -> Automatic port forwarding shows the details." % (new.get("error") or
                                  "; ".join("%s %s: %s" % (r["port"], r["proto"], r["error"]) for r in new["ports"] if not r["ok"])), "warning")

    # ---------- BeamMP-only guard
    def guard_ports(self):
        with LOCK:
            return sorted({i.port() or 30814 for i in INSTANCES.values()})

    def guard_loop(self):
        """Look at the connection table every second (cheap) while the guard is on."""
        saved = 0
        while True:
            time.sleep(1)
            if not self.settings.get("guard_on") or relay_on() or on_mac():
                if self.guard_applied != ((), ()):
                    self.guard_apply()
                time.sleep(4)
                continue
            try:
                with self.guard_lock:
                    new = self.guard.see(guard.connections(self.guard_ports()))
                    changed = new or self.guard.block_list() != list(self.guard_applied[1] if self.guard_applied else ())
                if changed or self.guard_applied is None:
                    self.guard_apply()
                for ip in new:
                    b = self.guard.blocked[ip]
                    activity("guard", "Blocked %s for %s: %s" % (ip, fmt_secs(int(b["until"] - b["at"])), b["why"]), "system")
                if new and len(self.guard.blocked) >= 3 and now() - self.state.get("guard_note", 0) > 6 * 3600:
                    self.state["guard_note"] = now()
                    self.notifier.add("network", "The BeamMP-only guard is blocking port scanners",
                                      "%d addresses kept knocking on your game port without ever playing, so they're blocked for now. "
                                      "Nothing to do - Settings -> BeamMP-only guard shows them." % len(self.guard.blocked), "info", send=False)
                if now() - saved > 60:
                    saved = now()
                    with self.guard_lock:
                        write_json(GUARD_FILE, self.guard.state())
            except Exception as e:
                self.guard_err = short_err(e)
                time.sleep(10)

    def guard_apply(self):
        """Hand the block list to the firewall (Linux root helper / Windows firewall task)."""
        on = bool(self.settings.get("guard_on")) and not relay_on() and not on_mac()
        with self.guard_lock:
            ports = tuple(self.guard_ports()) if on else ()
            ips = tuple(self.guard.block_list()) if on else ()
            write_json(GUARD_FILE, self.guard.state())
        key = (ports, ips)
        if key == self.guard_applied:
            return
        if IS_WIN:
            try:
                guard.write_block_file(GUARD_BLOCK_FILE, ports, ips)
                self.guard_err = ""
            except OSError as e:
                self.guard_err = "Couldn't write the block list: %s" % short_err(e)
                return
        else:
            r = control("guard-block", ports=list(ports), ips=list(ips), timeout=30)
            if not r.get("ok"):
                self.guard_err = r.get("msg") or "the server helper didn't answer"
                return
            self.guard_err = ""
        self.guard_applied = key

    def guard_status(self):
        """Is something actually blocking? (Windows: the firewall task leaves a note every minute.)"""
        if not IS_WIN:
            return {"enforced": not self.guard_err, "helper": True}
        try:
            age = now() - os.path.getmtime(GUARD_STATUS_FILE)
        except OSError:
            age = None
        return {"enforced": age is not None and age < 300 and not self.guard_err, "helper": age is not None and age < 300}

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

    def _rotation_tick(self, inst, S):
        """Map rotation (Config -> Map rotation): the next map from the list every few hours,
        with a countdown in the chat."""
        r = rotation_cfg(inst)
        maps = [m for m in r["maps"] if m in BUILTIN_MAPS or m in enabled_mod_maps()]
        if inst.meta.get("event_active"):
            return                                  # an event is running - it switches the map back itself
        if not r["on"] or len(maps) < 2:
            S.pop("rot", None)
            return
        t = now()
        key = json.dumps(r, sort_keys=True)
        rot = S.get("rot")
        if not rot or rot["key"] != key:
            nxt = next_clear(r, t)
            rot = S["rot"] = {"key": key, "at": nxt, "last_left": nxt - t}
        left = rot["at"] - t
        running = inst.server.status()["state"] == "running"
        online = online_names() if running else []
        cur = current_map()
        nxt_map = maps[(maps.index(cur) + 1) % len(maps)] if cur in maps else maps[0]
        if online and left > 0 and not r["empty_only"]:
            warn = r["warn"] * 60
            for p in sorted({600, 300, 120, 60, 30, 10, warn}, reverse=True):
                if 0 < p <= warn and rot["last_left"] > p >= left:
                    chat_say("Map rotation: switching to %s in %s." % (nxt_map, fmt_secs(p)))
                    break
        rot["last_left"] = left
        if left > 0:
            return
        if r["empty_only"] and online:
            if t - rot["at"] < 7200:
                return                              # wait for an empty server (up to 2 hours)
        else:
            if online:
                chat_say("Map rotation: switching to %s now - rejoin in a moment." % nxt_map)
                time.sleep(2)
            ok, note = self.switch_map(nxt_map)
            self.notifier.add("rotation", "Map rotation: %s" % nxt_map, note, "info" if ok else "warning")
        rot["at"] = next_clear(r, t + 61)
        rot["last_left"] = rot["at"] - t

    def backup_tick(self):
        """Nightly backup of every server's settings (Settings -> Backups)."""
        s = self.settings
        if not s.get("backup_on"):
            return
        t = time.localtime()
        today = time.strftime("%Y-%m-%d", t)
        h, m = (int(x) for x in (s.get("backup_at") or "03:30").split(":"))
        if self.state.get("backup_day") == today or (t.tm_hour, t.tm_min) < (h, m):
            return
        self.state["backup_day"] = today
        self.save_state()
        self.run_backups(bool(s.get("backup_mods")))

    def run_backups(self, include_mods):
        with LOCK:
            insts = list(INSTANCES.values())
        made, errors = [], []
        for inst in insts:
            try:
                made.append(make_backup(inst, include_mods))
            except Exception as e:
                errors.append("%s: %s" % (inst.name, short_err(e)))
        if errors:
            use_server("main")
            self.notifier.add("backup", "Backup failed", "Couldn't back up " + "; ".join(errors) +
                              ". Check that the disk isn't full.", "warning")
        if made and self.settings.get("backup_copy"):
            threading.Thread(target=self.copy_backups, args=(made,), daemon=True, name="backup-copy").start()
        if made and self.settings.get("gdrive_on") and gdrive_connected():
            threading.Thread(target=self.copy_backups, args=(made, "gdrive"), daemon=True, name="backup-gdrive").start()
        return made, errors

    def copy_backups(self, made, where=""):
        use_server("main")
        if where == "gdrive":
            try:
                note, ok = gdrive_copy(made), True
            except Exception as e:
                note, ok = str(e) if isinstance(e, RuntimeError) else short_err(e), False
                self.notifier.add("backup", "Google Drive copy failed", "The backups were made on this computer, but copying them "
                                  "to Google Drive failed: %s" % note, "warning")
            self.state["gdrive_last"] = {"t": now(), "ok": ok, "note": note}
            self.save_state()
            return
        try:
            note, ok = copy_backups(made), True
        except Exception as e:
            note, ok = str(e) if isinstance(e, RuntimeError) else short_err(e), False
            self.notifier.add("backup", "Backup copy failed", "The backups were made on this computer, but copying them "
                              "failed: %s" % note, "warning")
        self.state["backup_copy"] = {"t": now(), "ok": ok, "note": note}
        self.save_state()

    # ---------- commands from the other computers' dashboards (see "paired computers talk through files")
    def remote_tick(self):
        if not hasattr(self, "remote_done"):
            self.remote_done, self.remote_t, self.remote_last, self.remote_busy = [], 0, "", False
        try:
            names = sorted(os.listdir(REMOTE_IN))
        except OSError:
            names = []
        changed = False
        for n in names:
            p = os.path.join(REMOTE_IN, n)
            if REMOTE_CMD_RE.fullmatch(n):
                cmd = read_json(p, None)
                try:
                    os.remove(p)
                except OSError:
                    pass
                if not isinstance(cmd, dict) or not re.fullmatch(r"[0-9a-f]{8,32}", str(cmd.get("id") or "")):
                    continue
                if cmd.get("action") == "move-in":
                    if self.remote_busy:
                        self.remote_answer(cmd, {"ok": False, "note": "It's already putting a server in place - try again after."})
                    else:
                        self.remote_busy = True
                        threading.Thread(target=self.remote_move_in, args=(cmd,), daemon=True, name="move-in").start()
                    continue
                self.remote_answer(cmd, self.remote_do(cmd))
                changed = True
            else:
                try:                    # a move's file waits a day for its command (and a half-sent one, too)
                    old = now() - os.path.getmtime(p) > 86400
                    if (old or not (REMOTE_ZIP_RE.fullmatch(n) or n.startswith("."))) and (os.path.isfile(p) or os.path.islink(p)):
                        os.remove(p)
                except OSError:
                    pass
        if changed or now() - self.remote_t >= 30:
            self.remote_write()

    def remote_answer(self, cmd, r):
        self.remote_done = ([dict(r, id=str(cmd["id"]), action=str(cmd.get("action"))[:20], t=now())] + self.remote_done)[:10]
        self.remote_last = ""
        self.remote_write()

    def remote_write(self):
        self.remote_t = now()
        d = {"version": EASY_VERSION, "host": socket.gethostname()[:40], "servers": remote_snapshot(), "done": self.remote_done}
        key = json.dumps(d, sort_keys=True)
        if key == self.remote_last and now() - getattr(self, "remote_wrote", 0) < REMOTE_STALE // 2:
            return
        os.makedirs(REMOTE_IN, exist_ok=True)
        if not IS_WIN:
            os.chmod(REMOTE_DIR, 0o700)
            os.chmod(REMOTE_IN, 0o700)
        write_json(os.path.join(REMOTE_DIR, "status.json"), dict(d, t=now()))
        self.remote_last, self.remote_wrote = key, now()

    def remote_do(self, cmd):
        act = cmd.get("action")
        use_server("main")
        if act not in ("start", "stop", "restart"):
            return {"ok": False, "note": "This EasyServer doesn't know that command - update it."}
        if act == "start" and not I().meta.get("reviewed"):
            return {"ok": False, "note": "Open this computer's dashboard once and look over the settings first."}
        if act in ("start", "restart"):
            set_server_meta("main", moved_to=None)
        r = self.server.action(act)
        return {"ok": bool(r.get("ok")), "note": {"start": "Started.", "stop": "Stopped.", "restart": "Restarted."}[act]
                if r.get("ok") else (r.get("msg") or "It didn't work")}

    def remote_move_in(self, cmd):
        """A server moved here from another computer: a backup of this one first, then its settings, mods, bans,
        stats and games data, then start it."""
        name = str(cmd.get("file") or "")
        p = os.path.join(REMOTE_IN, name)
        try:
            use_server("main")
            if not REMOTE_ZIP_RE.fullmatch(name) or not os.path.isfile(p) or os.path.islink(p):
                return self.remote_answer(cmd, {"ok": False, "note": "The server's file didn't arrive - try again."})
            try:
                undo = make_backup(I(), False)
            except Exception as e:
                return self.remote_answer(cmd, {"ok": False, "note": "Couldn't save this computer's own settings first, so "
                                                "nothing was changed (%s)" % short_err(e)})
            cap = _Capture()
            Handler._import_zip(cap, p, {"settings": "1", "mods": "1", "games": "1"})
            code, body = cap.result
            if code != 200:
                return self.remote_answer(cmd, {"ok": False, "note": body.get("error") or "It couldn't be put in place"})
            rep = body.get("report") or {}
            set_server_meta("main", reviewed=True, moved_to=None)
            src = re.sub(r"[\x00-\x1f]", "", str(cmd.get("source") or "another computer"))[:80]
            self.notifier.add("backup", "A server moved here", "%s was moved to this computer. How this computer's server was "
                              "before is saved as a backup (%s)." % (src, undo), "info")
            r = self.server.action("restart" if self.server.status()["state"] == "running" else "start")
            nm, ng, nb = len(rep.get("mods_added") or []), len(rep.get("games") or []), len(rep.get("mods_blocked") or [])
            note = "Moved: the settings, %d mod%s and %d file%s of stats and games%s." % (
                nm, "" if nm == 1 else "s", ng, "" if ng == 1 else "s",
                (" - %d mod%s blocked by the virus check" % (nb, " was" if nb == 1 else "s were")) if nb else "")
            note += " The server is starting there." if r.get("ok") else " Start the server there yourself (%s)." % (r.get("msg") or "it didn't start")
            if not I().has_authkey():
                note += " It has no AuthKey yet: put yours in on its Settings page so it shows in the BeamMP server list."
            self.remote_answer(cmd, {"ok": True, "note": note})
        except Exception as e:
            self.remote_answer(cmd, {"ok": False, "note": "It stopped with an error: " + short_err(e)})
        finally:
            self.remote_busy = False
            try:
                os.remove(p)
            except OSError:
                pass

    def duck_tick(self, force=False):
        """Keep name.duckdns.org pointing at this home's current public IP."""
        dom, tok = self.settings.get("duckdns_domain"), self.secrets.get("DUCKDNS_TOKEN")
        if not (dom and tok):
            return
        t = now()
        if not force and t < self.state.get("duck_next", 0):
            return
        pip = public_ip()
        if not force and pip and pip == self.state.get("duck_ip") and t - self.state.get("duck_t", 0) < 86400:
            self.state["duck_next"] = t + 300
            return
        try:
            ok = duckdns_update(dom, tok)
        except Exception as e:
            ok, err = False, short_err(e)
        else:
            err = "DuckDNS said no - check the domain and the token"
        if ok:
            self.state.update({"duck_ip": pip, "duck_t": t, "duck_next": t + 300, "duck_err": ""})
        else:
            if not self.state.get("duck_err"):
                self.notifier.add("network", "DuckDNS update failed",
                                  "%s.duckdns.org couldn't be updated (%s). Friends using that name may not "
                                  "reach the server until this works again." % (dom, err), "warning")
            self.state.update({"duck_next": t + 600, "duck_err": err})
        self.save_state()
        return ok

    def resource_tick(self):
        """Once a minute: computer CPU, memory and upload. Warns when the computer
        can't keep up, with a suggestion for the player limit."""
        t = now()
        if t < getattr(self, "res_next", 0):
            return
        self.res_next = t + 60
        cpu, (tot, avail), up = sys_cpu_percent(), sys_mem(), sys_upload_kbps()
        with LOCK:
            insts = list(INSTANCES.values())
        players = 0
        for inst in insts:
            use_server(inst.id)
            if inst.server.status()["state"] == "running":
                players += len(online_names())
        use_server("main")
        o = read_json(os.path.join(INSTANCES["main"].STATS_DIR, "online.json"), None) if "main" in INSTANCES else None
        ping = o.get("ping") if isinstance(o, dict) and t - int(o.get("t", 0)) < 120 and isinstance(o.get("ping"), int) else None
        sample = {"t": t, "cpu": cpu, "mem_total": tot, "mem_free": avail, "up_kbps": up, "players": players, "ping": ping}
        if "res_hist" not in self.__dict__:          # the last week survives a restart of the dashboard
            old = read_json(PERF_FILE, [])
            self.res_hist = [x for x in old if isinstance(x, dict) and isinstance(x.get("t"), (int, float)) and x["t"] > t - 7 * 86400] \
                if isinstance(old, list) else []
        hist = self.res_hist
        hist.append(sample)
        del hist[:-PERF_KEEP]               # a week, one sample a minute
        if len(hist) % 10 == 0:
            try:
                write_json(PERF_FILE, hist)
            except OSError:
                pass
        self.res = sample
        last = lambda n: hist[-n:] if len(hist) >= n else []
        warned = self.__dict__.setdefault("res_warned", {})
        def warn(key, title, msg):
            if t - warned.get(key, 0) > 6 * 3600:
                warned[key] = t
                self.notifier.add("resources", title, msg, "warning")
        low = [x for x in last(3) if x["mem_total"] and x["mem_free"] is not None
               and (x["mem_free"] < 300 or x["mem_free"] < x["mem_total"] * 0.08)]
        if last(3) and len(low) == 3:
            warn("mem", "This computer is running out of memory",
                 "Only %s MB of %s MB is free. The game server can start lagging or crash. Close programs you don't "
                 "need, use fewer or smaller mods, or lower the player limit (Config -> Max players)."
                 % (sample["mem_free"], sample["mem_total"]))
        laggy = [x for x in last(5) if x.get("players") and x.get("ping") is not None and x["ping"] >= 250]
        if last(5) and len(laggy) == 5:
            warn("ping", "Players have a lot of lag",
                 "The players' average ping has been above 250 ms for 5 minutes (now %d ms, %d players). If the "
                 "computer and upload graphs on the Health page look fine, it's their connection or the distance to "
                 "your server. If they're full, lower the player limit." % (sample["ping"], players))
        busy = [x for x in last(5) if x["cpu"] is not None and x["cpu"] >= 90]
        if last(5) and len(busy) == 5:
            warn("cpu", "This computer's processor is at its limit",
                 "The CPU has been above 90%% for 5 minutes (%d players online). Players will notice lag. Lower the "
                 "player limit, run fewer servers at once, or close other programs." % players)
        cap = float(self.settings.get("upload_mbit") or 0) * 1000
        full = [x for x in last(3) if cap and x["up_kbps"] and x["players"] and x["up_kbps"] >= cap * 0.85]
        if cap and last(3) and len(full) == 3:
            per = max(1.0, sum(x["up_kbps"] / x["players"] for x in full) / 3)
            warn("up", "Your upload speed is almost used up",
                 "The server is sending %.1f of your %.0f Mbit/s upload (%d players, about %.0f kbit/s each). Players "
                 "will lag or time out. A safe player limit for your connection is about %d."
                 % (sample["up_kbps"] / 1000, cap / 1000, players, per, max(1, int(cap * 0.8 / per))))

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
            if old_p and not relay_on() and duck_host():
                self.notifier.add("network", "Your public IP address changed",
                                  "It was %s, now it's %s. Friends using %s don't need to change anything - DuckDNS "
                                  "is updated automatically." % (old_p, pip, duck_host()), "info", send=False)
                threading.Thread(target=self.duck_tick, kwargs={"force": True}, daemon=True).start()
            elif old_p and not relay_on():
                self.notifier.add("network", "Your public IP address changed",
                                  "It was %s, now it's %s. Friends who join from outside your home need the new "
                                  "address: %s:%s. Most home internet gets a new IP now and then." %
                                  (old_p, pip, pip, (INSTANCES["main"].port() if "main" in INSTANCES else None) or 30814), "warning")
            self.state["addr_pub"], changed = pip, True
        if changed:
            self.save_state()

    def mod_update_tick(self):
        if not self.settings.get("mod_update_check"):
            return
        t = now()
        if self.settings.get("mod_auto_update") and t >= self.state.get("modauto_next", 0):
            self.state["modauto_next"] = t + 600
            self.mod_auto_update()
        if t < self.state.get("modupd_next", 0):
            return
        self.state["modupd_next"] = t + 24 * 3600
        self.run_mod_check(False)

    def mod_auto_update(self):
        """Install known mod updates on every server nobody is playing on, then restart it if it's running
        (players already on it would have the old version)."""
        with LOCK:
            insts = list(INSTANCES.values())
        for inst in insts:
            ups = (getattr(self, "mod_updates", {}) or {}).get(inst.id) or {}
            todo = [n for n, u in sorted(ups.items()) if u.get("update")]
            if not todo:
                continue
            use_server(inst.id)
            if online_names():
                continue
            try:
                done, failed = update_mods(todo, ups)
            except Exception as e:
                sys.stderr.write("mod auto update %s: %s\n" % (inst.id, short_err(e)))
                continue
            if done:
                refresh_mod_desc()
                restart = inst.server.status()["state"] == "running" and not online_names()
                if restart:
                    inst.server.action("restart")
                else:
                    self.config_changed()
                self.notifier.add("mod_update", "Mod%s updated by itself" % ("s" if len(done) > 1 else ""),
                                  "While nobody was playing on %s: %s.%s" % (inst.name, ", ".join(done[:15]),
                                                                            " The server was restarted." if restart else ""), "info")
            if failed:
                self.notifier.add("mod_update", "A mod update didn't work", "\n".join("%s: %s" % (n, e) for n, e in failed[:10]), "warning")
                for n, _ in failed:
                    ups[n]["update"] = False       # don't try again every 10 minutes; the next daily check brings it back

    def run_mod_check(self, force):
        with LOCK:
            insts = list(INSTANCES.values())
        found = {}
        for inst in insts:
            try:
                ups = mod_updates_for(inst, force)
            except Exception as e:
                sys.stderr.write("mod updates %s: %s\n" % (inst.id, short_err(e)))
                continue
            found[inst.id] = ups
            seen = self.state.setdefault("modupd_told", {})
            new = [(n, u) for n, u in ups.items() if u["update"] and seen.get("%s/%s" % (inst.id, n)) != u["latest_id"]]
            for n, u in new:
                seen["%s/%s" % (inst.id, n)] = u["latest_id"]
            if new:
                use_server(inst.id)
                self.notifier.add("mod_update", "Mod update%s available" % ("s" if len(new) > 1 else ""),
                                  "\n".join("%s: %s -> %s" % (u["title"] or n, u["have"] or "?", u["latest"] or "new version")
                                            for n, u in new[:15]) + "\nUpdate them on the Mods page with one click.", "info")
        self.mod_updates = found
        self.state["modupd_t"] = now()
        self.save_state()
        return found

    def bridge_out(self, chat):
        """Chat bridge, game -> Discord: one webhook message per batch, never pinging anyone."""
        lines = ["**%s**: %s" % (discord_escape(n), discord_escape(m)) for n, m in chat if m]
        try:
            while lines:
                part = []
                while lines and len("\n".join(part + [lines[0]])) < 1900:
                    part.append(lines.pop(0))
                if not part:
                    part = [lines.pop(0)[:1900]]
                webhook_call("POST", body={"username": "Game chat", "content": "\n".join(part),
                                           "allowed_mentions": {"parse": []}})
        except Exception as e:
            sys.stderr.write("chat bridge: %s\n" % short_err(e))

    def health_tick(self):
        """Every 30 minutes: run the health checks. When something newly fails, save a diagnostic report
        and say so (once per problem, not every half hour)."""
        t = now()
        if t < getattr(self, "health_next", t + 600) or self.sleeping:
            if not hasattr(self, "health_next"):
                self.health_next = t + 600      # first run 10 minutes after the dashboard starts
            return
        self.health_next = t + 1800
        with LOCK:
            insts = list(INSTANCES.values())
        for inst in insts:
            use_server(inst.id)
            if inst.server.status()["state"] not in ("running", "failed"):
                continue                       # a stopped server isn't a problem
            h = health_report()
            bad = sorted(x["id"] for x in h["checks"] if x["state"] == "fail")
            key = "health_fail_" + inst.id
            if bad and bad != self.state.get(key):
                name = save_diagnostic_report(inst.id, diagnostic_report())
                titles = [x["title"] for x in h["checks"] if x["state"] == "fail"]
                self.notifier.add("crash", "Health check failed: " + ", ".join(titles),
                                  "; ".join("%s - %s" % (x["title"], x["detail"]) for x in h["checks"] if x["state"] == "fail")[:900] +
                                  " A diagnostic report was saved (Overview → Health → Reports): " + name, "warning")
            self.state[key] = bad
        use_server("main")
        self.save_state()

    # ---------- sleep / wake up
    def sleep_blockers(self):
        """Why the computer must stay awake right now ("" = it may sleep)."""
        t = now()
        with LOCK:
            insts = list(INSTANCES.values())
        players = 0
        for inst in insts:
            use_server(inst.id)
            if inst.server.status()["state"] == "running":
                players += len(online_names())
            if isinstance(inst.meta.get("event_active"), dict):
                use_server("main")
                return "an event is running"
            for e in events_cfg(inst):
                st = event_next_start(e, t) if e.get("on", True) else None
                if st and st - t < 30 * 60:
                    use_server("main")
                    return "an event starts soon"
        use_server("main")
        if players:
            return "%d player%s online" % (players, "" if players == 1 else "s")
        if t - self.last_use < 10 * 60:
            return "the dashboard is being used"
        if self.bot.busy:
            return "a server is being started from Discord"
        return ""

    def sleep_tick(self):
        s, t = self.settings, now()
        why = self.sleep_blockers() if s.get("sleep_on") else "auto-sleep is off"
        self.sleep_busy_why = why
        if why or self.sleeping:
            if why:
                self.idle_since = t
            return
        if t - self.idle_since < max(5, int(s.get("sleep_idle") or 30)) * 60:
            return
        if not in_time_window(s.get("sleep_from"), s.get("sleep_to"), t):
            return
        if not power_status().get("can_sleep"):
            return
        self.go_sleep("Nobody played for %d minutes." % int(s.get("sleep_idle") or 30))

    def go_sleep(self, why, delay=6):
        """Send the computer to sleep (in the background, after `delay` seconds)."""
        if self.sleeping:
            return {"ok": False, "msg": "already going to sleep"}
        self.sleeping = True
        self.idle_since = now()
        at = next_wake_at()
        err = set_wake_timer(at) if at else ""
        mac = wol_target()[0]
        how = []
        if at and not err:
            how.append("it wakes up by itself %s" % time.strftime("%a %H:%M", time.localtime(at)))
        if mac:
            how.append("wake it from your router, the phone app or the wake helper (MAC %s)" % mac)
        self.state.update({"slept_at": now(), "slept_why": why, "wake_at": at if not err else 0})
        self.save_state()
        self.notifier.add("sleep", "Server computer went to sleep", "%s %s" % (why, ("Next: " + "; ".join(how) + ".") if how else
                          "Press its power button to wake it up."), "info")
        try:
            self.status_msg_asleep(at if not err else 0)
        except Exception as e:
            sys.stderr.write("discord status: %s\n" % short_err(e))

        def later():
            time.sleep(delay)
            try:
                if IS_WIN:
                    win_sleep()
                    r = {"ok": True}
                else:
                    r = control("sleep", timeout=30)
                if not r.get("ok"):
                    self.sleeping = False
                    self.notifier.add("sleep", "Couldn't go to sleep", r.get("msg") or "unknown error", "warning", send=False)
            except Exception as e:
                self.sleeping = False
                self.notifier.add("sleep", "Couldn't go to sleep", short_err(e), "warning", send=False)
            # if the computer never really slept (or woke up quickly), carry on normally
            threading.Timer(300, lambda: setattr(self, "sleeping", False)).start()
        threading.Thread(target=later, daemon=True).start()
        return {"ok": True, "wake_at": at if not err else 0, "timer_error": err}

    def on_resume(self, gap):
        self.sleeping = False
        self.idle_since = now()                 # give people time to join before sleeping again
        self.status_next = 0
        self.state["duck_next"] = 0
        _PUBLIC_IP["t"] = 0
        with LOCK:
            _POWER["t"] = 0
        self.state["woke_at"] = now()
        self.save_state()
        threading.Thread(target=set_wake_timer, args=(0,), daemon=True).start()
        self.bot.reconnect()                     # the old Discord connection died while sleeping
        h, m = int(gap // 3600), int(gap % 3600 // 60)
        self.notifier.add("sleep", "Server computer woke up", "It was asleep for %s." % (
            ("%dh %dmin" % (h, m)) if h else "%d minutes" % max(1, m)), "success")

    def status_msg_asleep(self, wake_at):
        """Show "asleep" in the live Discord status message before the computer goes to sleep."""
        mid = self.state.get("status_msg")
        if not (self.settings.get("discord_status_msg") and mid and webhook_parts()[0]):
            return
        txt = "The server computer is asleep to save power."
        if wake_at:
            txt += " It wakes up by itself <t:%d:R>." % wake_at
        if self.secrets.has("WAKE_TOPIC") and self.settings.get("discord_bot"):
            txt += " Use **/start** to wake it up now."
        webhook_call("PATCH", "/messages/%s" % mid, {"embeds": [{"title": "💤 BeamMP servers - asleep", "color": 0x64748B,
                                                                  "description": txt}]})

    def community_tick(self):
        """Once a minute: uptime for the status page, timed announcements, event advertising."""
        t = now()
        if t < getattr(self, "community_next", 0):
            return
        self.community_next = t + 60 - t % 60 + 2
        with LOCK:
            insts = list(INSTANCES.values())
        states = {}
        for inst in insts:
            use_server(inst.id)
            states[inst.id] = inst.server.status()["state"] == "running"
        if not self.sleeping:
            uptime_record(states)
        lt = time.localtime(t)
        hm, wd, day = "%02d:%02d" % (lt.tm_hour, lt.tm_min), lt.tm_wday, time.strftime("%Y-%m-%d", lt)
        sent = self.state.setdefault("timed_sent", {})
        adv = self.state.setdefault("ev_ads", {})
        changed = False
        for inst in insts:
            use_server(inst.id)
            # timed announcements: "at 20:00 on Fri + Sat say ..."
            for i, m in enumerate(timed_msgs(inst)):
                if not m.get("on", True) or m.get("at") != hm or wd not in (m.get("days") or []):
                    continue
                k = "%s:%d:%s" % (inst.id, i, day)
                if k in sent:
                    continue
                sent[k] = t
                changed = True
                if states.get(inst.id) and online_names():
                    for line in str(m.get("text") or "").split("\n")[:3]:
                        if line.strip():
                            chat_say(line.strip())
                if m.get("discord"):
                    broadcast(inst.name, m.get("text", ""))
            # event advertising
            if not self.settings.get("event_ads"):
                continue
            for e in events_cfg(inst):
                if not e.get("on", True):
                    continue
                st = event_next_start(e, t)
                if not st:
                    continue
                left = st - t
                k = "%s:%s:%d" % (inst.id, e.get("id"), st)
                if 23 * 3600 < left <= 24 * 3600 and k + ":day" not in adv and int(e.get("announce") or 0) != 1440:
                    adv[k + ":day"] = t
                    changed = True
                    broadcast("📅 Tomorrow: %s" % e["name"], "%s starts <t:%d:F> (<t:%d:R>) on %s%s.%s" % (
                        e["name"], st, st, inst.name, (" - map " + e["map"]) if e.get("map") else "",
                        (" " + e["text"]) if e.get("text") else ""))
                # in-game reminder every 30 minutes during the last 3 hours
                if 0 < left <= 3 * 3600 and lt.tm_min % 30 == 0 and states.get(inst.id) and online_names() \
                        and left > int(e.get("announce") or 0) * 60:
                    chat_say("Coming up: %s in %s%s. Don't miss it!" % (e["name"], fmt_secs(left), (" on " + e["map"]) if e.get("map") else ""))
        for d in (sent, adv):
            for k in [k for k, v in d.items() if v < t - 8 * 86400]:
                del d[k]
                changed = True
        if changed:
            self.save_state()

    def status_msg_tick(self):
        """A message in the webhook's Discord channel that shows the servers and updates itself every minute."""
        if not self.settings.get("discord_status_msg") or not webhook_parts()[0]:
            return
        t = now()
        if t < getattr(self, "status_next", 0):
            return
        self.status_next = t + 60
        body = {"username": "BeamMP servers", "allowed_mentions": {"parse": []},
                "embeds": [{"title": "BeamMP servers", "color": 0x3B82F6, "fields": discord_server_status(),
                            "footer": {"text": "Updates every minute · last update"},
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))}]}
        up = upcoming_events_text()
        if up != "No events planned.":
            body["embeds"].append({"title": "Upcoming events", "color": 0x8B5CF6, "description": up})
        use_server("main")
        mid = self.state.get("status_msg")
        key = APP.secrets.get("DISCORD_WEBHOOK")[-12:]
        if mid and self.state.get("status_key") == key:
            try:
                webhook_call("PATCH", "/messages/%s" % mid, body)
                return
            except urllib.error.HTTPError as e:
                if e.code not in (404, 403):
                    raise                         # Discord hiccup - try again next minute
        r = webhook_call("POST", body=body, query="?wait=true")
        self.state.update({"status_msg": str((r or {}).get("id") or ""), "status_key": key})
        self.save_state()

    def _event_tick(self, inst, S):
        """Weekly events (Config -> Events): announce, switch map and mods, switch back."""
        evs = [e for e in events_cfg(inst) if e.get("on", True)]
        act = inst.meta.get("event_active")
        t = now()
        if isinstance(act, dict):
            if t < act.get("end", 0):
                return
            # the event is over: put the map, mods and games back, post the results
            for m in act.get("mods") or []:
                set_mod_enabled(m, False)
            if act.get("game") and act.get("game_prev") is False:
                cfg = read_games_cfg()
                cfg[act["game"]] = False
                write_games_cfg(cfg)
            try:
                res = event_results(act, min(t, act.get("end") or t))
            except Exception as ex:
                sys.stderr.write("event results: %s\n" % short_err(ex))
                res = None
            if res is not None:
                set_server_meta(inst.id, event_last={"name": act.get("name"), "end": t, "results": res})
                if act.get("results") and webhook_parts()[0]:
                    try:
                        webhook_call("POST", body={"username": "BeamMP events", "content": event_results_text(act.get("name", "The event"), res)[:1900],
                                                   "allowed_mentions": {"parse": []}})
                    except Exception as ex:
                        sys.stderr.write("event results: %s\n" % short_err(ex))
            if act.get("once"):
                set_server_meta(inst.id, events=[dict(e, on=False) if e.get("id") == act.get("id") else e for e in events_cfg(inst)])
            if online_names():
                chat_say("%s is over - thanks for joining! Switching back to %s." % (act.get("name", "The event"), act.get("prev_map")))
                time.sleep(2)
            set_server_meta(inst.id, event_active=None)
            ok, note = self.switch_map(act.get("prev_map")) if act.get("prev_map") else (True, "")
            if act.get("mods") and not act.get("prev_map"):
                self.config_changed()
            self.notifier.add("rotation", "Event ended: %s" % act.get("name"), note or "Back to normal.", "info")
            return
        warned = S.setdefault("ev_warned", {})
        for e in evs:
            st = event_next_start(e, t)
            if not st:
                continue
            left = st - t
            ann = int(e.get("announce", 30)) * 60
            k = "%s@%d" % (e.get("id"), st)
            if 0 < left <= ann and k not in warned:
                warned[k] = True
                txt = "📅 **%s** starts <t:%d:R> on %s - map %s.%s" % (
                    discord_escape(e["name"]), st, discord_escape(inst.name), discord_escape(e["map"]),
                    (" " + discord_escape(e.get("text"))) if e.get("text") else "")
                if webhook_parts()[0]:
                    try:
                        webhook_call("POST", body={"username": "BeamMP events",
                                                   "content": ("@everyone " if e.get("ping") else "") + txt,
                                                   "allowed_mentions": {"parse": ["everyone"] if e.get("ping") else []}})
                    except Exception as ex:
                        sys.stderr.write("event announce: %s\n" % short_err(ex))
                if online_names():
                    chat_say("Event: %s starts in %s on map %s!" % (e["name"], fmt_secs(left), e["map"]))
            if left <= 0:
                prev = current_map()
                moved = [m for m in e.get("mods") or [] if set_mod_enabled(m, True)]
                game, game_prev = e.get("game") or "", None
                if game in EVENT_GAMES:
                    cfg = read_games_cfg()
                    game_prev = bool(cfg.get(game))
                    if not game_prev:
                        cfg[game] = True
                        write_games_cfg(cfg)
                set_server_meta(inst.id, event_active={"id": e.get("id"), "name": e["name"], "end": st + int(e["minutes"]) * 60,
                                                        "prev_map": prev if prev != e["map"] else None, "mods": moved,
                                                        "start": t, "game": game, "game_prev": game_prev,
                                                        "results": bool(e.get("results")), "once": bool(e.get("date")),
                                                        "online": [str(n)[:64] for n in online_names()][:50]})
                if online_names():
                    hint = {"race": " Type /race to start a race." if any(tr["map"] == e["map"] for tr in read_tracks())
                            else " Races are on, but this map has no race track yet.",
                            "drift": " Slide for drift points - /drift shows the best.",
                            "cnr": " Type /cnr to start cops and robbers."}.get(game, "")
                    chat_say("%s starts now!%s%s" % (
                        e["name"], (" Switching to %s - rejoin in a moment." % e["map"]) if e["map"] != prev else "", hint))
                    time.sleep(2)
                if e["map"] != prev:
                    ok, note = self.switch_map(e["map"])
                else:
                    ok, note = True, ""
                    if moved:
                        self.config_changed()
                self.notifier.add("rotation", "Event started: %s" % e["name"], note or "Map %s." % e["map"], "info")
                return
        for k in [k for k in warned if int(k.rsplit("@", 1)[1]) < t - 3600]:
            warned.pop(k, None)

    def _recap_tick(self, inst):
        """The weekly recap (Games page), once a week at the hour the owner picked."""
        cfg = recap_cfg(inst)
        if not cfg["on"]:
            return
        lt = time.localtime()
        week = time.strftime("%G-W%V", lt)
        if lt.tm_wday != cfg["day"] or lt.tm_hour < cfg["hour"] or inst.meta.get("recap_week") == week:
            return
        set_server_meta(inst.id, recap_week=week)        # once a week, even if posting fails
        r = weekly_recap()
        if r and broadcast(r[0], r[1]):
            set_server_meta(inst.id, recap_last=now())

    def _bridge_flag(self, inst, S):
        want = "on" if (self.settings.get("discord_bridge") and
                        (self.settings.get("discord_bridge_server") or "main") == inst.id and webhook_parts()[0]) else "off"
        if S.get("bridge_flag") != want and os.path.isdir(inst.STATS_DIR):
            shared_write(inst.BRIDGE_FILE, "# Managed by the dashboard (Settings -> Discord bot -> chat bridge)\nbridge=%s\n" % want)
            S["bridge_flag"] = want

    def _monitor_one(self, inst, S):
        self._check_tampering(inst, S)
        if moved_note(inst) and inst.server.status()["state"] == "running":
            inst.server.action("stop")
            self.notifier.add("stopped", "Server kept off", moved_note(inst) + ", so it was stopped here again. To run it on "
                              "this computer, press Start in the dashboard.", "info")
        if now() >= S.get("maint_next", 0):
            S["maint_next"] = now() + 300
            try:
                if not map_timeline(inst):
                    record_map(inst, current_map())
                ensure_chat_lang(inst)           # picks up translations that came with a dashboard update
                if not online_names():           # never pull mods away under players' feet
                    moved = light_sync(inst)
                    how = ensure_tools_mod(inst)
                    if moved or how:
                        self.config_changed()
            except Exception as e:
                sys.stderr.write("map/tools upkeep %s: %s\n" % (inst.id, short_err(e)))
        try:
            self._bridge_flag(inst, S)
        except OSError:
            pass
        try:
            self._event_tick(inst, S)
        except Exception as e:
            sys.stderr.write("events %s: %s\n" % (inst.id, short_err(e)))
        try:
            self._recap_tick(inst)
        except Exception as e:
            sys.stderr.write("weekly recap %s: %s\n" % (inst.id, short_err(e)))
        try:
            self._rotation_tick(inst, S)
        except Exception as e:
            sys.stderr.write("map rotation %s: %s\n" % (inst.id, short_err(e)))
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
                joined, denied, modmsgs, bots, refused, chat, reports = [], [], [], 0, [], [], []
                for line in chunk.splitlines():
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(e, dict) or not isinstance(e.get("t"), int) or e["t"] < S["last_t"]:
                        continue
                    if e.get("ev") == "join":
                        joined.append(clean_player_name(e.get("name")))
                    elif e.get("ev") == "report" and len(reports) < 10:
                        reports.append(e)
                    elif e.get("ev") == "votekick":
                        activity(clean_player_name(e.get("by")), "/votekick %s (%s)" % (clean_player_name(e.get("name")), chat_text(e.get("reason"))[:80]),
                                 "game", server=inst.id)
                    elif e.get("ev") == "chat" and len(chat) < 40:
                        chat.append((clean_player_name(e.get("name")), clean_msg(e.get("msg"))[:300]))
                    elif e.get("ev") == "mapvote" and isinstance(e.get("map"), str):
                        S["pending_map"] = (now() + 30, e["map"][:80], clean_player_name(e.get("by")))
                    elif e.get("ev") == "denied":
                        n = clean_player_name(e.get("name"))
                        if not any(d[0] == n for d in denied):
                            denied.append((n, bool(e.get("guest"))))
                    elif e.get("ev") in ("ban", "unban", "kick", "mute"):
                        n, by = clean_player_name(e.get("name")), clean_player_name(e.get("by") or "?")
                        activity(by, "/%s %s%s" % (e["ev"], n, (" (%s)" % str(e.get("reason"))[:80]) if e.get("reason") else ""), "game", server=inst.id)
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
                for e in reports:
                    r = add_report(inst, e)
                    lines = "\n".join("%s %s: %s" % (time.strftime("%H:%M", time.localtime(c["t"])), c["name"], chat_text(c["msg"]))
                                      for c in r["chat"][-8:])
                    self.notifier.add("report", "%s reported %s" % (r["by"], r["target"]),
                                      "Reason: %s%s\nSee Players -> Reports in the dashboard." % (r["reason"], ("\n\nChat before the report:\n" + lines) if lines else ""),
                                      "warning")
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
                if chat and self.settings.get("discord_bridge") and \
                        (self.settings.get("discord_bridge_server") or "main") == inst.id:
                    self.bridge_out(chat)
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
        res["channel"] = update_channel()
        if res["channel"] == "experimental":
            try:
                pre = github_prerelease(REPO)
                if pre and newer(pre[0], max(res.get("easy_latest") or "0.0.0", EASY_VERSION, key=lambda v: tuple(map(int, v.split("."))))):
                    res["easy_early"], res["easy_early_url"] = pre
            except Exception:
                pass
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
            if res.get("easy_early") and prev.get("notified_early") != res["easy_early"]:
                if res["channel"] == "experimental" and not PAID_FEATURES:
                    self.notifier.add("update", "Rolling release: EasyServer %s is out" % res["easy_early"],
                                      "The newest features, may have bugs. Download: %s" % res.get("easy_early_url"), "info")
                elif res["channel"] == "experimental":
                    self.notifier.add("update", "Experimental: EasyServer %s is out" % res["easy_early"],
                                      "The newest features, not fully tested yet. Download it from your supporter order: %s" % res.get("easy_early_url"), "info")
                else:
                    self.notifier.add("update", "Early access: EasyServer %s is ready to try" % res["easy_early"],
                                      "Thanks for supporting EasyServer! Download it from your supporter order: %s" % res.get("easy_early_url"), "info")
            res["notified_early"] = res.get("easy_early") or prev.get("notified_early")
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
            if at_server(ip):
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
            elif not at_server(ip):
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

    def new_session(self, ip, user="owner", role="owner"):
        tok = secrets.token_urlsafe(32)
        with LOCK:
            t = now()
            self.sessions = {k: v for k, v in self.sessions.items() if v["last"] > t - 7200 and v["created"] > t - 43200}
            self.sessions[tok] = {"created": t, "last": t, "ip": ip, "csrf": secrets.token_urlsafe(24), "user": user, "role": role}
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
        if s.get("user", "owner") != "owner":   # an extra account: still there? role changed? still allowed from outside?
            u = find_user(s["user"])
            if not u or u.get("disabled") or (ip_is_remote(s.get("ip", "")) and not (u.get("remote") and u.get("totp"))):
                with LOCK:
                    self.sessions.pop(tok, None)
                return None
            s["role"] = u["role"]
            s["_u"] = u
        with LOCK:
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
            for one in (v if isinstance(v, (list, tuple)) else [v]):
                self.send_header(k, one)
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
        self._code = code
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
        if getattr(self, "_json", None) is not None:
            return self._json                   # already read - the body can only be read once
        n = self.content_length()
        if n > limit:
            raise ValueError("request too large")
        raw = self.rfile.read(n) if n else b"{}"
        self._body_done = True
        try:
            v = json.loads(raw or b"{}")
        except ValueError:
            raise ValueError("bad JSON")
        self._json = v if isinstance(v, dict) else {}
        return self._json

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
        if not app.secrets.has("MODS_PASSWORD") and not at_server(self.ip):
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
        self._json = None
        self._code = 200
        self._restore_undo = None
        try:
            if not self.gate():
                return
            path, q = self.route()
            if method == "GET" and path == "/":
                APP.last_use = now()
                return self.page()
            if method == "GET" and path in APP_FILES:
                return self.app_file(path)
            if method == "GET" and path == "/lang/index.json":
                return self.send(200, {"languages": lang_index()}, extra={"Cache-Control": "no-cache"})
            if method == "GET" and LANG_PATH_RE.fullmatch(path):
                return self.lang_file(path)
            if method == "GET" and path == "/whatsnew.json":
                return self.whatsnew_file()
            public = {("GET", "/api/session"), ("POST", "/api/login"), ("POST", "/api/setup"),
                      ("GET", "/api/teaminvite/info"), ("POST", "/api/teaminvite/accept"),
                      ("POST", "/api/discord/start"), ("POST", "/api/discord/finish")}
            if (method, path) in public:
                return getattr(self, "api_" + path[5:].replace("/", "_"))(q)
            if method in ("GET", "HEAD") and path in ("/status", "/status.json"):
                return self.status_page(path)
            if not path.startswith("/api/"):
                return self.fail(404, "not found")
            sess = self.authed(method != "GET")
            if not sess:
                return
            fn = getattr(self, "%s_%s" % (method.lower(), path[5:].replace("/", "_").replace("-", "_")), None)
            if not fn:
                return self.fail(404, "not found")
            _TL.user = sess.get("user", "owner")
            want = self.headers.get("X-ES-Server") or q.get("srv") or "main"
            with LOCK:
                known = want in INSTANCES
            if sess.get("role", "owner") == "owner" or sess.get("user", "owner") == "owner":
                need = required_role(method, path)
                if ROLES.get(sess.get("role", "owner"), 0) < ROLES[need]:
                    return self.fail(403, "Only the owner can do that.")
                self.sess = sess
            else:
                u = sess.get("_u") or find_user(sess["user"])
                if not u:
                    return self.fail(401, "Please log in")
                if path in TEAM_ANY_SERVER and known and not user_role_for(u, want):
                    with LOCK:                   # pages about the account, not a server: use one it may see
                        want = next((i for i in INSTANCES if user_role_for(u, i)), want)
                ok, msg = team_allows(u, want if known else "main", method, path)
                if not ok:
                    return self.fail(403, msg)
                # handlers see the role this account has on the server it is working on
                self.sess = dict(sess, role=user_role_for(u, want if known else "main") or "viewer")
                self.sess_real = sess
            if method != "GET":
                APP.last_use = now()
            if not known:
                return self.fail(404, "That server doesn't exist (any more)")
            use_server(want)
            fn(q)
            if method in ("POST", "PUT") and path not in ("/api/notifications/read", "/api/security/ack", "/api/logout") \
                    and not path.startswith("/api/2fa/begin") and not (path == "/api/power/helper" and (self._json or {}).get("action") == "test"):
                body = self._json or {}
                if path == "/api/mods/upload":
                    body = {"name": q.get("name", "")}
                code = getattr(self, "_code", 200)
                if code != 409:                  # 409 = "are you sure?" question, nothing happened
                    activity(sess.get("user", "owner"), describe_action(path, body), "dashboard", self.ip, want, ok=code < 400)
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

    def app_file(self, path):
        """Files that make the dashboard installable as a phone app (no login needed, nothing private)."""
        if path == "/manifest.webmanifest":
            body = json.dumps({
                "name": "BeamMP Dashboard", "short_name": "BeamMP", "id": "/", "start_url": "/", "scope": "/",
                "display": "standalone", "background_color": "#151514", "theme_color": "#1f5fd6",
                "description": "Manage your BeamMP servers", "orientation": "any",
                "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
                          {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}).encode()
            return self.send(200, body, "application/manifest+json", {"Cache-Control": "max-age=3600"})
        if path == "/sw.js":
            return self.send(200, SW_JS.encode(), "text/javascript", {"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})
        size = {"/icon-192.png": 192, "/icon-512.png": 512, "/apple-touch-icon.png": 180}[path]
        return self.send(200, app_icon_png(size), "image/png", {"Cache-Control": "max-age=86400"})

    def lang_file(self, path):
        """A translation of the dashboard (dashboard/lang/xx.json). Public: the login page is translated too."""
        code = LANG_PATH_RE.fullmatch(path).group(1)
        try:
            with open(os.path.join(LANG_DIR, code + ".json"), "rb") as f:
                body = f.read(2 * 1024 * 1024)
        except OSError:
            return self.fail(404, "not found")
        return self.send(200, body, "application/json", {"Cache-Control": "no-cache"})

    def whatsnew_file(self):
        """The "New in" cards shown on the Overview after an update (dashboard/whatsnew.json, made from
        CHANGELOG.md when the website is built). Public like the language files: nothing private in it."""
        try:
            with open(os.path.join(HERE, "whatsnew.json"), "rb") as f:
                body = f.read(256 * 1024)
        except OSError:
            return self.send(200, {"version": "", "languages": {}}, extra={"Cache-Control": "no-cache"})
        return self.send(200, body, "application/json", {"Cache-Control": "no-cache"})

    def page(self):
        nonce = secrets.token_urlsafe(16)
        html_ = APP.page.replace("__NONCE__", nonce).replace("__VERSION__", EASY_VERSION)
        csp = ("default-src 'none'; script-src 'nonce-%s'; style-src 'unsafe-inline'; img-src 'self' data:; "
               "connect-src 'self'; manifest-src 'self'; worker-src 'self'; form-action 'none'; "
               "frame-ancestors 'none'; base-uri 'none'") % nonce
        self.send(200, html_.encode(), "text/html", {"Content-Security-Policy": csp})

    def status_page(self, path):
        if not APP.settings.get("statuspage_on"):
            return self.send(404, "There is no public status page here.", "text/plain")
        d = public_status()
        if path.endswith(".json"):
            return self.send(200, d, extra={"Access-Control-Allow-Origin": "*", "Cache-Control": "max-age=20"})
        self.send(200, render_status_page(d).encode(), "text/html",
                  {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
                   "Cache-Control": "max-age=20"})

    # ---------- public endpoints
    def session_server_roles(self, sess):
        """{server id: role} for an extra account (custom roles as their name), so the page shows the right tabs."""
        if not sess or sess.get("user", "owner") == "owner":
            return None
        u = find_user(sess["user"])
        if not u:
            return {}
        names = {r["id"]: r for r in load_roles()}
        with LOCK:
            ids = list(INSTANCES)
        out = {}
        for sid in ids:
            r = user_role_for(u, sid)
            if r:
                out[sid] = {"role": r, "name": names[r]["name"] if r in names else r,
                            "perms": names[r]["perms"] if r in names else None}
        return out

    def api_session(self, q):
        app = APP
        sess = app.session(self.cookie("es_session"))
        extra = None
        if not sess and self.cookie(DEVICE_COOKIE) and app.secrets.has("MODS_PASSWORD"):
            who = None if app.is_locked(self.ip) else device_login(self.cookie(DEVICE_COOKIE), self.ip)
            if who:
                tok = app.new_session(self.ip, who["user"], who["role"])
                sess = app.session(tok)
                sess["device"] = who["device"]
                extra = {"Set-Cookie": [self.cookie_header(tok),
                                        self.cookie_header(self.cookie(DEVICE_COOKIE), name=DEVICE_COOKIE, max_age=DEVICE_DAYS * 86400)]}
                activity(who["user"], "Logged in (remembered device)", "dashboard", self.ip, "main")
            else:                       # forgotten or expired: drop the cookie
                extra = {"Set-Cookie": self.cookie_header("", clear=True, name=DEVICE_COOKIE)}
        self.send(200, {
            "logged_in": bool(sess), "csrf": sess["csrf"] if sess else None,
            "user": sess.get("user", "owner") if sess else None, "role": sess.get("role", "owner") if sess else None,
            "server_roles": self.session_server_roles(sess),
            "supporter": bool(sess) and supporter_active(),
            "needs_setup": not app.secrets.has("MODS_PASSWORD"),
            "setup_allowed": at_server(self.ip) and host_name(self.headers.get("Host")) in ("localhost", "127.0.0.1", "::1"),
            "totp": app.secrets.has("TOTP_SECRET"),
            "discord_login": dlogin_available() and dlogin_conf() is not None,
            "version": EASY_VERSION, "platform": "windows" if IS_WIN else "linux",
            "https": self.https,
        }, extra=extra)

    def api_setup(self, q):
        app = APP
        if app.secrets.has("MODS_PASSWORD") or not at_server(self.ip):
            return self.fail(403, "Setup is only possible once, on the server computer itself"
                             + (" (on a Mac: run the installer again, it sets the password)" if on_mac() else ""))
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

    def cookie_header(self, tok, clear=False, name="es_session", max_age=None):
        c = "%s=%s; Path=/; HttpOnly; SameSite=Strict" % (name, "" if clear else tok)
        if self.https:
            c += "; Secure"
        if clear:
            c += "; Max-Age=0"
        elif max_age:
            c += "; Max-Age=%d" % max_age
        return c

    def login_cookies(self, tok, user, remember):
        """Set-Cookie for a fresh login: the session, plus a remembered-device cookie when asked for."""
        if not remember:
            return [self.cookie_header(tok)]
        dev = remember_device(user, self.ip, self.headers.get("User-Agent"))
        return [self.cookie_header(tok), self.cookie_header(dev, name=DEVICE_COOKIE, max_age=DEVICE_DAYS * 86400)]

    def api_login(self, q):
        app = APP
        if app.is_locked(self.ip):
            return self.fail(429, "Too many wrong attempts. Try again in 15 minutes.")
        b = self.body_json(4096)
        pw = str(b.get("password", ""))
        uname = str(b.get("user") or "").strip()
        if uname and uname.lower() != "owner":
            return self.login_user(uname, pw)
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
            activity("owner", "Failed login", "dashboard", self.ip, "main", ok=False)
            return self.fail(401, "Wrong password or two-step code" if has_totp else "Wrong password",
                             need_code=has_totp)
        tok = app.new_session(self.ip)
        activity("owner", "Logged in", "dashboard", self.ip, "main")
        self.send(200, {"ok": True}, extra={"Set-Cookie": self.login_cookies(tok, "owner", b.get("remember") is True)})

    def login_user(self, uname, pw):
        """Extra accounts. From the home network with their password (and their two-step code if they set
        one up). From the internet only when the owner allowed it for this account AND it has two-step login."""
        app = APP
        local = not ip_is_remote(self.ip)
        u = find_user(uname)
        ok_pw = bool(u) and not u.get("disabled") and check_password(pw, u.get("pw", ""))
        # the code is only checked when the password is right; the answer is the same either way
        ok = ok_pw and (not u.get("totp") or user_totp_ok(u, (self._json or {}).get("code")))
        if not ok:
            time.sleep(0.7)
            app.login_failed(self.ip)
            activity(uname[:24], "Failed login", "dashboard", self.ip, "main", ok=False)
            return self.fail(401, "Wrong name, password or two-step code", need_code=True)
        if not local and not (u.get("remote") and u.get("totp")):
            activity(u["name"], "Login refused (from the internet)", "dashboard", self.ip, "main", ok=False)
            return self.fail(403, "This account can only log in from the home network. The owner can allow internet "
                                  "access for it (Settings → Users), and it needs two-step login.")
        users = load_users()
        for x in users:
            if x["name"].lower() == u["name"].lower():
                x["last_login"] = now()
        save_users(users)
        tok = app.new_session(self.ip, u["name"], u["role"])
        activity(u["name"], "Logged in" + ("" if local else " (from the internet)"), "dashboard", self.ip, "main")
        b = self._json or {}
        self.send(200, {"ok": True}, extra={"Set-Cookie": self.login_cookies(tok, u["name"], b.get("remember") is True)})

    def post_logout(self, q):
        with LOCK:
            APP.sessions.pop(self.cookie("es_session"), None)
        dev = self.cookie(DEVICE_COOKIE)
        if dev:                         # logging out also forgets this device
            with _DEV_LOCK:
                devs = load_devices()
                keep = [d for d in devs if not hmac.compare_digest(d["hash"], _dev_hash(dev))]
                if len(keep) != len(devs):
                    save_devices(keep)
        self.send(200, {"ok": True}, extra={"Set-Cookie": [self.cookie_header("", clear=True),
                                                           self.cookie_header("", clear=True, name=DEVICE_COOKIE)]})

    # ---------- remembered devices
    def get_devices(self, q):
        me = self.sess.get("user", "owner")
        owner = self.sess.get("role") == "owner"
        cur = self.cookie(DEVICE_COOKIE)
        h = _dev_hash(cur) if cur else ""
        out = [{"id": d["id"], "user": d.get("user", "owner"), "name": d.get("name", ""), "created": d["created"],
                "last": d["last"], "ip": d.get("ip", ""), "this": bool(h) and hmac.compare_digest(d["hash"], h)}
               for d in load_devices() if owner or d.get("user", "owner").lower() == me.lower()]
        self.send(200, {"devices": sorted(out, key=lambda d: -d["last"]), "days": DEVICE_DAYS})

    def post_devices(self, q):
        b = self.body_json()
        me = self.sess.get("user", "owner")
        owner = self.sess.get("role") == "owner"
        if b.get("action") == "forget":
            n = forget_devices(None if owner else me, str(b.get("id") or "")[:20])
        elif b.get("action") == "forget_all":
            n = forget_devices(None if owner else me)
        else:
            raise ValueError("unknown action")
        self.send(200, {"ok": True, "forgotten": n})

    # ---------- overview
    # ---------- several servers
    def get_servers(self, q):
        with LOCK:
            insts = list(INSTANCES.values())
        if self.sess.get("user", "owner") != "owner":
            u = find_user(self.sess["user"]) or {}
            insts = [i for i in insts if user_role_for(u, i.id)]
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
        src = str(b.get("clone_from") or "")
        with LOCK:
            src_inst = INSTANCES.get(src) if src else None
        if src and not src_inst:
            return self.fail(400, "The server to copy doesn't exist any more")
        use_server(src_inst.id if src_inst else "main")
        text = APP.read_config_text()
        sets = [("Name", name), ("Port", port), ("AuthKey", "")]
        if not src_inst:
            sets += [("MaxPlayers", maxp), ("Map", "/levels/%s/info.json" % mp),
                     ("Description", str(b.get("description") or "")[:300]), ("Private", bool(b.get("private", False)))]
        for k, v in sets:
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
        meta = {"name": name, "autostart": True}
        if src_inst:
            for k in ("events", "restart", "rotation", "limits"):
                if k in src_inst.meta:
                    meta[k] = json.loads(json.dumps(src_inst.meta[k]))
        with LOCK:
            INSTANCES[iid] = Instance(iid, meta)
        save_servers()
        if src_inst:
            copied = clone_server_files(src_inst, INSTANCES[iid])
            note = note.rstrip(" .") + ". Copied the settings, moderation, bans and messages from %s (%d files)." % (src_inst.name, copied)
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
        for k in ("filter", "spam", "antibot", "verify", "guests", "report", "votekick", "chatlog"):
            if k in b:
                d[k] = bool(b[k])
        if "kickwords_action" in b:
            if b["kickwords_action"] not in KICKWORD_ACTIONS:
                return self.fail(400, "bad kick word action")
            d["kickwords_action"] = b["kickwords_action"]
        for k in ("admins", "words", "kickwords"):
            if k in b:
                if not isinstance(b[k], list):
                    return self.fail(400, "bad list")
                items = []
                for x in b[k][:500]:
                    x = re.sub(r"[\t\r\n,]", "", str(x)).strip()[:64]
                    if k in ("words", "kickwords"):
                        x = x.lower()
                    if x and x not in items:
                        items.append(x)
                d[k] = items
        for k, lo, hi in (("spam_limit", 2, 30), ("per_ip", 0, 20), ("join_flood", 0, 100), ("votekick_min", 3, 20)):
            if k in b:
                v = int(b[k])
                if not lo <= v <= hi:
                    return self.fail(400, "%s must be between %d and %d" % (k.replace("_", " "), lo, hi))
                d[k] = v
        write_mod(d)
        self.send(200, {"ok": True, "note": "Saved - works right away, no restart needed."})

    def get_reports(self, q):
        items = load_reports(I())
        self.send(200, {"items": items[:100], "open": sum(1 for x in items if x.get("open")),
                        "on": read_mod()["report"]})

    def post_reports_close(self, q):
        b = self.body_json()
        rid, every = str(b.get("id") or ""), b.get("id") == "all"
        with _REPORT_LOCK:
            items = load_reports(I())
            hit = 0
            for x in items:
                if (every or x["id"] == rid) and x.get("open"):
                    x["open"], x["closed_by"], x["closed_at"] = False, getattr(_TL, "user", "owner"), now()
                    hit += 1
            if not hit and not every:
                return self.fail(404, "No such report")
            write_json(_reports_path(I()), items)
        self.send(200, {"ok": True, "note": "Marked as handled."})

    def get_chat(self, q):
        """Chat history: newest last. q = words, player = name, around = a time (shows the 5 minutes around it)."""
        try:
            around = int(q.get("around") or 0)
        except ValueError:
            around = 0
        days = 30
        lines = read_chat(I(), around - 300 if around else now() - days * 86400, around + 300 if around else None)
        word = str(q.get("q") or "").strip().lower()[:80]
        player = str(q.get("player") or "").strip().lower()[:40]
        if not around:
            if player:
                lines = [c for c in lines if c["name"].lower() == player]
            if word:
                lines = [c for c in lines if word in c["msg"].lower() or word in c["name"].lower()]
        total = len(lines)
        self.send(200, {"lines": lines[-500:], "total": total, "on": read_mod()["chatlog"],
                        "players": sorted({c["name"] for c in lines[-3000:]}, key=str.lower)[:300] if not player else []})

    def post_chat_clear(self, q):
        for name in CHAT_FILES:
            try:
                os.remove(os.path.join(I().STATS_DIR, name))
            except FileNotFoundError:
                pass
            except OSError as e:
                return self.fail(500, "Couldn't delete the chat history (%s)" % short_err(e))
        self.send(200, {"ok": True, "note": "Chat history deleted."})

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
        b = self.body_json()
        what = b.get("action")
        if what == "start" and not I().meta.get("reviewed"):
            return self.fail(409, "Look over the settings first - open the dashboard and press Start again.")
        if what in ("start", "restart") and moved_note(I()):
            if not b.get("anyway"):
                return self.send(409, {"ok": False, "moved": True, "error": moved_note(I()) + ". Start it on this computer "
                                       "too? Use the same AuthKey on only one of them."})
            set_server_meta(I().id, moved_to=None)
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
                        "desc_modsize": bool(I().meta.get("desc_modsize")),
                        "light": bool(I().meta.get("light_maps")), "current_map": current_map(),
                        "all_maps_size": sum(m["size"] for m in mods if (m["enabled"] or m.get("parked")) and m["maps"]),
                        "storage": mods_storage(I(), mods), "sets": mod_sets_view(I(), mods),
                        "upload_mbit": APP.settings.get("upload_mbit") or 0,
                        "limit_kbps": int((I().meta.get("limits") or {}).get("upload_kbps") or 0)})

    def get_mods_advice(self, q):
        self.send(200, mod_advice(I()))

    def post_mods_sets(self, q):
        """Mod sets: save the mods in use now under a name, switch to a saved set, or delete one."""
        b = self.body_json()
        act = b.get("action")
        name = clean_set_name(b.get("name"))
        inst = I()
        sets = mod_sets(inst)
        cur = next((x for x in sets if x["name"].lower() == name.lower()), None)
        if act == "save":
            mods = mods_in_use(list_mods(), inst)
            if not mods:
                return self.fail(400, "Turn some mods on first - a set saves the mods that are on now")
            if cur:
                cur["mods"] = mods
                cur["name"] = name
            elif len(sets) >= MODSET_MAX:
                return self.fail(400, "You have %d mod sets - delete one first" % MODSET_MAX)
            else:
                sets.append({"name": name, "mods": mods})
            set_server_meta(inst.id, mod_sets=sets)
            return self.send(200, {"ok": True, "note": "Saved the mod set %s (%d mod%s)." % (name, len(mods), "" if len(mods) == 1 else "s")})
        if not cur:
            return self.fail(404, "There's no mod set called %s" % name)
        if act == "delete":
            set_server_meta(inst.id, mod_sets=[x for x in sets if x is not cur] or None)
            return self.send(200, {"ok": True, "note": "Deleted the mod set %s. The mods themselves are still there." % cur["name"]})
        if act != "apply":
            return self.fail(400, "bad action")
        on, off, missing = apply_mod_set(inst, cur["mods"])
        note = "Switched to %s: %d mod%s turned on, %d turned off." % (cur["name"], len(on), "" if len(on) == 1 else "s", len(off))
        if missing:
            note += " %d mod%s in this set %s no longer on the server: %s." % (
                len(missing), "" if len(missing) == 1 else "s", "is" if len(missing) == 1 else "are", ", ".join(missing[:5]) + (" ..." if len(missing) > 5 else ""))
        if on or off:
            refresh_mod_desc()
            APP.config_changed()
            note += " " + APP.applied_note()
        self.send(200, {"ok": True, "note": note, "on": on, "off": off, "missing": missing})

    def post_mods_light(self, q):
        on = bool(self.body_json().get("on"))
        inst = I()
        if on:
            set_server_meta(inst.id, light_maps=True)
            moved = light_sync(inst)
            note = "Light mode is on. %d map mod%s parked - players only download the map being played." % (
                len([m for m in moved if m[0] == "-"]), "" if len([m for m in moved if m[0] == "-"]) == 1 else "s")
        else:
            back = light_off(inst)
            moved = back
            note = "Light mode is off - %d map mod%s turned back on." % (len(back), "" if len(back) == 1 else "s")
        if moved:
            refresh_mod_desc()
            APP.config_changed()
            note += " " + APP.applied_note()
        self.send(200, {"ok": True, "note": note})

    def put_mods_upload(self, q):
        name = safe_zip_name(q.get("name"))
        if not name:
            return self.fail(400, "Only .zip files can be uploaded")
        room = upload_room_error(self.content_length())
        if room:
            return self.fail(507, room)
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
        if name == TOOLS_MOD and act in ("toggle", "delete"):
            return self.fail(400, "This is EasyServer's own tools mod - turn /tp and /repair off under Config -> In-game tools to remove it")
        if name in parked_maps(I()):
            set_server_meta(I().id, parked_maps=[n for n in parked_maps(I()) if n != name])
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
        """Check the mods that haven't been checked yet (new, changed, or checked by an older version of the
        checker). {"all": true} checks every mod again - e.g. after the antivirus got new virus definitions."""
        everything = self.body_json().get("all") is True
        res = []
        for m in list_mods():
            folder = I().CLIENT_DIR if m["enabled"] else I().DISABLED_DIR
            path = os.path.join(folder, m["name"])
            done = None if everything else modscan.cached_result(path)
            if done:
                res.append({"name": m["name"], "verdict": done["verdict"], "reasons": done.get("reasons", []), "skipped": True})
                continue
            # not forced: same content under another name still counts as checked
            r = modscan.scan(path, force=everything)
            if r["verdict"] == "blocked":
                os.makedirs(I().QUAR_DIR, exist_ok=True)
                dest = os.path.join(I().QUAR_DIR, m["name"])
                shutil.move(os.path.join(folder, m["name"]), dest)
                modscan.write_note(dest + ".why.txt", modscan.why_text(r["reasons"]))
            res.append({"name": m["name"], "verdict": r["verdict"], "reasons": r["reasons"], "skipped": bool(r.get("cached"))})
        self.send(200, {"ok": True, "results": res, "checked": sum(1 for x in res if not x["skipped"]),
                        "skipped": sum(1 for x in res if x["skipped"])})

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

    # ---------- lap times
    def get_laps(self, q):
        cfg = read_laps_cfg()
        g = toml_parse(APP.read_config_text())[0].get("General", {})
        self.send(200, dict(cfg, radii=list(LAP_RADII), tracks=laps_summary(25), map=map_name(g.get("Map")) or "",
                            plugin=os.path.exists(os.path.join(I().STATS_DIR, "main.lua")),
                            status_page=bool(APP.settings.get("statuspage_on"))))

    def post_laps(self, q):
        b = self.body_json()
        act = b.get("action")
        if not act:
            cfg = read_laps_cfg()
            if "on" in b:
                cfg["on"] = bool(b["on"])
            if "public" in b:
                cfg["public"] = bool(b["public"])
            if "radius" in b:
                try:
                    r = int(b["radius"])
                except (TypeError, ValueError):
                    r = 0
                if r not in LAP_RADII:
                    return self.fail(400, "Pick a line width from the list")
                cfg["radius"] = r
            write_laps_cfg(cfg)
            _STATUS_CACHE["t"] = 0
            return self.send(200, {"ok": True, "note": ("Saved - the game picks it up within 10 seconds." if cfg["on"] else "Saved - lap times are off.")
                                   + self._games_mod_note()})
        tid = str(b.get("id") or "")
        lines = read_track_lines()
        mine = [l for l in lines if l.split("\t", 1)[0] == tid]
        if not mine:
            return self.fail(404, "That track doesn't exist any more")
        times = read_laptimes()
        if act == "rename":
            name = re.sub(r"[\t\r\n;,]", " ", clean_msg(b.get("name") or "")).strip()[:40]
            if not name:
                return self.fail(400, "Give the track a name")
            if any(l.split("\t")[1].lower() == name.lower() and l.split("\t", 1)[0] != tid for l in lines):
                return self.fail(400, "There's already a track with that name")
            p = mine[0].split("\t")
            p[1] = name
            shared_write(laps_file("tracks.tsv"), "".join((("\t".join(p) if l is mine[0] else l) + "\n") for l in lines))
            note = "Renamed."
        elif act == "delete":
            shared_write(laps_file("tracks.tsv"), "".join(l + "\n" for l in lines if l is not mine[0]))
            times.pop(tid, None)
            write_laptimes(times)
            note = "Track and its times deleted."
        elif act == "clear":
            times.pop(tid, None)
            write_laptimes(times)
            note = "Times cleared - the next lap is a new record."
        elif act == "remove_time":
            who = str(b.get("name") or "").lower()
            times[tid] = [r for r in times.get(tid, []) if r["name"].lower() != who]
            write_laptimes(times)
            note = "Time removed."
        else:
            return self.fail(400, "Unknown action")
        _STATUS_CACHE["t"] = 0
        self.send(200, {"ok": True, "note": note})

    def _games_mod_note(self):
        """Games and lap times are drawn on screen by the helper mod: add or remove it to match."""
        try:
            how = ensure_tools_mod()
        except OSError as e:
            sys.stderr.write("helper mod: %s\n" % short_err(e))
            return ""
        if how not in ("added", "removed"):
            return ""
        refresh_mod_desc()
        APP.config_changed()
        if how == "added":
            return (" Players download a tiny helper mod (%s) when they join - it shows checkpoints, a timer and cops and robbers"
                    " on screen." % fmt_bytes(len(tools_mod_bytes())))
        return " The helper mod was removed."

    # ---------- games: races, cops and robbers, speed traps, badges, seasons, live map, weekly recap
    def get_games(self, q):
        self.send(200, games_summary())

    def post_games(self, q):
        b = self.body_json()
        act = b.get("action")
        if not act:
            cfg = read_games_cfg()
            for k in GAME_SWITCHES:
                if k in b:
                    cfg[k] = bool(b[k])
            if "champ_points" in b:
                if b["champ_points"] not in CHAMP_POINTS:
                    return self.fail(400, "Pick a points system from the list")
                cfg["champ_points"] = b["champ_points"]
            if "champ_name" in b:
                cfg["champ_name"] = re.sub(r"[\x00-\x1f]", "", str(b["champ_name"] or "")).strip()[:60]
            if cfg["champ"] and not cfg["champ_started"]:
                cfg["champ_started"] = now()
            for k in ("race_who", "cnr_who"):
                if k in b:
                    if b[k] not in ("everyone", "admins"):
                        return self.fail(400, "Pick who can start games from the list")
                    cfg[k] = b[k]
            if "cnr_busted" in b:
                if b["cnr_busted"] not in ("out", "cop"):
                    return self.fail(400, "Pick what happens to a busted robber from the list")
                cfg["cnr_busted"] = b["cnr_busted"]
            for k, allowed in (("cnr_minutes", CNR_MINUTES), ("cnr_catch", CNR_CATCH), ("cnr_hold", CNR_HOLD)):
                if k in b:
                    try:
                        v = int(b[k])
                    except (TypeError, ValueError):
                        v = -1
                    if v not in allowed:
                        return self.fail(400, "Pick a value from the list")
                    cfg[k] = v
            write_games_cfg(cfg)
            return self.send(200, {"ok": True, "note": "Saved - the game picks it up within 10 seconds." + self._games_mod_note()})
        if act in ("champ_new", "champ_end"):
            cfg = read_games_cfg()
            winner = end_champ(cfg)
            note = ("%s won %s. " % (winner, cfg["champ_name"] or "the championship")) if winner else ""
            if act == "champ_new":
                name = re.sub(r"[\x00-\x1f]", "", str(b.get("name") or "")).strip()[:60]
                if not name:
                    return self.fail(400, "Give the championship a name")
                cfg.update(champ=True, champ_name=name, champ_started=now())
                note += "%s has started - every race with 2 or more drivers counts." % name
            else:
                cfg.update(champ=False, champ_started=0)
                note += "Championship ended."
            write_games_cfg(cfg)
            return self.send(200, {"ok": True, "note": note})
        if act in ("clear_drift", "remove_drift"):
            m, who = str(b.get("map") or ""), str(b.get("name") or "").lower()
            rows = read_drift()
            keep = [r for r in rows if r["raw_map"] != m or (act == "remove_drift" and r["name"].lower() != who)]
            if len(keep) == len(rows):
                return self.fail(404, "That drift score is already gone")
            write_drift(keep)
            return self.send(200, {"ok": True, "note": "Drift scores cleared." if act == "clear_drift" else "Drift score removed."})
        tid = str(b.get("id") or "")
        lines = [l for l in shared_read(laps_file("traps.tsv"), 256 * 1024).splitlines() if TRAP_RE.match(l)]
        mine = [l for l in lines if l.split("\t", 1)[0] == tid]
        if not mine:
            return self.fail(404, "That speed trap doesn't exist any more")
        speeds = read_trap_speeds()
        if act == "delete_trap":
            shared_write(laps_file("traps.tsv"), "".join(l + "\n" for l in lines if l is not mine[0]))
            speeds.pop(tid, None)
            note = "Speed trap and its speeds deleted."
        elif act == "clear_trap":
            speeds.pop(tid, None)
            note = "Speeds cleared."
        elif act == "remove_speed":
            who = str(b.get("name") or "").lower()
            speeds[tid] = [r for r in speeds.get(tid, []) if r["name"].lower() != who]
            note = "Speed removed."
        else:
            return self.fail(400, "Unknown action")
        write_trap_speeds(speeds)
        self.send(200, {"ok": True, "note": note})

    def get_livemap(self, q):
        self.send(200, live_map())

    def get_recap(self, q):
        cfg = recap_cfg()
        r = weekly_recap()
        self.send(200, dict(cfg, days=list(RECAP_DAYS), channels=recap_channels(), last=I().meta.get("recap_last"),
                            preview={"title": r[0], "text": r[1]} if r else None))

    def post_recap(self, q):
        b = self.body_json()
        if b.get("send"):
            r = weekly_recap()
            if not r:
                return self.fail(400, "Nobody played this week, so there's nothing to post")
            where = broadcast(r[0], r[1])
            if not where:
                return self.fail(400, "There's no channel to post to - set up the Discord webhook, Telegram or a custom webhook in Settings first")
            set_server_meta(I().id, recap_last=now())
            return self.send(200, {"ok": True, "note": "Posted to " + " and ".join(where) + "."})
        cfg = recap_cfg()
        if "on" in b:
            cfg["on"] = bool(b["on"])
        for k, hi in (("day", 6), ("hour", 23)):
            if k in b:
                try:
                    v = int(b[k])
                except (TypeError, ValueError):
                    v = -1
                if not 0 <= v <= hi:
                    return self.fail(400, "Pick a day and an hour from the lists")
                cfg[k] = v
        set_server_meta(I().id, recap=cfg)
        self.send(200, {"ok": True, "note": ("Saved - it's posted every %s at %02d:00." % (RECAP_DAYS[cfg["day"]], cfg["hour"])) if cfg["on"] else "Saved - the weekly recap is off."})

    # ---------- player profiles
    def get_players_profile(self, q):
        name = str(q.get("name") or "").strip()[:64]
        if not name:
            return self.fail(400, "Which player?")
        p = player_profile(name)
        with LOCK:
            ids = [i for i in INSTANCES if i != I().id]
        if ids and self.sess.get("user", "owner") != "owner":
            u = find_user(self.sess["user"]) or {}
            ids = [i for i in ids if user_role_for(u, i)]
        p["elsewhere"] = [{k: c[k] for k in ("server", "id", "seconds", "sessions", "last_seen", "online", "laps", "drift")}
                          for c in player_everywhere(name, ids)] if ids else []
        self.send(200, p)

    def post_players_note(self, q):
        b = self.body_json()
        name = str(b.get("name") or "").strip()[:64]
        if not name:
            return self.fail(400, "Which player?")
        lname = name.lower()
        notes = dict(player_notes())
        mine = list(notes.get(lname, []))
        if b.get("delete"):
            mine = [n for n in mine if n.get("id") != b["delete"]]
            note = "Note deleted."
        else:
            text = clean_msg(b.get("text") or "").strip()[:500]
            if not text:
                return self.fail(400, "Write something first")
            if len(mine) >= NOTES_MAX:
                return self.fail(400, "That's a lot of notes - delete some old ones first")
            mine.insert(0, {"id": secrets.token_hex(4), "t": now(), "by": getattr(_TL, "user", "owner") or "owner", "text": text})
            note = "Note saved. Only people who can see this dashboard can read it."
        if mine:
            notes[lname] = mine
        else:
            notes.pop(lname, None)
        if len(notes) > 2000:
            return self.fail(400, "Too many players with notes")
        set_server_meta(I().id, player_notes=notes)
        self.send(200, {"ok": True, "note": note, "notes": mine})

    # ---------- first-time setup checklist
    def get_checklist(self, q):
        self.send(200, setup_checklist())

    def post_checklist(self, q):
        b = self.body_json()
        inst = I()
        if "hidden" in b:
            set_server_meta(inst.id, setup_hidden=bool(b["hidden"]) or None)
        if b.get("skip") in ("name", "authkey", "mods", "reach", "invite", "alerts"):
            sk = [x for x in (inst.meta.get("setup_skipped") or []) if x != b["skip"]] + ([b["skip"]] if b.get("on", True) else [])
            set_server_meta(inst.id, setup_skipped=sk or None)
        if b.get("invited"):
            set_server_meta(inst.id, invited=True)
        self.send(200, dict(setup_checklist(), ok=True))

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

    def get_upnp(self, q):
        app = APP
        if on_mac():
            h = host_info()
            return self.send(200, {"mac": True, "on": h.get("ports") == "auto", "relay": relay_on(), "state": {"ports": [], "error": h.get("upnp_error")},
                                   "mac_upnp": h.get("upnp") or "off", "mac_upnp_at": int(h.get("upnp_at") or 0), "mac_ip": mac_lan_ip(),
                                   "mode": "always", "open_until": 0, "is_open": h.get("upnp") == "ok", "players": app.upnp_players(),
                                   "idle": UPNP_IDLE, "ports": [{"port": p, "proto": pr} for p, pr in app.upnp_ports()]})
        st = app.upnp_state
        if q.get("check") == "1" or st is None:
            st = app.upnp_apply(fresh=True) if app.settings.get("upnp_on") and not relay_on() else self._upnp_probe()
        self.send(200, {"on": bool(app.settings.get("upnp_on")), "relay": relay_on(), "state": st,
                        "mode": app.settings.get("upnp_mode") or "always", "open_until": int(app.settings.get("upnp_open_until") or 0),
                        "is_open": bool(app.settings.get("upnp_mapped")), "players": app.upnp_players(), "idle": UPNP_IDLE,
                        "ports": [{"port": p, "proto": pr} for p, pr in app.upnp_ports()]})

    def _upnp_probe(self):
        """Look for a UPnP router without changing anything."""
        st = {"t": now(), "ports": [], "error": None, "router": None, "external_ip": None, "local_ip": None, "probe": True}
        try:
            gw = APP.upnp_gateway(fresh=True)
        except Exception as e:
            gw, st["error"] = None, short_err(e)
        if not gw:
            st["error"] = st["error"] or "Your router didn't answer - UPnP is off or not supported."
        else:
            st.update(router=gw.name or gw.host, local_ip=gw.local_ip)
            try:
                st["external_ip"] = gw.external_ip()
            except Exception:
                pass
        APP.upnp_state = st
        return st

    def post_upnp(self, q):
        app = APP
        b = self.body_json()
        if "mode" in b or "open_for" in b or "close_now" in b:
            if b.get("mode") in ("always", "needed"):
                app.settings.update_one("upnp_mode", b["mode"])
                if b["mode"] == "needed":
                    app.upnp_open_for(UPNP_IDLE)       # don't slam the door on someone joining right now
            if "open_for" in b:
                app.upnp_open_for(max(60, min(int(b.get("open_for") or 0), 24 * 3600)))
            if b.get("close_now"):
                app.settings.update_one("upnp_open_until", 0)
            if not app.settings.get("upnp_on") or relay_on():
                return self.send(200, {"ok": True, "on": bool(app.settings.get("upnp_on")), "note": "Saved."})
            st = app.upnp_apply()
            ok = not st.get("error") and all(r["ok"] for r in st["ports"])
            opened = bool(st["ports"])
            note = (("Port open until nobody has played for %d minutes." % (UPNP_IDLE // 60) if opened else
                     "Port closed - it opens again when you copy an invite.")
                    if app.settings.get("upnp_mode") == "needed" else "Port kept open all the time.")
            return self.send(200, {"ok": bool(ok), "on": True, "note": note if ok else (st.get("error") or "The router refused: " +
                             "; ".join("%s %s: %s" % (r["port"], r["proto"], r["error"]) for r in st["ports"] if not r["ok"])), "state": st})
        on = bool(b.get("on"))
        if on and on_mac():
            return self.fail(400, "On a Mac the Mac itself opens the port (always, while it's on). To change that, run the Mac installer again.")
        if on and relay_on():
            return self.fail(400, "\"Hide my IP\" is on - players join through the relay, so nothing needs to be opened on your router.")
        if on:
            app.settings.update_one("upnp_on", True)
            if app.settings.get("upnp_mode") == "needed":
                app.upnp_open_for(UPNP_IDLE)
            st = app.upnp_apply(fresh=True)
            ok = not st.get("error") and st["ports"] and all(r["ok"] for r in st["ports"])
            if not ok:
                app.settings.update_one("upnp_on", bool(st["ports"]) and any(r["ok"] for r in st["ports"]))
            note = ("Done - your router now forwards port %s to this computer. Friends can join from anywhere." %
                    ", ".join(sorted({str(r["port"]) for r in st["ports"]})) if ok else
                    (st.get("error") or "Some ports couldn't be opened: " +
                     "; ".join("%s %s: %s" % (r["port"], r["proto"], r["error"]) for r in st["ports"] if not r["ok"])))
            _PUBLIC_IP["t"] = 0                       # the network check should look again
            return self.send(200, {"ok": bool(ok), "note": note, "state": st, "on": app.settings.get("upnp_on")})
        app.settings.update_one("upnp_on", False)
        closed, err = app.upnp_close()
        self.send(200, {"ok": not err, "on": False, "note": ("Closed the port on your router." if closed else "Automatic port forwarding is off.")
                        + (" (The router didn't answer: %s - it may still have the forward until it restarts.)" % err if err else "")})

    def get_invite(self, q):
        """A ready-to-paste invitation for Discord / WhatsApp."""
        app = APP
        data, _ = validate_config(app.read_config_text(), app.settings.get("port"), I().has_authkey())[:2]
        g = data.get("General", {})
        name = re.sub(r"\^.", "", str(g.get("Name", "") or "my BeamMP server")).strip() or "my BeamMP server"
        host, port, via_relay = game_address()
        lan = lan_ip()
        online = len(analytics_online())
        public = not g.get("Private") and I().has_authkey()
        internet = bool(via_relay or duck_host() or public_ip())
        lines = ["**Join my BeamNG.drive multiplayer server: %s**" % name, ""]
        if internet:
            lines.append("In BeamMP: **Direct Connect** -> IP `%s` port `%s`" % (host, port))
        if public:
            lines.append("Or search **%s** in the BeamMP server list." % name)
        lines.append("Map: %s - %s/%s players online" % (map_name(g.get("Map")) or "?", online, g.get("MaxPlayers", "?")))
        mods = sum(1 for m in list_mods() if m["enabled"])
        if mods:
            size = sum(m.get("size", 0) for m in list_mods() if m["enabled"])
            lines.append("Mods: %d (%s, downloaded when you join)" % (mods, ("%.1f GB" % (size / 1073741824.0) if size >= 1073741824 else "%d MB" % max(1, round(size / 1048576.0)))))
        note = clean_msg(app.settings.get("invite_note") or "")[:300]
        foot = "Need BeamMP? https://beammp.com"
        credit = bool(app.settings.get("credit_link"))
        if credit:
            foot += "\nServer hosted with BeamMP EasyServer (free): " + SITE_URL
        self.send(200, {"base": "\n".join(lines), "footer": foot, "credit": credit, "credit_line": "Server hosted with BeamMP EasyServer (free): " + SITE_URL,
                        "text": "\n".join(lines + (["", note] if note else []) + ["", foot]), "host": host, "port": port, "lan": "%s:%s" % (lan, port),
                        "internet": internet, "relay": via_relay, "public": public, "note": note,
                        "lan_text": "Join **%s** on our Wi-Fi: BeamMP -> Direct Connect -> IP `%s` port `%s`" % (name, lan, port)})

    def post_invite(self, q):
        b = self.body_json()
        if "note" in b:
            APP.settings.update_one("invite_note", clean_msg(str(b.get("note") or ""))[:300])
        if "credit" in b:
            APP.settings.update_one("credit_link", bool(b.get("credit")))
            _STATUS_CACHE["t"] = 0
        self.send(200, {"ok": True})

    # ---------- BeamMP-only guard
    def get_guard(self, q):
        app = APP
        with app.guard_lock:
            g = app.guard
            blocked = [{"ip": ip, "until": int(b["until"]), "at": int(b["at"]), "why": b.get("why", ""), "times": b.get("times", 1)}
                       for ip, b in sorted(g.blocked.items(), key=lambda x: -x[1]["at"])][:200]
            out = {"on": bool(app.settings.get("guard_on")), "relay": relay_on(), "blocked": blocked, "count": len(g.blocked),
                   "total": g.total, "players_known": len(g.good), "error": app.guard_err,
                   "strikes": guard.STRIKES, "window": guard.WINDOW, "stay": guard.STAY,
                   "platform": "mac" if on_mac() else "windows" if IS_WIN else "linux", "mac": on_mac()}
        out.update(app.guard_status())
        self.send(200, out)

    def post_guard(self, q):
        app = APP
        b = self.body_json()
        ip = str(b.get("unblock") or "").strip()
        if b.get("unblock_all"):
            with app.guard_lock:
                for x in list(app.guard.blocked):
                    app.guard.unblock(x)
            app.guard_apply()
            return self.send(200, {"ok": True, "note": "Everyone is unblocked."})
        if not guard.norm_ip(ip):
            return self.fail(400, "That isn't an IP address")
        with app.guard_lock:
            gone = app.guard.unblock(ip)
        app.guard_apply()
        self.send(200, {"ok": True, "note": ("Unblocked %s - it won't be blocked again for a month." % ip) if gone else
                        "%s wasn't blocked. It's marked as a player now, so it won't be." % ip})

    # ---------- supporter licence
    def get_supporter(self, q):
        if not PAID_FEATURES:
            return self.send(200, {"off": True})
        sup = APP.settings.get("supporter") or {}
        self.send(200, {"active": supporter_active(), "shop_open": bool(LS_STORE_ID), "url": SUPPORT_URL,
                        "status": sup.get("status"), "plan": sup.get("plan"), "expires_at": sup.get("expires_at"),
                        "email": sup.get("email"), "checked": sup.get("checked"), "has_key": APP.secrets.has("SUPPORTER_KEY"),
                        "early_access": bool(APP.settings.get("early_access")),
                        "early": APP.updates.get("easy_early"), "early_url": APP.updates.get("easy_early_url")})

    def post_supporter(self, q):
        app = APP
        b = self.body_json()
        if "early_access" in b and "key" not in b and b.get("action") != "remove":
            app.settings.update_one("early_access", bool(b["early_access"]))
            return self.send(200, {"ok": True})
        sup = dict(app.settings.get("supporter") or {})
        if b.get("action") == "remove":
            if sup.get("instance_id") and app.secrets.has("SUPPORTER_KEY"):
                try:
                    ls_call("deactivate", license_key=app.secrets.get("SUPPORTER_KEY"), instance_id=sup["instance_id"])
                except Exception:
                    pass
            app.secrets.set("SUPPORTER_KEY", "")
            app.settings.update_one("supporter", {})
            return self.send(200, {"ok": True, "note": "Removed the licence from this computer - you can use it on another one now."})
        key = str(b.get("key") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9-]{8,80}", key):
            return self.fail(400, "That doesn't look like a licence key - copy it from the email you got after buying")
        if not LS_STORE_ID:
            return self.fail(400, "Supporter licences aren't on sale yet - EasyServer is completely free in the meantime.")
        try:
            d = ls_call("activate", license_key=key, instance_name=("EasyServer on %s" % socket.gethostname())[:60])
        except Exception as e:
            return self.fail(502, "Couldn't reach the licence server (%s) - try again in a minute" % short_err(e))
        info = ls_summary(d)
        if not d.get("activated") or info["store_id"] != LS_STORE_ID:
            err = clean_msg(str(d.get("error") or ""))[:200]
            return self.fail(400, "This key wasn't accepted%s." % (": " + err if err else ""))
        app.secrets.set("SUPPORTER_KEY", key)
        sup = dict(info, instance_id=str((d.get("instance") or {}).get("id") or ""), checked=now(), ok_at=now())
        app.settings.update_one("supporter", sup)
        threading.Thread(target=app.check_updates, kwargs={"notify": True}, daemon=True).start()
        self.send(200, {"ok": True, "note": "Thank you for supporting EasyServer! Your licence is active%s." % (" (" + info["plan"] + ")" if info["plan"] else "")})

    # ---------- updates
    def get_updates(self, q):
        up = dict(APP.updates)
        up.setdefault("installed", APP.server.installed_version())
        up["easy_installed"] = EASY_VERSION
        up["repo"] = REPO
        up["channel"] = update_channel()
        up["supporter"] = bool(supporter_active())
        up["paid"] = PAID_FEATURES
        if up["channel"] != "experimental":
            up.pop("easy_early", None)
        self.send(200, up)

    def post_updates_check(self, q):
        b = self.body_json(1024) if int(self.headers.get("Content-Length") or 0) else {}
        if b.get("channel") is not None:
            if b["channel"] not in ("stable", "experimental"):
                return self.fail(400, "channel must be stable or experimental")
            if PAID_FEATURES and b["channel"] == "experimental" and not supporter_active():
                return self.fail(403, "Experimental versions are for supporters - Settings -> Supporter")
            APP.settings.update_one("early_access" if PAID_FEATURES else "rolling", b["channel"] == "experimental")
            if b["channel"] == "stable":
                with LOCK:
                    APP.updates.pop("easy_early", None)
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

    # ---------- welcome message + announcements
    def get_messages(self, q):
        self.send(200, dict(read_messages(), every_choices=list(MSG_EVERY),
                            plugin=os.path.exists(os.path.join(I().STATS_DIR, "main.lua")),
                            chat_lang=I().meta.get("chat_lang") or "", languages=lang_index()))

    def post_messages(self, q):
        b = self.body_json()
        if "chat_lang" in b:
            code = str(b["chat_lang"] or "")
            if code and code not in {x["code"] for x in lang_index()}:
                return self.fail(400, "Pick a language from the list")
            set_server_meta(I().id, chat_lang=code or None)
            ensure_chat_lang()
            if len(b) == 1:
                return self.send(200, {"ok": True, "note": "Saved - the game chat switches within 30 seconds."})
        d = read_messages()
        for k in ("welcome", "announce"):
            if k in b:
                d[k] = bool(b[k])
        if "every" in b:
            if int(b["every"]) not in MSG_EVERY:
                return self.fail(400, "Pick how often from the list")
            d["every"] = int(b["every"])
        for k, n in (("welcome_text", 5), ("messages", 30)):
            if k in b:
                v = b[k] if isinstance(b[k], list) else str(b[k] or "").split("\n")
                d[k] = [clean_msg(x) for x in v if clean_msg(x)][:n]
        if d["welcome"] and not d["welcome_text"]:
            return self.fail(400, "Write the welcome message first")
        if d["announce"] and not d["messages"]:
            return self.fail(400, "Add at least one announcement")
        write_messages(d)
        self.send(200, {"ok": True, "note": "Saved - it works right away, no restart needed."})

    # ---------- map rotation
    def get_rotation(self, q):
        r = rotation_cfg(I())
        avail = BUILTIN_MAPS + [m for m in enabled_mod_maps() if m not in BUILTIN_MAPS]
        self.send(200, dict(r, available=avail, current=current_map(),
                            next=next_clear(r) if r["on"] else None, every_choices=list(CLEAR_EVERY),
                            warn_choices=[0, 1, 2, 5, 10]))

    def post_rotation(self, q):
        b = self.body_json()
        r = rotation_cfg(I())
        avail = set(BUILTIN_MAPS) | set(enabled_mod_maps())
        if "maps" in b:
            maps = []
            for m in (b["maps"] if isinstance(b["maps"], list) else [])[:50]:
                m = str(m).strip()
                if m in avail and m not in maps:
                    maps.append(m)
            r["maps"] = maps
        if "on" in b:
            r["on"] = bool(b["on"])
        if "empty_only" in b:
            r["empty_only"] = bool(b["empty_only"])
        if "every" in b:
            if int(b["every"]) not in CLEAR_EVERY:
                return self.fail(400, "Pick how often from the list")
            r["every"] = int(b["every"])
        if "at" in b:
            at = str(b["at"]).strip()
            if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", at):
                return self.fail(400, "Enter the time like 20:00")
            r["at"] = "%02d:%s" % (int(at.split(":")[0]), at.split(":")[1])
        if "warn" in b:
            if int(b["warn"]) not in (0, 1, 2, 5, 10):
                return self.fail(400, "Pick the countdown length from the list")
            r["warn"] = int(b["warn"])
        if r["on"] and len(r["maps"]) < 2:
            return self.fail(400, "Pick at least two maps")
        if r["warn"] * 60 >= r["every"] * 3600:
            return self.fail(400, "The countdown must be shorter than the time between map changes")
        set_server_meta(I().id, rotation=r)
        self.send(200, {"ok": True, "note": "Saved." + (" Next map change: %s." % time.strftime("%a %H:%M", time.localtime(next_clear(r)))
                                                         if r["on"] else "")})

    # ---------- server templates
    def get_templates(self, q):
        self.send(200, {"templates": [{"id": k, "label": v["label"], "about": v["about"], "map": v["map"],
                                       "max_players": v["max_players"], "tags": v["extras"]["tags"],
                                       "games": [g for g in GAME_SWITCHES if (v.get("games") or {}).get(g)], "laps": bool(v.get("laps"))}
                                      for k, v in TEMPLATES.items()], "current": I().meta.get("template") or ""})

    def post_template(self, q):
        b = self.body_json()
        tp = TEMPLATES.get(str(b.get("id")))
        if not tp:
            return self.fail(400, "Pick a template")
        app = APP
        ex = read_extras()
        ex.update(tp["extras"])
        write_extras(ex)
        md = read_mod()
        md["spam"] = bool(tp.get("spam", md["spam"]))
        md["filter"] = bool(tp.get("filter", md["filter"]))
        write_mod(md)
        msg = read_messages()
        msg.update({"welcome": True, "welcome_text": [tp["welcome"]], "announce": True, "messages": tp["messages"],
                    "every": max(msg["every"], 15)})
        write_messages(msg)
        if tp.get("games"):                      # the games that fit (Games page) and lap times
            cfg = read_games_cfg()
            cfg.update(tp["games"])
            if tp.get("champ_name") and not cfg["champ_name"]:
                cfg["champ_name"] = tp["champ_name"]
            if cfg["champ"] and not cfg["champ_started"]:
                cfg["champ_started"] = now()
            write_games_cfg(cfg)
            laps = read_laps_cfg()
            laps["on"] = bool(tp.get("laps"))
            write_laps_cfg(laps)
        set_server_meta(I().id, template=str(b.get("id")))
        text = toml_set(app.read_config_text(), "General", "MaxPlayers", tp["max_players"])
        note = "Applied the %s template." % tp["label"]
        if b.get("map") and (tp["map"] in BUILTIN_MAPS or tp["map"] in enabled_mod_maps()):
            app.write_config_text(text)
            ok, n2 = app.switch_map(tp["map"])
            note += " " + n2
        else:
            app.write_config_text(text)
            note += " " + app.applied_note()
        self.send(200, {"ok": True, "note": note, "search": tp.get("search") or ""})

    # ---------- presets
    def get_preset(self, q):
        md, (al_on, al_names) = read_mod(), read_allowlist()
        data, _, _ = toml_parse(APP.read_config_text())
        g = data.get("General", {})
        cur = None
        for pid, p in PRESETS.items():
            if all(g.get(k) == v for k, v in p.get("config", {}).items()) and all(md.get(k) == v for k, v in p.get("mod", {}).items()) \
                    and ("allowlist" not in p or p["allowlist"] == al_on):
                cur = pid
                break
        self.send(200, {"current": cur, "allow_count": len(al_names), "is_win": IS_WIN,
                        "presets": [{"id": k, "label": v["label"], "about": v["about"]} for k, v in PRESETS.items()]})

    def post_preset(self, q):
        b = self.body_json()
        p = PRESETS.get(str(b.get("id") or b.get("preset") or ""))
        if not p:
            return self.fail(400, "Pick a preset")
        notes = []
        if p.get("mod"):
            md = read_mod()
            md.update(p["mod"])
            write_mod(md)
        if p.get("extras"):
            ex = read_extras()
            ex.update(p["extras"])
            write_extras(ex)
        if "allowlist" in p:
            on, names = read_allowlist()
            if p["allowlist"] and not names:
                admins = read_mod()["admins"]
                names = admins[:]
                if not names:
                    notes.append("The invite list is still empty, so it stays off - add your friends in Players → Who can join, then turn it on.")
            write_allowlist(bool(p["allowlist"] and names), names)
        if p.get("flood") is not None and not IS_WIN and bool(APP.settings.get("flood_protect")) != p["flood"]:
            APP.settings.update({"flood_protect": p["flood"]})
            threading.Thread(target=APP.flood_tick, daemon=True).start()
        if p.get("config"):
            text = APP.read_config_text()
            for k, v in p["config"].items():
                text = toml_set(text, "General", k, v)
            APP.write_config_text(text, why="preset " + p["label"])
            notes.append(APP.applied_note())
        self.send(200, {"ok": True, "note": ("Applied \"%s\". " % p["label"]) + " ".join(n for n in notes if n)})

    # ---------- maintenance mode
    def get_maintenance(self, q):
        self.send(200, maintenance_cfg(I()))

    def post_maintenance(self, q):
        b = self.body_json()
        inst = I()
        cfg = maintenance_cfg(inst)
        if "message" in b:
            cfg["message"] = clean_msg(b["message"]) or cfg["message"]
        if "allow" in b:
            cfg["allow"] = clean_allow_names(b["allow"])[:200]
        if "kick" in b:
            cfg["kick"] = bool(b["kick"])
        was = cfg["on"]
        if "state" in b or "on" in b:
            cfg["on"] = str(b.get("state", b.get("on"))).lower() in ("on", "true", "1")
        if cfg["on"] and not was:
            cfg["since"] = now()
        set_server_meta(inst.id, maintenance=cfg)
        write_maintenance_file(inst, cfg)
        note = "Saved."
        if cfg["on"] and not was:
            admins = {a.lower() for a in read_mod()["admins"]} | {a.lower() for a in cfg["allow"]}
            online = online_names()
            out = [n for n in online if n.lower() not in admins] if cfg["kick"] else []
            if online:
                chat_say("Maintenance starting%s: %s" % (" - you'll be disconnected in 10 seconds" if out else "", cfg["message"]))
            if out:
                def later(iid=inst.id, names=out, msg=cfg["message"]):
                    time.sleep(10)
                    use_server(iid)
                    for n in names:
                        queue_action("kick", n, text=msg)
                threading.Thread(target=later, daemon=True).start()
            APP.notifier.add("server", "Maintenance mode on", "%s Only admins%s can join." % (
                inst.name, " and %d listed players" % len(cfg["allow"]) if cfg["allow"] else ""), "info")
            note = "Maintenance mode is on - only admins%s can join.%s" % (
                " and the players you listed" if cfg["allow"] else "", " %d player(s) will be disconnected in 10 seconds." % len(out) if out else "")
        elif was and not cfg["on"]:
            if online_names():
                chat_say("Maintenance is over - everyone can join again!")
            APP.notifier.add("server", "Maintenance mode off", "%s is open to everyone again." % inst.name, "info")
            note = "Maintenance is over - everyone can join again."
        self.send(200, {"ok": True, "note": note, "maintenance": cfg})

    # ---------- config history / comparison
    def get_config_history(self, q):
        vs = config_versions(I())
        self.send(200, {"items": [{k: v[k] for k in ("id", "t", "who", "why")} for v in vs], "keep": HIST_KEEP})

    def get_config_diff(self, q):
        """Compare: a saved version against now (?v=), two versions (?v=&w=) or this server against another (?other=)."""
        cur = APP.read_config_text()
        vs = {v["id"]: v for v in config_versions(I())}
        a_label, b_label = "before", "now"
        if q.get("other"):
            with LOCK:
                o = INSTANCES.get(q["other"])
            if not o:
                return self.fail(400, "Unknown server")
            me = I()
            use_server(o.id)
            a = APP.read_config_text()
            use_server(me.id)
            a_label, b_label, b_text = o.name, me.name, cur
        else:
            v = vs.get(q.get("v", ""))
            if not v:
                return self.fail(400, "Pick a saved version")
            a = v["text"]
            w = vs.get(q.get("w", ""))
            b_text = w["text"] if w else cur
            a_label = time.strftime("%Y-%m-%d %H:%M", time.localtime(v["t"])) + " (" + v["who"] + ")"
            if w:
                b_label = time.strftime("%Y-%m-%d %H:%M", time.localtime(w["t"])) + " (" + w["who"] + ")"
        d = config_diff(a, b_text)
        d.update({"a": a_label, "b": b_label})
        self.send(200, d)

    def post_config_restore(self, q):
        v = {x["id"]: x for x in config_versions(I())}.get(str(self.body_json().get("v", "")))
        if not v:
            return self.fail(400, "That version doesn't exist any more")
        cur = APP.read_config_text()
        key = re.search(r'(?m)^\s*AuthKey\s*=\s*"([^"]*)"', cur)
        text = v["text"]
        if key and key.group(1):
            text = toml_set(text, "General", "AuthKey", key.group(1))
        try:
            toml_parse(text)
        except Exception:
            return self.fail(400, "That saved version can't be read")
        APP.write_config_text(text, why="restored the version from " + time.strftime("%Y-%m-%d %H:%M", time.localtime(v["t"])))
        self.send(200, {"ok": True, "note": "Restored. " + APP.applied_note()})

    # ---------- in-game tools
    def get_tools(self, q):
        d = read_tools()
        d["installed"] = os.path.exists(os.path.join(I().CLIENT_DIR, TOOLS_MOD))
        d["size"] = len(tools_mod_bytes())
        self.send(200, d)

    def post_tools(self, q):
        b = self.body_json()
        d = read_tools()
        if "tp" in b:
            d["tp"] = bool(b["tp"])
        if "suggest" in b:
            d["suggest"] = bool(b["suggest"])
        if b.get("repair") in ("free", "cooldown", "off"):
            d["repair"] = b["repair"]
        try:
            if "repair_cd" in b:
                d["repair_cd"] = max(1, min(120, int(b["repair_cd"])))
            if "tp_cd" in b:
                d["tp_cd"] = max(0, min(3600, int(b["tp_cd"])))
        except (TypeError, ValueError):
            return self.fail(400, "Cooldowns must be numbers")
        write_tools(d)
        how = ensure_tools_mod()
        note = "Saved - works right away."
        if how in ("added", "removed"):
            refresh_mod_desc()
            APP.config_changed()
            note = ("Saved. Players download a tiny helper mod (%s) when they join. " % fmt_bytes(len(tools_mod_bytes()))
                    if how == "added" else "Saved. The helper mod was removed. ") + APP.applied_note().replace("Saved. ", "")
        self.send(200, {"ok": True, "note": note, "tools": d})

    # ---------- vehicle rules
    def get_vehicles(self, q):
        d = read_veh()
        mods = server_mod_vehicles()
        act = veh_activity()
        for s in act["seen"]:
            s["kind"] = veh_kind(s["jbm"], mods)
            s["blocked"] = s["jbm"].lower() in {j.lower() for j, _ in veh_blocklist(d)} if d["on"] else False
        self.send(200, {"rules": d, "preset": veh_preset_match(d),
                        "presets": [{"id": k, "label": v[0], "about": v[1]} for k, v in VEH_PRESETS.items()],
                        "blocked": [{"jbm": j, "why": w} for j, w in veh_blocklist(d)],
                        "mods": sorted(mods.values(), key=lambda v: (not v["heavy"], v["jbm"].lower())),
                        "base": {"cars": BASE_CARS, "trailers": BASE_TRAILERS, "props": BASE_PROPS, "heavyprops": BASE_HEAVY_PROPS},
                        "heavy_limits": {"nodes": HEAVY_NODES, "beams": HEAVY_BEAMS}, "activity": act})

    def post_vehicles(self, q):
        b = self.body_json()
        d = read_veh()
        for k in ("on", "exempt", "only", "props", "trailers", "heavyprops", "heavymods"):
            if k in b:
                d[k] = bool(b[k])
        try:
            if "cooldown" in b:
                d["cooldown"] = max(0, min(3600, int(b["cooldown"] or 0)))
            if "spam" in b:
                d["spam"] = max(0, min(120, int(b["spam"] or 0)))
        except (TypeError, ValueError):
            return self.fail(400, "The cooldown and the spawn limit must be numbers")
        for k in ("cars", "allow"):
            if k in b:
                raw = b[k] if isinstance(b[k], list) else re.split(r"[\s,]+", str(b[k] or ""))
                lst = []
                for x in raw:
                    j = clean_jbm(x)
                    if x and str(x).strip() and not j:
                        return self.fail(400, "\"%s\" isn't a vehicle name (letters, numbers, _ . - only)" % str(x)[:40])
                    if j and j.lower() not in [y.lower() for y in lst]:
                        lst.append(j)
                d[k] = lst[:500]
        if d["only"] and not d["allow"]:
            return self.fail(400, "Pick at least one car for \"only these cars\", or turn that off")
        write_veh(d)
        n = len(veh_blocklist(d))
        self.send(200, {"ok": True, "rules": d, "note": ("Saved - works within 10 seconds, no restart. %d vehicle%s blocked." %
                                                        (n, "" if n == 1 else "s")) if d["on"] else "Saved. Vehicle rules are off."})

    def post_vehicles_preset(self, q):
        pid = self.body_json().get("preset")
        if pid not in VEH_PRESETS:
            return self.fail(400, "Unknown preset")
        d = read_veh()
        d.update(VEH_PRESETS[pid][2])
        write_veh(d)
        self.send(200, {"ok": True, "note": "Using \"%s\" - works within 10 seconds, no restart." % VEH_PRESETS[pid][0]})

    def post_vehicles_block(self, q):
        b = self.body_json()
        j = clean_jbm(b.get("jbm"))
        if not j:
            return self.fail(400, "Unknown vehicle")
        d = read_veh()
        d["cars"] = [x for x in d["cars"] if x.lower() != j.lower()]
        if b.get("block", True):
            d["cars"].append(j)
            d["on"] = True
        write_veh(d)
        self.send(200, {"ok": True, "note": ("Blocked %s - works within 10 seconds." if b.get("block", True) else "%s is allowed again.") % j})

    # ---------- server plugins
    def _plug_job_public(self, j):
        return {k: v for k, v in j.items() if not k.startswith("_") and k != "dir"}

    def _plug_new_job(self, **kw):
        with LOCK:
            for k in [k for k, j in PLUGIN_JOBS.items() if j.get("finished") and now() - j["t"] > 3600]:
                shutil.rmtree(PLUGIN_JOBS.pop(k).get("dir") or "", ignore_errors=True)
            if len([j for j in PLUGIN_JOBS.values() if not j.get("finished")]) >= 2:
                return None
            os.makedirs(UPLOAD_TMP, exist_ok=True)
            jid = secrets.token_hex(6)
            job = dict(kw, job=jid, server=I().id, t=now(), state="Starting…", done=0, total=0, finished=False,
                       dir=tempfile.mkdtemp(dir=UPLOAD_TMP, prefix=".plug-dl-"))
            PLUGIN_JOBS[jid] = job
            return job

    def get_plugins(self, q):
        sdir = plugin_server_dir()
        self.send(200, {"catalog": plugin_catalog(), **plugins_overview(),
                        "writable": IS_WIN or os.access(sdir, os.W_OK), "owner": self.sess.get("role", "owner") == "owner"})

    def post_plugins_fetch(self, q):
        pid = str(self.body_json().get("id") or "")
        entry = next((p for p in plugin_catalog() if p["id"] == pid), None)
        if not entry:
            return self.fail(400, "That plugin isn't in the list")
        job = self._plug_new_job(id=pid, name=entry["name"], entry=entry)
        if not job:
            return self.fail(429, "Two plugin downloads are already running - wait for one to finish")
        threading.Thread(target=plugin_fetch, args=(job, I().id, entry), daemon=True).start()
        self.send(200, {"ok": True, "job": job["job"]})

    def get_plugins_job(self, q):
        j = PLUGIN_JOBS.get(q.get("job") or "")
        if not j or j["server"] != I().id:
            return self.fail(404, "no such download")
        self.send(200, self._plug_job_public(j))

    def put_plugins_upload(self, q):
        name = safe_zip_name(q.get("name"))
        if not name:
            return self.fail(400, "Only .zip files can be uploaded")
        job = self._plug_new_job(id="file-" + re.sub(r"[^a-z0-9_\-]", "-", os.path.splitext(name)[0].lower())[:30].strip("-"),
                                 name=os.path.splitext(name)[0][:60], entry=None)
        if not job:
            return self.fail(429, "Two plugin downloads are already running - wait for one to finish")
        tmp = os.path.join(job["dir"], "plugin.zip")
        try:
            self.body_to_file(tmp, PLUGIN_MAX)
            if not zipfile.is_zipfile(tmp):
                raise RuntimeError("That isn't a zip file.")
            h = hashlib.sha256()
            with open(tmp, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            sha = h.hexdigest()
            plan = plugin_plan(tmp)
            job.update(ok=True, finished=True, state="Ready to install", review=True, plan=plan_public(plan), version="uploaded",
                       sha256=sha, size=os.path.getsize(tmp), _plan=plan, _path=tmp, url="")
        except Exception as e:
            job.update(ok=False, finished=True, state="Failed", error=str(e) if isinstance(e, RuntimeError) else short_err(e))
        self.send(200 if job.get("ok") else 400, self._plug_job_public(job))

    def post_plugins_install(self, q):
        b = self.body_json()
        j = PLUGIN_JOBS.get(str(b.get("job") or ""))
        if not j or j["server"] != I().id or not j.get("review") or j.get("installed"):
            return self.fail(404, "That download is gone - start again")
        if not j.get("entry") and b.get("trust") is not True:
            return self.fail(400, "Tick that you trust this plugin's author first")
        rid = j["id"]
        replace = rid in plugin_records()
        e = j.get("entry") or {}
        meta = {"name": j["name"], "author": e.get("author", ""), "page": e.get("page", ""), "license": e.get("license", ""),
                "version": j.get("version", ""), "sha256": j.get("sha256", ""), "catalog": bool(e), "url": j.get("url", "")}
        try:
            plugin_install(j["_path"], j["_plan"], rid, meta, replace=replace)
        except RuntimeError as ex:
            return self.fail(400, str(ex))
        j["installed"] = True
        shutil.rmtree(j.get("dir") or "", ignore_errors=True)
        self.send(200, {"ok": True, "note": "%s %s. Restart the server (Overview) to load it." % (j["name"], "updated" if replace else "installed")})

    def post_plugins_toggle(self, q):
        b = self.body_json()
        try:
            plugin_set_on(str(b.get("id") or ""), bool(b.get("on")))
        except RuntimeError as e:
            return self.fail(400, str(e))
        self.send(200, {"ok": True, "note": ("Turned on" if b.get("on") else "Turned off") + ". Restart the server (Overview) for it to take effect."})

    def post_plugins_remove(self, q):
        try:
            plugin_remove(str(self.body_json().get("id") or ""))
        except RuntimeError as e:
            return self.fail(400, str(e))
        self.send(200, {"ok": True, "note": "Removed. Restart the server (Overview) for it to take effect."})

    def post_plugins_adopt(self, q):
        """Let EasyServer manage a plugin someone copied in by hand (so it can be turned off and on)."""
        f = str(self.body_json().get("folder") or "")
        if not PLUGIN_FOLDER_RE.fullmatch(f) or f.lower() == OWN_PLUGIN.lower() or not os.path.isdir(os.path.join(plugin_server_dir(), f)):
            return self.fail(400, "Unknown plugin folder")
        rid = "manual-" + re.sub(r"[^a-z0-9_\-]", "-", f.lower())[:30]
        d = _plug_read()
        d.setdefault(I().id, {})[rid] = {"name": f, "author": "", "page": "", "license": "", "version": "copied in by hand",
                                         "sha256": "", "catalog": False, "url": "", "server": [f], "client": [],
                                         "installed": now(), "on": True}
        _plug_write(d)
        self.send(200, {"ok": True, "id": rid})

    # ---------- mod pack share code
    def get_modpack_code(self, q):
        """A short code with the BeamNG repository mods that are turned on. Another EasyServer can paste it."""
        ids, other = [], []
        for m in list_mods():
            if not m["enabled"] or m["builtin"]:
                continue
            info = modscan_info_cached(os.path.join(I().CLIENT_DIR, m["name"]))
            (ids.append(info["resource_id"]) if info else other.append(m["name"]))
        code = ""
        if ids:
            raw = zlib.compress(json.dumps({"v": 1, "ids": sorted(set(ids))}, separators=(",", ":")).encode(), 9)
            code = "ES1-" + base64.urlsafe_b64encode(raw).decode().rstrip("=")
        self.send(200, {"code": code, "count": len(set(ids)), "not_included": other})

    def post_modpack_code(self, q):
        code = re.sub(r"\s+", "", str(self.body_json().get("code") or ""))
        try:
            if not code.startswith("ES1-") or len(code) > 20000:
                raise ValueError
            dec = zlib.decompressobj()
            raw = dec.decompress(base64.urlsafe_b64decode(code[4:] + "=" * (-len(code[4:]) % 4)), 65536)
            if dec.unconsumed_tail:
                raise ValueError("too big")
            ids = json.loads(raw.decode("utf-8")).get("ids")
            ids = [int(x) for x in ids if isinstance(x, int) and 0 < x < 10 ** 7][:60]
        except (ValueError, TypeError, AttributeError, zlib.error, binascii.Error):
            return self.fail(400, "That isn't an EasyServer mod pack code (they start with ES1-)")
        have = installed_repo_ids()
        todo = [i for i in ids if i not in have]
        if not todo:
            return self.send(200, {"ok": True, "jobs": [], "note": "You already have all %d mods from that code." % len(ids)})
        jobs = []
        with LOCK:
            for i in todo:
                jid = secrets.token_hex(6)
                job = {"job": jid, "id": i, "server": I().id, "t": now(), "state": "Waiting…", "done": 0, "total": 0,
                       "finished": False, "name": "", "title": "Mod %d" % i}
                MODB_JOBS[jid] = job
                jobs.append(job)
        inst_id = I().id

        def run():
            for job in jobs:                    # one at a time - kind to beamng.com
                modb_install(job, inst_id, job["id"])
        threading.Thread(target=run, daemon=True).start()
        self.send(200, {"ok": True, "jobs": [j["job"] for j in jobs],
                        "note": "Downloading %d mod%s from the BeamNG repository, one after another (%d you already have). "
                                "Each gets the virus check. Watch the progress on this page."
                                % (len(todo), "" if len(todo) == 1 else "s", len(ids) - len(todo))})

    # ---------- per-map statistics
    def get_players_maps(self, q):
        try:
            days = max(1, min(90, int(q.get("days") or 30)))
        except ValueError:
            days = 30
        self.send(200, per_map_stats(I(), days))

    # ---------- log explainer
    def get_logs_explain(self, q):
        try:
            with open(I().SERVER_LOG, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                f.seek(max(0, size - 4 * 1024 * 1024))
                text = f.read().decode("utf-8", "replace")
        except OSError:
            return self.send(200, {"groups": [], "lines": 0, "note": "There's no server log yet - start the server once."})
        groups = explain_log(text)
        self.send(200, {"groups": groups, "lines": text.count("\n"), "size": size,
                        "note": "Looked at the last %s of the log." % fmt_bytes(min(size, 4 * 1024 * 1024))})

    def post_logs_explain(self, q):
        line = str(self.body_json().get("line") or "")[:2000]
        self.send(200, {"explain": explain_line(line)})

    # ---------- public status page
    def get_statuspage(self, q):
        s = APP.settings
        base = dashboard_url().rstrip("/")
        self.send(200, {"on": bool(s.get("statuspage_on")), "players": bool(s.get("statuspage_players")), "mods": bool(s.get("statuspage_mods")),
                        "address": bool(s.get("statuspage_address")), "relay": relay_on(),
                        "title": s.get("statuspage_title") or "", "about": s.get("statuspage_about") or "",
                        "discord": s.get("statuspage_discord") or "", "url": base + "/status", "lan_url": "http://%s:%s/status" % (lan_ip(), s.get("port")),
                        "remote": bool(s.get("remote_enabled")), "credit": bool(s.get("credit_link")), "preview": public_status()})

    def post_statuspage(self, q):
        b = self.body_json()
        upd = {}
        if "on" in b:
            upd["statuspage_on"] = bool(b["on"])
        if "players" in b:
            upd["statuspage_players"] = bool(b["players"])
        if "title" in b:
            upd["statuspage_title"] = clean_msg(b["title"])[:80]
        if "about" in b:
            upd["statuspage_about"] = "\n".join(clean_msg(x) for x in str(b["about"] or "").splitlines()).strip()[:500]
        if "discord" in b:
            inv = str(b["discord"] or "").strip()
            if inv and not DISCORD_INVITE_RE.fullmatch(inv):
                return self.fail(400, "Paste a Discord invite link like https://discord.gg/abc123")
            upd["statuspage_discord"] = inv
        if "mods" in b:
            upd["statuspage_mods"] = bool(b["mods"])
        if "address" in b:
            upd["statuspage_address"] = bool(b["address"])
        if "credit" in b:
            upd["credit_link"] = bool(b["credit"])
        APP.settings.update(upd)
        _STATUS_CACHE["t"] = 0
        self.send(200, {"ok": True, "note": "Saved." + (" The page is public now - anyone with the link can see it." if upd.get("statuspage_on") else "")})

    # ---------- alert channels: Telegram + any webhook, event advertising
    def get_integrations(self, q):
        s, sec = APP.settings, APP.secrets
        self.send(200, {"telegram": {"enabled": bool(s.get("telegram_enabled")), "has_token": sec.has("TELEGRAM_TOKEN"), "chat": s.get("telegram_chat") or ""},
                        "webhook": {"enabled": bool(s.get("webhook_enabled")), "has_url": sec.has("CUSTOM_WEBHOOK"),
                                    "host": urllib.parse.urlparse(sec.get("CUSTOM_WEBHOOK") or "").hostname or ""},
                        "event_ads": bool(s.get("event_ads")), "discord": bool(webhook_parts()[0])})

    def post_integrations(self, q):
        b = self.body_json()
        app, upd, notes = APP, {}, []
        if "telegram_token" in b:
            tok = str(b["telegram_token"] or "").strip()
            if tok and not re.fullmatch(r"\d{5,15}:[A-Za-z0-9_-]{30,60}", tok):
                return self.fail(400, "That doesn't look like a Telegram bot token (it looks like 123456789:ABC...)")
            app.secrets.set("TELEGRAM_TOKEN", tok)
            if not tok:
                upd.update(telegram_enabled=False, telegram_chat="")
        if "telegram_chat" in b:
            c = str(b["telegram_chat"] or "").strip()
            if c and not re.fullmatch(r"-?\d{1,20}|@[A-Za-z0-9_]{4,40}", c):
                return self.fail(400, "The chat ID is a number (or @channelname)")
            upd["telegram_chat"] = c
        if b.get("telegram_find"):
            if not app.secrets.has("TELEGRAM_TOKEN"):
                return self.fail(400, "Save the bot token first")
            try:
                cid, title = telegram_find_chat(app.secrets.get("TELEGRAM_TOKEN"))
            except ValueError as e:
                return self.fail(400, str(e))
            if not cid:
                return self.fail(400, "No message found - send your bot a message (e.g. \"hi\") in Telegram, or add it to your group, then try again")
            upd["telegram_chat"] = cid
            notes.append("Found the chat %s." % (title or cid))
        if "telegram_enabled" in b:
            upd["telegram_enabled"] = bool(b["telegram_enabled"])
        if "webhook_url" in b:
            u = str(b["webhook_url"] or "").strip()
            if u and not valid_custom_webhook(u):
                return self.fail(400, "The webhook address must start with https://")
            if u and valid_webhook(u):
                return self.fail(400, "That's a Discord webhook - put it in the Discord section instead")
            if u and not public_host(urllib.parse.urlparse(u).hostname):
                return self.fail(400, "The webhook must be an internet address (https://...). Addresses in your home network, "
                                      "this computer and cloud-internal addresses aren't allowed")
            app.secrets.set("CUSTOM_WEBHOOK", u)
            if not u:
                upd["webhook_enabled"] = False
        if "webhook_enabled" in b:
            upd["webhook_enabled"] = bool(b["webhook_enabled"])
        if "event_ads" in b:
            upd["event_ads"] = bool(b["event_ads"])
        if upd:
            app.settings.update(upd)
        test = str(b.get("test") or "")
        if test == "telegram":
            try:
                telegram_send("Test from BeamMP EasyServer - alerts will arrive here.", "success")
                notes.append("Test message sent to Telegram.")
            except ValueError as e:
                return self.fail(400, "Telegram: %s" % e)
        elif test == "webhook":
            try:
                custom_webhook_send("Test from BeamMP EasyServer", "Alerts will arrive here.", "success", "test")
                notes.append("Test sent to the webhook.")
            except ValueError as e:
                return self.fail(400, "Webhook: %s" % e)
        self.send(200, {"ok": True, "note": " ".join(notes) or "Saved."})

    # ---------- timed announcements
    def get_timed(self, q):
        self.send(200, {"items": timed_msgs(I()), "discord": bool(webhook_parts()[0])})

    def post_timed(self, q):
        raw = self.body_json().get("items")
        if not isinstance(raw, list) or len(raw) > 20:
            return self.fail(400, "At most 20 timed messages")
        out = []
        for m in raw:
            if not isinstance(m, dict):
                return self.fail(400, "bad message")
            text = "\n".join(clean_msg(x) for x in str(m.get("text") or "").splitlines() if clean_msg(x))[:600]
            if not text:
                continue
            at = str(m.get("at") or "").strip()
            if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", at):
                return self.fail(400, "Enter the time like 20:00")
            days = sorted({int(d) for d in (m.get("days") or []) if str(d).isdigit() and 0 <= int(d) <= 6})
            if not days:
                return self.fail(400, "Pick at least one day for \"%s\"" % text[:30])
            out.append({"at": "%02d:%s" % (int(at.split(":")[0]), at.split(":")[1]), "days": days, "text": text,
                        "discord": bool(m.get("discord")), "on": bool(m.get("on", True))})
        set_server_meta(I().id, timed_msgs=out)
        self.send(200, {"ok": True, "note": "Saved %d timed message%s." % (len(out), "" if len(out) == 1 else "s")})

    # ---------- modpack
    def get_modpack(self, q):
        mods = [m for m in list_mods() if (m["enabled"] or m.get("parked")) and m["name"] != TOOLS_MOD]
        if not mods:
            return self.fail(400, "This server has no enabled mods")
        fd, tmp = tempfile.mkstemp(suffix=".zip", dir=DATA_DIR)
        os.close(fd)
        try:
            man = {"format": "beammp-easyserver-modpack", "version": 1, "server": I().name, "made": now(),
                   "easy_version": EASY_VERSION, "map": map_name(toml_parse(APP.read_config_text())[0].get("General", {}).get("Map")),
                   "mods": []}
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
                for m in mods:
                    pth = os.path.join(I().CLIENT_DIR if m["enabled"] else I().DISABLED_DIR, m["name"])
                    h = hashlib.sha256()
                    with open(pth, "rb") as f:
                        for chunk in iter(lambda: f.read(1 << 20), b""):
                            h.update(chunk)
                    z.write(pth, "mods/" + m["name"])
                    man["mods"].append({"name": m["name"], "size": m["size"], "sha256": h.hexdigest(), "maps": m["maps"]})
                z.writestr("modpack.json", json.dumps(man, indent=1))
                z.writestr("README.txt", "Modpack from %s (%d mods).\r\n\r\nServer owners: BeamMP EasyServer -> Mods -> Import modpack.\r\n"
                           "Players: you don't need this - BeamMP downloads the mods when you join. To save time on slow internet,\r\n"
                           "copy the files from the mods folder into  Documents\\BeamNG.drive\\mods\\multiplayer  before joining.\r\n"
                           "modpack.json lists every file with its SHA-256 checksum.\r\n" % (I().name, len(mods)))
            size = os.path.getsize(tmp)
            fname = "modpack-%s-%s.zip" % (re.sub(r"[^A-Za-z0-9]+", "-", I().name).strip("-")[:30] or "server", time.strftime("%Y%m%d"))
            self.send_response(200)
            self.headers_common("application/zip", size, {"Content-Disposition": 'attachment; filename="%s"' % fname})
            with open(tmp, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
        finally:
            os.remove(tmp)

    # ---------- backups
    def get_backups(self, q):
        s = APP.settings
        self.send(200, {"on": bool(s.get("backup_on")), "at": s.get("backup_at"), "mods": bool(s.get("backup_mods")),
                        "keep": BACKUP_KEEP, "items": list_backups(I().id), "folder": BACKUP_DIR,
                        "copy": s.get("backup_copy") or "", "copy_path": s.get("backup_copy_path") or "",
                        "copy_ip": s.get("backup_copy_ip") or "", "copy_last": APP.state.get("backup_copy"),
                        "drives": backup_drives(), "copy_dir": BACKUP_COPY_DIR,
                        "computers": [{"ip": x["ip"], "name": x.get("host") or x["ip"]} for x in pi_saved() if pi_key_ok(x)]})

    def post_backups(self, q):
        b = self.body_json()
        upd = {}
        if "on" in b:
            upd["backup_on"] = bool(b["on"])
        if "mods" in b:
            upd["backup_mods"] = bool(b["mods"])
        if "at" in b:
            at = str(b["at"]).strip()
            if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", at):
                return self.fail(400, "Enter the time like 03:30")
            upd["backup_at"] = "%02d:%s" % (int(at.split(":")[0]), at.split(":")[1])
        if "copy" in b:
            kind = b["copy"] if b["copy"] in ("", "folder", "computer") else None
            if kind is None:
                return self.fail(400, "Unknown place for the copies")
            if _TL.user != "owner":
                return self.fail(403, "Only the owner can choose where copies of the backups go.")
            upd["backup_copy"] = kind
            if kind == "folder":
                path = str(b.get("copy_path") or "").strip().strip('"')[:400]
                why = backup_folder_check(path)
                if why:
                    return self.fail(400, why)
                upd["backup_copy_path"] = path
            if kind == "computer":
                ip = str(b.get("copy_ip") or "")
                pi = next((x for x in pi_saved() if x["ip"] == ip), None)
                if pi is None or not pi_key_ok(pi):
                    return self.fail(400, "Pick one of the computers set up under Other computers at home")
                upd["backup_copy_ip"] = ip
        APP.settings.update(upd)
        self.send(200, {"ok": True, "note": "Saved."})

    def post_backups_now(self, q):
        made, errors = APP.run_backups(bool(self.body_json().get("mods")))
        if errors:
            return self.fail(500, "; ".join(errors))
        self.send(200, {"ok": True, "note": "Backed up %d server%s." % (len(made), "" if len(made) == 1 else "s") +
                        (" Copying them to the other place now…" if APP.settings.get("backup_copy") else "") +
                        (" Copying them to Google Drive now…" if APP.settings.get("gdrive_on") and gdrive_connected() else "")})

    # ---------- Google Drive copies and rescue
    def get_gdrive(self, q):
        if self.sess.get("role", "owner") != "owner":      # the sign-in code would let someone link their own Drive
            return self.fail(403, "Only the owner can see the Google Drive settings")
        s = APP.settings
        d = {"ready": gdrive_ready(), "own_app": bool(s.get("gdrive_client_id")), "own_client_id": s.get("gdrive_client_id") or "",
             "connected": gdrive_connected(), "on": bool(s.get("gdrive_on")), "account": s.get("gdrive_account") or "",
             "estimate": gdrive_estimate(), "last": APP.state.get("gdrive_last"), "folder": GDRIVE_FOLDER_NAME,
             "flow": None, "drive": None, "files": [], "error": "", "computer": backup_tag(), "backups_on": bool(s.get("backup_on"))}
        f = _GD["flow"]
        if f and (f["state"] != "waiting" or now() < f["until"]):
            d["flow"] = {k: f[k] for k in ("code", "url", "until", "state", "note")}
        if d["connected"] and q.get("details") == "1":
            try:
                d["drive"] = gdrive_about()
                fs = gdrive_list()
                d["files"] = fs[:60]
                d["used_by_us"] = sum(x["size"] for x in fs)
            except Exception as e:
                d["error"] = str(e) if isinstance(e, RuntimeError) else short_err(e)
        self.send(200, d)

    def post_gdrive(self, q):
        b = self.body_json()
        act = b.get("action")
        try:
            if act == "connect":
                if not gdrive_ready():
                    return self.fail(400, "Google Drive isn't set up in this version yet - use your own Google app (below).")
                f = gdrive_flow_start()
                return self.send(200, {"ok": True, "flow": {k: f[k] for k in ("code", "url", "until", "state", "note")}})
            if act == "cancel":
                _GD["flow"] = None
                return self.send(200, {"ok": True})
            if act == "disconnect":
                gdrive_disconnect()
                return self.send(200, {"ok": True, "note": "Disconnected. The copies already in your Drive stay there."})
            if act == "on":
                if b.get("on") and not gdrive_connected():
                    return self.fail(400, "Connect Google Drive first")
                APP.settings.update({"gdrive_on": bool(b.get("on"))})
                return self.send(200, {"ok": True, "note": "Saved."})
            if act == "now":
                if not gdrive_connected():
                    return self.fail(400, "Connect Google Drive first")
                files = [x["file"] for x in newest_backups()]
                if not files:
                    files, errors = APP.run_backups(bool(APP.settings.get("backup_mods")))
                    if errors:
                        return self.fail(500, "; ".join(errors))
                    if APP.settings.get("gdrive_on"):
                        return self.send(200, {"ok": True, "note": "Made a backup and copying it to Google Drive now…"})
                threading.Thread(target=APP.copy_backups, args=(files, "gdrive"), daemon=True).start()
                return self.send(200, {"ok": True, "note": "Copying the newest backups to Google Drive now…"})
            if act == "own_app":
                cid = str(b.get("client_id") or "").strip()
                if cid and not re.fullmatch(r"[0-9]{6,20}-[a-z0-9]{10,64}\.apps\.googleusercontent\.com", cid):
                    return self.fail(400, "That doesn't look like a Google client ID (it ends in .apps.googleusercontent.com)")
                sec = str(b.get("client_secret") or "").strip()
                if cid and not sec and not APP.secrets.has("GDRIVE_SECRET"):
                    return self.fail(400, "Paste the client secret too")
                if gdrive_connected():
                    gdrive_disconnect()
                if sec or not cid:
                    APP.secrets.set("GDRIVE_SECRET", sec if cid else "")
                APP.settings.update({"gdrive_client_id": cid, "gdrive_folder": ""})
                return self.send(200, {"ok": True, "note": "Saved - now press Connect Google Drive." if cid else "Back to the built-in Google app."})
            if act == "restore":
                if not gdrive_connected():
                    return self.fail(400, "Connect Google Drive first")
                fid = str(b.get("id") or "")
                f = next((x for x in gdrive_list() if x["id"] == fid), None)
                if not f:
                    return self.fail(404, "That backup isn't in the Drive folder any more")
                fd, tmp = tempfile.mkstemp(suffix=".zip", dir=DATA_DIR)
                os.close(fd)
                try:
                    gdrive_download(fid, tmp)
                    try:
                        undo = make_backup(I(), False)
                    except Exception as e:
                        return self.fail(500, "Couldn't save the current settings first, so nothing was restored (%s)" % short_err(e))
                    self._restore_undo = undo
                    return self._import_zip(tmp, {"settings": "1", "mods": "1" if b.get("mods") is True else "0",
                                                  "games": "1"})
                finally:
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
        except GDriveError as e:
            return self.fail(502, str(e))
        self.fail(400, "unknown action")

    def get_backups_download(self, q):
        name = str(q.get("file") or "")
        if not any(x["file"] == name for x in list_backups(I().id)):
            return self.fail(404, "No such backup")
        path = os.path.join(BACKUP_DIR, name)
        size = os.path.getsize(path)
        self.send_response(200)
        self.headers_common("application/zip", size, {"Content-Disposition": 'attachment; filename="%s"' % name})
        with open(path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    # ---------- DuckDNS
    def post_duckdns(self, q):
        app = APP
        b = self.body_json()
        dom = str(b.get("domain") or "").strip().lower()
        dom = re.sub(r"^https?://", "", dom).split("/")[0]
        dom = dom[:-len(".duckdns.org")] if dom.endswith(".duckdns.org") else dom
        tok = str(b.get("token") or "").strip()
        if not dom:
            app.settings.update({"duckdns_domain": ""})
            app.secrets.set("DUCKDNS_TOKEN", "")
            return self.send(200, {"ok": True, "note": "DuckDNS is off."})
        if not DUCK_RE.fullmatch(dom):
            return self.fail(400, "Enter just your DuckDNS name, like myserver (from myserver.duckdns.org)")
        if tok and not re.fullmatch(r"[0-9a-fA-F-]{36}", tok):
            return self.fail(400, "The token is the long code at the top of duckdns.org after you sign in")
        tok = tok or app.secrets.get("DUCKDNS_TOKEN")
        if not tok:
            return self.fail(400, "Paste your DuckDNS token")
        try:
            ok = duckdns_update(dom, tok)
        except Exception as e:
            return self.fail(400, "Couldn't reach duckdns.org (%s)" % short_err(e))
        if not ok:
            return self.fail(400, "DuckDNS refused it - check that the name is yours and the token is right")
        app.settings.update({"duckdns_domain": dom})
        if tok != app.secrets.get("DUCKDNS_TOKEN"):
            app.secrets.set("DUCKDNS_TOKEN", tok)
        app.state.update({"duck_ip": public_ip(), "duck_t": now(), "duck_next": now() + 300, "duck_err": ""})
        app.save_state()
        self.send(200, {"ok": True, "note": "Done - friends can now join at %s.duckdns.org:%s" % (dom, I().port() or 30814)})

    # ---------- computer load
    def get_resources(self, q):
        app = APP
        hist = getattr(app, "res_hist", [])
        rng = q.get("range")
        series = None
        if rng in ("day", "week"):
            cut = now() - (86400 if rng == "day" else 7 * 86400)
            series = perf_series([x for x in hist if x["t"] >= cut], 300 if rng == "day" else 1800)
        self.send(200, {"now": getattr(app, "res", None), "history": hist[-min(1440, int(q.get("n") or 60)):], "series": series,
                        "upload_mbit": app.settings.get("upload_mbit") or 0, "cpus": os.cpu_count() or 1})

    def post_resources(self, q):
        try:
            v = float(self.body_json().get("upload_mbit") or 0)
            assert 0 <= v <= 100000
        except (TypeError, ValueError, AssertionError):
            return self.fail(400, "Enter your upload speed in Mbit/s, like 20")
        APP.settings.update({"upload_mbit": round(v, 1)})
        self.send(200, {"ok": True, "note": "Saved."})

    # ---------- all computers on one page
    def get_machines(self, q):
        job = dict(_PI["job"]) if _PI["job"] else None
        if job:
            job["password"] = ""
        self.send(200, {"here": {"host": socket.gethostname()[:40], "version": EASY_VERSION, "servers": remote_snapshot(),
                                 "ip": pi_lan_ip()},
                        "machines": pi_overview(), "job": job})

    def post_machines(self, q):
        b = self.body_json()
        act = b.get("action")
        ip = str(b.get("ip") or "")
        pi = next((x for x in pi_saved() if x["ip"] == ip), None)
        if pi is None:
            return self.fail(404, "That computer isn't set up here")
        if not pi_can_remote(pi):
            return self.fail(400, "This dashboard can't control that computer yet - update EasyServer on it first.")
        if act in ("start", "stop", "restart"):
            try:
                pi_remote_send(pi, act)
            except RuntimeError as e:
                return self.fail(502, str(e))
            _PI.pop("overview", None)
            return self.send(200, {"ok": True, "note": "Sent. It does it within 10 seconds."})
        if act == "move":
            if _TL.user != "owner":
                return self.fail(403, "Only the owner can move the server.")
            if _PI["job"] and _PI["job"]["state"] == "running":
                return self.fail(409, "Wait until the other job is done")
            st = next((x["remote"] for x in pi_overview() if x["ip"] == ip), {})
            if st.get("error") == "old":
                return self.fail(400, "Update EasyServer on that computer first (the Update button), then move the server.")
            if st.get("error"):
                return self.fail(400, "Can't reach EasyServer on that computer right now.")
            pi_move_job(pi, I().id, bool(b.get("stop_here", True)))
            return self.send(200, {"ok": True})
        return self.fail(400, "Unknown action")

    # ---------- Raspberry Pi on the same network
    def get_pi(self, q):
        job = dict(_PI["job"]) if _PI["job"] else None
        if job and _TL.user != "owner":
            job["password"] = ""
        self.send(200, {"pis": pi_status(), "scan": _PI["scan"], "scanning": _PI["scanning"], "job": job,
                        "ssh": bool(pi_ssh_exe()), "me": pi_lan_ip(), "card": IS_WIN, **pi_here()})

    def post_pi(self, q):
        b = self.body_json()
        act = b.get("action")
        if act == "scan":
            if not _PI["scanning"]:
                _PI["scanning"] = True

                def scan():
                    try:
                        _PI["scan"] = pi_scan()
                    except Exception as e:
                        _PI["scan"] = {"t": now(), "found": [], "error": "Looking for it failed: " + short_err(e)}
                    finally:
                        _PI["scanning"] = False
                threading.Thread(target=scan, daemon=True, name="pi-scan").start()
            return self.send(200, {"ok": True})
        if act == "disks":
            return self.send(200, {"disks": pi_disks()})
        if act == "card":
            return self.pi_card(b)
        ip = str(b.get("ip") or "").strip()
        if not pi_private(ip):
            return self.fail(400, "Enter the computer's address on your network, like 192.168.0.23")
        if act == "forget":
            with _PI_LOCK:
                pi_store([x for x in pi_saved() if x["ip"] != ip])
            return self.send(200, {"ok": True, "note": "Forgotten. EasyServer stays on that computer."})
        if act not in ("install", "update", "password"):
            return self.fail(400, "Unknown action")
        if _PI["job"] and _PI["job"]["state"] == "running":
            return self.fail(409, "Wait until the computer that's being set up is done")
        pi = next((x for x in pi_saved() if x["ip"] == ip), None)
        try:
            if act == "install" and (pi is None or b.get("password")):
                user = str(b.get("user") or "").strip()
                if not PI_USER_RE.fullmatch(user):
                    return self.fail(400, "Enter the computer's user name (like pi)")
                if not b.get("password"):
                    return self.fail(400, "Enter the computer's password")
                pi = pi_pair(ip, user, str(b["password"])[:200])
            if pi is None:
                return self.fail(404, "Set up this computer first")
            if pi_problem(pi):
                return self.fail(400, pi_problem(pi))
            if act == "password":
                if pi.get("os") == "windows":
                    return self.fail(400, "Windows keeps it locked to that PC's login, so it can't be shown from here. Forgot it? "
                                          "Run Reset-Dashboard-Login.bat in the BeamMP server folder on that PC.")
                if not pi.get("sudo"):
                    return self.fail(400, "Look it up on the Raspberry Pi with: beammp dashboard")
                code, out = pi_ssh(pi, "%s/usr/local/lib/beammp-easyserver/secrets.sh get MODS_PASSWORD"
                                   % ("" if pi.get("root") else "sudo -n "), timeout=30)
                pw = out.strip().splitlines()[-1] if code == 0 and out.strip() else ""
                if not re.fullmatch(r"\S{4,64}", pw):
                    return self.fail(502, "Couldn't read it - is EasyServer installed on it?" if code != 255 else pi_ssh_error(out))
                return self.send(200, {"ok": True, "password": pw})
            sudo_pw = str(b.get("password") or "")[:200] or None
            if pi.get("os") == "windows" and act == "install" and not sudo_pw:
                return self.fail(400, "Enter the password of that PC's Windows account")
            if not pi.get("sudo") and not pi.get("root") and not sudo_pw:
                return self.fail(400, "This computer asks for its password for system changes - enter it")
            name = re.sub(r"[\x00-\x1f\"]", "", str(b.get("name") or "")).strip()[:60]
            pi_job(act, pi, name=name, sudo_pw=sudo_pw)
        except RuntimeError as e:
            return self.fail(502, str(e))
        except (OSError, subprocess.SubprocessError) as e:
            return self.fail(502, "Couldn't connect: " + short_err(e))
        self.send(200, {"ok": True, "note": "Installing EasyServer…" if act == "install" else "Updating…"})

    def pi_card(self, b):
        if not IS_WIN:
            return self.fail(400, "Making the card from here works on Windows. Use Raspberry Pi Imager - the steps are on this page.")
        if _PI["job"] and _PI["job"]["state"] == "running":
            return self.fail(409, "Wait until the computer that's being set up is done")
        user = str(b.get("user") or "").strip()
        if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user) or user in ("root", "daemon", "bin", "sys", "nobody"):
            return self.fail(400, "Pick a user name for the Raspberry Pi: small letters and numbers, like beammp")
        pw = str(b.get("password") or "")
        if len(pw) < 8 or len(pw) > 128:
            return self.fail(400, "Pick a password for the Raspberry Pi: at least 8 characters")
        ssid, wpw = str(b.get("ssid") or "").strip(), str(b.get("wifi_password") or "")
        if ssid and not PI_WIFI_RE.fullmatch(ssid):
            return self.fail(400, "That Wi-Fi name is too long")
        if ssid and wpw and not 8 <= len(wpw) <= 63:
            return self.fail(400, "A Wi-Fi password is 8 to 63 characters - check it")
        country = str(b.get("country") or "").strip().upper()
        if ssid and not PI_COUNTRY_RE.fullmatch(country):
            return self.fail(400, "Pick the country you're in (the Wi-Fi rules depend on it)")
        if not b.get("erase_ok"):
            return self.fail(400, "Tick that everything on the card may be erased")
        disk = next((d for d in pi_disks() if d["n"] == b.get("disk")), None)
        if not disk:
            return self.fail(400, "That card isn't there any more - press Look for cards")
        name = re.sub(r"[\x00-\x1f\"]", "", str(b.get("name") or "")).strip()[:60]
        host = "beammp-pi-" + secrets.token_hex(2)
        pi_card_job({"user": user, "pw_hash": sha512_crypt(pw), "ssid": ssid, "psk": pi_psk(ssid, wpw) if ssid and wpw else "",
                     "country": country, "disk": disk, "name": name, "host": host})
        self.send(200, {"ok": True, "note": "Making the card…"})

    # ---------- mod updates
    def get_mods_updates(self, q):
        ups = (getattr(APP, "mod_updates", {}) or {}).get(I().id)
        self.send(200, {"checked": APP.state.get("modupd_t"), "on": bool(APP.settings.get("mod_update_check")),
                        "auto": bool(APP.settings.get("mod_auto_update")), "mods": ups if ups is not None else {}})

    def post_mods_updates(self, q):
        b = self.body_json()
        if "on" in b:
            APP.settings.update({"mod_update_check": bool(b["on"])})
            return self.send(200, {"ok": True})
        if "auto" in b:
            APP.settings.update({"mod_auto_update": bool(b["auto"])})
            return self.send(200, {"ok": True, "note": "Saved - updates are installed by themselves while nobody is playing, and a running "
                                                       "server is restarted for them." if b["auto"] else "Saved."})
        if now() - getattr(APP, "modupd_manual", 0) < 30:
            return self.fail(429, "Just checked - try again in a moment")
        APP.modupd_manual = now()
        found = APP.run_mod_check(True).get(I().id, {})
        n = sum(1 for u in found.values() if u["update"])
        self.send(200, {"ok": True, "mods": found,
                        "note": ("%d update%s available." % (n, "" if n == 1 else "s")) if n else
                                ("All %d repository mods are up to date." % len(found) if found else
                                 "None of your mods come from the BeamNG repository, so they can't be checked.")})

    def post_mods_update(self, q):
        """Download the newest version of a repository mod, virus-check it and replace the old file."""
        name = safe_zip_name(self.body_json().get("name"))
        ups = (getattr(APP, "mod_updates", {}) or {}).get(I().id) or {}
        u = ups.get(name or "")
        if not u or not u.get("update"):
            return self.fail(400, "No update known for this mod - press Check for updates first")
        st, r = apply_mod_update(name, u)
        if st != 200:
            return self.send(st, r) if r.get("blocked") else self.fail(st, r["error"])
        refresh_mod_desc()
        APP.config_changed()
        self.send(200, {"ok": True, "note": "Updated %s to %s. %s" % (name, r["version"] or "the newest version", APP.applied_note())})

    def post_mods_updateall(self, q):
        """Every repository mod that has an update, one after the other."""
        ups = (getattr(APP, "mod_updates", {}) or {}).get(I().id) or {}
        todo = [n for n, u in sorted(ups.items()) if u.get("update")]
        if not todo:
            return self.fail(400, "No updates known - press Check for updates first")
        done, failed = update_mods(todo, ups)
        if done:
            refresh_mod_desc()
            APP.config_changed()
        note = ("Updated %d mod%s. %s" % (len(done), "" if len(done) == 1 else "s", APP.applied_note())) if done else ""
        if failed:
            note += (" " if note else "") + " ".join("%s: %s" % (n, e) for n, e in failed[:5])
        self.send(200 if done else 502, {"ok": bool(done), "note": note, "error": note, "done": done,
                                         "failed": [{"name": n, "error": e} for n, e in failed]})

    # ---------- mod browser
    def get_modbrowser(self, q):
        cat = q.get("cat") or REPO_CATS[0][0]
        if cat not in dict(REPO_CATS):
            return self.fail(400, "unknown category")
        order = q.get("order") if q.get("order") in REPO_ORDERS else "download_count"
        text = (q.get("q") or "").strip()[:100]
        try:
            page = max(1, min(50, int(q.get("page") or 1)))
        except ValueError:
            page = 1
        items, more, err = [], False, None
        try:
            rid = repo_id_from(text) or (int(text) if text.isdigit() and len(text) <= 7 else None)
            if rid:
                items = [repo_mod_page(rid)]
            elif text:
                words = [w.lower() for w in re.findall(r"\w+", text)]
                pages = range((page - 1) * 5 + 1, page * 5 + 1)    # search 5 list pages (100 mods) at a time
                for n in pages:
                    lst = parse_repo_list(_repo_get(REPO_SITE + "resources/categories/%s/?order=%s&page=%d" % (cat, order, n)))
                    for it in lst:
                        hay = ("%s %s %s" % (it["title"], it["tagline"], it["author"])).lower()
                        if all(w in hay for w in words):
                            items.append(it)
                    more = len(lst) >= 20
                    if not more:
                        break
            else:
                items = parse_repo_list(_repo_get(REPO_SITE + "resources/categories/%s/?order=%s&page=%d" % (cat, order, page)))
                more = len(items) >= 20
        except Exception as e:
            err = "Couldn't load the mod list from beamng.com: %s" % (str(e) if isinstance(e, RuntimeError) else short_err(e))
        have = installed_repo_ids()
        for it in items:
            it["installed"] = have.get(it["id"])
        self.send(200, {"items": items, "more": more, "page": page, "error": err, "cats": REPO_CATS,
                        "orders": REPO_ORDERS, "cat": cat, "order": order,
                        "jobs": [j for j in MODB_JOBS.values() if j["server"] == I().id and not j.get("seen")]})

    def get_modbrowser_icon(self, q):
        try:
            rid = int(q.get("id") or 0)
        except ValueError:
            rid = 0
        if not 0 < rid < 10 ** 7:
            return self.fail(400, "bad id")
        path = os.path.join(REPO_ICON_DIR, "%d.jpg" % rid)
        body = None
        try:
            if time.time() - os.path.getmtime(path) < 7 * 86400:
                with open(path, "rb") as f:
                    body = f.read()
        except OSError:
            pass
        if body is None:
            try:
                req = urllib.request.Request(REPO_SITE + "data/resource_icons/%d/%d.jpg" % (rid // 1000, rid),
                                             headers={"User-Agent": "BeamMP-EasyServer/%s (mod browser)" % EASY_VERSION})
                with urllib.request.urlopen(req, timeout=15) as r:
                    body = r.read(300 * 1024 + 1)
                if len(body) > 300 * 1024 or body[:3] not in (b"\xff\xd8\xff", b"\x89PN"):
                    body = b""
            except Exception:
                body = b""
            try:
                os.makedirs(REPO_ICON_DIR, exist_ok=True)
                with open(path, "wb") as f:
                    f.write(body)
            except OSError:
                pass
        if not body:
            return self.send(404, b"", "image/jpeg", {"Cache-Control": "max-age=86400"})
        self.send(200, body, "image/png" if body[:3] == b"\x89PN" else "image/jpeg", {"Cache-Control": "max-age=604800"})

    def post_modbrowser_install(self, q):
        try:
            rid = int(self.body_json().get("id") or 0)
        except (TypeError, ValueError):
            rid = 0
        if not 0 < rid < 10 ** 7:
            return self.fail(400, "bad mod id")
        with LOCK:
            busy = [j for j in MODB_JOBS.values() if not j.get("finished")]
            if len(busy) >= 3:
                return self.fail(429, "Three downloads are already running - wait for one to finish")
            if any(j["id"] == rid and j["server"] == I().id for j in busy):
                return self.fail(409, "That mod is already downloading")
            for k in [k for k, j in MODB_JOBS.items() if j.get("finished") and now() - j["t"] > 3600]:
                MODB_JOBS.pop(k, None)
            jid = secrets.token_hex(6)
            job = {"job": jid, "id": rid, "server": I().id, "t": now(), "state": "Starting…", "done": 0, "total": 0,
                   "finished": False, "name": "", "title": str(self.body_json().get("title") or "")[:120]}
            MODB_JOBS[jid] = job
        threading.Thread(target=modb_install, args=(job, I().id, rid), daemon=True).start()
        self.send(200, {"ok": True, "job": jid})

    def get_modbrowser_job(self, q):
        j = MODB_JOBS.get(q.get("job") or "")
        if not j or j["server"] != I().id:
            return self.fail(404, "no such download")
        if j.get("finished"):
            j["seen"] = True
        self.send(200, j)

    # ---------- phone app
    def get_phoneapp(self, q):
        """The link the Android app opens (via a QR code) to connect to this dashboard."""
        st = APP.settings
        https_ = bool(st.get("https"))
        hosts = []
        if duck_host() and st.get("remote_enabled"):
            hosts.append(duck_host())
        hosts.append(lan_ip())
        base = "%s://%s:%s/" % ("https" if https_ else "http", hosts[-1], st.get("port"))
        fp = cert_sha256() if https_ else ""
        args = {"url": base, "fp": fp}
        mac, brd, _ = wol_target()
        if mac:                                  # the app can wake the computer up when it's asleep
            args.update({"mac": mac, "bc": ",".join(brd)})
        if APP.secrets.has("WAKE_TOPIC"):
            args.update({"wt": APP.secrets.get("WAKE_TOPIC"), "ns": (st.get("ntfy_server") or "https://ntfy.sh").rstrip("/")})
        link = "easyserver://connect?" + urllib.parse.urlencode(args)
        self.send(200, {"https": https_, "url": base, "fingerprint": fp, "link": link, "qr": qr_svg_path(link),
                        "apk": "https://github.com/%s/releases/latest" % REPO})

    # ---------- phone push (ntfy)
    def get_ntfy(self, q):
        s, topic = APP.settings, APP.secrets.get("NTFY_TOPIC")
        server = (s.get("ntfy_server") or "https://ntfy.sh").rstrip("/")
        host = re.sub(r"^https?://", "", server)
        self.send(200, {"enabled": bool(s.get("ntfy_enabled")), "server": server, "has_topic": bool(topic),
                        "subscribe": ("%s/%s" % (server, topic)) if topic else None,
                        "app_link": ("ntfy://%s/%s" % (host, topic)) if topic else None,
                        "qr": qr_svg_path("%s/%s" % (server, topic)) if topic else None})

    def post_ntfy(self, q):
        app = APP
        b = self.body_json()
        upd = {}
        if b.get("new_topic") or (b.get("enabled") and not app.secrets.has("NTFY_TOPIC")):
            app.secrets.set("NTFY_TOPIC", "beammp-" + secrets.token_urlsafe(18).replace("-", "x").replace("_", "y"))
        if "server" in b:
            srv = str(b["server"] or "").strip().rstrip("/") or "https://ntfy.sh"
            if not re.fullmatch(r"https://[A-Za-z0-9.\-]{1,253}(:\d{1,5})?", srv):
                return self.fail(400, "The ntfy server must be an https:// address, like https://ntfy.sh")
            upd["ntfy_server"] = srv
        if "enabled" in b:
            upd["ntfy_enabled"] = bool(b["enabled"])
        if upd:
            app.settings.update(upd)
        if b.get("test"):
            try:
                ntfy_send("Test notification", "Your BeamMP dashboard can send notifications to this phone.", "success",
                          dashboard_url())
            except Exception as e:
                return self.fail(400, "Couldn't send it: %s" % short_err(e))
        self.send(200, {"ok": True})

    # ---------- sleep + Wake-on-LAN
    def get_power(self, q):
        app, s = APP, APP.settings
        st = power_status(force=q.get("refresh") == "1")
        mac, brd, ip = wol_target()
        t = now()
        idle_min = int(s.get("sleep_idle") or 30)
        why = app.sleep_busy_why if s.get("sleep_on") else ""
        sleeps_at = 0
        if s.get("sleep_on") and not why:
            sleeps_at = app.idle_since + idle_min * 60
        self.send(200, {
            "platform": "windows" if IS_WIN else "linux",
            "settings": {k: s.get(k) for k in ("sleep_on", "sleep_idle", "sleep_from", "sleep_to", "sleep_wake_at",
                                               "sleep_wake_events")},
            "adapters": st.get("adapters") or [], "main": st.get("main") or "", "on_wifi": bool(st.get("on_wifi")),
            "can_sleep": bool(st.get("can_sleep")), "rtc": bool(st.get("rtc")), "error": st.get("msg") if not st.get("ok") else "",
            "mac": mac, "brd": brd, "ip": ip, "busy": why, "idle_for": max(0, t - app.idle_since),
            "sleeps_at": sleeps_at, "in_window": in_time_window(s.get("sleep_from"), s.get("sleep_to"), t),
            "next_wake": next_wake_at(), "slept_at": app.state.get("slept_at") or 0, "woke_at": app.state.get("woke_at") or 0,
            "wol_score": wol_score(st),
            "helper": {"paired": app.secrets.has("WAKE_TOPIC"), "last_seen": app.state.get("helper_seen") or 0,
                       "version": app.state.get("helper_version") or "", "bot": bool(s.get("discord_bot"))},
            "ntfy_server": (s.get("ntfy_server") or "https://ntfy.sh").rstrip("/"),
        })

    def post_power(self, q):
        b = self.body_json()
        upd = {}
        if "sleep_on" in b:
            upd["sleep_on"] = bool(b["sleep_on"])
            if upd["sleep_on"] and not APP.settings.get("sleep_on"):
                APP.idle_since = now()          # count from now, don't fall asleep right away
        if "sleep_idle" in b:
            try:
                v = int(b["sleep_idle"])
            except (TypeError, ValueError):
                raise ValueError("Pick how many minutes")
            if not 5 <= v <= 1440:
                raise ValueError("Pick between 5 minutes and 24 hours")
            upd["sleep_idle"] = v
        for k in ("sleep_from", "sleep_to", "sleep_wake_at"):
            if k in b:
                v = str(b[k] or "").strip()
                if v and not HHMM_RE.fullmatch(v):
                    raise ValueError("Times look like 23:30")
                upd[k] = v
        if bool(upd.get("sleep_from", APP.settings.get("sleep_from"))) != bool(upd.get("sleep_to", APP.settings.get("sleep_to"))):
            raise ValueError("Fill in both times (from and until), or leave both empty")
        if "sleep_wake_events" in b:
            upd["sleep_wake_events"] = bool(b["sleep_wake_events"])
        if upd:
            APP.settings.update(upd)
        self.send(200, {"ok": True})

    def post_power_wol(self, q):
        """Turn Wake-on-LAN on for the network cable adapter."""
        name = str(self.body_json().get("adapter") or "")
        st = power_status(force=True)
        a = next((x for x in st.get("adapters") or [] if x.get("name") == name), None)
        if not a:
            return self.fail(400, "That network adapter wasn't found - press Refresh")
        if a.get("wifi"):
            return self.fail(400, "Wake-on-LAN doesn't work over Wi-Fi. Connect the computer with a network cable.")
        if IS_WIN:
            n = name.replace("'", "''")
            cmd = ("$n='%s'; Set-NetAdapterPowerManagement -Name $n -WakeOnMagicPacket Enabled -ErrorAction SilentlyContinue;"
                   "Set-NetAdapterAdvancedProperty -Name $n -RegistryKeyword '*WakeOnMagicPacket' -RegistryValue 1 -ErrorAction SilentlyContinue;"
                   "$d=(Get-NetAdapter -Name $n).InterfaceDescription; powercfg /deviceenablewake \"$d\";"
                   "powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP RTCWAKE 1; powercfg /setactive SCHEME_CURRENT" % n)
            enc = base64.b64encode(cmd.encode("utf-16-le")).decode()
            subprocess.Popen(["powershell.exe", "-NoProfile", "-Command",
                              "Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList '-NoProfile','-EncodedCommand','%s'" % enc],
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            with LOCK:
                _POWER["t"] = 0
            return self.send(200, {"ok": True, "msg": "Windows asks for permission on the server PC - click Yes there, then press Refresh."})
        r = control("wol-enable", iface=name, timeout=330)
        with LOCK:
            _POWER["t"] = 0
        if not r.get("ok"):
            return self.fail(400, r.get("msg") or "Couldn't turn on Wake-on-LAN")
        APP.notifier.add("network", "Wake-on-LAN turned on", "Adapter %s (%s)." % (name, a.get("mac")), "success", send=False)
        self.send(200, {"ok": True, "msg": r.get("msg")})

    def post_power_sleep(self, q):
        app = APP
        why = app.sleep_blockers()
        if why and why != "the dashboard is being used" and not self.body_json().get("force"):
            return self.send(409, {"ok": False, "error": "Not now: %s." % why, "busy": why})
        if not power_status().get("can_sleep"):
            return self.fail(400, "This computer can't go to sleep")
        r = app.go_sleep("Sent to sleep from the dashboard.", delay=4)
        if not r.get("ok"):
            return self.fail(400, r.get("msg"))
        self.send(200, r)

    # ---------- users + activity log
    def get_users(self, q):
        self.send(200, {"users": [dict({k: u.get(k) for k in ("name", "role", "created", "last_login", "disabled", "remote")},
                                       servers=u.get("servers") if isinstance(u.get("servers"), dict) else "all",
                                       totp=bool(u.get("totp")), invited_by=u.get("invited_by"),
                                       discord=(u.get("discord") or {}).get("name"))
                                  for u in load_users()],
                        "roles": ["admin", "moderator", "viewer"], "custom_roles": load_roles(),
                        "perm_groups": [{"id": g[0], "name": g[1], "about": g[2]} for g in PERM_GROUPS],
                        "servers": [{"id": i.id, "name": i.name} for i in sorted(INSTANCES.values(), key=lambda i: (i.id != "main", i.id))],
                        "invites": [{k: x.get(k) for k in ("id", "role", "servers", "remote", "created", "expires", "note")} for x in load_invites()],
                        "remote_enabled": bool(APP.settings.get("remote_enabled")),
                        "discord_login": {"available": dlogin_available(), "on": dlogin_conf() is not None}})

    def post_discordlogin(self, q):
        dlogin_set(bool(self.body_json().get("on")))
        self.send(200, {"ok": True, "on": dlogin_conf() is not None})

    def post_users(self, q):
        b = self.body_json()
        act, name = b.get("action"), str(b.get("name") or "").strip()
        if not USER_RE.fullmatch(name) or name.lower() == "owner":
            raise ValueError("Names are 2-24 letters, numbers, dots, dashes or underscores (and not 'owner')")
        users = load_users()
        u = next((x for x in users if x["name"].lower() == name.lower()), None)
        role = b.get("role")
        kick = False
        if act == "add":
            if u:
                raise ValueError("That name is taken")
            if len(users) >= 50:
                raise ValueError("At most 50 accounts")
            check_role_exists(role)
            pw = str(b.get("password") or "")
            if len(pw) < 10:
                raise ValueError("Use a password with at least 10 characters")
            nu = {"name": name, "role": role, "pw": hash_password(pw), "created": now(), "last_login": 0}
            sv = clean_servers_map(b.get("servers"))
            if sv:
                nu["servers"] = sv
            users.append(nu)
        elif not u:
            raise ValueError("No such account")
        elif act == "role":
            check_role_exists(role)
            u["role"] = role
        elif act == "servers":
            sv = clean_servers_map(b.get("servers"))
            for r in (sv or {}).values():
                check_role_exists(r)
            if sv:
                u["servers"] = sv
            else:
                u.pop("servers", None)
        elif act == "remote":
            if b.get("remote") and on_mac():
                raise ValueError(MAC_NO_REMOTE)
            u["remote"] = bool(b.get("remote"))
            kick = not u["remote"]
        elif act == "reset_2fa":
            u.pop("totp", None)
            kick = True
        elif act == "discord_unlink":
            u.pop("discord", None)
            kick = True
        elif act == "password":
            pw = str(b.get("password") or "")
            if len(pw) < 10:
                raise ValueError("Use a password with at least 10 characters")
            u["pw"] = hash_password(pw)
            kick = True
        elif act == "disable":
            u["disabled"] = not u.get("disabled")
        elif act == "delete":
            users = [x for x in users if x is not u]
            kick = True
        else:
            raise ValueError("unknown action")
        save_users(users)
        if kick:                                 # log them out everywhere
            with LOCK:
                APP.sessions = {k: v for k, v in APP.sessions.items() if v.get("user", "").lower() != name.lower()}
            forget_devices(name)
        note = "Saved"
        if act == "remote" and u.get("remote"):
            note = ("Saved. %s can log in from the internet once two-step login is set up on their account%s." %
                    (name, "" if u.get("totp") else " (they do that under My account, at home)"))
            if not APP.settings.get("remote_enabled"):
                note += " Internet access to the dashboard is off - turn it on under Settings first."
        self.send(200, {"ok": True, "note": note})

    # ---------- custom roles
    def post_roles(self, q):
        b = self.body_json()
        act = b.get("action")
        with _TEAM_LOCK:
            roles = load_roles()
            if act == "save":
                rid = str(b.get("id") or "")
                name = clean_msg(b.get("name"))[:40].strip()
                perms = [p for p in (b.get("perms") or []) if p in PERM_IDS]
                if not name:
                    raise ValueError("Give the role a name")
                if name.lower() in ("owner", "admin", "moderator", "viewer"):
                    raise ValueError("That name is used by a built-in role")
                if rid:
                    r = next((x for x in roles if x["id"] == rid), None)
                    if not r:
                        raise ValueError("No such role")
                    r.update(name=name, perms=perms)
                else:
                    if len(roles) >= 20:
                        raise ValueError("At most 20 custom roles")
                    rid = "c_" + secrets.token_hex(4)
                    roles.append({"id": rid, "name": name, "perms": perms})
            elif act == "delete":
                rid = str(b.get("id") or "")
                used = [u["name"] for u in load_users() if u.get("role") == rid or rid in (u.get("servers") or {}).values()]
                used += ["an invite"] if any(x.get("role") == rid or rid in (x.get("servers") or {}).values() for x in load_invites()) else []
                if used:
                    raise ValueError("Still in use by: %s. Give them another role first." % ", ".join(used[:5]))
                roles = [x for x in roles if x["id"] != rid]
            else:
                raise ValueError("unknown action")
            save_roles(roles)
        self.send(200, {"ok": True, "id": rid})

    # ---------- invite links for the team
    def post_teaminvite(self, q):
        b = self.body_json()
        if b.get("action") == "revoke":
            with _TEAM_LOCK:
                items = [x for x in load_invites() if x.get("id") != str(b.get("id") or "")]
                save_invites(items)
            return self.send(200, {"ok": True})
        if b.get("remote") and on_mac():
            raise ValueError(MAC_NO_REMOTE)
        role = b.get("role")
        check_role_exists(role)
        sv = clean_servers_map(b.get("servers"))
        for r in (sv or {}).values():
            check_role_exists(r)
        try:
            hours = max(1, min(72, int(b.get("hours") or INVITE_HOURS)))
        except (TypeError, ValueError):
            hours = INVITE_HOURS
        tok = secrets.token_urlsafe(32)
        inv = {"id": secrets.token_hex(4), "hash": invite_hash(tok), "role": role, "servers": sv, "remote": bool(b.get("remote")),
               "created": now(), "expires": now() + hours * 3600, "by": self.sess.get("user", "owner"),
               "note": clean_msg(b.get("note"))[:60]}
        with _TEAM_LOCK:
            items = load_invites()
            if len(items) >= 20:
                raise ValueError("At most 20 open invites - revoke an old one")
            items.append(inv)
            save_invites(items)
        st = APP.settings
        lan = "%s://%s:%s/#team=%s" % ("https" if st.get("https") else "http", lan_ip(), st.get("port"), tok)
        net = (dashboard_url().split("?")[0].rstrip("/") + "/#team=" + tok) if st.get("remote_enabled") else ""
        self.send(200, {"ok": True, "link": net if inv["remote"] and net else lan, "lan_link": lan, "internet_link": net,
                        "expires": inv["expires"],
                        "note": "Send the link to them now. It works once and stops working in %d hour%s." % (hours, "" if hours == 1 else "s")})

    def _invite_or_fail(self, tok):
        if APP.is_locked(self.ip):
            self.fail(429, "Too many wrong attempts. Try again in 15 minutes.")
            return None
        inv = find_invite(tok)
        if not inv:
            time.sleep(0.5)
            APP.login_failed(self.ip)
            self.fail(404, "This invite link doesn't work any more (used, revoked or expired). Ask for a new one.")
            return None
        if ip_is_remote(self.ip) and not inv.get("remote"):
            self.fail(403, "This invite only works on the server's home network.")
            return None
        return inv

    _INVITE_TOTP = {}

    def api_teaminvite_info(self, q):
        inv = self._invite_or_fail(q.get("t"))
        if not inv:
            return
        names = {r["id"]: r["name"] for r in load_roles()}
        out = {"role": names.get(inv["role"], inv["role"]), "remote": inv["remote"], "server": server_name() or "BeamMP server",
               "servers": None if not inv.get("servers") else [INSTANCES[s].name for s in inv["servers"] if s in INSTANCES]}
        if inv["remote"]:                        # internet access needs two-step login from the start
            secret, pub = new_totp("team")
            with LOCK:
                Handler._INVITE_TOTP[inv["hash"]] = (secret, now())
                for k in [k for k, v in Handler._INVITE_TOTP.items() if now() - v[1] > 3600]:
                    Handler._INVITE_TOTP.pop(k, None)
            out["totp"] = pub
        self.send(200, out)

    def api_teaminvite_accept(self, q):
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlparse(origin).netloc != self.headers.get("Host", ""):
            return self.fail(403, "Security check failed - open the link again")
        b = self.body_json(4096)
        inv = self._invite_or_fail(b.get("t"))
        if not inv:
            return
        name, pw = str(b.get("name") or "").strip(), str(b.get("password") or "")
        if not USER_RE.fullmatch(name) or name.lower() == "owner":
            return self.fail(400, "Names are 2-24 letters, numbers, dots, dashes or underscores")
        if len(pw) < 10:
            return self.fail(400, "Use a password with at least 10 characters")
        totp = ""
        if inv["remote"]:
            with LOCK:
                pend = Handler._INVITE_TOTP.get(inv["hash"])
            if not pend or not totp_matches(pend[0], b.get("code")):
                return self.fail(400, "That two-step code is wrong - check the time on your phone and try again")
            totp = pend[0]
        with _TEAM_LOCK:
            if not find_invite(b.get("t")):
                return self.fail(404, "This invite link was just used")
            users = load_users()
            if any(x["name"].lower() == name.lower() for x in users):
                return self.fail(400, "That name is taken - pick another")
            if len(users) >= 50:
                return self.fail(400, "This dashboard has the most accounts it can have")
            nu = {"name": name, "role": inv["role"], "pw": hash_password(pw), "created": now(), "last_login": 0,
                  "remote": inv["remote"], "invited_by": inv.get("by")}
            if inv.get("servers"):
                nu["servers"] = inv["servers"]
            if totp:
                nu["totp"] = _seal(totp)
            users.append(nu)
            save_users(users)
            items = load_invites()
            for x in items:
                if x["hash"] == inv["hash"]:
                    x["used"] = now()
            save_invites([x for x in items if not x.get("used")])
        with LOCK:
            Handler._INVITE_TOTP.pop(inv["hash"], None)
        activity(name, "Joined the team with an invite (%s)" % inv["role"], "dashboard", self.ip, "main")
        APP.notifier.add("team", "%s joined the dashboard team" % name, "They used an invite link and can now log in.", "info")
        self.send(200, {"ok": True})

    # ---------- Sign in with Discord (team accounts)
    _DLOGIN_PENDING = {}            # nonce -> {"mode", "user", "ret", "exp"}

    def session_discord_on(self):
        return dlogin_available() and dlogin_conf() is not None

    def own_return_address(self):
        """This dashboard's own address as the browser uses it - only one this computer really has, so
        nobody can have the sign-in sent to a site of their own."""
        hdr = (self.headers.get("Host") or "").strip()
        host = host_name(hdr)
        if not re.fullmatch(r"[A-Za-z0-9.\-]+(:\d{1,5})?|\[[0-9a-fA-F:.]+\](:\d{1,5})?", hdr):
            return None
        port = hdr.rsplit(":", 1)[1] if re.search(r":\d{1,5}$", hdr) else ("443" if self.https else "80")
        if port != str(APP.settings.get("port")):
            return None
        mine = {"localhost", "127.0.0.1", "::1", mac_lan_ip(), duck_host()} | set(tlsgen.local_ips())
        if APP.settings.get("remote_enabled"):
            mine.add(public_ip())
        if not host or host not in {str(x).lower() for x in mine if x}:
            return None
        return "%s://%s/" % ("https" if self.https else "http", hdr.lower())

    def _dlogin_begin(self, mode, user=None):
        conf = dlogin_conf() if dlogin_available() else None
        if not conf:
            raise ValueError("Discord sign-in is off on this dashboard")
        ret = self.own_return_address()
        if not ret:
            raise ValueError("Open the dashboard by its own address (like http://192.168.1.20:%s) to use Discord sign-in"
                             % APP.settings.get("port"))
        nonce, exp = secrets.token_urlsafe(24), now() + 600
        with LOCK:
            pend = Handler._DLOGIN_PENDING
            for k in [k for k, v in pend.items() if v["exp"] < now()]:
                pend.pop(k, None)
            if len(pend) > 200:
                raise ValueError("Too many sign-ins at once - try again in a few minutes")
            pend[nonce] = {"mode": mode, "user": user, "ret": ret, "exp": exp}
        sig = dlogin_sig(conf["key"], "start|%s|%s|%s|%d" % (conf["inst"], nonce, ret, exp))
        url = LOGIN_SERVICE + "/start?" + urllib.parse.urlencode({"inst": conf["inst"], "nonce": nonce, "ret": ret, "exp": exp, "sig": sig})
        self.send(200, {"ok": True, "url": url}, extra={"Set-Cookie": self.cookie_header(nonce, name="es_dn", max_age=600)})

    def api_discord_start(self, q):
        if APP.is_locked(self.ip):
            return self.fail(429, "Too many wrong attempts. Try again in 15 minutes.")
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlparse(origin).netloc != self.headers.get("Host", ""):
            return self.fail(403, "Security check failed - reload the page")
        try:
            self._dlogin_begin("login")
        except ValueError as e:
            self.fail(400, str(e))

    def post_me_discord_link(self, q):
        u = self._me()
        self._dlogin_begin("link", u["name"])

    def post_me_discord_unlink(self, q):
        u = self._me()
        users = load_users()
        for x in users:
            if x["name"].lower() == u["name"].lower():
                x.pop("discord", None)
        save_users(users)
        activity(u["name"], "Unlinked Discord", "dashboard", self.ip, "main")
        self.send(200, {"ok": True})

    def api_discord_finish(self, q):
        app = APP
        if app.is_locked(self.ip):
            return self.fail(429, "Too many wrong attempts. Try again in 15 minutes.")
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlparse(origin).netloc != self.headers.get("Host", ""):
            return self.fail(403, "Security check failed - reload the page")
        conf = dlogin_conf() if dlogin_available() else None
        b = self.body_json(8192)
        nonce = self.cookie("es_dn") or ""
        note = dlogin_check_note(conf, b.get("a")) if conf else None
        with LOCK:
            pend = Handler._DLOGIN_PENDING.get(nonce)
        ret = self.own_return_address()
        # the note must be for this browser's sign-in (its cookie), for this dashboard and for this address
        if not note or not pend or pend["exp"] < now() or not hmac.compare_digest(note["nonce"], nonce) \
                or note.get("aud") != pend["ret"] or ret != pend["ret"]:
            time.sleep(0.5)
            app.login_failed(self.ip)
            return self.fail(400, "That sign-in didn't work or took too long - try again")
        did, dname = note["sub"], clean_msg(str(note.get("name") or note.get("user") or ""))[:40] or "Discord user"
        clear = self.cookie_header("", clear=True, name="es_dn")
        if pend["mode"] == "link":
            with _TEAM_LOCK:
                users = load_users()
                other = next((x for x in users if (x.get("discord") or {}).get("id") == did and x["name"].lower() != str(pend["user"]).lower()), None)
                if other:
                    with LOCK:
                        Handler._DLOGIN_PENDING.pop(nonce, None)
                    return self.fail(400, "That Discord account is already linked to another dashboard account")
                me = next((x for x in users if x["name"].lower() == str(pend["user"]).lower()), None)
                if not me:
                    return self.fail(400, "Your account is gone")
                me["discord"] = {"id": did, "name": dname, "t": now()}
                save_users(users)
            with LOCK:
                Handler._DLOGIN_PENDING.pop(nonce, None)
            activity(me["name"], "Linked Discord (%s)" % dname, "dashboard", self.ip, "main")
            return self.send(200, {"ok": True, "linked": dname}, extra={"Set-Cookie": clear})
        # sign in: Discord stands in for the password only
        u = find_user_by_discord(did)
        local = not ip_is_remote(self.ip)
        if not u or u.get("disabled"):
            with LOCK:
                Handler._DLOGIN_PENDING.pop(nonce, None)
            time.sleep(0.5)
            app.login_failed(self.ip)
            return self.send(403, {"ok": False, "error": "No dashboard account is linked to this Discord account. Log in with "
                                   "your name and password, then link Discord under My account."}, extra={"Set-Cookie": clear})
        if not local and not (u.get("remote") and u.get("totp")):
            with LOCK:
                Handler._DLOGIN_PENDING.pop(nonce, None)
            activity(u["name"], "Login refused (from the internet)", "dashboard", self.ip, "main", ok=False)
            return self.fail(403, "This account can only log in from the home network.")
        if u.get("totp") and not user_totp_ok(u, b.get("code")):
            if b.get("code"):
                time.sleep(0.7)
                app.login_failed(self.ip)
            return self.fail(401, "Enter the code from your two-step login app", need_code=True)
        with LOCK:
            if not Handler._DLOGIN_PENDING.pop(nonce, None):
                return self.fail(400, "That sign-in was already used - try again")
        users = load_users()
        for x in users:
            if x["name"].lower() == u["name"].lower():
                x["last_login"] = now()
        save_users(users)
        tok = app.new_session(self.ip, u["name"], u["role"])
        activity(u["name"], "Logged in with Discord" + ("" if local else " (from the internet)"), "dashboard", self.ip, "main")
        self.send(200, {"ok": True}, extra={"Set-Cookie": self.login_cookies(tok, u["name"], b.get("remember") is True) + [clear]})

    # ---------- my account (extra accounts)
    def _me(self):
        if self.sess.get("user", "owner") == "owner":
            raise ValueError("The owner changes these under Settings")
        u = find_user(self.sess["user"])
        if not u:
            raise ValueError("No such account")
        return u

    def get_me(self, q):
        if self.sess.get("user", "owner") == "owner":
            return self.send(200, {"owner": True})
        u = self._me()
        self.send(200, {"name": u["name"], "totp": bool(u.get("totp")), "remote": bool(u.get("remote")),
                        "discord": (u.get("discord") or {}).get("name"), "discord_login": self.session_discord_on(),
                        "remote_enabled": bool(APP.settings.get("remote_enabled")), "roles": self.session_server_roles(self.sess_real)})

    def post_me_password(self, q):
        u = self._me()
        b = self.body_json()
        if not check_password(str(b.get("current") or ""), u.get("pw", "")):
            time.sleep(0.7)
            APP.login_failed(self.ip)
            raise ValueError("Your current password is wrong")
        pw = str(b.get("new") or "")
        if len(pw) < 10:
            raise ValueError("Use a password with at least 10 characters")
        users = load_users()
        for x in users:
            if x["name"].lower() == u["name"].lower():
                x["pw"] = hash_password(pw)
        save_users(users)
        forget_devices(u["name"])
        self.send(200, {"ok": True})

    def post_me_2fa_begin(self, q):
        u = self._me()
        secret, pub = new_totp(u["name"])
        self.sess_real["pending_totp"] = secret
        self.send(200, pub)

    def post_me_2fa_confirm(self, q):
        u = self._me()
        secret = self.sess_real.get("pending_totp")
        if not secret:
            return self.fail(400, "Start the setup again")
        if not totp_matches(secret, self.body_json().get("code")):
            return self.fail(400, "That code is wrong - check the time on your phone and try again")
        users = load_users()
        for x in users:
            if x["name"].lower() == u["name"].lower():
                x["totp"] = _seal(secret)
        save_users(users)
        self.sess_real.pop("pending_totp", None)
        self.send(200, {"ok": True})

    def post_me_2fa_disable(self, q):
        u = self._me()
        if not check_password(str(self.body_json().get("password") or ""), u.get("pw", "")):
            time.sleep(0.7)
            APP.login_failed(self.ip)
            raise ValueError("Wrong password")
        if u.get("remote") and ip_is_remote(self.ip):
            raise ValueError("You're logged in from the internet - turn it off at home, or ask the owner")
        users = load_users()
        for x in users:
            if x["name"].lower() == u["name"].lower():
                x.pop("totp", None)
        save_users(users)
        self.send(200, {"ok": True})

    def get_activity(self, q):
        try:
            n = max(20, min(2000, int(q.get("limit", 300))))
        except ValueError:
            n = 300
        self.send(200, {"rows": read_activity(n, str(q.get("who") or ""), str(q.get("via") or ""))})

    # ---------- health report, diagnostics, connection doctor
    def get_health(self, q):
        self.send(200, health_report(deep=q.get("deep") == "1"))

    def get_health_report(self, q):
        body = diagnostic_report().encode("utf-8")
        fname = "beammp-diagnostics-%s.txt" % time.strftime("%Y%m%d-%H%M")
        self.send_response(200)
        self.headers_common("text/plain; charset=utf-8", len(body), {"Content-Disposition": 'attachment; filename="%s"' % fname})
        self.wfile.write(body)

    def get_health_reports(self, q):
        self.send(200, {"reports": list_diagnostic_reports(I().id)})

    def get_health_saved(self, q):
        name = str(q.get("file") or "")
        if not re.fullmatch(r"diagnostics-[a-z0-9]{1,12}-\d{8}-\d{6}\.txt", name) or not name.startswith("diagnostics-%s-" % I().id):
            return self.fail(404, "not found")
        try:
            with open(os.path.join(DIAG_DIR, name), "rb") as f:
                body = f.read()
        except OSError:
            return self.fail(404, "not found")
        self.send_response(200)
        self.headers_common("text/plain; charset=utf-8", len(body), {"Content-Disposition": 'attachment; filename="%s"' % name})
        self.wfile.write(body)

    def get_health_join(self, q):
        self.send(200, connection_doctor(q.get("player") or ""))

    def get_power_offline(self, q):
        """What the "server is asleep" page (cached by the browser) needs to send a wake-up."""
        topic = APP.secrets.get("WAKE_TOPIC")
        self.send(200, {"server": (APP.settings.get("ntfy_server") or "https://ntfy.sh").rstrip("/"), "topic": topic} if topic else {})

    def post_power_helper(self, q):
        """The always-on wake helper: pair (new code), test (is it listening?) or forget it."""
        app = APP
        b = self.body_json()
        act = b.get("action")
        if act == "pair":
            if not wol_target()[0]:
                power_status(force=True)
            if not wol_target()[0]:
                return self.fail(400, "No network cable adapter found - Wake-on-LAN needs one")
            if not app.secrets.has("WAKE_TOPIC") or b.get("new"):
                app.secrets.set("WAKE_TOPIC", "beammp-wake-" + secrets.token_hex(14))
                app.state.update({"helper_seen": 0, "helper_version": ""})
                app.save_state()
            return self.send(200, {"ok": True, "code": wake_pairing_code()})
        if act == "forget":
            app.secrets.set("WAKE_TOPIC", "")
            app.state.update({"helper_seen": 0, "helper_version": ""})
            app.save_state()
            return self.send(200, {"ok": True})
        if act == "test":
            if not app.secrets.has("WAKE_TOPIC"):
                return self.fail(400, "Set up the wake helper first")
            nonce = secrets.token_hex(6)
            try:
                ntfy_wake_post("ping " + nonce)
                for _ in range(8):
                    time.sleep(1.5)
                    for m in ntfy_wake_replies("1m"):
                        p = m.split()
                        if len(p) >= 3 and p[0] == "pong" and p[1] == nonce:
                            app.state.update({"helper_seen": now(), "helper_version": re.sub(r"[^\w.\-]", "", p[2])[:20]})
                            app.save_state()
                            return self.send(200, {"ok": True, "found": True, "version": app.state["helper_version"]})
            except (OSError, ValueError) as e:
                return self.fail(400, "Couldn't reach ntfy: %s" % short_err(e))
            return self.send(200, {"ok": True, "found": False})
        self.fail(400, "unknown action")

    # ---------- scheduled events
    def get_events(self, q):
        avail = BUILTIN_MAPS + [m for m in enabled_mod_maps() if m not in BUILTIN_MAPS]
        act = I().meta.get("event_active")
        evs = []
        for e in events_cfg(I()):
            st = event_next_start(e, now()) if e.get("on", True) else None
            evs.append(dict(e, next=st))
        last = I().meta.get("event_last")
        self.send(200, {"events": evs, "maps": avail, "mods": [m["name"] for m in list_mods()],
                        "days": list(EVENT_DAYS), "active": act if isinstance(act, dict) else None,
                        "games": [{"id": k, "label": v} for k, v in EVENT_GAMES.items()],
                        "last": last if isinstance(last, dict) else None, "today": time.strftime("%Y-%m-%d"),
                        "has_webhook": bool(webhook_parts()[0])})

    def post_events(self, q):
        b = self.body_json()
        raw = b.get("events")
        if not isinstance(raw, list) or len(raw) > 20:
            return self.fail(400, "At most 20 events")
        avail = set(BUILTIN_MAPS) | set(enabled_mod_maps())
        allmods = {m["name"] for m in list_mods()}
        out = []
        for e in raw:
            if not isinstance(e, dict):
                return self.fail(400, "bad event")
            name = clean_msg(e.get("name"))[:60]
            if not name:
                return self.fail(400, "Give every event a name")
            days = sorted({int(d) for d in (e.get("days") or []) if str(d).isdigit() and 0 <= int(d) <= 6})
            date = str(e.get("date") or "").strip()
            if date:
                try:
                    dt = time.strptime(date, "%Y-%m-%d")
                    assert 2020 <= dt.tm_year <= 2100
                except (ValueError, AssertionError):
                    return self.fail(400, "Enter the date of %s like 2026-12-31" % name)
                days = []
            elif not days:
                return self.fail(400, "Pick at least one day for %s" % name)
            game = str(e.get("game") or "")
            if game and game not in EVENT_GAMES:
                return self.fail(400, "bad game")
            at = str(e.get("at") or "").strip()
            if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", at):
                return self.fail(400, "Enter the start time of %s like 20:00" % name)
            try:
                minutes = int(e.get("minutes") or 0)
                assert 15 <= minutes <= 720
            except (TypeError, ValueError, AssertionError):
                return self.fail(400, "%s must last 15 minutes to 12 hours" % name)
            mp = str(e.get("map") or "")
            mods = [m for m in (e.get("mods") or []) if m in allmods][:20]
            if mp not in avail and not mods:
                return self.fail(400, "Pick the map for %s" % name)
            ann = int(e.get("announce") or 0)
            if ann not in (0, 10, 30, 60, 120, 1440):
                return self.fail(400, "bad announce time")
            out.append({"id": re.sub(r"[^a-z0-9]", "", str(e.get("id") or ""))[:12] or uuid.uuid4().hex[:8],
                        "name": name, "days": days, "at": "%02d:%s" % (int(at.split(":")[0]), at.split(":")[1]),
                        "minutes": minutes, "map": mp, "mods": mods, "announce": ann, "ping": bool(e.get("ping")),
                        "text": clean_msg(e.get("text"))[:200], "on": bool(e.get("on", True)),
                        "date": date, "game": game, "results": bool(e.get("results"))})
        before = {e.get("id") for e in events_cfg(I())}
        set_server_meta(I().id, events=out)
        note = "Saved %d event%s." % (len(out), "" if len(out) == 1 else "s")
        new = [e for e in out if e["id"] not in before and e["on"]]
        if new and APP.settings.get("event_ads"):
            inst = I()
            def post(evs=new, inst=inst):
                use_server(inst.id)
                for e in evs:
                    st = event_next_start(e, now())
                    if e.get("date"):
                        if not st:
                            continue
                        broadcast("🎉 New event: %s" % e["name"], "<t:%d:F> (<t:%d:R>) on %s%s.%s" % (
                            st, st, inst.name, (" - map " + e["map"]) if e.get("map") else "",
                            (" " + e["text"]) if e.get("text") else ""))
                        continue
                    days = ", ".join(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d] for d in e["days"])
                    broadcast("🎉 New event: %s" % e["name"], "Every %s at %s on %s%s. First one: <t:%d:F>.%s" % (
                        days, e["at"], inst.name, (" - map " + e["map"]) if e.get("map") else "", st or now(),
                        (" " + e["text"]) if e.get("text") else ""))
            threading.Thread(target=post, daemon=True).start()
            note += " Advertised the new event%s." % ("" if len(new) == 1 else "s")
        self.send(200, {"ok": True, "note": note})

    def post_events_stop(self, q):
        act = I().meta.get("event_active")
        if not isinstance(act, dict):
            return self.fail(400, "No event is running")
        set_server_meta(I().id, event_active=dict(act, end=0))
        self.send(200, {"ok": True, "note": "Ending the event - the map switches back within a few seconds."})

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
        for k, sk in (("status_msg", "discord_status_msg"), ("bridge", "discord_bridge")):
            if k in b:
                if b[k] and not webhook_parts()[0]:
                    return self.fail(400, "Add your Discord webhook under Settings -> Notifications first - "
                                          "the status message and the game chat go to its channel")
                upd[sk] = bool(b[k])
        if "bridge_server" in b:
            with LOCK:
                if str(b["bridge_server"]) not in INSTANCES:
                    return self.fail(400, "Pick a server")
            upd["discord_bridge_server"] = str(b["bridge_server"])
        bridge_changed = "discord_bridge" in upd and upd["discord_bridge"] != bool(app.settings.get("discord_bridge"))
        status_off = upd.get("discord_status_msg") is False and app.settings.get("discord_status_msg")
        if upd:
            app.settings.update(upd)
        if status_off and app.state.get("status_msg"):
            try:
                webhook_call("DELETE", "/messages/%s" % app.state["status_msg"])
            except Exception:
                pass
            app.state.pop("status_msg", None)
            app.save_state()
        if upd.get("discord_status_msg"):
            app.status_next = 0
        if "token" in b or "enabled" in b or bridge_changed:
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
            "has_duck": app.secrets.has("DUCKDNS_TOKEN"), "duck_err": app.state.get("duck_err") or "",
            "port_main": INSTANCES["main"].port() if "main" in INSTANCES else None,
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
        if upd.get("guard_on") and on_mac():
            return self.fail(400, "The BeamMP-only guard doesn't work on a Mac yet: players reach the server through the Mac, so they all look like one address.")
        if upd:
            app.settings.update(upd)
        if "flood_protect" in upd:
            threading.Thread(target=app.flood_tick, daemon=True).start()
        if "guard_on" in upd:
            threading.Thread(target=app.guard_apply, daemon=True).start()
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
        forget_devices()                # a new password logs out every remembered device
        self.send(200, {"ok": True}, extra={"Set-Cookie": self.cookie_header("", clear=True, name=DEVICE_COOKIE)})

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
            if on_mac():
                # every visitor looks like 127.0.0.1 there, so "home network only" rules can't be enforced
                return self.fail(400, "Internet access to the dashboard isn't available on a Mac yet. "
                                      "Don't forward the dashboard port on your router either.")
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
        include_mods = q.get("mods") == "1"
        fd, tmp = tempfile.mkstemp(suffix=".zip", dir=DATA_DIR)
        os.close(fd)
        try:
            build_export(tmp, include_mods)
            size = os.path.getsize(tmp)
            fname = "beammp-server-%s.zip" % time.strftime("%Y%m%d-%H%M")
            self.send_response(200)
            self.headers_common("application/zip", size, {"Content-Disposition": 'attachment; filename="%s"' % fname})
            with open(tmp, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
        finally:
            os.remove(tmp)

    def put_import(self, q):
        fd, tmp = tempfile.mkstemp(suffix=".zip", dir=DATA_DIR)
        os.close(fd)
        try:
            self.body_to_file(tmp, 20 * 1024 ** 3)
            return self._import_zip(tmp, q)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass

    def post_backups_restore(self, q):
        """Put a nightly backup back with one click - no download and upload. A backup of how things are right
        now is made first, so a restore can be undone. Mods in the backup only come back when asked for."""
        b = self.body_json()
        name = str(b.get("file") or "")
        if not any(x["file"] == name for x in list_backups(I().id)):
            return self.fail(404, "No such backup")
        fd, tmp = tempfile.mkstemp(suffix=".zip", dir=DATA_DIR)
        os.close(fd)
        try:
            shutil.copyfile(os.path.join(BACKUP_DIR, name), tmp)   # copied first: the backup below can't replace it
            try:
                undo = make_backup(I(), False)
            except Exception as e:
                return self.fail(500, "Couldn't save the current settings first, so nothing was restored (%s)" % short_err(e))
            self._restore_undo = undo
            return self._import_zip(tmp, {"settings": "1", "mods": "1" if b.get("mods") is True else "0"})
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass

    def _import_zip(self, tmp, q):
        """Apply an export / backup zip (the file at tmp) to the current server."""
        app = APP
        report = {"config": False, "settings": False, "mods_added": [], "mods_blocked": [], "skipped": []}
        try:
            z = zipfile.ZipFile(tmp)
        except zipfile.BadZipFile:
            return self.fail(400, "That isn't an export file (.zip)")
        with z:
            names = z.namelist()
            only_mods = "ServerConfig.toml" not in names and "modpack.json" in names
            if not only_mods:
                if "ServerConfig.toml" not in names:
                    return self.fail(400, "No ServerConfig.toml or modpack.json in this file")
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
            for extra, rd, wr in (("extras.txt", read_extras, write_extras), ("moderation.txt", read_mod, write_mod),
                                  ("messages.txt", read_messages, write_messages)):
                if extra in names and z.getinfo(extra).file_size < 256 * 1024:
                    shared_write(os.path.join(I().STATS_DIR, extra), z.read(extra).decode("utf-8", "replace"))
                    wr(rd())                     # re-written through the checks
                    report.setdefault("restored", []).append(extra)
            if "bans.txt" in names and z.getinfo("bans.txt").file_size < 256 * 1024:
                shared_write(I().BANS_FILE, z.read("bans.txt").decode("utf-8", "replace"))
                write_bans(read_bans())
                report.setdefault("restored", []).append("bans.txt")
            if q.get("games") == "1":
                for n in names:
                    gm = re.fullmatch(r"games/([^/]+)", n)
                    if not gm:
                        continue
                    zi = z.getinfo(n)
                    if not games_name_ok(gm.group(1)) or zi.file_size > GAMES_MAX:
                        report["skipped"].append(n[:120])
                        continue
                    dest = os.path.join(I().STATS_DIR, gm.group(1))
                    try:
                        os.unlink(dest + ".tmp")
                    except OSError:
                        pass
                    with z.open(zi) as src, open_shared(dest + ".tmp", "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    os.replace(dest + ".tmp", dest)
                    report.setdefault("games", []).append(gm.group(1))
            if q.get("mods", "1") == "1":
                total = 0
                for n in names:
                    m = re.fullmatch(r"(mods|mods-disabled)/([^/]+)", n)
                    if not m:
                        if n not in ("ServerConfig.toml", "easyserver-export.json", "modpack.json", "README.txt") + STATS_EXPORT \
                                and not n.endswith("/") and not (n.startswith("games/") and q.get("games") == "1"):
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
        if only_mods:
            report["modpack"] = True
            if report["mods_added"]:
                app.config_changed()
            return self.send(200, {"ok": True, "report": report, "note": "Added %d mod%s from the modpack." % (
                len(report["mods_added"]), "" if len(report["mods_added"]) == 1 else "s") + (" " + app.applied_note() if report["mods_added"] else "")})
        old_port = (toml_parse(app.read_config_text())[0].get("General") or {}).get("Port")
        text = app.move_plaintext_authkey(text)
        app.write_config_text(text)
        report["config"] = True
        new_port = (toml_parse(text)[0].get("General") or {}).get("Port")
        if isinstance(new_port, int) and new_port != old_port and not IS_WIN:
            control("firewall-game", old=old_port if isinstance(old_port, int) else None, new=new_port, timeout=30)
            app.notifier.add("network", "Server port changed", "Import changed the port %s -> %d. "
                             "Remember to forward the new port on your router." % (old_port, new_port))
        undo = getattr(self, "_restore_undo", None)
        note = app.applied_note()
        if undo:
            note = "Backup restored. How things were just before is saved as a backup too, if you want it back. " + note
        self.send(200, {"ok": True, "report": report, "note": note, "undo": undo})


def clean_settings(b):
    """Checked copy of the user-changeable notification settings in b (raises ValueError)."""
    upd = {}
    if isinstance(b.get("notify"), dict):
        cur = APP.settings.get("notify")
        cur.update({k: bool(v) for k, v in b["notify"].items() if k in DEFAULT_SETTINGS["notify"]})
        upd["notify"] = cur
    for k in ("discord_enabled", "email_enabled", "auto_restart", "update_check", "security_alerts", "security_reminders",
              "relay_enabled", "flood_protect", "guard_on"):
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

    def finish_request(self, request, client_address):
        request.settimeout(30)
        if not self.tls_ctx:
            return super().finish_request(request, client_address)
        # HTTPS is on. A browser that still opens http:// (an old shortcut or bookmark) gets sent to
        # https:// instead of a "connection reset". Done here, in the request's own thread, so a slow
        # client can't hold up the others.
        try:
            request.settimeout(10)
            first = request.recv(1, socket.MSG_PEEK)
        except OSError:
            return
        if not first:
            return
        if first != b"\x16":                 # not a TLS handshake: plain HTTP
            return self.redirect_to_https(request)
        try:
            tls = self.tls_ctx.wrap_socket(request, server_side=True, do_handshake_on_connect=False)
        except (ssl.SSLError, OSError):
            return
        try:
            tls.settimeout(30)
            tls.do_handshake()
            super().finish_request(tls, client_address)
        except (ssl.SSLError, OSError):
            pass
        finally:
            try:
                tls.close()
            except OSError:
                pass

    def redirect_to_https(self, sock):
        data = b""
        try:
            while b"\r\n\r\n" not in data and len(data) < 8192:
                part = sock.recv(2048)
                if not part:
                    break
                data += part
        except OSError:
            return
        m = re.search(rb"(?im)^host:[ \t]*([A-Za-z0-9.\-]{1,100}|\[[0-9A-Fa-f:.]{2,60}\])(?::\d{1,5})?[ \t]*\r?$", data)
        port = self.server_address[1]
        host = m.group(1).decode() if m else "localhost"
        body = b"This dashboard uses HTTPS - open https://%s:%d/" % (host.encode(), port)
        try:
            sock.sendall(b"HTTP/1.1 301 Moved Permanently\r\nLocation: https://%s:%d/\r\nContent-Type: text/plain\r\n"
                         b"Content-Length: %d\r\nConnection: close\r\n\r\n%s" % (host.encode(), port, len(body), body))
        except OSError:
            pass

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
    threading.Thread(target=APP.guard_loop, daemon=True).start()
    threading.Thread(target=APP.bot.run, daemon=True).start()
    if not APP.updates:
        threading.Thread(target=APP.check_updates, kwargs={"notify": True}, daemon=True).start()
    print("BeamMP EasyServer dashboard %s on %s://0.0.0.0:%d" % (EASY_VERSION, "https" if ctx else "http", port), flush=True)
    httpd.serve_forever()


class RollingLog:
    """dashboard.log on Windows. It holds visitors' IP addresses, so it doesn't grow forever: at 5 MB, or
    30 days after it was started, it becomes dashboard.log.1 (replacing the older one) and a new one begins."""
    MAX, AGE = 5 * 1024 * 1024, 30 * 86400

    def __init__(self, path):
        self.path, self.lock, self.next_check = path, threading.Lock(), 0
        self._open()

    def _open(self):
        self.f = open(self.path, "a", encoding="utf-8", buffering=1)
        try:
            with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                first = f.readline()
            self.started = time.mktime(time.strptime(first[:19], "%Y-%m-%d %H:%M:%S"))
        except (OSError, ValueError, OverflowError):
            self.started = os.path.getctime(self.path)     # a log from before this (Windows: when it was made)
            if not os.path.getsize(self.path):
                self.started = time.time()
                self.f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " log started\n")

    def _roll(self):
        now = time.time()
        if now < self.next_check:
            return
        self.next_check = now + 60
        try:
            if self.f.tell() < self.MAX and now - self.started < self.AGE:
                return
            self.f.close()
            os.replace(self.path, self.path + ".1")
        except OSError:
            pass
        self._open()

    def write(self, s):
        with self.lock:
            self._roll()
            return self.f.write(s)

    def flush(self):
        self.f.flush()

    def isatty(self):
        return False

    def __getattr__(self, name):                       # encoding, fileno … of the open file
        return getattr(self.f, name)


if __name__ == "__main__":
    if IS_WIN and (sys.stderr is None or sys.stdout is None):
        # started hidden (pythonw): keep messages and crashes in a log file
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            sys.stdout = sys.stderr = RollingLog(os.path.join(DATA_DIR, "dashboard.log"))
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
