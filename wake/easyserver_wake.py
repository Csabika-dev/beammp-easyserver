#!/usr/bin/env python3
"""BeamMP EasyServer - wake helper.

Runs on a small device at home that is always on (a Raspberry Pi, a NAS,
another PC). While the BeamMP server computer sleeps, it:
  * listens for "wake" on your private ntfy topic (the Wake up button in the
    phone app and on the "server is asleep" page) and
  * answers /start and /status in your Discord (optional, needs the bot token)
and wakes the server computer with a Wake-on-LAN "magic packet".

It can only send wake-up packets - it has no access to the server computer.
No port forwarding needed: it only makes outgoing connections.

    python3 easyserver_wake.py setup     # paste the pairing code from the dashboard
    python3 easyserver_wake.py run       # what the service runs
    python3 easyserver_wake.py wake      # wake the server computer right now
    python3 easyserver_wake.py status    # show the settings

Not affiliated with the BeamMP team. Only uses the Python standard library.
"""
import base64
import getpass
import hashlib
import ipaddress
import json
import os
import re
import socket
import ssl
import struct
import sys
import threading
import time
import urllib.error
import urllib.request

VERSION = "1.13.0"
DISCORD_API = os.environ.get("ES_DISCORD_API") or "https://discord.com/api/v10"
DISCORD_GATEWAY = os.environ.get("ES_DISCORD_GATEWAY") or "wss://gateway.discord.gg/?v=10&encoding=json"
TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]{20,100}\.[A-Za-z0-9_\-]{4,20}\.[A-Za-z0-9_\-]{20,100}")
MAC_RE = re.compile(r"([0-9a-f]{2}:){5}[0-9a-f]{2}")
TOPIC_RE = re.compile(r"beammp-wake-[A-Za-z0-9]{20,40}")
NTFY_RE = re.compile(r"https://[A-Za-z0-9.\-]{1,253}(:\d{1,5})?")
PERM_ADMIN, PERM_MANAGE_GUILD = 0x8, 0x20
UA = "BeamMP-EasyServer-WakeHelper/" + VERSION


def default_config():
    if os.environ.get("BEAMMP_WAKE_CONFIG"):
        return os.environ["BEAMMP_WAKE_CONFIG"]
    if os.name == "nt":
        return os.path.join(os.environ.get("ProgramData") or os.path.expanduser("~"), "BeamMP-Wake", "config.json")
    if os.geteuid() == 0 or os.path.isdir("/etc/beammp-wake"):
        return "/etc/beammp-wake/config.json"
    return os.path.join(os.path.expanduser("~"), ".config", "beammp-wake", "config.json")


def log(msg):
    sys.stdout.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    sys.stdout.flush()


def short_err(e):
    return ("%s: %s" % (e.__class__.__name__, e))[:200]


# ----------------------------------------------------------------------------- pairing code
def decode_code(code):
    """Check everything in the pairing code - it's pasted by a person and could be anything."""
    code = re.sub(r"\s", "", code or "")
    if not code.startswith("ESW1-"):
        raise ValueError("That isn't a pairing code (it starts with ESW1-)")
    raw = code[5:]
    try:
        d = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode())
    except (ValueError, UnicodeDecodeError):
        raise ValueError("The pairing code is damaged - copy it again")
    if not isinstance(d, dict) or d.get("v") != 1:
        raise ValueError("This pairing code is for a newer version - update the helper")
    out = {"mac": str(d.get("mac") or "").lower(), "ip": str(d.get("ip") or ""), "port": d.get("port"),
           "ntfy": str(d.get("ntfy") or "").rstrip("/"), "topic": str(d.get("topic") or ""),
           "guild": str(d.get("guild") or ""), "name": str(d.get("name") or "BeamMP server")[:60]}
    if not MAC_RE.fullmatch(out["mac"]):
        raise ValueError("The pairing code has no valid MAC address")
    brd = []
    for b in d.get("brd") or []:
        try:
            brd.append(str(ipaddress.IPv4Address(str(b))))
        except ValueError:
            pass
    out["brd"] = brd[:4]
    try:
        out["ip"] = str(ipaddress.IPv4Address(out["ip"])) if out["ip"] else ""
    except ValueError:
        out["ip"] = ""
    if not (isinstance(out["port"], int) and 1 <= out["port"] <= 65535):
        out["port"] = 30815
    if not NTFY_RE.fullmatch(out["ntfy"]) or not TOPIC_RE.fullmatch(out["topic"]):
        raise ValueError("The pairing code has no valid wake topic - make a new code in the dashboard")
    if out["guild"] and not re.fullmatch(r"\d{5,25}", out["guild"]):
        out["guild"] = ""
    out["users"] = [str(u) for u in d.get("users") or [] if re.fullmatch(r"\d{5,25}", str(u))][:50]
    return out


