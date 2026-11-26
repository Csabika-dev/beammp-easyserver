"""Community features: one-off events with a game and results, the public server page, Discord /player and
/leaderboard, player profiles across servers, the mod advice and the Google Drive copies (with a fake Google)."""
import json
import os
import time
import unittest
from unittest import mock

import harness  # noqa: F401  (sets up the throw-away server folder first)
from harness import D


class Base(unittest.TestCase):
    def setUp(self):
        self.c = harness.owner()
        D.use_server("main")
        self.addCleanup(D.use_server, "main")
        meta = D.INSTANCES["main"].meta
        old = {k: meta.get(k) for k in ("events", "event_active", "event_last")}
        self.addCleanup(lambda: D.set_server_meta("main", **old))
        s = D.APP.settings
        olds = {k: s.get(k) for k in ("statuspage_on", "statuspage_about", "statuspage_discord", "upload_mbit", "gdrive_on",
                                     "gdrive_client_id", "gdrive_folder", "gdrive_account", "backup_on", "backup_copy")}
        self.addCleanup(s.update, olds)
        D._STATUS_CACHE["t"] = 0


class Events(Base):
    def test_one_off_date(self):
        e = {"at": "20:00", "date": time.strftime("%Y-%m-%d", time.localtime(D.now() + 2 * 86400)), "days": []}
        st = D.event_next_start(e, D.now())
        self.assertEqual(time.strftime("%H:%M", time.localtime(st)), "20:00")
        self.assertGreater(st, D.now() + 86400)
        self.assertIsNone(D.event_next_start(dict(e, date="2020-01-01"), D.now()))
        self.assertIsNone(D.event_next_start(dict(e, date="2020-02-31"), D.now()))

    def test_save_and_validate(self):
        day = time.strftime("%Y-%m-%d", time.localtime(D.now() + 86400))
        ev = {"name": "Race night", "date": day, "at": "21:00", "minutes": 120, "map": "gridmap_v2", "announce": 30,
              "game": "race", "results": True}
        st, d = self.c.call("/api/events", {"events": [ev]})[:2]
        self.assertEqual(st, 200, d)
        st, d = self.c.call("/api/events")[:2]
        e = d["events"][0]
        self.assertEqual((e["date"], e["game"], e["results"], e["days"]), (day, "race", True, []))
        self.assertTrue(e["next"])
        self.assertIn("race", [g["id"] for g in d["games"]])
        self.assertEqual(self.c.call("/api/events", {"events": [dict(ev, date="tomorrow")]})[0], 400)
        self.assertEqual(self.c.call("/api/events", {"events": [dict(ev, game="poker")]})[0], 400)
        self.assertEqual(self.c.call("/api/events", {"events": [dict(ev, date="", days=[])]})[0], 400)

    def test_start_switches_the_game_on(self):
        cfg = D.read_games_cfg()
        self.addCleanup(D.write_games_cfg, dict(cfg))
        D.write_games_cfg(dict(cfg, drift=False))
        t = D.now()
        e = {"id": "dn1", "name": "Drift night", "date": time.strftime("%Y-%m-%d", time.localtime(t)),
             "at": time.strftime("%H:%M", time.localtime(t)), "minutes": 60, "map": D.current_map(), "mods": [],
             "announce": 0, "game": "drift", "results": True, "on": True}
        D.set_server_meta("main", events=[e], event_active=None)
        with mock.patch.object(D, "online_names", lambda: []), mock.patch.object(D, "webhook_parts", lambda: ("", "")):
            D.APP._event_tick(D.INSTANCES["main"], {})
        act = D.INSTANCES["main"].meta["event_active"]
        self.assertEqual((act["game"], act["game_prev"], act["results"], act["once"]), ("drift", False, True, True))
        self.assertTrue(D.read_games_cfg()["drift"])

    def test_end_posts_results_and_turns_one_off_events_off(self):
        cfg = D.read_games_cfg()
        self.addCleanup(D.write_games_cfg, dict(cfg))
        D.write_games_cfg(dict(cfg, race=True))
        t0 = D.now() - 3600
        D.set_server_meta("main", events=[{"id": "rn1", "name": "Race night", "on": True, "date": "2026-01-01", "at": "20:00",
                                           "days": [], "minutes": 60, "map": "gridmap_v2"}],
                          event_active={"id": "rn1", "name": "Race night", "end": D.now() - 5, "prev_map": None, "mods": [],
                                        "start": t0, "game": "race", "game_prev": False, "results": True, "once": True,
                                        "online": ["Host"]})
        posts = []
        laps = {"t1": [{"name": "Dani", "ms": 61234, "car": "etk800", "t": t0 + 60}, {"name": "Old", "ms": 50000, "car": "", "t": t0 - 999}]}
        with mock.patch.object(D, "online_names", lambda: []), \
                mock.patch.object(D, "webhook_parts", lambda: ("1", "x")), \
                mock.patch.object(D, "webhook_call", lambda m, body=None, **k: posts.append(body["content"])), \
                mock.patch.object(D, "read_events", lambda since=0: [{"ev": "join", "name": "Dani", "t": t0 + 5},
                                                                    {"ev": "join", "name": "Sam", "t": t0 + 9}]), \
                mock.patch.object(D, "read_laptimes", lambda: laps), \
                mock.patch.object(D, "read_drift", lambda: [{"raw_map": "x", "name": "Sam", "score": 4200, "car": "", "t": t0 + 30}]):
            D.APP._event_tick(D.INSTANCES["main"], {})
        meta = D.INSTANCES["main"].meta
        self.assertNotIn("event_active", meta)
        self.assertFalse(D.read_games_cfg()["race"])              # was off before the event
        self.assertFalse(meta["events"][0]["on"])                  # a one-off event is done
        self.assertEqual(meta["event_last"]["results"]["players"], ["Host", "Dani", "Sam"])   # Host was on when it started
        self.assertEqual(len(posts), 1)
        self.assertIn("3 players joined", posts[0])
        self.assertIn("1:01.234", posts[0])
        self.assertNotIn("Old", posts[0])                          # set before the event
        self.assertIn("4200 points", posts[0])


