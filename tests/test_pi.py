"""Raspberry Pi setup from the dashboard: finding it on the network, logging in over SSH once, then installing and
updating EasyServer on it. No real Pi or SSH: the network, ssh and the installer download are replaced by fakes."""
import base64
import hashlib
import io
import json
import lzma
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
        self.assertIn("turned off", D.pi_ssh_error("ssh: connect to host 192.168.0.5 port 22: Connection refused"))
        self.assertIn("Forget", D.pi_ssh_error("Host key verification failed."))
        self.assertIn("same network", D.pi_ssh_error("ssh: connect to host 192.168.0.5 port 22: Connection timed out"))
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
        self.banner = ""
        for p in (mock.patch.object(D, "pi_key", lambda: ("k", "ssh-ed25519 AAAA beammp-easyserver")),
                  mock.patch.object(D, "pi_banner", lambda ip: self.banner)):
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
            with self.assertRaisesRegex(RuntimeError, "didn't accept this dashboard's key"):
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
        self.assertIn("SSH is turned off", job["error"])


class Kinds(PiDir):
    """Which computers are found, and which can take EasyServer."""

    def test_banner(self):
        self.assertEqual(D.pi_os_from_banner("SSH-2.0-OpenSSH_for_Windows_9.5"), "windows")
        self.assertEqual(D.pi_os_from_banner("SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13.5"), "ubuntu")
        self.assertEqual(D.pi_os_from_banner("SSH-2.0-OpenSSH_9.2p1 Debian-2+deb12u3"), "debian")
        self.assertEqual(D.pi_os_from_banner("SSH-2.0-OpenSSH_7.9p1 Raspbian-10+deb10u2"), "raspbian")
        self.assertEqual(D.pi_os_from_banner("SSH-2.0-dropbear_2022.83"), "")      # a router: not listed
        self.assertEqual(D.pi_os_from_banner(""), "")

    def test_problems(self):
        ok = [{"os": "debian", "arch": "aarch64", "bits": 64}, {"os": "ubuntu", "arch": "x86_64", "bits": 64},
              {"os": "linuxmint", "os_like": "ubuntu,debian", "bits": 64}, {"os": "windows", "admin": True}, {}]
        for pi in ok:
            self.assertEqual(D.pi_problem(pi), "", pi)
        self.assertIn("TrueNAS", D.pi_problem({"os": "debian", "truenas": True}))
        self.assertIn("Ubuntu, Debian", D.pi_problem({"os": "fedora", "os_like": "rhel"}))
        self.assertIn("32-bit Raspberry Pi OS", D.pi_problem({"os": "debian", "bits": 32, "kind": "pi"}))
        self.assertIn("32-bit system", D.pi_problem({"os": "debian", "bits": 32, "kind": "pc"}))
        self.assertIn("processor", D.pi_problem({"os": "debian", "arch": "armv7l", "bits": 64}))
        self.assertIn("administrator", D.pi_problem({"os": "windows", "admin": False}))

    def test_scan(self):
        banners = {"192.168.0.10": "SSH-2.0-OpenSSH_for_Windows_9.5", "192.168.0.11": "SSH-2.0-OpenSSH_9.6p1 Ubuntu-3",
                   "192.168.0.12": "SSH-2.0-dropbear", "192.168.0.13": "SSH-2.0-OpenSSH_9.2p1 Debian-2"}
        with mock.patch.object(D, "pi_lan_ip", lambda: "192.168.0.120"), \
                mock.patch.object(D, "pi_banner", lambda ip: banners.get(ip, "")), \
                mock.patch.object(D, "pi_neighbors", lambda: {"192.168.0.13": "d8:3a:dd:00:00:01", "192.168.0.14": "dc:a6:32:00:00:02"}), \
                mock.patch.object(D, "pi_open", lambda ip, port, timeout=0.7: False), \
                mock.patch.object(D, "pi_hostname", lambda ip: "box" + ip.rsplit(".", 1)[1]), \
                mock.patch.object(D.socket, "gethostbyname", side_effect=OSError("no mdns")):
            r = D.pi_scan()
        got = {f["ip"]: (f["kind"], f["os"], f["ssh"], f["pi"]) for f in r["found"]}
        self.assertEqual(got, {"192.168.0.10": ("windows", "windows", True, False), "192.168.0.11": ("pc", "ubuntu", True, False),
                               "192.168.0.13": ("pi", "debian", True, True), "192.168.0.14": ("pi", "", False, True)})
        self.assertEqual(r["found"][0]["name"], "box10")

    def test_pair_linux_nas(self):
        out = ("ES_BITS=64 ES_HOST=nas ES_ARCH=x86_64 ES_UID=0\nES_OS=debian ES_LIKE=\nES_MODEL=\nES_OMV=1")
        with mock.patch.object(D, "pi_key", lambda: ("k", "ssh-ed25519 AAAA x")), mock.patch.object(D, "pi_banner", lambda ip: "SSH-2.0-OpenSSH_9.2p1 Debian"), \
                mock.patch.object(D, "pi_ssh", fake_ssh({"authorized_keys": (0, out), "ES_KEY_OK": (0, "ES_KEY_OK")}, [])), \
                mock.patch.object(D, "pi_neighbors", lambda: {}):
            pi = D.pi_pair("192.168.0.60", "root", "pw")
        self.assertEqual((pi["kind"], pi["root"], pi["sudo"], pi["omv"], pi["os"], pi["arch"]), ("nas", True, True, True, "debian", "x86_64"))
        self.assertEqual(D.pi_problem(pi), "")

    def test_pair_pi_model(self):
        out = "ES_BITS=64 ES_HOST=garage ES_ARCH=aarch64 ES_UID=1000\nES_OS=debian ES_LIKE=\nES_MODEL=Raspberry_Pi_5_Model_B_Rev_1.0\nES_SUDO=1"
        with mock.patch.object(D, "pi_key", lambda: ("k", "ssh-ed25519 AAAA x")), mock.patch.object(D, "pi_banner", lambda ip: ""), \
                mock.patch.object(D, "pi_ssh", fake_ssh({"authorized_keys": (0, out), "ES_KEY_OK": (0, "ES_KEY_OK")}, [])), \
                mock.patch.object(D, "pi_neighbors", lambda: {}):
            pi = D.pi_pair("192.168.0.50", "pi", "pw")
        self.assertEqual((pi["kind"], pi["model"], pi["root"]), ("pi", "Raspberry Pi 5 Model B Rev 1.0", False))

    def test_pair_windows(self):
        calls = []
        with mock.patch.object(D, "pi_key", lambda: ("k", "ssh-ed25519 AAAA beammp-easyserver")), \
                mock.patch.object(D, "pi_banner", lambda ip: "SSH-2.0-OpenSSH_for_Windows_9.5"), \
                mock.patch.object(D, "pi_ssh", fake_ssh({"EncodedCommand": (0, "ES_BITS=64\r\nES_HOST=LIVINGROOM\r\nES_ADMIN=1"),
                                                          "ES_KEY_OK": (0, "ES_KEY_OK")}, calls)), \
                mock.patch.object(D, "pi_neighbors", lambda: {}):
            pi = D.pi_pair("192.168.0.61", "Gamer", "pw")
        script = base64.b64decode(calls[0]["cmd"].rsplit(" ", 1)[1]).decode("utf-16-le")
        self.assertIn("$k = 'ssh-ed25519 AAAA beammp-easyserver'", script)
        self.assertIn("administrators_authorized_keys", script)
        self.assertIn("*S-1-5-32-544:F", script)                    # by SID: the group name depends on Windows' language
        self.assertEqual((pi["os"], pi["kind"], pi["admin"], pi["sudo"], pi["host"]), ("windows", "windows", True, True, "LIVINGROOM"))


