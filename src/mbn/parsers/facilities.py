"""Public facility lists (Ministry of Health, Ministry of Education): count by region."""

from __future__ import annotations

import unicodedata
from typing import Any, cast

import pandas as pd

REGION_KEYS = {
    "tanger": "Tanger-Tétouan-Al Hoceïma",
    "oriental": "Oriental",
    "fes": "Fès-Meknès",
    "rabat": "Rabat-Salé-Kénitra",
    "beni": "Béni Mellal-Khénifra",
    "casablanca": "Casablanca-Settat",
    "marrakech": "Marrakech-Safi",
    "draa": "Drâa-Tafilalet",
    "souss": "Souss-Massa",
    "guelmim": "Guelmim-Oued Noun",
    "laayoune": "Laâyoune-Sakia El Hamra",
    "dakhla": "Dakhla-Oued Ed-Dahab",
}
PRIMARY_CARE = {"CSU-1", "CSU-2", "CSR-1", "CSR-2", "DR"}
"""Urban and rural health centres and rural dispensaries; excludes labs and specialist centres."""


def region(v: object) -> str | None:
    """Official region name from any spelling (accents, case and extra words ignored)."""
    s = unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode().lower()
    return next((r for k, r in REGION_KEYS.items() if k in s), None)


def count_by_region(path: Any, col_hint: set[str], keep: set[str] | None = None) -> tuple[dict[str, int], int]:
    """({region: facilities}, rows whose region could not be matched).

    The header row is the first of the first 15 rows with a cell in ``col_hint``;
    ``keep`` filters on the "Catégorie" column.
    """
    df = pd.read_excel(path, header=None)
    hdr = next(i for i in range(15) if any(str(c).strip().lower() in col_hint for c in df.iloc[i]))
    col = next(j for j, c in enumerate(df.iloc[hdr]) if str(c).strip().lower() in col_hint)
    body = df.iloc[hdr + 1 :]
    if keep:
        cat = next(j for j, c in enumerate(df.iloc[hdr]) if str(c).strip().lower().startswith("cat"))
        body = body[body[cat].astype(str).str.strip().isin(keep)]
    regs = body[col].map(region)
    counts = cast(dict[str, int], regs.value_counts().to_dict())
    return counts, int(regs.isna().sum())
