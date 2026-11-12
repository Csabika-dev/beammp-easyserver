"""The Linux root helper (linux/control.py) must refuse bad requests before it runs any command as root.
Runs without root: every command it would run is caught by a fake."""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "linux"))

try:
    import control as C
except ImportError:          # Windows: no pwd module - this helper is Linux-only anyway
    C = None


@unittest.skipUnless(C, "Linux only")
class RootHelper(unittest.TestCase):
    def setUp(self):
        self.ran = []
        p = mock.patch.object(C, "run", side_effect=lambda cmd, **kw: self.ran.append(cmd) or mock.Mock(returncode=1, stdout="", stderr=""))
        p.start()
        self.addCleanup(p.stop)
        for name in ("open_servers_dir", "_create_server", "_delete_server", "update_server"):
            q = mock.patch.object(C, name, side_effect=AssertionError("touched the real system: " + name))
            q.start()
            self.addCleanup(q.stop)

    def refused(self, req):
        r = C.handle(req)
        self.assertFalse(r.get("ok"), req)
        self.assertEqual(self.ran, [], "ran a command for a bad request: %r" % (req,))
        self.ran.clear()

    def test_unknown_action(self):
        self.refused({"action": "rm -rf /"})
        self.refused({"action": None})

    def test_server_ids(self):
        for bad in ("../etc", "main", "A", "x" * 13, "a/b", "", None, 5, "s1;reboot"):
            self.refused({"action": "create-server", "server": bad, "config": "[General]\nName='x'\n"})
            self.refused({"action": "delete-server", "server": bad})

    def test_server_config_checked(self):
        for bad in (None, "", "x", "no section here" * 3, "[General]" + "x" * 70000, 5):
            self.refused({"action": "create-server", "server": "s9", "config": bad})

    def test_secret_names(self):
        for bad in ("PATH", "LD_PRELOAD", "BEAMMP_AUTH_KEY_../x", "", None):
            self.refused({"action": "set-secret", "name": bad, "value": "x"})
        for bad in ("a\nb", "a\rb", "x" * 3000, 5):
            self.refused({"action": "set-secret", "name": "NTFY_TOPIC", "value": bad})

    def test_ports(self):
        for bad in (0, 22, 80, 70000, "30814; reboot", None, "x"):
            self.refused({"action": "firewall-remote", "state": "on", "port": bad})
            self.refused({"action": "firewall-game", "old": None, "new": bad})
        with mock.patch.object(C.shutil, "which", return_value="/usr/sbin/nft"):
            for bad in ([], [22], ["x"], list(range(2000, 2100)), None):
                r = C.flood_protect("on", bad or [])
                self.assertFalse(r.get("ok"), bad)
            self.ran.clear()

    def test_limits(self):
        with mock.patch.object(C.os.path, "isdir", return_value=True):
            for bad in ((-1, 0, 0), (0, -5, 0), (0, 0, -1), ("x", 0, 0), (1e9, 0, 0)):
                self.refused({"action": "set-limits", "server": "main", "cpu_cores": bad[0], "ram_mb": bad[1], "upload_kbps": bad[2]})

    def test_wake(self):
        for bad in ("eth0; reboot", "../../x", "", None, "a" * 20):
            self.refused({"action": "wol-enable", "iface": bad})
        with mock.patch.object(C.shutil, "which", return_value="/usr/sbin/rtcwake"):
            for bad in ("x", 1, 10 ** 12):
                self.refused({"action": "rtc-wake", "at": bad})


if __name__ == "__main__":
    unittest.main()
