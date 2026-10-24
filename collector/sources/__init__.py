"""Source adapters. Each adapter module exposes:

    SOURCE = {"id": ..., "name": ..., "kind": "logs" | "billing"}
    def collect(options: dict, tz: ZoneInfo) -> dict

collect() returns {"rows": [...], "punch": 7x24 list or None, "longest_session": {...} or None}.
Rows follow docs/data-format.md. Register new adapters in ADAPTERS below.
"""
from . import claude_code

ADAPTERS = {
    claude_code.SOURCE["id"]: claude_code,
}
