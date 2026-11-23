"""The Games page: rules for races and cops and robbers, leaderboards, speed traps, badges, seasons,
the live map and the weekly recap."""
import json
import os
import time
import unittest

import harness
from harness import D


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class Games(unittest.TestCase):
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

    def test_rules_are_saved_for_the_plugin(self):
        self.addCleanup(lambda: os.path.exists(self.stats("games.txt")) and os.remove(self.stats("games.txt")))
        d = self.owner.call("/api/games")[1]
        self.assertTrue(d["race"] and d["cnr"] and d["traps"] and d["badges"])
        self.assertFalse(d["seasons"])                      # off until the owner wants times to reset
        st, r, _ = self.owner.call("/api/games", {"cnr": False, "seasons": True, "race_who": "admins", "cnr_minutes": 15,
                                                  "cnr_catch": 8, "cnr_hold": 5, "cnr_busted": "cop"})
        self.assertEqual(st, 200, r)
        txt = self.read("games.txt")
        for line in ("cnr=off", "seasons=on", "race=on", "race_who=admins", "cnr_minutes=15", "cnr_catch=8", "cnr_hold=5", "cnr_busted=cop"):
            self.assertIn(line + "\n", txt)
        for bad in ({"cnr_minutes": 7}, {"cnr_catch": 100}, {"race_who": "robbers"}, {"cnr_busted": "jail"}):
            self.assertEqual(self.owner.call("/api/games", bad)[0], 400, bad)

    def test_results_leaderboards_and_profiles(self):
        t = int(time.time())
        evs = [{"t": t - 900, "ev": "join", "id": 1, "name": "Bob"},
               {"t": t - 500, "ev": "race", "track": "Ring", "laps": 3, "by": "Boss",
                "results": [{"name": "Bob", "ms": 180500, "pos": 1}, {"name": "Boss", "ms": 184210, "pos": 2}], "dnf": ["Alice"]},
               {"t": t - 500, "ev": "racepos", "name": "Bob", "track": "Ring", "pos": 1, "of": 3, "ms": 180500},
               {"t": t - 300, "ev": "bust", "name": "Boss", "target": "Bob"},
               {"t": t - 200, "ev": "cnr", "winner": "robbers", "minutes": 10, "seconds": 600, "cops": ["Boss"], "robbers": ["Bob", "Alice"],
                "escaped": ["Alice"], "busts": [{"cop": "Boss", "robber": "Bob"}]},
               {"t": t - 100, "ev": "badge", "name": "Bob", "badge": "race_win", "title": "Race winner"}]
        self.write("events.log", "".join(json.dumps(x) + "\n" for x in evs))
        self.write("seasonstats.tsv", "Bob\t10\t1\t1\t0\t0\t1\nBoss\t2\t1\t0\t1\t0\t1\nAlice\t0\t1\t0\t0\t1\t1\n")
        self.write("gamestats.tsv", "Bob\t30\t5\t3\t0\t2\t4\n")
        self.write("badges.tsv", "Bob\trace_win\t%d\nBob\tfirst_lap\t%d\nAlice\tgetaway\t%d\n" % (t - 100, t - 2000, t - 200))
        self.write("seasons.tsv", "2026-10\tlap\tRing\tBoss\t61001\n2026-10\ttrap\tStraight\tAlice\t201.5\n2026-10\twins\t\tBob\t4\n")
        d = self.owner.call("/api/games")[1]
        race = d["races"][0]
        self.assertEqual((race["track"], race["laps"], race["dnf"]), ("Ring", 3, ["Alice"]))
        self.assertEqual([(r["name"], r["time"], r.get("gap")) for r in race["results"]], [("Bob", "3:00.500", None), ("Boss", "3:04.210", "+3.710")])
        self.assertEqual(d["cnr_games"][0]["escaped"], ["Alice"])
        self.assertEqual(d["wins"], [{"name": "Bob", "n": 1}])
        self.assertEqual(d["busts"], [{"name": "Boss", "n": 1}])
        self.assertEqual(d["escapes"], [{"name": "Alice", "n": 1}])
        self.assertEqual(next(b for b in d["badge_list"] if b["id"] == "race_win")["owners"], 1)
        self.assertEqual(d["badge_leaders"][0], {"name": "Bob", "n": 2})
        self.assertEqual(d["season_archive"][0]["season"], "2026-10")
        self.assertEqual([w["shown"] for w in d["season_archive"][0]["winners"]], ["1:01.001", "201 km/h", "4"])
        # the profile shows the games, and a bust for both the cop and the robber
        p = self.owner.call("/api/players/profile?name=bob")[1]
        self.assertEqual(p["games"]["all"]["wins"], 3)
        self.assertEqual(p["games"]["season"]["races"], 1)
        self.assertEqual([b["id"] for b in p["games"]["badges"]], ["first_lap", "race_win"])
        evs_seen = [h["ev"] for h in p["history"]]
        self.assertIn("racepos", evs_seen)
        self.assertEqual(next(h for h in p["history"] if h["ev"] == "bust")["me"], "robber")
        boss = self.owner.call("/api/players/profile?name=Boss")[1]
        self.assertEqual(next(h for h in boss["history"] if h["ev"] == "bust")["me"], "cop")

    def test_speed_traps(self):
        t = int(time.time())
        self.write("traps.tsv", "aa1\tStraight\t/levels/gridmap_v2/info.json\t1000.00,0.00,0.00\nbb2\tHill\t\t5,5,0\n")
        self.write("trapspeeds.tsv", "aa1\tBob\t150.0\tpickup\t%d\naa1\tAlice\t201.5\tsunburst2\t%d\n" % (t, t))
        d = self.owner.call("/api/games")[1]
        tr = next(x for x in d["trap_boards"] if x["id"] == "aa1")
        self.assertEqual([(r["name"], r["shown"]) for r in tr["top"]], [("Alice", "201 km/h"), ("Bob", "150 km/h")])
        self.assertEqual(tr["map"], "gridmap_v2")
        self.owner.call("/api/games", {"action": "remove_speed", "id": "aa1", "name": "alice"})
        self.assertNotIn("Alice", self.read("trapspeeds.tsv"))
        self.owner.call("/api/games", {"action": "delete_trap", "id": "bb2"})
        self.assertNotIn("Hill", self.read("traps.tsv"))
        self.assertEqual(self.owner.call("/api/games", {"action": "delete_trap", "id": "nope"})[0], 404)

    def test_live_map_asks_the_plugin_and_shows_fresh_positions(self):
        self.addCleanup(lambda: os.path.exists(self.stats("livemap.txt")) and os.remove(self.stats("livemap.txt")))
        D.INSTANCES["main"].livemap_asked = 0
        self.write("tracks.tsv", "a1\tRing\t\tloop\t0.00,0.00,0.00;300.00,0.00,0.00;300.00,300.00,0.00\n")
        d = self.owner.call("/api/livemap")[1]
        self.assertFalse(d["fresh"])
        self.assertEqual(d["cars"], [])
        until = int(self.read("livemap.txt").split("=")[1])
        self.assertAlmostEqual(until, time.time() + D.LIVEMAP_ASK, delta=3)
        self.assertEqual(d["tracks"][0]["pts"], [[0.0, 0.0], [300.0, 0.0], [300.0, 300.0]])
        self.write("livemap.json", json.dumps({"t": int(time.time()), "map": "", "cars": [
            {"n": "Bob", "x": 12.5, "y": -3, "z": 1, "v": 88, "car": "pickup", "role": "robber"},
            {"n": "<b>x</b>", "x": "bad"}], "cnr": {"state": "on", "left": 300}}))
        d = self.owner.call("/api/livemap")[1]
        self.assertTrue(d["fresh"])
        self.assertEqual(d["cars"], [{"n": "Bob", "x": 12.5, "y": -3.0, "v": 88, "car": "pickup", "role": "robber"}])
        self.assertEqual(d["game"]["cnr"], {"state": "on", "left": 300})
        self.write("livemap.json", json.dumps({"t": int(time.time()) - 60, "cars": [{"n": "Old", "x": 0, "y": 0}]}))
        self.assertEqual(self.owner.call("/api/livemap")[1]["cars"], [], "old positions shown as live")

    def test_weekly_recap(self):
        self.addCleanup(lambda: D.set_server_meta("main", recap=None, recap_week=None, recap_last=None))
        t = int(time.time())
        evs = [{"t": t - 30 * 86400, "ev": "join", "id": 1, "name": "Old"}, {"t": t - 30 * 86400 + 600, "ev": "leave", "id": 1, "name": "Old"},
               {"t": t - 7200, "ev": "join", "id": 1, "name": "Bob"}, {"t": t - 3600, "ev": "join", "id": 2, "name": "Alice"},
               {"t": t - 3000, "ev": "lap", "name": "Bob", "track": "Ring", "ms": 61001, "record": True},
               {"t": t - 2500, "ev": "race", "track": "Ring", "laps": 3, "results": [{"name": "Bob", "ms": 1, "pos": 1}], "dnf": ["Alice"]},
               {"t": t - 2000, "ev": "cnr", "winner": "robbers", "busts": [{"cop": "Alice", "robber": "Bob"}], "escaped": []},
               {"t": t - 1000, "ev": "trap", "name": "Alice", "trap": "Straight", "kmh": 201.5, "record": True},
               {"t": t - 900, "ev": "badge", "name": "Bob", "badge": "record"}]
        self.write("events.log", "".join(json.dumps(x) + "\n" for x in evs))
        d = self.owner.call("/api/recap")[1]
        self.assertFalse(d["on"])
        txt = d["preview"]["text"]
        self.assertIn("2 players, 2 new", txt)
        self.assertIn("Most time on the server: Bob 2.0 h, Alice 1.0 h", txt)
        self.assertIn("New lap records: Ring – Bob 1:01.001", txt)
        self.assertIn("1 race – wins: Bob 1", txt)
        self.assertIn("most busts: Alice (1)", txt)
        self.assertIn("Straight – Alice 201 km/h", txt)
        self.assertIn("1 badge earned", txt)
        self.assertNotIn("Old", txt)
        self.assertEqual(self.owner.call("/api/recap", {"on": True, "day": 9})[0], 400)
        st, r, _ = self.owner.call("/api/recap", {"on": True, "day": 2, "hour": 20})
        self.assertEqual(st, 200)
        self.assertIn("Wednesday at 20:00", r["note"])
        self.assertEqual(D.recap_cfg(D.INSTANCES["main"]), {"on": True, "day": 2, "hour": 20})
        # nothing set up to post to
        if not D.recap_channels():
            self.assertEqual(self.owner.call("/api/recap", {"send": True})[0], 400)
        self.assertEqual(D.required_role("GET", "/api/recap"), "admin")
        self.assertEqual(D.perm_group("POST", "/api/games"), "config")
        self.assertIsNone(D.perm_group("GET", "/api/livemap"))
