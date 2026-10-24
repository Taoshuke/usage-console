"""Builds public/: embeds sample/usage.json into the page as fallback data and publishes data/usage.json.

Until the real collector writes public/data/usage.json, the sample is published there too.
"""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
page = (root / "src" / "index.template.html").read_text(encoding="utf-8")
sample = (root / "sample" / "usage.json").read_text(encoding="utf-8")
(root / "public" / "index.html").write_text(page.replace("__SAMPLE__", sample), encoding="utf-8")
data = root / "public" / "data" / "usage.json"
if not data.exists():
    data.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "sample" / "usage.json", data)
