"""Mod updates from the BeamNG repository: "Update all" and installing updates by themselves while nobody plays.
beamng.com is never asked: the download is replaced by a fake."""
import types
import unittest
from unittest import mock

import harness  # noqa: F401  (sets up the throw-away server folder first)
from harness import D


def fake_apply(results):
    def apply(name, u):
        st = results[name]
        if st == 200:
            u.update(update=False, have="2.0")
            return 200, {"version": "2.0"}
        return st, {"error": "%s broke" % name}
    return apply


class FakeServer:
    def __init__(self, state):
        self.state, self.actions = state, []

    def status(self):
        return {"state": self.state}

    def action(self, what):
        self.actions.append(what)


class UpdateMods(unittest.TestCase):
    def setUp(self):
        self.ups = {"a.zip": {"update": True}, "b.zip": {"update": True}, "c.zip": {"update": False}}
        patches = [mock.patch.object(D, "apply_mod_update", fake_apply({"a.zip": 200, "b.zip": 502})),
                   mock.patch.object(D.time, "sleep", lambda s: None),
                   mock.patch.object(D, "refresh_mod_desc", lambda: None)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_one_after_the_other(self):
        done, failed = D.update_mods(["a.zip", "b.zip"], self.ups)
        self.assertEqual(done, ["a.zip"])
        self.assertEqual(failed, [("b.zip", "b.zip broke")])

    def app(self, players, state="running"):
        server = FakeServer(state)
        inst = types.SimpleNamespace(id="main", name="Test server", server=server)
        notes = []
        app = types.SimpleNamespace(mod_updates={inst.id: self.ups}, config_changed=lambda: notes.append(("config",)),
                                    notifier=types.SimpleNamespace(add=lambda *a: notes.append(a)))
        p1 = mock.patch.object(D, "online_names", lambda: list(players))
        p2 = mock.patch.dict(D.INSTANCES, {"main": inst}, clear=True)
        before = getattr(D._TL, "inst", None)       # mod_auto_update switches the current server: put it back
        self.addCleanup(lambda: setattr(D._TL, "inst", before) if before is not None else D._TL.__dict__.pop("inst", None))
        p1.start(), p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)
        return app, server, notes

    def test_nothing_happens_while_someone_plays(self):
        app, server, notes = self.app(["Bob"])
        D.App.mod_auto_update(app)
        self.assertEqual((notes, server.actions), ([], []))
        self.assertTrue(self.ups["a.zip"]["update"])

    def test_updates_and_restarts_an_empty_server(self):
        app, server, notes = self.app([])
        D.App.mod_auto_update(app)
        self.assertEqual(server.actions, ["restart"])
        self.assertFalse(self.ups["a.zip"]["update"])
        titles = [n[1] for n in notes if len(n) > 1]
        self.assertIn("Mod updated by itself", titles)
        self.assertIn("A mod update didn't work", titles)
        self.assertFalse(self.ups["b.zip"]["update"], "a failed update is tried again only after the next check")

    def test_a_stopped_server_is_not_started(self):
        app, server, notes = self.app([], state="stopped")
        D.App.mod_auto_update(app)
        self.assertEqual(server.actions, [])
        self.assertIn(("config",), notes)


if __name__ == "__main__":
    unittest.main()
