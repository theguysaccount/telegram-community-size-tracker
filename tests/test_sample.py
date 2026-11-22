import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from pipeline import sample, store as S, tme


class SampleTests(unittest.TestCase):
    def setUp(self):
        self.data = tempfile.mkdtemp()
        with open(os.path.join(self.data, "channels.json"), "w") as f:
            json.dump([{"handle": "examplechan", "category": "Test", "added": "2026-01-01"},
                       {"handle": "brokenchan", "category": "Test", "added": "2026-01-01"}], f)

    def tearDown(self):
        shutil.rmtree(self.data)

    def fake(self, handle):
        if handle == "brokenchan":
            return tme.Page(handle=handle, status=503, error="HTTP 503")
        return tme.Page(handle=handle, ok=True, status=200, title="Example", kind="channel", count=12345)

    def test_sample_appends_skips_and_keeps_errors(self):
        with mock.patch.object(tme, "fetch", self.fake):
            self.assertEqual(sample.main(["--data", self.data]), 0)
            self.assertEqual(len(S.history("examplechan", self.data)), 1)
            sample.main(["--data", self.data])       # a re-run within 6 hours adds nothing
        self.assertEqual(len(S.history("examplechan", self.data)), 1)
        st = S.state(self.data)
        self.assertEqual(st["channels"]["examplechan"]["count"], 12345)
        self.assertEqual(st["channels"]["brokenchan"]["status"], "error")
        self.assertEqual(S.history("brokenchan", self.data), [])
        self.assertTrue(st["sampled"])

    def test_run_fails_only_when_nothing_could_be_read(self):
        with mock.patch.object(tme, "fetch", lambda h: tme.Page(handle=h, error="blocked")):
            self.assertEqual(sample.main(["--data", self.data]), 1)


if __name__ == "__main__":
    unittest.main()
