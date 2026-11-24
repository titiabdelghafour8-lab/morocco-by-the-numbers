"""The "Water" page: a drought monitor for the Souss basin (Souss-Massa river basin agency data).

Builds ``data/water.json`` (+ CSV) from the downloaded files, renders ``water.html`` and
holds the claims for every number the page quotes.
"""

from __future__ import annotations

import datetime
import os
from typing import Any, cast

import pandas as pd

from mbn.analyses import water
from mbn.config import DATA_DIR
from mbn.model import schemas
from mbn.model.claims import Claim
from mbn.parsers import abh
from mbn.publish import data_export, site
from mbn.sources.store import DatasetStore

ABH = "agence-du-bassin-hydraulique-de-souss-massa/"
DATA_FILE = DATA_DIR / "water.json"
CSV_FILE = DATA_DIR / "water_annual.csv"
CALIB = (1971, 1999)
TEST_FROM = 2000

STATIONS = {
    "ybt": ("Youssef Ben Tachfine dam", "pluie-journaliere-du-barrage-y*", "rain"),
    "agadir": ("Agadir", "pluie-journaliere-de-la-station-abhsmd*", "rain"),
    "talaint_rain": ("Talaint", "pluie-journaliere-de-la-station-talaint*", "rain"),
    "aitmelloul_rain": ("Aït Melloul", "pluie-journaliere-de-la-station-ait*", "rain"),
    "aitmelloul_flow": ("Aït Melloul (river flow)", "debit-moyen-journalier-de-la-station-ait*", "flow"),
    "talaint_flow": ("Talaint (river flow)", "debit-moyen-journalier-de-la-station-talaint*", "flow"),
}
DATASETS = (
    "pluie-journaliere-du-barrage-y-b-tachfine*",
    "pluie-journaliere-de-la-station-abhsmd*",
    "pluie-journaliere-de-la-station-talaint*",
    "pluie-journaliere-de-la-station-ait-melloul*",
    "debit-moyen-journalier-de-la-station-ait-melloul*",
    "debit-moyen-journalier-de-la-station-talaint*",
)


def load(st: DatasetStore, key: str) -> pd.Series:
    _, pattern, kind = STATIONS[key]
    df = schemas.daily(abh.station_daily(st.files(ABH + pattern + "/*.xlsx"), kind))
    return df.set_index("date")["value"]


def _i(x: Any) -> int:
    return int(cast(int, x))


def _fmt(v: float, d: int = 1) -> str:
    return f"{v:,.{d}f}".replace("-", "−")


