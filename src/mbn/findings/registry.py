"""What the site shows: every finding with its datasets, sources and claims.

The CLI, the weekly sync's watch list (``data/datasets.txt``), the claims check and the
page checks all read this registry. Adding a finding means adding an entry here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mbn.model.claims import Claim, Data, avg, by_x, yearly


@dataclass(frozen=True)
class SourceRef:
    """A portal dataset folder, as a glob under <publisher>/; ``last`` picks the newest match."""

    pattern: str
    last: bool = False


@dataclass(frozen=True)
class Finding:
    id: str
    """Section id on the page (``#id``); charts are ``c-...`` inside it."""
    group: str
    title: str
    page: str
    datasets: tuple[str, ...]
    """CKAN dataset-name patterns watched by the weekly sync."""
    sources: tuple[str, ...]
    """Keys into ``SOURCES``: the datasets credited under the chart."""
    claims: tuple[Claim, ...] = field(default=())


ACAPS = "autorite-de-controle-des-assurances-et-de-la-prevoyance-sociale/"
EDU = "ministere-de-l-education-nationale-et-de-la-formation-professionnelle/"

# Order matters: it is the order of ``src`` in the published data file.
SOURCES: dict[str, SourceRef] = {
    "flow": SourceRef("agence-du-bassin-hydraulique-de-souss-massa/debit-moyen-journalier-de-la-station-ait*"),
    "rain": SourceRef("agence-du-bassin-hydraulique-de-souss-massa/pluie-journaliere-du-barrage-y*"),
    "cereals": SourceRef("departement-de-l-agriculture/production*"),
    "u_age": SourceRef("haut-commissariat-au-plan/data_i4252"),
    "u_dip": SourceRef("haut-commissariat-au-plan/data_i4248"),
    "region": SourceRef("haut-commissariat-au-plan/data_i3287"),
    "prov": SourceRef("haut-commissariat-au-plan/data_imt_txch_02"),
    "cpi": SourceRef("haut-commissariat-au-plan/data_i4166"),
    "amo": SourceRef(ACAPS + "taux-de-couverture*"),
    "internet": SourceRef("anrt/parc-de-l-internet*"),
    "mobile": SourceRef("anrt/parc-de-la-telephonie-mobile*"),
    "roads": SourceRef("narsa/statistiques-des-accidents-de-la-circulation-routiere-2024"),
    "courts": SourceRef("ministere-de-la-justice-et-des-libertes/evolution-des-affaires-au-cours-du-quinquennat-2018-2022"),
    "corr": SourceRef("l-instance-nationale*/indice-de-perception*"),
    "gdp": SourceRef("haut-commissariat-au-plan/data_i4276"),
    "credit": SourceRef("bank-al-maghrib/creances-sur-l-economie*"),
    "funds": SourceRef("ammc/stat-hebdo-opcvm-2026"),
    "startups": SourceRef("agence-de-developpement-du-digital/donnees-sur-les-startups"),
    "pensions": SourceRef(ACAPS + "rapport-demographique*"),
    "parliament": SourceRef("parlement/liste-des-questions-ecrites-de-la-session-d-avril"),
    "amo_in": SourceRef(ACAPS + "ressources-des-regimes-amo"),
    "amo_out": SourceRef(ACAPS + "depenses-des-regimes-amo"),
    "pen_in": SourceRef(ACAPS + "cotisations-des-regimes-de-retraite"),
    "pen_out": SourceRef(ACAPS + "prestations-des-regimes-de-retraite"),
    "pen_res": SourceRef(ACAPS + "reserves-des-regimes-de-retraite"),
    "vehicles": SourceRef("narsa/statistiques-des-immatriculations-et-permis-de-conduire-delivres*", last=True),
    "primary_care": SourceRef("ministere-de-la-sante/repartition-des-etablissements-de-soins-de-sante-primaire*"),
    "hospitals": SourceRef("ministere-de-la-sante/la-liste-des-hopitaux"),
    "schools": SourceRef(EDU + "liste-des-etablissements-publics-primaire"),
}


def _flow(d: Data) -> dict[int, float]:
    return dict(d["flow"])


def _rain(d: Data) -> dict[int, float]:
    return dict(d["rain"])


def _reg(d: Data, name: str) -> list[float]:
    return {r[0]: r for r in d["region"]}[name]  # type: ignore[no-any-return]


def _roads(d: Data) -> dict[int, list[int]]:
    return {r[0]: r for r in d["roads"]}


def _svc(d: Data, name: str) -> list[float]:
    return {r[0]: r for r in d["services"]}[name]  # type: ignore[no-any-return]


def _af(d: Data) -> dict[str, dict[int, float]]:
    return {k: dict(v) for k, v in d["amo_finance"].items()}


def _pm(d: Data) -> dict[str, dict[int, float]]:
    return {k: dict(v) for k, v in d["pension_money"].items()}


def _vh(d: Data) -> dict[str, dict[int, float]]:
    return {k: dict(v) for k, v in d["vehicles"].items()}


def _deficit_run_start(d: Data) -> int:
    pm = _pm(d)
    b, c = pm["benefits"], pm["contributions"]
    return min(y for y in b if all(b[z] > c[z] for z in b if z >= y))


FINDINGS: tuple[Finding, ...] = (
    Finding(
        "water",
        "land",
        "The Souss river has almost stopped flowing",
        "index",
        ("debit-moyen-journalier-de-la-station-ait-melloul*", "pluie-journaliere-du-barrage-y-b-tachfine*"),
        ("flow", "rain"),
        (
            Claim("Souss flow 1971-1999 average (m3/s)", lambda d: avg([v for y, v in _flow(d).items() if y <= 1999]), 6.6, 0.05),
            Claim(
                "Souss flow since 2015 average (m3/s)", lambda d: avg([v for y, v in _flow(d).items() if y >= 2015]), 1.4, 0.05
            ),
            Claim(
                "Rainfall change 1969-1999 vs 2015+ (%)",
                lambda d: (
                    (avg([v for y, v in _rain(d).items() if y >= 2015]) / avg([v for y, v in _rain(d).items() if y <= 1999]) - 1)
                    * 100
                ),
                -20,
                3,
            ),
        ),
    ),
    Finding(
        "harvest",
        "land",
        "A drought year can cut the cereal harvest by two-thirds",
        "index",
        ("production-vegetale*",),
        ("cereals",),
        (
            Claim(
                "Poor harvests under 6 Mt, last 12 seasons",
                lambda d: sum(v < 6 for v in list(dict(d["cereals"]).values())[-12:]),
                5,
                0,
            ),
        ),
    ),
    Finding(
        "youth",
        "work",
        "More than a third of young people looking for work can't find it",
        "index",
        ("data_i4252",),
        ("u_age",),
        (
            Claim("Youth unemployment 2017 average (%)", lambda d: yearly(d["u_youth"], 2017), 27, 0.5),
            Claim("Youth unemployment 2025 average (%)", lambda d: yearly(d["u_youth"], 2025), 37, 0.5),
            Claim("Young women unemployment 2025 average (%)", lambda d: yearly(d["u_youth_w"], 2025), 53, 0.5),
            Claim("National unemployment 2025 average (%)", lambda d: yearly(d["u_total"], 2025), 13.0, 0.05),
        ),
    ),
    Finding(
        "degrees",
        "work",
        "Graduates are six times more likely to be unemployed",
        "index",
        ("data_i4248",),
        ("u_dip",),
        (
            Claim("Higher-degree unemployment Q4 2025 (%)", lambda d: by_x(d["u_high"])[2025.75], 25.7, 0.05),
            Claim("No-diploma unemployment Q4 2025 (%)", lambda d: by_x(d["u_none"])[2025.75], 4.2, 0.05),
        ),
    ),
    Finding(
        "regions",
        "work",
        "In the South, more than half of women in the labour force are unemployed",
        "index",
        ("data_i3287", "data_imt_txch_02"),
        ("region", "prov"),
        (
            Claim("Southern regions unemployment 2025 (%)", lambda d: _reg(d, "Régions du Sud")[1], 22.8, 0.05),
            Claim("Southern regions women unemployment 2025 (%)", lambda d: _reg(d, "Régions du Sud")[3], 53.5, 0.05),
            Claim("Marrakech-Safi unemployment 2025 (%)", lambda d: _reg(d, "Marrakech-safi")[1], 8.1, 0.05),
        ),
    ),
    Finding(
        "gdp",
        "economy",
        "The economy is growing 4-5% a year, after a 14-15% drop in spring 2020",
        "index",
        ("data_i4276",),
        ("gdp",),
    ),
    Finding(
        "credit",
        "economy",
        "Bank lending is growing at its fastest pace since 2010",
        "index",
        ("creances-sur-l-economie*",),
        ("credit",),
        (Claim("Credit growth latest (%)", lambda d: d["credit"][-1][1], 11.0, 0.05),),
    ),
    Finding(
        "prices",
        "economy",
        "Food inflation peaked at about 20%. Food prices are now falling",
        "index",
        ("data_i4166",),
        ("cpi",),
        (Claim("Food inflation Aug 2026 (%)", lambda d: d["infl_food"][-1][1], -4.2, 0.05),),
    ),
    Finding(
        "funds",
        "economy",
        "Money held in investment funds has grown 77% since 2020",
        "index",
        ("stat-hebdo-opcvm-*",),
        ("funds",),
        (Claim("Fund assets growth since Jan 2020 (%)", lambda d: (d["funds"][-1][1] / d["funds"][0][1] - 1) * 100, 77, 0.6),),
    ),
    Finding(
        "startups",
        "economy",
        "More than two in three listed startups are in Casablanca or Rabat",
        "index",
        ("donnees-sur-les-startups",),
        ("startups",),
        (Claim("Startups (unique companies)", lambda d: d["startup_n"], 802, 0),),
    ),
    Finding(
        "health",
        "living",
        "Health insurance went from 1 in 5 Moroccans to 3 in 4",
        "index",
        ("taux-de-couverture-de-la-population-marocaine-par-l-amo*",),
        ("amo",),
        (Claim("AMO coverage 2024 (%)", lambda d: dict(d["amo"])[2024], 77.1, 0.05),),
    ),
    Finding(
        "amo-money",
        "living",
        "Health insurance pays out five times more than in 2012",
        "index",
        ("ressources-des-regimes-amo*", "depenses-des-regimes-amo*"),
        ("amo_in", "amo_out"),
        (
            Claim("AMO benefits paid 2012 (bn)", lambda d: _af(d)["benefits_paid"][2012], 5.1, 0.05),
            Claim("AMO benefits paid 2024 (bn)", lambda d: _af(d)["benefits_paid"][2024], 27.2, 0.05),
            Claim("AMO income 2024 (bn)", lambda d: _af(d)["resources"][2024], 46.1, 0.05),
            Claim("AMO spending 2024 (bn)", lambda d: _af(d)["expenses"][2024], 40.9, 0.05),
            Claim(
                "Years AMO spending exceeded income",
                lambda d: sum(_af(d)["expenses"][y] > _af(d)["resources"][y] for y in _af(d)["resources"]),
                1,
                0,
            ),
        ),
    ),
    Finding(
        "services",
        "living",
        "Casablanca-Settat has the fewest public health centres per resident",
        "index",
        (
            "la-liste-des-hopitaux",
            "repartition-des-etablissements-de-soins-de-sante-primaire*",
            "liste-des-etablissements-publics-primaire",
            "liste-de-etablissements-publics-collegial",
            "liste-des-etablissements-publics-qualifiants",
        ),
        ("primary_care", "hospitals", "schools"),
        (
            Claim("Health centres per 100k, Casablanca-Settat", lambda d: _svc(d, "Casablanca-Settat")[1], 4.9, 0.05),
            Claim("Health centres per 100k, Guelmim-Oued Noun", lambda d: _svc(d, "Guelmim-Oued Noun")[1], 22, 0.5),
            Claim("Health centres and dispensaries (total)", lambda d: d["services_totals"]["primary_care"], 3086, 0),
        ),
    ),
    Finding(
        "pensions",
        "living",
        "Fewer workers now pay in for each pensioner",
        "index",
        ("rapport-demographique-des-regimes-de-base*",),
        ("pensions",),
        (Claim("Pension contributors per pensioner, latest", lambda d: d["pension_ratio"][-1][1], 4.8, 0.05),),
    ),
    Finding(
        "pension-money",
        "living",
        "Since 2017, the basic pension schemes have paid out more than they collect",
        "index",
        ("cotisations-des-regimes-de-retraite*", "prestations-des-regimes-de-retraite*", "reserves-des-regimes-de-retraite*"),
        ("pen_in", "pen_out", "pen_res"),
        (
            Claim("Pension contributions 2024 (bn)", lambda d: _pm(d)["contributions"][2024], 73.0, 0.05),
            Claim("Pensions paid 2024 (bn)", lambda d: _pm(d)["benefits"][2024], 78.7, 0.05),
            Claim("First year of a run of deficits to today", _deficit_run_start, 2017, 0),
            Claim("Pension reserves peak (bn)", lambda d: max(_pm(d)["reserves"].values()), 270.9, 0.05),
            Claim("Pension reserves 2024 (bn)", lambda d: _pm(d)["reserves"][2024], 264.9, 0.05),
        ),
    ),
    Finding(
        "internet",
        "living",
        "There are now more internet subscriptions than people",
        "index",
        ("parc-de-l-internet*", "parc-de-la-telephonie-mobile*"),
        ("internet", "mobile"),
        (
            Claim("Internet per 100 people 2025", lambda d: dict(d["internet"])[2025], 113, 0.5),
            Claim("Mobile lines per 100 people 2025", lambda d: dict(d["mobile"])[2025], 161, 0.5),
        ),
    ),
    Finding(
        "roads",
        "living",
        "Road deaths are climbing: 4,024 in 2024, about 11 a day",
        "index",
        ("statistiques-des-accidents-de-la-circulation-routiere*",),
        ("roads",),
        (
            Claim("Road deaths 2024", lambda d: _roads(d)[2024][1], 4024, 0),
            Claim("Road deaths change 2022-2024 (%)", lambda d: (_roads(d)[2024][1] / _roads(d)[2022][1] - 1) * 100, 15, 0.5),
        ),
    ),
    Finding(
        "vehicles",
        "living",
        "Vehicles are multiplying faster than road deaths",
        "index",
        ("statistiques-des-immatriculations-et-permis-de-conduire-delivres*",),
        ("vehicles", "roads"),
        (
            Claim("Vehicles 2023 (millions)", lambda d: _vh(d)["Total"][2023] / 1e6, 4.5, 0.05),
            Claim("Vehicles 2012 (millions)", lambda d: _vh(d)["Total"][2012] / 1e6, 3.1, 0.05),
            Claim("Motorcycles 2023", lambda d: _vh(d)["Motocyclettes"][2023], 312000, 500),
            Claim("Deaths per 10,000 vehicles 2021", lambda d: _roads(d)[2021][1] / _vh(d)["Total"][2021] * 1e4, 9.1, 0.05),
            Claim("Deaths per 10,000 vehicles 2023", lambda d: _roads(d)[2023][1] / _vh(d)["Total"][2023] * 1e4, 8.5, 0.05),
        ),
    ),
    Finding(
        "courts",
        "state",
        "Appeal courts receive 63% more cases than in 2021",
        "index",
        ("evolution-des-affaires-au-cours-du-quinquennat*",),
        ("courts",),
        (
            Claim(
                "Appeal court cases change 2021-2025 (%)",
                lambda d: (dict(d["appeal"])[2025] / dict(d["appeal"])[2021] - 1) * 100,
                63,
                0.6,
            ),
        ),
    ),
    Finding(
        "integrity",
        "state",
        "Morocco has dropped 26 places in the corruption ranking since 2018",
        "index",
        ("indice-de-perception-de-la-corruption*",),
        ("corr",),
        (
            Claim(
                "Corruption rank change 2018-2024 (places)",
                lambda d: {r[0]: r for r in d["corr"]}[2024][2] - {r[0]: r for r in d["corr"]}[2018][2],
                26,
                0,
            ),
        ),
    ),
    Finding(
        "parliament",
        "state",
        "MPs asked 67,000 questions in seven years",
        "index",
        ("liste-des-questions-*",),
        ("parliament",),
        (Claim("Parliamentary questions (unique)", lambda d: d["parl_total"], 67114, 0),),
    ),
)


def by_page(page: str) -> tuple[Finding, ...]:
    return tuple(f for f in FINDINGS if f.page == page)


def all_claims(page: str = "index") -> list[Claim]:
    return [c for f in by_page(page) for c in f.claims]


def watch_patterns(extra: tuple[str, ...] = ()) -> list[str]:
    """CKAN dataset-name patterns the weekly sync watches, without duplicates, in registry order."""
    seen: dict[str, None] = {}
    for f in FINDINGS:
        for p in f.datasets:
            seen.setdefault(p)
    for p in extra:
        seen.setdefault(p)
    return list(seen)
