"""The pages work in a real browser: every chart draws, the theme switch works, no sideways scroll on phones."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from mbn.findings.pages import PAGES
from mbn.publish import site

pytestmark = pytest.mark.e2e

PAGE_FILES = [p.html for p in PAGES]


@pytest.fixture(params=[(1280, 900), (375, 812)], ids=["desktop", "phone"])
def viewport(request: pytest.FixtureRequest, page: Page) -> tuple[int, int]:
    w, h = request.param
    page.set_viewport_size({"width": w, "height": h})
    return w, h


@pytest.mark.parametrize("html", PAGE_FILES)
def test_every_chart_draws(page: Page, site_url: str, viewport: tuple[int, int], html: str) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{site_url}/{html}")
    n = len(site.chart_ids(site.read_template(html)))
    charts = page.locator(".chart")
    expect(charts).to_have_count(n)
    for i in range(n):
        expect(charts.nth(i).locator("svg")).to_have_count(1)
    assert not errors


@pytest.mark.parametrize("html", PAGE_FILES)
def test_no_sideways_scroll(page: Page, site_url: str, viewport: tuple[int, int], html: str) -> None:
    page.goto(f"{site_url}/{html}")
    page.wait_for_selector(".chart svg")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


@pytest.mark.parametrize("html", PAGE_FILES)
def test_theme_switch_toggles_and_is_remembered(page: Page, site_url: str, html: str) -> None:
    page.emulate_media(color_scheme="light")
    page.goto(f"{site_url}/{html}")
    bg_light = page.evaluate("getComputedStyle(document.body).backgroundColor")
    page.click("#theme-toggle")
    assert page.evaluate("document.documentElement.dataset.theme") == "dark"
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") != bg_light
    page.reload()
    assert page.evaluate("document.documentElement.dataset.theme") == "dark"


@pytest.mark.parametrize("html", PAGE_FILES)
def test_every_chart_cites_its_source(page: Page, site_url: str, html: str) -> None:
    page.goto(f"{site_url}/{html}")
    page.wait_for_selector(".chart svg")
    for section in page.locator("section.ch:has(.chart)").all():
        links = section.locator(".source a")
        assert links.count() >= 1
        assert all((links.nth(i).get_attribute("href") or "").startswith("https://") for i in range(links.count()))
