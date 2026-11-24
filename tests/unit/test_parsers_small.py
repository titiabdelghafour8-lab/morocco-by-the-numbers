"""Small publisher layouts, on synthetic sheets that copy each file's real structure."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from mbn.analyses import findings as an
from mbn.parsers import hcp, others


def _xlsx(path: Path, rows: list[list[Any]], sheet: str = "Sheet1", header: bool = False) -> Path:
    df = pd.DataFrame(rows[1:], columns=rows[0]) if header else pd.DataFrame(rows)
    df.to_excel(path, sheet_name=sheet, header=header, index=False)
    return path


def test_crops_sum_production_by_family_and_season(tmp_path: Path) -> None:
    p = _xlsx(
        tmp_path / "c.xlsx",
        [
            ["Filière ", "Indicateur", "Occurrence", "Valeur"],
            ["Céréales", "Production (T)", "2021/2022", 1.0],
            ["Céréales", "Production (T)", "2021/2022", 2.0],
            ["Céréales", "Superficie", "2021/2022", 9.0],
            ["Agrumes", "Production (T)", "2022/2023", 5.0],
        ],
        header=True,
    )
    assert others.crops(p) == {"Agrumes": {"2022/2023": 5.0}, "Céréales": {"2021/2022": 3.0}}


def test_acaps_tables(tmp_path: Path) -> None:
    cov = _xlsx(tmp_path / "cov.xlsx", [["", 2012, 2024, None], ["Taux", 0.197, 0.771, None]])
    assert others.acaps_coverage(cov) == {2012: 19.7, 2024: 77.1}
    ratio = _xlsx(tmp_path / "r.xlsx", [["", 2012, 2024], ["Rapport", 6.61, None]])
    assert others.acaps_ratio(ratio) == [[2012, 6.61]]
    rows = _xlsx(tmp_path / "rows.xlsx", [["", 2023, 2024], ["TOTAL", 10.0, 12.0], [None, None, None], ["Note", "n/a", 1.0]])
    assert others.acaps_rows(rows) == {"TOTAL": {2023: 10.0, 2024: 12.0}, "Note": {2024: 1.0}}


def test_anrt_keeps_year_end_rows(tmp_path: Path) -> None:
    p = _xlsx(
        tmp_path / "a.xlsx",
        [
            ["Parc mobile", None, None],
            ["Période (à fin)", "L", "M"],
            ["T3-2024", 1.0, 1.5],
            ["T4-2024", 2.0, 1.6],
            ["T4-2025", 3.0, None],
        ],
    )
    assert others.anrt_q4(p, ["L", "M"]) == {"2024": [2.0, 1.6], "2025": [3.0, None]}


def test_road_accidents_and_vehicles(tmp_path: Path) -> None:
    p = _xlsx(
        tmp_path / "r.xlsx", [["Statistiques 2024", None, None, None], ["Tués", 1000, 3024, 4024], ["Total Accidents", 1, 2, 3]]
    )
    assert others.road_accidents(p) == (2024, {"Tués": [1000, 3024, 4024], "Total Accidents": [1, 2, 3]})
    with pytest.raises(ValueError):
        others.road_accidents(_xlsx(tmp_path / "x.xlsx", [["no year", 1, 2, 3]]))
    v = _xlsx(
        tmp_path / "v.xlsx",
        [
            ["Parc", None, None],
            ["Au 31 décembre", 2022.0, 2023.0],
            ["Voitures", 10, 11],
            ["Utilitaires", 1, 2],
            ["Motocyclettes", 3, 4],
            ["Total", 14, 17],
            ["après", 0, 0],
        ],
        sheet="3-4",
    )
    assert others.vehicles(v)["Total"] == {2022: 14.0, 2023: 17.0}
    assert len(others.vehicles(v)) == 4


def test_courts_sections(tmp_path: Path) -> None:
    p = _xlsx(
        tmp_path / "c.xlsx",
        [
            ["title", None, None],
            ["", 2021, 2025],
            ["ignored", 1, 1],
            ["القضايا المسجلة", 100, 200],
            ["محاكم الاستئناف العادية", 10, 20],
            ["القضايا المحكومة", 90, 210],
        ],
    )
    assert others.courts(p) == {
        "registered": {2021: 100.0, 2025: 200.0},
        "registered|محاكم الاستئناف العادية": {2021: 10.0, 2025: 20.0},
        "judged": {2021: 90.0, 2025: 210.0},
    }


def test_corruption_index(tmp_path: Path) -> None:
    p = _xlsx(tmp_path / "c.xlsx", [["Année", "CPI", "Rank"], [2018, 43, 73], [2024, 37, 99]], sheet="CPI_DATA", header=True)
    assert others.corruption_index(p) == [[2018, 43, 73], [2024, 37, 99]]


def test_bam_credit_keeps_the_last_observation_of_each_month(tmp_path: Path) -> None:
    p = _xlsx(
        tmp_path / "b.xlsx",
        [
            ["t", None, None, None],
            ["", None, None, None],
            ["", pd.Timestamp("2025-01-15"), pd.Timestamp("2025-01-31"), pd.Timestamp("2025-02-28")],
            ["Crédits des", 1.0, 2.0, 3.0],
        ],
    )
    s = others.bam_credit(p)
    assert s.to_dict() == {(2025, 1): 2.0, (2025, 2): 3.0}


def test_fund_totals(tmp_path: Path) -> None:
    ok = _xlsx(tmp_path / "stat-03-01-2020.xlsx", [["Catégorie", "Actif"], ["Actions", 2.0e9], ["Total général", 469.4e9]])
    assert others.fund_total(str(ok)) == ("2020-01-03", 469.4)
    nodate = _xlsx(tmp_path / "stat.xlsx", [["Total", 1e10]])
    assert others.fund_total(str(nodate)) is None
    nototal = _xlsx(tmp_path / "s-03-01-2020.xlsx", [["x", 1]])
    assert others.fund_total(str(nototal)) is None
    (tmp_path / "bad-03-01-2020.xlsx").write_bytes(b"not a spreadsheet")
    assert others.fund_total(str(tmp_path / "bad-03-01-2020.xlsx")) is None


def test_startups_are_deduplicated_and_reduced_to_city_and_sector(tmp_path: Path) -> None:
    p = _xlsx(
        tmp_path / "s.xlsx",
        [
            ["Raison social ", "City", "Main sector", "Founder"],
            ["Acme", "Casablanca", "Fintech", "A Person"],
            ["ACME ", "Casablanca", "Fintech", "A Person"],
            ["Beta", "Fès", "Health", "B Person"],
        ],
        header=True,
    )
    df = others.startups(p)
    assert df.to_dict("records") == [
        {"city": "casablanca", "sector": "Fintech"},
        {"city": "fès", "sector": "Health"},
    ]  # "fès" is merged later
    assert list(df.columns) == ["city", "sector"]  # no names kept


def test_hcp_regional_provincial_and_gdp(tmp_path: Path) -> None:
    body = pd.DataFrame(
        {
            "Milieu": ["National", "National"],
            "Région": ["Oriental", "Oriental"],
            "Sexe": ["Total", "Féminin"],
            "2025": [22.1, 30.0],
            "2015": [17.0, 25.0],
        }
    )
    total, women = hcp.regional_unemployment(body)
    assert total == [["National", "Oriental", "22.1", "17.0", "Total"]] and women == [["National", "Oriental", "30.0"]]
    prov = pd.DataFrame({"Milieu": ["National"], "Provinces/Préfectures": ["Oujda"], "2025": [20.0], "2017": [15.0]})
    assert hcp.provincial_unemployment(prov) == [["National", "Oujda", "20.0", "15.0"]]
    p = _xlsx(tmp_path / "g.xlsx", [["PIB", None, None], ["", "T1-2019", "T1-2020"], ["Volume", 100.0, 90.0]])
    assert hcp.gdp_quarterly(p) == {(2019, 1): 100.0, (2020, 1): 90.0}


def test_build_more_and_pack_assemble_the_published_shape(golden_data: dict[str, Any]) -> None:
    r = {
        "gdp_growth": [[2020.0, -10.0]],
        "credit": [[2009.0, 5.0, 1], [2010.0, 6.0, 2]],
        "pension_ratio": [[2024, 4.8]],
        "funds": [[f"2020-{m:02d}-01", float(m)] for m in range(1, 11)],
        "startup_n": 2,
        "startup_city": {"casablanca": 2},
        "parl_n": {"oral": 1},
        "parl_years": {"2020": 1},
        "parl_ministries": {"وزارة الداخلية": 1},
        "amo_finance": {"resources": {"2024": 46100.0}},
        "pension_money": {"reserves": {"2024": 264900.0}},
        "vehicles": {"Total": {"2023": 4.5e6}},
    }
    s2 = an.jsonify(an.build_more(an.jsonify(r)))
    assert s2["credit"] == [[2010.0, 6.0]] and s2["parl_total"] == 1
    assert s2["amo_finance"] == {"resources": [[2024, 46.1]]}
    main_keys = [
        "flow",
        "rain",
        "cereals",
        "region",
        "prov_top",
        "prov_bottom",
        "infl",
        "infl_food",
        "amo",
        "internet",
        "mobile",
        "roads",
        "corr",
    ]
    s = {k: golden_data[k] for k in main_keys}
    s["unemp"] = {
        k: golden_data[v]
        for k, v in [
            ("total", "u_total"),
            ("youth", "u_youth"),
            ("youth_women", "u_youth_w"),
            ("no_degree", "u_none"),
            ("mid_degree", "u_mid"),
            ("higher_degree", "u_high"),
        ]
    }
    s["courts"] = {
        "registered|محاكم الاستئناف العادية": golden_data["appeal"],
        "registered": golden_data["registered"],
        "judged": golden_data["judged"],
    }
    s3 = {
        "pop": {"A": 100000},
        "primary_care": {"A": 5},
        "hospitals": {},
        "schools_primary": {},
        "schools_middle": {},
        "schools_high": {},
    }
    out = an.pack(s, s2, s3, {"x": {}})
    assert out["services"] == [["A", 5.0, 0.0, 0.0, 100000]]
    assert list(out)[:3] == ["flow", "rain", "cereals"]
