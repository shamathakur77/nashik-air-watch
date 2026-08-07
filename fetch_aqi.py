import json, os, time, urllib.request
from datetime import datetime, timezone, timedelta

RESOURCE = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
KEY = os.environ.get("DATA_GOV_KEY", "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b")
FOCUS_CITIES = ["Nashik", "Pune"]
WHO_LIMITS = {"PM2.5": 15, "PM10": 45}  # WHO 24h guideline, ug/m3

def fetch(filter_field, filter_value, limit=100):
    url = (f"https://api.data.gov.in/resource/{RESOURCE}"
           f"?api-key={KEY}&format=json&limit={limit}"
           f"&filters[{filter_field}]={urllib.parse.quote(filter_value)}")
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "api-key": KEY})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r).get("records", [])
        except urllib.error.HTTPError as e:
            print(f"{filter_value} attempt {attempt+1}: HTTP {e.code} - {e.read()[:200]}")
        except Exception as e:
            print(f"{filter_value} attempt {attempt+1}: {e}")
        time.sleep(20)
    return []

import urllib.parse

records = []
for c in FOCUS_CITIES:
    records += fetch("city", c)

# Maharashtra-wide ranking (best effort; skip silently if the key won't allow it)
state_records = fetch("state", "Maharashtra", limit=500)
records += state_records

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
