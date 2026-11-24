"""Extract economy, pensions, funds, startups and parliament data -> raw2.json. Usage: python 02b_extract_more.py <datasets dir>"""
import glob, os, re, json, sys, warnings, collections
import pandas as pd
warnings.filterwarnings("ignore")
D = sys.argv[1]; o = {}
g = lambda p: sorted(f for f in glob.glob(os.path.join(D, p)) if not f.endswith("metadata.json") and "metadata.xlsx" not in f)

# GDP volume quarterly (chained, SA) -> yoy growth
df = pd.read_excel(g("haut-commissariat-au-plan/data_i4276/*_data.xlsx")[0], header=None)
q = dict(zip(df.iloc[1, 1:], df.iloc[2, 1:]))
key = lambda s: (int(s[3:]), int(s[1]))
qs = {key(k): float(v) for k, v in q.items() if isinstance(k, str) and re.match(r"T\d-\d{4}", k)}
o["gdp_growth"] = [[y + (t - 1) / 4, round((v / qs[(y - 1, t)] - 1) * 100, 1)] for (y, t), v in sorted(qs.items()) if (y - 1, t) in qs]

# Bank credit to the economy (monthly, latest file)
f = [x for x in g("bank-al-maghrib/creances-sur-l-economie*/*.xlsx") if "2026" in x][0]
df = pd.read_excel(f, header=None)
dates = pd.to_datetime(df.iloc[2, 1:], errors="coerce")
row = df[df[0].astype(str).str.strip() == "Crédits des"].iloc[0, 1:]
s = pd.Series(row.values.astype(float), index=dates).dropna()
s = s[~s.index.isna()]; s = s.groupby([s.index.year, s.index.month]).last()
o["credit"] = [[y + (m - 1) / 12, round((v / s[(y - 1, m)] - 1) * 100, 1), round(v / 1000)] for (y, m), v in s.items() if (y - 1, m) in s.index]

# Pension demographic ratio
df = pd.read_excel(g("autorite-de-controle-des-assurances-et-de-la-prevoyance-sociale/rapport-demographique*/*.xlsx")[0], header=None)
o["pension_ratio"] = [[int(y), round(float(v), 2)] for y, v in zip(df.iloc[0, 1:], df.iloc[1, 1:]) if pd.notna(y) and pd.notna(v)]

# AMMC weekly fund assets: total net assets per file
funds = []
for f in g("ammc/stat-hebdo-opcvm-*/*.xls*"):
    try:
        x = pd.read_excel(f, header=None, sheet_name=0)
    except Exception as e:
        continue
    m = re.search(r"(\d{2})[-_.](\d{2})[-_.](\d{4})", os.path.basename(f))
    if not m: continue
    d = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    tot = None
    for _, r in x.iterrows():
        cells = [str(c).strip() for c in r.values]
        if any(c.lower().startswith("total") for c in cells):
            nums = [c for c in r.values if isinstance(c, (int, float)) and not pd.isna(c) and c > 1e9]
            if nums: tot = float(nums[0]); break
    if tot: funds.append([d, round(tot / 1e9, 1)])
o["funds"] = sorted(funds); o["funds_files"] = len(g("ammc/stat-hebdo-opcvm-*/*.xls*"))

# ACAPS year-by-row tables: {row label: {year: value}} in million dirhams
def acaps(pattern):
    df = pd.read_excel(g("autorite-de-controle-des-assurances-et-de-la-prevoyance-sociale/" + pattern)[0], header=None)
    years = [int(y) if pd.notna(y) else None for y in df.iloc[0, 1:]]
    out = {}
    for _, r in df.iloc[1:].iterrows():
        lab = str(r.iloc[0]).strip()
        if lab and lab != "nan":
            out[lab] = {y: float(v) for y, v in zip(years, r.iloc[1:]) if y and pd.notna(v) and isinstance(v, (int, float))}
    return out
amo_in, amo_out = acaps("ressources-des-regimes-amo/*.xlsx"), acaps("depenses-des-regimes-amo/*.xlsx")
o["amo_finance"] = {"resources": amo_in["TOTAL"], "expenses": amo_out["TOTAL"],
                    "contributions": amo_in["Cotisations"], "benefits_paid": amo_out["Prestations et frais payés"]}
o["pension_money"] = {"contributions": acaps("cotisations-des-regimes-de-retraite/*.xlsx")["Régimes de base"],
                      "benefits": acaps("prestations-des-regimes-de-retraite/*.xlsx")["Régimes de base"],
                      "reserves": acaps("reserves-des-regimes-de-retraite/*.xlsx")["Régimes de base"]}

# Vehicles in circulation (NARSA, latest yearly file, sheet "3-4")
vf = sorted(g("narsa/statistiques-des-immatriculations-et-permis-de-conduire-delivres*/*.xls*"))[-1]
df = pd.read_excel(vf, sheet_name="3-4", header=None)
hdr = next(i for i in range(len(df)) if str(df.iloc[i, 0]).strip().startswith("Au 31"))
yrs = [int(float(y)) for y in df.iloc[hdr, 1:7] if pd.notna(y)]
veh = {}
for _, r in df.iloc[hdr + 1: hdr + 5].iterrows():
    veh[str(r.iloc[0]).strip()] = {y: float(v) for y, v in zip(yrs, r.iloc[1:1 + len(yrs)])}
o["vehicles"] = veh

# Startups (company-level, aggregated by city and sector only)
df = pd.read_excel(g("agence-de-developpement-du-digital/donnees-sur-les-startups/bdd-startups-add_2024.xlsx")[0])
df.columns = [c.strip() for c in df.columns]
# the database merges four overlapping lists: keep one row per company name
df = df.loc[~df["Raison social"].astype(str).str.strip().str.lower().duplicated()]
city = df["City"].astype(str).str.strip().str.lower().str.replace("é", "e")
o["startup_n"] = len(df)
o["startup_city"] = city.value_counts().head(12).to_dict()
o["startup_sector"] = df["Main sector"].astype(str).str.strip().value_counts().head(12).to_dict()

# Parliament questions, aggregated by ministry and year (no names kept)
ministries, years, kinds, seen = {}, {}, {}, set()
for f in g("parlement/liste-des-questions-*/*.xlsx"):
    kind = "oral" if "orales" in f else "written"
    x = pd.read_excel(f); cols = [str(k).strip().lower() for k in x.columns]
    if any("minist" in k for k in cols):
        x.columns = cols; m = next(k for k in cols if "minist" in k); dcol = next(k for k in cols if "date" in k)
        ncol = next((k for k in cols if "num" in k), cols[0])
    else:  # one file ships without a header row
        x = pd.read_excel(f, header=None); m, dcol, ncol = 6, 2, 0
    for n, d, v in zip(x[ncol], x[dcol], x[m]):
        key = (kind, str(n).strip(), str(d)[:10])
        if key in seen: continue  # several files overlap the same sessions
        seen.add(key)
        k = str(v).strip(); ministries[k] = ministries.get(k, 0) + 1
        dt = pd.to_datetime(d, errors="coerce")
        if pd.notna(dt): years[str(dt.year)] = years.get(str(dt.year), 0) + 1
        kinds[kind] = kinds.get(kind, 0) + 1
o["parl_n"] = kinds; o["parl_years"] = years; o["parl_ministries"] = ministries
json.dump(o, open("raw2.json", "w", encoding="utf-8"), ensure_ascii=False)
for k, v in o.items():
    if k == "parl_ministries": continue
    s = json.dumps(v, ensure_ascii=False); print("##", k, s[:700] if len(s) < 700 else s[:350] + " ... " + s[-300:])
