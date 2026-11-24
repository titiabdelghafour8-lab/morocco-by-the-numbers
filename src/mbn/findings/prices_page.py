"""The "Prices" page: a monthly price monitor from HCP's consumer price index (base 100 = 2017).

Refreshes through the weekly sync whenever HCP publishes a month.
"""

from __future__ import annotations

import datetime
import os
from typing import Any, cast

import numpy as np
import pandas as pd

from mbn.analyses import prices
from mbn.config import DATA_DIR
from mbn.model import schemas
from mbn.model.claims import Claim
from mbn.parsers import hcp
from mbn.publish import data_export, site
from mbn.sources.store import DatasetStore

DATA_FILE = DATA_DIR / "prices.json"
CSV_FILE = DATA_DIR / "prices_latest.csv"
DATASETS = ("data_i4166",)
HEADLINE, FOOD = "GR", "01"
ANNOUNCED_FEB_2023_FOOD = 20.1
"""HCP's first announcement for food inflation in February 2023 (press release of March 2023)."""

DIVISIONS = {
    "01": "Food and soft drinks",
    "02": "Alcohol and tobacco",
    "03": "Clothing and shoes",
    "04": "Housing, water and energy",
    "05": "Furnishings and household",
    "06": "Health",
    "07": "Transport",
    "08": "Communications",
    "09": "Recreation and culture",
    "10": "Education",
    "11": "Restaurants and hotels",
    "12": "Other goods and services",
}
CLASSES = {
    "0111": "Bread and cereals",
    "0112": "Meat",
    "0113": "Fish and seafood",
    "0114": "Milk, cheese and eggs",
    "0115": "Oils and fats",
    "0116": "Fruit",
    "0117": "Vegetables",
    "0118": "Sugar, jam, honey and sweets",
    "0119": "Other food",
    "0121": "Coffee, tea and cocoa",
    "0122": "Water, soft drinks and juices",
}
MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def name(code: str, french: str) -> str:
    if code in DIVISIONS:
        return DIVISIONS[code]
    if code in CLASSES:
        return CLASSES[code]
    return french.capitalize()


