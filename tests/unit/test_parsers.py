"""Parsers on trimmed real files (tests/fixtures) and on small synthetic sheets."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from mbn.model import schemas
from mbn.parsers import abh, facilities, hcp, parliament

FLOW_FILE = "debits-moyens-journaliers_ait-melloul-_-2023-2024.xlsx"


# --- ABH ----------------------------------------------------------------------------------------
def test_rain_year_reads_label_total_and_completeness(fixtures: Path) -> None:
    assert abh.rain_year(fixtures / "abh_rain.xlsx") == (2023, 118.7, 12)


def test_flow_year_takes_year_from_file_name(fixtures: Path) -> None:
    year, mean, months = abh.flow_year(str(fixtures / FLOW_FILE))
    assert (year, months) == (2024, 12)
    assert mean == pytest.approx(0.001, abs=1e-3)


def test_flow_year_without_years_in_name_fails() -> None:
    with pytest.raises(ValueError):
        abh.flow_year_from_name("debit.xlsx")


def test_rain_grid_is_days_by_hydrological_months(fixtures: Path) -> None:
    grid = abh.rain_grid(pd.read_excel(fixtures / "abh_rain.xlsx", header=None))
    assert list(grid.columns) == abh.HYDRO_MONTHS
    assert grid.index.min() == 1 and grid.index.max() == 31


def test_daily_drops_impossible_dates_and_spans_sep_to_aug() -> None:
    grid = pd.DataFrame(1.0, index=range(1, 32), columns=abh.HYDRO_MONTHS)
    d = abh.daily(grid, 2024)  # Sep 2023 .. Aug 2024, a leap year
    assert len(d) == 366
    assert d["date"].min() == pd.Timestamp("2023-09-01")
    assert d["date"].max() == pd.Timestamp("2024-08-31")
    schemas.daily(d)


def test_rain_year_label_finds_slash_year() -> None:
    df = pd.DataFrame([["x", " 2001 / 2002"], [None, None]])
    assert abh.rain_year_label(df) == 2002
    assert abh.rain_year_label(pd.DataFrame([["nothing"]])) is None


# --- HCP ------------------------------------------------------------------------------------------
def test_unemployment_series_have_quarters(fixtures: Path, golden_data: dict) -> None:
    u = hcp.unemployment(
        hcp.read_data_sheet(fixtures / "hcp_i4252_data.xlsx"), hcp.read_data_sheet(fixtures / "hcp_i4248_data.xlsx")
    )
    assert set(u) == {"total", "women", "men", "youth", "youth_women", "no_degree", "mid_degree", "higher_degree"}
    assert u["higher_degree"]["T4-2025"] == pytest.approx(25.7)
    assert u["no_degree"]["T4-2025"] == pytest.approx(4.2)


def test_cpi_national_picks_listed_groups(fixtures: Path) -> None:
    body = hcp.read_data_sheet(fixtures / "hcp_i4166_data.xlsx")
    cpi = hcp.cpi_national(body)
    assert set(cpi) == {"(GR) GENERAL", "(01) PRODUITS ALIMENTAIRES ET BOISSONS NON ALCOOLISÉES", "(0112) VIANDE"}
    assert cpi["(GR) GENERAL"]["Août-2026"] == pytest.approx(119.6)


def test_cpi_long_is_tidy_and_valid(fixtures: Path) -> None:
    long = schemas.cpi_long(hcp.cpi_long(hcp.read_data_sheet(fixtures / "hcp_i4166_data.xlsx")))
    assert set(long["city"]) == {"National", "Rabat"}
    assert set(long["code"]) == {"GR", "01", "0112"}
    assert long["month"].max() == pd.Timestamp("2026-08-01")
    assert long.groupby(["city", "code"]).size().nunique() == 1


# --- Parliament -----------------------------------------------------------------------------------
def _questions_file(path: Path, rows: list[list[object]], header: bool = True) -> str:
    cols = ["رقم السؤال", "النائب", "تاريخ السؤال", "موضوع السؤال", "الفريق", "نص السؤال", "الوزارة"]
    df = pd.DataFrame(rows, columns=cols)
    df.columns = ["Numero", "Depute", "Date", "موضوع", "Groupe", "نص", "Ministère"]
    df.to_excel(path, index=False, header=header)
    return str(path)


def test_question_files_with_and_without_header_are_read(tmp_path: Path) -> None:
    row = [12, "X", pd.Timestamp("2022-05-03"), "subject", "G", "body", "وزارة الصحة"]
    a = parliament.read_questions(_questions_file(tmp_path / "liste-des-questions-ecrites-a.xlsx", [row]))
    b = parliament.read_questions(_questions_file(tmp_path / "liste-des-questions-orales-b.xlsx", [row], header=False))
    assert a.loc[0, ["kind", "number", "date_key", "ministry", "subject"]].tolist() == [
        "written",
        "12",
        "2022-05-03",
        "وزارة الصحة",
        "subject",
    ]
    assert b.loc[0, ["kind", "number", "date_key", "ministry"]].tolist() == ["oral", "12", "2022-05-03", "وزارة الصحة"]


def test_reader_never_keeps_the_mp_column(tmp_path: Path) -> None:
    row = [1, "Name Of Member", pd.Timestamp("2022-05-03"), "s", "Group", "t", "وزارة"]
    df = parliament.read_questions(_questions_file(tmp_path / "liste-des-questions-ecrites.xlsx", [row]))
    assert "Name Of Member" not in df.astype(str).to_numpy().ravel().tolist()
    assert "Group" not in df.astype(str).to_numpy().ravel().tolist()


def test_overlapping_files_are_counted_once(tmp_path: Path) -> None:
    r1 = [1, "x", pd.Timestamp("2021-01-04"), "s", "g", "t", "وزارة الداخلية"]
    r2 = [2, "x", pd.Timestamp("2021-02-04"), "s", "g", "t", "وزارة الصحة"]
    f1 = parliament.read_questions(_questions_file(tmp_path / "liste-des-questions-ecrites-1.xlsx", [r1, r2]))
    f2 = parliament.read_questions(_questions_file(tmp_path / "liste-des-questions-ecrites-2.xlsx", [r2]))
    f3 = parliament.read_questions(_questions_file(tmp_path / "liste-des-questions-orales-3.xlsx", [r2]))
    df = schemas.questions(parliament.dedupe([f1, f2, f3]))
    kinds, years, ministries = parliament.counts(df)
    assert kinds == {"written": 2, "oral": 1}
    assert years == {"2021": 3}
    assert ministries == {"وزارة الداخلية": 1, "وزارة الصحة": 2}


def test_dedupe_of_nothing_is_empty() -> None:
    assert parliament.dedupe([]).empty


# --- Facilities ----------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("REGION DE CASABLANCA-SETTAT", "Casablanca-Settat"),
        ("Fès - Meknès", "Fès-Meknès"),
        ("laayoune sakia el hamra", "Laâyoune-Sakia El Hamra"),
        ("Atlantis", None),
    ],
)
def test_region_names_are_matched_whatever_the_spelling(raw: str, expected: str | None) -> None:
    assert facilities.region(raw) == expected


def test_count_by_region_filters_categories(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            ["title", None, None],
            ["Région", "Catégorie", "Nom"],
            ["Souss-Massa", "CSU-1", "a"],
            ["Souss-Massa", "LAB", "b"],
            ["Nowhere", "DR", "c"],
        ]
    )
    p = tmp_path / "essp.xlsx"
    df.to_excel(p, header=False, index=False)
    counts, unmatched = facilities.count_by_region(p, {"région"}, keep=facilities.PRIMARY_CARE)
    assert counts == {"Souss-Massa": 1}
    assert unmatched == 1
