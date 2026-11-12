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
