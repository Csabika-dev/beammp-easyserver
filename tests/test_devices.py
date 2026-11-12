"""'Stay logged in on this device' and the http -> https redirect.

Remembered devices must survive a dashboard restart, be forgotten on logout and password changes,
never be stored in a readable form, and not work when the device list was changed by something else."""
import json
import os
import socket
import ssl
import tempfile
import threading
import unittest

import harness
from harness import D, Client

LINUX = not D.IS_WIN


def device_cookie(c):
    return next((x for x in c.jar if x.name == D.DEVICE_COOKIE), None)


def restart_sessions():
    """What a dashboard restart does to logins: the in-memory sessions are gone."""
    with D.LOCK:
        D.APP.sessions.clear()


@unittest.skipUnless(LINUX, "live tests run on Linux")
class Devices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        harness.owner()

    def setUp(self):
        D.forget_devices()

    def remembered(self, password=harness.PASSWORD, user=None):
        c = Client(self.base)
        self.assertEqual(c.login(password, user, remember=True), 200)
        return c

    def test_cookie_only_when_asked_and_flags(self):
        plain = Client(self.base)
        self.assertEqual(plain.login(), 200)
        self.assertIsNone(device_cookie(plain))
        c = self.remembered()
        ck = device_cookie(c)
        self.assertIsNotNone(ck)
        self.assertTrue(ck.has_nonstandard_attr("HttpOnly"))
        self.assertEqual(ck.get_nonstandard_attr("SameSite"), "Strict")
        self.assertGreater(ck.expires - D.now(), 29 * 86400)

    def test_survives_a_restart(self):
        c = self.remembered()
        restart_sessions()
        st, d, h = c.call("/api/session")
        self.assertTrue(d["logged_in"])
        self.assertEqual(d["role"], "owner")
        c.csrf = d["csrf"]
        self.assertEqual(c.call("/api/overview")[0], 200)
        self.assertEqual(c.call("/api/maintenance", {"state": "off"})[0], 200)

    def test_token_is_not_stored_readably(self):
        c = self.remembered()
        with open(D.DEVICES_FILE) as f:
            raw = f.read()
        self.assertNotIn(device_cookie(c).value, raw)

    def test_logout_forgets_the_device(self):
        c = self.remembered()
        tok = device_cookie(c).value
        self.assertEqual(c.call("/api/logout", {})[0], 200)
        self.assertIsNone(D.device_login(tok, "127.0.0.1"))
        thief = Client(self.base)
        thief.jar.set_cookie(_cookie(D.DEVICE_COOKIE, tok))
        self.assertFalse(thief.call("/api/session")[1]["logged_in"])

    def test_forget_from_settings(self):
        a, b = self.remembered(), self.remembered()
        devs = a.call("/api/devices")[1]["devices"]
        self.assertEqual(len(devs), 2)
        other = next(x for x in devs if not x["this"])
        self.assertEqual(a.call("/api/devices", {"action": "forget", "id": other["id"]})[0], 200)
        restart_sessions()
        self.assertTrue(a.call("/api/session")[1]["logged_in"])
        self.assertFalse(b.call("/api/session")[1]["logged_in"])

    def test_viewer_can_only_forget_their_own(self):
        o = harness.owner()
        o.call("/api/users", {"action": "add", "name": "devview", "role": "viewer", "password": "devview-password-1"})
        mine = self.remembered()
        v = self.remembered("devview-password-1", "devview")
        seen = v.call("/api/devices")[1]["devices"]
        self.assertEqual([x["user"] for x in seen], ["devview"])
        self.assertEqual(v.call("/api/devices", {"action": "forget_all"})[0], 200)
        restart_sessions()
        self.assertTrue(mine.call("/api/session")[1]["logged_in"], "a viewer must not log the owner out")
        self.assertFalse(v.call("/api/session")[1]["logged_in"])

    def test_password_change_and_delete_forget_the_account(self):
        o = harness.owner()
        o.call("/api/users", {"action": "add", "name": "devmod", "role": "moderator", "password": "devmod-password-1"})
        m = self.remembered("devmod-password-1", "devmod")
        self.assertEqual(o.call("/api/users", {"action": "password", "name": "devmod", "password": "devmod-password-2"})[0], 200)
        restart_sessions()
        self.assertFalse(m.call("/api/session")[1]["logged_in"])
        m = self.remembered("devmod-password-2", "devmod")
        o = harness.owner()
        self.assertEqual(o.call("/api/users", {"action": "delete", "name": "devmod"})[0], 200)
        restart_sessions()
        self.assertFalse(m.call("/api/session")[1]["logged_in"])

    def test_extra_accounts_only_from_home(self):
        o = harness.owner()
        o.call("/api/users", {"action": "add", "name": "devhome", "role": "viewer", "password": "devhome-password-1"})
        tok = device_cookie(self.remembered("devhome-password-1", "devhome")).value
        self.assertIsNotNone(D.device_login(tok, "192.168.1.20"))
        self.assertIsNone(D.device_login(tok, "8.8.8.8"))

    def test_tampered_list_is_ignored(self):
        c = self.remembered()
        tok = device_cookie(c).value
        with open(D.DEVICES_FILE) as f:
            d = json.load(f)
        d["devices"].append(dict(d["devices"][0], id="abcdef123456", hash=D._dev_hash("planted-token-planted-token")))
        with open(D.DEVICES_FILE, "w") as f:
            json.dump(d, f)
        self.assertIsNone(D.device_login("planted-token-planted-token", "127.0.0.1"))
        self.assertIsNone(D.device_login(tok, "127.0.0.1"), "an unsigned list is not trusted at all")

    def test_junk_tokens(self):
        for t in ("", "x", "a" * 500, "../../etc", "abc def ghi jkl mno pqr"):
            self.assertIsNone(D.device_login(t, "127.0.0.1"))

    def test_expired_device(self):
        c = self.remembered()
        tok = device_cookie(c).value
        with D._DEV_LOCK:
            devs = D.load_devices()
            devs[0]["last"] = D.now() - (D.DEVICE_DAYS + 1) * 86400
            D.save_devices(devs)
        self.assertIsNone(D.device_login(tok, "127.0.0.1"))