def analyse(long: pd.DataFrame, backtest_origins: int = 36) -> dict[str, Any]:
    """Every published series and number from the tidy CPI table (pure)."""
    names = long.drop_duplicates("code").set_index("code")["product"].to_dict()
    nat = long[long["city"] == "National"].pivot(index="month", columns="code", values="index").sort_index()
    latest = pd.Timestamp(nat.index.max())
    gr, food = nat[HEADLINE], nat[FOOD]
    sa = prices.seasonally_adjusted(gr)
    divisions = sorted(c for c in nat.columns if len(c) == 2 and c.isdigit())

    w = prices.implied_weights(nat, divisions, HEADLINE)
    contrib = prices.contributions(nat, w.weights, HEADLINE).loc[latest]
    contrib_d = {str(c): float(cast(float, v)) for c, v in contrib.items()}
    contrib_rows: list[list[Any]] = sorted(
        ([c, DIVISIONS[c], round(v, 2)] for c, v in contrib_d.items()), key=lambda r: -float(r[2])
    )

    classes = [c for c in nat.columns if len(c) == 4 and c.isdigit()]
    movers: list[list[Any]] = []
    for c in classes:
        m = prices.mom(nat[c]).dropna()
        if len(m) < 24:
            continue
        z = prices.robust_z(m)
        movers.append(
            [
                c,
                name(c, names[c]),
                round(float(m.iloc[-1]), 1),
                round(float(prices.yoy(nat[c]).iloc[-1]), 1),
                round(float(z.iloc[-1]), 1),
            ]
        )
    movers.sort(key=lambda r: -abs(float(r[4])))

    cities = sorted(c for c in long["city"].unique() if c != "National")
    by_city = {c: long[long["city"] == c].pivot(index="month", columns="code", values="index").sort_index() for c in cities}
    sa_changes = pd.DataFrame({c: prices.mom(prices.seasonally_adjusted(df[HEADLINE])) for c, df in by_city.items()}).dropna()
    groups = prices.cluster(sa_changes, k=3)
    order = sorted(cities, key=lambda c: (groups[c], -float(prices.yoy(by_city[c][HEADLINE]).iloc[-1])))
    heat = [
        [
            c,
            groups[c],
            round(float(prices.yoy(by_city[c][HEADLINE]).iloc[-1]), 1),
            [round(float(prices.yoy(by_city[c][d]).iloc[-1]), 1) for d in divisions],
        ]
        for c in order
    ]

    bt = prices.backtest(gr, horizon=3, origins=backtest_origins)
    decision = prices.forecast_decision(bt.mae)
    fc = prices.forecast_yoy(gr, decision.model, 3) if decision.model else []

    head_yoy, food_yoy = prices.yoy(gr), prices.yoy(food)
    city_yoy = {str(h[0]): float(h[2]) for h in heat}
    hi, lo = max(city_yoy, key=lambda c: city_yoy[c]), min(city_yoy, key=lambda c: city_yoy[c])
    top = contrib_rows[0]
    summary = {
        "latest": latest.strftime("%Y-%m"),
        "headline_yoy": round(float(head_yoy.iloc[-1]), 1),
        "headline_mom": round(float(prices.mom(gr).iloc[-1]), 1),
        "food_yoy": round(float(food_yoy.iloc[-1]), 1),
        "sa3m": round(float(prices.annualised_3m(sa).iloc[-1]), 1),
        "headline_peak": round(float(head_yoy.max()), 1),
        "headline_peak_month": pd.Timestamp(str(head_yoy.idxmax())).strftime("%Y-%m"),
        "food_feb2023": round(float(food_yoy.loc["2023-02-01"]), 1),
        "top_contrib_code": top[0],
        "top_contrib": top[2],
        "food_contrib": round(contrib_d[FOOD], 2),
        "contrib_sum": round(sum(contrib_d.values()), 2),
        "weight_food": round(float(w.weights[FOOD]) * 100, 1),
        "weights_residual": round(w.max_residual, 3),
        "weights_half_gap": round(w.half_sample_gap * 100, 2),
        "weights_sum": round(float(w.weights.sum()), 4),
        "mover_code": movers[0][0],
        "mover_mom": movers[0][2],
        "mover_z": movers[0][4],
        "city_high": hi,
        "city_high_yoy": round(city_yoy[hi], 1),
        "city_low": lo,
        "city_low_yoy": round(city_yoy[lo], 1),
        "cities_n": len(cities),
        "clusters": max(groups.values()),
        "forecast_model": decision.model,
        "forecast_improvement": round(decision.improvement * 100),
        "mae": {k: round(v, 2) for k, v in bt.mae.items()},
        "backtest_origins": backtest_origins,
        "backtest_from": bt.errors[0][0],
        "backtest_to": bt.errors[-1][0],
    }
    return {
        "headline": [[x, v, f] for (x, v), (_, f) in zip(prices.points(head_yoy), prices.points(food_yoy), strict=True)],
        "sa3m": prices.points(prices.annualised_3m(sa)),
        "contributions": contrib_rows,
        "weights": [[str(c), DIVISIONS[str(c)], round(float(v) * 100, 2)] for c, v in w.weights.items()],
        "movers": movers[:5],
        "divisions": [[d, DIVISIONS[d]] for d in divisions],
        "heatmap": heat,
        "forecast": {
            "model": decision.model,
            "mae": summary["mae"],
            "path": [round(v, 1) for v in fc],
            "months": [(latest + pd.DateOffset(months=j + 1)).strftime("%Y-%m") for j in range(len(fc))],
        },
        "summary": summary,
    }


