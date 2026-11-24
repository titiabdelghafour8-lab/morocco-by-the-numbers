"""Build the main page's data file from downloaded portal files (the I/O shell around the analyses)."""

from __future__ import annotations

import datetime
import os
import warnings
from typing import Any

from mbn.analyses import findings as an
from mbn.findings.registry import SOURCES
from mbn.model import schemas
from mbn.parsers import abh, facilities, hcp, others, parliament
from mbn.sources.population import POP_2024
from mbn.sources.store import DatasetStore

ABH = "agence-du-bassin-hydraulique-de-souss-massa/"
HCP = "haut-commissariat-au-plan/"
ACAPS = "autorite-de-controle-des-assurances-et-de-la-prevoyance-sociale/"


def extract_main(st: DatasetStore) -> tuple[dict[str, Any], dict[str, dict[int, float]]]:
    """Land, work, prices, living and state datasets."""
    raw: dict[str, Any] = {}
    rain = {}
    for f in st.files(ABH + "pluie-journaliere-du-barrage-y*/*.xlsx"):
        yr, total, months = abh.rain_year(f)
        rain[yr] = (total, months)
    raw["rain"] = rain
    flow = {}
    for f in st.files(ABH + "debit-moyen-journalier-de-la-station-ait*/*.xlsx"):
        yr, m, months = abh.flow_year(f)
        flow[yr] = (m, months)
    raw["flow"] = flow
    raw["crops"] = others.crops(st.file("departement-de-l-agriculture/production-vegetale*/*.xlsx"))

    def sheet(code: str) -> Any:
        return hcp.read_data_sheet(st.file(f"{HCP}{code}/*_data.xlsx"))

    raw["unemp_q"] = hcp.unemployment(sheet("data_i4252"), sheet("data_i4248"))
    raw["region_unemp"], raw["region_unemp_women"] = hcp.regional_unemployment(sheet("data_i3287"))
    raw["prov_unemp"] = hcp.provincial_unemployment(sheet("data_imt_txch_02"))
    raw["cpi"] = hcp.cpi_national(sheet("data_i4166"))
    raw["amo"] = others.acaps_coverage(st.file(ACAPS + "taux-de-couverture*/*.xlsx"))
    raw["mobile"] = others.anrt_q4(st.file("anrt/parc-de-la-telephonie-mobile*/*.xlsx"), ["L", "M"])
    raw["internet"] = others.anrt_q4(st.file("anrt/parc-de-l-internet*/*.xlsx"), ["Q", "R", "H", "D", "K"])
    roads = {}
    for f in st.files("narsa/statistiques-des-accidents-de-la-circulation-routiere-*/*.xlsx"):
        yr, rows = others.road_accidents(f)
        roads[yr] = rows
    raw["roads"] = roads
    raw["cpi_corr"] = others.corruption_index(st.file("l-instance-nationale*/indice-de-perception*/*.xlsx"))
    courts: dict[str, dict[int, float]] = {}
    for f in st.files("ministere-de-la-justice-et-des-libertes/evolution-des-affaires-au-cours-du-quinq*/*.xlsx"):
        for k, v in others.courts(f).items():
            courts.setdefault(k, {}).update(v)
    return raw, courts


def parliament_questions(st: DatasetStore) -> Any:
    """Every question file, deduplicated (kind, number, date); validated against the contract."""
    frames = [parliament.read_questions(f) for f in st.files("parlement/liste-des-questions-*/*.xlsx")]
    return schemas.questions(parliament.dedupe(frames))