def load_config(path):
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    c["pair"] = decode_code(c.get("code") or "")
    tok = c.get("bot_token") or ""
    c["bot_token"] = tok if TOKEN_RE.fullmatch(tok) else ""
    return c


def save_config(path, code, token):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"code": code, "bot_token": token}, f)
    os.replace(tmp, path)


# ----------------------------------------------------------------------------- Wake-on-LAN
def magic_packet(mac):
    return b"\xff" * 6 + bytes.fromhex(mac.replace(":", "")) * 16


def send_wake(pair, why=""):
    pkt = magic_packet(pair["mac"])
    targets = list(dict.fromkeys(pair["brd"] + ["255.255.255.255"]))
    sent = 0
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for _ in range(3):
            for host in targets:
                for port in (9, 7):
                    try:
                        s.sendto(pkt, (host, port))
                        sent += 1
                    except OSError:
                        pass
            time.sleep(0.3)
    finally:
        s.close()
    log("wake-up sent to %s%s (%d packets)" % (pair["mac"], (" - " + why) if why else "", sent))
    return sent > 0


def is_awake(pair):
    """The dashboard answers on its port when the computer is awake."""
    if not pair["ip"]:
        return False
    try:
        socket.create_connection((pair["ip"], pair["port"]), timeout=3).close()
        return True
    except OSError:
        return False


# ----------------------------------------------------------------------------- Discord (only while asleep)
class WSClosed(Exception):
    pass


class MiniWebSocket:
    """Just enough of a WebSocket client for the Discord gateway."""

    def __init__(self, url, timeout=90):
        from urllib.parse import urlsplit
        u = urlsplit(url)
        raw = socket.create_connection((u.hostname, u.port or (80 if u.scheme == "ws" else 443)), timeout=30)
        self.s = raw if u.scheme == "ws" else ssl.create_default_context().wrap_socket(raw, server_hostname=u.hostname)
        key = base64.b64encode(os.urandom(16)).decode()
        path = (u.path or "/") + ("?" + u.query if u.query else "")
        self.s.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nUser-Agent: %s\r\n\r\n"
                        % (path, u.hostname, key, UA)).encode())
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
                raise WSClosed("closed by Discord (%s)" % (struct.unpack(">H", data[:2])[0] if len(data) >= 2 else 1000))
            if op == 9:
                self.send(data, 10)
                continue
            if op == 10:
                continue
            msg += data
            if b1 & 0x80:
                return msg.decode("utf-8", "replace")

    def close(self):
        for fn in (lambda: self.send(struct.pack(">H", 1000), 8), lambda: self.s.shutdown(socket.SHUT_RDWR), self.s.close):
            try:
                fn()
            except Exception:
                pass


