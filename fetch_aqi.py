import json, os, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

RESOURCE = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
KEY = os.environ.get("DATA_GOV_KEY", "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b")
FOCUS_CITIES = ["Nashik", "Pune"]
WHO_LIMITS = {"PM2.5": 15, "PM10": 45}

BASE = f"https://api.data.gov.in/resource/{RESOURCE}"

def try_url(url, headers):
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.load(r)
            return data.get("records", [])
    except urllib.error.HTTPError as e:
        print(f"  -> HTTP {e.code}: {e.read()[:120]}")
    except Exception as e:
        print(f"  -> {e}")
    return None

def fetch(field, value, limit=10):
    v = urllib.parse.quote(value)
    formats = [
        ("encoded brackets, key in query",
         f"{BASE}?api-key={KEY}&format=json&limit={limit}&filters%5B{field}%5D={v}",
         {"User-Agent": "Mozilla/5.0"}),
        ("plain brackets, key in query",
         f"{BASE}?api-key={KEY}&format=json&limit={limit}&filters[{field}]={v}",
         {"User-Agent": "Mozilla/5.0"}),
        ("no filter, key in query",
         f"{BASE}?api-key={KEY}&format=json&limit=500",
         {"User-Agent": "Mozilla/5.0"}),
    ]
    for name, url, hdrs in formats:
        print(f"{value}: trying [{name}]")
        recs = try_url(url, hdrs)
        if recs:
            print(f"  -> SUCCESS with [{name}], {len(recs)} records")
            if name.startswith("no filter"):
                recs = [r for r in recs if r.get("city", "").lower() == value.lower()] or recs
            return recs
        time.sleep(10)
    return []

records = []
seen_all = None
for c in FOCUS_CITIES:
    recs = fetch("city", c)
    records += recs

state_recs = fetch("state", "Maharashtra", limit=500)
records += state_recs

if not records:
    print("No data at all today; exiting gracefully.")
    raise SystemExit(0)

cities = {}
for rec in records:
    city = rec.get("city", "")
    pol = rec.get("pollutant_id", "")
    try:
        val = float(rec.get("pollutant_avg") or rec.get("avg_value"))
    except (TypeError, ValueError):
        continue
    if val <= 0 or val > 1500:
        continue
    cities.setdefault(city, {}).setdefault(pol, []).append(val)

report = {c: {p: round(sum(v)/len(v), 1) for p, v in pols.items()} for c, pols in cities.items()}

ist = timezone(timedelta(hours=5, minutes=30))
today = datetime.now(ist).strftime("%Y-%m-%d")
ranking = sorted(((c, d["PM2.5"]) for c, d in report.items() if "PM2.5" in d), key=lambda x: -x[1])

lines = [f"# Air Report - {today}", ""]
for name in FOCUS_CITIES:
    d = report.get(name)
    if not d:
        lines.append(f"## {name}: no data reported today\n")
        continue
    lines.append(f"## {name}")
    for p, v in sorted(d.items()):
        limit = WHO_LIMITS.get(p)
        if limit:
            flag = "BREACH" if v > limit else "ok"
            lines.append(f"- {p}: {v} ug/m3 = {round(v/limit,1)}x WHO limit [{flag}]")
        else:
            lines.append(f"- {p}: {v}")
    lines.append("")

if len(ranking) > 2:
    lines.append("## Worst PM2.5 in Maharashtra today")
    for i, (c, v) in enumerate(ranking[:10], 1):
        lines.append(f"{i}. {c}: {v} ug/m3")

os.makedirs("reports", exist_ok=True)
with open(f"reports/{today}.md", "w") as f:
    f.write("\n".join(lines))
with open("latest.json", "w") as f:
    json.dump({"date": today, "cities": report, "ranking": ranking[:10]}, f, indent=2)

print("\n".join(lines))
