"""Paired computers: their status and commands through files, moving a server to one, copies of the backups on a
USB drive or another computer, and the join-time numbers on the Mods page. No real SSH: pi_ssh is replaced."""
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from unittest import mock

import harness  # noqa: F401  (sets up the throw-away server folder first)
from harness import D

LINUX_PI = {"ip": "192.168.0.61", "user": "pi", "sudo": True, "bits": 64, "os": "raspbian", "version": "1.15.0", "host": "pi5"}


class Dirs(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        for p in (mock.patch.object(D, "PI_DIR", os.path.join(self.dir, "pi")),
                  mock.patch.object(D, "REMOTE_DIR", os.path.join(self.dir, "remote")),
                  mock.patch.object(D, "REMOTE_IN", os.path.join(self.dir, "remote", "in")),
                  mock.patch.dict(D._PI, {"scan": None, "scanning": False, "job": None})):
            p.start()
            self.addCleanup(p.stop)
        D._PI.pop("overview", None)


class Ssh(Dirs):
    """What is sent to the other computer."""

    def setUp(self):
        super().setUp()
        self.sent = []

        def fake(pi, cmd, password=None, stdin_data=None, timeout=60, on_line=None):
            data = stdin_data.read() if hasattr(stdin_data, "read") else stdin_data
            self.sent.append((pi["ip"], cmd, data))
            return 0, self.answer
        self.answer = "ES_PUT_OK"
        p = mock.patch.object(D, "pi_ssh", fake)
        p.start()
        self.addCleanup(p.stop)

    def test_linux_put_runs_as_the_dashboard_user(self):
        cid = D.pi_remote_send(LINUX_PI, "stop")
        ip, cmd, data = self.sent[0]
        self.assertTrue(cmd.startswith("sudo -n -u beammp-dash sh -c "), cmd)
        self.assertIn(D.REMOTE_LINUX, cmd)
        self.assertIn("c-%s.json" % cid, cmd)
        self.assertEqual(json.loads(data), {"id": cid, "action": "stop"})
        D.pi_remote(dict(LINUX_PI, root=True, sudo=False), "status")
        self.assertTrue(self.sent[1][1].startswith("runuser -u beammp-dash -- cat "))

    def test_windows_finds_its_data_folder(self):
        D.pi_remote(dict(LINUX_PI, os="windows"), "put", "c-0123456789abcdef.json", b"{}")
        cmd = self.sent[0][1]
        self.assertTrue(cmd.startswith("powershell "))
        import base64
        script = base64.b64decode(cmd.split()[-1]).decode("utf-16-le")
        self.assertIn("BeamMP Dashboard (EasyServer)", script)
        self.assertIn("OpenStandardInput", script)
        self.assertIn("c-0123456789abcdef.json", script)

    def test_bad_names_and_refusals(self):
        with self.assertRaises(ValueError):
            D.pi_remote(LINUX_PI, "put", "../x.json", b"")
        self.answer = "sudo: a password is required"
        with self.assertRaises(RuntimeError):
            D.pi_remote_send(LINUX_PI, "start")

    def test_overview(self):
        pis = [dict(LINUX_PI, online=False), dict(LINUX_PI, ip="192.168.0.62", online=True, version=""),
               dict(LINUX_PI, ip="192.168.0.63", online=True, sudo=False),
               dict(LINUX_PI, ip="192.168.0.64", online=True), dict(LINUX_PI, ip="192.168.0.65", online=True)]
        good = json.dumps({"t": D.now(), "version": "1.16.0", "servers": [
            {"id": "main", "name": "Pi server", "state": "running", "players": 2, "max": 8, "map": "utah"}]})

        def remote(pi, op, name="", data=None, timeout=60):
            return (0, "cat: no such file") if pi["ip"] == "192.168.0.64" else (0, "warning\n" + good)
        with mock.patch.object(D, "pi_status", lambda: [dict(x) for x in pis]), mock.patch.object(D, "pi_remote", remote):
            r = {x["ip"]: x["remote"] for x in D.pi_overview()}
        self.assertEqual(r["192.168.0.61"]["error"], "off")
        self.assertEqual(r["192.168.0.62"]["error"], "none")
        self.assertEqual(r["192.168.0.63"]["error"], "nokey")
        self.assertEqual(r["192.168.0.64"]["error"], "old")
        self.assertEqual(r["192.168.0.65"]["servers"][0]["players"], 2)
        self.assertFalse(r["192.168.0.65"]["stale"])

    def test_backup_copy_to_a_computer(self):
        D.pi_remember(LINUX_PI["ip"], **{k: v for k, v in LINUX_PI.items() if k != "ip"})
        cmd = D.backup_put_cmd(LINUX_PI, "pc-main-20261124-0330.zip", "pc-main-")
        self.assertIn("~/easyserver-backups", cmd)
        self.assertIn("tail -n +%d" % (D.BACKUP_KEEP + 1), cmd)
        os.makedirs(D.BACKUP_DIR, exist_ok=True)
        name = "main-20261124-0330.zip"
        with open(os.path.join(D.BACKUP_DIR, name), "wb") as f:
            f.write(b"zipdata")
        self.addCleanup(os.remove, os.path.join(D.BACKUP_DIR, name))
        st = {"backup_copy": "computer", "backup_copy_ip": LINUX_PI["ip"]}
        with mock.patch.object(D, "APP", mock.Mock(settings=mock.Mock(get=st.get))):
            note = D.copy_backups([name])
            self.assertIn("pi5", note)
            self.assertEqual(self.sent[-1][2], b"zipdata")
            self.assertIn("%s-%s" % (D.backup_tag(), name), self.sent[-1][1])
            self.answer = "No space left on device"
            with self.assertRaises(RuntimeError):
                D.copy_backups([name])
            st["backup_copy_ip"] = "192.168.0.99"
            with self.assertRaises(RuntimeError):
                D.copy_backups([name])


class Pure(unittest.TestCase):
    def test_games_names(self):
        for ok in ("laptimes.tsv", "champ.tsv", "games.txt", "events.log", "seasons.tsv"):
            self.assertTrue(D.games_name_ok(ok), ok)
        for bad in ("main.lua", "bridge.txt", "online.json", "bans.txt", "../x.tsv", "a b.tsv", "x.tsv.tmp"):
            self.assertFalse(D.games_name_ok(bad), bad)

    def test_folder_check(self):
        self.assertIn("whole path", D.backup_folder_check("backups"))
        self.assertIn("plugged in", D.backup_folder_check(os.path.join(tempfile.gettempdir(), "no-such-folder-es")))
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        self.assertEqual(D.backup_folder_check(d), "")

    def test_can_remote(self):
        self.assertTrue(D.pi_can_remote(LINUX_PI))
        self.assertFalse(D.pi_can_remote(dict(LINUX_PI, version="")))
        self.assertFalse(D.pi_can_remote(dict(LINUX_PI, sudo=False)))
        self.assertTrue(D.pi_can_remote(dict(LINUX_PI, sudo=False, root=True)))
        self.assertFalse(D.pi_can_remote(dict(LINUX_PI, os="windows", sudo=False)))


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class Live(Dirs):
    def setUp(self):
        super().setUp()
        self.c = harness.owner()
        self.addCleanup(lambda: D._TL.__dict__.pop("inst", None))
        D.use_server("main")
        was = D.I().meta.get("reviewed")
        self.addCleanup(lambda: D.set_server_meta("main", reviewed=was))

    def cmd(self, cid, **kw):
        os.makedirs(D.REMOTE_IN, exist_ok=True)
        with open(os.path.join(D.REMOTE_IN, "c-%s.json" % cid), "w") as f:
            json.dump(dict(kw, id=cid), f)

    def status(self):
        with open(os.path.join(D.REMOTE_DIR, "status.json")) as f:
            return json.load(f)

    def test_commands(self):
        D.set_server_meta("main", reviewed=False)
        self.cmd("aaaaaaaa", action="stop")
        self.cmd("bbbbbbbb", action="start")
        self.cmd("cccccccc", action="format-disk")
        self.cmd("nothex!!", action="stop")
        D.APP.remote_tick()
        done = {x["id"]: x for x in self.status()["done"]}
        self.assertTrue(done["aaaaaaaa"]["ok"])
        self.assertFalse(done["bbbbbbbb"]["ok"])         # its settings weren't looked over yet
        self.assertFalse(done["cccccccc"]["ok"])
        self.assertEqual(len(done), 3)
        self.assertEqual(os.listdir(D.REMOTE_IN), [])
        st = self.status()
        self.assertEqual(st["version"], D.EASY_VERSION)
        self.assertEqual(st["servers"][0]["id"], "main")

    def test_move_round_trip(self):
        sd = D.I().STATS_DIR
        for n, body in (("laptimes.tsv", "track1\tAnna\t61.2\n"), ("bridge.txt", "x")):
            with open(os.path.join(sd, n), "w") as f:
                f.write(body)
        self.addCleanup(lambda: [os.remove(os.path.join(sd, n)) for n in ("laptimes.tsv", "bridge.txt") if os.path.exists(os.path.join(sd, n))])
        zp = os.path.join(D.REMOTE_IN, "move-0123456789abcdef.zip")
        os.makedirs(D.REMOTE_IN, exist_ok=True)
        D.build_export(zp, True, include_games=True)
        with zipfile.ZipFile(zp) as z:
            names = z.namelist()
        self.assertIn("games/laptimes.tsv", names)
        self.assertNotIn("games/bridge.txt", names)
        self.assertNotIn("games/main.lua", names)
        os.remove(os.path.join(sd, "laptimes.tsv"))
        D.APP.remote_tick()                                # (sets up its fields)
        D.APP.remote_move_in({"id": "dddddddd", "action": "move-in", "file": os.path.basename(zp), "source": "PC"})
        r = next(x for x in self.status()["done"] if x["id"] == "dddddddd")
        self.assertTrue(r["ok"], r)
        self.assertRegex(r["note"], r"\d+ files? of stats and games")
        with open(os.path.join(sd, "laptimes.tsv")) as f:
            self.assertIn("Anna", f.read())
        self.assertFalse(os.path.exists(zp))
        self.assertTrue(D.I().meta.get("reviewed"))

    def test_move_needs_its_file(self):
        D.APP.remote_tick()
        D.APP.remote_move_in({"id": "eeeeeeee", "action": "move-in", "file": "move-ffffffffffffffff.zip"})
        r = next(x for x in self.status()["done"] if x["id"] == "eeeeeeee")
        self.assertFalse(r["ok"])

    def test_backup_copy_to_a_folder(self):
        dest = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, dest, True)
        os.makedirs(D.BACKUP_DIR, exist_ok=True)
        made = []
        for day in range(1, 10):
            n = "main-202611%02d-0330.zip" % day
            with open(os.path.join(D.BACKUP_DIR, n), "wb") as f:
                f.write(b"z")
            made.append(n)
        self.addCleanup(lambda: [os.remove(os.path.join(D.BACKUP_DIR, n)) for n in made if os.path.exists(os.path.join(D.BACKUP_DIR, n))])
        st, d = self.c.call("/api/backups", {"copy": "folder", "copy_path": dest})[:2]
        self.assertEqual(st, 200, d)
        self.addCleanup(D.APP.settings.update, {"backup_copy": ""})
        self.assertIn("Copied", D.copy_backups(made))
        kept = sorted(os.listdir(os.path.join(dest, D.BACKUP_COPY_DIR, D.backup_tag())))
        self.assertEqual(kept, made[-D.BACKUP_KEEP:])
        st, d = self.c.call("/api/backups", {"copy": "folder", "copy_path": "relative/path"})[:2]
        self.assertEqual(st, 400)
        st, d = self.c.call("/api/backups", {"copy": "computer", "copy_ip": "192.168.0.99"})[:2]
        self.assertEqual(st, 400)
        st, d = self.c.call("/api/backups")[:2]
        self.assertEqual(d["copy"], "folder")
        self.assertIn("drives", d)

    def test_machines_api(self):
        with mock.patch.object(D, "pi_status", lambda: []):
            st, d = self.c.call("/api/machines")[:2]
        self.assertEqual(st, 200, d)
        self.assertEqual(d["here"]["servers"][0]["id"], "main")
        self.assertEqual(self.c.call("/api/machines", {"action": "stop", "ip": "192.168.0.99"})[0], 404)
        D.pi_remember("192.168.0.62", user="pi", sudo=True, bits=64, version="")
        self.assertEqual(self.c.call("/api/machines", {"action": "stop", "ip": "192.168.0.62"})[0], 400)
        self.assertIn("/api/machines", D.OWNER_WRITE)

    def test_moved_server_stays_off(self):
        D.set_server_meta("main", reviewed=True, moved_to={"ip": "192.168.0.61", "host": "pi5", "t": D.now()})
        self.addCleanup(lambda: D.set_server_meta("main", moved_to=None))
        st, d = self.c.call("/api/server/action", {"action": "start"})[:2]
        self.assertEqual(st, 409)
        self.assertTrue(d["moved"])
        self.assertIn("pi5", d["error"])
        inst = D.INSTANCES["main"]
        stops = []
        with mock.patch.object(D.ServerManager, "status", lambda self: {"state": "running", "pid": 1, "uptime": 5, "restarts": 0}), \
                mock.patch.object(D.ServerManager, "action", lambda self, a: stops.append(a) or {"ok": True}), \
                mock.patch.object(D, "internet_ok", lambda: False):
            D.APP._monitor_one(inst, D.APP._monitor_init(inst))     # e.g. the computer restarted and started it
            self.assertEqual(stops[:1], ["stop"])
            checks = {c["id"]: c for c in D.health_report()["checks"]}
        self.assertEqual(checks["moved"]["state"], "warn")
        self.assertEqual(checks["moved"]["go"], "servers")
        self.assertEqual(checks["backups"]["go"], "settings")
        st, d = self.c.call("/api/server/action", {"action": "start", "anyway": True})[:2]
        self.assertEqual(st, 200, d)
        self.assertNotIn("moved_to", D.INSTANCES["main"].meta)

    def test_health_backups_and_join_time(self):
        s = D.APP.settings
        old = {k: s.get(k) for k in ("backup_on", "backup_copy", "upload_mbit")}
        self.addCleanup(s.update, old)
        with mock.patch.object(D, "internet_ok", lambda: False), \
                mock.patch.object(D, "list_mods", lambda: [{"name": "big.zip", "size": 600 * 10 ** 6, "enabled": True, "maps": [], "safety": "clean", "reasons": [], "needs": []}]):
            s.update({"backup_on": True, "backup_copy": "", "upload_mbit": 10})
            checks = {c["id"]: c for c in D.health_report()["checks"]}
            self.assertIn("only on this computer", checks["backups"]["detail"])
            self.assertEqual(checks["join"]["state"], "warn")          # 600 MB at 10 Mbit/s = 8 minutes
            self.assertIn("8 minutes", checks["join"]["detail"])
            s.update({"backup_copy": "folder", "upload_mbit": 100})
            checks = {c["id"]: c for c in D.health_report()["checks"]}
            self.assertEqual(checks["join"]["state"], "pass")
            s.update({"upload_mbit": 0})
            self.assertIn("isn't entered", {c["id"]: c for c in D.health_report()["checks"]}["join"]["detail"])

    def test_mods_join_numbers(self):
        st, d = self.c.call("/api/mods")[:2]
        self.assertEqual(st, 200)
        self.assertIn("upload_mbit", d)
        self.assertIn("limit_kbps", d)


if __name__ == "__main__":
    unittest.main()
