import os
import unittest

from pipeline import store as S, tme

# Personal channels are out of scope (channels, never people). Known examples are blocked outright.
PERSONAL = {"durov"}


class DataTests(unittest.TestCase):
    def test_channel_list(self):
        chans = S.channels()
        handles = [c["handle"].lower() for c in chans]
        self.assertGreater(len(chans), 0)
        self.assertEqual(len(handles), len(set(handles)))
        for c in chans:
            self.assertRegex(c["handle"], tme.HANDLE_RE)
            self.assertTrue(c["category"])
            self.assertNotIn(c["handle"].lower(), PERSONAL)

    def test_histories(self):
        for c in S.channels():
            rows = S.history(c["handle"])
            times = [r["time"] for r in rows]
            self.assertEqual(times, sorted(times), c["handle"])
            self.assertEqual(len(times), len(set(times)))
            for r in rows:
                self.assertGreater(r["count"], 0)
                self.assertIn(r["source"], ("t.me", "archive"))
                self.assertRegex(r["time"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        # No history file for a channel that is no longer listed
        listed = {c["handle"].lower() for c in S.channels()}
        for name in os.listdir(os.path.join(S.DATA, "history")):
            self.assertIn(name[:-4], listed, name)


if __name__ == "__main__":
    unittest.main()