def discord_api(method, path, token=None, body=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    hdr = {"User-Agent": "DiscordBot (https://github.com/Csabika-dev/beammp-easyserver, %s)" % VERSION,
           "Content-Type": "application/json"}
    if token:
        hdr["Authorization"] = "Bot " + token
    req = urllib.request.Request(DISCORD_API + path, data=data, method=method, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


# ----------------------------------------------------------------------------- the helper
class Helper:
    def __init__(self, cfg):
        self.pair, self.token = cfg["pair"], cfg["bot_token"]
        self.awake = is_awake(self.pair)
        self.changed = time.time()
        self.last_wake = 0
        self.ws = None
        self.app_id = None

    def wake(self, why):
        if time.time() - self.last_wake < 8:            # someone pressing the button 10 times
            return True
        self.last_wake = time.time()
        return send_wake(self.pair, why)

    # ---------- is the server computer awake?
    def watch(self):
        while True:
            a = is_awake(self.pair)
            if a != self.awake:
                self.awake, self.changed = a, time.time()
                log("the server computer is %s" % ("awake" if a else "asleep (or off)"))
                if a and self.ws:
                    self.ws.close()                       # its own Discord bot takes over again
            time.sleep(15)

    # ---------- ntfy: the phone app / web page "Wake up" button and the dashboard's test
    def ntfy(self):
        url = "%s/%s/json" % (self.pair["ntfy"], self.pair["topic"])
        backoff = 5
        while True:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=120) as r:       # ntfy sends a keepalive every ~45 s
                    log("listening for wake-ups (ntfy)")
                    backoff = 5
                    for line in r:
                        try:
                            m = json.loads(line.decode("utf-8", "replace"))
                        except ValueError:
                            continue
                        if not isinstance(m, dict) or m.get("event") != "message":
                            continue
                        if abs(time.time() - int(m.get("time") or 0)) > 180:
                            continue                                       # old news
                        self.on_ntfy(str(m.get("message") or "").strip()[:100])
            except Exception as e:
                log("ntfy: %s - trying again in %d s" % (short_err(e), backoff))
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)

    def on_ntfy(self, text):
        parts = text.split()
        if not parts:
            return
        if parts[0] == "wake":
            self.wake("Wake up button")
        elif parts[0] == "ping" and len(parts) == 2 and re.fullmatch(r"[a-f0-9]{6,32}", parts[1]):
            body = "pong %s %s %s" % (parts[1], VERSION, "awake" if self.awake else "asleep")
            try:
                req = urllib.request.Request("%s/%s-r" % (self.pair["ntfy"], self.pair["topic"]), data=body.encode(),
                                             method="POST", headers={"User-Agent": UA})
                urllib.request.urlopen(req, timeout=15).read()
                log("answered a test from the dashboard")
            except Exception as e:
                log("couldn't answer the test: %s" % short_err(e))

    # ---------- Discord: answers /start and /status while the server computer sleeps
    def discord(self):
        backoff = 10
        while True:
            # Only while the computer has been asleep for a bit - when it's awake, its own bot answers.
            if self.awake or time.time() - self.changed < 40:
                time.sleep(5)
                continue
            try:
                self.session()
                backoff = 10
            except WSClosed as e:
                if "4004" in str(e):
                    log("Discord rejected the bot token - run setup again with the new token")
                    backoff = 3600
            except Exception as e:
                if not self.awake:                       # closing it on purpose isn't worth a log line
                    log("discord: %s" % short_err(e))
            finally:
                ws, self.ws = self.ws, None
                if ws:
                    ws.close()
            time.sleep(backoff if not self.awake else 5)
            backoff = min(backoff * 2, 600)

    def session(self):
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
                except Exception:
                    ws.close()
                    return
                time.sleep(interval)

        threading.Thread(target=beat, daemon=True).start()
        ws.send(json.dumps({"op": 2, "d": {"token": self.token, "intents": 0,
                                           "properties": {"os": sys.platform, "browser": "beammp-wake", "device": "beammp-wake"}}}))
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
                self.app_id = str((d.get("application") or {}).get("id") or "")
                log("answering /start in Discord while the server computer sleeps")
            elif op == 0 and t == "INTERACTION_CREATE":
                threading.Thread(target=self.on_interaction, args=(d,), daemon=True).start()

    def on_interaction(self, d):
        if d.get("type") != 2:
            return
        name = (d.get("data") or {}).get("name")
        cb = "/interactions/%s/%s/callback" % (d.get("id"), d.get("token"))
        edit = "/webhooks/%s/%s/messages/@original" % (self.app_id, d.get("token"))
        say = lambda text, private=False: discord_api("POST", cb, body={"type": 4, "data": dict(
            {"content": text, "allowed_mentions": {"parse": []}}, **({"flags": 64} if private else {}))})
        try:
            # No Discord server in the pairing code = don't trust any (pair again after picking one in the dashboard)
            if not self.pair["guild"] or str(d.get("guild_id") or "") != self.pair["guild"]:
                return say("This bot isn't set up for this Discord server.", True)
            label = self.pair["name"].replace("*", "").replace("_", "").replace("`", "")
            if name == "status":
                return say("💤 **%s** is asleep to save power. Use **/start** to wake it up." % label)
            if name not in ("start", "restart"):
                return say("💤 The server computer is asleep - use **/start** to wake it up first.", True)
            member = d.get("member") or {}
            uid = str((member.get("user") or {}).get("id") or "")
            perms = int(member.get("permissions") or 0)
            if not (perms & (PERM_ADMIN | PERM_MANAGE_GUILD)) and uid not in self.pair["users"]:
                return say("Only people with **Manage Server** (or who are allowed in the dashboard) can do that.", True)
            who = (member.get("user") or {}).get("global_name") or (member.get("user") or {}).get("username") or "someone"
            if not self.wake("/%s in Discord by %s" % (name, who)):
                return say("❌ Couldn't send the wake-up signal.")
            say("⏰ Waking up **%s**… this usually takes 30-60 seconds." % label)
            for i in range(36):                                  # up to 3 minutes
                time.sleep(5)
                if self.awake or is_awake(self.pair):
                    return discord_api("PATCH", edit, body={"content": "🟢 **%s** is awake. If the game server doesn't come "
                                                                       "back by itself, use **/start** again." % label,
                                                            "allowed_mentions": {"parse": []}})
                if i == 6:
                    self.last_wake = 0
                    self.wake("second try")
            discord_api("PATCH", edit, body={"content": "⚠️ **%s** didn't wake up. Check Wake-on-LAN (dashboard: Settings → "
                                                        "Sleep & wake-up) or press its power button." % label,
                                             "allowed_mentions": {"parse": []}})
        except Exception as e:
            log("discord command: %s" % short_err(e))

    def run(self):
        log("BeamMP wake helper %s for %s (%s)" % (VERSION, self.pair["name"], self.pair["mac"]))
        threads = [self.watch, self.ntfy] + ([self.discord] if self.token else [])
        for fn in threads:
            threading.Thread(target=fn, daemon=True).start()
        while True:
            time.sleep(3600)