def analyse(daily: dict[str, pd.Series]) -> dict[str, Any]:
    """Every published series and number, from the daily station data (pure)."""
    rain = daily["ybt"]
    years = water.year_completeness(rain)
    last = water.last_complete_year(years)
    years = years[years.index <= last + 1]  # keep the partial latest year visible as excluded
    monthly = water.monthly_totals(rain)
    spis = {k: water.spi(monthly, k, end=last) for k in (3, 6, 12)}
    spi12 = spis[12]
    aug = spi12[pd.DatetimeIndex(spi12.index).month == 8].dropna()
    annual = water.annual_totals(rain, years)
    annual = annual[annual.index <= last]
    tr = water.trend(annual)
    cp = water.change_point(annual)

    flow_d = daily["aitmelloul_flow"]
    fyears = water.year_completeness(flow_d)
    flow = water.annual_means(flow_d, fyears)
    both = pd.concat([annual.rename("rain"), flow.rename("flow")], axis=1, join="inner").dropna()
    both = both[both.index >= CALIB[0]]
    rr = water.rain_vs_river(both, CALIB, TEST_FROM)

    decades = water.dry_years_by_decade(aug)
    years_per_decade = {_i(k): int(v) for k, v in pd.Series(pd.DatetimeIndex(aug.index).year // 10 * 10).value_counts().items()}
    spells = {}
    for dec in decades:
        part = rain[(rain.index >= f"{dec - 1}-09-01") & (rain.index < f"{dec + 9}-09-01")]
        spells[dec] = water.longest_dry_spell(part)

    checks = []
    for key in ("agadir", "aitmelloul_rain", "talaint_rain"):
        other = daily[key]
        oy = water.year_completeness(other)
        r, n = water.correlation(annual, water.annual_totals(other, oy))
        checks.append({"station": STATIONS[key][0], "r": round(r, 2), "years": n})

    slope = tr.slope_per_decade / 10
    intercept = float((annual - slope * annual.index.to_numpy(dtype=float)).median())  # Sen's line
    driest = aug.idxmin()
    latest_date = pd.Timestamp(spi12.dropna().index.max())
    excluded = years[~years["complete"]]
    summary = {
        "first_year": int(annual.index.min()),
        "last_year": last,
        "years_total": len(years),
        "years_complete": int(years["complete"].sum()),
        "excluded": [[_i(y), int(r.missing_days), int(r.bad_months)] for y, r in excluded.iterrows()],
        "spi12_latest": round(float(spi12.dropna().iloc[-1]), 2),
        "spi12_latest_month": latest_date.strftime("%Y-%m"),
        "spi12_latest_class": water.spi_class(float(spi12.dropna().iloc[-1])),
        "dry_years": int((aug <= -1).sum()),
        "years_with_spi": len(aug),
        "driest_year": int(pd.Timestamp(cast(str, driest)).year),
        "driest_spi": round(float(aug.min()), 2),
        "rain_mean": round(float(annual.mean()), 1),
        "trend_mm_per_decade": round(tr.slope_per_decade, 1),
        "trend_p": round(tr.p, 3),
        "trend_s": tr.s,
        "trend_p_corrected": [round(tr.p_range[0], 3), round(tr.p_range[1], 3)],
        "trend_robust": tr.robust,
        "trend_n": tr.n,
        "trend_direction": tr.direction,
        "trend_pct_per_decade": round(tr.slope_per_decade / float(annual.mean()) * 100, 1),
        "pettitt_year": cp.year,
        "pettitt_p": round(cp.p, 3),
        "flow_before": round(rr.observed_before, 2),
        "flow_after": round(rr.observed_after, 2),
        "flow_pred_after": round(rr.predicted_after, 2),
        "flow_pred_after_linear": round(rr.predicted_after_linear, 2),
        "share_ratio_pct": round(rr.share_explained_ratio * 100),
        "share_linear_pct": round(rr.share_explained_linear * 100),
        "runoff_ratio": round(rr.ratio, 4),
        "flow_years": [int(both.index.min()), int(both.index.max())],
        "flow_years_n": len(both),
        "dry_decade_max": max(decades, key=lambda d: (decades[d], d)),
        "longest_spell": max(spells.values()),
        "longest_spell_decade": max(spells, key=lambda d: (spells[d], d)),
    }
    return {
        "station": STATIONS["ybt"][0],
        "spi": {str(k): water.as_points(v) for k, v in spis.items()},
        "annual": [[_i(y), float(v)] for y, v in annual.items()],
        "trend_line": [[t, round(intercept + slope * t, 1)] for t in (int(annual.index.min()), last)],
        "river": [
            [_i(y), round(float(r.flow), 3), round(float(rr.predicted[_i(y)]), 3), float(r.rain)] for y, r in both.iterrows()
        ],
        "decades": [[d, decades[d], years_per_decade.get(d, 0), spells[d]] for d in sorted(decades)],
        "completeness": [
            [_i(y), int(r.days), int(r.missing_days), int(r.bad_months), bool(r.complete)] for y, r in years.iterrows()
        ],
        "crosscheck": checks,
        "summary": summary,
    }


def text(s: dict[str, Any]) -> dict[str, str]:
    """Sentences' numbers and words, formatted from the summary (so the text follows the data)."""
    months = [
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
    y, m = s["spi12_latest_month"].split("-")
    sig = s["trend_p"] < 0.05
    direction = "falling" if s["trend_mm_per_decade"] < 0 else "rising"
    trend_words = (direction if s["trend_robust"] else f"probably {direction}") if sig else "not clearly changing"
    pettitt = (
        f"The Pettitt test puts the shift in rainfall around {s['pettitt_year']} (p = {s['pettitt_p']:.2f})."
        if s["pettitt_p"] < 0.05
        else f"There is no single year when it shifted: the Pettitt test is not significant (p = {s['pettitt_p']:.2f}), "
        "so the decline is gradual and uneven rather than a step."
    )
    excluded = ", ".join(f"{e[0] - 1}–{str(e[0])[2:]}" for e in s["excluded"])
    return {
        "latest_month": f"{months[int(m) - 1]} {y}",
        "spi_latest": _fmt(s["spi12_latest"], 2),
        "spi_class": s["spi12_latest_class"],
        "first_year": str(s["first_year"]),
        "last_year": str(s["last_year"]),
        "dry_years": str(s["dry_years"]),
        "years_with_spi": str(s["years_with_spi"]),
        "driest_year": f"{s['driest_year'] - 1}–{str(s['driest_year'])[2:]}",
        "driest_spi": _fmt(s["driest_spi"], 2),
        "rain_mean": _fmt(s["rain_mean"], 0),
        "trend_abs": _fmt(abs(s["trend_mm_per_decade"]), 0),
        "trend_words": trend_words,
        "trend_pct": _fmt(abs(s["trend_pct_per_decade"]), 0),
        "trend_p": f"{s['trend_p']:.2f}",
        "trend_sig": "significant at the 5% level" if sig else "not significant",
        "trend_p_lo": f"{s['trend_p_corrected'][0]:.2f}",
        "trend_p_hi": f"{s['trend_p_corrected'][1]:.2f}",
        "trend_verdict": (
            "The fall holds whichever version is used."
            if s["trend_robust"]
            else "So treat the fall as likely, not certain."
            if sig
            else "So there is no firm evidence of a trend."
        ),
        "pettitt": pettitt,
        "flow_before": _fmt(s["flow_before"], 1),
        "flow_after": _fmt(s["flow_after"], 1),
        "flow_pred": _fmt(s["flow_pred_after"], 1),
        "flow_pred_lin": _fmt(s["flow_pred_after_linear"], 1),
        "share_ratio": str(s["share_ratio_pct"]),
        "share_linear": str(s["share_linear_pct"]),
        "flow_last": str(s["flow_years"][1]),
        "dry_decade": f"{s['dry_decade_max']}s",
        "longest_spell": str(s["longest_spell"]),
        "longest_spell_decade": f"{s['longest_spell_decade']}s",
        "years_complete": str(s["years_complete"]),
        "years_total": str(s["years_total"]),
        "excluded": excluded,
    }


def build(st: DatasetStore, updated: str | None = None) -> dict[str, Any]:
    daily = {k: load(st, k) for k in STATIONS}
    out = analyse(daily)
    out["text"] = text(out["summary"])
    out["src"] = {k: st.source(ABH + p).as_dict() for k, (_, p, _) in STATIONS.items()}
    out["updated"] = updated or os.environ.get("DATA_DATE") or datetime.date.today().isoformat()
    data_export.write_csv(
        CSV_FILE,
        [
            {"hydro_year": r[0], "rain_mm_ybt_dam": r[3], "flow_m3s_ait_melloul": r[1], "flow_rain_only_model_m3s": r[2]}
            for r in out["river"]
        ],
        ["hydro_year", "rain_mm_ybt_dam", "flow_m3s_ait_melloul", "flow_rain_only_model_m3s"],
    )
    return out


def render(data: dict[str, Any], nav: str = "") -> str:
    return site.render_page("water.html", data, nav)


def _s(key: str) -> Any:
    return lambda d: d["summary"][key]


CLAIMS: list[Claim] = [
    Claim("Complete hydrological years", _s("years_complete"), 49, 0),
    Claim("Last complete hydrological year", _s("last_year"), 2024, 0),
    Claim("12-month SPI, August 2024", _s("spi12_latest"), -0.58, 0.25),
    Claim("Dry years (SPI-12 <= -1 in August)", _s("dry_years"), 13, 0),
    Claim("Years with an August SPI-12", _s("years_with_spi"), 49, 0),
    Claim("Driest year (end of hydrological year)", _s("driest_year"), 2012, 0),
    Claim("Driest year SPI-12", _s("driest_spi"), -1.66, 0.1),
    Claim("Mean annual rainfall (mm)", _s("rain_mean"), 146, 2),
    Claim("Rainfall trend (mm per decade, 'about 14')", _s("trend_mm_per_decade"), -13.5, 1.0),
    Claim("Rainfall trend is significant, original test (p < 0.05)", _s("trend_p"), 0.025, 0.025),
    Claim(
        "Persistence-corrected tests disagree (highest p >= 0.05, 'likely, not certain')",
        lambda d: d["summary"]["trend_p_corrected"][1],
        0.5,
        0.45,
    ),
    Claim("Rainfall trend as % of mean per decade ('about 9%')", _s("trend_pct_per_decade"), -9.2, 0.8),
    Claim("No significant change point (Pettitt p >= 0.05)", _s("pettitt_p"), 0.5, 0.45),
    Claim("Flow 1971-1999 (m3/s, 'about 6.5')", _s("flow_before"), 6.54, 0.1),
    Claim("Flow 2000-2024 (m3/s, 'about 1.2')", _s("flow_after"), 1.2, 0.1),
    Claim("Rain-only prediction 2000-2024 (m3/s)", _s("flow_pred_after"), 5.33, 0.1),
    Claim("Rain-only prediction, linear (m3/s)", _s("flow_pred_after_linear"), 4.64, 0.1),
    Claim("Share of decline explained by rain (%, 'about a quarter')", _s("share_ratio_pct"), 23, 3),
    Claim("Share explained, linear fit (%, 'about a third')", _s("share_linear_pct"), 36, 3),
    Claim("Longest dry spell (days)", _s("longest_spell"), 313, 0),
    Claim("Decade with most dry years", _s("dry_decade_max"), 2000, 0),
]