def forecast_sentence(decision: prices.ForecastDecision) -> str:
    base = decision.mae.get(prices.BASELINE, float("nan"))
    if decision.model is None:
        best = min((m for m in decision.mae if m != prices.BASELINE), key=lambda m: decision.mae[m], default=None)
        rival = f" The best model, {best}, missed by {decision.mae[best]:.2f} points on average." if best else ""
        return (
            f'No forecast is published. In back-tests, no model beat the simple rule "same monthly changes as last year", '
            f"which missed headline inflation three months ahead by {base:.2f} points on average.{rival}"
        )
    return (
        f'The {decision.model} model beat the simple rule "same monthly changes as last year" in back-tests: its '
        f"three-month-ahead error was {decision.improvement:.0%} smaller ({decision.mae[decision.model]:.2f} against "
        f"{base:.2f} points)."
    )


def _month(ym: str) -> str:
    y, m = ym.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def _pct(v: float, sign: bool = False) -> str:
    s = f"{abs(v):.1f}%"
    return ("+" if v > 0 else "−" if v < 0 else "") + s if sign else s


def _dir(v: float, up: str = "higher", down: str = "lower") -> str:
    return up if v > 0 else down if v < 0 else "unchanged"


def cluster_sentence(heat: list[list[Any]]) -> str:
    groups: dict[int, list[str]] = {}
    for row in heat:
        groups.setdefault(int(row[1]), []).append(str(row[0]))
    main = max(groups, key=lambda g: len(groups[g]))
    apart = [c for g, cs in groups.items() if g != main for c in cs]
    if not apart:
        return "All cities' prices move together month to month."
    return (
        f"{len(groups[main])} of {len(heat)} cities' prices move together month to month; "
        f"{' and '.join(apart)} {'moves' if len(apart) == 1 else 'move'} differently and {'is' if len(apart) == 1 else 'are'} listed last."
    )


def text(data: dict[str, Any]) -> dict[str, str]:
    s = data["summary"]
    dec = prices.ForecastDecision(s["forecast_model"], s["mae"], s["forecast_improvement"] / 100)
    mover = data["movers"][0]
    if s["headline_yoy"] <= 0:
        heading = "Prices are lower than a year ago"
    elif s["sa3m"] > s["headline_yoy"] + 0.5:
        heading = "Price rises are speeding up"
    elif s["sa3m"] < s["headline_yoy"] - 0.5:
        heading = "Price rises are slowing"
    else:
        heading = "Prices are rising at a steady pace"
    return {
        "latest": _month(s["latest"]),
        "heading": heading,
        "headline_abs": _pct(s["headline_yoy"]),
        "headline_dir": _dir(s["headline_yoy"]),
        "food_abs": _pct(s["food_yoy"]),
        "food_dir": _dir(s["food_yoy"]),
        "headline_mom": _pct(s["headline_mom"], True),
        "sa3m": _pct(s["sa3m"], True),
        "peak": _pct(s["headline_peak"]),
        "peak_month": _month(s["headline_peak_month"]),
        "top_contrib_name": DIVISIONS[s["top_contrib_code"]],
        "top_contrib": f"{s['top_contrib']:+.2f}".replace("-", "−"),
        "food_contrib": f"{s['food_contrib']:+.2f}".replace("-", "−"),
        "weight_food": f"{s['weight_food']:.0f}%",
        "weights_residual": f"{s['weights_residual']:.2f}",
        "weights_half_gap": f"{s['weights_half_gap']:.1f}",
        "mover_name": mover[1],
        "mover_mom": _pct(mover[2], True),
        "mover_z": f"{mover[4]:.0f}",
        "city_high": s["city_high"],
        "city_high_yoy": _pct(s["city_high_yoy"], True),
        "city_low": s["city_low"],
        "city_low_yoy": _pct(s["city_low_yoy"], True),
        "cities_n": str(s["cities_n"]),
        "cluster_sentence": cluster_sentence(data["heatmap"]),
        "food_feb2023": _pct(s["food_feb2023"]),
        "food_feb2023_announced": _pct(ANNOUNCED_FEB_2023_FOOD),
        "forecast_sentence": forecast_sentence(dec),
        "backtest_origins": str(s["backtest_origins"]),
        "backtest_from": _month(s["backtest_from"][:7]),
        "backtest_to": _month(s["backtest_to"][:7]),
    }


