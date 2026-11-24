"""CKAN client for data.gov.ma: one place for retries and the user agent."""

from __future__ import annotations

import fnmatch
import json
import time
import urllib.request
from collections.abc import Callable, Iterable, Iterator
from typing import Any

from mbn.config import CKAN_API, USER_AGENT

Fetch = Callable[[str], dict[str, Any]]


def get_json(url: str, retries: int = 4, backoff: float = 5.0, user_agent: str = USER_AGENT) -> dict[str, Any]:
    """GET a JSON document, retrying with a growing pause."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": user_agent})
            with urllib.request.urlopen(req, timeout=60) as r:
                result: dict[str, Any] = json.load(r)
                return result
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(backoff * (attempt + 1))
    raise RuntimeError("unreachable")


def search(fields: str | None = None, rows: int = 200, fetch: Fetch = get_json) -> Iterator[dict[str, Any]]:
    """Yield every dataset on the portal (optionally only some fields)."""
    start = 0
    while True:
        url = f"{CKAN_API}/package_search?rows={rows}&start={start}" + (f"&fl={fields}" if fields else "")
        res = fetch(url)["result"]
        yield from res["results"]
        start += rows
        if start >= res["count"]:
            return


def matches(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def norm_time(s: object) -> str:
    """Timestamps come back in two formats (microseconds or milliseconds + Z): compare to the second."""
    return str(s)[:19]


def watched_state(patterns: list[str], fetch: Fetch = get_json) -> dict[str, str]:
    """Last-modified time of every watched dataset on the portal."""
    return {
        d["name"]: norm_time(d["metadata_modified"])
        for d in search("name,metadata_modified", fetch=fetch)
        if matches(d["name"], patterns)
    }


def diff_states(old: dict[str, str], new: dict[str, str]) -> list[str]:
    """Markdown lines describing new, updated and removed datasets (pure)."""
    old = {k: norm_time(v) for k, v in old.items()}
    lines = [
        f"- `{n}`: {'new dataset' if n not in old else 'updated ' + new[n][:10]}" for n in sorted(new) if old.get(n) != new[n]
    ]
    lines += [f"- `{n}`: removed from the portal" for n in sorted(set(old) - set(new))]
    return lines
