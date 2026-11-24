"""The weekly sync's decision: publish straight away, or ask a person to review the text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mbn.model.claims import Claim
from mbn.publish import claims as claims_mod
from mbn.publish.compare import changed_series


@dataclass(frozen=True)
class Verdict:
    changed: bool
    """Some published series differs from the previous data file."""
    claims_ok: bool
    """Every number quoted in the text still holds."""
    changes: list[str]
    report: list[str]

    @property
    def action(self) -> str:
        """``publish`` (open a pull request that can merge on green CI) or ``review`` (open an issue)."""
        return "publish" if (not self.changed or self.claims_ok) else "review"


def verdict(old: dict[str, Any], new: dict[str, Any], claims: list[Claim]) -> Verdict:
    changes = changed_series(old, new)
    report, failed = claims_mod.check(claims, new)
    return Verdict(changed=bool(changes), claims_ok=failed == 0, changes=changes, report=report)
