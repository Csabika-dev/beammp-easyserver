"""Vehicle rules (blocked props, heavy mod cars, spawn limits), mod auto-detection and missing-mod warnings."""
import json
import os
import unittest
import zipfile

import harness
from harness import D

NODE = '["n%d", 0.1, 0.2, 0.3],\n'
BEAM = '["n%d", "n%d"],\n'


def make_mod(name, files):
    path = os.path.join(harness.SRV, "Resources", "Client", name)
    with zipfile.ZipFile(path, "w") as z:
        for fn, text in files.items():
            z.writestr(fn, text)
    return path


def jbeam(nodes, beams):
    return ('{"part": {"slotType": "main", // comment\n "nodes": [["id", "posX", "posY", "posZ"],\n'
            + "".join(NODE % i for i in range(nodes)) + '],\n "beams": [["id1:", "id2:"],\n'
            + "".join(BEAM % (i, i + 1) for i in range(beams)) + ']}}')


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class VehicleRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()
        cls.mods = [
            make_mod("monster.zip", {"vehicles/monster/info.json": '{"Name": "Monster", "Brand": "Big", "Type": "Car",}',
                                     "vehicles/monster/monster.jbeam": jbeam(D.HEAVY_NODES + 10, 50)}),
            make_mod("rampprop.zip", {"vehicles/megaramp/info.json": '{"Name": "Mega ramp", "Type": "Prop"}',
                                      "vehicles/megaramp/ramp.jbeam": jbeam(20, 30)}),
            make_mod("smallcar.zip", {"vehicles/tiny/info_tiny.json": '{"Name": "Tiny", "Type": "Car"}',
                                      "vehicles/tiny/tiny.jbeam": jbeam(300, 900)}),
            make_mod("monster_parts.zip", {"vehicles/someonescar/extra_parts.jbeam": jbeam(5, 5),
                                           "vehicles/etk800/etk_extra.jbeam": jbeam(5, 5)}),
        ]

    @classmethod
    def tearDownClass(cls):
        for p in cls.mods:
            os.remove(p)
        try:
            os.remove(os.path.join(D.I().STATS_DIR, "vehicles.txt"))
        except OSError:
            pass

    def vehfile(self):
        with open(os.path.join(D.I().STATS_DIR, "vehicles.txt"), encoding="utf-8") as f:
            return f.read()

    def test_mod_detection(self):
        vs = {v["jbm"]: v for v in D.server_mod_vehicles().values()}
        self.assertTrue(vs["monster"]["heavy"])
        self.assertEqual(vs["monster"]["kind"], "car")
        self.assertEqual(vs["monster"]["name"], "Big Monster")
        self.assertEqual(vs["megaramp"]["kind"], "prop")
        self.assertFalse(vs["tiny"]["heavy"])
        self.assertEqual(vs["tiny"]["nodes"], 300)
        self.assertEqual(vs["tiny"]["beams"], 900)
        self.assertNotIn("someonescar", vs)                 # only parts, no vehicle

    def test_missing_mod_warning(self):
        mods = {m["name"]: m for m in D.list_mods()}
        self.assertEqual(mods["monster_parts.zip"]["needs"], ["someonescar"])   # etk800 is in the game
        self.assertEqual(mods["monster.zip"]["needs"], [])

    def test_rules_file_and_api(self):
        st, d, _ = self.owner.call("/api/vehicles", {"on": True, "props": True, "heavymods": True, "trailers": False, "heavyprops": False, "cooldown": 7, "spam": 5,
                                                     "cars": "bolide, sbr"})
        self.assertEqual(st, 200, d)
        txt = self.vehfile()
        for line in ("on=on", "cooldown=7", "spam=5", "car=bolide", "block=cones\tprops are turned off",
                     "block=megaramp\tprops are turned off", "block=monster\tthis car is too heavy for the server",
                     "block=bolide\tthe server owner blocked it"):
            self.assertIn(line, txt)
        self.assertNotIn("block=tiny", txt)
        self.assertNotIn("block=flatbed", txt)            # trailers not chosen
        st, d, _ = self.owner.call("/api/vehicles")
        self.assertEqual(st, 200)
        self.assertTrue(d["rules"]["on"])
        self.assertIn("megaramp", [b["jbm"] for b in d["blocked"]])
        self.assertEqual(self.owner.call("/api/vehicles", {"cars": ["bad name!"]})[0], 400)
        self.assertEqual(self.owner.call("/api/vehicles", {"only": True, "allow": []})[0], 400)

    def test_presets_and_quick_block(self):
        st, d, _ = self.owner.call("/api/vehicles/preset", {"preset": "racing"})
        self.assertEqual(st, 200, d)
        self.assertEqual(self.owner.call("/api/vehicles")[1]["preset"], "racing")
        self.assertIn("block=flatbed\ttrailers are turned off", self.vehfile())
        self.owner.call("/api/vehicles/block", {"jbm": "covet"})
        self.assertIn("car=covet", self.vehfile())
        self.owner.call("/api/vehicles/block", {"jbm": "covet", "block": False})
        self.assertNotIn("car=covet", self.vehfile())
        self.assertEqual(self.owner.call("/api/vehicles/preset", {"preset": "nope"})[0], 400)

    def test_new_mod_is_covered_without_saving_again(self):
        self.owner.call("/api/vehicles", {"on": True, "props": True})
        p = make_mod("laterprop.zip", {"vehicles/laterprop/info.json": '{"Type": "Prop"}'})
        try:
            D.refresh_mod_desc()                            # what every mod upload / install / delete calls
            self.assertIn("block=laterprop", self.vehfile())
        finally:
            os.remove(p)

    def test_activity_from_the_plugin_log(self):
        path = os.path.join(D.I().STATS_DIR, "events.log")
        t = D.now()
        with open(path, "a") as f:
            for e in ({"ev": "spawn", "name": "Alice", "jbm": "etk800"}, {"ev": "spawn", "name": "Bob", "jbm": "etk800"},
                      {"ev": "spawn", "name": "Bob", "jbm": "large_crusher"},
                      {"ev": "vehblock", "name": "Bob", "jbm": "cones", "why": "props are turned off"},
                      {"ev": "vehspam", "name": "Eve", "count": 6}):
                f.write(json.dumps(dict(e, t=t)) + "\n")
        d = self.owner.call("/api/vehicles")[1]["activity"]
        seen = {s["jbm"]: s for s in d["seen"]}
        self.assertEqual(seen["etk800"]["count"], 2)
        self.assertEqual(seen["etk800"]["players"], 2)
        self.assertEqual(seen["large_crusher"]["kind"], "heavy prop")
        self.assertEqual(d["blocked"][0]["jbm"], "cones")
        self.assertEqual(d["spam"][0]["name"], "Eve")


if __name__ == "__main__":
    unittest.main()
