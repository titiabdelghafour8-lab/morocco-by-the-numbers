from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = Path(__file__).parent / "golden"
DATASETS = os.environ.get("MBN_DATASETS")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if DATASETS and Path(DATASETS).is_dir():
        return
    skip = pytest.mark.skip(reason="set MBN_DATASETS to the downloaded portal files to run")
    for item in items:
        if "datasets" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def golden_data() -> dict[str, Any]:
    with open(GOLDEN / "morocco_by_the_numbers.json", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


@pytest.fixture(scope="session")
def published_data() -> dict[str, Any]:
    with open(ROOT / "data" / "morocco_by_the_numbers.json", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data
