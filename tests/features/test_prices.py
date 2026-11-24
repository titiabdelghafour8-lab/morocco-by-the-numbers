from __future__ import annotations

import copy
from typing import Any

from pytest_bdd import given, scenarios, then, when

from mbn.analyses import prices
from mbn.findings import prices_page
from mbn.publish import data_export
from mbn.publish.review import Verdict, verdict

scenarios("prices.feature")


@given("the published prices data", target_fixture="ctx")
def published() -> dict[str, Any]:
    d = data_export.read_json(prices_page.DATA_FILE)
    return {"old": d, "new": copy.deepcopy(d)}


@given("HCP publishes a new month in which headline inflation stays within its claim")
def new_month(ctx: dict[str, Any]) -> None:
    last_x, last_v = ctx["new"]["headline"][-1][:2]
    ctx["new"]["headline"].append([round(last_x + 1 / 12, 3), last_v, ctx["new"]["headline"][-1][2]])


@when("the sync checks the rebuilt data", target_fixture="result")
def check(ctx: dict[str, Any]) -> Verdict:
    return verdict(ctx["old"], ctx["new"], prices_page.CLAIMS)


@then("the data has changed")
def changed(result: Verdict) -> None:
    assert result.changed


@then("the sync opens a pull request to publish")
def publish(result: Verdict) -> None:
    assert result.action == "publish", "\n".join(result.report)


@given('back-test errors where the best model is worse than "same change as last year"', target_fixture="errors")
def worse() -> dict[str, float]:
    return {"seasonal naive": 0.80, "ETS": 0.95, "ARIMA": 0.90}


@given('back-test errors where ETS beats "same change as last year"', target_fixture="errors")
def better() -> dict[str, float]:
    return {"seasonal naive": 0.80, "ETS": 0.60, "ARIMA": 0.90}


@when("the page decides whether to publish a forecast", target_fixture="decision")
def decide(errors: dict[str, float]) -> prices.ForecastDecision:
    return prices.forecast_decision(errors)


@then("no forecast is published")
def none(decision: prices.ForecastDecision) -> None:
    assert decision.model is None


@then("the page says that no model beat the benchmark")
def says(decision: prices.ForecastDecision) -> None:
    assert "No forecast is published" in prices_page.forecast_sentence(decision)


@then("the ETS forecast is published")
def ets(decision: prices.ForecastDecision) -> None:
    assert decision.model == "ETS"


@then("the contributions of the twelve divisions add up to headline inflation within 0.1 points")
def adds_up(ctx: dict[str, Any]) -> None:
    d = ctx["new"]
    total = sum(r[2] for r in d["contributions"])
    assert len(d["contributions"]) == 12
    assert abs(total - d["summary"]["headline_yoy"]) <= 0.1
