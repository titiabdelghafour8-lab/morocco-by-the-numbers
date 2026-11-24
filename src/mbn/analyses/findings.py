"""The 21 findings on the main page: pure functions from parsed tables to published series.

``build`` reproduces the published ``data/morocco_by_the_numbers.json`` exactly (apart
from ``src`` and ``updated``, which the registry and the caller add). Intermediate
values pass through ``jsonify`` where the original scripts passed them through a JSON
file, because that round trip decides key types and therefore sort order.
"""

from __future__ import annotations

import collections
import json
import re
from typing import Any

MONTH_TOKENS = {
    "Janv": 1,
    "Févr": 2,
    "Mars": 3,
    "Avr": 4,
    "Mai": 5,
    "Juin": 6,
    "Juill": 7,
    "Août": 8,
    "Sept": 9,
    "Oct": 10,
    "Nov": 11,
    "Déc": 12,
}

RAIN_MIN_MONTHS = 11
"""A rainfall year is kept only if at least 11 of its 12 months have data."""
FLOW_MIN_MONTHS = 12

PARLIAMENT_THEMES = [
    ("Interior", "الداخلية"),
    ("Agriculture, fisheries, water and forests", "الفلاحة"),
    ("Health and social protection", "الصحة"),
    ("Education and research", "التربية|التعليم|البحث العلمي"),
    ("Infrastructure, transport and water", "التجهيز|النقل|بالماء"),
    ("Economy and finance", "الاقتصاد|المالية|الميزانية"),
    ("Housing and planning", "السكنى|الإسكان|إعداد التراب|التعمير"),
    ("Employment and skills", "الشغل|التشغيل|الإدماج المهني"),
    ("Social affairs and family", "التضامن|الأسرة"),
    ("Justice", "العدل"),
    ("Youth, culture and sport", "الشباب|الثقافة|الرياضة"),
    ("Energy and environment", "الطاقة|البيئة|التنمية المستدامة"),
    ("Tourism and crafts", "السياحة"),
    ("Industry and trade", "الصناعة|التجارة"),
    ("Islamic affairs", "الأوقاف"),
    ("Foreign affairs and Moroccans abroad", "الخارجية|المقيمين بالخارج"),
    ("Head of government", "رئيس الحكومة"),
]
"""Ministry names changed in 2021, so questions are grouped into policy areas by keyword."""

STARTUP_CITY_SPELLINGS = {"tanger-assilah": "tanger", "tangier": "tanger", "fès": "fes"}
COURT_KEEP = "الاستئناف العادية"  # ordinary appeal courts


def jsonify(x: Any) -> Any:
    """Round-trip through JSON: tuples become lists, dict keys become strings."""
    return json.loads(json.dumps(x, ensure_ascii=False, default=str))


def mean(xs: list[float]) -> float:
    return round(sum(xs) / len(xs), 1)


# --- helpers --------------------------------------------------------------------------------
def yoy(levels: dict[tuple[int, int], float], periods: int) -> list[list[float]]:
    """Year-on-year % change of a (year, sub-period) series; x = year + (sub - 1) / periods."""
    return [
        [y + (t - 1) / periods, round((v / levels[(y - 1, t)] - 1) * 100, 1)]
        for (y, t), v in sorted(levels.items())
        if (y - 1, t) in levels
    ]


def chron_quarters(d: dict[str, float | None]) -> list[tuple[float, float]]:
    """{"T1-2017": v} -> [(2017.0, v)], dropping gaps, in time order."""
    return sorted((int(k[3:]) + (int(k[1]) - 1) / 4, v) for k, v in d.items() if v is not None)


def cpi_yoy(levels: dict[str, float]) -> list[tuple[float, float]]:
    """{"Janv-2018": index} -> [(2018.0, % change on a year earlier)]."""
    s = {(int(k.split("-")[1]), MONTH_TOKENS[k.split("-")[0]]): v for k, v in levels.items()}
    return [(y + (m - 1) / 12, round((v / s[(y - 1, m)] - 1) * 100, 1)) for (y, m), v in sorted(s.items()) if (y - 1, m) in s]


