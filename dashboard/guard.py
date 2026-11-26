"""BeamMP-only guard: block addresses that keep knocking on the game port but never play.

Port scanners and bots connect to any open port they find, get nothing useful
back and hang up within a second. Real BeamMP players stay connected (while they
download mods and while they drive). The guard watches the computer's own
connection table - no admin rights needed to read it - and counts "knocks":
connections to the game port that are gone again within a few seconds. An
address that knocks too often without ever staying is blocked for a while.

Blocking itself is done by the firewall: on Linux by the root helper
(nftables), on Windows by a small task the installer sets up (Windows Firewall).
"""
import ipaddress
import os
import socket
import struct
import sys
import time

IS_WIN = sys.platform == "win32"

STAY = 20            # connected this long = a real player, never blocked
WINDOW = 10 * 60     # knocks are counted over this long
STRIKES = 8          # this many short knocks in WINDOW gets an address blocked
BLOCK_STEPS = (3600, 6 * 3600, 24 * 3600)
GOOD_FOR = 30 * 86400
HISTORY_FOR = 30 * 86400   # a blocked address is forgotten this long after its block ends
MAX_BLOCKED = 2000

TCP_STATES = {"01": "ESTABLISHED", "02": "SYN_SENT", "03": "SYN_RECV", "04": "FIN_WAIT1", "05": "FIN_WAIT2",
              "06": "TIME_WAIT", "07": "CLOSE", "08": "CLOSE_WAIT", "09": "LAST_ACK", "0A": "LISTEN", "0B": "CLOSING"}
WIN_STATES = {1: "CLOSED", 2: "LISTEN", 3: "SYN_SENT", 4: "SYN_RECV", 5: "ESTABLISHED", 6: "FIN_WAIT1",
              7: "FIN_WAIT2", 8: "CLOSE_WAIT", 9: "CLOSING", 10: "LAST_ACK", 11: "TIME_WAIT", 12: "DELETE_TCB"}


def norm_ip(ip):
    """Plain address text; IPv4 written as IPv6 (::ffff:1.2.3.4) becomes 1.2.3.4."""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    return str(a)


def is_local(ip):
    """Your own network, this computer, VPN-style ranges: never blocked."""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return a.is_private or a.is_loopback or a.is_link_local or a.is_unspecified or a.is_multicast or \
        a in ipaddress.ip_network("100.64.0.0/10")


# ----------------------------------------------------------------------------- reading the connection table
def _proc_addr(h):
    ip, port = h.split(":")
    raw = bytes.fromhex(ip)
    if len(raw) == 4:
        addr = socket.inet_ntop(socket.AF_INET, raw[::-1])
    else:
        addr = socket.inet_ntop(socket.AF_INET6, b"".join(raw[i:i + 4][::-1] for i in range(0, 16, 4)))
    return addr, int(port, 16)


def parse_proc(text, ports):
    """Lines of /proc/net/tcp(6) -> [(remote ip, remote port, state)] for connections to our ports."""
    out = []
    for line in text.splitlines()[1:]:
        f = line.split()
        if len(f) < 4:
            continue
        try:
            (_, lport), (rip, rport) = _proc_addr(f[1]), _proc_addr(f[2])
        except (ValueError, OSError):
            continue
        st = TCP_STATES.get(f[3].upper(), "")
        if lport in ports and st not in ("LISTEN", ""):
            out.append((norm_ip(rip), rport, st))
    return out


def _win_table(ports):
    import ctypes
    from ctypes import wintypes
    out = []
    iphlp = ctypes.WinDLL("iphlpapi.dll")
    for fam in (socket.AF_INET, socket.AF_INET6):
        size = wintypes.DWORD(0)
        iphlp.GetExtendedTcpTable(None, ctypes.byref(size), False, fam, 4, 0)    # 4 = TCP_TABLE_OWNER_PID_CONNECTIONS
        buf = ctypes.create_string_buffer(size.value + 4096)
        size = wintypes.DWORD(len(buf))
        if iphlp.GetExtendedTcpTable(buf, ctypes.byref(size), False, fam, 4, 0) != 0:
            continue
        raw = buf.raw
        n = struct.unpack_from("<I", raw, 0)[0]
        if fam == socket.AF_INET:          # state, laddr, lport, raddr, rport, pid  (6 x DWORD)
            for i in range(n):
                st, la, lp, ra, rp, _ = struct.unpack_from("<IIIIII", raw, 4 + i * 24)
                lport = socket.ntohs(lp & 0xFFFF)
                if lport in ports:
                    out.append((socket.inet_ntoa(struct.pack("<I", ra)), socket.ntohs(rp & 0xFFFF), WIN_STATES.get(st, "")))
        else:                              # laddr[16], lscope, lport, raddr[16], rscope, rport, state, pid
            for i in range(n):
                off = 4 + i * 56
                lport = socket.ntohs(struct.unpack_from("<I", raw, off + 20)[0] & 0xFFFF)
                if lport not in ports:
                    continue
                ra = socket.inet_ntop(socket.AF_INET6, raw[off + 24:off + 40])
                rp = socket.ntohs(struct.unpack_from("<I", raw, off + 44)[0] & 0xFFFF)
                st = struct.unpack_from("<I", raw, off + 48)[0]
                out.append((norm_ip(ra), rp, WIN_STATES.get(st, "")))
    return [c for c in out if c[2] not in ("LISTEN", "CLOSED", "")]


