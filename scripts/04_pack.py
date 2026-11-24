import json, glob, os, sys
D = sys.argv[1]; s = json.load(open("site_data.json", encoding="utf-8"))
def src(pat):
    f = glob.glob(os.path.join(D, pat, "metadata.json"))[0]
    m = json.load(open(f, encoding="utf-8"))
    return {"title": m["title"].strip(), "org": (m.get("organization") or {}).get("title", "").strip(), "url": "https://data.gov.ma/data/fr/dataset/" + m["name"]}
r = lambda xs, n=2: [[round(a, 3), round(b, n)] for a, b in xs]
out = {
 "flow": r(s["flow"], 2), "rain": r(s["rain"], 0), "cereals": s["cereals"],
 "u_total": r(s["unemp"]["total"], 1), "u_youth": r(s["unemp"]["youth"], 1), "u_youth_w": r(s["unemp"]["youth_women"], 1),
 "u_none": r(s["unemp"]["no_degree"], 1), "u_mid": r(s["unemp"]["mid_degree"], 1), "u_high": r(s["unemp"]["higher_degree"], 1),
 "region": s["region"], "prov_top": s["prov_top"], "prov_bottom": s["prov_bottom"],
 "infl": r(s["infl"], 1), "infl_food": r(s["infl_food"], 1),
 "amo": s["amo"], "internet": s["internet"], "mobile": s["mobile"],
 "roads": s["roads"], "appeal": s["courts"]["registered|محاكم الاستئناف العادية"],
 "registered": s["courts"]["registered"], "judged": s["courts"]["judged"], "corr": s["corr"],
 "src": {
  "flow": src("agence-du-bassin-hydraulique-de-souss-massa/debit-moyen-journalier-de-la-station-ait*"),
  "rain": src("agence-du-bassin-hydraulique-de-souss-massa/pluie-journaliere-du-barrage-y*"),
  "cereals": src("departement-de-l-agriculture/production*"),
  "u_age": src("haut-commissariat-au-plan/data_i4252"), "u_dip": src("haut-commissariat-au-plan/data_i4248"),
  "region": src("haut-commissariat-au-plan/data_i3287"), "prov": src("haut-commissariat-au-plan/data_imt_txch_02"),
  "cpi": src("haut-commissariat-au-plan/data_i4166"),
  "amo": src("autorite-de-controle-des-assurances-et-de-la-prevoyance-sociale/taux-de-couverture*"),
  "internet": src("anrt/parc-de-l-internet*"), "mobile": src("anrt/parc-de-la-telephonie-mobile*"),
  "roads": src("narsa/statistiques-des-accidents-de-la-circulation-routiere-2024"),
  "courts": src("ministere-de-la-justice-et-des-libertes/evolution-des-affaires-au-cours-du-quinquennat-2018-2022"),
  "corr": src("l-instance-nationale*/indice-de-perception*"),
 }}
s2 = json.load(open("site_data2.json", encoding="utf-8"))
for k in ["gdp_growth", "credit", "funds", "pension_ratio", "startup_city", "startup_n", "parl_themes", "parl_total", "parl_n", "amo_finance", "pension_money", "vehicles"]:
    out[k] = s2[k]
out["credit"] = [[round(x, 3), v] for x, v in out["credit"]]; out["funds"] = [[round(x, 3), v] for x, v in out["funds"]]
out["src"].update({
  "gdp": src("haut-commissariat-au-plan/data_i4276"),
  "credit": src("bank-al-maghrib/creances-sur-l-economie*"),
  "funds": src("ammc/stat-hebdo-opcvm-2026"),
  "startups": src("agence-de-developpement-du-digital/donnees-sur-les-startups"),
  "pensions": src("autorite-de-controle-des-assurances-et-de-la-prevoyance-sociale/rapport-demographique*"),
  "parliament": src("parlement/liste-des-questions-ecrites-de-la-session-d-avril"),
  "amo_in": src("autorite-de-controle-des-assurances-et-de-la-prevoyance-sociale/ressources-des-regimes-amo"),
  "amo_out": src("autorite-de-controle-des-assurances-et-de-la-prevoyance-sociale/depenses-des-regimes-amo"),
  "pen_in": src("autorite-de-controle-des-assurances-et-de-la-prevoyance-sociale/cotisations-des-regimes-de-retraite"),
  "pen_out": src("autorite-de-controle-des-assurances-et-de-la-prevoyance-sociale/prestations-des-regimes-de-retraite"),
  "pen_res": src("autorite-de-controle-des-assurances-et-de-la-prevoyance-sociale/reserves-des-regimes-de-retraite"),
  "vehicles": sorted(glob.glob(os.path.join(D, "narsa/statistiques-des-immatriculations-et-permis-de-conduire-delivres*")))[-1:] and src(os.path.relpath(sorted(glob.glob(os.path.join(D, "narsa/statistiques-des-immatriculations-et-permis-de-conduire-delivres*")))[-1], D)),
})
s3 = json.load(open("raw3.json", encoding="utf-8")); P = s3["pop"]
out["services"] = sorted([[r, round(s3["primary_care"].get(r, 0) / P[r] * 1e5, 1), round(s3["hospitals"].get(r, 0) / P[r] * 1e6, 1),
                           round(s3["schools_primary"].get(r, 0) / P[r] * 1e5, 1), P[r]] for r in P], key=lambda x: -x[1])
out["services_totals"] = {k: sum(s3[k].values()) for k in ["hospitals", "primary_care", "schools_primary", "schools_middle", "schools_high"]}
out["src"].update({"primary_care": src("ministere-de-la-sante/repartition-des-etablissements-de-soins-de-sante-primaire*"),
                   "hospitals": src("ministere-de-la-sante/la-liste-des-hopitaux"),
                   "schools": src("ministere-de-l-education-nationale-et-de-la-formation-professionnelle/liste-des-etablissements-publics-primaire")})
import datetime
out["updated"] = os.environ.get("DATA_DATE") or datetime.date.today().isoformat()
os.makedirs("data", exist_ok=True)
json.dump(out, open("data/morocco_by_the_numbers.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
js = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
print(len(js))
open("data.min.json", "w", encoding="utf-8").write(js)
print(json.dumps(out["src"], ensure_ascii=False)[:1500])