# ----------------------------------------------------------------------------- command line
def setup(path, args):
    code = ""
    if "--code" in args and args.index("--code") + 1 < len(args):
        code = args[args.index("--code") + 1]
    while True:
        if not code:
            print("Paste the pairing code from the dashboard (Settings → Sleep & wake-up → Show pairing code):")
            code = sys.stdin.readline().strip()
        try:
            pair = decode_code(code)
            break
        except ValueError as e:
            print("  %s" % e)
            if not sys.stdin.isatty():
                sys.exit(1)
            code = ""
    print("  OK: %s, MAC %s" % (pair["name"], pair["mac"]))
    token = ""
    if "--no-token" not in args:
        old = ""
        try:
            old = load_config(path).get("bot_token") or ""
        except Exception:
            pass
        print("\nOptional: the Discord bot token, so /start works while the server computer sleeps.")
        print("Discord Developer Portal → your app → Bot → Reset Token → Copy. Then paste the NEW token in the")
        print("dashboard too (Settings → Discord bot), because resetting makes the old one stop working.")
        print("Press Enter to %s." % ("keep the saved token" if old else "skip"))
        while True:
            token = getpass.getpass("Bot token: ").strip() if sys.stdin.isatty() else sys.stdin.readline().strip()
            if not token:
                token = old
                break
            if not TOKEN_RE.fullmatch(token):
                print("  That doesn't look like a bot token.")
                continue
            try:
                me = discord_api("GET", "/users/@me", token)
                print("  OK: the bot is %s" % me.get("username"))
                break
            except urllib.error.HTTPError as e:
                print("  Discord says the token is wrong (%d)." % e.code if e.code == 401 else "  Discord error %d." % e.code)
            except OSError as e:
                print("  Can't reach Discord right now (%s) - saving it anyway." % short_err(e))
                break
    save_config(path, re.sub(r"\s", "", code), token)
    print("\nSaved to %s" % path)
    if not pair["ip"] or not is_awake(pair):
        print("Note: the dashboard isn't reachable from here right now - that's fine if the server computer is asleep.")


def main():
    args = sys.argv[1:]
    cmd = args[0] if args and not args[0].startswith("-") else "run"
    path = default_config()
    if "--config" in args and args.index("--config") + 1 < len(args):
        path = args[args.index("--config") + 1]
    if cmd == "setup":
        return setup(path, args)
    if "--log" in args and args.index("--log") + 1 < len(args):    # Windows service: log to a file
        lf = args[args.index("--log") + 1]
        try:
            if os.path.getsize(lf) > 1048576:
                os.replace(lf, lf + ".old")
        except OSError:
            pass
        sys.stdout = sys.stderr = open(lf, "a", encoding="utf-8", buffering=1)
    try:
        cfg = load_config(path)
    except FileNotFoundError:
        sys.exit("Not set up yet - run: %s setup" % sys.argv[0])
    except ValueError as e:
        sys.exit("The saved settings are broken (%s) - run setup again" % e)
    if cmd == "wake":
        send_wake(cfg["pair"], "by hand")
    elif cmd == "status":
        p = cfg["pair"]
        print("Server: %s\nMAC: %s\nBroadcast: %s\nDashboard: %s:%s (%s)\nntfy: %s\nDiscord: %s" % (
            p["name"], p["mac"], ", ".join(p["brd"]) or "-", p["ip"] or "-", p["port"],
            "awake" if is_awake(p) else "asleep / not reachable", p["ntfy"],
            "bot token saved" if cfg["bot_token"] else "off (no bot token)"))
    elif cmd == "run":
        Helper(cfg).run()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
