"""Claude Code adapter: reads Claude Code's /stats cache and the session logs under ~/.claude/projects.

Days the cache has computed (~/.claude/stats-cache.json, through its lastComputedDate) take its numbers, so
tokens, messages and sessions match /stats exactly:
- each model's daily tokens come from the cache; they are split into input, output, cache read and cache
  write in the proportions the logs show for that day and model, or the model's all-time proportions when
  the logs for that day are gone
- the share of cache writes that went to the 1-hour cache follows the logs for that day and model
- the day's messages and sessions come from the cache and go to the row of the day's busiest model; a day
  with activity but no token record is put under the "unrecorded_model" option ("unknown" by default)
- the longest session is the one the cache reports
Days after that are counted from the logs with the rules below.

Log counting rules (they differ from /stats):
- a session is a main-thread sessionId; it counts on the day of its first message, under the model
  of its first reply
- tokens are input + output + cache read + cache write of every assistant reply, subagents included;
  a reply streamed over several log lines shares one message.id and is counted once
- the weekly rhythm counts main-thread prompts and replies (tool results are not messages)
"""
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SOURCE = {"id": "claude-code", "name": "Claude Code", "kind": "logs"}
PARTS = (("in", "input_tokens"), ("out", "output_tokens"), ("cr", "cache_read_input_tokens"),
         ("cw", "cache_creation_input_tokens"))
CACHE_PARTS = (("in", "inputTokens"), ("out", "outputTokens"), ("cr", "cacheReadInputTokens"),
               ("cw", "cacheCreationInputTokens"))


def _is_tool_result(content):
    return isinstance(content, list) and bool(content) and all(
        isinstance(c, dict) and c.get("type") == "tool_result" for c in content)


def load_cache(path):
    """The /stats cache as {through, days: {day: {model: tokens}}, activity: {day: (messages, sessions)},
    mix: {model: {part: tokens}}, longest}, or None when there is no usable cache."""
    try:
        cache = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    days = {}
    for d in cache.get("dailyModelTokens") or []:
        by_model = d.get("tokensByModel") or {k: v for k, v in d.items() if k != "date" and isinstance(v, (int, float))}
        days[d["date"]] = {m: int(n) for m, n in by_model.items() if n}
    activity = {d["date"]: (d.get("messageCount") or 0, d.get("sessionCount") or 0)
                for d in cache.get("dailyActivity") or []}
    through = cache.get("lastComputedDate") or max(list(days) + list(activity), default=None)
    if not through:
        return None
    mix = {m: {k: u.get(f) or 0 for k, f in CACHE_PARTS}
           for m, u in (cache.get("modelUsage") or {}).items() if isinstance(u, dict)}
    return {"through": through, "days": days, "activity": activity, "mix": mix,
            "longest": cache.get("longestSession")}