def credit_growth(s: Any) -> list[list[float]]:
    """Monthly credit Series indexed by (year, month) -> [[x, % yoy, level in billions]]."""
    return [
        [y + (m - 1) / 12, round((v / s[(y - 1, m)] - 1) * 100, 1), round(v / 1000)]
        for (y, m), v in s.items()
        if (y - 1, m) in s.index
    ]


def funds_monthly(funds: list[list[Any]]) -> tuple[list[list[float]], dict[str, Any]]:
    """Weekly fund totals -> last report of each month, from the first year with >= 10 reports."""
    by: collections.OrderedDict[str, tuple[str, float]] = collections.OrderedDict()
    for d, v in funds:
        by[d[:7]] = (d, v)
    yrs = collections.Counter(d[:4] for d, _ in funds)
    start = min(y for y, n in yrs.items() if n >= 10)
    series = [[int(k[:4]) + (int(k[5:]) - 1) / 12, v] for k, (_d, v) in by.items() if k[:4] >= start]
    return series, {"start": start, "files_per_year": dict(sorted(yrs.items()))}


def parliament_themes(ministries: dict[str, int]) -> tuple[list[list[Any]], int]:
    """Questions per policy area (largest first) and the number that matched no area."""
    cnt: collections.Counter[str] = collections.Counter()
    unmapped = 0
    for name, n in ministries.items():
        for t, pat in PARLIAMENT_THEMES:
            if re.search(pat, name):
                cnt[t] += n
                break
        else:
            unmapped += n
    return [[t, n] for t, n in cnt.most_common()], unmapped


def startup_cities(top_cities: dict[str, int], n: int = 6) -> list[tuple[str, int]]:
    city: collections.Counter[str] = collections.Counter()
    for k, v in top_cities.items():
        city[STARTUP_CITY_SPELLINGS.get(k, k)] += v
    return city.most_common(n)


# --- stage 1: land, work, prices, living, state ----------------------------------------------
def build_main(raw: dict[str, Any], courts: dict[str, dict[int, float]]) -> dict[str, Any]:
    """Series from the first group of datasets (``raw`` has been through ``jsonify``)."""
    o: dict[str, Any] = {}
    rain = {int(y): v[0] for y, v in raw["rain"].items() if v[1] >= RAIN_MIN_MONTHS}
    o["rain"] = sorted(rain.items())
    flow = {int(y): v[0] for y, v in raw["flow"].items() if v[1] >= FLOW_MIN_MONTHS}
    o["flow"] = sorted(flow.items())
    cer = raw["crops"]["Céréales"]
    o["cereals"] = [(int(k[-4:]), round(v / 1e6, 2)) for k, v in sorted(cer.items())]
    o["unemp"] = {k: chron_quarters(v) for k, v in raw["unemp_q"].items()}
    region = [(r[1], float(r[2]), float(r[3])) for r in raw["region_unemp"] if r[0] == "National" and r[1] != "Ensemble"]
    wom = {r[1]: float(r[2]) for r in raw["region_unemp_women"] if r[0] == "National"}
    o["region"] = [(n, t, old, wom.get(n)) for n, t, old in region]
    prov = [(r[1], float(r[2])) for r in raw["prov_unemp"] if r[0] == "National" and re.match(r"^[\d.]+$", r[2])]
    prov.sort(key=lambda x: -x[1])
    o["prov_n"], o["prov_top"], o["prov_bottom"] = len(prov), prov[:8], prov[-8:]
    o["infl"] = cpi_yoy(raw["cpi"]["(GR) GENERAL"])
    o["infl_food"] = cpi_yoy(raw["cpi"]["(01) PRODUITS ALIMENTAIRES ET BOISSONS NON ALCOOLISÉES"])
    o["amo"] = sorted((int(k), v) for k, v in raw["amo"].items())
    o["mobile"] = [(int(y), round(v[1] * 100, 1)) for y, v in sorted(raw["mobile"].items())]
    o["internet"] = [(int(y), round(v[1] * 100, 1)) for y, v in sorted(raw["internet"].items()) if v[1]]
    o["roads"] = sorted(
        (int(y), v["Tués"][2], v["Total Accidents"][2], v["Tués"][0], v["Tués"][1]) for y, v in raw["roads"].items()
    )
    o["courts"] = {k: sorted(v.items()) for k, v in courts.items() if "|" not in k or COURT_KEEP in k}
    o["corr"] = raw["cpi_corr"]
    return o


