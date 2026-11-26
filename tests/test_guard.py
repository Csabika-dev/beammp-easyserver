"""BeamMP-only guard: who gets blocked, and the dashboard side of it."""
import os
import unittest
from unittest import mock

import harness
from harness import D

G = D.guard
SCAN = "45.33.32.156"
PLAYER = "84.2.40.11"


class Decisions(unittest.TestCase):
    def knock(self, g, ip, n, t0=1000.0, port=40000):
        new = []
        for i in range(n):
            t = t0 + i * 10
            new += g.see([(ip, port + i, "SYN_RECV")], t)
            new += g.see([], t + 1)
        return new

    def test_scanner_is_blocked(self):
        g = G.Guard()
        self.assertEqual(self.knock(g, SCAN, G.STRIKES - 1), [])
        self.assertEqual(self.knock(g, SCAN, 1, t0=1000 + G.STRIKES * 10), [SCAN])
        self.assertIn(SCAN, g.block_list())
        self.assertAlmostEqual(g.blocked[SCAN]["until"] - g.blocked[SCAN]["at"], 3600)

    def test_player_who_stays_is_never_blocked(self):
        g = G.Guard()
        g.see([(PLAYER, 5000, "ESTABLISHED")], 1000)
        g.see([(PLAYER, 5000, "ESTABLISHED")], 1000 + G.STAY + 1)
        g.see([], 1100)
        self.assertEqual(self.knock(g, PLAYER, G.STRIKES * 2, t0=1200), [])     # e.g. a wrong mod version, retrying

    def test_home_network_ignored(self):
        g = G.Guard()
        for ip in ("192.168.1.50", "10.0.0.3", "127.0.0.1", "::1", "100.64.1.1"):
            self.assertEqual(self.knock(g, ip, G.STRIKES * 2), [])

    def test_slow_knocks_are_forgiven(self):
        g = G.Guard()
        new = []
        for i in range(G.STRIKES * 2):
            t = 1000 + i * (G.WINDOW // 2)
            new += g.see([(SCAN, 1, "SYN_RECV")], t) + g.see([], t + 1)
        self.assertEqual(new, [])

    def test_block_expires_and_repeat_offender_gets_longer(self):
        g = G.Guard()
        self.knock(g, SCAN, G.STRIKES)
        g.expire(1000 + 3700 + 200)
        self.assertEqual(g.block_list(), [])
        self.knock(g, SCAN, G.STRIKES, t0=10000)
        b = g.blocked[SCAN]
        self.assertEqual(b["times"], 2)
        self.assertAlmostEqual(b["until"] - b["at"], 6 * 3600)
        g2 = G.Guard(g.state())                    # survives a dashboard restart
        self.assertIn(SCAN, g2.block_list())

    def test_old_blocks_are_forgotten_after_30_days(self):
        g = G.Guard()
        self.knock(g, SCAN, G.STRIKES)
        end = g.blocked[SCAN]["until"]
        g.expire(end + 1)
        self.assertEqual(g._times(SCAN), 1)
        g.expire(end + G.HISTORY_FOR - 60)
        self.assertEqual(g._times(SCAN), 1)
        g.expire(end + G.HISTORY_FOR + 60)
        self.assertEqual(g._times(SCAN), 0)
        self.assertNotIn(SCAN, g.state()["history"])

    def test_history_saved_by_older_versions_still_loads(self):
        g = G.Guard({"history": {SCAN: 2}})        # just the count, no date
        self.assertEqual(g._times(SCAN), 2)
        g.expire()
        self.assertEqual(g._times(SCAN), 2)        # its 30 days start now

    def test_unblock_vouches(self):
        g = G.Guard()
        self.knock(g, SCAN, G.STRIKES)
        self.assertTrue(g.unblock(SCAN))
        self.assertEqual(self.knock(g, SCAN, G.STRIKES * 2, t0=5000), [])

    def test_ipv4_mapped(self):
        self.assertEqual(G.norm_ip("::ffff:45.33.32.156"), SCAN)
        self.assertIsNone(G.norm_ip("nope"))

    def test_proc_table(self):
        text = ("  sl  local_address rem_address   st\n"
                "   0: 00000000:787E 00000000:0000 0A\n"                       # listening on 30846: ignored
                "   1: 0100A8C0:787E 9C20212D:9C40 03\n"                       # 45.33.32.156:40000 -> :30846 SYN_RECV
                "   2: 0100A8C0:1F90 9C20212D:9C41 01\n")                      # other port
        self.assertEqual(G.parse_proc(text, {30846}), [(SCAN, 40000, "SYN_RECV")])

    def test_block_file(self):
        p = os.path.join(harness.TMP if hasattr(harness, "TMP") else "/tmp", "guard-test.txt")
        G.write_block_file(p, [30814, 30814, 30816], [SCAN])
        with open(p) as f:
            self.assertEqual(f.read(), "ports=30814,30816\n%s\n" % SCAN)


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class Endpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()

    def setUp(self):
        self.calls = []
        p = mock.patch.object(D, "control", lambda action, **kw: self.calls.append((action, kw)) or {"ok": True})
        p.start()
        self.addCleanup(p.stop)
        D.APP.guard = G.Guard()
        D.APP.guard_applied = None
        self.addCleanup(lambda: D.APP.settings.update({"guard_on": False}))

    def test_off_by_default(self):
        self.assertFalse(D.DEFAULT_SETTINGS["guard_on"])
        st, d, _ = self.owner.call("/api/guard")
        self.assertEqual(st, 200)
        self.assertFalse(d["on"])

    def test_block_and_unblock(self):
        self.owner.call("/api/settings", {"guard_on": True})
        D.APP.guard.blocked[SCAN] = {"until": D.now() + 3600, "at": D.now(), "times": 1, "why": "test"}
        D.APP.guard_apply()
        action, kw = self.calls[-1]
        self.assertEqual(action, "guard-block")
        self.assertEqual(kw["ips"], [SCAN])
        st, d, _ = self.owner.call("/api/guard")
        self.assertEqual(d["count"], 1)
        st, d, _ = self.owner.call("/api/guard", {"unblock": SCAN})
        self.assertEqual(st, 200, d)
        self.assertEqual(self.calls[-1][1]["ips"], [])
        st, d, _ = self.owner.call("/api/guard", {"unblock": "not an ip"})
        self.assertEqual(st, 400)

    def test_turning_off_clears_the_firewall(self):
        self.owner.call("/api/settings", {"guard_on": True})
        D.APP.guard.blocked[SCAN] = {"until": D.now() + 3600, "at": D.now(), "times": 1, "why": "test"}
        D.APP.guard_apply()
        D.APP.settings.update({"guard_on": False})
        D.APP.guard_apply()
        self.assertEqual(self.calls[-1][1], {"ports": [], "ips": [], "timeout": 30})

    def test_viewer_cannot_unblock(self):
        self.assertEqual(D.required_role("POST", "/api/guard"), "admin")




@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class UpdateChannel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        harness.start()
        cls.owner = harness.owner()

    def test_switch_channel(self):
        self.addCleanup(lambda: D.APP.settings.update({"early_access": True}))
        paid = mock.patch.object(D, "PAID_FEATURES", True); paid.start(); self.addCleanup(paid.stop)
        with mock.patch.object(D, "github_latest", lambda repo: "1.13.0"), \
                mock.patch.object(D, "github_prerelease", lambda repo: ("9.9.9", "https://example.invalid/x")):
            with mock.patch.object(D, "supporter_active", lambda: False):
                st, d, _ = self.owner.call("/api/updates/check", {"channel": "experimental"})
                self.assertEqual(st, 403)                       # supporters only
                st, d, _ = self.owner.call("/api/updates")
                self.assertEqual(d["channel"], "stable")
                self.assertNotIn("easy_early", d)
            with mock.patch.object(D, "supporter_active", lambda: True):
                st, d, _ = self.owner.call("/api/updates/check", {"channel": "nightly"})
                self.assertEqual(st, 400)
                st, d, _ = self.owner.call("/api/updates/check", {"channel": "experimental"})
                self.assertEqual(st, 200, d)
                self.assertEqual(d["easy_early"], "9.9.9")
                st, d, _ = self.owner.call("/api/updates/check", {"channel": "stable"})
                self.assertNotIn("easy_early", d)
                st, d, _ = self.owner.call("/api/updates")
                self.assertEqual(d["channel"], "stable")

    def test_rolling_for_everyone_when_free(self):
        self.addCleanup(lambda: D.APP.settings.update({"rolling": False}))
        with mock.patch.object(D, "PAID_FEATURES", False), \
                mock.patch.object(D, "supporter_active", lambda: False), \
                mock.patch.object(D, "github_latest", lambda repo: "1.13.0"), \
                mock.patch.object(D, "rolling_version", lambda repo: ("9.9.9", "https://example.invalid/main.zip")):
            st, d, _ = self.owner.call("/api/updates")
            self.assertEqual(d["channel"], "stable")
            self.assertFalse(d["paid"])
            st, d, _ = self.owner.call("/api/updates/check", {"channel": "experimental"})
            self.assertEqual(st, 200, d)                        # no supporter licence needed
            self.assertEqual(d["easy_early"], "9.9.9")
            self.assertTrue(D.APP.settings.get("rolling"))
            st, d, _ = self.owner.call("/api/supporter")
            self.assertEqual(d, {"off": True})                  # supporter box hidden
            st, d, _ = self.owner.call("/api/updates/check", {"channel": "stable"})
            self.assertNotIn("easy_early", d)

    def test_rolling_version_reads_main(self):
        class R:
            def __init__(self, b): self.b = b
            def read(self, n=-1): return self.b
            def __enter__(self): return self
            def __exit__(self, *a): return False
        body = b'#!/usr/bin/env python3\nEASY_VERSION = "1.15.0"\nREPO = "x/y"\n'
        with mock.patch.object(D.urllib.request, "urlopen", lambda req, timeout=0: R(body)):
            v, url = D.rolling_version("x/y")
        self.assertEqual(v, "1.15.0")
        self.assertTrue(url.endswith("/x/y/archive/refs/heads/main.zip"))


class AtServer(unittest.TestCase):
    def test_loopback_counts_everywhere_else(self):
        with mock.patch.object(D, "host_info", lambda: {}):
            self.assertTrue(D.at_server("127.0.0.1"))
            self.assertTrue(D.at_server("::ffff:127.0.0.1"))
            self.assertFalse(D.at_server("192.168.1.20"))


class MacHost(unittest.TestCase):
    """EasyServer on a Mac: the Linux server runs in a small VM and the Mac tells the dashboard about itself."""

    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()

    def setUp(self):
        info = {"platform": "mac", "lan_ip": "192.168.1.50", "ports": "auto", "upnp": "ok", "upnp_at": 1794700000}
        p = mock.patch.object(D, "host_info", lambda: info)
        p.start()
        self.addCleanup(p.stop)

    def test_lan_ip_is_the_macs(self):
        self.assertTrue(D.on_mac())
        self.assertEqual(D.lan_ip(), "192.168.1.50")

    def test_upnp_card_comes_from_the_mac(self):
        st, d, _ = self.owner.call("/api/upnp")
        self.assertEqual(st, 200, d)
        self.assertTrue(d["mac"])
        self.assertTrue(d["on"])
        self.assertEqual(d["mac_upnp"], "ok")
        self.assertEqual(d["mac_ip"], "192.168.1.50")
        st, d, _ = self.owner.call("/api/upnp", {"on": True})
        self.assertEqual(st, 400)                       # the VM can't reach the router: the Mac does it
        st, d, _ = self.owner.call("/api/upnp", {"open_for": 7200})
        self.assertEqual(st, 200)                       # Copy invite keeps working

    def test_local_address_is_not_trusted_on_a_mac(self):
        # every device reaches the VM through the Mac's port forwarder as 127.0.0.1
        self.assertFalse(D.at_server("127.0.0.1"))
        self.assertFalse(D.at_server("::1"))
        st, d, _ = self.owner.call("/api/remote", {"remote_enabled": True})
        self.assertEqual(st, 400, d)
        self.assertIn("Mac", d["error"])

    def test_guard_is_off_on_a_mac(self):
        st, d, _ = self.owner.call("/api/guard")
        self.assertTrue(d["mac"])
        self.assertEqual(d["platform"], "mac")
        st, d, _ = self.owner.call("/api/settings", {"guard_on": True})
        self.assertEqual(st, 400)
        self.assertFalse(D.APP.settings.get("guard_on"))

    def test_bad_address_is_ignored(self):
        with mock.patch.object(D, "host_info", lambda: {"platform": "mac", "lan_ip": "not-an-ip"}):
            self.assertNotEqual(D.lan_ip(), "not-an-ip")


class HostFile(unittest.TestCase):
    def test_reads_and_caches(self):
        import json, tempfile
        d = tempfile.mkdtemp()
        path = os.path.join(d, "host.json")
        with open(path, "w") as f:
            json.dump({"platform": "mac", "lan_ip": "10.0.0.7"}, f)
        with mock.patch.object(D, "HOST_FILE", path), mock.patch.dict(D._HOST, {"t": 0.0, "v": {}}):
            self.assertEqual(D.host_info()["lan_ip"], "10.0.0.7")
            os.remove(path)
            self.assertEqual(D.host_info()["lan_ip"], "10.0.0.7")     # cached for 30 s
        with mock.patch.object(D, "HOST_FILE", path), mock.patch.dict(D._HOST, {"t": 0.0, "v": {}}):
            self.assertEqual(D.host_info(), {})                       # no file: not a Mac
            self.assertFalse(D.on_mac())


if __name__ == "__main__":
    unittest.main()


class DashboardLog(unittest.TestCase):
    """The Windows log file (it has visitors' addresses) rolls over instead of growing forever."""
    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "dashboard.log")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_rolls_at_the_size_limit(self):
        log = D.RollingLog(self.path)
        with mock.patch.object(D.RollingLog, "MAX", 200):
            log.write("x" * 300 + "\n")
            log.next_check = 0
            log.write("after\n")
        log.f.close()
        self.assertTrue(os.path.exists(self.path + ".1"))
        with open(self.path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("after", text)
        self.assertNotIn("xxx", text)

    def test_rolls_after_30_days(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("2020-01-01 10:00:00 log started\nold line 1.2.3.4\n")
        log = D.RollingLog(self.path)
        log.write("new\n")
        log.f.close()
        with open(self.path, encoding="utf-8") as f:
            self.assertNotIn("1.2.3.4", f.read())
        with open(self.path + ".1", encoding="utf-8") as f:
            self.assertIn("1.2.3.4", f.read())

    def test_a_fresh_log_is_kept(self):
        log = D.RollingLog(self.path)
        log.write("hello\n")
        log.f.close()
        self.assertFalse(os.path.exists(self.path + ".1"))
