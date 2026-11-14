"""Automatic port forwarding: a fake UPnP router answers discovery and SOAP calls on localhost."""
import os
import re
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dashboard"))
import upnp  # noqa: E402

SVC = "urn:schemas-upnp-org:service:WANIPConnection:1"


class FakeRouter:
    def __init__(self, permanent_ok=True, other_client=None):
        self.maps = {}
        self.calls = []
        self.permanent_ok = permanent_ok
        if other_client:
            self.maps[(30814, "TCP")] = {"client": other_client, "lease": 0}
        router = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                body = ('<?xml version="1.0"?><root xmlns="urn:schemas-upnp-org:device-1-0"><device>'
                        '<friendlyName>Test Router</friendlyName><deviceList><device><deviceList><device>'
                        '<serviceList><service><serviceType>%s</serviceType><controlURL>/ctl/IPConn</controlURL>'
                        '</service></serviceList></device></deviceList></device></deviceList></device></root>' % SVC).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/xml")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                data = self.rfile.read(int(self.headers["Content-Length"])).decode()
                action = self.headers["SOAPAction"].strip('"').split("#")[1]
                val = lambda k: (re.search(r"<%s>(.*?)</%s>" % (k, k), data) or [None, ""])[1]
                router.calls.append(action)
                key = (int(val("NewExternalPort") or 0), val("NewProtocol"))
                out, err = "", None
                if action == "GetExternalIPAddress":
                    out = "<NewExternalIPAddress>203.0.113.7</NewExternalIPAddress>"
                elif action == "GetSpecificPortMappingEntry":
                    m = router.maps.get(key)
                    if not m:
                        err = 714
                    else:
                        out = ("<NewInternalPort>%d</NewInternalPort><NewInternalClient>%s</NewInternalClient>"
                               "<NewEnabled>1</NewEnabled><NewPortMappingDescription>x</NewPortMappingDescription>"
                               "<NewLeaseDuration>%d</NewLeaseDuration>" % (key[0], m["client"], m["lease"]))
                elif action == "AddPortMapping":
                    lease = int(val("NewLeaseDuration"))
                    if key in router.maps and router.maps[key]["client"] != val("NewInternalClient"):
                        err = 718
                    elif lease == 0 and not router.permanent_ok:
                        err = 402
                    else:
                        router.maps[key] = {"client": val("NewInternalClient"), "lease": lease}
                elif action == "DeletePortMapping":
                    if router.maps.pop(key, None) is None:
                        err = 714
                if err:
                    body = ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><s:Fault><detail>'
                            '<UPnPError xmlns="urn:schemas-upnp-org:control-1-0"><errorCode>%d</errorCode></UPnPError>'
                            '</detail></s:Fault></s:Body></s:Envelope>' % err).encode()
                    self.send_response(500)
                else:
                    body = ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
                            '<u:%sResponse xmlns:u="%s">%s</u:%sResponse></s:Body></s:Envelope>' % (action, SVC, out, action)).encode()
                    self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind(("127.0.0.1", 0))
        self.ssdp = self.udp.getsockname()
        threading.Thread(target=self._ssdp, daemon=True).start()

    def _ssdp(self):
        while True:
            try:
                data, addr = self.udp.recvfrom(2048)
            except OSError:
                return
            if b"M-SEARCH" in data:
                self.udp.sendto(("HTTP/1.1 200 OK\r\nST: x\r\nLOCATION: http://127.0.0.1:%d/desc.xml\r\n\r\n"
                                 % self.http.server_address[1]).encode(), addr)

    def close(self):
        self.http.shutdown()
        self.udp.close()


class UPnP(unittest.TestCase):
    def router(self, **kw):
        r = FakeRouter(**kw)
        self.addCleanup(r.close)
        return r

    def test_discover_and_forward(self):
        r = self.router()
        gw = upnp.find_gateway(timeout=1.5, addr=r.ssdp)
        self.assertIsNotNone(gw)
        self.assertEqual(gw.name, "Test Router")
        self.assertEqual(gw.external_ip(), "203.0.113.7")
        self.assertEqual(gw.add(30814, "TCP"), 0)
        self.assertEqual(gw.add(30814, "UDP"), 0)
        self.assertEqual(r.maps[(30814, "TCP")]["client"], gw.local_ip)
        self.assertEqual(gw.get(30814, "UDP")["port"], 30814)
        self.assertIsNone(gw.get(30815, "TCP"))
        self.assertTrue(gw.delete(30814, "TCP"))
        self.assertFalse(gw.delete(30814, "TCP"))

    def test_router_without_permanent_forwards_gets_a_lease(self):
        r = self.router(permanent_ok=False)
        gw = upnp.find_gateway(timeout=1.5, addr=r.ssdp)
        self.assertEqual(gw.add(30814, "UDP"), 86400)
        self.assertEqual(r.maps[(30814, "UDP")]["lease"], 86400)

    def test_port_taken_by_another_device_is_explained(self):
        r = self.router(other_client="192.168.1.99")
        gw = upnp.find_gateway(timeout=1.5, addr=r.ssdp)
        with self.assertRaises(upnp.UPnPError) as c:
            gw.add(30814, "TCP")
        self.assertIn("another device", str(c.exception))
        self.assertEqual(gw.get(30814, "TCP")["client"], "192.168.1.99")

    def test_no_router(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", 0))
        self.addCleanup(s.close)
        self.assertIsNone(upnp.find_gateway(timeout=0.8, addr=s.getsockname()))

    def test_bad_description_is_ignored(self):
        self.assertIsNone(upnp._find_service(b"<root><device><serviceList></serviceList></device></root>", "http://x/"))


if __name__ == "__main__":
    unittest.main()
