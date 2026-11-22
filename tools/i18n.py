"""Translations helper for the dashboard.

  python3 tools/i18n.py              how much of each language in dashboard/lang is translated
  python3 tools/i18n.py missing de   the English text that has no German translation yet

It reads the English text straight out of the dashboard's source (dashboard/ui/src), so it is always up to date."""
import re, json, sys
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(ROOT, "dashboard", "ui")
code = open(os.path.join(UI, "src", "legacy.js"), encoding="utf-8").read()     # pages still drawn as HTML text
jsx = "\n".join(open(os.path.join(UI, "src", f), encoding="utf-8").read() for f in sorted(os.listdir(os.path.join(UI, "src"))) if f.endswith(".jsx"))   # the React part
html_head = open(os.path.join(UI, "head.html"), encoding="utf-8").read()
M = "\x00"
templates, strings = [], []   # (text with M for ${}) ; (literal, plus_before, plus_after)

def skip_ws_back(i):
    while i >= 0 and code[i] in " \t\n": i -= 1
    return i

def parse(i, stop_brace=False):
    """Parse code from i; returns index after the closing } when stop_brace."""
    depth = 0
    n = len(code)
    while i < n:
        c = code[i]
        if c in "\"'":
            j = i + 1; buf = []
            while code[j] != c:
                if code[j] == "\\": buf.append(code[j:j+2]); j += 2; continue
                buf.append(code[j]); j += 1
            lit = "".join(buf)
            pb = code[skip_ws_back(i - 1)] == "+"
            k = j + 1
            while k < n and code[k] in " \t\n": k += 1
            pa = code[k] == "+" and code[k+1] != "+"
            strings.append((lit, pb, pa))
            i = j + 1; continue
        if c == "`":
            i = parse_template(i + 1); continue
        if c == "/" and code[i+1] == "/":
            i = code.index("\n", i); continue
        if c == "/" and code[i+1] == "*":
            i = code.index("*/", i) + 2; continue
        if c == "/":
            p = skip_ws_back(i - 1)
            prev = code[p] if p >= 0 else "("
            word = re.search(r"(\w+)$", code[:p+1])
            if prev in "(,=:[!&|?{};+-*%<>~^" or (word and word.group(1) in ("return", "typeof", "case")):
                j = i + 1; cls = False
                while True:
                    ch = code[j]
                    if ch == "\\": j += 2; continue
                    if ch == "[": cls = True
                    elif ch == "]": cls = False
                    elif ch == "/" and not cls: break
                    j += 1
                i = j + 1
                while i < n and code[i].isalpha(): i += 1
                continue
        if stop_brace:
            if c == "{": depth += 1
            elif c == "}":
                if depth == 0: return i + 1
                depth -= 1
        i += 1
    return i

def parse_template(i):
    buf = []
    while True:
        c = code[i]
        if c == "\\": buf.append(code[i+1]); i += 2; continue
        if c == "`": templates.append("".join(buf)); return i + 1
        if c == "$" and code[i+1] == "{":
            buf.append(M); i = parse(i + 2, stop_brace=True); continue
        buf.append(c); i += 1

parse(0)

keys = {}
def norm(t):
    t = re.sub(r"\s+", " ", t).strip()
    t = t.replace(M, "{}")
    t = re.sub(r"(\{\})(\s*\{\})+", "{}", t)
    return t
def add(t, where):
    t = norm(t)
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    letters = re.sub(r"\{\}", "", t)
    if not re.search(r"[A-Za-z]{2}", letters): return
    if re.fullmatch(r"[\w\-./:#{}]+", t) and not re.search(r"[A-Z][a-z]", t) and " " not in t: return   # ids, classes, urls
    if re.fullmatch(r"\{\}[\w\-]+|[\w\-]+\{\}", t): return
    if t.startswith(("http", "/api/", "#", ".")) or re.search(r"[;{}]\s*$", t.replace("{}", "")) : return
    if re.search(r"^(var\(|rgba?\(|\d+px|[a-z-]+:)", t): return
    keys.setdefault(t, where)

