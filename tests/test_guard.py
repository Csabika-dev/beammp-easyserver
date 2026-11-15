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


if __name__ == "__main__":
    unittest.main()
