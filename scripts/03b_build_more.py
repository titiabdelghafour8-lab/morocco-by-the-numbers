"""Derive chart series from raw2.json -> site_data2.json."""
import json, re, collections
r = json.load(open("raw2.json", encoding="utf-8")); o = {}
o["gdp_growth"] = r["gdp_growth"]
o["credit"] = [[x, g] for x, g, _ in r["credit"] if x >= 2010]
o["credit_level_last"] = r["credit"][-1]
o["pension_ratio"] = r["pension_ratio"]
# funds: last observation per month, from the first year with >= 10 files
by = collections.OrderedDict()
for d, v in r["funds"]:
    by[d[:7]] = (d, v)
yrs = collections.Counter(d[:4] for d, _ in r["funds"])
start = min(y for y, n in yrs.items() if n >= 10)
o["funds"] = [[int(k[:4]) + (int(k[5:]) - 1) / 12, v] for k, (d, v) in by.items() if k[:4] >= start]
o["funds_note"] = {"start": start, "files_per_year": dict(sorted(yrs.items()))}
# startups: merge city spellings
cm = {"tanger-assilah": "tanger", "tangier": "tanger", "fès": "fes"}
city = collections.Counter()
for k, v in r["startup_city"].items(): city[cm.get(k, k)] += v
o["startup_n"] = r["startup_n"]; o["startup_city"] = city.most_common(6)
# parliament: group ministries into policy areas by keyword (portfolios changed in 2021)
themes = [("Interior", "الداخلية"), ("Agriculture, fisheries, water and forests", "الفلاحة"), ("Health and social protection", "الصحة"),
          ("Education and research", "التربية|التعليم|البحث العلمي"), ("Infrastructure, transport and water", "التجهيز|النقل|بالماء"),
          ("Economy and finance", "الاقتصاد|المالية|الميزانية"), ("Housing and planning", "السكنى|الإسكان|إعداد التراب|التعمير"),
          ("Employment and skills", "الشغل|التشغيل|الإدماج المهني"), ("Social affairs and family", "التضامن|الأسرة"), ("Justice", "العدل"),
          ("Youth, culture and sport", "الشباب|الثقافة|الرياضة"), ("Energy and environment", "الطاقة|البيئة|التنمية المستدامة"),
          ("Tourism and crafts", "السياحة"), ("Industry and trade", "الصناعة|التجارة"), ("Islamic affairs", "الأوقاف"),
          ("Foreign affairs and Moroccans abroad", "الخارجية|المقيمين بالخارج"), ("Head of government", "رئيس الحكومة")]
cnt = collections.Counter(); unmapped = 0
for name, n in r["parl_ministries"].items():
    for t, pat in themes:
        if re.search(pat, name): cnt[t] += n; break
    else: unmapped += n
o["parl_n"] = r["parl_n"]; o["parl_total"] = sum(r["parl_ministries"].values()); o["parl_unmapped"] = unmapped
o["parl_years"] = r["parl_years"]; o["parl_themes"] = [[t, n] for t, n in cnt.most_common()]
pairs = lambda d: sorted([int(k), round(v / 1000, 2)] for k, v in d.items())  # million -> billion dirhams
o["amo_finance"] = {k: pairs(v) for k, v in r["amo_finance"].items()}
o["pension_money"] = {k: pairs(v) for k, v in r["pension_money"].items()}
o["vehicles"] = {k: sorted([int(y), round(v)] for y, v in d.items()) for k, d in r["vehicles"].items()}
json.dump(o, open("site_data2.json", "w", encoding="utf-8"), ensure_ascii=False)
print("parliament", o["parl_total"], o["parl_n"], "unmapped", unmapped, o["parl_themes"][:6])
print("funds", o["funds"][0], o["funds"][-1]); print("pension", o["pension_ratio"][-1]); print("startups", o["startup_city"])
