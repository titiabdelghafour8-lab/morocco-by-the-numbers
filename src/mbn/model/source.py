"""Where a published figure comes from (needed for ODbL attribution on every chart)."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Source:
    title: str
    org: str
    url: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)
