"""The dashboard side of newer features: automatic port forwarding, the invite message."""
import unittest
from unittest import mock

import harness
from harness import D
import test_upnp


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class PortForwarding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()

    def setUp(self):
        self.router = test_upnp.FakeRouter()
        self.addCleanup(self.router.close)
        real = D.upnp.find_gateway
        p = mock.patch.object(D.upnp, "find_gateway", lambda timeout=3.0, addr=None: real(1.0, self.router.ssdp))
        p.start()
        self.addCleanup(p.stop)
        D.APP._upnp_gw = None
        D.APP.upnp_state = None
        self.addCleanup(lambda: D.APP.settings.update({"upnp_on": False, "upnp_mapped": []}))

    def test_open_and_close(self):
        st, d, _ = self.owner.call("/api/upnp")
        self.assertEqual(st, 200)
        self.assertFalse(d["on"])
        self.assertEqual(d["state"]["router"], "Test Router")       # looked, changed nothing
        self.assertEqual(self.router.maps, {})
        st, d, _ = self.owner.call("/api/upnp", {"on": True})
        self.assertEqual(st, 200, d)
        self.assertTrue(d["ok"], d)
        self.assertIn((30814, "TCP"), self.router.maps)
        self.assertIn((30814, "UDP"), self.router.maps)
        self.assertEqual(sorted(map(tuple, D.APP.settings.get("upnp_mapped"))), [(30814, "TCP"), (30814, "UDP")])
        st, d, _ = self.owner.call("/api/upnp", {"on": False})
        self.assertEqual(st, 200)
        self.assertEqual(self.router.maps, {})

    def test_router_restart_is_repaired(self):
        self.owner.call("/api/upnp", {"on": True})
        self.router.maps.clear()                         # router rebooted and forgot
        D.APP.upnp_state["t"] = 0
        D.APP.upnp_tick()
        self.assertIn((30814, "UDP"), self.router.maps)

    def test_port_used_by_another_device(self):
        self.router.maps[(30814, "TCP")] = {"client": "192.168.1.99", "lease": 0}
        st, d, _ = self.owner.call("/api/upnp", {"on": True})
        self.assertFalse(d["ok"])
        self.assertIn("another device", d["note"])
        self.assertEqual(self.router.maps[(30814, "TCP")]["client"], "192.168.1.99")   # left alone

    def test_only_when_needed(self):
        self.addCleanup(lambda: D.APP.settings.update({"upnp_mode": "always", "upnp_open_until": 0}))
        self.owner.call("/api/upnp", {"on": True})
        st, d, _ = self.owner.call("/api/upnp", {"mode": "needed"})
        self.assertTrue(d["ok"], d)
        self.assertIn((30814, "UDP"), self.router.maps)          # stays open for a while after switching
        st, d, _ = self.owner.call("/api/upnp", {"close_now": True})
        self.assertEqual(self.router.maps, {})
        st, d, _ = self.owner.call("/api/upnp")
        self.assertEqual(d["mode"], "needed")
        self.assertFalse(d["is_open"])
        self.owner.call("/api/upnp", {"open_for": 7200})          # an invite was copied
        self.assertIn((30814, "TCP"), self.router.maps)
        D.APP.settings.update_one("upnp_open_until", 0)          # time's up and nobody is playing
        with mock.patch.object(D.APP, "upnp_players", lambda: 0):
            D.APP.upnp_tick()
        self.assertEqual(self.router.maps, {})
        with mock.patch.object(D.APP, "upnp_players", lambda: 2):   # someone is on (e.g. joined on the LAN)
            D.APP.upnp_tick()
        self.assertIn((30814, "UDP"), self.router.maps)
        self.assertGreater(D.APP.settings.get("upnp_open_until"), D.now() + 25 * 60)

    def test_viewer_cannot_change_it(self):
        self.assertEqual(D.required_role("POST", "/api/upnp"), "admin")


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class Invite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()

    def test_invite_has_address(self):
        with mock.patch.object(D, "public_ip", lambda: "203.0.113.7"):
            st, d, _ = self.owner.call("/api/invite")
        self.assertEqual(st, 200)
        self.assertIn("Test server", d["text"])
        self.assertIn("`203.0.113.7`", d["text"])
        self.assertIn("`30814`", d["text"])
        self.assertNotIn("server list", d["text"])          # private server, no AuthKey

    def test_note_is_saved_and_cleaned(self):
        st, _, _ = self.owner.call("/api/invite", {"note": "No ramming\r\n@everyone"})
        self.assertEqual(st, 200)
        with mock.patch.object(D, "public_ip", lambda: "203.0.113.7"):
            d = self.owner.call("/api/invite")[2 - 1]
        self.assertNotIn("\r", d["note"])
        D.APP.settings.update({"invite_note": ""})