ATTR_RE = re.compile(r'\b(placeholder|title|aria-label|alt)="([^"]*)"')
def html_text(h, where):
    for m in ATTR_RE.finditer(h):
        add(m.group(2), where + ":attr")
    # drop tags (they can contain markers in attributes)
    parts = re.split(r"<[^<>]*>", h)
    for p in parts:
        add(p, where)

for t in templates:
    if "<" in t or ">" in t:
        html_text(t, "tpl")
    else:
        add(t, "tpl")
def unesc(x):
    return re.sub(r"\\(u\{?[0-9a-fA-F]+\}?|.)", lambda m: {"n": "\n", "t": " "}.get(m.group(1), m.group(1)) if not m.group(1).startswith("u") else chr(int(m.group(1).strip("u{}"), 16)), x)
for lit, pb, pa in strings:
    lit = unesc(lit)
    if "\n" in lit:
        pieces = [x for x in lit.split("\n")]
        for k, piece in enumerate(pieces):
            add(("{}" if pb and k == 0 else "") + piece + ("{}" if pa and k == len(pieces) - 1 else ""), "str")
        continue
    if "<" in lit and ">" in lit:
        html_text(lit, "str"); continue
    s = (("{}" if pb else "") + lit + ("{}" if pa else ""))
    # code-ish strings
    if re.fullmatch(r"[#.\[\w\-=\]\s:>\"*,()]+", lit) and (lit.startswith(("#", ".", "[")) or " " not in lit.strip()):
        if not re.search(r"^[A-Z][a-z]", lit): continue
    add(s, "str")
html_text(re.sub(r"<style[\s\S]*?</style>", "", html_head), "head")

# React (app.jsx): text between tags, the attributes people read, and quoted text that isn't code
jsx = re.sub(r"//[^\n]*", "", jsx)
for m in re.finditer(r"(?<![=\w])>([^<>{}]*[A-Za-z][^<>{}]*)(?=[<{])|\}([^<>{}]*[A-Za-z][^<>{}]*)(?=<)", jsx):
    t = m.group(1) or m.group(2)
    if not re.search(r"[;=]|\breturn\b|\bcase\b|\)\s*$", t): add(t, "jsx")
CODE_ATTR = r"(?:className|key|type|autoComplete|inputMode|rel|target|href|kind|role|shapeRendering|fill|viewBox|value|name|n|d|x|y|width|height|style)"
for m in re.finditer(r'(\b' + CODE_ATTR + r'=)?"((?:[^"\\\n]|\\.)*)"', jsx):
    if m.group(1): continue
    lit = unesc(m.group(2))
    if re.fullmatch(r"[#.\[\w\-=\]\s:>\"*,()/]+", lit) and not re.search(r"^[A-Z][a-z]", lit) and not re.search(r"[a-z] [a-z]", lit):
        continue
    add(lit, "jsx")
ENGLISH = sorted(keys)


def lang_files():
    d = os.path.join(ROOT, "dashboard", "lang")
    return {f[:-5]: json.load(open(os.path.join(d, f), encoding="utf-8")) for f in sorted(os.listdir(d)) if f.endswith(".json")}


def coverage(strings):
    done = [k for k in ENGLISH if strings.get(k)]
    return len(done) / max(1, len(ENGLISH))


if __name__ == "__main__":
    langs = lang_files()
    if len(sys.argv) >= 3 and sys.argv[1] == "missing":
        s = langs[sys.argv[2]]["strings"]
        for k in ENGLISH:
            if not s.get(k):
                print(k)
    else:
        print("%d English texts in the dashboard" % len(ENGLISH))
        for code, d in langs.items():
            print("  %-6s %-10s %5.1f%% translated" % (code, d.get("language", "?"), coverage(d.get("strings", {})) * 100))
