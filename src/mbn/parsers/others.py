"""Parsers for publishers with one or two small tables each.

Every function reads one file and returns plain Python structures or a DataFrame.
No function here looks at more than the file it is given.
"""

from __future__ import annotations

import os
import re
from typing import Any, cast

import pandas as pd


# --- Department of Agriculture: crop production ---------------------------------------------
def crops(path: Any) -> dict[str, dict[str, float]]:
    """Production by crop family (Filière) and season label (Occurrence)."""
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    prod = df[df["Indicateur"].str.contains("Production", na=False)]
    return {
        str(k): cast(dict[str, float], v.groupby("Occurrence")["Valeur"].sum().round(0).to_dict())
        for k, v in prod.groupby("Filière")
    }


# --- ACAPS: insurance and pensions supervisor -------------------------------------------------
def acaps_coverage(path: Any) -> dict[int, float]:
    """Share of the population covered by AMO, percent by year (file holds shares 0-1)."""
    df = pd.read_excel(path, header=None)
    return {int(y): round(float(v) * 100, 1) for y, v in zip(df.iloc[0, 1:], df.iloc[1, 1:], strict=False) if pd.notna(y)}


def acaps_ratio(path: Any) -> list[list[float]]:
    """Two-row year table (years, values) -> [[year, value rounded to 0.01]]."""
    df = pd.read_excel(path, header=None)
    return [
        [int(y), round(float(v), 2)] for y, v in zip(df.iloc[0, 1:], df.iloc[1, 1:], strict=False) if pd.notna(y) and pd.notna(v)
    ]


def acaps_rows(path: Any) -> dict[str, dict[int, float]]:
    """Year-by-row table: {row label: {year: value}} (million dirhams)."""
    df = pd.read_excel(path, header=None)
    years = [int(y) if pd.notna(y) else None for y in df.iloc[0, 1:]]
    out: dict[str, dict[int, float]] = {}
    for _, r in df.iloc[1:].iterrows():
        lab = str(r.iloc[0]).strip()
        if lab and lab != "nan":
            out[lab] = {
                y: float(v) for y, v in zip(years, r.iloc[1:], strict=False) if y and pd.notna(v) and isinstance(v, int | float)
            }
    return out


# --- ANRT: telecom regulator --------------------------------------------------------------------
def anrt_q4(path: Any, cols: list[str]) -> dict[str, list[float | None]]:
    """Year-end (T4) rows of an ANRT park table, selected columns by header letter."""
    df = pd.read_excel(path, header=None)
    i = df.index[df[0].astype(str).str.startswith("Période")][0]
    hdr = df.iloc[i].tolist()
    body = df.iloc[i + 1 :].copy()
    body.columns = hdr
    body = body[body["Période (à fin)"].astype(str).str.match(r"T4-\d{4}")]
    return {str(r["Période (à fin)"])[3:]: [None if pd.isna(r[k]) else float(r[k]) for k in cols] for _, r in body.iterrows()}


# --- NARSA: road safety agency --------------------------------------------------------------------
def road_accidents(path: Any) -> tuple[int, dict[str, list[int]]]:
    """One yearly accident file -> (year, {row label: [in towns, outside towns, total]})."""
    df = pd.read_excel(path, header=None)
    m = re.search(r"(\d{4})", str(df.iloc[0, 0]))
    if not m:
        raise ValueError(f"no year in the title of {path}")
    rows = {str(r[0]).strip(): [r[1], r[2], r[3]] for r in df.values[1:]}
    return int(m.group(1)), {k: [int(x) for x in v] for k, v in rows.items()}


