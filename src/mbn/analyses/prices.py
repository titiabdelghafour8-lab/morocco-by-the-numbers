"""Price monitor: growth rates, implied basket weights, contributions, anomalies, city clusters, forecasts.

Pure functions on monthly index Series (DatetimeIndex at month starts) and wide tables
(one column per product or city).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np
import pandas as pd

BASELINE = "seasonal naive"


def yoy(ix: pd.Series) -> pd.Series:
    """% change on the same month a year earlier."""
    return (ix / ix.shift(12) - 1) * 100


def mom(ix: pd.Series) -> pd.Series:
    """% change on the previous month."""
    return (ix / ix.shift(1) - 1) * 100


def index_from_mom(changes: pd.Series, start: float) -> pd.Series:
    """Rebuild an index from its monthly % changes (the first change is ignored)."""
    factors = (1 + changes.fillna(0) / 100).to_numpy(dtype=float)
    factors[0] = 1.0
    return pd.Series(start * np.cumprod(factors), index=changes.index)


def annualised_3m(ix: pd.Series) -> pd.Series:
    """Change over three months, compounded to a yearly rate (use on a seasonally adjusted index)."""
    return ((ix / ix.shift(3)) ** 4 - 1) * 100


def seasonally_adjusted(ix: pd.Series) -> pd.Series:
    """Index with its seasonal pattern removed (robust STL on the log index, period 12)."""
    from statsmodels.tsa.seasonal import STL

    logs = np.log(ix.astype(float))
    res = STL(logs, period=12, robust=True).fit()
    return cast(pd.Series, np.exp(logs - res.seasonal))


# --- weights and contributions --------------------------------------------------------------------
@dataclass(frozen=True)
class ImpliedWeights:
    weights: pd.Series
    """Share of each component in the basket (sums to about 1)."""
    max_residual: float
    """Largest gap, in index points, between the headline and the weighted components."""
    half_sample_gap: float
    """Largest difference in a weight fitted on the first and on the second half of the months."""


def _nnls(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    from scipy.optimize import nnls

    coef, _ = nnls(x, y)
    return cast(np.ndarray, coef)


def implied_weights(wide: pd.DataFrame, components: list[str], total: str) -> ImpliedWeights:
    """Weights that rebuild the headline index from its components (non-negative least squares).

    A fixed-base (Laspeyres) index is a weighted sum of its components, so when the fit is
    exact up to rounding, these are the basket weights.
    """
    df = wide[[*components, total]].dropna()
    x, y = df[components].to_numpy(dtype=float), df[total].to_numpy(dtype=float)
    coef = _nnls(x, y)
    half = len(df) // 2
    gap = float(np.abs(_nnls(x[:half], y[:half]) - _nnls(x[half:], y[half:])).max())
    return ImpliedWeights(pd.Series(coef, index=components), float(np.abs(x @ coef - y).max()), gap)


def contributions(wide: pd.DataFrame, weights: pd.Series, total: str, lag: int = 12) -> pd.DataFrame:
    """Percentage points each component adds to the headline's change over ``lag`` months."""
    comp = wide[list(weights.index)]
    return comp.sub(comp.shift(lag)).mul(weights, axis=1).div(wide[total].shift(lag), axis=0) * 100


# --- anomalies and clusters ----------------------------------------------------------------------
def robust_z(x: pd.Series) -> pd.Series:
    """(x - median) / (1.4826 x median absolute deviation): one spike cannot hide another."""
    med = x.median()
    mad = (x - med).abs().median() * 1.4826
    if not mad:
        mad = (x - med).abs().mean() * 1.2533
    if not mad:
        return pd.Series(0.0, index=x.index)
    return (x - med) / mad


def cluster(changes: pd.DataFrame, k: int = 3) -> dict[str, int]:
    """Group columns by how they move together (average linkage on 1 - correlation)."""
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    dist = 1 - changes.corr().to_numpy()
    np.fill_diagonal(dist, 0)
    z = linkage(squareform(np.clip(dist, 0, None), checks=False), method="average")
    labels = fcluster(z, k, criterion="maxclust")
    return {str(c): int(g) for c, g in zip(changes.columns, labels, strict=True)}


