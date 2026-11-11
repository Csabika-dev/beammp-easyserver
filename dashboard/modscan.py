#!/usr/bin/env python3
"""BeamMP EasyServer - mod safety scanner.

Checks a mod .zip before it is given to players:
  1. Built-in checks (always on, offline): hidden programs (.exe/.dll/...,
     or files whose content is a Windows/Linux program), path tricks,
     password-protected files, zip bombs, suspicious Lua code.
  2. ClamAV antivirus, if it is installed (clamscan/clamdscan).
  3. VirusTotal (70+ antivirus engines), if an API key is set in the
     VT_API_KEY environment variable. The key is stored encrypted by the
     installer and only ever handed to this script in memory.

Verdicts:  clean | warning (allowed, but shown) | blocked (refused/quarantined)

Usage:
  modscan.py FILE.zip [...]        scan files, print results (exit 2 if any blocked)
  modscan.py --json FILE.zip       same, JSON output
  modscan.py --sweep DIR QUAR      scan every new zip in DIR, move blocked ones to QUAR
Not affiliated with the BeamMP team.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.environ.get("MODSCAN_CACHE") or os.path.join(
    os.environ.get("BEAMMP_DIR", "/opt/beammp-server"),
    os.path.join("EasyServer", "data") if os.name == "nt" else ".easyserver", "scancache.json")
SCANNER_VERSION = 1  # bump to force rescans when the rules change

# File types that have no business in a BeamNG mod and can run on a PC
BLOCKED_EXT = {
    "exe", "dll", "scr", "com", "pif", "cpl", "sys", "drv", "ocx", "msi", "msp", "mst",
    "bat", "cmd", "ps1", "psm1", "psd1", "vbs", "vbe", "jse", "wsf", "wsh", "wsc", "hta",
    "lnk", "url", "reg", "inf", "jar", "appx", "msix", "application", "gadget", "chm",
    "sh", "bash", "elf", "so", "dylib", "app", "apk", "deb", "rpm", "run", "bin",
    "iso", "img", "vhd", "vhdx", "docm", "xlsm", "pptm",
}
# Archives inside the mod can't be checked from here
NESTED_ARCHIVE_EXT = {"zip", "rar", "7z", "tar", "gz", "bz2", "xz", "cab", "zst"}
# Content signatures of programs, whatever the file is called
MAGIC = [(b"MZ", "a Windows program"), (b"\x7fELF", "a Linux program"),
         (b"\xcf\xfa\xed\xfe", "a macOS program"), (b"\xca\xfe\xba\xbe", "a macOS/Java program")]
# Files that legitimately start with those bytes are rare in mods; these
# extensions are never treated as programs to avoid false alarms.
MAGIC_SAFE_EXT = {"txt", "json", "jbeam", "lua", "md", "cs", "ini", "csv", "html", "css", "js"}

LUA_PATTERNS = [
    (r"\bos\.execute\s*\(", "runs system commands (os.execute)"),
    (r"\bio\.popen\s*\(", "runs system commands (io.popen)"),
    (r"\bffi\.load\s*\(", "loads native code (ffi.load)"),
    (r"\bpackage\.loadlib\s*\(", "loads native code (package.loadlib)"),
    (r"require\s*\(?\s*[\"']socket", "opens network connections (socket)"),
    (r"\b(loadstring|load)\s*\(\s*[\"'][A-Za-z0-9+/=\\]{400,}", "runs hidden encoded code"),
    (r"(\\x[0-9a-fA-F]{2}){80,}|(\\\d{2,3}){120,}", "contains a large block of encoded bytes"),
    (r"https?://[^\s\"']+\.(exe|dll|bat|ps1|scr|msi)\b", "links to a program download"),
    (r"\bos\.remove\s*\(\s*[\"'][A-Za-z]:\\", "deletes files on the PC"),
]
MAX_TOTAL_UNCOMPRESSED = 12 * 1024 ** 3      # 12 GB
MAX_RATIO = 250                              # compression ratio of a single large entry
MAX_ENTRIES = 200_000


# --------------------------------------------------------------------------- helpers
def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        tmp = CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        os.replace(tmp, CACHE_FILE)
    except OSError:
        pass


def worst(a, b):
    order = {"clean": 0, "warning": 1, "blocked": 2}
    return a if order[a] >= order[b] else b


# --------------------------------------------------------------------------- 1. built-in
def builtin_checks(path):
    verdict, reasons = "clean", []

    def flag(level, msg):
        nonlocal verdict
        verdict = worst(verdict, level)
        if msg not in reasons:
            reasons.append(msg)

    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        return "blocked", ["not a valid .zip file"]

    with z:
        infos = z.infolist()
        if len(infos) > MAX_ENTRIES:
            flag("blocked", "contains an absurd number of files (%d)" % len(infos))
            return verdict, reasons
        total = 0
        has_mod_content = False
        for info in infos:
            name = info.filename.replace("\\", "/")
            low = name.lower()
            base = low.rsplit("/", 1)[-1]
            ext = base.rsplit(".", 1)[-1] if "." in base else ""
            total += info.file_size

            if name.startswith("/") or re.match(r"^[a-z]:", low) or "/../" in "/" + name + "/":
                flag("blocked", "tries to write outside the mod folder: %s" % name)
            if info.flag_bits & 0x1:
                flag("blocked", "has password-protected files that can't be checked: %s" % name)
                continue
            if info.is_dir():
                continue
            if low.startswith(("vehicles/", "levels/", "art/", "ui/", "lua/", "scripts/",
                               "settings/", "gameplay/", "mods/")) or ext in ("jbeam", "dae"):
                has_mod_content = True
            if ext in BLOCKED_EXT:
                flag("blocked", "contains a program/script file: %s" % name)
            elif re.search(r"\.(exe|scr|bat|cmd|js|vbs|pif|com)\.[a-z0-9]{1,4}$", base) and ext not in ("js",):
                flag("blocked", "has a disguised file name: %s" % name)
            if ext in NESTED_ARCHIVE_EXT:
                flag("warning", "contains another archive that wasn't checked: %s" % name)
            if info.file_size > 50 * 1024 ** 2 and info.compress_size and \
                    info.file_size / info.compress_size > MAX_RATIO:
                flag("blocked", "looks like a 'zip bomb' (fills up the disk): %s" % name)

            # content checks (only read what is needed)
            try:
                if ext not in MAGIC_SAFE_EXT and info.file_size >= 4:
                    with z.open(info) as fh:
                        head = fh.read(4)
                    for sig, what in MAGIC:
                        if head.startswith(sig):
                            flag("blocked", "%s is really %s" % (name, what))
                            break
                if ext == "lua" and info.file_size < 8 * 1024 ** 2:
                    code = z.read(info).decode("utf-8", "replace")
                    for pat, what in LUA_PATTERNS:
                        if re.search(pat, code):
                            flag("warning", "Lua script %s %s" % (name, what))
            except (RuntimeError, zipfile.BadZipFile, NotImplementedError, OSError, EOFError) as e:
                flag("blocked", "damaged or unreadable file inside: %s (%s)" % (name, e.__class__.__name__))

        if total > MAX_TOTAL_UNCOMPRESSED:
            flag("blocked", "unpacks to more than 12 GB - looks like a 'zip bomb'")
        if not has_mod_content and infos and verdict != "blocked":
            flag("warning", "doesn't look like a BeamNG mod (no vehicles/, levels/, ui/... folders)")
    return verdict, reasons


# --------------------------------------------------------------------------- 2. ClamAV
def clamav_check(path):
    for tool in ("clamdscan", "clamscan"):
        exe = shutil.which(tool)
        if not exe:
            continue
        args = [exe, "--no-summary", "--infected"]
        if tool == "clamdscan":
            args.append("--fdpass")
        try:
            r = subprocess.run(args + [path], capture_output=True, text=True, timeout=900)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 1:
            hit = (r.stdout.strip().splitlines() or ["virus found"])[0].split(":", 1)[-1].strip()
            return "blocked", ["ClamAV antivirus: %s" % hit], "ClamAV"
        if r.returncode == 0:
            return "clean", [], "ClamAV"
    return "clean", [], None


def defender_check(path):
    """Microsoft Defender (Windows only). Returns (verdict, reasons, used_name)."""
    if os.name != "nt":
        return "clean", [], None
    exe = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Windows Defender", "MpCmdRun.exe")
    if not os.path.isfile(exe):
        return "clean", [], None
    try:
        r = subprocess.run([exe, "-Scan", "-ScanType", "3", "-File", path, "-DisableRemediation"],
                           capture_output=True, text=True, timeout=900,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        return "clean", [], None
    if r.returncode == 2:
        threat = next((l.split(":", 1)[1].strip() for l in r.stdout.splitlines() if "Threat" in l and ":" in l),
                      "threat found")
        return "blocked", ["Microsoft Defender: %s" % threat], "Microsoft Defender"
    if r.returncode == 0:
        return "clean", [], "Microsoft Defender"
    return "clean", [], None


# --------------------------------------------------------------------------- 3. VirusTotal
VT = "https://www.virustotal.com/api/v3"


def _vt(method, url, key, data=None, headers=None, timeout=60):
    h = {"x-apikey": key, "accept": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _vt_verdict(stats, sha):
    mal, sus = int(stats.get("malicious", 0)), int(stats.get("suspicious", 0))
    link = "https://www.virustotal.com/gui/file/%s" % sha
    if mal >= 2:
        return "blocked", ["VirusTotal: %d antivirus engines say it's malicious (%s)" % (mal, link)]
    if mal == 1 or sus:
        return "warning", ["VirusTotal: %d engine(s) flagged it - probably a false alarm (%s)" % (mal + sus, link)]
    return "clean", []


def virustotal_check(path, sha, key, upload_max_mb):
    """Returns (verdict, reasons, note)."""
    try:
        try:
            d = _vt("GET", "%s/files/%s" % (VT, sha), key)
            stats = d["data"]["attributes"].get("last_analysis_stats", {})
            if sum(int(v) for v in stats.values()) > 0:
                v, r = _vt_verdict(stats, sha)
                return v, r, "VirusTotal (known file)"
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return "clean", [], "VirusTotal skipped: the API key is wrong"
            if e.code == 429:
                return "clean", [], "VirusTotal skipped: free limit reached, try later"
            if e.code != 404:
                raise

        size_mb = os.path.getsize(path) / 1024 ** 2
        if size_mb > upload_max_mb:
            return "clean", [], "VirusTotal skipped: new file is %.0f MB (upload limit %d MB)" % (size_mb, upload_max_mb)

        # new file: upload it (VirusTotal allows up to 650 MB)
        url = "%s/files" % VT
        if size_mb > 32:
            url = _vt("GET", "%s/files/upload_url" % VT, key)["data"]
        boundary = uuid.uuid4().hex
        fname = os.path.basename(path).encode("utf-8", "replace").replace(b'"', b"_")
        with open(path, "rb") as f:
            payload = (b"--" + boundary.encode() + b"\r\n"
                       b'Content-Disposition: form-data; name="file"; filename="' + fname + b'"\r\n'
                       b"Content-Type: application/zip\r\n\r\n" + f.read() + b"\r\n--" +
                       boundary.encode() + b"--\r\n")
        up = _vt("POST", url, key, data=payload,
                 headers={"Content-Type": "multipart/form-data; boundary=" + boundary}, timeout=1800)
        analysis = up["data"]["id"]
        deadline = time.time() + 300
        while time.time() < deadline:
            time.sleep(20)  # free API: 4 requests per minute
            a = _vt("GET", "%s/analyses/%s" % (VT, analysis), key)
            attr = a["data"]["attributes"]
            if attr.get("status") == "completed":
                v, r = _vt_verdict(attr.get("stats", {}), sha)
                return v, r, "VirusTotal (uploaded)"
        return "clean", [], "VirusTotal: still analysing after 5 minutes - built-in checks used"
    except Exception as e:  # network problems must never break uploads
        return "clean", [], ("VirusTotal skipped: can't reach it (no internet?)" if isinstance(e, urllib.error.URLError) else "VirusTotal skipped: %s" % e.__class__.__name__)


# --------------------------------------------------------------------------- main API
def _file_id(path):
    # ctime + inode can't be set back by hand (unlike the modified date), so a
    # changed file can't pretend to be one that was checked before
    st = os.stat(path)
    return "%s|%d|%d|%d|%d" % (os.path.basename(path), st.st_size, int(st.st_mtime), st.st_ino, st.st_ctime_ns)


def remember(path, sha):
    """Note that the file at path has this (already checked) content - e.g. after it was moved."""
    try:
        cache = load_cache()
        if sha in cache:
            cache.setdefault("_index", {})[_file_id(path)] = sha
            save_cache(cache)
    except OSError:
        pass


def cached_result(path):
    """Result for a file scanned before, without re-hashing it (fast, for lists)."""
    try:
        cache = load_cache()
        sha = cache.get("_index", {}).get(_file_id(path))
        r = cache.get(sha) if sha else None
        return r if r and r.get("v") == SCANNER_VERSION else None
    except OSError:
        return None


def scan(path, use_cache=True, force=False):
    """force=True: check again even if a result is cached, and save the new result."""
    cache = load_cache() if use_cache else {}
    sha = (None if force else cache.get("_index", {}).get(_file_id(path))) or sha256_of(path)
    hit = None if force else cache.get(sha)
    vt_key = os.environ.get("VT_API_KEY", "").strip()
    if hit and hit.get("v") == SCANNER_VERSION and (hit.get("vt") or not vt_key or hit.get("verdict") == "blocked"):
        fid = _file_id(path)
        if use_cache and cache.get("_index", {}).get(fid) != sha:
            cache.setdefault("_index", {})[fid] = sha     # same content under a new name/date
            save_cache(cache)
        return dict(hit, cached=True, name=os.path.basename(path))

    verdict, reasons = builtin_checks(path)
    checks = ["built-in"]
    notes = []
    for av in (clamav_check, defender_check):
        if verdict == "blocked":
            break
        v, r, used = av(path)
        if used:
            checks.append(used)
        verdict, reasons = worst(verdict, v), reasons + r
    vt_done = False
    if verdict != "blocked" and vt_key:
        try:
            limit = int(os.environ.get("VT_UPLOAD_MAX_MB", "200"))
        except ValueError:
            limit = 200
        v, r, note = virustotal_check(path, sha, vt_key, limit)
        if note.startswith("VirusTotal (") or note.startswith("VirusTotal: still"):
            checks.append("VirusTotal")
            vt_done = note.startswith("VirusTotal (")
        else:
            notes.append(note)
        verdict, reasons = worst(verdict, v), reasons + r

    result = {"sha256": sha, "verdict": verdict, "reasons": reasons, "checks": checks,
              "notes": notes, "v": SCANNER_VERSION, "vt": vt_done,
              "name": os.path.basename(path), "time": int(time.time())}
    if use_cache:
        cache = load_cache()
        cache[sha] = result
        idx = cache.setdefault("_index", {})
        idx[_file_id(path)] = sha
        # keep the cache small
        results = [k for k in cache if k != "_index"]
        if len(results) > 2000:
            for k in sorted(results, key=lambda k: cache[k].get("time", 0))[:500]:
                cache.pop(k, None)
        if len(idx) > 4000:
            cache["_index"] = {}
        save_cache(cache)
    return result


def write_note(path, text):
    """Write a small text file in a shared folder without following links."""
    try:
        os.unlink(path)
    except OSError:
        pass
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o664)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def why_text(reasons):
    return "Blocked by the BeamMP EasyServer mod safety check:\n- " + "\n- ".join(reasons) + "\n"


def sweep(folder, quarantine):
    """Scan all zips in folder; move blocked ones into quarantine. Returns count blocked."""
    blocked = 0
    if not os.path.isdir(folder):
        return 0
    for n in sorted(os.listdir(folder)):
        p = os.path.join(folder, n)
        if not (n.lower().endswith(".zip") and os.path.isfile(p)) or os.path.islink(p):
            continue            # links are ignored: they could point at private files
        r = scan(p)
        if r["verdict"] == "blocked":
            os.makedirs(quarantine, exist_ok=True)
            dest = os.path.join(quarantine, n)
            os.replace(p, dest)
            write_note(dest + ".why.txt", why_text(r["reasons"]))
            print("BLOCKED and moved to quarantine: %s" % n)
            for reason in r["reasons"]:
                print("   - " + reason)
            blocked += 1
    return blocked


def print_result(r):
    icon = {"clean": "OK     ", "warning": "WARNING", "blocked": "BLOCKED"}[r["verdict"]]
    print("[%s] %s   (checked by: %s)" % (icon, r["name"], ", ".join(r["checks"])))
    for reason in r["reasons"]:
        print("    - " + reason)
    for note in r.get("notes", []):
        print("    note: " + note)


def main(argv):
    if len(argv) >= 3 and argv[0] == "--sweep":
        n = sweep(argv[1], argv[2])
        return 2 if n else 0
    as_json = bool(argv) and argv[0] == "--json"
    files = argv[1:] if as_json else argv
    if not files:
        print(__doc__)
        return 1
    results, rc = [], 0
    for f in files:
        r = scan(f) if os.path.isfile(f) else {"name": f, "verdict": "blocked",
                                                 "reasons": ["file not found"], "checks": [], "notes": []}
        if r["verdict"] == "blocked":
            rc = 2
        results.append(r)
        if not as_json:
            print_result(r)
    if as_json:
        print(json.dumps(results))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
