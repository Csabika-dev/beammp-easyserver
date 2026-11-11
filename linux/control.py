#!/usr/bin/env python3
"""BeamMP EasyServer - root helper for the dashboard (Linux).

The dashboard runs as the unprivileged "beammp-dash" user. When it needs
something only root may do (start/stop the server, install an update, save
an encrypted key, open the firewall) it drops a small JSON request into
/run/beammp-easyserver-ctl. systemd starts this script, which:
  * only accepts files owned by beammp-dash (not links, max 64 KB)
  * only performs a fixed list of actions with validated arguments
  * writes a short answer (never a secret) to /run/beammp-easyserver-ctl-out
"""
import json
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request

IN = "/run/beammp-easyserver-ctl"
OUT = "/run/beammp-easyserver-ctl-out"
LIB = "/usr/local/lib/beammp-easyserver"
SERVER_DIR = "/opt/beammp-server"
INSTALL_ENV = "/etc/beammp-easyserver/install.env"
SERVERS = SERVER_DIR + "/servers"              # extra servers: servers/<id>/
LIMITS_DIR = "/etc/beammp-easyserver/limits"   # upload limits, re-applied when a server starts
SECRET_NAMES = {"MODS_PASSWORD", "VT_API_KEY", "DISCORD_WEBHOOK", "SMTP_PASSWORD", "TOTP_SECRET", "BEAMMP_AUTH_KEY"}
ID_RE = re.compile(r"[a-z0-9]{1,12}")
RELEASE_BASE = "https://github.com/BeamMP/BeamMP-Server/releases/latest/download/"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=kw.pop("timeout", 120), **kw)


def unit_for(server):
    server = server or "main"
    if server == "main":
        return "beammp-server"
    if not ID_RE.fullmatch(str(server)) or not os.path.isdir(os.path.join(SERVERS, server)):
        raise ValueError("unknown server")
    return "beammp-server@%s" % server


def systemctl(action, unit="beammp-server"):
    r = run(["systemctl", action, unit], timeout=90)
    return {"ok": r.returncode == 0, "msg": "done" if r.returncode == 0 else (r.stderr.strip()[-300:] or "failed")}