class StatusPage(Base):
    def test_about_discord_and_link_preview(self):
        st, d = self.c.call("/api/statuspage", {"on": True, "about": "Drift <b>fun</b>\nFridays", "discord": "https://discord.gg/abc123"})[:2]
        self.assertEqual(st, 200, d)
        self.assertEqual(self.c.call("/api/statuspage", {"discord": "https://evil.example/x"})[0], 400)
        D._STATUS_CACHE["t"] = 0
        html = D.render_status_page(D.public_status())
        self.assertIn('property="og:description"', html)
        self.assertIn("Join our Discord", html)
        self.assertIn("https://discord.gg/abc123", html)
        self.assertIn("Drift &lt;b&gt;fun&lt;/b&gt;", html)
        self.assertNotIn("<b>fun</b>", html)

    def test_join_time_and_events(self):
        D.APP.settings.update({"upload_mbit": 10})
        mods = [{"name": "a.zip", "size": 75 * 10 ** 6, "enabled": True, "builtin": False, "maps": []}]
        with mock.patch.object(D, "list_mods", lambda: mods):
            secs, total = D.join_estimate(D.INSTANCES["main"])
        self.assertEqual((secs, total), (60, 75 * 10 ** 6))
        day = time.strftime("%Y-%m-%d", time.localtime(D.now() + 86400))
        D.set_server_meta("main", events=[{"id": "a", "name": "Cops night", "on": True, "date": day, "at": "20:00", "days": [],
                                           "minutes": 60, "map": "", "game": "cnr", "text": "Bring a fast car"}])
        D._STATUS_CACHE["t"] = 0
        d = D.public_status()
        ev = d["servers"][0]["events"][0]
        self.assertEqual((ev["name"], ev["game"]), ("Cops night", "Cops and robbers"))
        html = D.render_status_page(d)
        self.assertIn("Coming up", html)
        self.assertIn("Bring a fast car", html)


