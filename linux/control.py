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
SECRET_NAMES = {"MODS_PASSWORD", "VT_API_KEY", "DISCORD_WEBHOOK", "SMTP_PASSWORD", "TOTP_SECRET", "BEAMMP_AUTH_KEY"}
RELEASE_BASE = "https://github.com/BeamMP/BeamMP-Server/releases/latest/download/"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=kw.pop("timeout", 120), **kw)


def systemctl(action, unit="beammp-server"):
    r = run(["systemctl", action, unit], timeout=90)
    return {"ok": r.returncode == 0, "msg": "done" if r.returncode == 0 else (r.stderr.strip()[-300:] or "failed")}


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
    fd, tmp = tempfile.mkstemp(dir=SERVER_DIR, prefix=".update-")
    os.close(fd)
    try:
        req = urllib.request.Request(RELEASE_BASE + asset, headers={"User-Agent": "BeamMP-EasyServer"})
        with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        with open(tmp, "rb") as f:
            if f.read(4) != b"\x7fELF":
                return {"ok": False, "msg": "download was not a Linux program"}
        u = pwd.getpwnam("beammp")
        os.chown(tmp, u.pw_uid, u.pw_gid)
        os.chmod(tmp, 0o755)
        was_active = run(["systemctl", "is-active", "beammp-server"]).stdout.strip() == "active"
        if was_active:
            systemctl("stop")
        os.replace(tmp, os.path.join(SERVER_DIR, "BeamMP-Server"))
        if was_active:
            systemctl("start")
        return {"ok": True, "msg": "updated"}
    except Exception as e:
        return {"ok": False, "msg": "update failed: %s" % e.__class__.__name__}
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def set_secret(name, value):
    if name not in SECRET_NAMES:
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
        msgs.append("ufw updated")
    elif shutil.which("firewall-cmd") and run(["firewall-cmd", "--state"]).returncode == 0:
        flag = "--add-port" if state == "on" else "--remove-port"
        run(["firewall-cmd", "--permanent", "%s=%d/tcp" % (flag, port)])
        run(["firewall-cmd", "--reload"])
        msgs.append("firewalld updated")
    return {"ok": True, "msg": ", ".join(msgs) or "no active firewall"}


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
        return systemctl(a)
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
    main()
