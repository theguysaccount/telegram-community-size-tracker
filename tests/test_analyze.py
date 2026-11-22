import datetime as dt
import unittest

from pipeline import analyze as A


def series(counts, start="2026-11-01T06:00:00Z", hours=12, source="t.me"):
    t0 = A.parse_time(start)
    return [{"time": (t0 + dt.timedelta(hours=hours * i)).strftime("%Y-%m-%dT%H:%M:%SZ"), "count": c, "source": source}
            for i, c in enumerate(counts)]


class AnalyzeTests(unittest.TestCase):
    def test_steady_growth_is_not_unusual(self):
        rows = series([100_000 + 200 * i for i in range(40)])
        self.assertEqual(A.unusual(rows), [])

    def test_a_jump_is_flagged_once(self):
        counts = [100_000 + 200 * i for i in range(20)]
        counts.append(counts[-1] + 30_000)                 # +~29% in 12 hours
        counts += [counts[-1] + 200 * i for i in range(1, 10)]
        found = A.unusual(series(counts))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["kind"], "jump")
        self.assertGreater(found[0]["pct"], 20)

    def test_a_drop_is_flagged(self):
        counts = [500_000 - 100 * i for i in range(20)] + [400_000]
        self.assertEqual(A.unusual(series(counts))[0]["kind"], "drop")

    def test_small_channels_and_long_gaps_and_archive_points_are_not_flagged(self):
        small = [1000 + i for i in range(20)] + [1900]           # +90% but only 880 accounts
        self.assertEqual(A.unusual(series(small)), [])
        gapped = series([100_000 + 200 * i for i in range(20)] + [160_000], hours=96)  # samples too far apart
        self.assertEqual(A.unusual(gapped), [])
        archive = series([100_000 + 200 * i for i in range(20)] + [160_000], source="archive")
        self.assertEqual(A.unusual(archive), [])

    def test_needs_a_baseline(self):
        self.assertEqual(A.unusual(series([100_000, 100_100, 160_000])), [])

    def test_change_over(self):
        rows = series([1000 * (i + 1) for i in range(30)], hours=24)
        c = A.change_over(rows, 7, A.parse_time(rows[-1]["time"]))
        self.assertEqual((c["from"], c["to"]), (23000, 30000))
        self.assertIsNone(A.change_over(rows, 365, A.parse_time(rows[-1]["time"])))
        self.assertIsNone(A.change_over(rows[:1], 7, A.parse_time(rows[0]["time"])))

    def test_formatting(self):
        self.assertEqual(A.compact(9_071_412), "9.07M")
        self.assertEqual(A.compact(315_181), "315K")
        self.assertEqual(A.compact(8_917), "8.9K")
        self.assertEqual(A.signed_pct(2.345), "+2.3%")
        self.assertEqual(A.signed_pct(-0.01), "0.0%")


if __name__ == "__main__":
    unittest.main()