class DiscordHub(Base):
    def test_commands_listed(self):
        names = [c["name"] for c in D.DiscordBot.commands(mock.Mock())] if hasattr(D, "DiscordBot") else []
        if names:
            self.assertIn("player", names)
            self.assertIn("leaderboard", names)

    def test_player_embed(self):
        self.assertIn("hasn't played", D.discord_player_embed("Nobody_" + str(D.now()))["description"])
        card = {"name": "Dani", "online": False, "seen": True, "seconds": 7200, "seconds_30d": 3600, "sessions": 3,
                "first_seen": 1, "last_seen": D.now() - 60, "laps": [{"track": "Loop", "time": "1:01.234", "pos": 1, "of": 4, "car": ""}],
                "drift": {"score": 999, "car": ""}, "champ": {"pos": 2, "of": 5, "points": 40}, "badges": 2, "records": None,
                "server": "Main", "id": "main"}
        with mock.patch.object(D, "player_everywhere", lambda name, ids: [card]):
            e = D.discord_player_embed("dani")
        self.assertEqual(e["title"], "Dani")
        for want in ("2.0 h", "Loop: 1:01.234 (#1 of 4)", "999 points", "#2 of 5", "2 badges"):
            self.assertIn(want, e["description"])

    def test_leaderboards(self):
        rows = [{"raw_map": "/levels/utah/info.json", "name": "A", "score": 10, "car": "", "t": 1},
                {"raw_map": "/levels/utah/info.json", "name": "A", "score": 30, "car": "", "t": 2},
                {"raw_map": "/levels/utah/info.json", "name": "B", "score": 20, "car": "", "t": 3}]
        with mock.patch.object(D, "read_drift", lambda: rows):
            e = D.discord_leaderboard_embed(D.INSTANCES["main"], "drift")
        lines = e["description"].splitlines()
        self.assertTrue(lines[0].startswith("🥇 **A** - 30"), lines)
        self.assertTrue(lines[1].startswith("🥈 **B** - 20"), lines)
        self.assertIn("Nothing here yet", D.discord_leaderboard_embed(D.INSTANCES["main"], "champ")["description"])
        self.assertEqual(D.I().id, "main")

    def test_profile_elsewhere(self):
        st, d = self.c.call("/api/players/profile?name=Dani")[:2]
        self.assertEqual(st, 200, d)
        self.assertIn("elsewhere", d)


class ModAdvice(Base):
    def test_unused_and_double(self):
        mods = [{"name": "tool.zip", "size": 1, "enabled": True, "builtin": True, "maps": []},
                {"name": "bus.zip", "size": 300, "enabled": True, "builtin": False, "maps": []},
                {"name": "bus_old.zip", "size": 100, "enabled": True, "builtin": False, "maps": []},
                {"name": "car.zip", "size": 50, "enabled": True, "builtin": False, "maps": []},
                {"name": "island.zip", "size": 900, "enabled": True, "builtin": False, "maps": ["far_island"]},
                {"name": "off.zip", "size": 999, "enabled": False, "builtin": False, "maps": []}]
        vehs = {"bus.zip": [{"jbm": "citybus", "name": "City bus", "defines": True}],
                "bus_old.zip": [{"jbm": "citybus", "name": "City bus", "defines": True}],
                "car.zip": [{"jbm": "fastcar", "name": "Fast car", "defines": True}]}
        t = D.now()
        evs = [{"ev": "join", "name": "x", "t": t - 10 * 86400}, {"ev": "spawn", "name": "x", "jbm": "fastcar", "t": t - 100},
               {"ev": "spawn", "name": "x", "jbm": "citybus", "t": t - 50}]
        D.APP.settings.update({"upload_mbit": 1})
        with mock.patch.object(D, "list_mods", lambda: mods), \
                mock.patch.object(D, "mod_vehicles", lambda p: vehs.get(os.path.basename(p), [])), \
                mock.patch.object(D, "read_events", lambda since=0: evs), \
                mock.patch.dict(D.INSTANCES["main"].meta, {"light_maps": False}):
            a = D.mod_advice(D.INSTANCES["main"])
        kinds = {x["name"]: x["kind"] for x in a["items"]}
        self.assertEqual(kinds, {"island.zip": "map", "bus.zip": "double"})
        self.assertEqual(a["save"], 1200)
        self.assertTrue(a["enough"])
        evs[:] = [{"ev": "spawn", "name": "x", "jbm": "fastcar", "t": t - 100}, {"ev": "join", "name": "x", "t": t - 10 * 86400}]
        with mock.patch.object(D, "list_mods", lambda: mods), \
                mock.patch.object(D, "mod_vehicles", lambda p: vehs.get(os.path.basename(p), [])), \
                mock.patch.object(D, "read_events", lambda since=0: evs):
            kinds = {x["name"]: x["kind"] for x in D.mod_advice(D.INSTANCES["main"])["items"]}
        self.assertEqual(kinds.get("bus_old.zip"), "unused")
        self.assertEqual(self.c.call("/api/mods/advice")[0], 200)


