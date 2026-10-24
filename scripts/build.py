"""Builds the deployable site into public/.

web/index.html is a page fragment: it opens with its <title>, <meta> and <link> tags, then styles, markup
and script. This script moves those head tags into a full HTML document (with an explicit UTF-8 charset,
without which browsers on a Chinese system may decode the page as GBK), embeds demo/usage.json as the
fallback data, and copies the demo data to public/data/usage.json unless real data is already there.

    python3 scripts/build.py            # build public/
    python3 scripts/build.py --preview  # also write public/preview.html, the bare fragment
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
{head}
<style>
:root{{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}
img{{max-width:100%}}
[hidden]{{display:none!important}}
</style>
</head>
<body>
"""


def main():
    page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    demo = (ROOT / "demo" / "usage.json").read_text(encoding="utf-8")
    fragment = page.replace("__DEMO__", demo.replace("</", "<\\/"))
    lines = fragment.split("\n")
    n = 0
    while n < len(lines) and lines[n].startswith(("<title", "<meta", "<link")):
        n += 1
    head, body = "\n".join(lines[:n]), "\n".join(lines[n:])

    out = ROOT / "public"
    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(HEAD.format(head=head) + body + "\n</body>\n</html>\n", encoding="utf-8")
    if "--preview" in sys.argv:
        (out / "preview.html").write_text(fragment, encoding="utf-8")
    shutil.copyfile(ROOT / "web" / "_headers", out / "_headers")
    data = out / "data" / "usage.json"
    if not data.exists():
        shutil.copyfile(ROOT / "demo" / "usage.json", data)
    print(f"built {out / 'index.html'}")


if __name__ == "__main__":
    main()
