"""Drought monitor analyses: completeness, SPI, trends, rain versus river, dry spells."""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy import stats

from mbn.analyses import water


def _series(values: list[float], start: str = "2000-09-01") -> pd.Series:
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="D"), dtype=float)


# --- completeness --------------------------------------------------------------------------
def test_month_with_more_than_three_missing_days_has_no_total() -> None:
    s = _series([1.0] * 30)  # September 2000
    s.iloc[:4] = np.nan
    assert np.isnan(water.monthly_totals(s).iloc[0])
    s.iloc[0] = 1.0  # three missing: kept, total of the days present
    assert water.monthly_totals(s).iloc[0] == 27.0


def test_year_completeness_counts_missing_days_and_bad_months() -> None:
    s = _series([0.0] * 365)  # hydrological year 2001
    s.iloc[40:45] = np.nan  # 5 days in October
    y = water.year_completeness(s)
    assert y.loc[2001, "missing_days"] == 5
    assert y.loc[2001, "bad_months"] == 1
    assert not y.loc[2001, "complete"]


def test_constant_runs_flag_stuck_sensors() -> None:
    s = _series([0, 0, 0, 0, 5.2, 5.2, 5.2, 5.2, 1, 0])
    assert water.stuck_runs(s, min_len=3) == [(pd.Timestamp("2000-09-05"), 4, 5.2)]


def test_annual_totals_only_for_complete_years() -> None:
    s = _series([1.0] * 365 + [1.0] * 10)
    a = water.annual_totals(s, water.year_completeness(s))
    assert a.to_dict() == {2001: 365.0}


# --- SPI ----------------------------------------------------------------------------------------
def _monthly(years: int = 40, seed: int = 3) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1970-01-01", periods=12 * years, freq="MS")
    return pd.Series(rng.gamma(2.0, 20.0, len(idx)), index=idx)


def test_spi_matches_a_hand_computed_gamma_case() -> None:
    m = _monthly()
    spi1 = water.spi(m, 1)
    jan = m[m.index.month == 1]
    a, _, scale = stats.gamma.fit(jan.values, floc=0)
    expected = stats.norm.ppf(stats.gamma.cdf(jan.values, a, scale=scale))
    got = spi1[spi1.index.month == 1].values
    assert np.allclose(got, expected, atol=0.05)


def test_spi_is_standardised() -> None:
    s = water.spi(_monthly(), 12).dropna()
    assert abs(s.mean()) < 0.1 and 0.9 < s.std() < 1.1


@settings(max_examples=15, deadline=None)
@given(st.floats(0.1, 50))
def test_spi_is_unchanged_when_every_month_is_scaled(k: float) -> None:
    """Gamma SPI compares each month with its own reference years, so a unit change cannot move it.

    (Adding a constant does change a gamma fit's shape, so the additive version of this rule
    in the plan does not hold for SPI; scaling is the invariance that does.)
    """
    m = _monthly(30)
    assert np.allclose(water.spi(m, 6).dropna(), water.spi(m * k, 6).dropna(), atol=0.02)


@pytest.mark.parametrize(
    "value,label",
    [(2.1, "extremely wet"), (-0.5, "near normal"), (-1.2, "moderately dry"), (-1.7, "severely dry"), (-2.4, "extremely dry")],
)
def test_wmo_classes(value: float, label: str) -> None:
    assert water.spi_class(value) == label


# --- trend tests --------------------------------------------------------------------------------
def _sen_textbook(y: np.ndarray) -> float:
    return float(np.median([(y[j] - y[i]) / (j - i) for i, j in itertools.combinations(range(len(y)), 2)]))


def _mk_s_textbook(y: np.ndarray) -> int:
    return int(sum(np.sign(y[j] - y[i]) for i, j in itertools.combinations(range(len(y)), 2)))


def test_trend_matches_an_independent_textbook_computation() -> None:
    """Golden: pymannkendall's S and Sen's slope equal a from-scratch computation on fixed data."""
    y = np.array([210.0, 180, 175, 160, 190, 150, 120, 140, 130, 100, 115, 95, 160, 90, 85])
    t = water.trend(pd.Series(y, index=range(2000, 2015)))
    assert t.s == _mk_s_textbook(y) == -78
    assert t.slope_per_decade == pytest.approx(_sen_textbook(y) * 10)
    assert t.direction == "decreasing" and t.significant


