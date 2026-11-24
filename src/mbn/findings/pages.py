"""The site's pages: each one has a data file, a builder, a renderer and claims.

The CLI loops over ``PAGES``; a new project page is one more entry here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mbn.config import DATA_DIR
from mbn.findings import build as findings_build
from mbn.findings.registry import all_claims, watch_patterns
from mbn.model.claims import Claim
from mbn.publish import site
from mbn.sources.store import DatasetStore


@dataclass(frozen=True)
class Page:
    name: str
    """Short name, also the nav label key."""
    html: str
    """Output file at the site root."""
    data_file: Path
    build: Callable[[DatasetStore, str | None], dict[str, Any]]
    render: Callable[[dict[str, Any]], str]
    claims: Callable[[], list[Claim]]
    datasets: tuple[str, ...]
    """CKAN dataset-name patterns this page needs."""


FINDINGS_PAGE = Page(
    name="findings",
    html="index.html",
    data_file=DATA_DIR / "morocco_by_the_numbers.json",
    build=lambda st, updated: findings_build.build(st, updated),
    render=site.render_findings,
    claims=lambda: all_claims("index"),
    datasets=tuple(watch_patterns()),
)

PAGES: tuple[Page, ...] = (FINDINGS_PAGE,)


def page(name: str) -> Page:
    for p in PAGES:
        if p.name == name:
            return p
    raise KeyError(name)


def all_watch_patterns() -> list[str]:
    seen: dict[str, None] = {}
    for p in PAGES:
        for d in p.datasets:
            seen.setdefault(d)
    return list(seen)
