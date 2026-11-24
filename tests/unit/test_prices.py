"""Price monitor analyses: growth rates, implied weights, contributions, anomalies, clusters, forecasts."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mbn.analyses import prices

MONTHS = pd.date_range("2017-01-01", periods=60, freq="MS")


def _wide(seed: int = 0, weights: tuple[float, ...] = (0.5, 0.3, 0.2)) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    comps = {f"0{i + 1}": 100 * np.cumprod(1 + rng.normal(0.002 * (i + 1), 0.01, len(MONTHS))) for i in range(len(weights))}
    df = pd.DataFrame(comps, index=MONTHS)
    df = df / df.iloc[:12].mean() * 100  # base 100 = average of the first year, like HCP's 2017 base
    df["GR"] = sum(w * df[k] for w, k in zip(weights, comps, strict=True))
    return df


# --- growth rates ------------------------------------------------------------------------------
def test_yoy_and_mom() -> None:
    ix = pd.Series([100.0] * 12 + [110.0], index=pd.date_range("2020-01-01", periods=13, freq="MS"))
    assert prices.yoy(ix).iloc[-1] == pytest.approx(10.0)
    assert prices.mom(ix).iloc[-1] == pytest.approx(10.0)
    assert prices.yoy(ix).iloc[:12].isna().all()


@given(st.floats(1, 1000), st.integers(13, 40))
def test_a_constant_index_gives_zero_inflation(v: float, n: int) -> None:
    ix = pd.Series(v, index=pd.date_range("2020-01-01", periods=n, freq="MS"))
    assert (prices.yoy(ix).dropna() == 0).all() and (prices.mom(ix).dropna() == 0).all()


@settings(deadline=None)
@given(st.lists(st.floats(-5, 5), min_size=2, max_size=60), st.floats(50, 200))
def test_index_and_growth_round_trip(changes: list[float], start: float) -> None:
    idx = pd.date_range("2020-01-01", periods=len(changes) + 1, freq="MS")
    ix = pd.Series(start * np.cumprod([1.0] + [1 + c / 100 for c in changes]), index=idx)
    rebuilt = prices.index_from_mom(prices.mom(ix), start)
    assert np.allclose(rebuilt.values, ix.values)


def test_three_month_annualised_rate() -> None:
    ix = pd.Series(100 * 1.01 ** np.arange(40), index=pd.date_range("2020-01-01", periods=40, freq="MS"))
    rate = prices.annualised_3m(ix).dropna()
    assert np.allclose(rate, (1.01**12 - 1) * 100)


# --- weights and contributions -------------------------------------------------------------------
def test_implied_weights_recover_the_basket() -> None:
    w = prices.implied_weights(_wide(), ["01", "02", "03"], "GR")
    assert w.weights.round(4).to_dict() == {"01": 0.5, "02": 0.3, "03": 0.2}
    assert w.max_residual < 1e-6
    assert w.half_sample_gap < 1e-3


@settings(max_examples=20, deadline=None)
@given(st.integers(0, 10_000), st.lists(st.floats(0.05, 1), min_size=3, max_size=3))
def test_contributions_add_up_to_the_headline_rate(seed: int, raw: list[float]) -> None:
    w = np.array(raw) / sum(raw)
    df = _wide(seed, tuple(w))
    c = prices.contributions(df, pd.Series(w, index=["01", "02", "03"]), "GR")
    assert np.allclose(c.sum(axis=1, min_count=1).dropna(), prices.yoy(df["GR"]).dropna(), atol=1e-9)


# --- anomalies and clusters ----------------------------------------------------------------------
def test_robust_z_is_not_masked_by_another_spike() -> None:
    x = pd.Series([0.1, -0.1, 0.2, 0.0, 0.1, -0.2, 0.0, 0.1, 30.0, 0.1, 0.0, 8.0])
    z = prices.robust_z(x)
    assert z.iloc[-1] > 20  # the mean/sd version would hide it behind the 30% spike
    sd = (x - x.mean()) / x.std()
    assert sd.iloc[-1] < 1


def test_robust_z_of_a_flat_series_is_zero() -> None:
    assert (prices.robust_z(pd.Series([0.0, 0.0, 0.0])) == 0).all()


def test_cities_that_move_together_cluster_together() -> None:
    rng = np.random.default_rng(4)
    a, b = rng.normal(0, 1, 80), rng.normal(0, 1, 80)
    df = pd.DataFrame(
        {
            "A1": a + rng.normal(0, 0.1, 80),
            "A2": a + rng.normal(0, 0.1, 80),
            "B1": b + rng.normal(0, 0.1, 80),
            "B2": b + rng.normal(0, 0.1, 80),
        }
    )
    groups = prices.cluster(df, k=2)
    assert groups["A1"] == groups["A2"] != groups["B1"] == groups["B2"]


def test_seasonal_adjustment_removes_a_fixed_pattern() -> None:
    idx = pd.date_range("2015-01-01", periods=96, freq="MS")
    season = np.tile([0, 1, 2, 1, 0, -1, -2, -1, 0, 1, 0, -1], 8) / 100
    ix = pd.Series(100 * np.exp(0.002 * np.arange(96) + season), index=idx)
    sa = prices.seasonally_adjusted(ix)
    assert np.std(np.diff(np.log(sa.values))) < np.std(np.diff(np.log(ix.values))) / 3


# --- forecasts -----------------------------------------------------------------------------------
def test_backtest_runs_every_model_on_a_rolling_origin() -> None:
    ix = pd.Series(
        100 * np.exp(0.003 * np.arange(84) + np.tile(np.sin(np.arange(12)) / 200, 7)),
        index=pd.date_range("2017-01-01", periods=84, freq="MS"),
    )
    bt = prices.backtest(ix, horizon=3, origins=12)
    assert set(bt.mae) == {"seasonal naive", "ETS", "ARIMA"}
    assert all(v >= 0 for v in bt.mae.values())
    assert len(bt.errors) == 12 * 3


def test_forecast_decision_needs_a_strict_win() -> None:
    assert prices.forecast_decision({"seasonal naive": 0.5, "ETS": 0.5}).model is None
    d = prices.forecast_decision({"seasonal naive": 0.5, "ETS": 0.4, "ARIMA": 0.3})
    assert d.model == "ARIMA" and d.improvement == pytest.approx(0.4)
