"""Unit tests: small functions that protect the server. Each security fix has a test here so it can't
silently come back."""
import socket
import time
import unittest
from unittest import mock

import harness  # noqa: F401  (sets up a throw-away server folder first)
from harness import D


class Redaction(unittest.TestCase):
    """The AuthKey must never end up in config history, comparisons or diagnostic reports."""

    FORMS = ('AuthKey = "abc-SECRET-123"', "AuthKey = 'abc-SECRET-123'", "AuthKey='abc-SECRET-123'",
             'AuthKey = """abc-SECRET-123"""', "AuthKey = '''abc-SECRET-123'''", '  authkey = "abc-SECRET-123"',
             "AUTHKEY = abc-SECRET-123", 'AuthKey="abc-SECRET-123" # comment')

    def test_history_redaction_every_toml_form(self):
        for line in self.FORMS:
            self.assertNotIn("SECRET", D.redact_key(line), line)

    def test_report_redaction_every_toml_form(self):
        for line in self.FORMS:
            self.assertNotIn("SECRET", D.redact(line), line)

    def test_redacted_config_still_parses(self):
        cfg = "[General]\nName = \"x\"\nAuthKey = 'abc-SECRET-123'\nPort = 30814\n"
        g = D.toml_parse(D.redact_key(cfg))[0]["General"]
        self.assertEqual(g["AuthKey"], "")
        self.assertEqual(g["Port"], 30814)

    def test_report_hides_webhooks_and_tokens(self):
        # A made-up token, put together at run time so secret scanners
        # don't mistake it for a real one.
        fake = ".".join(["MTA5ODc2NTQzMjEwOTg3NjU0", "GhIjKl",
                         "aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"])
        t = D.redact("hook https://discord.com/api/webhooks/123/abcDEF token " + fake)
        self.assertNotIn("abcDEF", t)
        self.assertNotIn("aBcDeFgHiJ", t)


class Names(unittest.TestCase):
    def test_upload_names_stay_in_the_mods_folder(self):
        for bad, want in (("../../evil.zip", "evil.zip"), ("/etc/evil.zip", "evil.zip"), ("a/../../b.zip", "b.zip")):
            self.assertEqual(D.safe_zip_name(bad), want)
        for bad in ("evil.exe", ".zip", "ok.zip\x00.txt", "x" * 300 + ".zip", None, 5):
            self.assertIsNone(D.safe_zip_name(bad), repr(bad))

    def test_reserved_windows_names_refused(self):
        for bad in ("CON.zip", "con.ZIP", "nul.zip", "lpt1.zip", "COM3.zip", "aux.tar.zip"):
            self.assertIsNone(D.safe_zip_name(bad), bad)
        for ok in ("console.zip", "NULmap.zip", "map (v2).zip"):
            self.assertEqual(D.safe_zip_name(ok), ok)

    def test_player_names_lose_formatting(self):
        self.assertEqual(D.clean_player_name("@everyone **x** <@123> [a](b)"), "everyone x 123 ab")

    def test_discord_escape_blocks_pings_formatting_and_masked_links(self):
        t = D.discord_escape("[Free mods](https://evil.example) @everyone **bold** <@1>")
        self.assertNotIn("[Free mods](", t)
        self.assertNotIn("@everyone", t.replace("\\@", ""))
        self.assertIn("\\[", t)
        self.assertIn("\\*\\*", t)


class Webhook(unittest.TestCase):
    """The custom alert webhook may only reach the internet, never the home network."""

    def _resolve(self, mapping):
        real = socket.getaddrinfo

        def fake(host, *a, **k):
            if host in mapping:
                fam = socket.AF_INET6 if ":" in mapping[host][0] else socket.AF_INET
                return [(fam, 1, 6, "", (ip, 443)) for ip in mapping[host]]
            return real(host, *a, **k)
        return mock.patch("socket.getaddrinfo", fake)

    def test_internal_targets_refused(self):
        for h in ("127.0.0.1", "localhost", "169.254.169.254", "192.168.1.1", "10.0.0.1", "::1",
                  "0x7f000001", "100.64.0.1", "::ffff:127.0.0.1", "0.0.0.0"):
            self.assertFalse(D.public_host(h), h)

    def test_public_targets_allowed(self):
        with self._resolve({"hooks.example": ["34.236.124.18"], "v6.example": ["2606:4700::1111"]}):
            self.assertTrue(D.public_host("hooks.example"))
            self.assertTrue(D.public_host("v6.example"))

    def test_name_with_any_private_address_refused(self):
        with self._resolve({"rebind.example": ["8.8.8.8", "10.0.0.5"]}):
            self.assertFalse(D.public_host("rebind.example"))

    def test_url_shape(self):
        self.assertTrue(D.valid_custom_webhook("https://hooks.slack.com/services/x"))
        for bad in ("http://hooks.slack.com/x", "https://10.0.0.1@evil.com/", "https://x.com:99999/", "https://a b.com/", "", None):
            self.assertFalse(D.valid_custom_webhook(bad), repr(bad))


