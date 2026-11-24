import json, re, glob, statistics as st, pandas as pd, sys
raw = json.load(open("raw.json", encoding="utf-8")); D = sys.argv[1]; o = {}
mean = lambda xs: round(sum(xs) / len(xs), 1)
rain = {int(y): v[0] for y, v in raw["rain"].items() if v[1] >= 11}
o["rain"] = sorted(rain.items())
flow = {int(y): v[0] for y, v in raw["flow"].items() if v[1] >= 12}
o["flow"] = sorted(flow.items())
cer = raw["crops"]["Céréales"]
o["cereals"] = [(int(k[-4:]), round(v / 1e6, 2)) for k, v in sorted(cer.items())]
# unemployment quarterly -> chronological
def chron(d): return sorted(((int(k[3:]) + (int(k[1]) - 1) / 4, v) for k, v in d.items() if v is not None))
o["unemp"] = {k: chron(v) for k, v in raw["unemp_q"].items()}
o["region"] = [(r[1], float(r[2]), float(r[3])) for r in raw["region_unemp"] if r[0] == "National" and r[1] != "Ensemble"]
wom = {r[1]: float(r[2]) for r in raw["region_unemp_women"] if r[0] == "National"}
o["region"] = [(n, t, old, wom.get(n)) for n, t, old in o["region"]]
prov = [(r[1], float(r[2])) for r in raw["prov_unemp"] if r[0] == "National" and re.match(r"^[\d.]+$", r[2])]
prov.sort(key=lambda x: -x[1]); o["prov_n"] = len(prov); o["prov_top"] = prov[:8]; o["prov_bottom"] = prov[-8:]
# CPI yoy
M = {"Janv": 1, "Févr": 2, "Mars": 3, "Avr": 4, "Mai": 5, "Juin": 6, "Juill": 7, "Août": 8, "Sept": 9, "Oct": 10, "Nov": 11, "Déc": 12}
def cpi(name):
    s = {(int(k.split("-")[1]), M[k.split("-")[0]]): v for k, v in raw["cpi"][name].items()}
    return [(y + (m - 1) / 12, round((v / s[(y - 1, m)] - 1) * 100, 1)) for (y, m), v in sorted(s.items()) if (y - 1, m) in s]
o["infl"] = cpi("(GR) GENERAL"); o["infl_food"] = cpi("(01) PRODUITS ALIMENTAIRES ET BOISSONS NON ALCOOLISÉES")
lvl = lambda n: raw["cpi"][n]
o["cpi_since2017"] = {n: lvl(n)["Août-2026"] for n in raw["cpi"]}
o["amo"] = sorted((int(k), v) for k, v in raw["amo"].items())
o["mobile"] = [(int(y), round(v[1] * 100, 1)) for y, v in sorted(raw["mobile"].items())]
o["internet"] = [(int(y), round(v[1] * 100, 1)) for y, v in sorted(raw["internet"].items()) if v[1]]
o["ftth"] = [(int(y), v[4]) for y, v in sorted(raw["internet"].items()) if v[4]]
o["roads"] = sorted((int(y), v["Tués"][2], v["Total Accidents"][2], v["Tués"][0], v["Tués"][1]) for y, v in raw["roads"].items())
# courts: re-read with sections
sec = {"القضايا المسجلة": "registered", "القضايا الرائجة": "workload", "القضايا المحكومة": "judged"}
courts = {}
for f in sorted(glob.glob(D + "/ministere-de-la-justice-et-des-libertes/evolution-des-affaires-au-cours-du-quinq*/*.xlsx")):
    df = pd.read_excel(f, header=None).dropna(how="all").dropna(axis=1, how="all")
    yrs = df.iloc[1, 1:].tolist(); cur = None
    for _, r in df.iloc[2:].iterrows():
        lab = str(r.iloc[0]).strip()
        if lab in sec: cur = sec[lab]; key = cur
        elif cur: key = cur + "|" + lab
        else: continue
        courts.setdefault(key, {}).update({int(y): float(v) for y, v in zip(yrs, r.iloc[1:]) if pd.notna(y) and pd.notna(v)})
o["courts_keys"] = list(courts)
o["courts"] = {k: sorted(v.items()) for k, v in courts.items() if "|" not in k or "الاستئناف العادية" in k}
o["corr"] = raw["cpi_corr"]
json.dump(o, open("site_data.json", "w", encoding="utf-8"), ensure_ascii=False)
# findings
r = dict(o["rain"]); f_ = dict(o["flow"])
print("rain 1969-1999", mean([v for y, v in r.items() if y <= 1999]), "| 2000-2014", mean([v for y, v in r.items() if 2000 <= y <= 2014]), "| 2015-2024", mean([v for y, v in r.items() if y >= 2015]), "| last", o["rain"][-6:])
print("flow 1971-1999", round(st.mean([v for y, v in f_.items() if y <= 1999]), 2), "| 2000-2014", round(st.mean([v for y, v in f_.items() if 2000 <= y <= 2014]), 2), "| 2015+", round(st.mean([v for y, v in f_.items() if y >= 2015]), 2), "| last", o["flow"][-8:])
print("cereals", o["cereals"])
for k in ["total", "youth", "youth_women", "women", "men", "no_degree", "higher_degree"]: print(k, o["unemp"][k][0], o["unemp"][k][-1], "max", max(o["unemp"][k], key=lambda x: x[1]))
print("region", o["region"]); print("prov", o["prov_n"], o["prov_top"], o["prov_bottom"])
print("infl max", max(o["infl"], key=lambda x: x[1]), "food max", max(o["infl_food"], key=lambda x: x[1]), "last", o["infl"][-3:], o["infl_food"][-3:])
print("since2017", o["cpi_since2017"])
print("mobile", o["mobile"][-1], "internet", o["internet"][0], o["internet"][-1], "ftth", o["ftth"][-1])
print("roads", o["roads"]); print("courts keys", o["courts_keys"]); print({k: v[-1] for k, v in o["courts"].items()}, o["courts"].get("registered|محاكم الاستئناف العادية"))