# --- stage 2: economy, pensions, startups, parliament ------------------------------------------
def build_more(r: dict[str, Any]) -> dict[str, Any]:
    o: dict[str, Any] = {}
    o["gdp_growth"] = r["gdp_growth"]
    o["credit"] = [[x, g] for x, g, _ in r["credit"] if x >= 2010]
    o["pension_ratio"] = r["pension_ratio"]
    o["funds"], o["funds_note"] = funds_monthly(r["funds"])
    o["startup_n"] = r["startup_n"]
    o["startup_city"] = startup_cities(r["startup_city"])
    o["parl_n"] = r["parl_n"]
    o["parl_total"] = sum(r["parl_ministries"].values())
    o["parl_themes"], o["parl_unmapped"] = parliament_themes(r["parl_ministries"])
    o["parl_years"] = r["parl_years"]

    def pairs(d: dict[str, float]) -> list[list[float]]:  # million -> billion dirhams
        return sorted([int(k), round(v / 1000, 2)] for k, v in d.items())

    o["amo_finance"] = {k: pairs(v) for k, v in r["amo_finance"].items()}
    o["pension_money"] = {k: pairs(v) for k, v in r["pension_money"].items()}
    o["vehicles"] = {k: sorted([int(y), round(v)] for y, v in d.items()) for k, d in r["vehicles"].items()}
    return o


# --- stage 3: public services per resident ---------------------------------------------------------
def services(s3: dict[str, Any], pop: dict[str, int]) -> tuple[list[list[Any]], dict[str, int]]:
    """Per-region facilities per resident (sorted by health centres per 100k, highest first) and totals."""
    rows = sorted(
        [
            [
                r,
                round(s3["primary_care"].get(r, 0) / pop[r] * 1e5, 1),
                round(s3["hospitals"].get(r, 0) / pop[r] * 1e6, 1),
                round(s3["schools_primary"].get(r, 0) / pop[r] * 1e5, 1),
                pop[r],
            ]
            for r in pop
        ],
        key=lambda x: -x[1],
    )
    totals = {k: sum(s3[k].values()) for k in ["hospitals", "primary_care", "schools_primary", "schools_middle", "schools_high"]}
    return rows, totals


# --- assembly ------------------------------------------------------------------------------------
def pack(s: dict[str, Any], s2: dict[str, Any], s3: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    """Assemble the published data file (key order matters for a byte-identical file)."""

    def r(xs: list[list[float]], n: int = 2) -> list[list[float]]:
        return [[round(a, 3), round(b, n)] for a, b in xs]

    un = s["unemp"]
    out: dict[str, Any] = {
        "flow": r(s["flow"], 2),
        "rain": r(s["rain"], 0),
        "cereals": s["cereals"],
        "u_total": r(un["total"], 1),
        "u_youth": r(un["youth"], 1),
        "u_youth_w": r(un["youth_women"], 1),
        "u_none": r(un["no_degree"], 1),
        "u_mid": r(un["mid_degree"], 1),
        "u_high": r(un["higher_degree"], 1),
        "region": s["region"],
        "prov_top": s["prov_top"],
        "prov_bottom": s["prov_bottom"],
        "infl": r(s["infl"], 1),
        "infl_food": r(s["infl_food"], 1),
        "amo": s["amo"],
        "internet": s["internet"],
        "mobile": s["mobile"],
        "roads": s["roads"],
        "appeal": s["courts"]["registered|محاكم الاستئناف العادية"],
        "registered": s["courts"]["registered"],
        "judged": s["courts"]["judged"],
        "corr": s["corr"],
        "src": src,
    }
    for k in [
        "gdp_growth",
        "credit",
        "funds",
        "pension_ratio",
        "startup_city",
        "startup_n",
        "parl_themes",
        "parl_total",
        "parl_n",
        "amo_finance",
        "pension_money",
        "vehicles",
    ]:
        out[k] = s2[k]
    out["credit"] = [[round(x, 3), v] for x, v in out["credit"]]
    out["funds"] = [[round(x, 3), v] for x, v in out["funds"]]
    out["services"], out["services_totals"] = services(s3, s3["pop"])
    return out