@settings(max_examples=25, deadline=None)
@given(st.lists(st.floats(0, 500, allow_nan=False), min_size=10, max_size=40, unique=True))
def test_trend_sign_flips_when_the_series_is_reversed(values: list[float]) -> None:
    fwd = water.trend(pd.Series(values, index=range(len(values))))
    rev = water.trend(pd.Series(values[::-1], index=range(len(values))))
    assert fwd.slope_per_decade == pytest.approx(-rev.slope_per_decade, abs=1e-9)
    assert fwd.s == -rev.s


def test_change_point_is_found_in_a_step() -> None:
    y = pd.Series([200.0] * 15 + [100.0] * 15, index=range(1970, 2000)) + np.random.default_rng(0).normal(0, 5, 30)
    cp = water.change_point(y)
    assert cp.significant and cp.year in (1984, 1985)


# --- rain versus river ---------------------------------------------------------------------------
def test_rain_vs_river_when_rain_explains_nothing() -> None:
    years = np.arange(1971, 2025)
    rain = np.full(len(years), 150.0) + np.random.default_rng(2).normal(0, 1, len(years))
    flow = np.where(years >= 2000, 1.0, 6.0)
    m = water.rain_vs_river(pd.DataFrame({"rain": rain, "flow": flow}, index=years), (1971, 1999), 2000)
    assert abs(m.share_explained_ratio) < 0.05
    assert m.observed_after < m.predicted_after


# --- extremes ------------------------------------------------------------------------------------
def test_longest_dry_spell_is_broken_by_missing_days() -> None:
    s = _series([5, 0, 0, 0, 0.5, 0, np.nan, 0, 0, 3])
    assert water.longest_dry_spell(s, wet_mm=1.0) == 5


def test_dry_years_by_decade() -> None:
    spi = pd.Series([-1.5, 0.2, -1.0, -2.0], index=pd.to_datetime(["1975-08-01", "1985-08-01", "1986-08-01", "1999-08-01"]))
    assert water.dry_years_by_decade(spi) == {1970: 1, 1980: 1, 1990: 1}


# --- parsing and rendering --------------------------------------------------------------------
def test_station_daily_joins_yearly_files_and_skips_templates(fixtures, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from mbn.parsers import abh

    blank = tmp_path / "precip.xlsx"
    pd.DataFrame([["Jour", "Mois", "Valeur"]]).to_excel(blank, header=False, index=False)
    df = abh.station_daily([str(fixtures / "abh_rain.xlsx"), str(blank)], "rain")
    assert df["date"].min() == pd.Timestamp("2022-09-01") and len(df) == 365
    assert df["value"].sum() == pytest.approx(118.7)
    flow = abh.station_daily([str(fixtures / "debits-moyens-journaliers_ait-melloul-_-2023-2024.xlsx")], "flow")
    assert len(flow) == 366
    assert abh.station_daily([], "rain").empty


def test_page_text_never_shows_a_blank() -> None:
    from mbn.publish import site

    assert "<p>7</p>" in site.render_page("x.html", {"text": {"n": "7"}}, template="<p>{{n}}</p>")
    with pytest.raises(KeyError):
        site.render_page("x.html", {"text": {}}, template="<p>{{n}}</p>")


def test_water_text_follows_the_numbers() -> None:
    from mbn.findings import water_page
    from mbn.publish import data_export

    s = dict(data_export.read_json(water_page.DATA_FILE)["summary"])
    assert water_page.text(s)["trend_words"] == "probably falling"
    s.update(trend_p=0.2)
    assert water_page.text(s)["trend_words"] == "not clearly changing"
    s.update(trend_p=0.01, trend_robust=True, pettitt_p=0.01)
    t = water_page.text(s)
    assert t["trend_words"] == "falling" and "puts the shift" in t["pettitt"]
