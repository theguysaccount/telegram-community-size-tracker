import unittest

from pipeline import tme

CHANNEL = """<div class="tgme_page_title" dir="auto"><span dir="auto">Example &amp; News</span><i class="verified-icon"></i></div>
<div class="tgme_page_extra">9 071&nbsp;412 subscribers</div><div class="tgme_page_description">Hello</div>"""
GROUP = """<div class="tgme_page_title" dir="auto"><span dir="auto">Example Group</span></div>
<div class="tgme_page_extra">315 181 members, 6 103 online</div>"""
NOTHING = """<div class="tgme_page_title"><span>Someone</span></div><div class="tgme_page_extra">@someone</div>"""


class ParseTests(unittest.TestCase):
    def test_channel(self):
        p = tme.parse("example", CHANNEL.replace("&nbsp;", " "))
        self.assertTrue(p.ok)
        self.assertEqual((p.kind, p.count, p.title, p.verified), ("channel", 9071412, "Example & News", True))

    def test_group_keeps_total_members_only(self):
        p = tme.parse("examplegroup", GROUP)
        self.assertEqual((p.kind, p.count, p.verified), ("group", 315181, False))
        self.assertNotIn("6103", str(p.__dict__))   # the "online" count is never kept

    def test_page_without_a_count_is_not_read(self):
        p = tme.parse("someone", NOTHING)
        self.assertFalse(p.ok)
        self.assertTrue(p.error)

    def test_handle_validation(self):
        self.assertFalse(tme.fetch("a b").ok)
        self.assertIn("valid", tme.fetch("../etc").error)


if __name__ == "__main__":
    unittest.main()
