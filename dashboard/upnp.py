"""Automatic port forwarding with UPnP (Internet Gateway Device protocol).

Most home routers let programs on the home network open a port themselves.
This asks the router to forward the BeamMP port(s) to this computer, so
friends can join without anyone opening the router's settings page.

Standard library only. Nothing here talks to the internet: SSDP is a local
multicast on the home network and the SOAP calls go to the router itself.
"""
import re
import socket
import time
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

SSDP_ADDR = ("239.255.255.250", 1900)
IGD_SERVICES = ("urn:schemas-upnp-org:service:WANIPConnection:2",
                "urn:schemas-upnp-org:service:WANIPConnection:1",
                "urn:schemas-upnp-org:service:WANPPPConnection:1")
SEARCH_TARGETS = ("urn:schemas-upnp-org:device:InternetGatewayDevice:2",
                  "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
                  "urn:schemas-upnp-org:service:WANIPConnection:1",
                  "urn:schemas-upnp-org:service:WANPPPConnection:1")
DESCRIPTION = "BeamMP EasyServer"
# The router is on the home network: never send these requests through a proxy.
_OPEN = urllib.request.build_opener(urllib.request.ProxyHandler({})).open

# Router error codes that are worth explaining (UPnP IGD spec)
ERRORS = {
    "606": "the router refused - UPnP may be in read-only mode",
    "714": "no such mapping",
    "715": "the router doesn't allow wildcard addresses",
    "716": "the router doesn't allow wildcard ports",
    "718": "this port is already forwarded to another device on your network",
    "724": "the router needs the same outside and inside port",
    "725": "the router only allows permanent forwards",
    "726": "the router needs a specific remote address",
    "727": "the router needs a specific outside port",
    "728": "the router's forwarding table is full",
    "729": "the router doesn't allow this port",
}


class UPnPError(Exception):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


def _local_ip_for(host):
    """The address of this computer on the network that leads to the router."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, 9))
        return s.getsockname()[0]
    finally:
        s.close()


def discover(timeout=3.0, addr=SSDP_ADDR):
    """Return the description URLs of the gateways that answered (best first)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    found = []
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(0.4)
        for st in SEARCH_TARGETS:
            msg = ("M-SEARCH * HTTP/1.1\r\nHOST: %s:%d\r\nMAN: \"ssdp:discover\"\r\nMX: 2\r\nST: %s\r\n\r\n"
                   % (addr[0], addr[1], st)).encode()
            try:
                sock.sendto(msg, addr)
            except OSError:
                pass
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            m = re.search(rb"(?im)^location:\s*(\S+)\s*$", data)
            if m:
                loc = m.group(1).decode("latin-1")
                if loc.startswith("http://") and loc not in found:
                    found.append(loc)
            if found and time.time() > end - timeout + 1.2:   # answers come in a burst - don't wait the full time
                break
    finally:
        sock.close()
    return found


def _tag(el):
    return el.tag.rsplit("}", 1)[-1]


def _find_service(xml_bytes, base):
    """(service type, absolute control URL, friendly name) of the WAN connection service."""
    root = ET.fromstring(xml_bytes)
    url_base = None
    name = ""
    services = []
    for el in root.iter():
        t = _tag(el)
        if t == "URLBase" and el.text:
            url_base = el.text.strip()
        elif t == "friendlyName" and el.text and not name:
            name = el.text.strip()
        elif t == "service":
            d = {_tag(c): (c.text or "").strip() for c in el}
            services.append(d)
    for want in IGD_SERVICES:
        for s in services:
            if s.get("serviceType") == want and s.get("controlURL"):
                return want, urllib.parse.urljoin(url_base or base, s["controlURL"]), name
    return None


