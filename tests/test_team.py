"""Team access: custom roles, per-server access, invite links, two-step login and internet logins for extra accounts."""
import os
import re
import shutil
import unittest
from unittest import mock

import harness
from harness import D, Client


def code_for(secret):
    return D.totp_code(re.sub(r"\s", "", secret), D.now() // 30)


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class Team(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()
        d = os.path.join(D.SERVERS_DIR, "s2")
        for sub in ("Resources/Client", "Resources/Client-disabled", "Resources/Quarantine", "Resources/Server/EasyServerStats"):
            os.makedirs(os.path.join(d, sub), exist_ok=True)
        with open(os.path.join(d, "ServerConfig.toml"), "w") as f:
            f.write('[General]\nName = "Second"\nPort = 30816\nMap = "/levels/gridmap_v2/info.json"\n')
        with D.LOCK:
            D.INSTANCES["s2"] = D.Instance("s2", {"name": "Second"})

    @classmethod
    def tearDownClass(cls):
        with D.LOCK:
            D.INSTANCES.pop("s2", None)
        shutil.rmtree(os.path.join(D.SERVERS_DIR, "s2"), ignore_errors=True)

    def add(self, name, role="moderator", **extra):
        self.owner.call("/api/users", {"action": "delete", "name": name})
        st, d, _ = self.owner.call("/api/users", dict({"action": "add", "name": name, "role": role, "password": name + "-password-1"}, **extra))
        self.assertEqual(st, 200, d)
        c = Client(self.base)
        self.assertEqual(c.login(name + "-password-1", name), 200)
        return c

    def test_custom_role_tick_boxes(self):
        st, r, _ = self.owner.call("/api/roles", {"action": "save", "name": "Map master", "perms": ["map", "mods"]})
        self.assertEqual(st, 200, r)
        rid = r["id"]
        c = self.add("mapper", rid)
        self.assertNotEqual(c.call("/api/rotation", {"on": False})[0], 403)          # map: allowed
        self.assertEqual(c.call("/api/maintenance", {"state": "off"})[0], 403)       # start & stop: not ticked
        self.assertEqual(c.call("/api/bans/add", {"name": "x", "minutes": 5})[0], 403)
        self.assertEqual(c.call("/api/settings", {"update_check": True})[0], 403)
        self.assertEqual(c.call("/api/plugins/fetch", {"id": "x"})[0], 403)          # owner only, never grantable
        self.assertEqual(c.call("/api/overview")[0], 200)                            # everyone can look
        self.assertIn("map", c.call("/api/session")[1]["server_roles"]["main"]["perms"])
        self.assertEqual(self.owner.call("/api/roles", {"action": "delete", "id": rid})[0], 400)   # still in use
        self.owner.call("/api/roles", {"action": "save", "id": rid, "name": "Map master", "perms": ["map", "server"]})
        self.assertNotEqual(c.call("/api/maintenance", {"state": "off"})[0], 403)    # takes effect at once
        self.owner.call("/api/users", {"action": "delete", "name": "mapper"})
        self.assertEqual(self.owner.call("/api/roles", {"action": "delete", "id": rid})[0], 200)

    def test_only_some_servers(self):
        c = self.add("s2mod", "viewer", servers={"s2": "admin"})
        ids = [s["id"] for s in c.call("/api/servers")[1]["servers"]]
        self.assertEqual(ids, ["s2"])
        self.assertEqual(c.call("/api/overview", headers={"X-ES-Server": "main"})[0], 403)
        self.assertNotEqual(c.call("/api/tools", {"tp": False}, headers={"X-ES-Server": "s2"})[0], 403)   # admin on s2
        self.assertEqual(c.call("/api/settings", {"update_check": True}, headers={"X-ES-Server": "s2"})[0], 403)  # global
        self.owner.call("/api/users", {"action": "servers", "name": "s2mod", "servers": "all"})
        self.assertEqual(c.call("/api/overview", headers={"X-ES-Server": "main"})[0], 200)
        self.assertEqual(self.owner.call("/api/users", {"action": "servers", "name": "s2mod", "servers": {"nope": "admin"}})[0], 400)

    def test_own_two_step_and_internet_login(self):
        c = self.add("remotey", "viewer")
        with mock.patch.object(D, "ip_is_remote", lambda ip: True):
            self.assertEqual(Client(self.base).login("remotey-password-1", "remotey"), 403)       # not allowed yet
        self.owner.call("/api/users", {"action": "remote", "name": "remotey", "remote": True})
        with mock.patch.object(D, "ip_is_remote", lambda ip: True):
            self.assertEqual(Client(self.base).login("remotey-password-1", "remotey"), 403)       # no two-step yet
        st, r, _ = c.call("/api/me/2fa/begin", {})
        self.assertEqual(st, 200, r)
        self.assertEqual(c.call("/api/me/2fa/confirm", {"code": "000000"})[0], 400)
        self.assertEqual(c.call("/api/me/2fa/confirm", {"code": code_for(r["secret"])})[0], 200)
        self.assertNotIn(re.sub(r"\s", "", r["secret"]), open(D.USERS_FILE).read())           # stored encrypted
        x = Client(self.base)
        self.assertEqual(x.login("remotey-password-1", "remotey"), 401)                        # code needed now
        with mock.patch.object(D, "_USER_TOTP_LAST", {}), mock.patch.object(D, "ip_is_remote", lambda ip: True):
            x.refresh()
            st, d, _ = x.call("/api/login", {"user": "remotey", "password": "remotey-password-1", "code": code_for(r["secret"])})
            self.assertEqual(st, 200, d)
            x.refresh()
            self.assertEqual(x.call("/api/overview")[0], 200)
            self.owner.call("/api/users", {"action": "remote", "name": "remotey", "remote": False})
            self.assertEqual(x.call("/api/overview")[0], 401)                                  # thrown out at once
        self.owner.call("/api/users", {"action": "delete", "name": "remotey"})

    def test_invite_link(self):
        st, r, _ = self.owner.call("/api/teaminvite", {"role": "moderator", "servers": {"main": "moderator"}})
        self.assertEqual(st, 200, r)
        self.assertLessEqual(r["expires"] - D.now(), 3600)                 # an hour, not days
        tok = r["link"].split("#team=")[1]
        guest = Client(self.base)
        st, info, _ = guest.call("/api/teaminvite/info?t=" + tok)
        self.assertEqual(st, 200, info)
        self.assertEqual(info["role"], "moderator")
        self.assertNotIn("totp", info)
        st, d, _ = guest.call("/api/teaminvite/accept", {"t": tok, "name": "invited1", "password": "invited1-password"})
        self.assertEqual(st, 200, d)
        u = D.find_user("invited1")
        self.assertEqual(u["servers"], {"main": "moderator"})
        self.assertEqual(guest.call("/api/teaminvite/accept", {"t": tok, "name": "invited2", "password": "invited2-password"})[0], 404)
        self.assertEqual(Client(self.base).login("invited1-password", "invited1"), 200)
        self.assertEqual(guest.call("/api/teaminvite/info?t=" + "x" * 43)[0], 404)
        # an internet invite sets up two-step login on the way in
        st, r, _ = self.owner.call("/api/teaminvite", {"role": "viewer", "remote": True})
        tok = r["link"].split("#team=")[1]
        info = guest.call("/api/teaminvite/info?t=" + tok)[1]
        self.assertIn("secret", info["totp"])
        self.assertEqual(guest.call("/api/teaminvite/accept", {"t": tok, "name": "invited3", "password": "invited3-password", "code": "123456"})[0], 400)
        st, d, _ = guest.call("/api/teaminvite/accept", {"t": tok, "name": "invited3", "password": "invited3-password",
                                                         "code": code_for(info["totp"]["secret"])})
        self.assertEqual(st, 200, d)
        u = D.find_user("invited3")
        self.assertTrue(u["remote"] and u["totp"])
        # a home-only invite doesn't work from the internet
        st, r, _ = self.owner.call("/api/teaminvite", {"role": "viewer"})
        tok = r["link"].split("#team=")[1]
        with mock.patch.object(D, "ip_is_remote", lambda ip: True):
            self.assertEqual(guest.call("/api/teaminvite/info?t=" + tok)[0], 403)
        with mock.patch.object(D, "now", lambda: D.time.time().__int__() + 3601):          # an hour later
            self.assertEqual(guest.call("/api/teaminvite/info?t=" + tok)[0], 404)
        self.owner.call("/api/teaminvite", {"action": "revoke", "id": self.owner.call("/api/users")[1]["invites"][0]["id"]})
        for n in ("invited1", "invited3"):
            self.owner.call("/api/users", {"action": "delete", "name": n})

    def test_only_owner_manages_the_team(self):
        c = self.add("teamadmin", "admin")
        for path, body in (("/api/users", {"action": "add", "name": "zz", "role": "admin", "password": "x" * 12}),
                           ("/api/roles", {"action": "save", "name": "x", "perms": PERMS}),
                           ("/api/teaminvite", {"role": "admin"})):
            self.assertEqual(c.call(path, body)[0], 403, path)
        self.owner.call("/api/users", {"action": "delete", "name": "teamadmin"})

    def test_sealed_secret(self):
        s = D._seal("JBSWY3DPEHPK3PXP")
        self.assertEqual(D._unseal(s), "JBSWY3DPEHPK3PXP")
        bad = s[:-1] + ("0" if s[-1] != "0" else "1")
        self.assertEqual(D._unseal(bad), "")


PERMS = ["players", "server", "map", "mods", "config", "settings"]

if __name__ == "__main__":
    unittest.main()
