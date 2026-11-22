"""Live tests: the real dashboard answers HTTP requests in a throw-away folder, and these tests attack
it like an outsider, a logged-in viewer or a moderator would. Linux only (on Windows keys are stored
with DPAPI, which these tests don't fake)."""
import os
import sys
import time
import unittest

import harness
from harness import D, Client

LINUX = not D.IS_WIN
PUBLIC = {("GET", "/api/session"), ("POST", "/api/login"), ("POST", "/api/setup")}


@unittest.skipUnless(LINUX, "live tests run on Linux")
class Live(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()

    # ---------------------------------------------------------------- outsiders
    def test_every_api_route_needs_login(self):
        anon = Client(self.base)
        anon.refresh()
        open_routes = []
        for method, path in harness.routes():
            if (method, path) in PUBLIC:
                continue
            body = {} if method in ("POST", "PUT") else None
            st = anon.call(path, body, method=method)[0]
            if st != 401:
                open_routes.append("%s %s -> %d" % (method, path, st))
        self.assertEqual(open_routes, [], "reachable without logging in")

    def test_setup_only_once(self):
        c = Client(self.base)
        c.refresh()
        self.assertEqual(c.call("/api/setup", {"password": "attacker-password-1"})[0], 403)

    def test_wrong_password_and_lockout(self):
        c = Client(self.base)
        sts = [c.login("wrong-password-%d" % i) for i in range(12)]
        self.assertEqual(sts[0], 401)
        self.assertIn(429, sts, "repeated wrong passwords must lock the address out")
        harness_reset_lockouts()

    def test_csrf_required(self):
        c = self.owner
        good = c.csrf
        try:
            c.csrf = ""
            self.assertEqual(c.call("/api/maintenance", {"state": "off"})[0], 403)
            c.csrf = "x" * 32
            self.assertEqual(c.call("/api/maintenance", {"state": "off"})[0], 403)
            c.csrf = good
            self.assertEqual(c.call("/api/maintenance", {"state": "off"}, headers={"Origin": "https://evil.example"})[0], 403)
        finally:
            c.csrf = good

    def test_dns_rebinding_blocked(self):
        st = Client(self.base).call("/api/session", headers={"Host": "evil.example.com"})[0]
        self.assertEqual(st, 421)

    def test_security_headers(self):
        st, _, h = Client(self.base).call("/")
        self.assertEqual(st, 200)
        self.assertIn("default-src 'none'", h.get("Content-Security-Policy", ""))
        self.assertEqual(h.get("X-Frame-Options"), "DENY")
        self.assertEqual(h.get("X-Content-Type-Options"), "nosniff")

    def test_session_cookie_flags(self):
        cookie = next(c for c in self.owner.jar if c.name == "es_session")
        self.assertTrue(cookie.has_nonstandard_attr("HttpOnly"))
        self.assertEqual(cookie.get_nonstandard_attr("SameSite"), "Strict")

    def test_oversized_body_refused(self):
        big = b'{"items":[' + b'{"at":"20:00","days":[1],"text":"x"},' * 60000 + b'{}]}'
        try:
            st = self.owner.call("/api/timed", raw=big, headers={"Content-Type": "application/json"})[0]
        except OSError:
            st = 413            # the connection was closed: also a refusal
        self.assertNotEqual(st, 200)

    # ---------------------------------------------------------------- logged in, but hostile input
    def test_upload_names_cannot_escape(self):
        for name in ("../../evil.zip", "/tmp/evil.zip", "CON.zip"):
            self.owner.call("/api/mods/upload?name=" + name.replace("/", "%2F"), method="PUT",
                            raw=b"PK\x05\x06" + b"\0" * 18, headers={"Content-Type": "application/octet-stream"})
        self.assertFalse(os.path.exists(os.path.join(harness.TMP, "evil.zip")))
        self.assertFalse(os.path.exists("/tmp/evil.zip") and os.path.getmtime("/tmp/evil.zip") > time.time() - 60)
        self.assertFalse(os.path.exists(os.path.join(harness.SRV, "Resources", "Client", "CON.zip")))
        for n in ("evil.zip",):
            p = os.path.join(harness.SRV, "Resources", "Client", n)
            if os.path.exists(p):
                os.remove(p)

    def test_check_new_mods_skips_checked_ones(self):
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("vehicles/testcar/info.json", '{"Name": "Test car %f"}' % time.time())
        path = os.path.join(harness.SRV, "Resources", "Client", "zz_scan_test.zip")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(buf.getvalue())
        try:
            first = self.owner.call("/api/mods/rescan", {})[1]
            mine = next(x for x in first["results"] if x["name"] == "zz_scan_test.zip")
            self.assertFalse(mine["skipped"])                     # new: checked
            again = self.owner.call("/api/mods/rescan", {})[1]
            self.assertTrue(next(x for x in again["results"] if x["name"] == "zz_scan_test.zip")["skipped"])
            self.assertEqual(again["checked"], 0)                 # nothing new
            full = self.owner.call("/api/mods/rescan", {"all": True})[1]
            self.assertFalse(next(x for x in full["results"] if x["name"] == "zz_scan_test.zip")["skipped"])
            self.assertEqual(full["skipped"], 0)
            # changed content counts as new again
            with zipfile.ZipFile(path, "a") as z:
                z.writestr("vehicles/testcar/extra.txt", "changed")
            later = self.owner.call("/api/mods/rescan", {})[1]
            self.assertFalse(next(x for x in later["results"] if x["name"] == "zz_scan_test.zip")["skipped"])
        finally:
            if os.path.exists(path):
                os.remove(path)

    def _mkmod(self, folder, name):
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("vehicles/%s/info.json" % name[:-4], '{"Name": "%s %f"}' % (name, time.time()))
        path = os.path.join(harness.SRV, "Resources", folder, name)
        with open(path, "wb") as f:
            f.write(buf.getvalue())
        return path

    def _where(self, name):
        for folder, on in (("Client", True), ("Client-disabled", False)):
            if os.path.exists(os.path.join(harness.SRV, "Resources", folder, name)):
                return on
        return None

    def test_mod_sets(self):
        names = ["zz_set_a.zip", "zz_set_b.zip", "zz_set_c.zip"]
        made = [self._mkmod("Client", names[0]), self._mkmod("Client", names[1]), self._mkmod("Client-disabled", names[2])]
        c = self.owner
        try:
            self.assertEqual(c.call("/api/mods/sets", {"action": "save", "name": "<b>bad</b>"})[0], 400)
            self.assertEqual(c.call("/api/mods/sets", {"action": "apply", "name": "Nope"})[0], 404)
            st, r = c.call("/api/mods/sets", {"action": "save", "name": "Drift night"})[:2]
            self.assertEqual(st, 200, r)
            d = c.call("/api/mods")[1]
            mine = next(x for x in d["sets"] if x["name"] == "Drift night")
            self.assertTrue(mine["active"])
            self.assertIn(names[0], mine["mods"])
            self.assertNotIn(names[2], mine["mods"])
            # change what's on, then switch back to the set
            c.call("/api/mods/action", {"action": "toggle", "name": names[0]})
            c.call("/api/mods/action", {"action": "toggle", "name": names[2]})
            self.assertFalse(next(x for x in c.call("/api/mods")[1]["sets"] if x["name"] == "Drift night")["active"])
            st, r = c.call("/api/mods/sets", {"action": "apply", "name": "drift NIGHT"})[:2]   # names ignore case
            self.assertEqual(st, 200, r)
            self.assertEqual([self._where(n) for n in names], [True, True, False])
            self.assertIn(names[0], r["on"])
            self.assertIn(names[2], r["off"])
            # a mod that was deleted is reported, not an error
            os.remove(made[1])
            r = c.call("/api/mods/sets", {"action": "apply", "name": "Drift night"})[1]
            self.assertEqual(r["missing"], [names[1]])
            self.assertEqual(c.call("/api/mods/sets", {"action": "delete", "name": "Drift night"})[0], 200)
            self.assertFalse(any(x["name"] == "Drift night" for x in c.call("/api/mods")[1]["sets"]))
            self.assertEqual(self._where(names[0]), True)            # deleting a set keeps the mods
        finally:
            c.call("/api/mods/sets", {"action": "delete", "name": "Drift night"})
            for n in names:
                for folder in ("Client", "Client-disabled"):
                    p = os.path.join(harness.SRV, "Resources", folder, n)
                    if os.path.exists(p):
                        os.remove(p)

    def test_mods_storage_and_full_disk(self):
        d = self.owner.call("/api/mods")[1]
        self.assertIsNotNone(d["storage"]["free"])
        self.assertGreaterEqual(d["storage"]["total"], d["storage"]["free"])
        old = D.UPLOAD_SPARE
        D.UPLOAD_SPARE = d["storage"]["free"] * 4           # pretend the disk is full
        try:
            st, r = self.owner.call("/api/mods/upload?name=zz_full.zip", method="PUT", raw=b"PK" + b"0" * 100,
                                    headers={"Content-Type": "application/zip"})[:2]
            self.assertEqual(st, 507)
            self.assertIn("Not enough space", r["error"])
            self.assertIsNone(self._where("zz_full.zip"))
        finally:
            D.UPLOAD_SPARE = old

    def test_restore_a_backup(self):
        c = self.owner
        self.assertEqual(c.call("/api/backups/restore", {"file": "../../etc/passwd"})[0], 404)
        self.assertEqual(c.call("/api/backups/now", {})[0], 200)
        first = c.call("/api/backups")[1]["items"][0]["file"]
        before = D.APP.read_config_text()
        D.APP.write_config_text(before.replace('MaxPlayers = 8', 'MaxPlayers = 3') if 'MaxPlayers = 8' in before else
                                D.toml_set(before, "General", "MaxPlayers", 3))
        try:
            st, r = c.call("/api/backups/restore", {"file": first})[:2]
            self.assertEqual(st, 200, r)
            self.assertTrue(r["undo"])
            self.assertNotEqual(r["undo"], first)              # the restored backup is still there
            self.assertIn(first, [x["file"] for x in c.call("/api/backups")[1]["items"]])
            self.assertIn(r["undo"], [x["file"] for x in c.call("/api/backups")[1]["items"]])
            self.assertEqual(D.toml_parse(D.APP.read_config_text())[0]["General"]["MaxPlayers"],
                             D.toml_parse(before)[0]["General"]["MaxPlayers"])
        finally:
            D.APP.write_config_text(before)

    def test_reports_and_chat_history(self):
        import json as _json
        inst = D.I()
        S = D.APP._monitor_init(inst)
        t = D.now()
        chat = os.path.join(inst.STATS_DIR, "chat.log")
        with open(chat, "w") as f:
            for i, (n, m) in enumerate((("Bob", "get out of my way"), ("Bob", "[click](http://evil.example)"),
                                        ("Alice", "stop ramming me"), ("Alice", "/report Bob ramming"))):
                f.write(_json.dumps({"t": t - 30 + i, "name": n, "msg": m}) + "\n")
            f.write(_json.dumps({"t": t - 20, "name": "Bob", "msg": "badword", "hid": 1}) + "\n")
        with open(os.path.join(inst.STATS_DIR, "events.log"), "a") as f:
            f.write(_json.dumps({"t": t, "ev": "report", "name": "Alice", "target": "Bob", "reason": "ramming [x](y)"}) + "\n")
        try:
            D.APP._monitor_one(inst, S)
            r = self.owner.call("/api/reports")[1]
            mine = next(x for x in r["items"] if x["by"] == "Alice" and x["target"] == "Bob" and x["t"] == t)
            self.assertTrue(mine["open"])
            self.assertEqual(mine["reason"], "ramming (x)(y)")             # no clickable links in Discord
            self.assertIn("stop ramming me", [c["msg"] for c in mine["chat"]])
            self.assertNotIn("/report Bob ramming", [c["msg"] for c in mine["chat"]])
            note = next(n for n in D.APP.notifier.items if n["kind"] == "report")
            self.assertIn("Alice reported Bob", note["title"])
            self.assertNotIn("](http", note["message"])
            # search + context
            d = self.owner.call("/api/chat?q=ramming")[1]
            self.assertEqual([c["msg"] for c in d["lines"]], ["stop ramming me", "/report Bob ramming"])
            d = self.owner.call("/api/chat?player=bob")[1]
            self.assertEqual(len(d["lines"]), 3)
            self.assertTrue(any(c["hid"] for c in d["lines"]))
            d = self.owner.call("/api/chat?around=%d" % (t - 28))[1]
            self.assertEqual(len(d["lines"]), 5)
            self.assertEqual(self.owner.call("/api/reports/close", {"id": mine["id"]})[0], 200)
            self.assertFalse(next(x for x in self.owner.call("/api/reports")[1]["items"] if x["id"] == mine["id"])["open"])
            self.assertEqual(self.owner.call("/api/reports/close", {"id": "nope"})[0], 404)
            self.assertEqual(self.owner.call("/api/chat/clear", {})[0], 200)
            self.assertFalse(os.path.exists(chat))
        finally:
            if os.path.exists(chat):
                os.remove(chat)

    def test_moderation_settings_for_reports_and_vote_kick(self):
        c = self.owner
        d = c.call("/api/moderation")[1]
        self.assertTrue(d["report"])
        self.assertFalse(d["votekick"])
        self.assertTrue(d["chatlog"])
        try:
            self.assertEqual(c.call("/api/moderation", {"votekick": True, "votekick_min": 2})[0], 400)
            self.assertEqual(c.call("/api/moderation", {"votekick": True, "votekick_min": 5, "chatlog": False})[0], 200)
            with open(D.I().MOD_FILE) as f:
                text = f.read()
            self.assertIn("votekick=on\nvotekick_min=5\nchatlog=off", text)
        finally:
            c.call("/api/moderation", {"votekick": False, "votekick_min": 4, "chatlog": True})

    def test_webhook_cannot_target_home_network(self):
        for u in ("https://127.0.0.1:30815/api/logout", "https://169.254.169.254/latest/", "https://192.168.1.1/",
                  "http://hooks.example/x", "https://10.0.0.1@evil.example/"):
            self.assertEqual(self.owner.call("/api/integrations", {"webhook_url": u})[0], 400, u)

    def test_status_page_escapes_html(self):
        x = '<script>alert(1)</script><img src=x onerror=alert(2)>'
        self.assertEqual(self.owner.call("/api/statuspage", {"on": True, "title": x, "players": True})[0], 200)
        self.assertEqual(self.owner.call("/api/maintenance", {"state": "on", "message": x, "kick": False})[0], 200)
        try:
            st, page, h = Client(self.base).call("/status")
            self.assertEqual(st, 200)
            page = page.decode() if isinstance(page, bytes) else str(page)
            self.assertNotIn("<script>alert", page)
            self.assertNotIn("<img src=x", page)
            self.assertIn("&lt;script&gt;", page)
            self.assertNotIn("script-src", h.get("Content-Security-Policy", ""))
        finally:
            self.owner.call("/api/maintenance", {"state": "off"})
            self.owner.call("/api/statuspage", {"on": False, "title": ""})

    def test_status_page_credit_link(self):
        self.assertEqual(self.owner.call("/api/statuspage", {"on": True})[0], 200)
        try:
            page = Client(self.base).call("/status")[1]
            page = page.decode() if isinstance(page, bytes) else str(page)
            self.assertIn('href="%s"' % D.SITE_URL, page)
            self.owner.call("/api/statuspage", {"credit": False})
            page = Client(self.base).call("/status")[1]
            page = page.decode() if isinstance(page, bytes) else str(page)
            self.assertNotIn(D.SITE_URL, page)
        finally:
            self.owner.call("/api/statuspage", {"on": False, "credit": True})

    def test_status_page_off_by_default_and_404(self):
        self.owner.call("/api/statuspage", {"on": False})
        self.assertEqual(Client(self.base).call("/status")[0], 404)

    def test_config_history_never_stores_the_key(self):
        st, d, _ = self.owner.call("/api/config")
        self.assertEqual(st, 200)
        text = D.APP.read_config_text()
        D.APP.write_config_text(text.replace('AuthKey = ""', "AuthKey = 'abc-SECRET-999'"), why="test")
        D.APP.write_config_text(text, why="test")
        hist = os.path.join(D.HIST_DIR, "main")
        for n in os.listdir(hist):
            with open(os.path.join(hist, n)) as f:
                self.assertNotIn("SECRET", f.read(), n)
        items = self.owner.call("/api/config/history")[1]["items"]
        for v in items[:3]:
            self.assertNotIn("SECRET", repr(self.owner.call("/api/config/diff?v=" + v["id"])[1]))

    def test_maintenance_writes_plugin_file_safely(self):
        st = self.owner.call("/api/maintenance", {"state": "on", "message": "line1\nallow=evil\nX", "allow": "Bob", "kick": False})[0]
        self.assertEqual(st, 200)
        with open(os.path.join(harness.SRV, "Resources", "Server", "EasyServerStats", "maintenance.txt")) as f:
            lines = f.read().splitlines()
        self.assertEqual(lines[0], "on")
        self.assertTrue(lines[1].startswith("message="))
        self.assertEqual(lines[2:], ["Bob"], "a newline in the message must not add names to the list")
        self.owner.call("/api/maintenance", {"state": "off"})

    def test_bad_allow_names_refused(self):
        st = self.owner.call("/api/allowlist", {"enabled": False, "names": ["ok", "mode=off"]})[0]
        self.assertEqual(st, 400)

    # ---------------------------------------------------------------- roles
    def test_roles(self):
        o = self.owner
        for name, role in (("modtest", "moderator"), ("viewtest", "viewer")):
            st, d, _ = o.call("/api/users", {"action": "add", "name": name, "role": role, "password": name + "-password-1"})
            self.assertIn(st, (200, 400), d)       # 400 = already exists from an earlier run
        mod, view = Client(self.base), Client(self.base)
        self.assertEqual(mod.login("modtest-password-1", "modtest"), 200)
        self.assertEqual(view.login("viewtest-password-1", "viewtest"), 200)
        allowed = {"/api/maintenance": {"state": "off"}, "/api/allowlist": {"enabled": False, "names": []}}
        denied = {"/api/settings": {"update_check": True}, "/api/users": {"action": "add", "name": "x", "role": "admin", "password": "x-password-123"},
                  "/api/preset": {"id": "open"}, "/api/config/save": {"text": "x"}, "/api/integrations": {"event_ads": True},
                  "/api/statuspage": {"on": True}, "/api/tools": {"tp": True}, "/api/mods/light": {"on": True},
                  "/api/config/restore": {"v": "x"}, "/api/password": {"current": "x", "new": "y"}}
        for p, b in allowed.items():
            self.assertEqual(mod.call(p, b)[0], 200, "moderator " + p)
            self.assertEqual(view.call(p, b)[0], 403, "viewer " + p)
        for p, b in denied.items():
            self.assertEqual(mod.call(p, b)[0], 403, "moderator " + p)
            self.assertEqual(view.call(p, b)[0], 403, "viewer " + p)
        for p in ("/api/export", "/api/modpack", "/api/activity", "/api/users", "/api/phoneapp", "/api/health/report"):
            self.assertEqual(mod.call(p)[0], 403, "moderator GET " + p)
        self.assertEqual(view.call("/api/overview")[0], 200)
        for p in ("/api/chat", "/api/reports"):             # what players wrote: moderators yes, viewers no
            self.assertEqual(mod.call(p)[0], 200, "moderator GET " + p)
            self.assertEqual(view.call(p)[0], 403, "viewer GET " + p)
        self.assertEqual(mod.call("/api/chat/clear", {})[0], 403, "moderator deleted the chat history")

    def test_tampered_user_list_locks_extra_accounts(self):
        o = self.owner
        o.call("/api/users", {"action": "add", "name": "tamper", "role": "viewer", "password": "tamper-password-1"})
        with open(D.USERS_FILE) as f:
            raw = f.read()
        try:
            with open(D.USERS_FILE, "w") as f:
                f.write(raw.replace('"viewer"', '"admin"'))
            self.assertNotEqual(Client(self.base).login("tamper-password-1", "tamper"), 200)
        finally:
            with open(D.USERS_FILE, "w") as f:
                f.write(raw)


def harness_reset_lockouts():
    """Forget wrong-password counters so later tests can log in again."""
    for name in ("fails", "locked", "global_fails", "lan_fails"):
        v = getattr(D.APP, name, None)
        if hasattr(v, "clear"):
            v.clear()
    for name in dir(D):
        v = getattr(D, name)
        if name.isupper() and "FAIL" in name and hasattr(v, "clear"):
            v.clear()


if __name__ == "__main__":
    unittest.main()
