"""tokenboard collector: runs the enabled source adapters and stores the dashboard's data.

    python3 collector/collect.py                      # uses tokenboard.config.json, writes public/data/usage.json
    python3 collector/collect.py --config my.json --out somewhere/usage.json

With "storage": "notion" in the config the data goes to Notion instead of a file (see docs/notion.md).
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import ADAPTERS  # noqa: E402
from sinks import notion  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=ROOT / "tokenboard.config.json", type=Path)
    ap.add_argument("--out", default=ROOT / "public" / "data" / "usage.json", type=Path)
    args = ap.parse_args(argv)

    if not args.config.exists():
        sys.exit(f"{args.config} not found; copy tokenboard.config.example.json to start")
    config = load_json(args.config)
    tz = ZoneInfo(config.get("timezone", "UTC"))
    prices_path = (args.config.parent / config.get("prices", "prices.json")).resolve()
    prices = load_json(prices_path) if prices_path.exists() else {"verified": False, "per_mtok": {}}

    sources, rows, punch, longest = [], [], {}, None
    for source_id, options in config.get("sources", {}).items():
        if not options.get("enabled", True):
            continue
        adapter = ADAPTERS.get(source_id)
        if adapter is None:
            sys.exit(f"unknown source '{source_id}'; available: {', '.join(ADAPTERS)}")
        result = adapter.collect(options, tz)
        sources.append(adapter.SOURCE)
        rows += result["rows"]
        if result.get("punch"):
            punch[source_id] = result["punch"]
        ls = result.get("longest_session")
        if ls and (longest is None or ls["ms"] > longest["ms"]):
            longest = ls
        print(f"{source_id}: {len(result['rows'])} rows", file=sys.stderr)

    data = {
        "version": 1,
        "generated": datetime.now(tz).isoformat(timespec="seconds"),
        "timezone": str(tz),
        "currency": config.get("currency", "USD"),
        "sources": sources,
        "prices": prices,
        "quotas": config.get("quotas", []),
        "longest_session": longest,
        "punch": punch,
        "rows": sorted(rows, key=lambda r: (r["d"], r["src"], r["model"])),
    }
    if config.get("storage", "json") == "notion":
        notion.push(data, config["notion"], log=lambda m: print(m, file=sys.stderr))
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, args.out)  # never leave a half-written file for a deploy to pick up
    print(f"wrote {args.out} ({len(data['rows'])} rows)", file=sys.stderr)


if __name__ == "__main__":
    main()
