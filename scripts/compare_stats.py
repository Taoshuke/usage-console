"""Compares Claude Code's own /stats cache with several ways of counting the session logs, to find the
counting rules that reproduce /stats. Run it on the machine that has the logs and paste the output.

    python3 scripts/compare_stats.py                 # uses the computer's local time zone
    python3 scripts/compare_stats.py --tz America/Chicago

It only reads ~/.claude/stats-cache.json and ~/.claude/projects; nothing is written or sent anywhere.
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

PARTS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def tool_result_only(content):
    return isinstance(content, list) and bool(content) and all(isinstance(c, dict) and c.get("type") == "tool_result" for c in content)


def load_cache(path):
    cache = json.loads(path.read_text(encoding="utf-8"))
    print(f"cache: version {cache.get('version')}, computed through {cache.get('lastComputedDate')}, keys: {', '.join(sorted(cache))}")
    days = {}
    for d in cache.get("dailyActivity", []):
        days[d["date"]] = {"messages": d.get("messageCount"), "sessions": d.get("sessionCount"), "tools": d.get("toolCallCount")}
    for d in cache.get("dailyModelTokens", []):
        by_model = d.get("tokensByModel") or {k: v for k, v in d.items() if isinstance(v, (int, float)) and k != "date"}
        days.setdefault(d["date"], {})["tokens"] = sum(by_model.values())
    models = {}
    for m, u in (cache.get("modelUsage") or {}).items():
        if isinstance(u, dict):
            models[m] = {k: v for k, v in u.items() if isinstance(v, (int, float))}
    return cache, days, models


def scan(root, tz):
    """One pass over the logs, keeping per-line facts so every rule can be evaluated afterwards."""
    lines = []
    files = 0
    for dirpath, _, names in os.walk(root):
        for name in names:
            if not name.endswith(".jsonl"):
                continue
            files += "subagents" not in dirpath
            with open(os.path.join(dirpath, name), encoding="utf-8", errors="replace") as f:
                for line in f:
                    if '"type":"user"' not in line and '"type":"assistant"' not in line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    kind, ts = rec.get("type"), rec.get("timestamp")
                    if kind not in ("user", "assistant") or not ts:
                        continue
                    msg = rec.get("message") or {}
                    when = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(tz)
                    usage = msg.get("usage") or {}
                    lines.append({"kind": kind, "uuid": rec.get("uuid"), "sid": rec.get("sessionId"), "side": bool(rec.get("isSidechain")),
                                  "meta": bool(rec.get("isMeta")), "day": when.date().isoformat(), "mid": msg.get("id"),
                                  "model": msg.get("model"), "tool": kind == "user" and tool_result_only(msg.get("content")),
                                  "usage": [usage.get(p) or 0 for p in PARTS]})
    return lines, files


def rule_tokens(lines, dedupe_uuid, dedupe_mid, main_only, parts):
    seen_u, seen_m, out = set(), set(), Counter()
    for l in lines:
        if l["kind"] != "assistant" or l["model"] == "<synthetic>" or (main_only and l["side"]):
            continue
        if dedupe_uuid:
            if l["uuid"] in seen_u:
                continue
            seen_u.add(l["uuid"])
        if dedupe_mid and l["mid"]:
            if l["mid"] in seen_m:
                continue
            seen_m.add(l["mid"])
        out[l["day"]] += sum(l["usage"][i] for i in parts)
    return out


def rule_messages(lines, dedupe_uuid, main_only, with_tools, with_meta, dedupe_mid):
    seen_u, seen_m, out = set(), set(), Counter()
    for l in lines:
        if (main_only and l["side"]) or (l["tool"] and not with_tools) or (l["meta"] and not with_meta):
            continue
        if dedupe_uuid:
            if l["uuid"] in seen_u:
                continue
            seen_u.add(l["uuid"])
        if dedupe_mid and l["kind"] == "assistant" and l["mid"]:
            if l["mid"] in seen_m:
                continue
            seen_m.add(l["mid"])
        out[l["day"]] += 1
    return out


def rule_sessions(lines, main_only, active_days):
    first, active = {}, defaultdict(set)
    for l in lines:
        if not l["sid"] or (main_only and l["side"]):
            continue
        first[l["sid"]] = min(first.get(l["sid"], l["day"]), l["day"])
        active[l["day"]].add(l["sid"])
    if active_days:
        return Counter({d: len(s) for d, s in active.items()})
    return Counter(first.values())


def compare(name, cache_days, field, counted, through):
    days = [d for d in cache_days if cache_days[d].get(field) is not None and d <= through]
    if not days:
        return None
    want = sum(cache_days[d][field] for d in days)
    got = sum(counted.get(d, 0) for d in days)
    exact = sum(1 for d in days if counted.get(d, 0) == cache_days[d][field])
    return (abs(got - want) / want if want else 0, name, want, got, exact, len(days))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tz", help="IANA time zone; defaults to this computer's local zone")
    ap.add_argument("--home", default=str(Path.home() / ".claude"))
    args = ap.parse_args()
    if args.tz:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(args.tz)
    else:
        tz = datetime.now().astimezone().tzinfo
    home = Path(os.path.expanduser(args.home))
    cache, cache_days, cache_models = load_cache(home / "stats-cache.json")
    through = cache.get("lastComputedDate") or max(cache_days)
    lines, files = scan(home / "projects", tz)
    print(f"logs: {len(lines)} user/assistant lines in {files} session files; time zone {tz}")
    print(f"cache totals: sessions {cache.get('totalSessions')}, messages {cache.get('totalMessages')}")
    log_days = sorted({l['day'] for l in lines})
    missing = [d for d in cache_days if d <= through and d not in log_days]
    print(f"days in cache but absent from the logs (logs cleaned up?): {len(missing)} {missing[:8]}")

    results = {"tokens": [], "messages": [], "sessions": []}
    for parts_name, parts in (("all four parts", (0, 1, 2, 3)), ("input+output", (0, 1)), ("input+output+cache write", (0, 1, 3))):
        for du in (True, False):
            for dm in (True, False):
                for mo in (False, True):
                    name = f"tokens: {parts_name}; {'uuid-deduped' if du else 'no uuid dedupe'}; {'one per reply id' if dm else 'every line'}; {'main thread' if mo else 'incl. subagents'}"
                    r = compare(name, cache_days, "tokens", rule_tokens(lines, du, dm, mo, parts), through)
                    if r: results["tokens"].append(r)
    for du in (True, False):
        for mo in (False, True):
            for wt in (True, False):
                for wm in (True, False):
                    for dm in (False, True):
                        name = f"messages: {'uuid-deduped' if du else 'no uuid dedupe'}; {'main thread' if mo else 'incl. subagents'}; {'with' if wt else 'without'} tool results; {'with' if wm else 'without'} meta; {'one per reply id' if dm else 'every line'}"
                        r = compare(name, cache_days, "messages", rule_messages(lines, du, mo, wt, wm, dm), through)
                        if r: results["messages"].append(r)
    for mo in (False, True):
        for ad in (False, True):
            name = f"sessions: {'main thread' if mo else 'incl. subagents'}; {'active that day' if ad else 'counted on first day'}"
            r = compare(name, cache_days, "sessions", rule_sessions(lines, mo, ad), through)
            if r: results["sessions"].append(r)

    for field, rs in results.items():
        print(f"\n== {field}: closest rules (total difference, days that match exactly)")
        for off, name, want, got, exact, n in sorted(rs)[:4]:
            print(f"{off*100:7.2f}%  exact {exact}/{n}  cache {want:,}  logs {got:,}  <- {name}")
    if cache_models:
        print("\n== modelUsage fields in the cache (first model):", json.dumps(next(iter(cache_models.items())))[:300])


if __name__ == "__main__":
    sys.exit(main())
