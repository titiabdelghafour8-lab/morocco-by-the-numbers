from __future__ import annotations

import copy
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from mbn.config import WATCH_FILE
from mbn.findings import registry
from mbn.findings.pages import all_watch_patterns
from mbn.publish.review import Verdict, verdict

scenarios("sync.feature")


@given("the published findings data", target_fixture="ctx")
def published(golden_data: dict[str, Any]) -> dict[str, Any]:
    return {"old": golden_data, "new": copy.deepcopy(golden_data)}


@given("the portal adds a month that changes no quoted number")
def add_month(ctx: dict[str, Any]) -> None:
    last_x, last_v = ctx["new"]["infl"][-1]
    ctx["new"]["infl"].append([round(last_x + 1 / 12, 3), last_v])  # headline inflation has no quoted number


@given(parsers.parse("the portal revises the latest food inflation to {value:f}%"))
def revise(ctx: dict[str, Any], value: float) -> None:
    ctx["new"]["infl_food"][-1][1] = value


@when("the sync checks the rebuilt data", target_fixture="result")
def check(ctx: dict[str, Any]) -> Verdict:
    return verdict(ctx["old"], ctx["new"], registry.all_claims("index"))


@then("the data has changed")
def changed(result: Verdict) -> None:
    assert result.changed


@then("the data has not changed")
def unchanged(result: Verdict) -> None:
    assert not result.changed


@then("every claim holds")
def all_hold(result: Verdict) -> None:
    assert result.claims_ok, "\n".join(result.report)


@then(parsers.parse('the claim "{text}" fails'))
def claim_fails(result: Verdict, text: str) -> None:
    assert any(line.startswith(f"FAIL {text}:") for line in result.report)


@then("the sync opens a pull request to publish")
def publish(result: Verdict) -> None:
    assert result.action == "publish"


@then("the sync opens a data-review issue instead of publishing")
def review(result: Verdict) -> None:
    assert result.action == "review"


@given("the registry of findings", target_fixture="watch")
def watch() -> list[str]:
    return [line for line in WATCH_FILE.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]


@then("every dataset pattern a finding needs is in data/datasets.txt")
def all_needed(watch: list[str]) -> None:
    needed = {p for f in registry.FINDINGS for p in f.datasets}
    assert needed <= set(watch)


@then("data/datasets.txt has no pattern that no page needs")
def nothing_extra(watch: list[str]) -> None:
    assert set(watch) == set(all_watch_patterns())