def read_untrusted(path, limit=262144):
    """Read a file in a folder the game server controls: no links, no FIFOs/devices, size-capped."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("not a regular file")
        with os.fdopen(fd, "rb", closefd=False) as f:
            return f.read(limit).decode("utf-8", "replace")
    finally:
        os.close(fd)


def server_port(server):
    path = os.path.join(SERVER_DIR if server == "main" else os.path.join(SERVERS, server), "ServerConfig.toml")
    try:
        m = re.search(r"(?m)^\s*Port\s*=\s*(\d+)", read_untrusted(path))
        port = int(m.group(1)) if m else None
        return port if port and 1 <= port <= 65535 else None
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- extra servers
def open_servers_dir():
    """Open servers/ safely and return (fd, path-through-fd).

    /opt/beammp-server belongs to the game server user, so it could replace
    "servers" with a link at any moment. We open the real folder once (no
    links allowed), make sure it is root-owned, and from then on only use the
    /proc/self/fd/<n> path, which always points at that exact folder."""
    try:
        os.mkdir(SERVERS, 0o755)
    except FileExistsError:
        pass
    fd = os.open(SERVERS, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    os.fchown(fd, 0, 0)
    os.fchmod(fd, 0o755)
    return fd, "/proc/self/fd/%d" % fd


def create_server(server, config, start):
    if not ID_RE.fullmatch(str(server or "")) or server == "main":
        return {"ok": False, "msg": "bad server id"}
    if not isinstance(config, str) or not 10 < len(config) < 60000 or "[General]" not in config:
        return {"ok": False, "msg": "bad config"}
    try:
        sfd, base = open_servers_dir()
    except OSError:
        return {"ok": False, "msg": "the servers folder is not a normal folder"}
    try:
        return _create_server(server, config, start, base)
    finally:
        os.close(sfd)


def _create_server(server, config, start, base):
    d = os.path.join(base, server)
    if os.path.lexists(d):
        return {"ok": False, "msg": "a server with this id already exists"}
    u = pwd.getpwnam("beammp")
    dash = pwd.getpwnam("beammp-dash")
    # Everything is built while the folder is still root-only (0700) and all
    # modes are set before ownership is handed over - so the game server user
    # never gets a chance to swap a path for a link while root works on it.
    os.mkdir(d, 0o700)
    for sub in ("Resources/Client", "Resources/Client-disabled", "Resources/Quarantine", "Resources/Server/EasyServerStats"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    with open(os.path.join(d, "ServerConfig.toml"), "w", encoding="utf-8") as f:
        f.write(config if config.endswith("\n") else config + "\n")
    src = os.path.join(SERVER_DIR, "Resources/Server/EasyServerStats/main.lua")
    try:
        lua = read_untrusted(src, 1024 * 1024)   # same plugin as the main server
    except OSError:
        lua = None
    if lua:
        with open(os.path.join(d, "Resources/Server/EasyServerStats/main.lua"), "w", encoding="utf-8") as f:
            f.write(lua)
    os.chmod(os.path.join(d, "ServerConfig.toml"), 0o660)
    for sub in ("Resources/Client", "Resources/Client-disabled", "Resources/Server/EasyServerStats", "Resources/Quarantine"):
        os.chmod(os.path.join(d, sub), 0o2775)
    q = os.path.join(d, "Resources/Quarantine")
    for root, dirs, files in os.walk(d):
        for x in dirs + files:
            os.lchown(os.path.join(root, x), u.pw_uid, u.pw_gid)
    os.lchown(q, dash.pw_uid, u.pw_gid)
    os.chmod(d, 0o2770)            # still root-owned here, so this can't be redirected
    os.lchown(d, u.pw_uid, u.pw_gid)  # hand over last
    run([LIB + "/apply.sh", "--record", server])
    run(["systemctl", "enable", "beammp-mods-apply@%s.path" % server, "beammp-server@%s" % server], timeout=60)
    run(["systemctl", "start", "beammp-mods-apply@%s.path" % server], timeout=60)
    port = server_port(server)
    fw = firewall_game(None, port)["msg"] if port else ""
    res = systemctl("start", "beammp-server@%s" % server) if start else {"ok": True}
    return {"ok": res["ok"], "msg": "created. " + fw if res["ok"] else "created, but it didn't start: " + res["msg"]}


def delete_server(server):
    if not ID_RE.fullmatch(str(server or "")) or server == "main":
        return {"ok": False, "msg": "bad server id"}
    try:
        sfd, base = open_servers_dir()
    except OSError:
        return {"ok": False, "msg": "the servers folder is not a normal folder"}
    try:
        return _delete_server(server, base)
    finally:
        os.close(sfd)


def _delete_server(server, base):
    d = os.path.join(base, server)
    if os.path.islink(d) or not os.path.isdir(d):
        return {"ok": False, "msg": "no such server"}
    port = server_port(server)
    run(["systemctl", "disable", "--now", "beammp-server@%s" % server, "beammp-mods-apply@%s.path" % server], timeout=120)
    set_limits(server, 0, 0, 0)
    try:
        os.remove(os.path.join(LIMITS_DIR, server + ".conf"))
    except OSError:
        pass
    shutil.rmtree("/etc/systemd/system.control/beammp-server@%s.service.d" % server, ignore_errors=True)
    run(["systemctl", "daemon-reload"])
    run([LIB + "/secrets.sh", "unset", "BEAMMP_AUTH_KEY_" + server.upper()])
    try:
        os.remove("/var/lib/beammp-easyserver/applied-%s" % server)
    except OSError:
        pass
    if port:
        firewall_game(port, None, close_only=True)
    shutil.rmtree(d)
    return {"ok": True, "msg": "deleted"}


# ---------------------------------------------------------------- resource limits
def set_limits(server, cpu_cores, ram_mb, upload_kbps):
    try:
        unit = unit_for(server)
        cpu = float(cpu_cores or 0)
        ram = int(ram_mb or 0)
        up = int(upload_kbps or 0)
        assert 0 <= cpu <= 256 and 0 <= ram <= 1048576 and 0 <= up <= 10000000
    except (TypeError, ValueError, AssertionError):
        return {"ok": False, "msg": "bad limits"}
    props = ["CPUQuota=%d%%" % round(cpu * 100) if cpu else "CPUQuota=",
             "MemoryMax=%dM" % ram if ram else "MemoryMax=infinity"]
    r = run(["systemctl", "set-property", unit + ".service"] + props, timeout=60)
    msgs = []
    if r.returncode != 0:
        msgs.append("CPU/RAM limit failed: " + (r.stderr.strip()[-200:] or "?"))
    os.makedirs(LIMITS_DIR, exist_ok=True)
    conf = os.path.join(LIMITS_DIR, (server or "main") + ".conf")
    if up:
        with open(conf, "w") as f:
            f.write("UPLOAD_KBPS=%d\n" % up)
    elif os.path.exists(conf):
        os.remove(conf)
    msgs.append(shape())
    return {"ok": r.returncode == 0, "msg": "; ".join(m for m in msgs if m)}


SAFE_ROOT_QDISCS = ("fq_codel", "pfifo_fast", "mq", "noqueue", "fq ", "pfifo ")


def shape():
    """Rebuild the upload (mod download) speed limits with tc: one HTB class per
    limited server, matching TCP traffic sent from its port. Everything else goes
    through a 10 Gbit/s default class, i.e. is not slowed down."""
    rules = []
    try:
        names = sorted(os.listdir(LIMITS_DIR))
    except OSError:
        names = []
    for n in names:
        sid = n[:-5]
        if not n.endswith(".conf") or not (sid == "main" or ID_RE.fullmatch(sid)):
            continue
        try:
            with open(os.path.join(LIMITS_DIR, n)) as f:
                m = re.search(r"UPLOAD_KBPS=(\d+)", f.read())
            kbps, port = int(m.group(1)) if m else 0, server_port(sid)
        except OSError:
            continue
        if kbps and port:
            rules.append((port, kbps))
    if not shutil.which("tc") or not shutil.which("ip"):
        return "upload limit needs the 'tc' and 'ip' tools (package iproute2)" if rules else ""
    devs = []
    for fam in ("-4", "-6"):
        for line in run(["ip", fam, "-o", "route", "show", "default"]).stdout.splitlines():
            m = re.search(r"\bdev (\S+)", line)
            if m and m.group(1) not in devs:
                devs.append(m.group(1))
    notes = []
    for dev in devs:
        cur = run(["tc", "qdisc", "show", "dev", dev, "root"]).stdout
        ours = "htb 1: root" in cur and "default 0x270f" in cur
        if ours:
            run(["tc", "qdisc", "del", "dev", dev, "root"])
        elif rules and cur.strip() and not any(q in cur + " " for q in SAFE_ROOT_QDISCS):
            notes.append("%s already has custom traffic shaping - left it alone" % dev)
            continue
        if not rules:
            continue
        cmds = [["qdisc", "replace", "dev", dev, "root", "handle", "1:", "htb", "default", "9999"],
                ["class", "add", "dev", dev, "parent", "1:", "classid", "1:9999", "htb", "rate", "10gbit"],
                ["qdisc", "add", "dev", dev, "parent", "1:9999", "fq_codel"]]
        for i, (port, kbps) in enumerate(rules):
            c = "1:%d" % (10 + i)
            cmds += [["class", "add", "dev", dev, "parent", "1:", "classid", c, "htb", "rate", "%dkbit" % kbps, "ceil", "%dkbit" % kbps],
                     ["qdisc", "add", "dev", dev, "parent", c, "fq_codel"],
                     ["filter", "add", "dev", dev, "parent", "1:", "protocol", "ip", "prio", "1", "u32",
                      "match", "ip", "protocol", "6", "0xff", "match", "ip", "sport", str(port), "0xffff", "flowid", c],
                     ["filter", "add", "dev", dev, "parent", "1:", "protocol", "ipv6", "prio", "2", "u32",
                      "match", "ip6", "protocol", "6", "0xff", "match", "ip6", "sport", str(port), "0xffff", "flowid", c]]
        for c in cmds:
            r = run(["tc"] + c)
            if r.returncode != 0:
                notes.append("tc failed on %s: %s" % (dev, r.stderr.strip()[-160:]))
                run(["tc", "qdisc", "del", "dev", dev, "root"])
                break
    if rules and not notes:
        notes.append("upload limit active on " + ", ".join(devs) if devs else "no network interface found")
    return "; ".join(notes)


def read_env():
    env = {}
    try:
        with open(INSTALL_ENV) as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    env[k] = v
    except OSError:
        pass
    return env


def update_server():
    asset = read_env().get("ASSET", "")
    if not re.fullmatch(r"BeamMP-Server\.[a-z]+\.\d+(\.\d+)?\.(x86_64|arm64)", asset):
        return {"ok": False, "msg": "unknown server build - re-run the installer"}
    # The server folder belongs to the game server user, so the file is only
    # ever touched through the descriptor mkstemp gave us (never by name).
    fd, tmp = tempfile.mkstemp(dir=SERVER_DIR, prefix=".update-")
    try:
        req = urllib.request.Request(RELEASE_BASE + asset, headers={"User-Agent": "BeamMP-EasyServer"})
        with urllib.request.urlopen(req, timeout=300) as r, os.fdopen(fd, "wb", closefd=False) as f:
            shutil.copyfileobj(r, f)
            f.flush()
        os.lseek(fd, 0, 0)
        if os.read(fd, 4) != b"\x7fELF":
            return {"ok": False, "msg": "download was not a Linux program"}
        u = pwd.getpwnam("beammp")
        os.fchown(fd, u.pw_uid, u.pw_gid)
        os.fchmod(fd, 0o755)
        os.close(fd)
        fd = None
        units = ["beammp-server"] + ["beammp-server@%s" % x for x in sorted(os.listdir(SERVERS))
                                     if ID_RE.fullmatch(x)] if os.path.isdir(SERVERS) else ["beammp-server"]
        active = [u_ for u_ in units if run(["systemctl", "is-active", u_]).stdout.strip() == "active"]
        for u_ in active:
            systemctl("stop", u_)
        os.replace(tmp, os.path.join(SERVER_DIR, "BeamMP-Server"))
        for u_ in active:
            systemctl("start", u_)
        return {"ok": True, "msg": "updated"}
    except Exception as e:
        return {"ok": False, "msg": "update failed: %s" % e.__class__.__name__}
    finally:
        if fd is not None:
            os.close(fd)
        if os.path.lexists(tmp):
            os.remove(tmp)


def set_secret(name, value):
    if name not in SECRET_NAMES and not re.fullmatch(r"BEAMMP_AUTH_KEY_[A-Z0-9]{1,12}", str(name)):
        return {"ok": False, "msg": "unknown key name"}
    if not isinstance(value, str) or len(value) > 2048 or "\n" in value or "\r" in value:
        return {"ok": False, "msg": "invalid value"}
    if value:
        r = run([LIB + "/secrets.sh", "set", name], input=value + "\n")
    else:
        r = run([LIB + "/secrets.sh", "unset", name])
    return {"ok": r.returncode == 0, "msg": "saved" if r.returncode == 0 else "could not save"}


def firewall(state, port):
    try:
        port = int(port)
        assert 1024 <= port <= 65535
    except (TypeError, ValueError, AssertionError):
        return {"ok": False, "msg": "bad port"}
    msgs = []
    if shutil.which("ufw") and "Status: active" in run(["ufw", "status"]).stdout:
        if state == "on":
            run(["ufw", "allow", "%d/tcp" % port])
        else:
            run(["ufw", "delete", "allow", "%d/tcp" % port])
        msgs.append("Firewall (ufw): port %d %s" % (port, "opened" if state == "on" else "closed"))
    elif shutil.which("firewall-cmd") and run(["firewall-cmd", "--state"]).returncode == 0:
        flag = "--add-port" if state == "on" else "--remove-port"
        run(["firewall-cmd", "--permanent", "%s=%d/tcp" % (flag, port)])
        run(["firewall-cmd", "--reload"])
        msgs.append("Firewall (firewalld): port %d %s" % (port, "opened" if state == "on" else "closed"))
    return {"ok": True, "msg": ", ".join(msgs) or "No firewall is active on this computer - nothing to change"}


def firewall_game(old, new, close_only=False):
    """The game server port changed: open the new one (TCP + UDP), close the old one."""
    if close_only:
        try:
            old = int(old)
            assert 1024 <= old <= 65535
        except (TypeError, ValueError, AssertionError):
            return {"ok": False, "msg": "bad port"}
        if shutil.which("ufw") and "Status: active" in run(["ufw", "status"]).stdout:
            for proto in ("tcp", "udp"):
                run(["ufw", "delete", "allow", "%d/%s" % (old, proto)])
        elif shutil.which("firewall-cmd") and run(["firewall-cmd", "--state"]).returncode == 0:
            for proto in ("tcp", "udp"):
                run(["firewall-cmd", "--permanent", "--remove-port=%d/%s" % (old, proto)])
            run(["firewall-cmd", "--reload"])
        return {"ok": True, "msg": "closed %d" % old}
    try:
        new = int(new)
        assert 1024 <= new <= 65535
        old = int(old) if old not in (None, "") else None
        assert old is None or 1024 <= old <= 65535
    except (TypeError, ValueError, AssertionError):
        return {"ok": False, "msg": "bad port"}
    if old == new:
        return {"ok": True, "msg": "port unchanged"}
    if shutil.which("ufw") and "Status: active" in run(["ufw", "status"]).stdout:
        for proto in ("tcp", "udp"):
            run(["ufw", "allow", "%d/%s" % (new, proto)])
            if old:
                run(["ufw", "delete", "allow", "%d/%s" % (old, proto)])
        return {"ok": True, "msg": "Firewall (ufw): opened port %d%s" % (new, ", closed %d" % old if old else "")}
    if shutil.which("firewall-cmd") and run(["firewall-cmd", "--state"]).returncode == 0:
        for proto in ("tcp", "udp"):
            run(["firewall-cmd", "--permanent", "--add-port=%d/%s" % (new, proto)])
            if old:
                run(["firewall-cmd", "--permanent", "--remove-port=%d/%s" % (old, proto)])
        run(["firewall-cmd", "--reload"])
        return {"ok": True, "msg": "Firewall (firewalld): opened port %d%s" % (new, ", closed %d" % old if old else "")}
    return {"ok": True, "msg": "No firewall is active on this computer - nothing to change"}


def firewall_status():
    if shutil.which("ufw"):
        out = run(["ufw", "status"]).stdout
        if "Status: active" in out:
            rules = [l.strip() for l in out.splitlines() if re.match(r"\s*\d+(/\w+)?\s", l)]
            return {"ok": True, "data": "ufw is on. Rules: " + ("; ".join(rules[:12]) or "none")}
        return {"ok": True, "data": "ufw is installed but off - nothing is blocked"}
    if shutil.which("firewall-cmd") and run(["firewall-cmd", "--state"]).returncode == 0:
        return {"ok": True, "data": "firewalld is on. Open ports: " + run(["firewall-cmd", "--list-ports"]).stdout.strip()}
    return {"ok": True, "data": "No firewall active on this computer"}


def handle(req):
    a = req.get("action")
    if a in ("start", "stop", "restart"):
        return systemctl(a, unit_for(req.get("server")))
    if a == "create-server":
        return create_server(req.get("server"), req.get("config"), bool(req.get("start")))
    if a == "delete-server":
        return delete_server(req.get("server"))
    if a == "set-limits":
        return set_limits(req.get("server"), req.get("cpu_cores"), req.get("ram_mb"), req.get("upload_kbps"))
    if a == "update-server":
        return update_server()
    if a == "set-secret":
        return set_secret(req.get("name"), req.get("value", ""))
    if a == "unset-secret":
        return set_secret(req.get("name"), "")
    if a == "restart-dashboard":
        run(["systemd-run", "--no-block", "--on-active=2", "--unit=beammp-dashboard-restart-%d" % int(time.time()),
             "/bin/systemctl", "restart", "beammp-dashboard.service"])
        return {"ok": True, "msg": "restarting"}
    if a == "firewall-remote":
        return firewall(req.get("state"), req.get("port"))
    if a == "firewall-game":
        return firewall_game(req.get("old"), req.get("new"))
    if a == "firewall-status":
        return firewall_status()
    return {"ok": False, "msg": "unknown action"}


def main():
    try:
        dash_uid = pwd.getpwnam("beammp-dash").pw_uid
    except KeyError:
        sys.exit("user beammp-dash missing")
    os.makedirs(OUT, exist_ok=True)
    os.chmod(OUT, 0o755)
    # the request folder must belong to the dashboard user and nobody else
    st = os.lstat(IN)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != dash_uid or st.st_mode & 0o077:
        sys.exit("unsafe request folder")
    for _ in range(200):          # handle everything that is waiting
        names = sorted(n for n in os.listdir(IN) if n.endswith(".req"))
        if not names:
            break
        for n in names:
            path = os.path.join(IN, n)
            rid = n[:-4]
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            except OSError:
                try:
                    os.unlink(path)
                except OSError:
                    pass
                continue
            try:
                fst = os.fstat(fd)
                ok_file = stat.S_ISREG(fst.st_mode) and fst.st_uid == dash_uid and fst.st_size <= 65536
                raw = os.read(fd, 65537) if ok_file else b""
            finally:
                os.close(fd)
                try:
                    os.unlink(path)
                except OSError:
                    pass
            if not ok_file or not re.fullmatch(r"[a-f0-9]{32}", rid):
                continue
            try:
                req = json.loads(raw)
                if not isinstance(req, dict) or req.get("id") != rid:
                    raise ValueError
                res = handle(req)
            except Exception as e:
                res = {"ok": False, "msg": "bad request (%s)" % e.__class__.__name__}
            out = os.path.join(OUT, rid + ".json")
            with open(out + ".tmp", "w") as f:
                json.dump(res, f)
            os.chmod(out + ".tmp", 0o644)
            os.replace(out + ".tmp", out)
    # tidy up old answers
    for n in os.listdir(OUT):
        p = os.path.join(OUT, n)
        try:
            if time.time() - os.lstat(p).st_mtime > 600:
                os.unlink(p)
        except OSError:
            pass


if __name__ == "__main__":
    if sys.argv[1:] == ["--shape"]:
        if os.geteuid() == 0:
            print(shape() or "no upload limits")
        sys.exit(0)
    main()
