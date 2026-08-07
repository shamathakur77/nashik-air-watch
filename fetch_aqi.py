import json, os, time, urllib.request
from datetime import datetime, timezone, timedelta

RESOURCE = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
KEY = os.environ.get("DATA_GOV_KEY", "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b")
FOCUS_CITIES = ["Nashik", "Pune"]
WHO_LIMITS = {"PM2.5": 15, "PM10": 45}  # WHO 24h guideline, ug/m3

url = (f"https://api.data.gov.in/resource/{RESOURCE}?api-key={KEY}"
       f"&format=json&limit=1000&filters%5Bstate%5D=Maharashtra")

records = []
for attempt in range(5):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            records = json.load(r).get("records", [])
        if records:
            break
    except Exception as e:
        print(f"Attempt {attempt + 1} failed: {e}")
        time.sleep(30)

if not records:
    print("No data received after 5 attempts; skipping today.")
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
        continue  # sensor junk
    cities.setdefault(city, {}).setdefault(pol, []).append(val)

report = {}
for city, pols in cities.items():
    report[city] = {p: round(sum(v) / len(v), 1) for p, v in pols.items()}

ist = timezone(timedelta(hours=5, minutes=30))
today = datetime.now(ist).strftime("%Y-%m-%d")

ranking = sorted(
    [(c, d["PM2.5"]) for c, d in report.items() if "PM2.5" in d],
    key=lambda x: -x[1])

lines = [f"# Maharashtra Air Report - {today}", ""]
for name in FOCUS_CITIES:
    d = report.get(name)
    if not d:
        lines.append(f"## {name}: no data reported today")
        continue
    lines.append(f"## {name}")
    for p, v in sorted(d.items()):
        limit = WHO_LIMITS.get(p)
        if limit:
            times = round(v / limit, 1)
            flag = "BREACH" if v > limit else "ok"
            lines.append(f"- {p}: {v} ug/m3 = {times}x WHO limit [{flag}]")
        else:
            lines.append(f"- {p}: {v}")
    lines.append("")

lines.append("## Worst PM2.5 in Maharashtra today")
for i, (c, v) in enumerate(ranking[:10], 1):
    lines.append(f"{i}. {c}: {v} ug/m3")

os.makedirs("reports", exist_ok=True)
with open(f"reports/{today}.md", "w") as f:
    f.write("\n".join(lines))
with open("latest.json", "w") as f:
    json.dump({"date": today, "cities": report, "ranking": ranking[:10]}, f, indent=2)

print("\n".join(lines))
