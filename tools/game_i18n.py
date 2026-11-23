"""Translations of what the game plugin says in the chat (and the helper mod shows on screen).

  python3 tools/game_i18n.py              how much of each language's "game" section is translated
  python3 tools/game_i18n.py missing de   the English messages that have no German translation yet
  python3 tools/game_i18n.py list         every English message the plugin can send

The English text is read straight out of the plugin (dashboard/EasyServerStats/main.lua): everything
passed to say(...). {} stands for something filled in (a name, a number, another message). A translation
can use {} in the same order, or {1}, {2}... to change the order or leave one out (like an English "s").
Pieces that are chosen inside a message ("for the next one", "none yet") are their own entries."""
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "dashboard", "EasyServerStats", "main.lua")
LANG = os.path.join(ROOT, "dashboard", "lang")

# Text that reaches the chat through a variable instead of straight inside say(...)
EXTRA = ["left the game", "left the server", "Your badges", "{}'s badges", "a race", "cops and robbers",
         "north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]
# The helper mod's on-screen text lives in the dashboard (GAME_HUD_TEXT), which sends it to the mod.
DASHBOARD = os.path.join(ROOT, "dashboard", "dashboard.py")


def hud_text():
    src = open(DASHBOARD, encoding="utf-8").read()
    m = re.search(r"^GAME_HUD_TEXT = (\(.*?\n\))", src, re.S | re.M)
    return list(ast.literal_eval(m.group(1)))


def _lit(s):
    return bytes(s, "utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")


def _skip_str(s, j):
    q = s[j]
    j += 1
    while s[j] != q:
        j += 2 if s[j] == "\\" else 1
    return j


def _close(s, i):
    """s[i] == '(' -> index just after the matching ')'."""
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c in "\"'":
            j = _skip_str(s, j)
        elif s.startswith("[==[", j):
            j = s.index("]==]", j) + 3
        elif s.startswith("--", j):
            j = s.index("\n", j) - 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    raise ValueError("unbalanced at %d" % i)


def _split(expr, sep):
    out, depth, j, start = [], 0, 0, 0
    while j < len(expr):
        c = expr[j]
        if c in "\"'":
            j = _skip_str(expr, j)
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and expr.startswith(sep, j):
            out.append(expr[start:j].strip())
            j += len(sep)
            start = j
            continue
        j += 1
    out.append(expr[start:].strip())
    return out


def _wrapped(p):
    if not (p.startswith("(") and p.endswith(")")):
        return False
    try:
        return _close(p, 0) == len(p)
    except ValueError:
        return False


STR = re.compile(r'^(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\')$')
FMT = re.compile(r"%[-+ #0]*\d*(?:\.\d+)?[sdfiq]")
ANY_STR = re.compile(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'')


def _fmt(f):
    return FMT.sub("{}", f).replace("%%", "%")


def _unwrap(p):
    while _wrapped(p):
        p = p[1:-1].strip()
    return p


def _text(p, used, pieces):
    """A literal, string.format(...) or a concatenation -> its template; anything else -> None."""
    p = _unwrap(p)
    m = STR.match(p)
    if m:
        s = _lit(m.group(1) if m.group(1) is not None else m.group(2))
        used.add(s)
        return s
    m = re.match(r'^string\.format\(\s*("(?:[^"\\]|\\.)*")', p)
    if m and _wrapped(p[len("string.format"):]):
        s = _lit(m.group(1)[1:-1])
        used.add(s)
        for a in _split(p[len("string.format") + 1:-1], ",")[1:]:
            _choices(a, used, pieces)
        return _fmt(s)
    if len(_split(p, "..")) > 1:
        return _template(p, used, pieces)
    return None


def _choices(p, used, pieces):
    """(x and "this" or "that" .. y): each text it can turn into is a piece of its own."""
    for alt in _split(_unwrap(p), " or "):
        for part in _split(_unwrap(alt), " and "):
            t = _text(part, used, pieces)
            if t is not None:
                pieces.append(t)


def _template(expr, used, pieces):
    out = ""
    for p in _split(expr, ".."):
        t = _text(p, used, pieces) if (STR.match(_unwrap(p)) or _unwrap(p).startswith("string.format")
                                        or len(_split(_unwrap(p), "..")) > 1) else None
        if t is not None:
            out += t
            continue
        _choices(p, used, pieces)
        out += "{}"
    return re.sub(r"(\{\})+", "{}", out)


def _clean(t):
    return t.strip()            # inner spaces stay: the plugin matches the exact message


def templates():
    """Every English message (and message piece) the plugin can say, in the order they appear."""
    src = open(PLUGIN, encoding="utf-8").read()
    out = []

    def add(t, leftover=False, sure=False):
        t = _clean(t)
        if not re.search(r"[A-Za-z]{2}", t) or t in out:
            return
        if not sure and re.fullmatch(r"[,/ ]*[a-z_]+", t):
            return       # code words ("cop", "speed")
        if leftover and re.fullmatch(r"[^{]*[:\-]|min\.|every.*|hour|Next repair in|No player called", t):
            return       # bits of a message that is put together elsewhere
        out.append(t)

    for m in re.finditer(r"\bsay\(", src):
        i = m.end() - 1
        end = _close(src, i)
        if src[max(0, m.start() - 15):m.start()].endswith("function "):
            continue
        args = _split(src[i + 1:end - 1], ",")
        if len(args) < 2:
            continue
        expr = src[i + 1:end - 1].split(",", 1)[1].strip()
        used, pieces = set(), []
        for alt in _split(expr, " or "):          # "or" and "and" bind looser than ".." in Lua
            for part in _split(alt, " and "):
                t = _text(part, used, pieces)
                if t is not None:
                    add(t)
        for t in pieces:                          # pieces chosen inside the message
            add(t)
        for a, b in ANY_STR.findall(expr):        # anything else that's text
            s = _lit(a or b)
            if s not in used:
                add(_fmt(s), leftover=True)
    # the command list (/help and the suggestions while typing): what to type after it, and what it does
    for m in re.finditer(r'\badd\(\s*"[a-z]+"\s*,', src):
        i = src.index("(", m.start())
        args = _split(src[i + 1:_close(src, i) - 1], ",")
        if len(args) == 3:
            for a in args[1:]:
                used, pieces = set(), []
                t = _text(a, used, pieces)
                for x in ([t] if t is not None else []) + pieces:
                    add(x, sure=True)
                if t is None:
                    _choices(a, used, pieces)
                    for x in pieces:
                        add(x, sure=True)
    # badges: their names and what they're for
    m = re.search(r"BADGES = \{(.*?)\n  \},", src, re.S)
    for _, title, what in re.findall(r'\{ "(\w+)", "([^"]+)", "([^"]+)" \}', m.group(1) if m else ""):
        add(title, sure=True)
        add(what, sure=True)
    for t in EXTRA + hud_text():
        add(t, sure=True)
    return out


def placeholders(t):
    return t.count("{}")


def lang_files():
    out = {}
    for n in sorted(os.listdir(LANG)):
        if n.endswith(".json"):
            with open(os.path.join(LANG, n), encoding="utf-8") as f:
                out[n[:-5]] = json.load(f)
    return out


def coverage(game, english=None):
    english = english if english is not None else templates()
    return sum(1 for k in english if game.get(k)) / max(1, len(english))


if __name__ == "__main__":
    english = templates()
    langs = lang_files()
    if len(sys.argv) >= 2 and sys.argv[1] == "list":
        print("\n".join(english))
    elif len(sys.argv) >= 3 and sys.argv[1] == "missing":
        g = langs[sys.argv[2]].get("game", {})
        print("\n".join(k for k in english if not g.get(k)))
    else:
        print("%d English messages in the game plugin" % len(english))
        for code, d in langs.items():
            print("  %-6s %-10s %5.1f%% translated" % (code, d.get("language", "?"), coverage(d.get("game", {}), english) * 100))
