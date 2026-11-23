"""The helper mod (easyserver_tools.zip): its Lua and the JavaScript it puts on screen must at least parse
(BeamNG only tells the player, in its log, when they don't), it must listen for the games' events, and the
dashboard must hand it out when only the games need it."""
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import types
import unittest
import zipfile

from harness import D

LUA = next((shutil.which(x) for x in ("lua5.3", "lua5.4", "lua", "texlua") if shutil.which(x)), None)
NODE = shutil.which("node")


class HelperMod(unittest.TestCase):
    def files(self):
        with zipfile.ZipFile(io.BytesIO(D.tools_mod_bytes())) as z:
            return {n: z.read(n).decode() for n in z.namelist()}

    def test_listens_for_the_games(self):
        lua = self.files()["lua/ge/extensions/easyserverTools.lua"]
        for ev in ("esHud", "esTags", "esCmds", "esToolsCfg"):
            self.assertIn('AddEventHandler("%s"' % ev, lua)
        self.assertIn("M.onPreRender", lua)
        self.assertEqual(D.tools_mod_bytes(), D.tools_mod_bytes(), "the zip must be the same every time")

    @unittest.skipUnless(LUA, "no Lua interpreter installed")
    def test_lua_parses(self):
        for name, text in self.files().items():
            r = subprocess.run([LUA, "-e", "assert(load(io.read('a'), '%s'))" % name], input=text,
                               capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(r.returncode, 0, name + ": " + r.stderr)

    @unittest.skipUnless(NODE, "no Node.js installed")
    def test_javascript_parses(self):
        parts = re.findall(r"\[==\[(.*?)\]==\]", D.TOOLS_CLIENT_LUA, re.S)
        self.assertGreaterEqual(len(parts), 2)
        code = "const p = JSON.parse(require('fs').readFileSync(0, 'utf8')); for (const s of p) new Function('return ' + s);"
        r = subprocess.run([NODE, "-e", code], input=json.dumps(parts), capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_games_want_the_mod(self):
        with tempfile.TemporaryDirectory() as d:
            inst = types.SimpleNamespace(STATS_DIR=d)

            def put(name, text):
                with open(os.path.join(d, name), "w") as f:
                    f.write(text)

            self.assertTrue(D.games_want_mod(inst), "races and cops and robbers are on by default")
            put("games.txt", "race=off\ncnr=off\ntraps=on\n")
            self.assertFalse(D.games_want_mod(inst))
            put("laps.txt", "mode=on\nradius=15\n")
            self.assertTrue(D.games_want_mod(inst), "lap times show a timer")
            put("laps.txt", "mode=off\n")
            put("games.txt", "race=off\ncnr=on\n")
            self.assertTrue(D.games_want_mod(inst))


if __name__ == "__main__":
    unittest.main()
