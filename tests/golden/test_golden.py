"""Characterisation tests: the refactor must not change a published byte (apart from the date).

``morocco_by_the_numbers.json`` and ``index.html`` here were snapshotted from ``main``
before the refactor (24 November 2026). If a later, deliberate change to the template
changes the page, regenerate ``index.html`` here with ``mbn render`` and say why in the
commit. The data golden must only change when the portal data does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mbn.findings import build
from mbn.publish import data_export, site
from mbn.sources.store import DatasetStore
from tests.conftest import DATASETS, GOLDEN


def _lf(p: Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def test_findings_page_renders_byte_for_byte(golden_data: dict[str, Any]) -> None:
    assert site.render_findings(golden_data) == _lf(GOLDEN / "index.html")


def test_data_file_serialises_byte_for_byte(golden_data: dict[str, Any]) -> None:
    assert data_export.to_json(golden_data) == _lf(GOLDEN / "morocco_by_the_numbers.json")


@pytest.mark.datasets
def test_rebuild_from_portal_files_is_byte_identical(golden_data: dict[str, Any]) -> None:
    out = build.build(DatasetStore(str(DATASETS)), updated=golden_data["updated"])
    assert data_export.to_json(out) == _lf(GOLDEN / "morocco_by_the_numbers.json")
