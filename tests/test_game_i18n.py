"""The game chat in the server's language: the "game" part of dashboard/lang/xx.json, the chatlang.tsv the
dashboard writes for the plugin, and the setting (Config -> Welcome message & announcements)."""
import os
import re
import sys
import unittest

import harness
from harness import D

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import game_i18n  # noqa: E402

ENGLISH = game_i18n.templates()


def placeholder_problem(en, tr):
    n, plain = en.count("{}"), tr.count("{}")
    nums = [int(x) for x in re.findall(r"\{(\d+)\}", tr)]
    if re.search(r"\{[^}\d]", tr.replace("{}", "")):
        return "stray {"
    if plain and nums:
        return "mixes {} and {1}"
    if nums:
        return None if max(nums) <= n else "{%d} but the English has %d" % (max(nums), n)
    return None if plain == n else "%d {} for %d" % (plain, n)


class Translations(unittest.TestCase):
    def test_every_message_is_found(self):
        for t in ("Races are turned off on this server.", "{} joined the race on {}.", "Tracks here: {}.",
                  "for the next one later", "Ask to teleport to a player", "player reason", "Sheriff", "north-east",
                  "No player called {} is online.", "Didn't finish: {}"):
            self.assertIn(t, ENGLISH)
        for t in ("cop", "speed", "join", "Next repair in", "No player called"):     # code words and half messages
            self.assertNotIn(t, ENGLISH)
        self.assertTrue(set(D.GAME_HUD_TEXT) <= set(ENGLISH))

    def test_languages_cover_the_game(self):
        for code, d in game_i18n.lang_files().items():
            self.assertGreater(game_i18n.coverage(d.get("game", {}), ENGLISH), 0.9, code)

    def test_placeholders_fit(self):
        bad = []
        for code, d in game_i18n.lang_files().items():
            for en, tr in d.get("game", {}).items():
                err = placeholder_problem(en, tr)
                if err or "\t" in tr or "\n" in tr:
                    bad.append((code, en, tr, err))
        self.assertEqual(bad, [])

    def test_chatlang_file(self):
        self.assertEqual(D.chat_lang_text(""), "")
        self.assertEqual(D.chat_lang_text("../hu"), "")
        self.assertEqual(D.chat_lang_text("xx"), "")
        lines = D.chat_lang_text("hu").splitlines()
        self.assertGreater(len(lines), 300)
        rows = {l.split("\t")[0]: l.split("\t")[1:] for l in lines}
        self.assertTrue(all(len(v) in (1, 2) and v[0] for v in rows.values()))
        self.assertEqual(rows["GO!"][1:], ["hud"])
        self.assertEqual(rows["Races are turned off on this server."][1:], [])


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class Setting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()

    def test_pick_the_language(self):
        path = os.path.join(D.INSTANCES["main"].STATS_DIR, "chatlang.tsv")
        self.addCleanup(lambda: self.owner.call("/api/messages", {"chat_lang": ""}))
        d = self.owner.call("/api/messages")[1]
        self.assertEqual(d["chat_lang"], "")
        self.assertIn("hu", [x["code"] for x in d["languages"]])
        st, r, _ = self.owner.call("/api/messages", {"chat_lang": "hu"})
        self.assertEqual(st, 200, r)
        with open(path, encoding="utf-8") as f:
            self.assertIn("Races are turned off on this server.\t", f.read())
        self.assertEqual(self.owner.call("/api/messages")[1]["chat_lang"], "hu")
        self.assertEqual(self.owner.call("/api/messages", {"chat_lang": "klingon"})[0], 400)
        self.assertEqual(self.owner.call("/api/messages", {"chat_lang": ""})[0], 200)
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), "")


if __name__ == "__main__":
    unittest.main()