def split(total, weights):
    """Splits total into integer parts proportional to weights (input, output, cache read, cache write)."""
    keys = [k for k, _ in PARTS]
    w = [max(weights.get(k, 0), 0) for k in keys]
    if not sum(w):
        w = [0, 0, 1, 0]  # nothing to go by: count it all as cache read, the bulk of Claude Code's tokens
    parts = [total * x // sum(w) for x in w]
    parts[w.index(max(w))] += total - sum(parts)
    return dict(zip(keys, parts))


def from_cache(cache, log_rows, unrecorded_model="unknown"):
    """Rows for the days the cache covers; log rows only lend their token proportions."""
    logged = {(r["d"], r["model"]): r for r in log_rows}
    rows = []
    for day in sorted(set(cache["days"]) | set(cache["activity"])):
        if day > cache["through"]:
            continue
        models = cache["days"].get(day, {})
        day_rows = []
        for model, total in sorted(models.items()):
            log = logged.get((day, model))
            row = {"d": day, "src": SOURCE["id"], "model": model, **split(total, log or cache["mix"].get(model, {}))}
            if log and log.get("cw1h") and log.get("cw"):
                row["cw1h"] = min(row["cw"], round(row["cw"] * log["cw1h"] / log["cw"]))
            day_rows.append(row)
        messages, sessions = cache["activity"].get(day, (0, 0))
        if (messages or sessions) and not day_rows:
            day_rows.append({"d": day, "src": SOURCE["id"], "model": unrecorded_model, **split(0, {})})
        if day_rows:
            top = max(day_rows, key=lambda r: models.get(r["model"], 0))
            if sessions:
                top["sessions"] = sessions
            if messages:
                top["messages"] = messages
        rows += day_rows
    return rows


def cached_longest(longest):
    try:
        start = datetime.fromisoformat(longest["timestamp"].replace("Z", "+00:00")).date().isoformat()
        return {"src": SOURCE["id"], "ms": int(longest["duration"]), "start": start}
    except (TypeError, KeyError, ValueError, AttributeError):
        return None


def collect(options, tz):
    result = collect_logs(options, tz)
    cache = load_cache(os.path.expanduser(options.get("stats_cache", "~/.claude/stats-cache.json")))
    if options.get("use_stats_cache", True) and cache:
        later = [r for r in result["rows"] if r["d"] > cache["through"]]
        result["rows"] = from_cache(cache, result["rows"], options.get("unrecorded_model", "unknown")) + later
        result["longest_session"] = cached_longest(cache["longest"]) or result["longest_session"]
        result["complete_through"] = cache["through"]
    return result


def collect_logs(options, tz):
    root = os.path.expanduser(options.get("path", "~/.claude/projects"))
    seen_uuids, seen_usage, seen_replies = set(), set(), set()
    usage = defaultdict(lambda: defaultdict(int))     # (day, model) -> part -> tokens
    sessions = {}                                     # sessionId -> [first, last, first model]
    punch = [[0] * 24 for _ in range(7)]

    for dirpath, _, files in os.walk(root):
        for name in files:
            if not name.endswith(".jsonl"):
                continue
            with open(os.path.join(dirpath, name), encoding="utf-8", errors="replace") as f:
                for line in f:
                    if '"type":"user"' not in line and '"type":"assistant"' not in line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # a session still being written can end in a partial line
                    kind, uuid, ts = rec.get("type"), rec.get("uuid"), rec.get("timestamp")
                    if kind not in ("user", "assistant") or rec.get("isMeta") or not uuid or not ts:
                        continue
                    if uuid in seen_uuids:
                        continue  # resumed and forked sessions copy earlier lines into a new file
                    seen_uuids.add(uuid)
                    when = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(tz)
                    msg = rec.get("message") or {}
                    main = not rec.get("isSidechain")
                    sid = rec.get("sessionId")
                    if main and sid:
                        s = sessions.setdefault(sid, [when, when, None])
                        s[0], s[1] = min(s[0], when), max(s[1], when)

                    if kind == "user":
                        if main and not _is_tool_result(msg.get("content")):
                            punch[when.weekday()][when.hour] += 1
                        continue

                    mid, model, u = msg.get("id"), msg.get("model"), msg.get("usage")
                    if model == "<synthetic>" or not mid:
                        continue
                    model = model or "unknown"
                    if main and mid not in seen_replies:
                        seen_replies.add(mid)
                        punch[when.weekday()][when.hour] += 1
                        if sid and sessions[sid][2] is None:
                            sessions[sid][2] = model
                    if u and mid not in seen_usage:
                        seen_usage.add(mid)
                        cell = usage[(when.date().isoformat(), model)]
                        for key, field in PARTS:
                            cell[key] += u.get(field) or 0
                        cell["cw1h"] += (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0

    session_count = defaultdict(int)
    for first, _, model in sessions.values():
        if model:
            session_count[(first.date().isoformat(), model)] += 1

    rows = []
    for day, model in sorted(set(usage) | set(session_count)):
        cell = usage.get((day, model), {})
        row = {"d": day, "src": SOURCE["id"], "model": model}
        row.update({key: cell.get(key, 0) for key, _ in PARTS})
        if cell.get("cw1h"):
            row["cw1h"] = cell["cw1h"]
        if session_count.get((day, model)):
            row["sessions"] = session_count[(day, model)]
        rows.append(row)

    longest = None
    if sessions:
        first, last, _ = max(sessions.values(), key=lambda s: s[1] - s[0])
        longest = {"src": SOURCE["id"], "ms": int((last - first).total_seconds() * 1000),
                   "start": first.date().isoformat()}
    return {"rows": rows, "punch": punch if any(map(any, punch)) else None, "longest_session": longest}
