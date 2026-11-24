from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from pytest_bdd import given, parsers, scenarios, then, when

from mbn.analyses import water
from mbn.findings import water_page
from mbn.publish import claims, data_export

scenarios("drought.feature")


def _daily(start: int, end: int) -> pd.Series:
    """Hydrological years start..end (Sep start-1 .. Aug end) with seasonal synthetic rain."""
    idx = pd.date_range(f"{start - 1}-09-01", f"{end}-08-31", freq="D")
    rng = np.random.default_rng(7)
    wet = np.isin(idx.month, [11, 12, 1, 2, 3])
    values = np.where(wet & (rng.random(len(idx)) < 0.2), rng.gamma(2.0, 6.0, len(idx)), 0.0)
    return pd.Series(values, index=idx)


@given(
    parsers.parse("daily rainfall from {a:d} to {b:d} where hydrological year {y:d} has {n:d} missing days"),
    target_fixture="rain",
)
def rain_with_gap(a: int, b: int, y: int, n: int) -> pd.Series:
    s = _daily(a, b)
    days = s[(s.index >= f"{y - 1}-10-01")].index[:n]
    s[days] = np.nan
    return s


@given(
    parsers.parse("daily rainfall from {a:d} to {b:d} where the last hydrological year stops in December"), target_fixture="rain"
)
def rain_partial(a: int, b: int) -> pd.Series:
    s = _daily(a, b)
    s[s.index >= f"{b}-01-01"] = np.nan
    return s


@when("the drought index is computed", target_fixture="result")
def compute(rain: pd.Series) -> dict[str, Any]:
    monthly = water.monthly_totals(rain)
    years = water.year_completeness(rain)
    last = water.last_complete_year(years)
    spi12 = water.spi(monthly, 12, end=last)
    return {"years": years, "spi12": spi12}


@then(parsers.parse("hydrological year {y:d} has no 12-month SPI"))
def no_spi(result: dict[str, Any], y: int) -> None:
    assert np.isnan(result["spi12"].get(pd.Timestamp(f"{y}-08-01"), np.nan))


@then(parsers.parse("hydrological year {y:d} is listed as excluded, with {n:d} missing days"))
def excluded_with(result: dict[str, Any], y: int, n: int) -> None:
    row = result["years"].loc[y]
    assert not row["complete"] and row["missing_days"] == n


@then(parsers.parse("hydrological year {y:d} is listed as excluded"))
def excluded(result: dict[str, Any], y: int) -> None:
    assert not result["years"].loc[y, "complete"]


@then(parsers.parse("the drought series ends in August {y:d}"))
def ends(result: dict[str, Any], y: int) -> None:
    assert result["spi12"].index.max() == pd.Timestamp(f"{y}-08-01")


@given("a river that always carries the same share of the rain", target_fixture="k")
def share() -> float:
    return 0.04


@given("rainfall halves after 1999", target_fixture="annual")
def halves(k: float) -> pd.DataFrame:
    years = np.arange(1971, 2025)
    rng = np.random.default_rng(1)
    rain = rng.uniform(100, 200, len(years)) * np.where(years >= 2000, 0.5, 1.0)
    return pd.DataFrame({"rain": rain, "flow": k * rain}, index=years)


@when("the rain-only model is fitted on 1971 to 1999", target_fixture="model")
def fit(annual: pd.DataFrame) -> water.RainRiver:
    return water.rain_vs_river(annual, calib=(1971, 1999), test_from=2000)


@then(parsers.parse("rain explains {pct:d}% of the river's decline"))
def explains(model: water.RainRiver, pct: int) -> None:
    assert abs(model.share_explained_ratio * 100 - pct) < 1e-6


@given("the built water page data", target_fixture="data")
def built() -> dict[str, Any]:
    return data_export.read_json(water_page.DATA_FILE)  # type: ignore[no-any-return]


@then("every claim of the water page holds")
def holds(data: dict[str, Any]) -> None:
    lines, failed = claims.check(water_page.CLAIMS, data)
    assert failed == 0, "\n".join(lines)
