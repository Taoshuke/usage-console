import json
import sys
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "collector"))
from sources import claude_code  # noqa: E402


def line(**rec):
    return json.dumps(rec, separators=(",", ":")) + "\n"


def reply(uuid, mid, ts, model="claude-opus-5-5", sid="s1", side=False, usage=(10, 20, 300, 40), cw1h=0):
    u = dict(zip(("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"), usage))
    if cw1h:
        u["cache_creation"] = {"ephemeral_5m_input_tokens": usage[3] - cw1h, "ephemeral_1h_input_tokens": cw1h}
    return line(type="assistant", uuid=uuid, timestamp=ts, sessionId=sid, isSidechain=side,
                message={"id": mid, "model": model, "usage": u})


class ClaudeCodeTest(unittest.TestCase):
    def run_on(self, files, cache=None, **options):
        with tempfile.TemporaryDirectory() as root:
            for name, text in files.items():
                p = Path(root, name)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            cache_path = Path(root, "stats-cache.json")
            if cache is not None:
                cache_path.write_text(json.dumps(cache), encoding="utf-8")
            return claude_code.collect({"path": str(Path(root, "projects")), "stats_cache": str(cache_path), **options}, ZoneInfo("UTC"))

    def test_counts_tokens_once_per_reply_and_skips_copies(self):
        log = (line(type="user", uuid="u1", timestamp="2026-10-07T09:00:00Z", sessionId="s1", message={"content": "hi"})
               + reply("a1", "m1", "2026-10-07T09:00:05Z")
               + reply("a2", "m1", "2026-10-07T09:00:06Z")    # same reply streamed over two lines
               + reply("a3", "m2", "2026-10-07T11:30:00Z", side=True, usage=(1, 1, 1, 1)))  # subagent
        out = self.run_on({"projects/p/s1.jsonl": log, "projects/p/s1-resumed.jsonl": log})  # a resume copies earlier lines
        self.assertEqual(out["rows"], [{"d": "2026-10-07", "src": "claude-code", "model": "claude-opus-5-5",
                                        "in": 11, "out": 21, "cr": 301, "cw": 41, "sessions": 1}])
        # prompt + one main-thread reply, both at 09:00 on a Wednesday (weekday 2)
        self.assertEqual(out["punch"][2][9], 2)
        self.assertEqual(sum(map(sum, out["punch"])), 2)
        self.assertEqual(out["longest_session"], {"src": "claude-code", "ms": 6000, "start": "2026-10-07"})

    def test_ignores_tool_results_meta_and_partial_lines(self):
        log = (line(type="user", uuid="u1", timestamp="2026-10-07T09:00:00Z", sessionId="s1",
                    message={"content": [{"type": "tool_result", "content": "x"}]})
               + line(type="user", uuid="u2", timestamp="2026-10-07T09:00:00Z", sessionId="s1", isMeta=True, message={"content": "x"})
               + reply("a1", "m1", "2026-10-07T09:00:05Z", model="<synthetic>")
               + '{"type":"assistant","uuid":"a9"')
        out = self.run_on({"projects/p/s1.jsonl": log})
        self.assertEqual(out["rows"], [])
        self.assertIsNone(out["punch"])

    def test_days_in_the_stats_cache_take_its_numbers(self):
        log = (line(type="user", uuid="u1", timestamp="2026-10-07T09:00:00Z", sessionId="s1", message={"content": "hi"})
               + reply("a1", "m1", "2026-10-07T09:00:05Z", usage=(1, 2, 6, 1), cw1h=1)
               + reply("a2", "m2", "2026-10-08T09:00:05Z", usage=(5, 5, 5, 5)))
        cache = {"lastComputedDate": "2026-10-07",
                 "dailyActivity": [{"date": "2026-02-20", "messageCount": 6, "sessionCount": 2},
                                   {"date": "2026-02-21", "messageCount": 9, "sessionCount": 1},
                                   {"date": "2026-10-07", "messageCount": 40, "sessionCount": 3}],
                 "dailyModelTokens": [{"date": "2026-02-21", "tokensByModel": {"claude-old": 1000}},
                                      {"date": "2026-10-07", "tokensByModel": {"claude-opus-5-5": 200, "claude-haiku": 7}}],
                 "modelUsage": {"claude-old": {"inputTokens": 1, "outputTokens": 1, "cacheReadInputTokens": 8,
                                               "cacheCreationInputTokens": 0}},
                 "longestSession": {"duration": 7200000, "timestamp": "2026-02-21T10:00:00Z"}}
        out = self.run_on({"projects/p/s1.jsonl": log}, cache, unrecorded_model="claude-opus-4-6")
        rows = {(r["d"], r["model"]): r for r in out["rows"]}
        tok = lambda r: r["in"] + r["out"] + r["cr"] + r["cw"]
        # activity without any token record goes under the configured model
        self.assertEqual(rows[("2026-02-20", "claude-opus-4-6")], {"d": "2026-02-20", "src": "claude-code", "model": "claude-opus-4-6",
                                                                  "in": 0, "out": 0, "cr": 0, "cw": 0, "sessions": 2, "messages": 6})
        # logs gone for February: the model's all-time mix splits the cached total
        self.assertEqual(rows[("2026-02-21", "claude-old")], {"d": "2026-02-21", "src": "claude-code", "model": "claude-old",
                                                             "in": 100, "out": 100, "cr": 800, "cw": 0, "sessions": 1, "messages": 9})
        # logged day: cached total in the logged proportions; messages and sessions go to the busiest model
        opus = rows[("2026-10-07", "claude-opus-5-5")]
        self.assertEqual((tok(opus), opus["in"], opus["out"], opus["cr"], opus["cw"], opus["cw1h"]), (200, 20, 40, 120, 20, 20))
        self.assertEqual((opus["sessions"], opus["messages"]), (3, 40))
        self.assertEqual(tok(rows[("2026-10-07", "claude-haiku")]), 7)
        self.assertNotIn("sessions", rows[("2026-10-07", "claude-haiku")])
        # after the cache: counted from the logs
        self.assertEqual(tok(rows[("2026-10-08", "claude-opus-5-5")]), 20)
        self.assertEqual(out["longest_session"], {"src": "claude-code", "ms": 7200000, "start": "2026-02-21"})
        self.assertEqual(out["complete_through"], "2026-10-07")


if __name__ == "__main__":
    unittest.main()
