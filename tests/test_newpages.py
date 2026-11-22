"""Lap times, player profiles, the setup checklist, performance history and the join box."""
import json
import os
import time
import unittest

import harness
from harness import D


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class NewPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()

    def stats(self, name):
        return os.path.join(D.INSTANCES["main"].STATS_DIR, name)

    def read(self, name):
        with open(self.stats(name)) as f:
            return f.read()

    def write(self, name, text):
        with open(self.stats(name), "w") as f:
            f.write(text)
        self.addCleanup(lambda: os.path.exists(self.stats(name)) and os.remove(self.stats(name)))

    def test_lap_times(self):
        self.addCleanup(lambda: os.path.exists(self.stats("laps.txt")) and os.remove(self.stats("laps.txt")))
        st, d, _ = self.owner.call("/api/laps", {"on": True, "radius": 20})
        self.assertEqual(st, 200)
        self.assertIn("mode=on\nradius=20", self.read("laps.txt"))
        self.assertEqual(self.owner.call("/api/laps", {"radius": 7})[0], 400)
        self.write("tracks.tsv", "a1\tRing\t/levels/gridmap_v2/info.json\tloop\t0.00,0.00,0.00;300.00,0.00,0.00;300.00,300.00,0.00\n"
                                 "b2\tHill\t\tsprint\t0,0,0;10,10,0\n")
        self.write("laptimes.tsv", "a1\tBob\t65432\tpessima\t%d\na1\tAlice\t61001\tsunburst2\t%d\n" % (time.time(), time.time()))
        d = self.owner.call("/api/laps")[1]
        ring = next(t for t in d["tracks"] if t["id"] == "a1")
        self.assertEqual((ring["checkpoints"], ring["kind"], ring["map"]), (2, "loop", "gridmap_v2"))
        self.assertEqual([r["name"] for r in ring["top"]], ["Alice", "Bob"])
        self.assertEqual(ring["top"][0]["time"], "1:01.001")
        self.assertEqual(self.owner.call("/api/laps", {"action": "rename", "id": "a1", "name": "Hill"})[0], 400)   # taken
        self.assertEqual(self.owner.call("/api/laps", {"action": "rename", "id": "a1", "name": "Big Ring"})[0], 200)
        self.assertIn("a1\tBig Ring\t", self.read("tracks.tsv"))
        self.owner.call("/api/laps", {"action": "remove_time", "id": "a1", "name": "alice"})
        self.assertNotIn("Alice", self.read("laptimes.tsv"))
        self.owner.call("/api/laps", {"action": "delete", "id": "b2"})
        self.assertNotIn("Hill", self.read("tracks.tsv"))
        # the public status page shows the board
        D.APP.settings.update({"statuspage_on": True})
        self.addCleanup(lambda: D.APP.settings.update({"statuspage_on": False}))
        D._STATUS_CACHE["t"] = 0
        st, body, _ = harness.Client(self.base).call("/status")
        self.assertEqual(st, 200)
        self.assertIn("Big Ring", body if isinstance(body, str) else body.decode())

    def test_player_profile_and_notes(self):
        t = int(time.time())
        lines = [{"t": t - 3600, "ev": "join", "id": 1, "name": "Dani"}, {"t": t - 600, "ev": "leave", "id": 1, "name": "Dani"},
                 {"t": t - 500, "ev": "kick", "name": "Dani", "by": "Boss", "reason": "ramming"},
                 {"t": t - 400, "ev": "report", "name": "Zoli", "target": "Dani", "reason": "spawn kill"}]
        self.write("events.log", "".join(json.dumps(x) + "\n" for x in lines))
        st, p, _ = self.owner.call("/api/players/profile?name=dani")
        self.assertEqual(st, 200)
        self.assertEqual((p["name"], p["sessions"]), ("Dani", 1))
        self.assertAlmostEqual(p["seconds"], 3000, delta=5)
        self.assertEqual([h["ev"] for h in p["history"]], ["report", "kick"])
        self.assertEqual(p["history"][0]["by"], "Zoli")
        self.addCleanup(lambda: D.set_server_meta("main", player_notes=None))
        st, r, _ = self.owner.call("/api/players/note", {"name": "Dani", "text": "Warned about ramming, 2nd time"})
        self.assertEqual(st, 200)
        self.assertEqual(len(r["notes"]), 1)
        p = self.owner.call("/api/players/profile?name=DANI")[1]
        self.assertEqual(p["notes"][0]["text"], "Warned about ramming, 2nd time")
        self.owner.call("/api/players/note", {"name": "Dani", "delete": p["notes"][0]["id"]})
        self.assertEqual(self.owner.call("/api/players/profile?name=Dani")[1]["notes"], [])

    def test_checklist(self):
        self.addCleanup(lambda: D.set_server_meta("main", setup_hidden=None, setup_skipped=None, invited=None))
        d = self.owner.call("/api/checklist")[1]
        self.assertEqual(d["total"], 6)
        before = d["done"]
        d = self.owner.call("/api/checklist", {"skip": "alerts"})[1]
        self.assertTrue(next(i for i in d["items"] if i["id"] == "alerts")["skipped"])
        self.assertGreaterEqual(d["done"], before)
        d = self.owner.call("/api/checklist", {"invited": True})[1]
        self.assertTrue(next(i for i in d["items"] if i["id"] == "invite")["done"])
        self.assertTrue(self.owner.call("/api/checklist", {"hidden": True})[1]["hidden"])

    def test_performance_series(self):
        t = int(time.time())
        D.APP.res_hist = [{"t": t - 60 * i, "cpu": 50, "mem_total": 1000, "mem_free": 250, "up_kbps": 2000, "players": 3, "ping": 80}
                          for i in range(120, 0, -1)]
        d = self.owner.call("/api/resources?range=day")[1]
        self.assertTrue(d["series"])
        row = d["series"][-1]
        self.assertEqual(row[1:], [50, 75.0, 2.0, 3, 80])
        self.assertIsNone(self.owner.call("/api/resources")[1]["series"])
