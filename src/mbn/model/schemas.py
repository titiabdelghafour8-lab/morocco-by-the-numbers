"""Data contracts (pandera) at the boundaries between parsers and analyses.

Each function validates a table and returns it unchanged, so it can wrap a parser call.
Bad data fails here, loudly, before it reaches a chart.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

QUESTIONS = DataFrameSchema(
    {
        "kind": Column(str, Check.isin(["oral", "written"])),
        "number": Column(str),
        "date_key": Column(str),
        "ministry": Column(str),
        "subject": Column(str),
        "text": Column(str),
    },
    unique=["kind", "number", "date_key"],
    strict=False,
)

DAILY = DataFrameSchema(
    {
        "date": Column("datetime64[ns]", unique=True),
        "value": Column(float, Check.ge(0), nullable=True),
    },
    strict=True,
)

CPI_LONG = DataFrameSchema(
    {
        "city": Column(str),
        "code": Column(str),
        "product": Column(str),
        "month": Column("datetime64[ns]"),
        "index": Column(float, Check.gt(0)),
    },
    unique=["city", "code", "month"],
    strict=True,
)

FACILITY_COUNTS = DataFrameSchema(
    {"region": Column(str, unique=True), "count": Column(int, Check.ge(0))},
)


def questions(df: pd.DataFrame) -> pd.DataFrame:
    return QUESTIONS.validate(df)


def daily(df: pd.DataFrame) -> pd.DataFrame:
    return DAILY.validate(df)


def cpi_long(df: pd.DataFrame) -> pd.DataFrame:
    return CPI_LONG.validate(df)


__all__ = ["CPI_LONG", "DAILY", "QUESTIONS", "cpi_long", "daily", "pa", "questions"]
