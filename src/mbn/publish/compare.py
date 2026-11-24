"""Compare a freshly built data file with the published one (for the review summary)."""

from __future__ import annotations

from typing import Any

IGNORED = ("src", "updated")


def changed_series(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    lines = []
    for k, v in new.items():
        if k in IGNORED or old.get(k) == v:
            continue
        if isinstance(v, list) and v and isinstance(old.get(k), list) and old[k]:
            lines.append(f"- **{k}**: last point {old[k][-1]} → {v[-1]} ({len(v) - len(old[k]):+d} points)")
        else:
            lines.append(f"- **{k}**: changed")
    return lines


def summary(pages: dict[str, list[str]]) -> str:
    """Markdown review summary; ``pages`` maps a page name to its changed-series lines."""
    body = [
        "## New data on data.gov.ma",
        "",
        "The weekly sync rebuilt the site from the latest portal files. These series changed:",
        "",
    ]
    any_change = False
    for page, lines in pages.items():
        if lines:
            any_change = True
            body += [f"**{page}**", "", *lines, ""]
    if not any_change:
        body += ["- none", ""]
    body += [
        "### Before merging",
        "",
        "- Charts update automatically, but some headline numbers in the text do not. Check every finding whose "
        "series changed and update its wording in `site/templates/` and its claims in `src/mbn/findings/`.",
        "- Check for method changes or breaks in the new data.",
        "- Re-run `mbn render` after editing a template.",
    ]
    return "\n".join(body) + "\n"
