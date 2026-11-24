"""Drought monitor: completeness, drought index (SPI), trends, rain versus river, dry spells.

Pure functions on pandas objects. Daily series are indexed by date; a hydrological year
runs from September to August and is named after the year it ends in (Sep 2023 - Aug 2024
is 2024), as the river basin agency names its files.
"""

from __future__ import annotations

import itertools
import logging
import warnings
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import pandas as pd

MAX_MISSING_PER_MONTH = 3
"""A month with more missing days than this has no total (and so no drought index)."""

WMO_CLASSES = [
    (2.0, "extremely wet"),
    (1.5, "very wet"),
    (1.0, "moderately wet"),
    (-0.99, "near normal"),
    (-1.49, "moderately dry"),
    (-1.99, "severely dry"),
]


def hydro_year(index: pd.DatetimeIndex) -> np.ndarray:
    """Hydrological year of each date (September starts the next year)."""
    return np.asarray(index.year + (index.month >= 9).astype(int))


def _full_days(daily: pd.Series) -> pd.Series:
    """The series on every calendar day of the hydrological years it touches (absent days -> NaN)."""
    idx = pd.DatetimeIndex(daily.index)
    years = hydro_year(idx)
    full = pd.date_range(f"{years.min() - 1}-09-01", f"{years.max()}-08-31", freq="D")
    return daily.reindex(full)


def monthly_totals(daily: pd.Series, max_missing: int = MAX_MISSING_PER_MONTH) -> pd.Series:
    """Monthly sums; NaN where more than ``max_missing`` days are missing."""
    s = _full_days(daily)
    g = s.resample("MS")
    total, present = g.sum(min_count=1), g.count()
    days = pd.Series(pd.DatetimeIndex(total.index).days_in_month, index=total.index)
    return total.where(days - present <= max_missing)


def year_completeness(daily: pd.Series, max_missing: int = MAX_MISSING_PER_MONTH) -> pd.DataFrame:
    """Per hydrological year: days, missing days, months over the missing-day limit, complete?"""
    s = _full_days(daily)
    idx = pd.DatetimeIndex(s.index)
    df = pd.DataFrame({"year": hydro_year(idx), "month": idx.to_period("M"), "missing": s.isna().to_numpy()})
    per_month = df.groupby(["year", "month"])["missing"].sum()
    out = pd.DataFrame(
        {
            "days": df.groupby("year").size(),
            "missing_days": df.groupby("year")["missing"].sum().astype(int),
            "bad_months": (per_month > max_missing).groupby(level=0).sum().astype(int),
        }
    )
    out["complete"] = out["bad_months"] == 0
    out.index.name = "year"
    return out


def last_complete_year(years: pd.DataFrame) -> int:
    return int(years.index[years["complete"]].max())


def annual_totals(daily: pd.Series, years: pd.DataFrame) -> pd.Series:
    """Rain per hydrological year, for complete years only."""
    s = _full_days(daily)
    tot = s.groupby(hydro_year(pd.DatetimeIndex(s.index))).sum(min_count=1)
    return tot[tot.index.isin(years.index[years["complete"]])].round(1)


def annual_means(daily: pd.Series, years: pd.DataFrame) -> pd.Series:
    """Mean daily value per hydrological year (river flow), for complete years only."""
    s = _full_days(daily)
    m = s.groupby(hydro_year(pd.DatetimeIndex(s.index))).mean()
    return m[m.index.isin(years.index[years["complete"]])]


def stuck_runs(daily: pd.Series, min_len: int = 3) -> list[tuple[pd.Timestamp, int, float]]:
    """Runs of the same non-zero value on ``min_len`` or more days in a row (a stuck gauge?)."""
    out = []
    vals = daily.to_numpy()
    idx = daily.index
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[i]:
            j += 1
        if vals[i] and not np.isnan(vals[i]) and j - i + 1 >= min_len:
            out.append((pd.Timestamp(idx[i]), j - i + 1, float(vals[i])))
        i = j + 1
    return out


# --- drought index ----------------------------------------------------------------------------
def spi(monthly: pd.Series, scale: int, end: int | None = None) -> pd.Series:
    """Standardized Precipitation Index (gamma fit, climate-indices reference implementation).

    Calibrated on every year in the series. ``end`` (a hydrological year) cuts the series at
    the end of that August, so a partial latest year never counts.
    """
    from climate_indices import compute, indices

    m = monthly.copy()
    if end is not None:
        m = m[m.index <= pd.Timestamp(f"{end}-08-01")]
    idx = pd.DatetimeIndex(m.index)
    first, last = int(idx.year.min()), int(idx.year.max())
    full = pd.date_range(f"{first}-01-01", f"{last}-12-01", freq="MS")
    values = m.reindex(full).to_numpy(dtype=float)
    logging.getLogger("climate_indices").setLevel(logging.WARNING)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = indices.spi(values, scale, indices.Distribution.gamma, first, first, last, compute.Periodicity.monthly)
    return pd.Series(out, index=full).reindex(m.index)


def spi_class(value: float) -> str:
    """WMO (2012) SPI category."""
    if value <= -2.0:
        return "extremely dry"
    for threshold, label in WMO_CLASSES:
        if value >= threshold:
            return label
    return "extremely dry"


