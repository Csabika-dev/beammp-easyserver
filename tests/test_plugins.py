"""Server plugins (catalog install, upload, turn off/on, remove) and mod pack share codes."""
import io
import json
import os
import time
import unittest
import zipfile
from unittest import mock

import harness
from harness import D


def zbytes(files, links=()):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, t in files.items():
            z.writestr(n, t)
        for n in links:
            zi = zipfile.ZipInfo(n)
            zi.external_attr = 0o120777 << 16
            z.writestr(zi, "/etc/passwd")
    return buf.getvalue()


def client_mod():
    return zbytes({"scripts/x/modScript.lua": "-- client", "lua/ge/extensions/x.lua": "local M = {} return M"})


class FakeResp(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url, self.headers = url, {"Content-Length": str(len(data))}

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class Plugins(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()

    def tmpzip(self, files, links=()):
        p = os.path.join(harness.TMP, "p%d.zip" % time.time_ns())
        with open(p, "wb") as f:
            f.write(zbytes(files, links))
        self.addCleanup(lambda: os.path.exists(p) and os.remove(p))
        return p

    def test_plan_layouts(self):
        p = self.tmpzip({"pkg/Resources/Server/Race/main.lua": "x", "pkg/Resources/Server/Race/cfg/a.json": "{}",
                         "pkg/Resources/Client/race.zip": client_mod(), "pkg/README.md": "hi"})
        plan = D.plan_public(D.plugin_plan(p))
        self.assertEqual(plan["server"], [{"folder": "Race", "files": 2, "lua": 1}])
        self.assertEqual(plan["client"], ["race.zip"])
        self.assertEqual(plan["skipped"], 1)
        p = self.tmpzip({"Server/Joy/main.lua": "x", "Client/joy.zip": client_mod()})      # unpacked into Resources
        plan = D.plan_public(D.plugin_plan(p))
        self.assertEqual([s["folder"] for s in plan["server"]], ["Joy"])
        p = self.tmpzip({"Cobalt-master/main.lua": "x", "Cobalt-master/lua/db.lua": "y", "Cobalt-master/.github/w.yml": ""})
        plan = D.plan_public(D.plugin_plan(p, "CobaltEssentials"))
        self.assertEqual(plan["server"], [{"folder": "CobaltEssentials", "files": 2, "lua": 2}])

    def test_plan_refuses_bad_files(self):
        for files, links in (({"../evil/main.lua": "x"}, ()), ({"Resources/Server/EasyServerStats/main.lua": "x"}, ()),
                             ({"Resources/Server/P/main.lua": "x"}, ("Resources/Server/P/link",)), ({"readme.txt": "x"}, ())):
            with self.assertRaises(RuntimeError):
                D.plugin_plan(self.tmpzip(files, links))

    def upload(self, files, name="myplugin.zip"):
        return self.owner.call("/api/plugins/upload?name=" + name, raw=zbytes(files), method="PUT")

    def test_upload_install_toggle_remove(self):
        st, j, _ = self.upload({"Resources/Server/MyPlug/main.lua": "print('hi')", "Resources/Client/myplug.zip": client_mod()})
        self.assertEqual(st, 200, j)
        self.assertTrue(j["review"])
        self.assertNotIn("_plan", j)
        self.assertEqual(self.owner.call("/api/plugins/install", {"job": j["job"]})[0], 400)       # must tick "trust"
        st, d, _ = self.owner.call("/api/plugins/install", {"job": j["job"], "trust": True})
        self.assertEqual(st, 200, d)
        sdir, cdir = D.plugin_server_dir(), D.I().CLIENT_DIR
        self.assertTrue(os.path.isfile(os.path.join(sdir, "MyPlug", "main.lua")))
        self.assertTrue(os.path.isfile(os.path.join(cdir, "myplug.zip")))
        ov = self.owner.call("/api/plugins")[1]
        rec = next(p for p in ov["installed"] if p["name"] == "myplugin")
        self.assertFalse(rec["catalog"])
        self.assertEqual(self.owner.call("/api/plugins/install", {"job": j["job"], "trust": True})[0], 404)   # used up
        self.owner.call("/api/plugins/toggle", {"id": rec["id"], "on": False})
        self.assertFalse(os.path.exists(os.path.join(sdir, "MyPlug")))
        self.assertTrue(os.path.isfile(os.path.join(D.I().DISABLED_DIR, "myplug.zip")))
        self.owner.call("/api/plugins/toggle", {"id": rec["id"], "on": True})
        self.assertTrue(os.path.isfile(os.path.join(sdir, "MyPlug", "main.lua")))
        st, j2, _ = self.upload({"Resources/Server/MyPlug/main.lua": "x"}, "other.zip")
        self.assertEqual(self.owner.call("/api/plugins/install", {"job": j2["job"], "trust": True})[0], 400)  # folder taken
        self.owner.call("/api/plugins/remove", {"id": rec["id"]})
        self.assertFalse(os.path.exists(os.path.join(sdir, "MyPlug")))
        self.assertFalse(os.path.exists(os.path.join(cdir, "myplug.zip")))

    def test_catalog_download_and_update(self):
        entry = {"id": "testplug", "name": "Test Plug", "author": "Someone", "repo": "someone/testplug", "source": "release",
                 "about": "", "license": "MIT", "notes": []}
        zipdata = zbytes({"testplug-1/Resources/Server/TestPlug/main.lua": "x"})

        def fake_get(url, accept=""):
            if url.endswith("/releases/latest"):
                return FakeResp(json.dumps({"tag_name": "v1.2", "assets": [{"name": "testplug.zip",
                                "browser_download_url": "https://github.com/someone/testplug/releases/download/v1.2/testplug.zip"}]}).encode(), url)
            return FakeResp(zipdata, "https://objects.githubusercontent.com/x")
        cat = [D.plugin_entry_ok(entry)]
        with mock.patch.object(D, "plugin_catalog", lambda: cat), mock.patch.object(D, "_plug_get", fake_get):
            for _ in range(2):                                              # install, then update
                st, r, _ = self.owner.call("/api/plugins/fetch", {"id": "testplug"})
                self.assertEqual(st, 200, r)
                for _ in range(100):
                    j = self.owner.call("/api/plugins/job?job=" + r["job"])[1]
                    if j["finished"]:
                        break
                    time.sleep(0.05)
                self.assertTrue(j["ok"], j)
                self.assertEqual(j["version"], "v1.2")
                st, d, _ = self.owner.call("/api/plugins/install", {"job": r["job"]})
                self.assertEqual(st, 200, d)
            ov = self.owner.call("/api/plugins")[1]
            rec = [p for p in ov["installed"] if p["id"] == "testplug"]
            self.assertEqual(len(rec), 1)
            self.assertEqual(rec[0]["author"], "Someone")
            self.owner.call("/api/plugins/remove", {"id": "testplug"})

    def test_catalog_entries_are_checked(self):
        self.assertIsNone(D.plugin_entry_ok({"id": "x", "repo": "../../etc"}))
        self.assertIsNone(D.plugin_entry_ok({"id": "x", "repo": "a/b", "folder": "../x"}))
        built_in = [D.plugin_entry_ok(p) for p in D.PLUGIN_CATALOG["plugins"]]
        self.assertTrue(built_in and all(built_in))
        self.assertTrue(all(p["author"] for p in built_in), "every plugin credits its author")
        with open(os.path.join(harness.ROOT, "docs", "plugins.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), D.PLUGIN_CATALOG, "docs/plugins.json and the built-in copy differ")

    def test_hand_copied_plugins_and_errors(self):
        d = os.path.join(D.plugin_server_dir(), "Handmade")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "main.lua"), "w") as f:
            f.write("x")
        with open(D.I().SERVER_LOG, "a") as f:
            f.write("[LUA ERROR] onTick: Resources/Server/Handmade/main.lua:3: attempt to index a nil value\n")
        ov = self.owner.call("/api/plugins")[1]
        h = next(p for p in ov["other"] if p["folder"] == "Handmade")
        self.assertEqual(h["errors"], 1)
        st, r, _ = self.owner.call("/api/plugins/adopt", {"folder": "Handmade"})
        self.assertEqual(st, 200)
        self.owner.call("/api/plugins/toggle", {"id": r["id"], "on": False})
        self.assertFalse(os.path.exists(d))
        self.owner.call("/api/plugins/remove", {"id": r["id"]})
        self.assertEqual(self.owner.call("/api/plugins/adopt", {"folder": "EasyServerStats"})[0], 400)


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class ModpackCode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()

    def test_round_trip(self):
        p = os.path.join(D.I().CLIENT_DIR, "repo_car.zip")
        with open(p, "wb") as f:
            f.write(zbytes({"mod_info/ABC123/info.json": json.dumps({"resource_id": 4242, "resource_version_id": 7})}))
        self.addCleanup(os.remove, p)
        d = self.owner.call("/api/modpack/code")[1]
        self.assertTrue(d["code"].startswith("ES1-"))
        self.assertEqual(d["count"], 1)
        st, r, _ = self.owner.call("/api/modpack/code", {"code": d["code"]})
        self.assertEqual(st, 200)
        self.assertEqual(r["jobs"], [])                    # already installed
        got = []
        with mock.patch.object(D, "modb_install", lambda job, inst, rid: (got.append(rid), job.update(finished=True))):
            import base64
            import zlib
            code = "ES1-" + base64.urlsafe_b64encode(zlib.compress(b'{"v":1,"ids":[4242,99,"x",-1]}')).decode().rstrip("=")
            st, r, _ = self.owner.call("/api/modpack/code", {"code": code})
            self.assertEqual(st, 200, r)
            for _ in range(50):
                if got:
                    break
                time.sleep(0.05)
        self.assertEqual(got, [99])
        self.assertEqual(self.owner.call("/api/modpack/code", {"code": "hello"})[0], 400)


if __name__ == "__main__":
    unittest.main()
