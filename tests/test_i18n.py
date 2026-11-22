"""Dashboard translations (dashboard/lang/*.json): well-formed, placeholders kept, served without login."""
import json
import os
import re
import sys
import unittest

import harness
from harness import D, Client

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG_DIR = os.path.join(ROOT, "dashboard", "lang")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import i18n  # noqa: E402


def files():
    return {f[:-5]: os.path.join(LANG_DIR, f) for f in sorted(os.listdir(LANG_DIR)) if f.endswith(".json")}


class Files(unittest.TestCase):
    def test_well_formed(self):
        self.assertGreaterEqual(set(files()), {"de", "es", "hu", "pl"})
        for code, path in files().items():
            self.assertRegex(code, r"^[a-z]{2}(-[a-z]{2})?$")
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            self.assertTrue(str(d.get("language", "")).strip(), code)
            self.assertIsInstance(d.get("strings"), dict, code)
            for k, v in d["strings"].items():
                self.assertIsInstance(v, str, (code, k))

    def test_placeholders_kept(self):
        """{} is filled in at runtime: a translation must use the same number of them (or numbered ones)."""
        bad = []
        for code, path in files().items():
            with open(path, encoding="utf-8") as f:
                strings = json.load(f)["strings"]
            for k, v in strings.items():
                n = k.count("{}")
                nums = [int(x) for x in re.findall(r"\{(\d+)\}", v)]
                if nums:
                    ok = all(1 <= x <= n for x in nums) and "{}" not in v
                else:
                    ok = len(re.findall(r"\{\}", v)) == n
                if not ok:
                    bad.append("%s: %r -> %r" % (code, k, v))
        self.assertEqual(bad, [])

    def test_mostly_translated(self):
        """The rest is commands, product names and examples that stay English on purpose."""
        for code, path in files().items():
            with open(path, encoding="utf-8") as f:
                strings = json.load(f)["strings"]
            self.assertGreater(i18n.coverage(strings), 0.85, code)

    def test_no_html_in_translations(self):
        """Translations are put into the page as text, but keep them free of markup anyway."""
        for code, path in files().items():
            with open(path, encoding="utf-8") as f:
                strings = json.load(f)["strings"]
            for k, v in strings.items():
                self.assertNotRegex(v, r"<\s*[a-zA-Z/!]", (code, k))


@unittest.skipIf(D.IS_WIN, "live tests run on Linux")
class Served(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = harness.start()

    def test_index_and_files_without_login(self):
        c = Client(self.base)
        st, d = c.call("/lang/index.json")[:2]
        self.assertEqual(st, 200)
        codes = {x["code"]: x["name"] for x in d["languages"]}
        self.assertEqual(codes.get("de"), "Deutsch")
        self.assertEqual(codes.get("hu"), "Magyar")
        st, d = c.call("/lang/pl.json")[:2]
        self.assertEqual(st, 200)
        self.assertIn("Zapisz", d["strings"].values())

    def test_only_language_files(self):
        c = Client(self.base)
        for p in ("/lang/xx.json", "/lang/../dashboard.py", "/lang/de.json.bak", "/lang/README.md", "/lang/%2e%2e/data.json"):
            self.assertNotEqual(c.call(p)[0], 200, p)


if __name__ == "__main__":
    unittest.main()