def connections(ports):
    """[(remote ip, remote port, state)] for TCP connections to any of ports, on this computer."""
    ports = set(ports)
    if IS_WIN:
        return _win_table(ports)
    out = []
    for p in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(p, encoding="ascii") as f:
                out += parse_proc(f.read(), ports)
        except OSError:
            pass
    return out


# ----------------------------------------------------------------------------- the decision
class Guard:
    """Feed it the connection table every second or two with see(); it says who to block."""

    def __init__(self, state=None):
        st = state or {}
        self.blocked = {k: dict(v) for k, v in (st.get("blocked") or {}).items()}   # ip -> {until, times, why}
        self.good = dict(st.get("good") or {})                                        # ip -> last seen playing
        self.open = {}         # (ip, port) -> first seen
        self.knocks = {}       # ip -> [times]
        # ip -> [times blocked before, when the last block ended]. Older saves kept only the count:
        # those start their 30 days now.
        now = time.time()
        self.history = {k: (list(v)[:2] if isinstance(v, (list, tuple)) else [int(v or 0), now])
                        for k, v in (st.get("history") or {}).items()}
        self.total = int(st.get("total") or 0)

    def state(self):
        return {"blocked": self.blocked, "good": self.good, "history": self.history, "total": self.total}

    def see(self, conns, t=None):
        """conns: [(ip, port, state)]. Returns the addresses that got newly blocked."""
        t = t or time.time()
        now_open = {}
        for ip, port, _st in conns:
            if ip and not is_local(ip):
                now_open[(ip, port)] = self.open.get((ip, port), t)
        new = []
        for key, since in now_open.items():
            if t - since >= STAY:
                self.good[key[0]] = t
        for (ip, port), since in self.open.items():
            if (ip, port) in now_open:
                continue
            # this connection is gone again
            if t - since < STAY and (ip not in self.good or t - self.good[ip] > GOOD_FOR):
                k = [x for x in self.knocks.get(ip, []) if t - x < WINDOW] + [t]
                self.knocks[ip] = k
                if len(k) >= STRIKES and ip not in self.blocked:
                    times = self._times(ip) + 1
                    self.blocked[ip] = {"until": t + BLOCK_STEPS[min(times, len(BLOCK_STEPS)) - 1], "times": times,
                                        "at": t, "why": "%d connections in %d minutes, never stayed to play" % (len(k), WINDOW // 60)}
                    self.knocks.pop(ip, None)
                    self.total += 1
                    new.append(ip)
        self.open = now_open
        self.expire(t)
        return new

    def _times(self, ip):
        h = self.history.get(ip)
        return int(h[0]) if h else 0

    def expire(self, t=None):
        t = t or time.time()
        for ip, b in list(self.blocked.items()):
            if b["until"] <= t:
                self.history[ip] = [int(b.get("times") or 1), b["until"]]
                del self.blocked[ip]
        for ip in [ip for ip, x in self.knocks.items() if not x or t - x[-1] > WINDOW]:
            del self.knocks[ip]
        for ip in [ip for ip, x in self.good.items() if t - x > GOOD_FOR]:
            del self.good[ip]
        for ip in [ip for ip, h in self.history.items() if t - h[1] > HISTORY_FOR]:
            del self.history[ip]
        if len(self.history) > 5000:
            self.history = dict(list(self.history.items())[-5000:])
        if len(self.blocked) > MAX_BLOCKED:      # keep the newest
            for ip in sorted(self.blocked, key=lambda i: self.blocked[i]["at"])[:len(self.blocked) - MAX_BLOCKED]:
                del self.blocked[ip]

    def unblock(self, ip):
        ip = norm_ip(ip) or ip
        gone = self.blocked.pop(ip, None) is not None
        self.knocks.pop(ip, None)
        self.good[ip] = time.time()            # you vouched for it
        return gone

    def block_list(self):
        return sorted(self.blocked)


def write_block_file(path, ports, ips):
    """For the Windows firewall task: first line the ports, then one address per line."""
    text = "ports=%s\n%s" % (",".join(str(int(p)) for p in sorted(set(ports))), "".join(ip + "\n" for ip in ips))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="ascii") as f:
        f.write(text)
    os.replace(tmp, path)
