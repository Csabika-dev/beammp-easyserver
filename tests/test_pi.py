"""Raspberry Pi setup from the dashboard: finding it on the network, logging in over SSH once, then installing and
updating EasyServer on it. No real Pi or SSH: the network, ssh and the installer download are replaced by fakes."""
import io
import os
import shutil
import tempfile
import time
import types
import unittest
from unittest import mock

import harness  # noqa: F401  (sets up the throw-away server folder first)
from harness import D


WIN_ARP = """
Interface: 192.168.0.120 --- 0xb
  Internet Address      Physical Address      Type
  192.168.0.1           a4-91-b1-00-11-22     dynamic
  192.168.0.77          d8-3a-dd-11-22-33     dynamic
  192.168.0.255         ff-ff-ff-ff-ff-ff     static
"""
PROC_ARP = """IP address       HW type     Flags       HW address            Mask     Device
192.168.1.50     0x1         0x2         b8:27:eb:aa:bb:cc     *        wlan0
192.168.1.9      0x1         0x0         00:00:00:00:00:00     *        wlan0
"""
MAC_ARP = "? (10.0.0.8) at 2c:cf:67:1:2:3 on en0 ifscope [ethernet]\n? (10.0.0.1) at (incomplete) on en0 ifscope [ethernet]\n"