# --- trends -------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Trend:
    s: int
    """Mann-Kendall S statistic."""
    p: float
    """p-value of the original Mann-Kendall test."""
    p_range: tuple[float, float]
    """Lowest and highest p-value of four versions that allow for year-to-year persistence
    (Hamed-Rao, Yue-Wang, pre-whitening, trend-free pre-whitening)."""
    slope_per_decade: float
    """Sen's slope on the actual years, times ten."""
    n: int

    @property
    def significant(self) -> bool:
        return self.p < 0.05

    @property
    def robust(self) -> bool:
        """Significant whichever persistence correction is used."""
        return self.significant and self.p_range[1] < 0.05

    @property
    def direction(self) -> str:
        if not self.significant:
            return "no significant trend"
        return "decreasing" if self.s < 0 else "increasing"


def sen_slope(series: pd.Series) -> float:
    t = np.asarray(series.index, dtype=float)
    y = series.to_numpy(dtype=float)
    return float(np.median([(y[j] - y[i]) / (t[j] - t[i]) for i, j in itertools.combinations(range(len(y)), 2)]))


def trend(series: pd.Series) -> Trend:
    """Mann-Kendall test (original and four persistence-corrected versions) and Sen's slope (gaps allowed)."""
    import pymannkendall as mk

    y = series.to_numpy(dtype=float)
    r = mk.original_test(y)
    ps = []
    for f in (
        mk.hamed_rao_modification_test,
        mk.yue_wang_modification_test,
        mk.pre_whitening_modification_test,
        mk.trend_free_pre_whitening_modification_test,
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            p = float(f(y).p)
        if not np.isnan(p):
            ps.append(p)
    p_range = (min(ps), max(ps)) if ps else (float("nan"), float("nan"))
    return Trend(s=int(r.s), p=float(r.p), p_range=p_range, slope_per_decade=sen_slope(series) * 10, n=len(series))


@dataclass(frozen=True)
class ChangePoint:
    year: int
    """First year of the new level."""
    p: float

    @property
    def significant(self) -> bool:
        return self.p < 0.05


def change_point(series: pd.Series) -> ChangePoint:
    """Pettitt test for a single shift in level."""
    import pyhomogeneity as hg

    r = hg.pettitt_test(series.to_numpy(dtype=float), sim=20000)
    return ChangePoint(year=int(series.index[int(r.cp)]), p=float(r.p))


# --- rain versus river --------------------------------------------------------------------------
@dataclass(frozen=True)
class RainRiver:
    ratio: float
    """Runoff ratio fitted on the calibration years: mean flow (m3/s) per mm of rain."""
    linear: tuple[float, float]
    """Slope and intercept of flow on rain, fitted on the calibration years (sensitivity check)."""
    observed_before: float
    observed_after: float
    predicted_after: float
    predicted_after_linear: float
    predicted: pd.Series
    """Rain-only prediction for every year (runoff ratio model)."""

    @property
    def share_explained_ratio(self) -> float:
        """Share of the fall in flow that the fall in rain explains (runoff ratio model)."""
        return (self.observed_before - self.predicted_after) / (self.observed_before - self.observed_after)

    @property
    def share_explained_linear(self) -> float:
        return (self.observed_before - self.predicted_after_linear) / (self.observed_before - self.observed_after)


def rain_vs_river(annual: pd.DataFrame, calib: tuple[int, int], test_from: int) -> RainRiver:
    """Fit flow on rain over ``calib`` years, predict later years, compare with what the river did.

    ``annual`` has columns ``rain`` (mm) and ``flow`` (m3/s) by hydrological year.
    """
    cal = annual[(annual.index >= calib[0]) & (annual.index <= calib[1])]
    after = annual[annual.index >= test_from]
    ratio = float(cal["flow"].sum() / cal["rain"].sum())
    slope, intercept = (float(v) for v in np.polyfit(cal["rain"], cal["flow"], 1))
    lin = np.maximum(0.0, slope * after["rain"] + intercept)
    return RainRiver(
        ratio=ratio,
        linear=(slope, intercept),
        observed_before=float(cal["flow"].mean()),
        observed_after=float(after["flow"].mean()),
        predicted_after=float((ratio * after["rain"]).mean()),
        predicted_after_linear=float(lin.mean()),
        predicted=ratio * annual["rain"],
    )


# --- extremes -----------------------------------------------------------------------------------
def longest_dry_spell(daily: pd.Series, wet_mm: float = 1.0) -> int:
    """Longest run of days with less than ``wet_mm`` of rain; a missing day ends a run."""
    best = run = 0
    for v in daily.to_numpy(dtype=float):
        if np.isnan(v) or v >= wet_mm:
            run = 0
        else:
            run += 1
            best = max(best, run)
    return best


def dry_years_by_decade(spi_end_of_year: pd.Series, threshold: float = -1.0) -> dict[int, int]:
    """Years whose 12-month SPI at the end of the hydrological year is at or below ``threshold``."""
    s = spi_end_of_year.dropna()
    decade = (pd.DatetimeIndex(s.index).year // 10) * 10
    return {int(cast(int, k)): int(v) for k, v in (s <= threshold).groupby(decade).sum().items()}


def correlation(a: pd.Series, b: pd.Series) -> tuple[float, int]:
    """Pearson correlation over the years both series have, and how many years that is."""
    both = pd.concat([a, b], axis=1, join="inner").dropna()
    return float(both.iloc[:, 0].corr(both.iloc[:, 1])), len(both)


def as_points(s: pd.Series, digits: int = 2) -> list[list[Any]]:
    """Monthly series -> [[year + (month-1)/12, value]] for the charts (NaN -> null)."""
    idx = pd.DatetimeIndex(s.index)
    xs = idx.year + (idx.month - 1) / 12
    return [
        [round(float(x), 3), None if np.isnan(v) else round(float(v), digits)]
        for x, v in zip(xs, s.to_numpy(dtype=float), strict=True)
    ]
