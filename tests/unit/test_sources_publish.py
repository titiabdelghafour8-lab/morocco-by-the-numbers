from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from mbn import cli
from mbn.config import ROOT
from mbn.findings import registry
from mbn.model.claims import Claim
from mbn.publish import claims, compare, data_export, site
from mbn.sources import ckan, files
from mbn.sources.store import DatasetStore


# --- CKAN ------------------------------------------------------------------------------------------
def fake_portal(datasets: list[dict[str, Any]]) -> ckan.Fetch:
    def fetch(url: str) -> dict[str, Any]:
        start = int(url.split("start=")[1].split("&")[0])
        rows = int(url.split("rows=")[1].split("&")[0])
        return {"result": {"count": len(datasets), "results": datasets[start : start + rows]}}

    return fetch


def test_search_pages_through_the_catalogue() -> None:
    ds = [{"name": f"d{i}", "metadata_modified": "2026-01-01T00:00:00.123456"} for i in range(450)]
    assert len(list(ckan.search(fetch=fake_portal(ds)))) == 450


def test_watched_state_keeps_matches_to_the_second() -> None:
    ds = [{"name": "data_i4166", "metadata_modified": "2026-10-30T10:55:18.123Z"}, {"name": "other", "metadata_modified": "x"}]
    assert ckan.watched_state(["data_i41*"], fetch=fake_portal(ds)) == {"data_i4166": "2026-10-30T10:55:18"}


def test_diff_states_lists_new_updated_and_removed() -> None:
    old = {"a": "2026-01-01T00:00:00.999", "b": "2026-01-01T00:00:00", "gone": "x"}
    new = {"a": "2026-01-01T00:00:00", "b": "2026-02-01T00:00:00", "c": "2026-03-01T00:00:00"}
    assert ckan.diff_states(old, new) == ["- `b`: updated 2026-02-01", "- `c`: new dataset", "- `gone`: removed from the portal"]


# --- files ------------------------------------------------------------------------------------------
def test_safe_names_and_unique_filenames() -> None:
    assert files.safe("a<b>:c?") == "a_b__c_"
    used: set[str] = set()
    res = {"url": "https://x/y/report.xlsx", "id": "1"}
    assert files.filename_for(res, used) == "report.xlsx"
    assert files.filename_for(res, used) == "report_2.xlsx"
    assert files.filename_for({"url": "https://x/", "id": "z", "name": "N", "format": "CSV"}, used) == "N.csv"


def test_store_finds_files_and_metadata(tmp_path: Path) -> None:
    d = tmp_path / "pub" / "ds-1"
    d.mkdir(parents=True)
    (d / "a.xlsx").write_bytes(b"x")
    (d / "metadata.json").write_text(
        json.dumps({"title": " T ", "name": "ds-1", "organization": {"title": "Org"}}), encoding="utf-8"
    )
    st = DatasetStore(tmp_path)
    assert [Path(p).name for p in st.files("pub/ds-*/*")] == ["a.xlsx"]
    assert st.source("pub/ds-*").as_dict() == {"title": "T", "org": "Org", "url": "https://data.gov.ma/data/fr/dataset/ds-1"}
    with pytest.raises(FileNotFoundError):
        st.file("pub/none/*")
    with pytest.raises(FileNotFoundError):
        st.source("nothing")


# --- claims and comparison ----------------------------------------------------------------------------
def test_claim_line_format_is_stable() -> None:
    c = Claim("Answer", lambda d: d["x"], 42, 0)
    assert c.line({"x": 42}) == (True, "OK   Answer: data 42.00, text 42")
    assert c.line({"x": 41}) == (False, "FAIL Answer: data 41.00, text 42")


def test_claim_that_cannot_be_computed_fails() -> None:
    lines, failed = claims.check([Claim("Missing", lambda d: d["nope"], 1, 0)], {})
    assert failed == 1 and lines[0].startswith("FAIL Missing: could not compute")


def test_all_44_claims_hold_on_the_golden_data(golden_data: dict[str, Any]) -> None:
    lines, failed = claims.check(registry.all_claims("index"), golden_data)
    assert failed == 0, "\n".join(lines)
    assert lines[-1] == "44/44 claims hold"


def test_changed_series_ignores_sources_and_date() -> None:
    old = {"a": [[1, 2]], "src": 1, "updated": "x", "b": 1}
    new = {"a": [[1, 2], [2, 3]], "src": 2, "updated": "y", "b": 2}
    assert compare.changed_series(old, new) == ["- **a**: last point [1, 2] → [2, 3] (+1 points)", "- **b**: changed"]
    assert "- none" in compare.summary({"findings": []})


# --- registry, site and CLI ------------------------------------------------------------------------------
def test_registry_has_21_findings_each_with_sources_and_datasets() -> None:
    assert len(registry.FINDINGS) == 21
    for f in registry.FINDINGS:
        assert f.datasets and f.sources
        assert all(k in registry.SOURCES for k in f.sources)


def test_every_finding_has_a_section_and_every_section_a_finding() -> None:
    tpl = site.read_template("index.html")
    for f in registry.FINDINGS:
        assert f'<section class="ch" id="{f.id}">' in tpl


def test_watchlist_file_is_generated_from_registry() -> None:
    assert cli.main(["watchlist", "--check"]) == 0


def test_render_and_claims_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(site, "ROOT", tmp_path)
    written: dict[str, str] = {}
    monkeypatch.setattr(cli.site, "write_page", lambda name, html: written.setdefault(name, html))
    assert cli.main(["render"]) == 0
    assert site.chart_ids(written["index.html"]) == site.chart_ids(site.read_template("index.html"))
    assert cli.main(["claims"]) == 0


def test_verify_command_writes_outputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    old = tmp_path / "old"
    old.mkdir()
    data_export.write_json(
        old / "morocco_by_the_numbers.json", data_export.read_json(ROOT / "data" / "morocco_by_the_numbers.json")
    )
    rc = cli.main(["verify", "--old", str(old), "--summary", str(tmp_path / "s.md"), "--claims", str(tmp_path / "c.txt")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "changed=false" in out and "claims_ok=true" in out
    assert "claims hold" in (tmp_path / "c.txt").read_text(encoding="utf-8")
