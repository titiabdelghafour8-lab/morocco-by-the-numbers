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


def nav_html(links: list[tuple[str, str]], current: str) -> str:
    """Links between the site's pages; empty while the site has a single page."""
    if len(links) < 2:
        return ""
    items = "".join(f'<a href="{href}"{' aria-current="page"' if href == current else ""}>{label}</a>' for label, href in links)
    return f'<nav class="site" aria-label="Pages"><div class="wrap">{items}</div></nav>'


def render_findings(data: dict[str, Any], template: str | None = None, nav: str = "") -> str:
    """The findings page (index.html): the data is embedded so the page works offline."""
    page = template if template is not None else read_template("index.html")
    return FINDINGS_HEAD + page.replace("<!--NAV-->", nav).replace("/*DATA*/", to_min_json(data))


PAGE_HEAD = FINDINGS_HEAD.split('<meta name="description"')[0]
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def render_page(name: str, data: dict[str, Any], nav: str = "", template: str | None = None) -> str:
    """A project page: numbers in the text come from ``data["text"]``; charts fetch the data file.

    Every ``{{key}}`` in the template must have a value, so a sentence can never show a blank.
    """
    page = template if template is not None else read_template(name)
    values: dict[str, str] = data.get("text", {})
    missing = sorted({k for k in PLACEHOLDER.findall(page) if k not in values})
    if missing:
        raise KeyError(f"{name}: no value for {missing}")
    return PAGE_HEAD + PLACEHOLDER.sub(lambda m: values[m.group(1)], page).replace("<!--NAV-->", nav)


def chart_ids(html: str) -> list[str]:
    return CHART_ID.findall(html)


def write_page(name: str, html: str, root: Path = ROOT) -> Path:
    path = root / name
    write_text(path, html)
    return path
