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

    @unittest.skipUnless(LUA, "no Lua interpreter installed")
    def test_drift_scoring(self):
        """The mod's drift scoring with a fake car: sideways at 60 km/h is banked once the car straightens up,
        a crash loses it, and nothing is scored until the server switches drift on."""
        sim = r"""
local sent, js = {}, {}
local handlers = {}
local V = {}
V.__index = V
function vec3(x, y, z) if type(x) == "table" then return setmetatable({ x = x.x, y = x.y, z = x.z }, V) end return setmetatable({ x = x, y = y, z = z or 0 }, V) end
function V:length() return math.sqrt(self.x ^ 2 + self.y ^ 2 + self.z ^ 2) end
local car = { vel = vec3(0, 0, 0), dir = vec3(0, 1, 0) }
function car:getVelocity() return self.vel end
function car:getDirectionVector() return self.dir end
function car:getID() return 1 end
be = { getPlayerVehicle = function() return car end, queueJS = function(_, s) js[#js + 1] = s end }
AddEventHandler = function(ev, fn) handlers[ev] = fn end
TriggerServerEvent = function(ev, data) sent[#sent + 1] = ev .. " " .. data end
log = function(_, _, msg) error(msg) end
local M = assert(load(io.read("a")))()
M.onExtensionLoaded()
local function drive(secs, kmh, deg)
  local a = math.rad(deg)
  car.vel = vec3(math.sin(a) * kmh / 3.6, math.cos(a) * kmh / 3.6, 0)
  for _ = 1, math.floor(secs * 60) do M.onPreRender(1 / 60, 1 / 60) end
end
drive(3, 60, 40)
assert(#sent == 0, "scored before the server switched drift on")
handlers.esDriftCfg("1")
drive(1, 60, 0) drive(3, 60, 40) drive(2, 60, 0)
assert(#sent == 1, "one drift should be sent, got " .. #sent)
local s, t = sent[1]:match('^esDrift {"s":(%d+),"t":([%d.]+)}$')
s, t = tonumber(s), tonumber(t)
-- 3 s at 40 degrees and 60 km/h: (40 - 10) * 60 / 20 = 90 a second
assert(t > 2.9 and t < 3.1 and s > 250 and s < 290, sent[1])
assert(js[#js]:find('("done",', 1, true), "the banked score isn't shown")
drive(3, 80, 45)
car.vel = vec3(0, 0, 0) M.onPreRender(1 / 60, 1 / 60)      -- into a wall
drive(2, 0, 0)
assert(#sent == 1, "a crashed drift was sent")
assert(js[#js]:find('("lost",', 1, true) or js[#js - 1]:find('("lost",', 1, true), "the lost drift isn't shown")
handlers.esDriftCfg("0")
drive(3, 60, 40) drive(2, 60, 0)
assert(#sent == 1, "scored after the server switched drift off")
print("ok")
"""
        lua = self.files()["lua/ge/extensions/easyserverTools.lua"]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sim.lua")
            with open(path, "w", encoding="utf-8") as f:
                f.write(sim)
            r = subprocess.run([LUA, path], input=lua, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "ok"), r.stderr)

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
