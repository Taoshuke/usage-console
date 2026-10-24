import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "collector"))
from sinks import notion  # noqa: E402


def page(pid, props):
    return {"id": pid, "properties": props}


class FakeNotion:
    """Records writes; serves the usage and settings databases from memory."""
    def __init__(self, usage_pages, settings_pages):
        self.db = {"U": usage_pages, "S": settings_pages}
        self.writes = []

    def call(self, token, method, path, body=None):
        self.writes.append((method, path, body))
        return {}

    def query_all(self, token, database_id):
        return self.db[database_id]


ROW = {"d": "2026-10-07", "src": "claude-code", "model": "claude-opus-5-5", "in": 10, "out": 20, "cr": 300, "cw": 40, "sessions": 2}


class NotionSinkTest(unittest.TestCase):
    def run_push(self, fake, rows):
        data = {"rows": rows, "sources": [{"id": "claude-code", "name": "Claude Code", "kind": "logs"}],
                "generated": "g", "timezone": "UTC", "currency": "USD", "prices": {}, "quotas": [], "longest_session": None, "punch": {}}
        with mock.patch.dict(os.environ, {"NOTION_TOKEN": "x"}), mock.patch.object(notion, "call", fake.call), \
                mock.patch.object(notion, "query_all", fake.query_all), mock.patch.object(notion, "WRITE_PAUSE", 0):
            notion.push(data, {"usage_database": "U", "settings_database": "S"}, log=lambda m: None)

    def test_round_trip_and_skip_unchanged(self):
        props = notion.row_props(ROW)
        # Notion hands numbers back as floats and text as rich-text runs
        stored = {k: ({"title": [{"plain_text": props["Key"]["title"][0]["text"]["content"]}]} if k == "Key" else
                      {"number": float(v["number"])} if "number" in v and v["number"] is not None else v)
                  for k, v in props.items()}
        self.assertEqual(notion.page_row(page("p1", stored)), ROW)
        fake = FakeNotion([page("p1", stored)], [])
        self.run_push(fake, [ROW])
        usage_writes = [w for w in fake.writes if w[2] and w[2].get("parent", {}).get("database_id") == "U" or w[1] == "/pages/p1"]
        self.assertEqual(usage_writes, [])

    def test_creates_new_rows_updates_changed_and_keeps_missing(self):
        old = notion.row_props({**ROW, "out": 1})
        stored = {"Key": {"title": [{"plain_text": notion.row_key(ROW)}]}, **{k: v for k, v in old.items() if k != "Key"}}
        gone = {"Key": {"title": [{"plain_text": "2026-01-01|claude-code|x"}]}}
        fake = FakeNotion([page("p1", stored), page("p2", gone)], [])
        new_row = {**ROW, "d": "2026-10-08"}
        self.run_push(fake, [ROW, new_row])
        methods = [(m, p) for m, p, b in fake.writes if p == "/pages/p1" or (b and b.get("parent", {}).get("database_id") == "U")]
        self.assertEqual(methods, [("PATCH", "/pages/p1"), ("POST", "/pages")])
        self.assertFalse(any(p == "/pages/p2" for _, p, _ in fake.writes))


if __name__ == "__main__":
    unittest.main()
