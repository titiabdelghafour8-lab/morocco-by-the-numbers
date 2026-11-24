import glob, os, re, json, sys, warnings
import pandas as pd
warnings.filterwarnings("ignore")
D = sys.argv[1]; out = {}
def g(pat): return sorted(f for f in glob.glob(os.path.join(D, pat)) if not f.endswith("metadata.json"))

# --- Rainfall, Youssef Ben Tachfine dam (daily, per hydrological year)
rain = {}
for f in g("agence-du-bassin-hydraulique-de-souss-massa/pluie-journaliere-du-barrage-y*/*.xlsx"):
    df = pd.read_excel(f, header=None)
    yr = None
    for v in df.values.ravel():
        m = re.match(r"\s*(\d{4})\s*/\s*(\d{4})", str(v))
        if m: yr = int(m.group(2)); break
    days = df[pd.to_numeric(df[1], errors="coerce").between(1, 31)]
    vals = days.iloc[:, 2:14].apply(lambda s: pd.to_numeric(s.astype(str).str.replace(",", ".").str.strip(), errors="coerce")).astype(float)
    months_ok = int(vals.notna().any().sum())
    rain[yr] = (round(float(vals.sum().sum()), 1), months_ok)
out["rain"] = rain

# --- River flow, Oued Souss at Ait Melloul (daily mean m3/s)
flow = {}
for f in g("agence-du-bassin-hydraulique-de-souss-massa/debit-moyen-journalier-de-la-station-ait*/*.xlsx"):
    df = pd.read_excel(f, header=None)
    m = re.search(r"(\d{4})\s*-\s*(\d{4})", os.path.basename(f))
    yr = int(m.group(2))
    days = df[pd.to_numeric(df[0], errors="coerce").between(1, 31)]
    vals = days.iloc[:, 1:13].apply(lambda s: pd.to_numeric(s.astype(str).str.replace(",", ".").str.strip(), errors="coerce")).astype(float)
    flow[yr] = (round(float(vals.stack().mean()), 3), int(vals.notna().any().sum()))
out["flow"] = flow

# --- Crop production
f = g("departement-de-l-agriculture/production-vegetale*/*.xlsx")[0]
df = pd.read_excel(f); df.columns = [str(c).strip() for c in df.columns]
out["filieres"] = sorted(df["Filière"].dropna().unique().tolist())
prod = df[df["Indicateur"].str.contains("Production", na=False)]
out["crops"] = {k: v.groupby("Occurrence")["Valeur"].sum().round(0).to_dict() for k, v in prod.groupby("Filière")}

# --- Unemployment
def hcp(code):
    f = g(f"haut-commissariat-au-plan/{code}/*_data.xlsx")[0]
    df = pd.read_excel(f, header=None)
    hdr = df.iloc[1].tolist(); body = df.iloc[2:]
    body.columns = [str(h).replace(".0", "") for h in hdr]
    return body
q = hcp("data_i4252"); qd = hcp("data_i4248")
qcols = [c for c in q.columns if re.match(r"T\d-\d{4}", c)]
def series(body, k1, v1, k2, v2):
    r = body[(body[k1].astype(str).str.strip() == v1) & (body[k2].astype(str).str.strip() == v2)].iloc[0]
    return {c: (None if pd.isna(r[c]) else float(r[c])) for c in qcols}
out["unemp_q"] = {
    "total": series(q, "Tranches d'âge", "Ensemble", "Sexe", "Total"),
    "women": series(q, "Tranches d'âge", "Ensemble", "Sexe", "Féminin"),
    "men": series(q, "Tranches d'âge", "Ensemble", "Sexe", "Masculin"),
    "youth": series(q, "Tranches d'âge", "15 - 24", "Sexe", "Total"),
    "youth_women": series(q, "Tranches d'âge", "15 - 24", "Sexe", "Féminin"),
    "no_degree": series(qd, "Type diplôme", "Sans diplôme", "Sexe", "Total"),
    "mid_degree": series(qd, "Type diplôme", "Ayant un diplôme:  Niveau moyen", "Sexe", "Total"),
    "higher_degree": series(qd, "Type diplôme", "Ayant un diplôme:  Niveau supérieur", "Sexe", "Total"),
}
out["age_groups"] = q[["Tranches d'âge", "Sexe"]].astype(str).values.tolist()
out["diplomas"] = qd[["Type diplôme", "Sexe"]].astype(str).values.tolist()
r = hcp("data_i3287")
out["region_unemp"] = r[r["Sexe"].astype(str).str.strip() == "Total"][["Milieu", "Région", "2025", "2015", "Sexe"]].astype(str).values.tolist()
r2 = r[r["Sexe"].astype(str).str.strip() == "Féminin"][["Milieu", "Région", "2025"]].astype(str).values.tolist()
out["region_unemp_women"] = r2
p = hcp("data_imt_txch_02")
out["prov_unemp"] = p[["Milieu", "Provinces/Préfectures", "2025", "2017"]].astype(str).values.tolist()

