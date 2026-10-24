# Builds sample usage data whose all-time totals match the user's /stats screenshot (2026-10-24).
import json, random, datetime as dt
random.seed(7)
D = dt.date
def rng(a, b):
    x = a
    while x <= b:
        yield x; x += dt.timedelta(1)
last = D(2026,10,24)
active = {D(2026,2,21)}
early = list(rng(D(2026,7,29), D(2026,9,21)))
off = set(random.sample(early[2:-2], 12))
# keep any run inside the early block shorter than 21 days
active |= {d for d in early if d not in off}
active |= set(rng(D(2026,9,22), D(2026,10,12)))
active |= set(rng(D(2026,10,14), D(2026,10,18)))
active |= set(rng(D(2026,10,20), D(2026,10,24)))
active.discard(D(2026,9,21))  # break so the 21-day streak stands alone
active.add(D(2026,7,30))
for d in sorted(off):
    if len(active) >= 75: break
    active.add(d)
assert len(active) == 75, len(active)
# per-model totals [input, output, cache_read, cache_write]
M = {
 "claude-opus-5-5":  [146.8e3, 67.9e6, 25.4e9, 505.7e6],
 "claude-opus-5":    [51.5e3, 23.9e6, 8.2e9, 401.8e6],
 "claude-fable-5-1": [4.4e6, 10.9e6, 2.5e9, 115.9e6],
 "claude-fable-5":   [28.1e3, 6.3e6, 1.7e9, 51.1e6],
 "other":            [1.77e6, 1.4e6, 0.48e9, 25.5e6],
}
def win(m, d):
    if m == "claude-opus-5-5":  return d >= D(2026,9,20)
    if m == "claude-opus-5":    return D(2026,8,10) <= d <= D(2026,9,19)
    if m == "claude-fable-5-1": return D(2026,8,28) <= d <= D(2026,9,12) or D(2026,10,15) <= d <= D(2026,10,17)
    if m == "claude-fable-5":   return d <= D(2026,8,24)
    return True
days = sorted(active)
w = {}
for m in M:
    ws = {}
    for d in days:
        if not win(m, d): continue
        base = random.lognormvariate(0, 0.7)
        if m == "claude-opus-5-5" and d == D(2026,10,7): base = 9
        if m == "claude-opus-5-5" and d in (D(2026,9,28), D(2026,9,29), D(2026,9,30), D(2026,10,1)): base *= 2.2
        ws[d] = base
    if m == "other" or not ws:
        ws = {d: random.random() for d in days if d.month == 2 or random.random() < .5}
    w[m] = ws
out = []
for d in days:
    t = {}
    for m, tot in M.items():
        if d in w[m]:
            share = w[m][d] / sum(w[m].values())
            t[m] = [round(v * share) for v in tot]
    out.append({"d": d.isoformat(), "s": 0, "t": t})
# sessions: 482 total, 2 on Feb 21
rest = 480
ws = [random.uniform(2, 12) for _ in out[1:]]
alloc = [max(1, round(rest * x / sum(ws))) for x in ws]
alloc[-1] += rest - sum(alloc)
out[0]["s"] = 2
for o, n in zip(out[1:], alloc): o["s"] = n
hours = [5,10,6,0,0,0,3,9,22,41,58,64,49,61,72,84,93,118,104,87,76,54,31,14]
data = {
 "generated": "2026-10-24T09:12:00-05:00", "timezone": "America/Chicago",
 "first_day": "2026-02-21", "last_day": last.isoformat(),
 "sample": True,
 "longest_session": {"ms": ((60*24+20)*60+49)*60000, "start": "2026-07-31"},
 "days": out, "hours": hours,
}
json.dump(data, open('sample/claude-code.json', 'w'), separators=(',', ':'))
tot = [0]*4
for o in out:
    for v in o["t"].values():
        for i in range(4): tot[i] += v[i]
print(len(out), sum(o["s"] for o in out), [f"{x:.4g}" for x in tot], f"{sum(tot):.4g}")