def _cookie(name, value):
    import http.cookiejar
    return http.cookiejar.Cookie(0, name, value, None, False, "127.0.0.1", False, False, "/", True, False, None,
                                 True, None, None, {})


@unittest.skipUnless(LINUX, "live tests run on Linux")
class HttpsRedirect(unittest.TestCase):
    """With HTTPS on, a plain http:// visit is sent to https:// instead of being cut off."""

    @classmethod
    def setUpClass(cls):
        harness.start()
        d = tempfile.mkdtemp(prefix="es-tls-")
        D.tlsgen.generate(d)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(os.path.join(d, "cert.pem"), os.path.join(d, "key.pem"))
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        cls.port = s.getsockname()[1]
        s.close()
        cls.httpd = D.Server(("127.0.0.1", cls.port), ctx)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def raw(self, data):
        with socket.create_connection(("127.0.0.1", self.port), timeout=10) as s:
            s.sendall(data)
            out = b""
            while True:
                part = s.recv(4096)
                if not part:
                    return out
                out += part

    def test_plain_http_is_redirected(self):
        out = self.raw(b"GET /settings HTTP/1.1\r\nHost: localhost:%d\r\n\r\n" % self.port)
        self.assertTrue(out.startswith(b"HTTP/1.1 301"), out[:80])
        self.assertIn(b"\r\nLocation: https://localhost:%d/\r\n" % self.port, out)

    def test_redirect_host_cannot_be_injected(self):
        out = self.raw(b"GET / HTTP/1.1\r\nHost: evil.example\r\nX: y\r\nLocation: http://x\r\n\r\n")
        self.assertIn(b"Location: https://evil.example:%d/" % self.port, out)   # same name, our port, https only
        out = self.raw(b"GET / HTTP/1.1\r\nHost: a\"b<script>\r\n\r\n")
        self.assertIn(b"Location: https://localhost:%d/" % self.port, out)
        self.assertNotIn(b"<script>", out)

    def test_https_still_works(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection(("127.0.0.1", self.port), timeout=10) as raw:
            with ctx.wrap_socket(raw, server_hostname="localhost") as s:
                s.sendall(b"GET /api/session HTTP/1.1\r\nHost: localhost:%d\r\nConnection: close\r\n\r\n" % self.port)
                out = b""
                while True:
                    part = s.recv(4096)
                    if not part:
                        break
                    out += part
        self.assertTrue(out.startswith(b"HTTP/1.0 200") or out.startswith(b"HTTP/1.1 200"), out[:80])

    def test_silent_client_does_not_block_others(self):
        idle = socket.create_connection(("127.0.0.1", self.port), timeout=10)
        try:
            self.test_plain_http_is_redirected()
        finally:
            idle.close()


if __name__ == "__main__":
    unittest.main()
