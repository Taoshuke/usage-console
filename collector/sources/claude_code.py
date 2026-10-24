"""Claude Code adapter: reads the session logs under ~/.claude/projects.

Counting rules (they differ from Claude Code's /stats, which reads its own cache):
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

SOURCE = {"id": "claude-code", "name": "Claude Code", "kind": "logs"}
PARTS = (("in", "input_tokens"), ("out", "output_tokens"), ("cr", "cache_read_input_tokens"),
         ("cw", "cache_creation_input_tokens"))


def _is_tool_result(content):
    return isinstance(content, list) and bool(content) and all(
        isinstance(c, dict) and c.get("type") == "tool_result" for c in content)


def collect(options, tz):
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

    session_count = defaultdict(int)
    for first, _, model in sessions.values():
        if model:
            session_count[(first.date().isoformat(), model)] += 1

    rows = []
    for day, model in sorted(set(usage) | set(session_count)):
        cell = usage.get((day, model), {})
        row = {"d": day, "src": SOURCE["id"], "model": model}
        row.update({key: cell.get(key, 0) for key, _ in PARTS})
        if session_count.get((day, model)):
            row["sessions"] = session_count[(day, model)]
        rows.append(row)

    longest = None
    if sessions:
        first, last, _ = max(sessions.values(), key=lambda s: s[1] - s[0])
        longest = {"src": SOURCE["id"], "ms": int((last - first).total_seconds() * 1000),
                   "start": first.date().isoformat()}
    return {"rows": rows, "punch": punch if any(map(any, punch)) else None, "longest_session": longest}
