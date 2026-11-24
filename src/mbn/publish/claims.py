"""Evaluate claims and produce the review report."""

from __future__ import annotations

from collections.abc import Iterable

from mbn.model.claims import Claim, Data


def check(claims: Iterable[Claim], d: Data) -> tuple[list[str], int]:
    """Report lines and the number of claims that failed (or could not be computed)."""
    lines, failed, total = [], 0, 0
    for c in claims:
        total += 1
        try:
            ok, line = c.line(d)
        except (KeyError, IndexError, ValueError, ZeroDivisionError, TypeError) as e:
            ok, line = False, f"FAIL {c.text}: could not compute ({type(e).__name__}: {e})"
        failed += not ok
        lines.append(line)
    lines.append("")
    lines.append(f"{total - failed}/{total} claims hold")
    return lines, failed