class LogExplainer(unittest.TestCase):
    def test_hostile_log_is_fast(self):
        """Player chat ends up in the log: crafted lines must not freeze the dashboard."""
        t = time.perf_counter()
        D.explain_log(("[CHAT] x: " + "backend proxy authkey attempt to " * 200 + "\n") * 2000)
        self.assertLess(time.perf_counter() - t, 3.0)

    def test_huge_log_stops_in_time(self):
        t = time.perf_counter()
        g = D.explain_log(("[ERROR] backend " * 40 + "\n") * 400000, budget=1.0)
        self.assertLess(time.perf_counter() - t, 3.0)
        self.assertTrue(any(x["id"] == "_partial" for x in g))

    def test_known_errors_recognised(self):
        cases = {"[ERROR] bind() failed: Address already in use": "port_busy",
                 "[LUA ERROR] main.lua:12: attempt to index a nil value": "lua_error",
                 "[ERROR] POST to https://backend.beammp.com/heartbeat failed": "backend_down",
                 "[WARN] Failed to unset IP_V6ONLY on TCP": "ipv6",
                 "[ERROR] something nobody knows": "unknown_error"}
        for line, rid in cases.items():
            self.assertEqual(D.explain_line(line)["id"], rid, line)
        self.assertIsNone(D.explain_line("[INFO] all good"))


class Roles(unittest.TestCase):
    def test_role_matrix(self):
        r = D.required_role
        self.assertEqual(r("POST", "/api/users"), "owner")
        self.assertEqual(r("POST", "/api/integrations"), "admin")   # like the Discord webhook and email
        self.assertEqual(r("POST", "/api/statuspage"), "owner")
        self.assertEqual(r("POST", "/api/password"), "owner")
        self.assertEqual(r("POST", "/api/settings"), "admin")
        self.assertEqual(r("POST", "/api/preset"), "admin")
        self.assertEqual(r("POST", "/api/config/restore"), "admin")
        self.assertEqual(r("POST", "/api/tools"), "admin")
        self.assertEqual(r("POST", "/api/players/act"), "moderator")
        self.assertEqual(r("POST", "/api/maintenance"), "moderator")
        self.assertEqual(r("POST", "/api/logout"), "viewer")
        self.assertEqual(r("GET", "/api/modpack"), "admin")
        self.assertEqual(r("GET", "/api/export"), "admin")
        self.assertEqual(r("GET", "/api/overview"), "viewer")

    def test_unknown_write_defaults_to_admin(self):
        """A new endpoint someone forgets to classify must not be open to moderators."""
        self.assertEqual(D.required_role("POST", "/api/some/new/thing"), "admin")

    def test_password_hashing(self):
        h = D.hash_password("correct horse")
        self.assertTrue(D.check_password("correct horse", h))
        self.assertFalse(D.check_password("wrong", h))
        self.assertNotIn("correct", h)


class Config(unittest.TestCase):
    def test_diff_finds_changes_and_hides_key(self):
        a = '[General]\nName = "A"\nMaxPlayers = 8\nAuthKey = "abc-SECRET-1"\n'
        b = '[General]\nName = "B"\nMaxPlayers = 8\nAuthKey = "abc-SECRET-2"\n'
        d = D.config_diff(a, b)
        self.assertEqual([c["key"] for c in d["changes"]], ["General.Name"])
        self.assertNotIn("SECRET", repr(d))

    def test_toml_set_round_trip(self):
        t = D.toml_set('[General]\nName = "x"\n', "General", "MaxPlayers", 12)
        self.assertEqual(D.toml_parse(t)[0]["General"]["MaxPlayers"], 12)


if __name__ == "__main__":
    unittest.main()
