"""A claim ties a number quoted in a page's text to the data it was computed from."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

Data = dict[str, Any]


@dataclass(frozen=True)
class Claim:
    text: str
    value: Callable[[Data], float]
    expected: float
    tol: float

    def check(self, d: Data) -> tuple[bool, float]:
        v = float(self.value(d))
        return abs(v - self.expected) <= self.tol, v

    def line(self, d: Data) -> tuple[bool, str]:
        ok, v = self.check(d)
        return ok, ("OK   " if ok else "FAIL ") + f"{self.text}: data {v:.2f}, text {self.expected}"


def avg(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def by_x(series: list[list[float]]) -> dict[float, float]:
    return {round(x, 3): y for x, y in series}


def yearly(series: list[list[float]], year: int) -> float:
    return avg([v for x, v in series if int(x) == year])
