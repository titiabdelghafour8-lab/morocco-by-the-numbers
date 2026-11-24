"""Rules that must hold for any input (hypothesis)."""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from mbn.analyses import findings as an
from mbn.parsers import facilities
from mbn.sources import ckan

levels = st.floats(min_value=1, max_value=1e6, allow_nan=False)
years = st.integers(min_value=1990, max_value=2030)


@given(st.dictionaries(st.tuples(years, st.integers(1, 4)), levels, min_size=1), st.floats(0.5, 2))
def test_yoy_is_unchanged_when_the_series_is_rescaled(series: dict[tuple[int, int], float], k: float) -> None:
    a = an.yoy(series, 4)
    b = an.yoy({key: v * k for key, v in series.items()}, 4)
    assert [x for x, _ in a] == [x for x, _ in b]
    assert all(abs(p - q) <= 0.1 + 1e-9 for (_, p), (_, q) in zip(a, b, strict=True))


@given(levels, st.integers(2000, 2020), st.integers(1, 10))
def test_a_constant_index_gives_zero_inflation(v: float, start: int, n: int) -> None:
    tokens = list(an.MONTH_TOKENS)
    series = {f"{tokens[m]}-{y}": v for y in range(start, start + n + 1) for m in range(12)}
    assert all(r == 0 for _, r in an.cpi_yoy(series))


json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False, allow_infinity=False) | st.text(),
    lambda c: st.lists(c) | st.dictionaries(st.text(), c),
    max_leaves=20,
)


@given(json_values)
def test_jsonify_is_idempotent(x: Any) -> None:
    once = an.jsonify(x)
    assert an.jsonify(once) == once


@given(st.dictionaries(st.text(min_size=1), st.text(min_size=19, max_size=19)))
def test_identical_states_have_no_changes(state: dict[str, str]) -> None:
    assert ckan.diff_states(state, state) == []


@given(st.sampled_from(sorted(facilities.REGION_KEYS.values())), st.sampled_from(["", "Région ", "REGION DE "]), st.booleans())
def test_every_region_name_matches_itself(name: str, prefix: str, upper: bool) -> None:
    raw = prefix + (name.upper() if upper else name)
    assert facilities.region(raw) == name


@given(st.dictionaries(st.text(min_size=1, max_size=30), st.integers(1, 1000), max_size=30))
def test_parliament_themes_never_lose_a_question(ministries: dict[str, int]) -> None:
    themes, unmapped = an.parliament_themes(ministries)
    assert sum(n for _, n in themes) + unmapped == sum(ministries.values())