class PiDir(unittest.TestCase):
    """Each test gets its own empty Pi folder and no job or scan from another test."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for p in (mock.patch.object(D, "PI_DIR", self.dir), mock.patch.dict(D._PI, {"scan": None, "scanning": False, "job": None})):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(shutil.rmtree, self.dir, True)


class Basics(unittest.TestCase):
    def test_addresses(self):
        for ip in ("192.168.0.23", "10.1.2.3", "172.16.5.5"):
            self.assertTrue(D.pi_private(ip), ip)
        for ip in ("8.8.8.8", "127.0.0.1", "169.254.1.1", "0.0.0.0", "", "pi.local", "192.168.0.300", "fe80::1", None):
            self.assertFalse(D.pi_private(ip), ip)

    def test_mac(self):
        self.assertEqual(D.pi_mac("D8-3A-DD-1-2-33"), "d8:3a:dd:01:02:33")
        self.assertEqual(D.pi_mac("b8:27:eb:aa:bb:cc"), "b8:27:eb:aa:bb:cc")
        for bad in ("", "(incomplete)", "b8:27:eb:aa:bb", "gg:27:eb:aa:bb:cc"):
            self.assertEqual(D.pi_mac(bad), "")
        self.assertTrue(D.pi_is_pi("d8:3a:dd:01:02:33"))
        self.assertFalse(D.pi_is_pi("a4:91:b1:00:11:22"))
        self.assertFalse(D.pi_is_pi(""))

    def neighbors(self, txt, win):
        run = mock.Mock(return_value=types.SimpleNamespace(stdout=txt))
        with mock.patch.object(D, "IS_WIN", win), mock.patch.object(D.subprocess, "run", run), \
                mock.patch.object(D.os.path, "exists", lambda p: False if p == "/proc/net/arp" else os.path.exists(p)):
            return D.pi_neighbors()

    def test_arp_tables(self):
        self.assertEqual(self.neighbors(WIN_ARP, True), {"192.168.0.1": "a4:91:b1:00:11:22", "192.168.0.77": "d8:3a:dd:11:22:33"})
        self.assertEqual(self.neighbors(PROC_ARP, False), {"192.168.1.50": "b8:27:eb:aa:bb:cc"})
        self.assertEqual(self.neighbors(MAC_ARP, False), {"10.0.0.8": "2c:cf:67:01:02:03"})

    def test_no_arp(self):
        with mock.patch.object(D.subprocess, "run", side_effect=OSError("no arp")), mock.patch.object(D, "IS_WIN", True):
            self.assertEqual(D.pi_neighbors(), {})

    def test_quote(self):
        self.assertEqual(D.pi_quote("it's"), "'it'\"'\"'s'")

    def test_ssh_errors(self):
        self.assertIn("user name and password", D.pi_ssh_error("pi@192.168.0.5: Permission denied (publickey,password)."))
        self.assertIn("Enable SSH", D.pi_ssh_error("ssh: connect to host 192.168.0.5 port 22: Connection refused"))
        self.assertIn("Forget", D.pi_ssh_error("Host key verification failed."))
        self.assertIn("same Wi-Fi", D.pi_ssh_error("ssh: connect to host 192.168.0.5 port 22: Connection timed out"))
        self.assertEqual(D.pi_ssh_error("weird\nthing broke"), "Couldn't connect: thing broke")


class FakeProc:
    """Stands in for ssh: remembers what it was given and prints set lines."""
    made = []

    def __init__(self, args, env=None, stdin=None, stdout=None, stderr=None, **kw):
        self.args, self.env = args, env
        self.stdin = io.BytesIO()
        self.stdin.close = lambda: None
        self.stdout = iter([b"\x1b[32m[OK]\x1b[0m done\r\n", b"second\n"])
        ask = env.get("SSH_ASKPASS")
        self.askpass = None
        if ask:
            with open(ask) as f:
                self.askpass = f.read()
        FakeProc.made.append(self)

    def wait(self):
        return 0

    def kill(self):
        pass


class Ssh(PiDir):
    def setUp(self):
        super().setUp()
        FakeProc.made = []
        for p in (mock.patch.object(D, "pi_ssh_exe", lambda name="ssh": "/usr/bin/" + name),
                  mock.patch.object(D, "pi_key", lambda: (os.path.join(self.dir, "id_ed25519"), "ssh-ed25519 AAAA beammp-easyserver")),
                  mock.patch.object(D.subprocess, "Popen", FakeProc)):
            p.start()
            self.addCleanup(p.stop)

    def test_with_password(self):
        lines = []
        code, out = D.pi_ssh({"ip": "192.168.0.77", "user": "pi"}, "echo hi", password="p@ss 'word\"$", on_line=lines.append)
        self.assertEqual((code, out), (0, "[OK] done\nsecond"))
        self.assertEqual(lines, ["[OK] done", "second"])
        p = FakeProc.made[0]
        self.assertEqual(p.args[-2:], ["pi@192.168.0.77", "echo hi"])
        self.assertIn("PubkeyAuthentication=no", p.args)
        self.assertNotIn("BatchMode=yes", p.args)
        self.assertEqual(p.env["ES_SSH_PW"], "p@ss 'word\"$")
        self.assertEqual(p.env["SSH_ASKPASS_REQUIRE"], "force")
        self.assertNotIn("p@ss", p.askpass)                         # the password is never written to a file
        self.assertNotIn("p@ss", " ".join(p.args))                  # nor put on the command line
        self.assertFalse(os.path.exists(os.path.dirname(p.env["SSH_ASKPASS"])))   # and the helper is gone afterwards

    def test_with_key(self):
        D.pi_ssh({"ip": "192.168.0.77", "user": "pi"}, "true", stdin_data=b"#!/bin/sh\n")
        p = FakeProc.made[0]
        self.assertIn("BatchMode=yes", p.args)
        self.assertEqual(p.args[p.args.index("-i") + 1], os.path.join(self.dir, "id_ed25519"))
        self.assertNotIn("SSH_ASKPASS", p.env.keys() - os.environ.keys())
        self.assertEqual(p.stdin.getvalue(), b"#!/bin/sh\n")
        self.assertIn('UserKnownHostsFile="%s"' % os.path.join(self.dir, "known_hosts"), p.args)

    def test_no_ssh_client(self):
        with mock.patch.object(D, "pi_ssh_exe", lambda name="ssh": None):
            with self.assertRaises(RuntimeError):
                D.pi_ssh({"ip": "192.168.0.77", "user": "pi"}, "true")


def fake_ssh(replies, calls):
    """pi_ssh that answers each command with the first reply whose key is in it."""
    def ssh(pi, cmd, password=None, stdin_data=None, timeout=60, on_line=None):
        calls.append({"pi": dict(pi), "cmd": cmd, "password": password, "stdin": stdin_data})
        for key, (code, out) in replies.items():
            if key in cmd:
                for line in out.splitlines():
                    if on_line:
                        on_line(line)
                return code, out
        return 255, "ssh: connect to host %s port 22: Connection refused" % pi["ip"]
    return ssh


class Pair(PiDir):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(D, "pi_key", lambda: ("k", "ssh-ed25519 AAAA beammp-easyserver"))
        p.start()
        self.addCleanup(p.stop)

    def test_pair(self):
        calls = []
        replies = {"authorized_keys": (0, "ES_BITS=64 ES_HOST=garage-pi\nES_SUDO=1"), "ES_KEY_OK": (0, "ES_KEY_OK")}
        with mock.patch.object(D, "pi_ssh", fake_ssh(replies, calls)), \
                mock.patch.object(D, "pi_neighbors", lambda: {"192.168.0.77": "d8:3a:dd:11:22:33"}):
            pi = D.pi_pair("192.168.0.77", "pi", "secret")
        self.assertEqual(calls[0]["password"], "secret")
        self.assertIsNone(calls[1]["password"])                     # the second login is with the key
        self.assertIn("'ssh-ed25519 AAAA beammp-easyserver'", calls[0]["cmd"])
        self.assertEqual((pi["bits"], pi["host"], pi["sudo"], pi["mac"]), (64, "garage-pi", True, "d8:3a:dd:11:22:33"))
        saved = D.pi_saved()
        self.assertEqual([x["ip"] for x in saved], ["192.168.0.77"])
        with open(os.path.join(self.dir, "pis.json")) as f:
            self.assertNotIn("secret", f.read())

    def test_wrong_password(self):
        replies = {"authorized_keys": (255, "pi@192.168.0.77: Permission denied (password).")}
        with mock.patch.object(D, "pi_ssh", fake_ssh(replies, [])):
            with self.assertRaisesRegex(RuntimeError, "user name and password"):
                D.pi_pair("192.168.0.77", "pi", "nope")
        self.assertEqual(D.pi_saved(), [])

    def test_key_refused(self):
        replies = {"authorized_keys": (0, "ES_BITS=64 ES_HOST=p"), "ES_KEY_OK": (255, "Permission denied (publickey).")}
        with mock.patch.object(D, "pi_ssh", fake_ssh(replies, [])):
            with self.assertRaisesRegex(RuntimeError, "didn't accept this computer's key"):
                D.pi_pair("192.168.0.77", "pi", "secret")


class Url:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        return self.body


INSTALLER = b"#!/usr/bin/env bash\n# BeamMP EasyServer installer\n"
RUN_OUT = "  [OK] Dependencies installed\n  BeamMP EasyServer v1.16.0\n    Password:  Tr0ub4dor-x\n  [OK] Server is running!"


class Job(PiDir):
    def run_job(self, kind, pi, replies, body=INSTALLER, **kw):
        calls = []
        with mock.patch.object(D, "pi_ssh", fake_ssh(replies, calls)), \
                mock.patch.object(D.urllib.request, "urlopen", lambda req, timeout=0: Url(body)), \
                mock.patch.object(D, "pi_web", lambda ip: "https://%s:30815/" % ip):
            job = D.pi_job(kind, pi, **kw)
            for _ in range(200):
                if job["state"] != "running":
                    break
                time.sleep(0.02)
        return job, calls

    def test_install(self):
        D.pi_remember("192.168.0.77", user="pi", sudo=True, bits=64)
        pi = D.pi_saved()[0]
        job, calls = self.run_job("install", pi, {"ES_COPIED": (0, "ES_COPIED"), "--unattended": (0, RUN_OUT)},
                                  name="Pi's server")
        self.assertEqual(job["state"], "done", job)
        self.assertEqual(job["password"], "Tr0ub4dor-x")
        self.assertFalse(any("Tr0ub4dor" in x for x in job["lines"]))   # the log shows it masked
        self.assertEqual(calls[0]["stdin"], INSTALLER)
        run = calls[1]["cmd"]
        self.assertTrue(run.startswith("sudo -n bash ~/.easyserver-install.sh '--unattended'"), run)
        self.assertIn("'--name' 'Pi'\"'\"'s server'", run)
        self.assertIsNone(calls[1]["stdin"])
        saved = D.pi_saved()[0]
        self.assertEqual((saved["version"], saved["web"]), ("1.16.0", "https://192.168.0.77:30815/"))

    def test_update_with_sudo_password(self):
        pi = {"ip": "192.168.0.77", "user": "pi", "sudo": False}
        job, calls = self.run_job("update", pi, {"ES_COPIED": (0, "ES_COPIED"), "--unattended": (0, RUN_OUT)},
                                  name="ignored", sudo_pw="hunter2")
        self.assertEqual(job["state"], "done", job)
        self.assertTrue(calls[1]["cmd"].startswith("sudo -S -p '' bash"))
        self.assertNotIn("--name", calls[1]["cmd"])                  # an update keeps the server's name
        self.assertEqual(calls[1]["stdin"], "hunter2\n")
        self.assertNotIn("hunter2", calls[1]["cmd"])

    def test_installer_fails(self):
        pi = {"ip": "192.168.0.77", "user": "pi", "sudo": True}
        job, _ = self.run_job("update", pi, {"ES_COPIED": (0, "ES_COPIED"), "--unattended": (1, "[X] No space left")})
        self.assertEqual(job["state"], "failed")
        self.assertIn("last lines", job["error"])
        self.assertIn("[X] No space left", job["lines"])

    def test_bad_download(self):
        job, calls = self.run_job("update", {"ip": "192.168.0.77", "user": "pi", "sudo": True}, {}, body=b"<html>rate limited</html>")
        self.assertEqual(job["state"], "failed")
        self.assertIn("doesn't look right", job["error"])
        self.assertEqual(calls, [])                                   # nothing was sent to the Pi

    def test_pi_unreachable(self):
        job, _ = self.run_job("update", {"ip": "192.168.0.77", "user": "pi", "sudo": True}, {})
        self.assertEqual(job["state"], "failed")
        self.assertIn("Enable SSH", job["error"])


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class Api(PiDir):
    def setUp(self):
        super().setUp()
        self.c = harness.owner()
        self.addCleanup(lambda: D._TL.__dict__.pop("inst", None))

    def post(self, **body):
        return self.c.call("/api/pi", body)[:2]

    def test_checks(self):
        self.assertEqual(self.post(action="install", ip="8.8.8.8", user="pi", password="x")[0], 400)
        self.assertEqual(self.post(action="reboot", ip="192.168.0.77")[0], 400)
        self.assertEqual(self.post(action="update", ip="192.168.0.77")[0], 404)
        self.assertEqual(self.post(action="install", ip="192.168.0.77", user="Bad User", password="x")[0], 400)
        self.assertEqual(self.post(action="install", ip="192.168.0.77", user="pi", password="")[0], 400)
        D.pi_remember("192.168.0.60", user="pi", sudo=True, bits=32)
        st, d = self.post(action="update", ip="192.168.0.60")
        self.assertEqual(st, 400)
        self.assertIn("64-bit", d["error"])
        D.pi_remember("192.168.0.61", user="pi", sudo=False, bits=64)
        self.assertEqual(self.post(action="update", ip="192.168.0.61")[0], 400)   # needs its password for sudo

    def test_busy_and_forget(self):
        D.pi_remember("192.168.0.61", user="pi", sudo=True, bits=64)
        D._PI["job"] = {"kind": "install", "ip": "192.168.0.70", "state": "running", "lines": [], "password": "", "error": ""}
        self.assertEqual(self.post(action="update", ip="192.168.0.61")[0], 409)
        self.assertEqual(self.post(action="forget", ip="192.168.0.61")[0], 200)
        self.assertEqual(D.pi_saved(), [])

    def test_update_starts_job(self):
        D.pi_remember("192.168.0.61", user="pi", sudo=True, bits=64)
        started = []
        with mock.patch.object(D, "pi_job", lambda kind, pi, name="", sudo_pw=None: started.append((kind, pi["ip"], sudo_pw))):
            st, d = self.post(action="update", ip="192.168.0.61")
        self.assertEqual(st, 200, d)
        self.assertEqual(started, [("update", "192.168.0.61", None)])

    def test_status(self):
        D._PI["job"] = {"kind": "install", "ip": "192.168.0.70", "state": "done", "lines": [], "password": "pw-1234", "error": ""}
        with mock.patch.object(D, "pi_open", lambda ip, port, timeout=0.7: False):
            st, d = self.c.call("/api/pi")[:2]
        self.assertEqual(st, 200)
        self.assertEqual(d["job"]["password"], "pw-1234")              # the owner sees it
        self.assertIn("pis", d)

    def test_admin_cannot_set_up(self):
        self.assertIn("/api/pi", D.OWNER_WRITE)


if __name__ == "__main__":
    unittest.main()