# --- CPI
c = hcp("data_i4166")
out["cpi_month_tokens"] = sorted({re.sub(r"-\d{4}", "", x) for x in c.columns[2:]})
nat = c[c["Villes"].astype(str).str.strip() == "National"]
keep = ["(GR) GENERAL", "(01) PRODUITS ALIMENTAIRES ET BOISSONS NON ALCOOLISÉES", "(0112) VIANDE", "(0117) LEGUMES", "(0115) HUILES ET GRAISSES", "(0111) PAIN ET CEREALES", "(07) TRANSPORT"]
out["cpi_groups"] = nat["Divisions et groupes de produits"].astype(str).str.strip().tolist()[:40]
out["cpi"] = {k: nat[nat["Divisions et groupes de produits"].astype(str).str.strip() == k].iloc[0, 2:].dropna().astype(float).to_dict()
              for k in keep if (nat["Divisions et groupes de produits"].astype(str).str.strip() == k).any()}

# --- AMO coverage
f = g("autorite-de-controle-des-assurances-et-de-la-prevoyance-sociale/taux-de-couverture*/*.xlsx")[0]
df = pd.read_excel(f, header=None)
out["amo"] = {int(y): round(float(v) * 100, 1) for y, v in zip(df.iloc[0, 1:], df.iloc[1, 1:]) if pd.notna(y)}

# --- Telecom
def anrt(pat, cols):
    df = pd.read_excel(g(pat)[0], header=None)
    i = df.index[df[0].astype(str).str.startswith("Période")][0]
    hdr = df.iloc[i].tolist(); body = df.iloc[i + 1:]; body.columns = hdr
    body = body[body["Période (à fin)"].astype(str).str.match(r"T4-\d{4}")]
    return {str(r["Période (à fin)"])[3:]: [None if pd.isna(r[k]) else float(r[k]) for k in cols] for _, r in body.iterrows()}
out["mobile"] = anrt("anrt/parc-de-la-telephonie-mobile*/*.xlsx", ["L", "M"])
out["internet"] = anrt("anrt/parc-de-l-internet*/*.xlsx", ["Q", "R", "H", "D", "K"])

# --- Road deaths
roads = {}
for f in g("narsa/statistiques-des-accidents-de-la-circulation-routiere-*/*.xlsx"):
    df = pd.read_excel(f, header=None)
    yr = int(re.search(r"(\d{4})", str(df.iloc[0, 0])).group(1))
    rows = {str(r[0]).strip(): [r[1], r[2], r[3]] for r in df.values[1:]}
    roads[yr] = {k: [int(x) for x in v] for k, v in rows.items()}
out["roads"] = roads

# --- Courts
courts = {}
for f in g("ministere-de-la-justice-et-des-libertes/evolution-des-affaires-au-cours-du-quinq*/*.xlsx"):
    df = pd.read_excel(f, header=None).dropna(how="all").dropna(axis=1, how="all")
    yrs = df.iloc[1, 1:].tolist()
    for _, r in df.iloc[2:].iterrows():
        courts.setdefault(str(r.iloc[0]).strip(), {}).update({int(y): float(v) for y, v in zip(yrs, r.iloc[1:]) if pd.notna(y) and pd.notna(v)})
out["courts"] = courts

# --- Corruption perception
f = g("l-instance-nationale*/indice-de-perception*/*.xlsx")[0]
df = pd.read_excel(f, sheet_name="CPI_DATA")
out["cpi_corr"] = df[["Année", "CPI", "Rank"]].values.tolist()

json.dump(out, open("raw.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0, default=str)
print("ok")
