"""Souss-Massa river basin agency (ABH): daily tables, one file per hydrological year.

Rainfall files: a "YYYY/YYYY" year label somewhere in the sheet; day number in column 1,
then twelve month columns (September to August). Flow files: day number in column 0, then
twelve month columns; the year is in the file name ("1970-1971").
"""

from __future__ import annotations

import os
import re
from typing import Any, cast

import pandas as pd

YEAR_LABEL = re.compile(r"\s*(\d{4})\s*/\s*(\d{4})")
HYDRO_MONTHS = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8]


def _numbers(frame: pd.DataFrame) -> pd.DataFrame:
    """Cells to floats; commas as decimal points; blanks and text become NaN."""
    out = frame.apply(lambda s: pd.to_numeric(s.astype(str).str.replace(",", ".").str.strip(), errors="coerce"))
    return cast(pd.DataFrame, out).astype(float)


def rain_year_label(df: pd.DataFrame) -> int | None:
    """Closing calendar year of the hydrological year written in the sheet (2023/2024 -> 2024)."""
    for v in df.values.ravel():
        m = YEAR_LABEL.match(str(v))
        if m:
            return int(m.group(2))
    return None


def rain_grid(df: pd.DataFrame) -> pd.DataFrame:
    """The day x month grid of a rainfall sheet (rows: days 1-31, columns: Sep..Aug)."""
    days = df[pd.to_numeric(df[1], errors="coerce").between(1, 31)]
    grid = _numbers(days.iloc[:, 2:14])
    grid.index = pd.to_numeric(days[1], errors="coerce").astype(int).values
    grid.columns = HYDRO_MONTHS[: grid.shape[1]]
    return grid


def flow_grid(df: pd.DataFrame) -> pd.DataFrame:
    days = df[pd.to_numeric(df[0], errors="coerce").between(1, 31)]
    grid = _numbers(days.iloc[:, 1:13])
    grid.index = pd.to_numeric(days[0], errors="coerce").astype(int).values
    grid.columns = HYDRO_MONTHS[: grid.shape[1]]
    return grid


def rain_year(path: Any) -> tuple[int | None, float, int]:
    """(hydrological year, total mm rounded to 0.1, number of months with any value)."""
    df = pd.read_excel(path, header=None)
    grid = rain_grid(df)
    return rain_year_label(df), round(float(grid.sum().sum()), 1), int(grid.notna().any().sum())


def flow_year_from_name(path: str) -> int:
    m = re.search(r"(\d{4})\s*-\s*(\d{4})", os.path.basename(path))
    if not m:
        raise ValueError(f"no year range in file name: {path}")
    return int(m.group(2))


def flow_year(path: str) -> tuple[int, float, int]:
    """(hydrological year, mean daily flow m3/s rounded to 0.001, months with any value)."""
    grid = flow_grid(pd.read_excel(path, header=None))
    return flow_year_from_name(path), round(float(cast(float, grid.stack().mean())), 3), int(grid.notna().any().sum())


def daily(grid: pd.DataFrame, year: int) -> pd.DataFrame:
    """Turn a day x month grid of hydrological year ``year`` (Sep year-1 .. Aug year) into dated rows.

    Impossible dates (31 April, 29 February in common years) are dropped. Missing cells stay NaN.
    """
    rows = []
    for month in grid.columns:
        m = int(month)
        cal_year = year - 1 if m >= 9 else year
        for day, value in grid[month].items():
            try:
                date = pd.Timestamp(year=cal_year, month=m, day=int(cast(int, day)))
            except ValueError:
                continue
            rows.append((date, value))
    return pd.DataFrame(rows, columns=["date", "value"]).sort_values("date").reset_index(drop=True)