# --- forecasts -----------------------------------------------------------------------------------
def _forecast_log(y: pd.Series, model: str, h: int) -> np.ndarray:
    """h-step forecast of a log index with one of three simple models."""
    v = y.to_numpy(dtype=float)
    if model == BASELINE:  # the same monthly changes as a year earlier
        d = np.diff(v)
        return cast(np.ndarray, v[-1] + np.cumsum([d[len(d) - 12 + j] for j in range(h)]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if model == "ETS":
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            fit = ExponentialSmoothing(v, trend="add", damped_trend=True, seasonal="add", seasonal_periods=12).fit()
            return cast(np.ndarray, np.asarray(fit.forecast(h)))
        if model == "ARIMA":
            from statsmodels.tsa.statespace.sarimax import SARIMAX

            fit = SARIMAX(v, order=(0, 1, 1), seasonal_order=(0, 1, 1, 12)).fit(disp=False)
            return cast(np.ndarray, np.asarray(fit.forecast(h)))
    raise ValueError(model)


MODELS = (BASELINE, "ETS", "ARIMA")


@dataclass(frozen=True)
class Backtest:
    mae: dict[str, float]
    """Mean absolute error of the forecast year-on-year rate, percentage points."""
    errors: list[tuple[str, str, float]] = field(default_factory=list)
    """(origin month, model, error) for every forecast."""
    horizon: int = 3


def forecast_yoy(ix: pd.Series, model: str, h: int) -> list[float]:
    """Year-on-year rate for each of the next h months, from a model of the log index."""
    logs = np.log(ix.astype(float))
    f = np.exp(_forecast_log(pd.Series(logs), model, h))
    base = ix.to_numpy(dtype=float)
    return [float((f[j] / base[len(base) - 12 + j] - 1) * 100) for j in range(h)]


def backtest(ix: pd.Series, horizon: int = 3, origins: int = 36, models: tuple[str, ...] = MODELS) -> Backtest:
    """Rolling-origin test: from each of the last ``origins`` months that still have an outcome,
    forecast ``horizon`` months ahead and score the year-on-year rate at that horizon."""
    n = len(ix)
    errors = []
    for t in range(n - horizon - origins + 1, n - horizon + 1):
        train = ix.iloc[:t]
        actual = float((ix.iloc[t + horizon - 1] / ix.iloc[t + horizon - 13] - 1) * 100)
        for m in models:
            pred = forecast_yoy(train, m, horizon)[-1]
            errors.append((str(pd.Timestamp(ix.index[t - 1]).date()), m, pred - actual))
    mae = {m: float(np.mean([abs(e) for _, mm, e in errors if mm == m])) for m in models}
    return Backtest(mae=mae, errors=errors, horizon=horizon)


@dataclass(frozen=True)
class ForecastDecision:
    model: str | None
    """The model to publish, or None when none beats the benchmark."""
    mae: dict[str, float]
    improvement: float
    """Fall in error against the benchmark (0.2 = 20% smaller), for the chosen model."""


def forecast_decision(mae: dict[str, float], baseline: str = BASELINE) -> ForecastDecision:
    """Publish the best model only if its error is strictly smaller than the benchmark's."""
    rivals = {m: e for m, e in mae.items() if m != baseline}
    best = min(rivals, key=lambda m: rivals[m]) if rivals else None
    if best is None or not rivals[best] < mae[baseline]:
        return ForecastDecision(None, mae, 0.0)
    return ForecastDecision(best, mae, 1 - rivals[best] / mae[baseline])


def points(s: pd.Series, digits: int = 1) -> list[list[Any]]:
    """Monthly series -> [[year + (month-1)/12, value]], dropping gaps."""
    s = s.dropna()
    idx = pd.DatetimeIndex(s.index)
    return [
        [round(float(y + (m - 1) / 12), 3), round(float(v), digits)]
        for y, m, v in zip(idx.year, idx.month, s.to_numpy(dtype=float), strict=True)
    ]