class WinJob(PiDir):
    def test_windows_install_and_update(self):
        for kind, pw in (("install", "winpw"), ("update", None)):
            calls = []
            with mock.patch.object(D, "pi_ssh", fake_ssh({"EncodedCommand": (0, "  BeamMP EasyServer v1.16.0 - installing\n    Password:  Abc123def456ghjk")}, calls)), \
                    mock.patch.object(D, "pi_web", lambda ip: "http://%s:30815/" % ip):
                job = D.pi_job(kind, {"ip": "192.168.0.61", "user": "Gamer", "os": "windows", "sudo": True}, name="Bob's", sudo_pw=pw)
                for _ in range(200):
                    if job["state"] != "running":
                        break
                    time.sleep(0.02)
            self.assertEqual(job["state"], "done", job)
            self.assertEqual(job["password"], "Abc123def456ghjk")
            self.assertEqual(calls[0]["password"], pw)                # the first install logs in with the password
            script = base64.b64decode(calls[0]["cmd"].rsplit(" ", 1)[1]).decode("utf-16-le")
            self.assertIn("archive/refs/heads/main.zip", script)
            if kind == "install":
                self.assertIn("-Unattended -ServerName 'Bob''s'", script)
            else:
                self.assertIn("-Unattended -Update", script)
                self.assertNotIn("ServerName", script)

    def test_root_needs_no_sudo(self):
        calls = []
        with mock.patch.object(D, "pi_ssh", fake_ssh({"ES_COPIED": (0, "ES_COPIED"), "--unattended": (0, RUN_OUT)}, calls)), \
                mock.patch.object(D.urllib.request, "urlopen", lambda req, timeout=0: Url(INSTALLER)), \
                mock.patch.object(D, "pi_web", lambda ip: ""):
            job = D.pi_job("update", {"ip": "192.168.0.60", "user": "root", "root": True, "sudo": True})
            for _ in range(200):
                if job["state"] != "running":
                    break
                time.sleep(0.02)
        self.assertEqual(job["state"], "done", job)
        self.assertTrue(calls[1]["cmd"].startswith("bash ~/.easyserver-install.sh"), calls[1]["cmd"])


