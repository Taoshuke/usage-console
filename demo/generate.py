"""Generates demo/usage.json: fully fictional usage for three sources, used by the live demo and as
the page's built-in fallback. Deterministic (fixed seed) so rebuilding does not churn the file."""
import json
import math
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

random.seed(2026)
END = date(2026, 10, 24)
START = END - timedelta(days=119)
TZ = "America/Los_Angeles"

SOURCES = [
    {"id": "claude-code", "name": "Claude Code", "kind": "logs"},
    {"id": "codex-cli", "name": "Codex CLI", "kind": "logs"},
    {"id": "anthropic-api", "name": "Anthropic API", "kind": "billing"},
]
# USD per million tokens: input, output, cache read, cache write. Illustrative only.
PRICES = {
    "claude-opus-5-5": [5, 25, 0.5, 6.25],
    "claude-sonnet-5-5": [3, 15, 0.3, 3.75],
    "claude-haiku-5-5": [1, 5, 0.1, 1.25],
    "example-model-a": [1.25, 10, 0.125, 0],
    "example-model-b": [0.25, 2, 0.025, 0],
}


def days():
    d = START
    while d <= END:
        yield d
        d += timedelta(days=1)


def busy(d, base):
    """Weekday rhythm, a slow upward trend and some noise."""
    weekday = [1.0, 1.1, 1.05, 1.15, 0.9, 0.35, 0.3][d.weekday()]
    trend = 0.55 + 0.9 * (d - START).days / (END - START).days
    return base * weekday * trend * random.lognormvariate(0, 0.45)


rows = []
for d in days():
    ds = d.isoformat()
    # Claude Code: Opus early, Sonnet takes over in September, Haiku for small jobs
    if random.random() > 0.12:
        mix = {"claude-opus-5-5": 0.75 if d < date(2026, 9, 1) else 0.35,
               "claude-sonnet-5-5": 0.15 if d < date(2026, 9, 1) else 0.55,
               "claude-haiku-5-5": 0.10}
        vol = busy(d, 1.0)
        if d == date(2026, 10, 7):
            vol *= 3.2  # one launch day stands out
        sessions = max(1, round(vol * random.uniform(3, 7)))
        for model, share in mix.items():
            k = vol * share * random.uniform(0.8, 1.2)
            rows.append({"d": ds, "src": "claude-code", "model": model,
                         "in": int(9e4 * k), "out": int(1.1e6 * k), "cr": int(2.6e8 * k), "cw": int(6e6 * k),
                         "sessions": round(sessions * share)})
    # Codex CLI: started mid-August, weekdays only
    if d >= date(2026, 8, 18) and d.weekday() < 5 and random.random() > 0.3:
        for model, share in (("example-model-a", 0.8), ("example-model-b", 0.2)):
            k = busy(d, 0.6) * share
            rows.append({"d": ds, "src": "codex-cli", "model": model,
                         "in": int(2.2e6 * k), "out": int(3e5 * k), "cr": int(2.4e7 * k), "cw": 0,
                         "sessions": max(0, round(k * 4))})
    # Anthropic API: a small app in production, billed daily
    if d >= date(2026, 7, 10) and not (d.weekday() >= 5 and random.random() < 0.6):
        for model, share in (("claude-sonnet-5-5", 0.7), ("claude-haiku-5-5", 0.3)):
            k = busy(d, 0.5) * share * (1.4 if d.weekday() < 5 else 1)
            i, o = int(3.1e6 * k), int(4.2e5 * k)
            p = PRICES[model]
            rows.append({"d": ds, "src": "anthropic-api", "model": model, "in": i, "out": o, "cr": 0, "cw": 0,
                         "requests": int(900 * k), "cost": round((i * p[0] + o * p[1]) / 1e6, 2)})

HOURLY = [2, 1, 1, 0, 0, 0, 1, 4, 11, 22, 30, 33, 24, 28, 34, 36, 33, 27, 18, 14, 12, 9, 6, 3]
WEEK = {"claude-code": [1.1, 1.15, 1.05, 1.2, 0.95, 0.4, 0.35], "codex-cli": [1, 1.1, 1, 1, 0.9, 0.1, 0.05],
        "anthropic-api": [1, 1, 1, 1, 1, 0.8, 0.8]}
SCALE = {"claude-code": 6, "codex-cli": 1.5, "anthropic-api": 0}
punch = {s: [[round(h * w * SCALE[s] * random.uniform(0.75, 1.25)) for h in HOURLY] for w in WEEK[s]]
         for s in WEEK if SCALE[s]}

data = {
    "version": 1,
    "demo": True,
    "generated": datetime(2026, 10, 24, 8, 30, tzinfo=timezone(timedelta(hours=-7))).isoformat(),
    "timezone": TZ,
    "currency": "USD",
    "sources": SOURCES,
    "prices": {"verified": False, "per_mtok": PRICES},
    "quotas": [
        {"src": "claude-code", "name": "Max plan", "window": "5h", "used": 0.42, "resets": "2026-10-24T11:00:00-07:00"},
        {"src": "claude-code", "name": "Max plan", "window": "7d", "used": 0.68, "resets": "2026-10-27T09:00:00-07:00"},
        {"src": "codex-cli", "name": "Plus plan", "window": "7d", "used": 0.21, "resets": "2026-10-29T00:00:00-07:00"},
    ],
    "longest_session": {"src": "claude-code", "ms": int((5 * 3600 + 42 * 60) * 1000), "start": "2026-10-07"},
    "punch": punch,
    "rows": rows,
}
out = Path(__file__).resolve().parent / "usage.json"
out.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
print(f"{len(rows)} rows, {out.stat().st_size // 1024} KB")
