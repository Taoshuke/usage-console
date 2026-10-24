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


def reply(uuid, mid, ts, model="claude-opus-5-5", sid="s1", side=False, usage=(10, 20, 300, 40)):
    u = dict(zip(("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"), usage))
    return line(type="assistant", uuid=uuid, timestamp=ts, sessionId=sid, isSidechain=side,
                message={"id": mid, "model": model, "usage": u})


class ClaudeCodeTest(unittest.TestCase):
    def run_on(self, files):
        with tempfile.TemporaryDirectory() as root:
            for name, text in files.items():
                p = Path(root, name)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            return claude_code.collect({"path": root}, ZoneInfo("UTC"))

    def test_counts_tokens_once_per_reply_and_skips_copies(self):
        log = (line(type="user", uuid="u1", timestamp="2026-10-07T09:00:00Z", sessionId="s1", message={"content": "hi"})
               + reply("a1", "m1", "2026-10-07T09:00:05Z")
               + reply("a2", "m1", "2026-10-07T09:00:06Z")    # same reply streamed over two lines
               + reply("a3", "m2", "2026-10-07T11:30:00Z", side=True, usage=(1, 1, 1, 1)))  # subagent
        out = self.run_on({"p/s1.jsonl": log, "p/s1-resumed.jsonl": log})  # a resume copies earlier lines
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
        out = self.run_on({"p/s1.jsonl": log})
        self.assertEqual(out["rows"], [])
        self.assertIsNone(out["punch"])


if __name__ == "__main__":
    unittest.main()
