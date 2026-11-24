from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from mbn.analyses import findings as an


def test_yoy_quarterly() -> None:
    levels = {(2019, 1): 100.0, (2020, 1): 90.0, (2020, 2): 50.0}
    assert an.yoy(levels, 4) == [[2020.0, -10.0]]


def test_cpi_yoy_uses_french_month_tokens() -> None:
    assert an.cpi_yoy({"Févr-2022": 100.0, "Févr-2023": 120.8}) == [(2023 + 1 / 12, 20.8)]


def test_chron_quarters_sorts_and_drops_gaps() -> None:
    assert an.chron_quarters({"T2-2018": 2.0, "T1-2018": 1.0, "T3-2018": None}) == [(2018.0, 1.0), (2018.25, 2.0)]


def test_credit_growth_from_month_series() -> None:
    idx = pd.MultiIndex.from_tuples([(2020, 1), (2021, 1), (2021, 2)])
    s = pd.Series([1000.0, 1100.0, 1200.0], index=idx)
    assert an.credit_growth(s) == [[2021.0, 10.0, 1]]


def test_funds_keep_last_report_per_month_from_first_full_year() -> None:
    weekly = [[f"2019-12-{d:02d}", 1.0] for d in (1, 8)] + [[f"2020-{m:02d}-0{w}", float(m)] for m in range(1, 7) for w in (1, 8)]
    series, note = an.funds_monthly(weekly)
    assert note["start"] == "2020"
    assert series[0] == [2020.0, 1.0] and len(series) == 6


def test_parliament_themes_group_ministries() -> None:
    themes, unmapped = an.parliament_themes({"وزارة الداخلية": 5, "وزارة الصحة والحماية الاجتماعية": 3, "وزارة مجهولة": 1})
    assert themes == [["Interior", 5], ["Health and social protection", 3]]
    assert unmapped == 1


def test_startup_city_spellings_are_merged() -> None:
    assert an.startup_cities({"casablanca": 5, "tanger": 1, "tangier": 2}) == [("casablanca", 5), ("tanger", 3)]


def test_services_rates_and_totals() -> None:
    s3: dict[str, Any] = {
        "primary_care": {"A": 10},
        "hospitals": {"A": 1},
        "schools_primary": {"A": 100},
        "schools_middle": {},
        "schools_high": {},
    }
    rows, totals = an.services(s3, {"A": 200_000, "B": 100_000})
    assert rows[0] == ["A", 5.0, 5.0, 50.0, 200_000]
    assert rows[1][1] == 0
    assert totals["primary_care"] == 10


def test_jsonify_turns_keys_into_strings() -> None:
    assert an.jsonify({1: (1, 2)}) == {"1": [1, 2]}


def test_pack_key_order_matches_published_file(golden_data: dict[str, Any]) -> None:
    keys = list(golden_data)
    assert keys[:3] == ["flow", "rain", "cereals"] and keys[-1] == "updated"
    assert keys.index("src") < keys.index("gdp_growth") < keys.index("services")


@pytest.mark.parametrize("months,kept", [(10, False), (11, True)])
def test_rain_years_need_eleven_months(months: int, kept: bool) -> None:
    raw: dict[str, Any] = {
        "rain": {"2000": [100.0, months]},
        "flow": {},
        "crops": {"Céréales": {}},
        "unemp_q": {},
        "region_unemp": [],
        "region_unemp_women": [],
        "prov_unemp": [],
        "cpi": {"(GR) GENERAL": {}, "(01) PRODUITS ALIMENTAIRES ET BOISSONS NON ALCOOLISÉES": {}},
        "amo": {},
        "mobile": {},
        "internet": {},
        "roads": {},
        "cpi_corr": [],
    }
    assert (an.build_main(raw, {})["rain"] == [(2000, 100.0)]) is kept
