"""Build from the real data and from fixtures; expected values come from the data, never launch-day numbers."""
import datetime as dt
import html
import json
import os
import re
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlsplit

from pipeline import build as B
from pipeline import store as S

SITE = "https://theguysaccount.github.io/telegram-community-size-tracker"


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class RealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp()
        cls.ctx = B.build(cls.out, site_url=SITE, env={})
        cls.tracked = [c for c in S.channels() if S.history(c["handle"])]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.out)

    def page(self, rel):
        return read(os.path.join(self.out, rel))

    def test_pages_and_files(self):
        self.assertGreater(len(self.tracked), 0)
        for c in self.tracked:
            slug = c["handle"].lower()
            for rel in (f"channels/{slug}/index.html", f"embed/{slug}.svg", f"data/history/{slug}.csv", f"og/{slug}.png"):
                self.assertTrue(os.path.exists(os.path.join(self.out, rel)), rel)
            p = self.page(f"channels/{slug}/index.html")
            last = S.history(c["handle"])[-1]
            self.assertIn(f"{last['count']:,}", p)
            self.assertIn('class="correction"', p)
            for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', p, re.S):
                json.loads(block)

    def test_sitemap_canonicals_links(self):
        locs = [el.text for el in ET.fromstring(self.page("sitemap.xml")).iter() if el.tag.endswith("loc")]
        self.assertEqual(len(locs), 3 + len(self.tracked))
        for loc in locs:
            canon = re.search(r'<link rel="canonical" href="([^"]+)"', self.page(loc[len(SITE) + 1:] + "index.html")).group(1)
            self.assertEqual(canon, loc)
        for root, _d, files in os.walk(self.out):
            for name in files:
                if name.endswith(".html") and name != "404.html":
                    rel = os.path.relpath(os.path.join(root, name), self.out)
                    for href in re.findall(r'(?:href|src)="([^"#]+)', read(os.path.join(root, name))):
                        href = html.unescape(href)
                        if re.match(r"^(https?:|mailto:|//)", href):
                            continue
                        target = urlsplit(urljoin("http://x/" + rel, href)).path.lstrip("/")
                        target += "index.html" if target == "" or target.endswith("/") else ""
                        self.assertTrue(os.path.exists(os.path.join(self.out, target)), f"{rel} -> {href}")

    def test_home_feed_data(self):
        p = self.page("index.html")
        self.assertIn(f'data-count="{len(self.tracked)}"', p)
        ET.fromstring(self.page("feed.xml"))
        data = json.loads(self.page("data/channels.json"))
        self.assertEqual(sorted(a["handle"] for a in data["apps"]), sorted(c["handle"] for c in self.tracked))
        counts = [a["count"] for a in data["apps"]]
        self.assertEqual(counts, sorted(counts, reverse=True))   # listed by size
        self.assertIn(f"Sitemap: {SITE}/sitemap.xml", self.page("robots.txt"))


class Fixtures(unittest.TestCase):
    def setUp(self):
        self.data = tempfile.mkdtemp()
        with open(os.path.join(self.data, "channels.json"), "w") as f:
            json.dump([{"handle": "spikychan", "category": "Test", "added": "2026-11-01"},
                       {"handle": "quietchan", "category": "Other", "added": "2026-11-01"}], f)
        t0 = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=15)
        rows = [{"time": (t0 + dt.timedelta(hours=12 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"), "count": 200_000 + 300 * i, "source": "t.me"}
                for i in range(25)]
        rows[20:] = [dict(r, count=r["count"] + 60_000) for r in rows[20:]]
        archive = [{"time": "2025-06-01T00:00:00Z", "count": 150_000, "source": "archive"}]
        S.write_history("spikychan", archive + rows, self.data)
        S.write_history("quietchan", rows[:3], self.data)
        S.save_state({"sampled": rows[-1]["time"], "channels": {"spikychan": {"title": "Spiky <Test>", "kind": "channel", "status": "ok"},
                                                                 "quietchan": {"title": "Quiet", "kind": "group", "status": "error", "error": "HTTP 503"}}}, self.data)
        self.out = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.data)
        shutil.rmtree(self.out)

    def test_unusual_change_and_error_states(self):
        B.build(self.out, data=self.data, site_url="https://example.org", env={})
        p = read(os.path.join(self.out, "channels/spikychan/index.html"))
        self.assertIn("Spiky &lt;Test&gt;", p)
        self.assertIn("rose +", p)
        self.assertIn("dot-archive", p)
        q = read(os.path.join(self.out, "channels/quietchan/index.html"))
        self.assertIn("could not read this page", q)
        self.assertIn("members", q)
        items = ET.fromstring(read(os.path.join(self.out, "feed.xml"))).findall("./channel/item")
        self.assertTrue(any(i.findtext("guid").startswith("unusual-spikychan") for i in items))
        self.assertIn('href="https://example.org/"', read(os.path.join(self.out, "index.html")))

    def test_money_slot_is_off_until_set(self):
        B.build(self.out, data=self.data, site_url="https://example.org", env={"SUPPORT_URL": "https://example.org/s"})
        self.assertIn('href="https://example.org/s"', read(os.path.join(self.out, "index.html")))
        B.build(self.out, data=self.data, site_url="https://example.org", env={})
        self.assertNotIn("example.org/s\"", read(os.path.join(self.out, "index.html")))


if __name__ == "__main__":
    unittest.main()
