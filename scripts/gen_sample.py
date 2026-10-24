# Sample data for the multi-source usage board. Claude Code totals match the user's /stats (2026-10-24);
# every other source is invented and flagged sample in the data itself.
import json, random, datetime as dt
random.seed(11)
cc = json.load(open('sample/claude-code.json'))
rows = []
for day in cc['days']:
    first = True
    for m, p in day['t'].items():
        rows.append({"d": day['d'], "src": "claude-code", "model": m, "in": p[0], "out": p[1], "cr": p[2], "cw": p[3],
                     "sessions": day['s'] if first else 0})
        first = False
D = dt.date
def days(a, b):
    while a <= b:
        yield a; a += dt.timedelta(1)
# Codex CLI (sample): lighter use from mid-September
for d in days(D(2026,9,14), D(2026,10,24)):
    if random.random() < .45: continue
    for m, scale in (("sample-model-a", 1.0), ("sample-model-b", .35)):
        if random.random() < .3: continue
        k = random.lognormvariate(0, .6) * scale
        rows.append({"d": d.isoformat(), "src": "codex", "model": m, "in": int(2.4e6*k), "out": int(3.1e5*k),
                     "cr": int(2.1e7*k), "cw": 0, "sessions": random.randint(1, 4)})
# Anthropic API (sample): billed, actual cost and request counts
for d in days(D(2026,8,20), D(2026,10,24)):
    if random.random() < .2: continue
    for m, scale, price in (("claude-opus-5-5", 1.0, (5, 25)), ("claude-haiku-5-5", 2.5, (1, 5))):
        k = random.lognormvariate(0, .5) * scale
        i, o = int(1.8e6*k), int(2.2e5*k)
        rows.append({"d": d.isoformat(), "src": "anthropic-api", "model": m, "in": i, "out": o, "cr": 0, "cw": 0,
                     "requests": int(140*k), "cost": round(i/1e6*price[0] + o/1e6*price[1], 2)})
hours = {
 "claude-code": cc['hours'],
 "codex": [0,0,0,0,0,0,0,1,3,6,9,8,5,7,9,11,10,8,5,3,2,1,0,0],
 "anthropic-api": [6,5,5,4,4,5,7,9,12,14,15,15,14,15,16,16,15,13,11,10,9,8,7,6],
}
WEEK = {'claude-code': [1.1, 1.15, 1.05, 1.2, .95, .55, .5], 'codex': [1, 1.1, 1, 1, .9, .2, .15],
        'anthropic-api': [1, 1, 1, 1, 1, .8, .8]}
data = {
 "generated": "2026-10-24T09:12:00-05:00", "timezone": "America/Chicago", "currency": "USD",
 "sample": True,
 "sources": [
   {"id": "claude-code", "name": "Claude Code", "kind": "logs", "sample": "daily"},
   {"id": "codex", "name": "Codex CLI", "kind": "logs", "sample": "all"},
   {"id": "anthropic-api", "name": "Anthropic API", "kind": "billing", "sample": "all"},
 ],
 # USD per million tokens: input, output, cache read, cache write. Placeholders until verified.
 "prices": {"verified": False, "per_mtok": {
   "claude-opus-5-5": [5, 25, 0.5, 6.25], "claude-opus-5": [5, 25, 0.5, 6.25],
   "claude-fable-5-1": [3, 15, 0.3, 3.75], "claude-fable-5": [3, 15, 0.3, 3.75],
   "claude-haiku-5-5": [1, 5, 0.1, 1.25], "other": [3, 15, 0.3, 3.75],
   "sample-model-a": [1.25, 10, 0.125, 0], "sample-model-b": [0.25, 2, 0.025, 0]}},
 "quotas": [
   {"name": "Claude Max", "window": "5 小时", "used": 0.34, "resets": "2026-10-24T12:00:00-05:00", "sample": True},
   {"name": "Claude Max", "window": "7 天", "used": 0.71, "resets": "2026-10-27T07:00:00-05:00", "sample": True},
   {"name": "Codex", "window": "7 天", "used": 0.22, "resets": "2026-10-29T00:00:00-05:00", "sample": True},
 ],
 "longest_session": {"src": "claude-code", "ms": cc['longest_session']['ms'], "start": cc['longest_session']['start']},
 # weekday x hour message counts (Mon..Sun rows), scaled from the hourly profile
 "punch": {src: [[round(n * w * random.uniform(.7, 1.3)) for n in arr] for w in wk]
           for src, arr in hours.items() for wk in [WEEK[src]]},
 "rows": rows,
}
json.dump(data, open('sample/usage.json', 'w'), separators=(',', ':'))
print(len(rows), round(len(json.dumps(data))/1024), 'KB')