if __name__ == "__main__":
    unittest.main()


LIST_ITEM = '''<li class="resourceListItem visible " id="resource-29735">
	<div class="listBlock resourceImage"><div class="listBlockInner">
		<a href="resources/arctic-circle-swdn.29735/" class="resourceIcon"><img src="data/resource_icons/29/29735.jpg?1706694532" alt=""></a>
	</div></div>
	<div class="listBlock main"><div class="listBlockInner">
		<h3 class="title">
			<a href="resources/arctic-circle-swdn.29735/">Arctic Circle &amp; SWDN</a>
			<span class="version">1.3</span>
		</h3>
		<div class="resourceDetails muted">
			<a href="resources/authors/track-broseff.547225/">Track Broseff</a>,
			<a href="resources/arctic-circle-swdn.29735/" class="faint"><span class="DateTime" title="Feb 1, 2024 at 1:43 PM">Feb 1, 2024</span></a>, <a href="resources/categories/terrains-levels-maps.9/">Terrains, Levels, Maps</a>
		</div>
		<div class="tagLine">
				Snowy map set within the Arctic Circle. <script>alert(1)</script>
		</div>
	</div></div>
	<div class="listBlock resourceStats"><div class="listBlockInner">
	<div class="rating"><dl><dd><span class="RatingValue"><span class="Number" itemprop="average">4.60526</span>/<span itemprop="best">5</span>,</span></dd></dl></div>
			<div class="pairsJustified">
<dl class="resourceDownloads"><dt>Downloads:</dt> <dd>289,356</dd></dl>
				<dl class="resourceUpdated"><dt>Updated:</dt> <dd><a href="x" class="concealed"><abbr class="DateTime" data-time="1794580515">Yesterday</abbr></a></dd></dl>
			</div>
	</div></div>
</li>'''