class Card(PiDir):
    """The ready-to-go SD card: hashes, the setup files, the image list, the card list and the writer."""

    def test_hashes(self):
        self.assertEqual(D.sha512_crypt("Hello world!", "saltstring"),
                         "$6$saltstring$svn8UoSVapNtMuq1ukKS4tPQd8iKwSMHWjl/O817G3uBnIFNjnQJuesI68u4OTLiBFdcbYEdFCoEOfaS35inz1")
        self.assertEqual(D.sha512_crypt("Hello world!", "saltstringsaltstring", 10000),
                         "$6$rounds=10000$saltstringsaltst$OW1/O6BYHV6BcXZu8QVeXbDWra3Oeqh0sbHbbMCVNSnCM/UrjmM0Dp8vOuZeHBy/YTBmSK6H9qs/y3RnOaw5v.")
        self.assertEqual(D.sha512_crypt("This is just a test", "toolongsaltstring", 5000),
                         "$6$toolongsaltstrin$lQ8jolhgVRVhY4b5pZKaysCLi0QBxGoNeKQzQ3glMhwllF7oGDZxUhx1yxdYcz/e1JSbq3y6JMxxl8audkUEm0")
        h = D.sha512_crypt("pw")
        self.assertTrue(h.startswith("$6$") and len(h.split("$")[2]) == 16)
        self.assertNotEqual(D.sha512_crypt("pw"), h)                  # a new salt each time
        self.assertEqual(D.pi_psk("IEEE", "password"), "f42c6fc52df0ebef9ebb4b90b38a5f902e83fe1b135a70e23aed762e9710a12e")

    def test_files(self):
        files, cmdline = D.pi_card_files("beammp-pi-ab12", "beammp", "$6$salt$hash", "ssh-ed25519 AAAA key", 'My "Wi-Fi"',
                                         "ab" * 32, "HU")
        ud = files["user-data"]
        self.assertTrue(ud.startswith("#cloud-config\n"))
        for line in ('hostname: "beammp-pi-ab12"', 'name: "beammp"', 'passwd: "$6$salt$hash"', '- "ssh-ed25519 AAAA key"',
                     "sudo: ALL=(ALL) NOPASSWD:ALL", "ssh_pwauth: true", "[ systemctl, enable, --now, ssh ]"):
            self.assertIn(line, ud)
        nc = files["network-config"]
        self.assertIn('"My \\"Wi-Fi\\"":', nc)                         # quotes in the Wi-Fi name stay inside the string
        self.assertIn('password: "%s"' % ("ab" * 32), nc)
        self.assertIn('regulatory-domain: "HU"', nc)
        iid = files["meta-data"].split(": ")[1].strip()
        self.assertEqual(cmdline, " ds=nocloud;i=" + iid)
        files, _ = D.pi_card_files("h", "u", "x", "k")                    # cable only: no Wi-Fi file
        self.assertNotIn("network-config", files)
        files, _ = D.pi_card_files("h", "u", "x", "k", "Open", "", "HU")  # an open Wi-Fi
        self.assertIn("key-management: none", files["network-config"])

    def oslist(self, entry):
        body = json.dumps({"os_list": [{"name": "Raspberry Pi OS (other)", "subitems": [entry]}]}).encode()
        return mock.patch.object(D.urllib.request, "urlopen", lambda req, timeout=0: Url(body))

    def test_image_list(self):
        good = {"name": "Raspberry Pi OS Lite (64-bit)", "url": "https://downloads.raspberrypi.com/x/2026-10-06-raspios-trixie-arm64-lite.img.xz",
                "extract_size": 3078619136, "extract_sha256": "AB" * 32, "image_download_size": 550466056,
                "release_date": "2026-10-06", "init_format": "cloudinit-rpi"}
        with self.oslist(good):
            img = D.pi_card_image()
        self.assertEqual((img["sha256"], img["size"], img["download"]), ("ab" * 32, 3078619136, 550466056))
        for bad in ({"url": "https://evil.example/x.img.xz"}, {"url": "http://downloads.raspberrypi.com/x.img.xz"},
                    {"init_format": "systemd"}, {"name": "Something else"}):
            with self.oslist({**good, **bad}):
                with self.assertRaises(RuntimeError):
                    D.pi_card_image()

    def test_disk_filter(self):
        rows = [{"n": 0, "model": "Samsung SSD", "size": 500e9, "media": "Fixed hard disk media", "bus": "SCSI", "letters": ["C:"]},
                {"n": 1, "model": "SD reader", "size": 31.9e9, "media": "Removable Media", "bus": "USB", "letters": ["E:"]},
                {"n": 2, "model": "USB disk", "size": 2e12, "media": "External hard disk media", "bus": "USB", "letters": ["F:"]},
                {"n": 3, "model": "Stick", "size": 16e9, "media": "Removable Media", "bus": "USB", "letters": ["C:"]},
                {"n": 4, "model": "Tiny", "size": 2e9, "media": "Removable Media", "bus": "USB", "letters": []},
                {"n": 5, "model": "Empty reader", "size": None, "media": "Removable Media", "bus": "USB", "letters": []},
                "junk"]
        with mock.patch.dict(os.environ, {"SystemDrive": "C:"}):
            self.assertEqual([d["n"] for d in D.pi_disk_filter(rows)], [1])

    def make_image(self, size=9 * 1024 * 1024 + 512):
        raw = (b"\x5a" * 4096 + os.urandom(4096)) * (size // 8192) + b"\x01" * (size % 8192)
        xz = os.path.join(self.dir, "os.img.xz")
        with open(xz, "wb") as f:
            f.write(lzma.compress(raw[:size // 2]) + lzma.compress(raw[size // 2:]))     # two xz streams, like xz -T
        return raw, xz

    def test_check_download(self):
        raw, xz = self.make_image()
        job = {}
        D.pi_card_check(xz, {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}, job)
        self.assertEqual(job["progress"], 99)
        with self.assertRaisesRegex(RuntimeError, "damaged"):
            D.pi_card_check(xz, {"sha256": "00" * 32, "size": len(raw)}, job)
        self.assertFalse(os.path.exists(xz))                             # a damaged download is deleted

    def test_writer(self):
        raw, xz = self.make_image()
        helper = {}
        exec(compile(D.PI_CARD_HELPER, "cardwriter", "exec"), helper)
        dev = os.path.join(self.dir, "card.bin")
        with open(dev, "wb") as f:
            f.write(b"\xff" * (len(raw) + 4096))                        # the old contents of the card
        seen = []
        helper["write_image"](xz, dev, len(raw), hashlib.sha256(raw).hexdigest(), seen.append)
        with open(dev, "rb") as f:
            self.assertEqual(f.read(len(raw)), raw)
        self.assertEqual(seen[-1], 99)
        with self.assertRaisesRegex(RuntimeError, "didn't take the data"):
            helper["write_image"](xz, dev, len(raw), "00" * 32)


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
        self.assertEqual(self.post(action="install", ip="192.168.0.77", user="bad;user", password="x")[0], 400)
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

    def test_card_checks(self):
        self.assertEqual(self.post(action="card")[0], 400)                 # not on Linux
        disk = {"n": 1, "model": "SD", "size": 32e9, "letters": ["E:"]}
        good = dict(action="card", user="beammp", password="longenough", ssid="Home", wifi_password="wifipass1",
                    country="hu", disk=1, erase_ok=True, name="Pi")
        made = []
        with mock.patch.object(D, "IS_WIN", True), mock.patch.object(D, "pi_disks", lambda: [disk]), \
                mock.patch.object(D, "pi_card_job", made.append), mock.patch.object(D, "pi_key", lambda: ("k", "ssh-ed25519 AAAA x")):
            for bad in ({"user": "Root"}, {"user": "root"}, {"password": "short"}, {"wifi_password": "short"},
                        {"country": "Hungary"}, {"erase_ok": False}, {"disk": 7}):
                st, d = self.post(**{**good, **bad})
                self.assertEqual(st, 400, (bad, d))
            self.assertEqual(made, [])
            st, d = self.post(**good)
        self.assertEqual(st, 200, d)
        o = made[0]
        self.assertEqual((o["user"], o["country"], o["disk"]["n"], o["ssid"]), ("beammp", "HU", 1, "Home"))
        self.assertTrue(o["pw_hash"].startswith("$6$"))
        self.assertEqual(o["psk"], D.pi_psk("Home", "wifipass1"))
        self.assertNotIn("longenough", json.dumps(o))                     # neither password itself goes any further
        self.assertNotIn("wifipass1", json.dumps(o))
        self.assertRegex(o["host"], r"^beammp-pi-[0-9a-f]{4}$")


if __name__ == "__main__":
    unittest.main()
