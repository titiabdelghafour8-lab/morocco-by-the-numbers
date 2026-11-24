"""House of Representatives question files (written and oral questions).

Files overlap (the same session appears in more than one file) and one file has no header
row. Only the question number, date, ministry and (for topic work) subject and text are
read: MP names and parliamentary groups are never kept.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

KINDS = ("oral", "written")
COLUMNS = ["kind", "number", "date_key", "date", "ministry", "subject", "text"]


def kind_of(path: str) -> str:
    return "oral" if "orales" in path else "written"


def _find(cols: list[str], *needles: str) -> str | None:
    return next((k for k in cols if any(n in k for n in needles)), None)


def read_questions(path: str) -> pd.DataFrame:
    """One question file -> columns kind, number (text), date_key (text), date (raw), ministry, subject, text.

    ``subject`` and ``text`` are empty strings when the file has no such column.
    """
    kind = kind_of(path)
    x = pd.read_excel(path)
    cols = [str(k).strip().lower() for k in x.columns]
    if any("minist" in k for k in cols):
        x.columns = cols
        m = next(k for k in cols if "minist" in k)
        dcol = next(k for k in cols if "date" in k)
        ncol = next((k for k in cols if "num" in k), cols[0])
        subj = _find(cols, "موضوع", "objet", "sujet")
        text = _find(cols, "نص", "texte", "contenu")
        frame = x
    else:  # one file ships without a header row
        frame = pd.read_excel(path, header=None)
        m, dcol, ncol = 6, 2, 0  # type: ignore[assignment]
        subj = text = None
    n = len(frame)
    return pd.DataFrame(
        {
            "kind": [kind] * n,
            "number": [str(v).strip() for v in frame[ncol]],
            "date_key": [str(v)[:10] for v in frame[dcol]],
            "date": pd.Series(list(frame[dcol]), dtype=object).values,
            "ministry": [str(v).strip() for v in frame[m]],
            "subject": frame[subj].astype(str).values if subj is not None else [""] * n,
            "text": frame[text].astype(str).values if text is not None else [""] * n,
        }
    )


def dedupe(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate question files in order and keep the first copy of each (kind, number, date).

    The key uses the number as text and the first ten characters of the date as text,
    exactly as the published counts were built.
    """
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.concat(frames, ignore_index=True)
    return df.loc[~df[["kind", "number", "date_key"]].duplicated()].reset_index(drop=True)


def counts(df: pd.DataFrame) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """(questions per kind, per year, per ministry), in first-seen order like the original build."""
    ministries: dict[str, int] = {}
    years: dict[str, int] = {}
    kinds: dict[str, int] = {}
    for kind, d, v in zip(df["kind"], df["date"], df["ministry"], strict=True):
        k = v
        ministries[k] = ministries.get(k, 0) + 1
        dt = pd.to_datetime(d, errors="coerce")
        if pd.notna(dt):
            years[str(dt.year)] = years.get(str(dt.year), 0) + 1
        kinds[kind] = kinds.get(kind, 0) + 1
    return kinds, years, ministries


def frame_dates(df: pd.DataFrame) -> Any:
    return pd.to_datetime(df["date"], errors="coerce")
