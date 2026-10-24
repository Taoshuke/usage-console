# Data format

The page reads `data/usage.json` next to `index.html`. Version 1:

```jsonc
{
  "version": 1,
  "generated": "2026-10-24T08:30:00-07:00",   // ISO time with offset
  "timezone": "America/Los_Angeles",          // IANA zone used to split days and hours
  "currency": "USD",
  "demo": false,                              // true shows the sample-data notice
  "sources": [{ "id": "claude-code", "name": "Claude Code", "kind": "logs" }],   // kind: logs | billing
  "prices": {                                 // USD per million tokens: input, output, cache read, 5-minute cache write,
    "verified": false,                        //   and optionally 1-hour cache write; false shows the "placeholder prices" notice
    "per_mtok": { "claude-opus-5-5": [4, 20, 0.2, 5, 8] }
  },
  "rows": [
    { "d": "2026-10-07", "src": "claude-code", "model": "claude-opus-5-5",
      "in": 90000, "out": 1100000, "cr": 260000000, "cw": 6000000,
      "cw1h": 4000000,        // optional: the part of cw written to the 1-hour cache (priced at the fifth price)
      "sessions": 4,          // optional: sessions that started that day with this model
      "messages": 310,        // optional: messages that day
      "requests": 0,          // optional: API requests (billing sources)
      "cost": 12.34 }         // optional: actual billed amount; when absent, cost is estimated from prices
  ],
  "quotas": [                 // optional usage limits
    { "src": "claude-code", "name": "Max plan", "window": "7d", "used": 0.68, "resets": "2026-10-27T09:00:00-07:00" }
  ],
  "punch": { "claude-code": [[0, 0, "... 24 hourly counts ..."], "... 7 rows, Monday first ..."] },
  "longest_session": { "src": "claude-code", "ms": 20520000, "start": "2026-10-07" },
  "complete": { "claude-code": "2026-10-23" }   // optional: per source, rows through this day are the full record
}
```

One row is one day, one source, one model. Token fields are integers; omit or zero what a source does not have.
`window` values `5h` and `7d` get translated labels; any other string is shown as is.

## Writing an adapter

Create `collector/sources/<name>.py`:

```python
SOURCE = {"id": "my-tool", "name": "My Tool", "kind": "logs"}

def collect(options, tz):
    # options: this source's object from tokenboard.config.json; tz: a ZoneInfo
    return {"rows": [...], "punch": None, "longest_session": None}
```

Register it in `collector/sources/__init__.py`, enable it under `"sources"` in your config, and add a test in `tests/`.