def _soap(control_url, service, action, args, timeout=6):
    body = "".join("<%s>%s</%s>" % (k, _x(v), k) for k, v in args)
    env = ('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
           's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
           '<u:%s xmlns:u="%s">%s</u:%s></s:Body></s:Envelope>' % (action, service, body, action)).encode()
    req = urllib.request.Request(control_url, data=env, method="POST", headers={
        "Content-Type": 'text/xml; charset="utf-8"', "SOAPAction": '"%s#%s"' % (service, action),
        "User-Agent": "BeamMP-EasyServer UPnP/1.1"})
    try:
        with _OPEN(req, timeout=timeout) as r:
            data = r.read(256 * 1024)
    except urllib.error.HTTPError as e:
        data = e.read(64 * 1024)
        m = re.search(rb"<(?:\w+:)?errorCode>\s*(\d+)\s*<", data)
        code = m.group(1).decode() if m else None
        raise UPnPError(ERRORS.get(code, "the router said no (error %s)" % (code or e.code)), code)
    out = {}
    try:
        for el in ET.fromstring(data).iter():
            if not list(el) and _tag(el).startswith("New"):
                out[_tag(el)] = (el.text or "").strip()
    except ET.ParseError:
        pass
    return out


def _x(v):
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Gateway:
    def __init__(self, location, service, control_url, name):
        self.location, self.service, self.control_url, self.name = location, service, control_url, name
        self.host = urllib.parse.urlparse(control_url).hostname
        self.local_ip = _local_ip_for(self.host)

    def external_ip(self):
        return _soap(self.control_url, self.service, "GetExternalIPAddress", []).get("NewExternalIPAddress") or None

    def get(self, port, proto):
        try:
            r = _soap(self.control_url, self.service, "GetSpecificPortMappingEntry",
                      [("NewRemoteHost", ""), ("NewExternalPort", int(port)), ("NewProtocol", proto)])
        except UPnPError as e:
            if e.code in ("714", "713", "402", None) or "no such" in str(e):
                return None
            raise
        return {"client": r.get("NewInternalClient", ""), "port": int(r.get("NewInternalPort") or 0),
                "description": r.get("NewPortMappingDescription", ""), "enabled": r.get("NewEnabled", "1") != "0",
                "lease": int(r.get("NewLeaseDuration") or 0)}

    def add(self, port, proto, lease=0):
        """Forward port/proto to this computer. Returns the lease used (0 = permanent)."""
        args = lambda l: [("NewRemoteHost", ""), ("NewExternalPort", int(port)), ("NewProtocol", proto),
                          ("NewInternalPort", int(port)), ("NewInternalClient", self.local_ip), ("NewEnabled", 1),
                          ("NewPortMappingDescription", DESCRIPTION), ("NewLeaseDuration", l)]
        try:
            _soap(self.control_url, self.service, "AddPortMapping", args(lease))
            return lease
        except UPnPError as e:
            if lease == 0 and e.code not in ("718", "606", "729", "728"):
                # IGD v2 routers (and some others) refuse permanent forwards: use a day and renew it
                _soap(self.control_url, self.service, "AddPortMapping", args(86400))
                return 86400
            if lease and e.code == "725":
                _soap(self.control_url, self.service, "AddPortMapping", args(0))
                return 0
            raise

    def delete(self, port, proto):
        try:
            _soap(self.control_url, self.service, "DeletePortMapping",
                  [("NewRemoteHost", ""), ("NewExternalPort", int(port)), ("NewProtocol", proto)])
            return True
        except UPnPError as e:
            if e.code == "714":
                return False
            raise


def find_gateway(timeout=3.0, addr=SSDP_ADDR):
    """The first gateway that offers port forwarding, or None."""
    for loc in discover(timeout, addr):
        try:
            req = urllib.request.Request(loc, headers={"User-Agent": "BeamMP-EasyServer UPnP/1.1"})
            with _OPEN(req, timeout=5) as r:
                xml = r.read(512 * 1024)
            svc = _find_service(xml, loc)
        except Exception:
            continue
        if svc:
            return Gateway(loc, svc[0], svc[1], svc[2])
    return None