def build(st: DatasetStore, updated: str | None = None) -> dict[str, Any]:
    body = hcp.read_data_sheet(st.file("haut-commissariat-au-plan/data_i4166/*_data.xlsx"))
    long = schemas.cpi_long(hcp.cpi_long(body))
    out = analyse(long)
    out["text"] = text(out)
    out["src"] = {"cpi": st.source("haut-commissariat-au-plan/data_i4166").as_dict()}
    out["updated"] = updated or os.environ.get("DATA_DATE") or datetime.date.today().isoformat()
    nat = long[long["city"] == "National"]
    last = nat["month"].max()
    rows = []
    for city, g in long.groupby("city"):
        w = g.pivot(index="month", columns="code", values="index").sort_index()
        for code in w.columns:
            y = prices.yoy(w[code])
            m = prices.mom(w[code])
            rows.append(
                {
                    "month": pd.Timestamp(last).strftime("%Y-%m"),
                    "city": city,
                    "code": code,
                    "product_fr": g.loc[g["code"] == code, "product"].iloc[0],
                    "index_2017_100": float(w[code].iloc[-1]),
                    "yoy_pct": None if np.isnan(y.iloc[-1]) else round(float(y.iloc[-1]), 2),
                    "mom_pct": None if np.isnan(m.iloc[-1]) else round(float(m.iloc[-1]), 2),
                }
            )
    data_export.write_csv(CSV_FILE, rows, ["month", "city", "code", "product_fr", "index_2017_100", "yoy_pct", "mom_pct"])
    return out


def render(data: dict[str, Any], nav: str = "") -> str:
    return site.render_page("prices.html", data, nav)


def _s(key: str) -> Any:
    return lambda d: d["summary"][key]


def _forecast_rule(d: dict[str, Any]) -> float:
    """1 when the page follows the rule: a forecast is shown only if it beat the benchmark."""
    f, mae = d["forecast"], d["summary"]["mae"]
    if f["model"] is None:
        return float(not f["path"])
    return float(mae[f["model"]] < mae[prices.BASELINE] and len(f["path"]) == 3)


# This page refreshes itself every month, so its numbers are written from the data. The claims
# guard what must not drift silently: history, the integrity of the method and the forecast rule.
CLAIMS: list[Claim] = [
    Claim("Food inflation Feb 2023, revised index (announced 20.1%)", _s("food_feb2023"), 20.8, 0.05),
    Claim("Peak headline inflation (%)", _s("headline_peak"), 10.1, 0.05),
    Claim(
        "Peak headline inflation month (YYYYMM)", lambda d: int(d["summary"]["headline_peak_month"].replace("-", "")), 202302, 0
    ),
    Claim(
        "Contributions add up to headline inflation (points)",
        lambda d: d["summary"]["contrib_sum"] - d["summary"]["headline_yoy"],
        0,
        0.1,
    ),
    Claim("Implied weights rebuild the headline index (max gap, index points)", _s("weights_residual"), 0.05, 0.05),
    Claim("Implied weights sum to 1", _s("weights_sum"), 1.0, 0.002),
    Claim("Food weight in the basket (%)", _s("weight_food"), 38.0, 1.0),
    Claim("Cities in the index", _s("cities_n"), 18, 0),
    Claim("Forecast shown only if it beats the benchmark", _forecast_rule, 1, 0),
    Claim("Back-test covers 36 forecast origins", _s("backtest_origins"), 36, 0),
]