def vehicles(path: Any) -> dict[str, dict[int, float]]:
    """Vehicles in circulation at year end, sheet "3-4": {category: {year: count}}."""
    df = pd.read_excel(path, sheet_name="3-4", header=None)
    hdr = next(i for i in range(len(df)) if str(df.iloc[i, 0]).strip().startswith("Au 31"))
    yrs = [int(float(y)) for y in df.iloc[hdr, 1:7] if pd.notna(y)]
    out: dict[str, dict[int, float]] = {}
    for _, r in df.iloc[hdr + 1 : hdr + 5].iterrows():
        out[str(r.iloc[0]).strip()] = {y: float(v) for y, v in zip(yrs, r.iloc[1 : 1 + len(yrs)], strict=False)}
    return out


# --- Ministry of Justice ------------------------------------------------------------------------------
COURT_SECTIONS = {"القضايا المسجلة": "registered", "القضايا الرائجة": "workload", "القضايا المحكومة": "judged"}


def courts(path: Any) -> dict[str, dict[int, float]]:
    """Five-year case table: {section or "section|court type": {year: cases}}."""
    df = pd.read_excel(path, header=None).dropna(how="all").dropna(axis=1, how="all")
    yrs = df.iloc[1, 1:].tolist()
    cur: str | None = None
    out: dict[str, dict[int, float]] = {}
    for _, r in df.iloc[2:].iterrows():
        lab = str(r.iloc[0]).strip()
        if lab in COURT_SECTIONS:
            cur = COURT_SECTIONS[lab]
            key = cur
        elif cur:
            key = cur + "|" + lab
        else:
            continue
        out.setdefault(key, {}).update(
            {int(y): float(v) for y, v in zip(yrs, r.iloc[1:], strict=False) if pd.notna(y) and pd.notna(v)}
        )
    return out


# --- INPPLC: Transparency International's index ----------------------------------------------------
def corruption_index(path: Any) -> list[list[Any]]:
    df = pd.read_excel(path, sheet_name="CPI_DATA")
    rows: list[list[Any]] = df[["Année", "CPI", "Rank"]].values.tolist()
    return rows


# --- Bank Al-Maghrib -----------------------------------------------------------------------------------
def bam_credit(path: Any) -> pd.Series:
    """Bank credit to the economy, last observation of each month: Series indexed by (year, month)."""
    df = pd.read_excel(path, header=None)
    dates = pd.to_datetime(df.iloc[2, 1:], errors="coerce")
    row = df[df[0].astype(str).str.strip() == "Crédits des"].iloc[0, 1:]
    s = pd.Series(row.values.astype(float), index=dates).dropna()
    s = s[~pd.isna(s.index)]
    idx = pd.DatetimeIndex(s.index)
    return s.groupby([idx.year, idx.month]).last()


# --- AMMC: weekly fund statistics ------------------------------------------------------------------------
FUND_DATE = re.compile(r"(\d{2})[-_.](\d{2})[-_.](\d{4})")


def fund_total(path: str) -> tuple[str, float] | None:
    """(ISO date from the file name, total net assets in billion dirhams), or None if unreadable."""
    try:
        x = pd.read_excel(path, header=None, sheet_name=0)
    except Exception:
        return None
    m = FUND_DATE.search(os.path.basename(path))
    if not m:
        return None
    d = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    for _, r in x.iterrows():
        cells = [str(c).strip() for c in r.values]
        if any(c.lower().startswith("total") for c in cells):
            nums = [c for c in r.values if isinstance(c, int | float) and not pd.isna(c) and c > 1e9]
            if nums:
                return d, round(float(nums[0]) / 1e9, 1)
    return None


# --- Digital Development Agency: startups (aggregated only, no names kept) -------------------------------
def startups(path: Any) -> pd.DataFrame:
    """One row per company (deduplicated by lower-cased name), with city and main sector only."""
    df = pd.read_excel(path)
    df.columns = [c.strip() for c in df.columns]
    # the database merges four overlapping lists: keep one row per company name
    df = df.loc[~df["Raison social"].astype(str).str.strip().str.lower().duplicated()]
    return pd.DataFrame(
        {
            "city": df["City"].astype(str).str.strip().str.lower().str.replace("é", "e").values,
            "sector": df["Main sector"].astype(str).str.strip().values,
        }
    )
