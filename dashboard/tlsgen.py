#!/usr/bin/env python3
"""BeamMP EasyServer - self-signed HTTPS certificate generator.

Pure Python (standard library only) so it works the same on Windows and Linux
without OpenSSL tools. Creates an RSA-2048 key and a SHA-256 signed X.509
certificate valid for 10 years.

    python3 tlsgen.py OUT_DIR [extra-hostname-or-ip ...]

Writes OUT_DIR/cert.pem and OUT_DIR/key.pem (key readable by owner only).
You can replace both files with a "real" certificate (e.g. Let's Encrypt)
at any time - the dashboard just loads whatever is there.
"""
import base64
import datetime
import hashlib
import ipaddress
import os
import secrets
import socket
import sys

# --------------------------------------------------------------------- RSA
_SMALL_PRIMES = [p for p in range(3, 2000) if all(p % d for d in range(2, int(p ** 0.5) + 1))]


def _is_probable_prime(n, rounds=40):
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _random_prime(bits):
    while True:
        c = secrets.randbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if _is_probable_prime(c):
            return c


def generate_rsa(bits=2048, e=65537):
    while True:
        p, q = _random_prime(bits // 2), _random_prime(bits // 2)
        if p == q:
            continue
        phi = (p - 1) * (q - 1)
        if phi % e == 0:
            continue
        n = p * q
        if n.bit_length() != bits:
            continue
        d = pow(e, -1, phi)
        return {"n": n, "e": e, "d": d, "p": p, "q": q,
                "dp": d % (p - 1), "dq": d % (q - 1), "qi": pow(q, -1, p)}


# --------------------------------------------------------------------- DER
def _len(n):
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _tlv(tag, content):
    return bytes([tag]) + _len(len(content)) + content


def _int(v):
    b = v.to_bytes(max(1, (v.bit_length() + 8) // 8), "big", signed=False)
    if b[0] & 0x80:
        b = b"\x00" + b
    # strip superfluous leading zero bytes
    while len(b) > 1 and b[0] == 0 and not (b[1] & 0x80):
        b = b[1:]
    return _tlv(0x02, b)


def _seq(*items):
    return _tlv(0x30, b"".join(items))


def _set(*items):
    return _tlv(0x31, b"".join(items))


def _oid(dotted):
    parts = [int(x) for x in dotted.split(".")]
    out = bytes([parts[0] * 40 + parts[1]])
    for p in parts[2:]:
        chunk = [p & 0x7F]
        p >>= 7
        while p:
            chunk.insert(0, 0x80 | (p & 0x7F))
            p >>= 7
        out += bytes(chunk)
    return _tlv(0x06, out)


def _null():
    return b"\x05\x00"


def _bitstring(b):
    return _tlv(0x03, b"\x00" + b)


def _octet(b):
    return _tlv(0x04, b)


def _utf8(s):
    return _tlv(0x0C, s.encode("utf-8"))


def _time(dt):
    if dt.year < 2050:
        return _tlv(0x17, dt.strftime("%y%m%d%H%M%SZ").encode())
    return _tlv(0x18, dt.strftime("%Y%m%d%H%M%SZ").encode())


def _ctx(n, content, constructed=True):
    return _tlv((0xA0 if constructed else 0x80) | n, content)


OID_SHA256_RSA = "1.2.840.113549.1.1.11"
OID_RSA = "1.2.840.113549.1.1.1"
OID_CN = "2.5.4.3"
OID_O = "2.5.4.10"
OID_SAN = "2.5.29.17"
OID_BASIC = "2.5.29.19"
OID_EKU = "2.5.29.37"
OID_SERVER_AUTH = "1.3.6.1.5.5.7.3.1"
OID_SHA256 = "2.16.840.1.101.3.4.2.1"


def _name(cn):
    return _seq(_set(_seq(_oid(OID_O), _utf8("BeamMP EasyServer"))),
                _set(_seq(_oid(OID_CN), _utf8(cn))))


def _sign(key, data):
    digest_info = _seq(_seq(_oid(OID_SHA256), _null()), _octet(hashlib.sha256(data).digest()))
    k = (key["n"].bit_length() + 7) // 8
    em = b"\x00\x01" + b"\xff" * (k - len(digest_info) - 3) + b"\x00" + digest_info
    m = int.from_bytes(em, "big")
    # CRT for speed
    s1 = pow(m, key["dp"], key["p"])
    s2 = pow(m, key["dq"], key["q"])
    h = (key["qi"] * (s1 - s2)) % key["p"]
    s = s2 + h * key["q"]
    return s.to_bytes(k, "big")


def make_certificate(key, hostnames, ips, days=3650):
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    not_before = now - datetime.timedelta(days=1)
    not_after = now + datetime.timedelta(days=days)
    alg = _seq(_oid(OID_SHA256_RSA), _null())
    spki = _seq(_seq(_oid(OID_RSA), _null()), _bitstring(_seq(_int(key["n"]), _int(key["e"]))))
    san_items = b"".join(_tlv(0x82, h.encode()) for h in hostnames) + \
        b"".join(_tlv(0x87, ipaddress.ip_address(i).packed) for i in ips)
    extensions = _ctx(3, _seq(
        _seq(_oid(OID_BASIC), _octet(_seq())),                                  # CA:FALSE
        _seq(_oid(OID_EKU), _octet(_seq(_oid(OID_SERVER_AUTH)))),
        _seq(_oid(OID_SAN), _octet(_seq(san_items))),
    ))
    cn = hostnames[0] if hostnames else "BeamMP EasyServer"
    tbs = _seq(
        _ctx(0, _int(2)),                                    # v3
        _int(secrets.randbits(120) | 1),                     # serial
        alg,
        _name(cn),
        _seq(_time(not_before), _time(not_after)),
        _name(cn),
        spki,
        extensions,
    )
    cert = _seq(tbs, alg, _bitstring(_sign(key, tbs)))
    return cert


def key_to_der(key):
    return _seq(_int(0), _int(key["n"]), _int(key["e"]), _int(key["d"]), _int(key["p"]),
                _int(key["q"]), _int(key["dp"]), _int(key["dq"]), _int(key["qi"]))


def _pem(label, der):
    b = base64.b64encode(der).decode()
    lines = "\n".join(b[i:i + 64] for i in range(0, len(b), 64))
    return "-----BEGIN %s-----\n%s\n-----END %s-----\n" % (label, lines, label)


def local_ips():
    ips = {"127.0.0.1"}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(ips)


def fingerprint(cert_pem_path):
    with open(cert_pem_path, encoding="ascii") as f:
        body = "".join(l for l in f if not l.startswith("-----"))
    h = hashlib.sha256(base64.b64decode(body)).hexdigest().upper()
    return ":".join(h[i:i + 2] for i in range(0, len(h), 2))


def generate(out_dir, extra=()):
    os.makedirs(out_dir, exist_ok=True)
    hosts = ["localhost", socket.gethostname()]
    ips = local_ips()
    for x in extra:
        try:
            ipaddress.ip_address(x)
            ips.append(x)
        except ValueError:
            if x:
                hosts.append(x)
    hosts = list(dict.fromkeys(h for h in hosts if h))
    ips = list(dict.fromkeys(ips))
    key = generate_rsa()
    cert = make_certificate(key, hosts, ips)
    key_path = os.path.join(out_dir, "key.pem")
    cert_path = os.path.join(out_dir, "cert.pem")
    fd = os.open(key_path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(_pem("RSA PRIVATE KEY", key_to_der(key)))
    os.replace(key_path + ".tmp", key_path)
    with open(cert_path + ".tmp", "w", encoding="ascii") as f:
        f.write(_pem("CERTIFICATE", cert))
    os.replace(cert_path + ".tmp", cert_path)
    return cert_path, key_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    c, k = generate(sys.argv[1], sys.argv[2:])
    print("Certificate:", c)
    print("Key:        ", k)
    print("SHA-256 fingerprint:", fingerprint(c))
