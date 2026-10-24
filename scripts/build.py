"""Builds public/: wraps the page template in a full HTML document, embeds sample/usage.json as fallback data
and publishes data/usage.json.

The template is written for the Artifact preview, whose host adds the document shell (charset, viewport,
base reset). The site has no such host, so this script adds the same shell; without the charset, browsers
on a Chinese system read the UTF-8 page as GBK.

Until the real collector writes public/data/usage.json, the sample is published there too.
"""
import shutil
from pathlib import Path

SHELL_HEAD = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
{head}
<style>
:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
body{margin:0}
img{max-width:100%}
[hidden]{display:none!important}
</style>
</head>
<body>
"""
SHELL_TAIL = "\n</body>\n</html>\n"

root = Path(__file__).resolve().parent.parent
page = (root / "src" / "index.template.html").read_text(encoding="utf-8")
sample = (root / "sample" / "usage.json").read_text(encoding="utf-8")
body = page.replace("__SAMPLE__", sample)
# The template opens with its <title>, <meta> and <link> tags; they belong in <head>.
lines = body.split("\n")
n = 0
while n < len(lines) and lines[n].startswith(("<title", "<meta", "<link")):
    n += 1
head, body = "\n".join(lines[:n]), "\n".join(lines[n:])
(root / "public" / "index.html").write_text(SHELL_HEAD.replace("{head}", head) + body + SHELL_TAIL, encoding="utf-8")
data = root / "public" / "data" / "usage.json"
if not data.exists():
    data.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "sample" / "usage.json", data)
