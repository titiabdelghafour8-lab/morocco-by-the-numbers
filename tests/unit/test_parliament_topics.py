from __future__ import annotations

import importlib.util

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from mbn.analyses import arabic
from mbn.analyses import parliament_topics as pt


# --- Arabic normalisation ------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("إصلاحُ الطّرقِ", "اصلاح الطرق"),
        ("مستشفى الأطفال", "مستشفي الاطفال"),
        ("المدرسة الابتدائية", "المدرسه الابتدائيه"),
        ("آبار ـــ القرى", "ابار القري"),
        ("  نسائلكم السيد الوزير عن   برنامج  السكن ", "برنامج السكن"),
    ],
)
def test_normaliser_on_known_strings(raw: str, expected: str) -> None:
    assert arabic.normalise(raw) == expected


@pytest.mark.skipif(importlib.util.find_spec("camel_tools") is None, reason="camel-tools not installed (topics extra)")
def test_normaliser_agrees_with_camel_tools() -> None:
    from camel_tools.utils.dediac import dediac_ar
    from camel_tools.utils.normalize import normalize_alef_ar, normalize_alef_maksura_ar, normalize_teh_marbuta_ar

    s = "إصلاحُ الطّرقِ في القرى المجاورة لمدينة آسفي"
    camel = normalize_teh_marbuta_ar(normalize_alef_maksura_ar(normalize_alef_ar(dediac_ar(s))))
    assert arabic.normalise(s) == " ".join(camel.split())


def test_tokens_drop_stop_words_and_place_markers() -> None:
    assert arabic.tokens("وضعية الطريق الرابطة بين جماعة سيدي علي وإقليم جرسيف") == ["الطريق", "الرابطه", "جرسيف"]


@given(st.text(alphabet="ابتثجحخدذرزسشصضطظعغفقكلمنهوي ًٌٍَُِّْإأآةى", max_size=60))
def test_normalising_twice_changes_nothing(s: str) -> None:
    assert arabic.normalise(arabic.normalise(s)) == arabic.normalise(s)


# --- topic summaries ------------------------------------------------------------------------------
def test_shares_by_year_add_up() -> None:
    df = pd.DataFrame({"year": [2017, 2017, 2017, 2018], "topic": [0, 0, 1, 1]})
    shares = pt.shares_by_year(df)
    assert shares.loc[2017].round(1).to_dict() == {0: 66.7, 1: 33.3}
    assert shares.sum(axis=1).round(6).eq(100).all()


def test_rising_and_falling_compare_first_and_last_years() -> None:
    shares = pd.DataFrame({0: [10.0, 10, 10, 20, 20, 20], 1: [90.0, 90, 90, 80, 80, 80]}, index=range(2017, 2023))
    change = pt.change_in_share(shares, first=(2017, 2019), last=(2020, 2022))
    assert change.to_dict() == {0: 10.0, 1: -10.0}


def test_fingerprint_depends_on_topics_not_order_of_keys() -> None:
    a = [{"id": 0, "words": ["a", "b"], "size": 3}, {"id": 1, "words": ["c"], "size": 1}]
    b = [{"size": 1, "words": ["c"], "id": 1}, {"words": ["a", "b"], "size": 3, "id": 0}]
    assert pt.fingerprint(a) == pt.fingerprint(b)
    assert pt.fingerprint(a) != pt.fingerprint([{"id": 0, "words": ["a", "x"], "size": 3}, a[1]])


def test_names_are_found_in_any_spelling_of_spacing_and_case() -> None:
    assert pt.contains_any("سؤال  فاطمة   الزهراء مثال", ["فاطمة الزهراء مثال"])
    assert pt.contains_any("Question by FATIMA zahra example", ["Fatima Zahra Example"])
    assert not pt.contains_any("سؤال حول الماء", ["فاطمة الزهراء مثال"])
    assert not pt.contains_any("anything", ["", "  "])


def test_coherence_and_diversity() -> None:
    docs = [["ماء", "سد"], ["ماء", "سد"], ["طريق", "قنطره"], ["طريق", "قنطره"]]
    good = pt.npmi_coherence([["ماء", "سد"], ["طريق", "قنطره"]], docs)
    bad = pt.npmi_coherence([["ماء", "طريق"], ["سد", "قنطره"]], docs)
    assert good > bad
    assert pt.diversity([["a", "b"], ["c", "d"]]) == 1.0
    assert pt.diversity([["a", "b"], ["a", "b"]]) == 0.5