class RepoParsing(unittest.TestCase):
    def test_list_page(self):
        html = "<ol class=\"resourceList\">" + LIST_ITEM + "\n" + LIST_ITEM.replace("29735", "123") + "\n</ol>"
        items = D.parse_repo_list(html)
        self.assertEqual([i["id"] for i in items], [29735, 123])
        it = items[0]
        self.assertEqual(it["title"], "Arctic Circle & SWDN")
        self.assertEqual(it["version"], "1.3")
        self.assertEqual(it["author"], "Track Broseff")
        self.assertEqual(it["category"], "Terrains, Levels, Maps")
        self.assertEqual(it["downloads"], 289356)
        self.assertEqual(it["rating"], 4.6)
        self.assertEqual(it["updated"], 1794580515)
        self.assertTrue(it["icon"])
        self.assertNotIn("<", it["tagline"])

    def test_mod_links(self):
        self.assertEqual(D.repo_id_from("https://www.beamng.com/resources/arctic-circle-swdn.29735/"), 29735)
        self.assertEqual(D.repo_id_from("beamng.com/resources/29735"), 29735)
        self.assertIsNone(D.repo_id_from("https://evil.example/resources/x.5/"))

    def test_mod_page(self):
        html = ('<h1>Arctic Circle SWDN <span class="muted">1.3</span></h1>'
                '<a href="resources/arctic-circle-swdn.29735/download?version=74999" class="inner" >'
                '<a href="resources/arctic-circle-swdn.29735/download?version=70000">')
        with mock.patch.object(D, "_repo_get", lambda url, **kw: html):
            p = D.repo_mod_page(29735)
        self.assertEqual((p["title"], p["version"], p["version_id"]), ("Arctic Circle SWDN", "1.3", 74999))


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class ModBrowserInstall(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()

    def _zip(self, rid):
        import io
        import json
        import zipfile
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("mod_info/ABC123/info.json", json.dumps({"resource_id": rid, "resource_version_id": 5, "version_string": "1.0", "title": "Test car"}))
            z.writestr("vehicles/testcar/testcar.jbeam", "{}")
        return b.getvalue()

    def _run(self, rid, data):
        import io
        import os

        class R(io.BytesIO):
            headers = {"Content-Disposition": 'attachment; filename="test_car.zip"', "Content-Length": str(len(data))}

            def geturl(self):
                return "https://www.beamng.com/x"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        page = {"id": rid, "title": "Test car", "version": "1.0", "version_id": 5, "page": "p"}
        with mock.patch.object(D, "repo_mod_page", lambda r: page), \
                mock.patch.object(D.urllib.request, "urlopen", lambda req, timeout=0: R(data)):
            st, d, _ = self.owner.call("/api/modbrowser/install", {"id": rid})
            self.assertEqual(st, 200, d)
            for _ in range(100):
                st, j, _ = self.owner.call("/api/modbrowser/job?job=" + d["job"])
                if j.get("finished"):
                    break
                import time
                time.sleep(0.05)
        self.addCleanup(lambda: [os.remove(p) for p in [os.path.join(D.I().CLIENT_DIR, "test_car.zip")] if os.path.exists(p)])
        return j

    def test_install(self):
        import os
        j = self._run(4242, self._zip(4242))
        self.assertTrue(j["ok"], j)
        self.assertTrue(os.path.exists(os.path.join(D.I().CLIENT_DIR, "test_car.zip")))

    def test_wrong_mod_refused(self):
        j = self._run(4243, self._zip(9999))
        self.assertFalse(j["ok"])
        self.assertIn("isn't the mod", j["error"])

    def test_not_a_zip(self):
        j = self._run(4244, b"<html>log in</html>")
        self.assertFalse(j["ok"])
        self.assertIn("zip", j["error"])


@unittest.skipUnless(not D.IS_WIN, "live tests run on Linux")
class Supporter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()
        cls.owner = harness.owner()

    def tearDown(self):
        D.APP.settings.update({"supporter": {}})
        harness.FAKE_SECRETS.pop("SUPPORTER_KEY", None)
        D.APP.secrets.cache.pop("SUPPORTER_KEY", None)

    def ok(self, store=77, status="active", valid=True):
        def call(action, **f):
            meta = {"store_id": store, "product_name": "EasyServer Supporter", "variant_name": "Yearly",
                    "customer_email": "player@example.com"}
            lk = {"status": status, "expires_at": None}
            if action == "activate":
                return {"activated": valid, "instance": {"id": "inst-1"}, "license_key": lk, "meta": meta}
            if action == "validate":
                return {"valid": valid, "license_key": lk, "meta": meta}
            return {"deactivated": True}
        return call

    def test_shop_closed(self):
        with mock.patch.object(D, "LS_STORE_ID", 0):
            st, d, _ = self.owner.call("/api/supporter", {"key": "ABCDEFGH-1234-5678"})
        self.assertEqual(st, 400)
        self.assertIn("free", d["error"])
        self.assertFalse(D.supporter_active())

    def test_activate_validate_remove(self):
        with mock.patch.object(D, "LS_STORE_ID", 77), mock.patch.object(D, "ls_call", self.ok()), \
                mock.patch.object(D.APP, "check_updates", lambda **k: {}):
            st, d, _ = self.owner.call("/api/supporter", {"key": "ABCDEFGH-1234-5678"})
            self.assertEqual(st, 200, d)
            self.assertTrue(D.supporter_active())
            info = self.owner.call("/api/supporter")[1]
            self.assertEqual(info["plan"], "EasyServer Supporter - Yearly")
            self.assertEqual(info["email"], "pl***@example.com")            # never the full address
            self.assertNotIn("ABCDEFGH", str(info))                          # the key is never sent back
            st, d, _ = self.owner.call("/api/supporter", {"action": "remove"})
            self.assertEqual(st, 200)
            self.assertFalse(D.supporter_active())

    def test_key_from_another_store_refused(self):
        with mock.patch.object(D, "LS_STORE_ID", 77), mock.patch.object(D, "ls_call", self.ok(store=12345)):
            st, d, _ = self.owner.call("/api/supporter", {"key": "ABCDEFGH-1234-5678"})
        self.assertEqual(st, 400)
        self.assertFalse(D.supporter_active())

    def test_refund_turns_it_off(self):
        with mock.patch.object(D, "LS_STORE_ID", 77), mock.patch.object(D, "ls_call", self.ok()), \
                mock.patch.object(D.APP, "check_updates", lambda **k: {}):
            self.owner.call("/api/supporter", {"key": "ABCDEFGH-1234-5678"})
        sup = dict(D.APP.settings.get("supporter"), checked=0)
        D.APP.settings.update({"supporter": sup})
        with mock.patch.object(D, "LS_STORE_ID", 77), mock.patch.object(D, "ls_call", self.ok(status="disabled", valid=False)):
            D.APP.supporter_tick()
        self.assertFalse(D.supporter_active())

    def test_owner_only(self):
        self.assertEqual(D.required_role("POST", "/api/supporter"), "owner")
