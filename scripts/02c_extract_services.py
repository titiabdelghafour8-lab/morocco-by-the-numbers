"""Count public health facilities and schools by region; join with RGPH 2024 population -> raw3.json.
Usage: python 02c_extract_services.py <datasets dir>
Population: HCP, Population légale du Royaume du Maroc, RGPH 2024 (https://www.hcp.ma/file/242342/).
"""
import glob, os, sys, json, unicodedata, warnings
import pandas as pd
warnings.filterwarnings("ignore")
D = sys.argv[1]
POP = {  # RGPH 2024 legal population, HCP
    "Tanger-Tétouan-Al Hoceïma": 4030222, "Oriental": 2294665, "Fès-Meknès": 4467911, "Rabat-Salé-Kénitra": 5132639,
    "Béni Mellal-Khénifra": 2525801, "Casablanca-Settat": 7688967, "Marrakech-Safi": 4892393, "Drâa-Tafilalet": 1655623,
    "Souss-Massa": 3020431, "Guelmim-Oued Noun": 448685, "Laâyoune-Sakia El Hamra": 451028, "Dakhla-Oued Ed-Dahab": 219965}
assert sum(POP.values()) == 36828330
KEYS = {"tanger": "Tanger-Tétouan-Al Hoceïma", "oriental": "Oriental", "fes": "Fès-Meknès", "rabat": "Rabat-Salé-Kénitra",
        "beni": "Béni Mellal-Khénifra", "casablanca": "Casablanca-Settat", "marrakech": "Marrakech-Safi", "draa": "Drâa-Tafilalet",
        "souss": "Souss-Massa", "guelmim": "Guelmim-Oued Noun", "laayoune": "Laâyoune-Sakia El Hamra", "dakhla": "Dakhla-Oued Ed-Dahab"}
def region(v):
    s = unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode().lower()
    return next((r for k, r in KEYS.items() if k in s), None)
def count(path, col_hint, keep=None):
    df = pd.read_excel(path, header=None)
    hdr = next(i for i in range(15) if any(str(c).strip().lower() in col_hint for c in df.iloc[i]))
    col = next(j for j, c in enumerate(df.iloc[hdr]) if str(c).strip().lower() in col_hint)
    body = df.iloc[hdr + 1:]
    if keep:  # filter on the "Catégorie" column
        cat = next(j for j, c in enumerate(df.iloc[hdr]) if str(c).strip().lower().startswith("cat"))
        body = body[body[cat].astype(str).str.strip().isin(keep)]
    regs = body[col].map(region)
    return regs.value_counts().to_dict(), int(regs.isna().sum())
f = lambda p: glob.glob(os.path.join(D, p))[0]
out = {"pop": POP}
out["hospitals"], out["hospitals_unmatched"] = count(f("ministere-de-la-sante/la-liste-des-hopitaux/liste-des-hopitaux-2025.xlsx"), {"région", "region"})
out["primary_care"], out["primary_care_unmatched"] = count(f("ministere-de-la-sante/repartition-des-etablissements-de-soins-de-sante-primaire*/essp-2025.xlsx"), {"région", "region"},
    keep={"CSU-1", "CSU-2", "CSR-1", "CSR-2", "DR"})  # health centres and rural dispensaries; excludes labs and specialist centres
for k, p in [("schools_primary", "liste-des-etablissements-publics-primaire/*2026*"), ("schools_middle", "liste-de-etablissements-publics-collegial/*2026*"),
             ("schools_high", "liste-des-etablissements-publics-qualifi*/*2026*")]:
    out[k], out[k + "_unmatched"] = count(f("ministere-de-l-education-nationale-et-de-la-formation-professionnelle/" + p), {"ll_reg", "region"})
json.dump(out, open("raw3.json", "w", encoding="utf-8"), ensure_ascii=False)
for k, v in out.items():
    if k != "pop": print(k, v if not isinstance(v, dict) else sum(v.values()))
