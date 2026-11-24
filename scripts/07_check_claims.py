"""Check that the numbers quoted in the page text still match the data.

Usage: python scripts/07_check_claims.py [data/morocco_by_the_numbers.json]
Prints one line per claim and exits with status 1 if any claim no longer holds.
Each claim mirrors a sentence in scripts/template.html; update both together.
"""
import json, sys

d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "data/morocco_by_the_numbers.json", encoding="utf-8"))
by = lambda series: {round(x, 3): y for x, y in series}
avg = lambda xs: sum(xs) / len(xs)
yearly = lambda s, y: avg([v for x, v in s if int(x) == y])
results = []

def claim(text, value, expected, tol):
    ok = abs(value - expected) <= tol
    results.append(ok)
    print(("OK   " if ok else "FAIL ") + f"{text}: data {value:.2f}, text {expected}")

flow, rain = dict(d["flow"]), dict(d["rain"])
claim("Souss flow 1971-1999 average (m3/s)", avg([v for y, v in flow.items() if y <= 1999]), 6.6, 0.05)
claim("Souss flow since 2015 average (m3/s)", avg([v for y, v in flow.items() if y >= 2015]), 1.4, 0.05)
claim("Rainfall change 1969-1999 vs 2015+ (%)", (avg([v for y, v in rain.items() if y >= 2015]) / avg([v for y, v in rain.items() if y <= 1999]) - 1) * 100, -20, 3)
cer = dict(d["cereals"])
claim("Poor harvests under 6 Mt, last 12 seasons", sum(v < 6 for v in list(cer.values())[-12:]), 5, 0)
claim("Youth unemployment 2017 average (%)", yearly(d["u_youth"], 2017), 27, 0.5)
claim("Youth unemployment 2025 average (%)", yearly(d["u_youth"], 2025), 37, 0.5)
claim("Young women unemployment 2025 average (%)", yearly(d["u_youth_w"], 2025), 53, 0.5)
claim("National unemployment 2025 average (%)", yearly(d["u_total"], 2025), 13.0, 0.05)
claim("Higher-degree unemployment Q4 2025 (%)", by(d["u_high"])[2025.75], 25.7, 0.05)
claim("No-diploma unemployment Q4 2025 (%)", by(d["u_none"])[2025.75], 4.2, 0.05)
reg = {r[0]: r for r in d["region"]}
claim("Southern regions unemployment 2025 (%)", reg["Régions du Sud"][1], 22.8, 0.05)
claim("Southern regions women unemployment 2025 (%)", reg["Régions du Sud"][3], 53.5, 0.05)
claim("Marrakech-Safi unemployment 2025 (%)", reg["Marrakech-safi"][1], 8.1, 0.05)
claim("Food inflation Aug 2026 (%)", d["infl_food"][-1][1], -4.2, 0.05)
claim("AMO coverage 2024 (%)", dict(d["amo"])[2024], 77.1, 0.05)
claim("Internet per 100 people 2025", dict(d["internet"])[2025], 113, 0.5)
claim("Mobile lines per 100 people 2025", dict(d["mobile"])[2025], 161, 0.5)
roads = {r[0]: r for r in d["roads"]}
claim("Road deaths 2024", roads[2024][1], 4024, 0)
claim("Road deaths change 2022-2024 (%)", (roads[2024][1] / roads[2022][1] - 1) * 100, 15, 0.5)
app = dict(d["appeal"])
claim("Appeal court cases change 2021-2025 (%)", (app[2025] / app[2021] - 1) * 100, 63, 0.6)
corr = {r[0]: r for r in d["corr"]}
claim("Corruption rank change 2018-2024 (places)", corr[2024][2] - corr[2018][2], 26, 0)
claim("Credit growth latest (%)", d["credit"][-1][1], 11.0, 0.05)
claim("Fund assets growth since Jan 2020 (%)", (d["funds"][-1][1] / d["funds"][0][1] - 1) * 100, 77, 0.6)
claim("Startups (unique companies)", d["startup_n"], 802, 0)
claim("Pension contributors per pensioner, latest", d["pension_ratio"][-1][1], 4.8, 0.05)
claim("Parliamentary questions (unique)", d["parl_total"], 67114, 0)
svc = {r[0]: r for r in d["services"]}
claim("Health centres per 100k, Casablanca-Settat", svc["Casablanca-Settat"][1], 4.9, 0.05)
claim("Health centres per 100k, Guelmim-Oued Noun", svc["Guelmim-Oued Noun"][1], 22, 0.5)
claim("Health centres and dispensaries (total)", d["services_totals"]["primary_care"], 3086, 0)

af = {k: dict(v) for k, v in d["amo_finance"].items()}
claim("AMO benefits paid 2012 (bn)", af["benefits_paid"][2012], 5.1, 0.05)
claim("AMO benefits paid 2024 (bn)", af["benefits_paid"][2024], 27.2, 0.05)
claim("AMO income 2024 (bn)", af["resources"][2024], 46.1, 0.05)
claim("AMO spending 2024 (bn)", af["expenses"][2024], 40.9, 0.05)
claim("Years AMO spending exceeded income", sum(af["expenses"][y] > af["resources"][y] for y in af["resources"]), 1, 0)
pm = {k: dict(v) for k, v in d["pension_money"].items()}
claim("Pension contributions 2024 (bn)", pm["contributions"][2024], 73.0, 0.05)
claim("Pensions paid 2024 (bn)", pm["benefits"][2024], 78.7, 0.05)
claim("First year of a run of deficits to today", min(y for y in pm["benefits"] if all(pm["benefits"][z] > pm["contributions"][z] for z in pm["benefits"] if z >= y)), 2017, 0)
claim("Pension reserves peak (bn)", max(pm["reserves"].values()), 270.9, 0.05)
claim("Pension reserves 2024 (bn)", pm["reserves"][2024], 264.9, 0.05)
vh = {k: dict(v) for k, v in d["vehicles"].items()}
claim("Vehicles 2023 (millions)", vh["Total"][2023] / 1e6, 4.5, 0.05)
claim("Vehicles 2012 (millions)", vh["Total"][2012] / 1e6, 3.1, 0.05)
claim("Motorcycles 2023", vh["Motocyclettes"][2023], 312000, 500)
claim("Deaths per 10,000 vehicles 2021", roads[2021][1] / vh["Total"][2021] * 1e4, 9.1, 0.05)
claim("Deaths per 10,000 vehicles 2023", roads[2023][1] / vh["Total"][2023] * 1e4, 8.5, 0.05)

failed = results.count(False)
print(f"\n{len(results) - failed}/{len(results)} claims hold")
sys.exit(1 if failed else 0)
