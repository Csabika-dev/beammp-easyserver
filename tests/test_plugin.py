"""Runs tests/plugin_test.lua against the game plugin with whichever Lua 5.3+ is installed."""
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "..", "dashboard", "EasyServerStats", "main.lua")
LUA = next((shutil.which(x) for x in ("lua5.3", "lua5.4", "lua", "texlua") if shutil.which(x)), None)


@unittest.skipUnless(LUA, "no Lua interpreter installed (sudo apt install lua5.3)")
class Plugin(unittest.TestCase):
    def test_plugin(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([LUA, os.path.join(HERE, "plugin_test.lua"), MAIN, d],
                               capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