def extract_more(st: DatasetStore) -> dict[str, Any]:
    """Economy, pensions, funds, startups and parliament datasets."""
    o: dict[str, Any] = {}
    o["gdp_growth"] = an.yoy(hcp.gdp_quarterly(st.file(HCP + "data_i4276/*_data.xlsx")), 4)
    credit_file = next(x for x in st.files("bank-al-maghrib/creances-sur-l-economie*/*.xlsx") if "2026" in x)
    o["credit"] = an.credit_growth(others.bam_credit(credit_file))
    o["pension_ratio"] = others.acaps_ratio(st.file(ACAPS + "rapport-demographique*/*.xlsx"))
    fund_files = st.files("ammc/stat-hebdo-opcvm-*/*.xls*")
    o["funds"] = sorted(list(t) for f in fund_files if (t := others.fund_total(f)))
    o["funds_files"] = len(fund_files)
    amo_in = others.acaps_rows(st.file(ACAPS + "ressources-des-regimes-amo/*.xlsx"))
    amo_out = others.acaps_rows(st.file(ACAPS + "depenses-des-regimes-amo/*.xlsx"))
    o["amo_finance"] = {
        "resources": amo_in["TOTAL"],
        "expenses": amo_out["TOTAL"],
        "contributions": amo_in["Cotisations"],
        "benefits_paid": amo_out["Prestations et frais payés"],
    }
    o["pension_money"] = {
        "contributions": others.acaps_rows(st.file(ACAPS + "cotisations-des-regimes-de-retraite/*.xlsx"))["Régimes de base"],
        "benefits": others.acaps_rows(st.file(ACAPS + "prestations-des-regimes-de-retraite/*.xlsx"))["Régimes de base"],
        "reserves": others.acaps_rows(st.file(ACAPS + "reserves-des-regimes-de-retraite/*.xlsx"))["Régimes de base"],
    }
    o["vehicles"] = others.vehicles(
        st.files("narsa/statistiques-des-immatriculations-et-permis-de-conduire-delivres*/*.xls*")[-1]
    )
    su = others.startups(st.file("agence-de-developpement-du-digital/donnees-sur-les-startups/bdd-startups-add_2024.xlsx"))
    o["startup_n"] = len(su)
    o["startup_city"] = su["city"].value_counts().head(12).to_dict()
    o["startup_sector"] = su["sector"].value_counts().head(12).to_dict()
    o["parl_n"], o["parl_years"], o["parl_ministries"] = parliament.counts(parliament_questions(st))
    return o


def extract_services(st: DatasetStore) -> dict[str, Any]:
    """Facilities by region, joined with census population."""
    out: dict[str, Any] = {"pop": POP_2024}
    reg = {"région", "region"}
    out["hospitals"], out["hospitals_unmatched"] = facilities.count_by_region(
        st.dirs("ministere-de-la-sante/la-liste-des-hopitaux/liste-des-hopitaux-2025.xlsx")[0], reg
    )
    out["primary_care"], out["primary_care_unmatched"] = facilities.count_by_region(
        st.dirs("ministere-de-la-sante/repartition-des-etablissements-de-soins-de-sante-primaire*/essp-2025.xlsx")[0],
        reg,
        keep=facilities.PRIMARY_CARE,
    )
    edu = "ministere-de-l-education-nationale-et-de-la-formation-professionnelle/"
    for k, p in [
        ("schools_primary", "liste-des-etablissements-publics-primaire/*2026*"),
        ("schools_middle", "liste-de-etablissements-publics-collegial/*2026*"),
        ("schools_high", "liste-des-etablissements-publics-qualifi*/*2026*"),
    ]:
        out[k], out[k + "_unmatched"] = facilities.count_by_region(st.dirs(edu + p)[0], {"ll_reg", "region"})
    return out


def sources(st: DatasetStore) -> dict[str, dict[str, str]]:
    out = {}
    for key, ref in SOURCES.items():
        pattern = ref.pattern
        if ref.last:
            pattern = os.path.relpath(st.dirs(pattern)[-1], st.root)
        out[key] = st.source(pattern).as_dict()
    return out


def build(st: DatasetStore, updated: str | None = None) -> dict[str, Any]:
    """The published data file for the findings page."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw, courts = extract_main(st)
        s = an.jsonify(an.build_main(an.jsonify(raw), courts))
        s2 = an.jsonify(an.build_more(an.jsonify(extract_more(st))))
        s3 = an.jsonify(extract_services(st))
    out = an.pack(s, s2, s3, sources(st))
    out["updated"] = updated or os.environ.get("DATA_DATE") or datetime.date.today().isoformat()
    return out
