from __future__ import annotations

import copy
import json
from typing import Any

import pandas as pd
import pytest
from pytest_bdd import given, scenarios, then, when

from mbn.analyses import parliament_topics as pt
from mbn.findings import parliament_page
from mbn.publish import data_export

scenarios("parliament.feature")

NAMES = ["Fatima Zahra Example", "فاطمة الزهراء مثال"]


@given("a list of members' names", target_fixture="names")
def names() -> list[str]:
    return NAMES


@given("a topic whose representative questions include one that names a member", target_fixture="model")
def model_with_name() -> dict[str, Any]:
    return {
        "fingerprint": "abc",
        "topics": [
            {
                "id": 0,
                "size": 3,
                "words": ["ماء", "سد"],
                "examples": ["بناء السدود", "سؤال فاطمة الزهراء مثال حول الماء", "الماء الصالح للشرب"],
            }
        ],
    }


@when("the parliament page data is built", target_fixture="out")
def build(model: dict[str, Any], names: list[str]) -> dict[str, Any]:
    labels = {"fingerprint": pt.fingerprint(model["topics"]), "topics": {"0": {"en": "Water", "fr": "Eau", "ar": "الماء"}}}
    assignments = pd.DataFrame(
        {"kind": ["oral"] * 3, "number": ["1", "2", "3"], "date_key": ["2019-01-01"] * 3, "topic": [0, 0, 0]}
    )
    questions = assignments.assign(date=pd.to_datetime(assignments["date_key"]))
    return parliament_page.analyse(questions, assignments, model, labels, member_names=names)


@then("no published parliament file contains any member's name")
def no_names(out: dict[str, Any], names: list[str]) -> None:
    text = json.dumps(out, ensure_ascii=False)
    assert not pt.contains_any(text, names)


@then("the topic still shows its other representative questions")
def others_kept(out: dict[str, Any]) -> None:
    assert out["topics"][0]["examples"] == ["بناء السدود", "الماء الصالح للشرب"]


@given("topic labels reviewed for the current topic model", target_fixture="ctx")
def reviewed() -> dict[str, Any]:
    model = data_export.read_json(parliament_page.MODEL_FILE)
    labels = data_export.read_json(parliament_page.LABELS_FILE)
    return {"model": model, "labels": labels}


@when("the topic model is rerun and its topics change")
def rerun(ctx: dict[str, Any]) -> None:
    m = copy.deepcopy(ctx["model"])
    m["topics"][0]["words"] = ["different", *m["topics"][0]["words"][1:]]
    m["fingerprint"] = pt.fingerprint(m["topics"])
    ctx["model"] = m


@then("building the parliament page fails and asks for the labels to be reviewed")
def fails(ctx: dict[str, Any]) -> None:
    with pytest.raises(pt.LabelsOutOfDate, match="review"):
        pt.check_labels(ctx["model"], ctx["labels"])


@given("the reviewed topic labels", target_fixture="labels")
def labels() -> dict[str, Any]:
    return data_export.read_json(parliament_page.LABELS_FILE)  # type: ignore[no-any-return]


@then("every topic has a name in Arabic, French and English")
def named(labels: dict[str, Any]) -> None:
    model = data_export.read_json(parliament_page.MODEL_FILE)
    for t in model["topics"]:
        lab = labels["topics"][str(t["id"])]
        assert all(lab.get(k, "").strip() for k in ("ar", "fr", "en"))


@given("the published parliament data", target_fixture="data")
def published() -> dict[str, Any]:
    return data_export.read_json(parliament_page.DATA_FILE)  # type: ignore[no-any-return]


@then("each year's topic shares add up to 100%")
def shares(data: dict[str, Any]) -> None:
    for j, _year in enumerate(data["years"]):
        assert abs(sum(t["share"][j] for t in data["topics"]) - 100) < 0.5
