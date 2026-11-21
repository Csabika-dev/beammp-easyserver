"""Sign in with Discord (team accounts): the signed round trip through the sign-in service, and what must fail."""
import base64
import json
import os
import unittest
import urllib.parse
from unittest import mock

import harness
from harness import D, Client

KEY = b"k" * 32
INST = "A" * 24


def b64u(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def note(nonce, aud, sub="123456789012345678", key=KEY, inst=INST, exp=None, name="Dani"):
    """What the sign-in service sends back after Discord said who it is."""
    body = b64u(json.dumps({"v": 1, "inst": inst, "nonce": nonce, "aud": aud, "sub": sub, "user": "dani",
                            "name": name, "exp": exp or D.now() + 300}).encode())
    return body + "." + D.dlogin_sig(key, "assert|" + body)


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class DiscordLogin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()
        cls.port = int(cls.base.rsplit(":", 1)[1])
        cls._svc = mock.patch.object(D, "LOGIN_SERVICE", "https://login.example")
        cls._svc.start()
        cls._old_port = D.APP.settings.get("port")
        D.APP.settings.data["port"] = cls.port          # the address the browser uses is this dashboard's own
        if not D.APP.secrets.has("USERS_KEY"):
            D.APP.secrets.set("USERS_KEY", "u" * 64)
        D._team_save(D.DLOGIN_FILE, "discord-login", [{"on": True, "inst": INST, "key": D._seal(b64u(KEY), "dlogin")}])

    @classmethod
    def tearDownClass(cls):
        D.APP.settings.data["port"] = cls._old_port
        cls._svc.stop()
        try:
            os.remove(D.DLOGIN_FILE)
        except OSError:
            pass

    def add(self, name, **extra):
        self.owner.call("/api/users", {"action": "delete", "name": name})
        st, d, _ = self.owner.call("/api/users", dict({"action": "add", "name": name, "role": "moderator", "password": name + "-password-1"}, **extra))
        self.assertEqual(st, 200, d)
        c = Client(self.base)
        self.assertEqual(c.login(name + "-password-1", name), 200)
        return c

    def start(self, c, path="/api/discord/start"):
        st, d, _ = c.call(path, {})
        self.assertEqual(st, 200, d)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(d["url"]).query))
        self.assertTrue(d["url"].startswith("https://login.example/start?"))
        # the dashboard signed exactly what the service checks
        self.assertEqual(q["sig"], D.dlogin_sig(KEY, "start|%s|%s|%s|%s" % (q["inst"], q["nonce"], q["ret"], q["exp"])))
        self.assertEqual(q["ret"], self.base + "/")
        return q

    def test_link_then_sign_in(self):
        c = self.add("dcuser")
        q = self.start(c, "/api/me/discord/link")
        st, r, _ = c.call("/api/discord/finish", {"a": note(q["nonce"], q["ret"])})
        self.assertEqual(st, 200, r)
        self.assertEqual(r["linked"], "Dani")
        self.assertEqual(D.find_user("dcuser")["discord"]["id"], "123456789012345678")
        # now sign in from a fresh browser
        b = Client(self.base)
        self.assertTrue(b.call("/api/session")[1]["discord_login"])
        q = self.start(b)
        st, r, _ = b.call("/api/discord/finish", {"a": note(q["nonce"], q["ret"])})
        self.assertEqual(st, 200, r)
        b.refresh()
        self.assertEqual(b.call("/api/session")[1]["user"], "dcuser")
        # a note can only be used once
        self.assertEqual(b.call("/api/discord/finish", {"a": note(q["nonce"], q["ret"])})[0], 400)
        self.owner.call("/api/users", {"action": "delete", "name": "dcuser"})

    def test_two_step_code_still_needed(self):
        c = self.add("dc2fa")
        secret = c.call("/api/me/2fa/begin", {})[1]["secret"].replace(" ", "")
        self.assertEqual(c.call("/api/me/2fa/confirm", {"code": D.totp_code(secret, D.now() // 30)})[0], 200)
        q = self.start(c, "/api/me/discord/link")
        self.assertEqual(c.call("/api/discord/finish", {"a": note(q["nonce"], q["ret"], sub="99999999")})[0], 200)
        b = Client(self.base)
        q = self.start(b)
        a = note(q["nonce"], q["ret"], sub="99999999")
        st, r, _ = b.call("/api/discord/finish", {"a": a})
        self.assertEqual(st, 401)
        self.assertTrue(r.get("need_code"))
        self.assertEqual(b.call("/api/discord/finish", {"a": a, "code": D.totp_code(secret, D.now() // 30 + 1)})[0], 200)
        self.owner.call("/api/users", {"action": "delete", "name": "dc2fa"})

    def test_what_must_fail(self):
        c = self.add("dcbad")
        q = self.start(c, "/api/me/discord/link")
        self.assertEqual(c.call("/api/discord/finish", {"a": note(q["nonce"], q["ret"], sub="555555555")})[0], 200)
        b = Client(self.base)
        q = self.start(b)
        n, r = q["nonce"], q["ret"]
        bad = [
            note(n, r, sub="555555555", key=b"x" * 32),                  # not signed by the service
            note(n, r, sub="555555555", inst="B" * 24),                   # for another dashboard
            note(n, "http://evil.example/", sub="555555555"),            # sent to another address
            note(n, r, sub="555555555", exp=D.now() - 1),                 # too old
            note("Z" * 32, r, sub="555555555"),                           # someone else's sign-in
        ]
        for a in bad:
            self.assertEqual(b.call("/api/discord/finish", {"a": a})[0], 400, a)
            D.APP.fails.clear()                                       # (five wrong tries lock the address)
            D.APP.locked.clear()
        # a note that reached another browser (no matching cookie) is useless there
        other = Client(self.base)
        self.assertEqual(other.call("/api/discord/finish", {"a": note(n, r, sub="555555555")})[0], 400)
        # an unknown Discord account gets no session
        q = self.start(Client(self.base))
        x = Client(self.base)
        q = self.start(x)
        st, d, _ = x.call("/api/discord/finish", {"a": note(q["nonce"], q["ret"], sub="777777777")})
        self.assertEqual(st, 403)
        self.assertFalse(x.call("/api/session")[1]["logged_in"])
        self.owner.call("/api/users", {"action": "delete", "name": "dcbad"})

    def test_foreign_address_refused(self):
        b = Client(self.base)
        st, d, _ = b.call("/api/discord/start", {}, headers={"Host": "evil.example:%d" % self.port, "Origin": "http://evil.example:%d" % self.port})
        self.assertIn(st, (400, 421))
        self.assertNotIn("url", d if isinstance(d, dict) else {})

    def test_owner_cannot_link(self):
        self.assertEqual(self.owner.call("/api/me/discord/link", {})[0], 400)

    def test_owner_switch_and_unlink(self):
        c = self.add("dcunl")
        q = self.start(c, "/api/me/discord/link")
        self.assertEqual(c.call("/api/discord/finish", {"a": note(q["nonce"], q["ret"], sub="31313131")})[0], 200)
        users = self.owner.call("/api/users")[1]
        self.assertEqual(next(u for u in users["users"] if u["name"] == "dcunl")["discord"], "Dani")
        self.assertEqual(users["discord_login"], {"available": True, "on": True})
        self.assertEqual(self.owner.call("/api/users", {"action": "discord_unlink", "name": "dcunl"})[0], 200)
        self.assertIsNone(D.find_user("dcunl").get("discord"))
        self.assertEqual(c.call("/api/session")[1]["logged_in"], False)        # logged out
        self.assertEqual(c.call("/api/discordlogin", {"on": False})[0], 401)   # only the owner switches it
        self.owner.call("/api/users", {"action": "delete", "name": "dcunl"})


class SignInServiceCertificate(unittest.TestCase):
    """Windows: if Python's certificate check trips, the sign-up goes through Windows' own (still checked) HTTPS."""

    def test_windows_falls_back_to_its_own_https(self):
        import ssl
        import urllib.error

        def fake_urlopen(req, timeout=None):
            raise urllib.error.URLError(ssl.SSLCertVerificationError("certificate has expired"))
        asked, saved = [], []
        with mock.patch.object(D, "LOGIN_SERVICE", "https://login.example"), \
                mock.patch.object(D, "IS_WIN", True), \
                mock.patch.object(D.urllib.request, "urlopen", fake_urlopen), \
                mock.patch.object(D, "win_post_json", lambda u: asked.append(u) or {"inst": "C" * 24, "key": "k" * 43}), \
                mock.patch.object(D, "_team_load", lambda *a: []), \
                mock.patch.object(D, "_seal", lambda v, kind="": "sealed"), \
                mock.patch.object(D, "APP", mock.Mock()), \
                mock.patch.object(D, "_team_save", lambda *a: saved.append(a)):
            D.dlogin_set(True)
        self.assertEqual(asked, ["https://login.example/register"])
        self.assertEqual(saved[0][2][0]["inst"], "C" * 24)

    def test_no_fallback_elsewhere_or_for_other_errors(self):
        import ssl
        import urllib.error
        for win, err in ((False, ssl.SSLCertVerificationError("bad")), (True, OSError("no network"))):
            def fake_urlopen(req, timeout=None, err=err):
                raise urllib.error.URLError(err)
            with mock.patch.object(D, "LOGIN_SERVICE", "https://login.example"), \
                    mock.patch.object(D, "IS_WIN", win), \
                    mock.patch.object(D.urllib.request, "urlopen", fake_urlopen), \
                    mock.patch.object(D, "win_post_json", lambda u: self.fail("no fallback expected")), \
                    mock.patch.object(D, "_team_load", lambda *a: []):
                with self.assertRaises(ValueError):
                    D.dlogin_set(True)

    def test_only_plain_service_addresses(self):
        with mock.patch.object(D, "IS_WIN", True):
            self.assertIsNone(D.win_post_json("https://x.example/register'; Remove-Item C:\\ -Recurse; '"))
            self.assertIsNone(D.win_post_json("http://x.example/register"))
