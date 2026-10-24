"""Notion storage for tokenboard.

Two databases hold the data:
- usage: one page per day, source and model, titled "date|source|model", with the token counts as numbers
- settings: one page per key (sources, prices, quotas, punch, ...), the value stored as JSON text

The collector upserts into them; the Worker in src/worker.js reads them back. Rows that the collector no
longer sees (for example days whose local logs were cleaned up) are left alone, so Notion keeps the history.

    python3 collector/sinks/notion.py init PARENT_PAGE_ID   # create both databases under a page
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
TEXT_CHUNK = 2000            # Notion caps one rich-text item at 2000 characters
WRITE_PAUSE = 0.34           # stay under the API's average limit of three requests per second
NUMBERS = (("in", "Input"), ("out", "Output"), ("cr", "Cache read"), ("cw", "Cache write"),
           ("sessions", "Sessions"), ("requests", "Requests"), ("cost", "Cost"))
SETTINGS = ("generated", "timezone", "currency", "sources", "prices", "quotas", "longest_session", "punch")


def call(token, method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Notion-Version": VERSION,
                                          "Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and attempt < 4:
                time.sleep(float(e.headers.get("Retry-After") or 2 ** attempt))
                continue
            raise RuntimeError(f"Notion {method} {path}: {e.code} {e.read().decode(errors='replace')[:300]}") from None
    raise RuntimeError("unreachable")


def query_all(token, database_id):
    pages, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = call(token, "POST", f"/databases/{database_id}/query", body)
        pages += res["results"]
        if not res.get("has_more"):
            return pages
        cursor = res["next_cursor"]


def plain(rich):
    return "".join(t.get("plain_text", "") for t in rich or [])


def chunks(text):
    return [{"type": "text", "text": {"content": text[i:i + TEXT_CHUNK]}} for i in range(0, len(text), TEXT_CHUNK)] or []


def row_key(row):
    return f'{row["d"]}|{row["src"]}|{row["model"]}'


def row_props(row):
    props = {"Key": {"title": chunks(row_key(row))},
             "Date": {"date": {"start": row["d"]}},
             "Source": {"select": {"name": row["src"]}},
             "Model": {"rich_text": chunks(row["model"])}}
    for key, name in NUMBERS:
        props[name] = {"number": row.get(key)}
    return props


def page_row(page):
    """Turns a usage page back into a row; also used by tests to check round trips."""
    p = page["properties"]
    key = plain(p["Key"]["title"])
    d, src, model = key.split("|", 2)
    row = {"d": d, "src": src, "model": model}
    for k, name in NUMBERS:
        v = p.get(name, {}).get("number")
        if v is not None:
            row[k] = int(v) if k != "cost" and float(v).is_integer() else v
    return row


def comparable(row):
    """Values as Notion will store them, so unchanged rows can be skipped."""
    return tuple(row.get(k) if row.get(k) is not None else None for k, _ in NUMBERS)


def push(data, options, log=print):
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        sys.exit("NOTION_TOKEN is not set; create an internal integration and export its token")
    usage_db, settings_db = options["usage_database"], options["settings_database"]

    existing = {}
    for page in query_all(token, usage_db):
        try:
            existing[plain(page["properties"]["Key"]["title"])] = (page["id"], comparable(page_row(page)))
        except (KeyError, ValueError):
            continue  # a row someone typed by hand; leave it
    created = updated = 0
    for row in data["rows"]:
        key = row_key(row)
        if key in existing:
            page_id, before = existing[key]
            if before == comparable(row):
                continue
            call(token, "PATCH", f"/pages/{page_id}", {"properties": row_props(row)})
            updated += 1
        else:
            call(token, "POST", "/pages", {"parent": {"database_id": usage_db}, "properties": row_props(row)})
            created += 1
        time.sleep(WRITE_PAUSE)

    settings = {plain(p["properties"]["Key"]["title"]): (p["id"], plain(p["properties"]["Value"]["rich_text"]))
                for p in query_all(token, settings_db)}
    if "sources" in settings:  # keep sources other collectors registered earlier
        try:
            known = {s["id"]: s for s in json.loads(settings["sources"][1])}
            known.update({s["id"]: s for s in data["sources"]})
            data = {**data, "sources": list(known.values())}
        except (ValueError, KeyError):
            pass
    for key in SETTINGS:
        value = json.dumps(data.get(key), ensure_ascii=False, separators=(",", ":"))
        props = {"Key": {"title": chunks(key)}, "Value": {"rich_text": chunks(value)}}
        if key in settings:
            if settings[key][1] == value:
                continue
            call(token, "PATCH", f"/pages/{settings[key][0]}", {"properties": props})
        else:
            call(token, "POST", "/pages", {"parent": {"database_id": settings_db}, "properties": props})
        time.sleep(WRITE_PAUSE)
    log(f"notion: {created} rows created, {updated} updated, {len(data['rows']) - created - updated} unchanged")


def init(parent_page_id):
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        sys.exit("NOTION_TOKEN is not set")
    num = {"number": {"format": "number"}}
    usage = call(token, "POST", "/databases", {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": "tokenboard usage"}}],
        "properties": {"Key": {"title": {}}, "Date": {"date": {}}, "Source": {"select": {}}, "Model": {"rich_text": {}},
                       "Input": num, "Output": num, "Cache read": num, "Cache write": num, "Sessions": num,
                       "Requests": num, "Cost": {"number": {"format": "dollar"}}}})
    settings = call(token, "POST", "/databases", {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": "tokenboard settings"}}],
        "properties": {"Key": {"title": {}}, "Value": {"rich_text": {}}}})
    print(json.dumps({"usage_database": usage["id"], "settings_database": settings["id"]}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "init":
        init(sys.argv[2])
    else:
        sys.exit(__doc__)
