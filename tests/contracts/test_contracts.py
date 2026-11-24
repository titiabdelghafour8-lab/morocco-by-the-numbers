"""Data contracts reject bad tables before they reach a chart."""

from __future__ import annotations

import pandas as pd
import pandera.errors
import pytest

from mbn.model import schemas


def _q(**over: object) -> pd.DataFrame:
    row = {
        "kind": "oral",
        "number": "1",
        "date_key": "2022-01-01",
        "date": "2022-01-01",
        "ministry": "m",
        "subject": "s",
        "text": "t",
    }
    row.update(over)
    return pd.DataFrame([row])


def test_valid_questions_pass() -> None:
    schemas.questions(_q())


def test_unknown_question_kind_fails() -> None:
    with pytest.raises(pandera.errors.SchemaError):
        schemas.questions(_q(kind="petition"))


def test_duplicate_questions_fail() -> None:
    with pytest.raises(pandera.errors.SchemaError):
        schemas.questions(pd.concat([_q(), _q()], ignore_index=True))


def test_negative_rain_fails() -> None:
    with pytest.raises(pandera.errors.SchemaError):
        schemas.daily(pd.DataFrame({"date": pd.to_datetime(["2020-01-01"]), "value": [-1.0]}))


def test_missing_rain_is_allowed_but_dates_are_unique() -> None:
    schemas.daily(pd.DataFrame({"date": pd.to_datetime(["2020-01-01"]), "value": [float("nan")]}))
    with pytest.raises(pandera.errors.SchemaError):
        schemas.daily(pd.DataFrame({"date": pd.to_datetime(["2020-01-01"] * 2), "value": [1.0, 2.0]}))


def test_cpi_index_must_be_positive_and_unique_per_month() -> None:
    ok = pd.DataFrame(
        {"city": ["National"], "code": ["GR"], "product": ["GENERAL"], "month": pd.to_datetime(["2020-01-01"]), "index": [100.0]}
    )
    schemas.cpi_long(ok)
    with pytest.raises(pandera.errors.SchemaError):
        schemas.cpi_long(ok.assign(index=[0.0]))
    with pytest.raises(pandera.errors.SchemaError):
        schemas.cpi_long(pd.concat([ok, ok], ignore_index=True))