class FakeGoogle:
    """Answers the few Google calls the dashboard makes."""

    def __init__(self):
        self.files, self.calls, self.pending = [], [], 1

    def __call__(self, url, fields=None, method=None, body=None, headers=None, timeout=30, want_headers=False):
        self.calls.append((method, url, fields))
        if url.endswith("/device/code"):
            assert fields["scope"] == D.GDRIVE_SCOPE
            return {"device_code": "dev", "user_code": "ABCD-EFGH", "verification_url": "https://www.google.com/device",
                    "expires_in": 600, "interval": 0}
        if url.endswith("/token"):
            if fields.get("grant_type", "").endswith("device_code") and self.pending:
                self.pending -= 1
                e = D.GDriveError("pending")
                e.code, e.kind = 428, "authorization_pending"
                raise e
            return {"access_token": "at", "expires_in": 3600, "refresh_token": "rt"}
        if url.endswith("/revoke"):
            return {}
        if "/about" in url:
            return {"user": {"emailAddress": "someone@example.com"}, "storageQuota": {"limit": "15000000000", "usage": "1000"}}
        if url.startswith(D.GDRIVE_UPLOAD):
            name = json.loads(body)["name"]
            out = {}, {"Location": "https://www.googleapis.com/upload/x?id=%s" % name}
            return out if want_headers else out[0]
        if url.startswith("https://www.googleapis.com/upload/x"):
            name = url.split("id=")[1]
            self.files.insert(0, {"id": "f%d" % len(self.calls), "name": name, "size": str(len(body.read())),
                                  "createdTime": "x"})
            return {}
        if "/files/" in url and method == "DELETE":
            fid = url.rsplit("/", 1)[1]
            self.files = [f for f in self.files if f["id"] != fid]
            return {}
        if "/files/" in url:
            return {"id": "folder1", "trashed": False}
        if "/files" in url and method == "POST":
            return {"id": "folder1"}
        if "/files" in url:
            return {"files": list(self.files)}
        raise AssertionError(url)


