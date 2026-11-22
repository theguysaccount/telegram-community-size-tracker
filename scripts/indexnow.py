"""Tell IndexNow search engines (Bing, Yandex, Seznam, Naver and others) about the site's pages.

    python3 scripts/indexnow.py dist/urls.txt

The key file (<key>.txt) is published at the site root by the build. A failed submission is reported
but exits 0: the site itself is already live, and the next deploy tries again. Standard library only.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SITE_URL = "https://theguysaccount.github.io/telegram-community-size-tracker"


def main(path):
    with open(os.path.join(ROOT, "site", "indexnow-key.txt"), encoding="utf-8") as f:
        key = f.read().strip()
    base = (os.environ.get("SITE_URL") or DEFAULT_SITE_URL).rstrip("/")
    host = urlparse(base).hostname
    with open(path, encoding="utf-8") as f:
        urls = [u for u in f.read().split() if urlparse(u).hostname == host and u.startswith(base + "/")][:10000]
    if not urls:
        print("IndexNow: no URLs to submit")
        return 0
    body = json.dumps({"host": host, "key": key, "keyLocation": f"{base}/{key}.txt", "urlList": urls}).encode()
    for attempt in range(4):  # a new key answers 403 until the engine has fetched the key file
        if attempt:
            time.sleep(30 * attempt)
        req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                print(f"IndexNow: HTTP {r.status} for {len(urls)} URLs")
                return 0
        except urllib.error.HTTPError as e:
            print(f"IndexNow: HTTP {e.code} {e.reason}")
            if e.code not in (403, 429) and e.code < 500:
                break
        except OSError as e:
            print(f"IndexNow: {e}")
    print("::warning::IndexNow submission did not succeed; the next deploy will try again")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist", "urls.txt")))
