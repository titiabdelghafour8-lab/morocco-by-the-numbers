"""Haut-Commissariat au Plan (HCP) "data" sheets.

Layout: row 0 is a title, row 1 holds the column headers (dimension names, then one
column per period such as ``T1-2017``, ``2025`` or ``Janv-2018``), data starts on row 2.
"""

from __future__ import annotations

import re
from typing import Any, cast

import pandas as pd

QUARTER = re.compile(r"T\d-\d{4}")
MONTHS_FR = {
    "Janv": 1,
    "Févr": 2,
    "Mars": 3,
    "Avr": 4,
    "Mai": 5,
    "Juin": 6,
    "Juill": 7,
    "Août": 8,
    "Sept": 9,
    "Oct": 10,
    "Nov": 11,
    "Déc": 12,
}


def read_data_sheet(path: Any) -> pd.DataFrame:
    """Read an HCP ``*_data.xlsx`` file into a table whose columns are the header row."""
    df = pd.read_excel(path, header=None)
    hdr = df.iloc[1].tolist()
    body = df.iloc[2:].copy()
    body.columns = [str(h).replace(".0", "") for h in hdr]
    return body


def quarter_columns(body: pd.DataFrame) -> list[str]:
    return [c for c in body.columns if QUARTER.match(c)]


def row_series(body: pd.DataFrame, k1: str, v1: str, k2: str, v2: str, cols: list[str]) -> dict[str, float | None]:
    """Values of the first row where column k1 == v1 and k2 == v2, over the given period columns."""
    r = body[(body[k1].astype(str).str.strip() == v1) & (body[k2].astype(str).str.strip() == v2)].iloc[0]
    return {c: (None if pd.isna(r[c]) else float(r[c])) for c in cols}


def unemployment(by_age: pd.DataFrame, by_diploma: pd.DataFrame) -> dict[str, dict[str, float | None]]:
    """Quarterly unemployment rates (data_i4252 by age and sex, data_i4248 by diploma)."""
    qcols = quarter_columns(by_age)
    age, sex, dip = "Tranches d'âge", "Sexe", "Type diplôme"
    return {
        "total": row_series(by_age, age, "Ensemble", sex, "Total", qcols),
        "women": row_series(by_age, age, "Ensemble", sex, "Féminin", qcols),
        "men": row_series(by_age, age, "Ensemble", sex, "Masculin", qcols),
        "youth": row_series(by_age, age, "15 - 24", sex, "Total", qcols),
        "youth_women": row_series(by_age, age, "15 - 24", sex, "Féminin", qcols),
        "no_degree": row_series(by_diploma, dip, "Sans diplôme", sex, "Total", qcols),
        "mid_degree": row_series(by_diploma, dip, "Ayant un diplôme:  Niveau moyen", sex, "Total", qcols),
        "higher_degree": row_series(by_diploma, dip, "Ayant un diplôme:  Niveau supérieur", sex, "Total", qcols),
    }


def regional_unemployment(body: pd.DataFrame) -> tuple[list[list[str]], list[list[str]]]:
    """data_i3287: rows (Milieu, Région, 2025, 2015, Sexe) for everyone, and (Milieu, Région, 2025) for women."""
    sex = body["Sexe"].astype(str).str.strip()
    total = body[sex == "Total"][["Milieu", "Région", "2025", "2015", "Sexe"]].astype(str).values.tolist()
    women = body[sex == "Féminin"][["Milieu", "Région", "2025"]].astype(str).values.tolist()
    return total, women


def provincial_unemployment(body: pd.DataFrame) -> list[list[str]]:
    """data_imt_txch_02: rows (Milieu, province, 2025, 2017)."""
    rows: list[list[str]] = body[["Milieu", "Provinces/Préfectures", "2025", "2017"]].astype(str).values.tolist()
    return rows


CPI_KEEP = [
    "(GR) GENERAL",
    "(01) PRODUITS ALIMENTAIRES ET BOISSONS NON ALCOOLISÉES",
    "(0112) VIANDE",
    "(0117) LEGUMES",
    "(0115) HUILES ET GRAISSES",
    "(0111) PAIN ET CEREALES",
    "(07) TRANSPORT",
]
CPI_CITY, CPI_PRODUCT = "Villes", "Divisions et groupes de produits"


def cpi_national(body: pd.DataFrame, keep: list[str] = CPI_KEEP) -> dict[str, dict[str, float]]:
    """data_i4166: national index level by month (``Janv-2018`` -> value) for selected groups."""
    nat = body[body[CPI_CITY].astype(str).str.strip() == "National"]
    names = nat[CPI_PRODUCT].astype(str).str.strip()
    return {
        k: cast(dict[str, float], nat[names == k].iloc[0, 2:].dropna().astype(float).to_dict())
        for k in keep
        if (names == k).any()
    }


def cpi_long(body: pd.DataFrame) -> pd.DataFrame:
    """data_i4166 as a tidy table: city, code, product, month (Timestamp), index."""
    months = [c for c in body.columns[2:] if re.fullmatch(r"[^\W\d_]+-\d{4}", c) and c.split("-")[0] in MONTHS_FR]
    df = body[[CPI_CITY, CPI_PRODUCT, *months]].copy()
    df[CPI_CITY] = df[CPI_CITY].astype(str).str.strip()
    df[CPI_PRODUCT] = df[CPI_PRODUCT].astype(str).str.strip()
    long = df.melt(id_vars=[CPI_CITY, CPI_PRODUCT], var_name="period", value_name="index")
    long["index"] = pd.to_numeric(long["index"], errors="coerce")
    long = long.dropna(subset=["index"])
    mon = long["period"].str.split("-")
    long["month"] = pd.to_datetime({"year": mon.str[1].astype(int), "month": mon.str[0].map(MONTHS_FR), "day": 1})
    code = long[CPI_PRODUCT].str.extract(r"^\((\w+)\)\s*(.*)$")
    out = pd.DataFrame(
        {
            "city": long[CPI_CITY].values,
            "code": code[0].values,
            "product": code[1].values,
            "month": long["month"].values,
            "index": long["index"].astype(float).values,
        }
    )
    return out.sort_values(["city", "code", "month"]).reset_index(drop=True)


def gdp_quarterly(path: Any) -> dict[tuple[int, int], float]:
    """data_i4276: chained-volume GDP by (year, quarter)."""
    df = pd.read_excel(path, header=None)
    q = dict(zip(df.iloc[1, 1:], df.iloc[2, 1:], strict=False))
    return {(int(k[3:]), int(k[1])): float(v) for k, v in q.items() if isinstance(k, str) and QUARTER.match(k)}