class GDrive(Base):
    def setUp(self):
        super().setUp()
        self.g = FakeGoogle()
        for p in (mock.patch.object(D, "_google", self.g), mock.patch.object(D, "GDRIVE_CLIENT_ID", "123-abc.apps.googleusercontent.com"),
                  mock.patch.object(D, "GDRIVE_CLIENT_SECRET", "not-secret"), mock.patch.object(D, "GDRIVE_MIN_WAIT", 0),
                  mock.patch.dict(D._GD, {"flow": None, "access": "", "exp": 0})):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(lambda: D.APP.secrets.cache.pop("GDRIVE_REFRESH", None))
        D.APP.secrets.cache.pop("GDRIVE_REFRESH", None)
        D.APP.settings.update({"gdrive_client_id": "", "gdrive_folder": "", "backup_on": False})

    def wait_flow(self):
        for _ in range(100):
            if D._GD["flow"]["state"] != "waiting":
                return D._GD["flow"]
            time.sleep(0.05)
        self.fail("sign-in never finished")

    def test_connect_copy_keep_and_restore(self):
        st, d = self.c.call("/api/gdrive")[:2]
        self.assertEqual(st, 200, d)
        self.assertTrue(d["ready"])
        self.assertFalse(d["connected"])
        self.assertIn("total", d["estimate"])
        st, d = self.c.call("/api/gdrive", {"action": "connect"})[:2]
        self.assertEqual(st, 200, d)
        self.assertEqual(d["flow"]["code"], "ABCD-EFGH")
        self.assertEqual(self.wait_flow()["state"], "done")
        self.assertTrue(D.gdrive_connected())
        self.assertTrue(D.APP.settings.get("gdrive_on"))
        self.assertEqual(D.APP.settings.get("gdrive_account"), "someone@example.com")
        # copies: the newest 7 of each server stay
        os.makedirs(D.BACKUP_DIR, exist_ok=True)
        made = []
        for i in range(9):
            n = "main-202611%02d-0300.zip" % (i + 1)
            with open(os.path.join(D.BACKUP_DIR, n), "wb") as f:
                f.write(b"PK" + bytes(i))
            self.addCleanup(lambda n=n: os.path.exists(os.path.join(D.BACKUP_DIR, n)) and os.remove(os.path.join(D.BACKUP_DIR, n)))
            made.append(n)
            D.gdrive_copy([n])
        names = [f["name"] for f in D.gdrive_list()]
        self.assertEqual(len(names), D.BACKUP_KEEP)
        self.assertTrue(all(n.startswith(D.backup_tag() + "-main-") for n in names))
        self.assertNotIn(D.backup_tag() + "-" + made[0], names)
        st, d = self.c.call("/api/gdrive?details=1")[:2]
        self.assertEqual(d["drive"]["free"], 15000000000 - 1000)
        self.assertEqual(len(d["files"]), D.BACKUP_KEEP)
        # restore downloads it and imports it as a backup
        fid = d["files"][0]["id"]
        with mock.patch.object(D, "gdrive_download", lambda i, dest: open(dest, "wb").write(b"not a zip")), \
                mock.patch.object(D, "make_backup", lambda inst, mods: "main-undo.zip"):
            st, d = self.c.call("/api/gdrive", {"action": "restore", "id": fid})[:2]
        self.assertEqual(st, 400, d)                                # went all the way to the import
        self.assertIn("export file", d.get("error", ""))
        self.assertEqual(self.c.call("/api/gdrive", {"action": "restore", "id": "nope"})[0], 404)
        # disconnect
        st, d = self.c.call("/api/gdrive", {"action": "disconnect"})[:2]
        self.assertEqual(st, 200)
        self.assertFalse(D.gdrive_connected())
        self.assertTrue(any(u.endswith("/revoke") for _, u, _ in self.g.calls))

    def test_own_app_and_not_ready(self):
        with mock.patch.object(D, "GDRIVE_CLIENT_ID", ""):
            self.assertEqual(self.c.call("/api/gdrive", {"action": "connect"})[0], 400)
            self.assertEqual(self.c.call("/api/gdrive", {"action": "own_app", "client_id": "nope"})[0], 400)
            self.assertEqual(self.c.call("/api/gdrive", {"action": "own_app", "client_id": "123456-abcdefghijkl.apps.googleusercontent.com"})[0], 400)
            st, d = self.c.call("/api/gdrive", {"action": "own_app", "client_id": "123456-abcdefghijkl.apps.googleusercontent.com",
                                                "client_secret": "s3"})[:2]
            self.assertEqual(st, 200, d)
            self.assertTrue(self.c.call("/api/gdrive")[1]["ready"])
            self.c.call("/api/gdrive", {"action": "own_app", "client_id": ""})
            self.assertFalse(self.c.call("/api/gdrive")[1]["ready"])

    def test_expired_access(self):
        D.APP.secrets.cache["GDRIVE_REFRESH"] = "rt"

        def bad(url, fields=None, **kw):
            e = D.GDriveError("Google said 400: bad")
            e.code, e.kind = 400, "invalid_grant"
            raise e
        with mock.patch.object(D, "_google", bad):
            with self.assertRaisesRegex(D.GDriveError, "connect it again"):
                D.gdrive_token()

    def test_health_counts_drive_as_a_copy(self):
        D.APP.secrets.cache["GDRIVE_REFRESH"] = "rt"
        D.APP.settings.update({"backup_on": True, "backup_copy": "", "gdrive_on": True})
        self.addCleanup(D.APP.state.pop, "gdrive_last", None)
        D.APP.state.pop("gdrive_last", None)
        with mock.patch.object(D, "internet_ok", lambda: False):
            checks = {c["id"]: c for c in D.health_report()["checks"]}
            self.assertEqual(checks["backups"]["state"], "pass")
            D.APP.state["gdrive_last"] = {"t": 1, "ok": False, "note": "Google said no"}
            checks = {c["id"]: c for c in D.health_report()["checks"]}
            self.assertIn("Google said no", checks["backups"]["detail"])


if __name__ == "__main__":
    unittest.main()
