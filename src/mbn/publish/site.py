"""Render the static pages from templates and data files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mbn.config import ROOT, TEMPLATES_DIR
from mbn.publish.data_export import to_min_json, write_text

FINDINGS_HEAD = (
    '<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
    '<meta name="description" content="Eleven findings from Morocco\'s open data portal: '
    'water, jobs, prices, health, internet, roads, courts and integrity.">\n'
)
CHART_ID = re.compile(r'class="chart" id="c-[a-z0-9-]*"')


def read_template(name: str, templates: Path = TEMPLATES_DIR) -> str:
    return (templates / name).read_text(encoding="utf-8")


def render_findings(data: dict[str, Any], template: str | None = None) -> str:
    """The findings page (index.html): the data is embedded so the page works offline."""
    page = template if template is not None else read_template("index.html")
    return FINDINGS_HEAD + page.replace("/*DATA*/", to_min_json(data))


def chart_ids(html: str) -> list[str]:
    return CHART_ID.findall(html)


def write_page(name: str, html: str, root: Path = ROOT) -> Path:
    path = root / name
    write_text(path, html)
    return path
