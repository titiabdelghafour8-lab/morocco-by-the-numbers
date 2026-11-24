"""Topics of parliamentary questions: shares by year, change, label checks, evaluation scores, name screening.

Pure functions. The topic model itself runs offline (``mbn topics``); this module only reads
its outputs.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
from collections import Counter
from typing import Any

import pandas as pd


class LabelsOutOfDate(Exception):
    """The topic model changed since its labels were reviewed."""


def fingerprint(topics: list[dict[str, Any]]) -> str:
    """Stable hash of each topic's id, size and top words (independent of key order)."""
    canon = sorted((int(t["id"]), int(t["size"]), tuple(t["words"])) for t in topics)
    return hashlib.sha256(json.dumps(canon, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def check_labels(model: dict[str, Any], labels: dict[str, Any]) -> None:
    """Fail unless the labels file was reviewed for exactly this model and names every topic."""
    if labels.get("fingerprint") != fingerprint(model["topics"]):
        raise LabelsOutOfDate(
            "the topic model changed since its labels were reviewed: read the new topics, update "
            "data/parliament/topic_labels.json and its fingerprint, then review it in a pull request"
        )
    missing = [t["id"] for t in model["topics"] if str(t["id"]) not in labels["topics"]]
    if missing:
        raise LabelsOutOfDate(f"topics without a reviewed label: {missing}; review the labels file")


def shares_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """Percentage of each year's questions in each topic (rows: years, columns: topics)."""
    counts = df.groupby(["year", "topic"]).size().unstack(fill_value=0)
    return counts.div(counts.sum(axis=1), axis=0) * 100


def change_in_share(shares: pd.DataFrame, first: tuple[int, int], last: tuple[int, int]) -> pd.Series:
    """Average share in the ``last`` years minus the average in the ``first`` years, in points."""
    a = shares.loc[first[0] : first[1]].mean()
    b = shares.loc[last[0] : last[1]].mean()
    return (b - a).round(6)


def _norm_name(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().casefold()


def contains_any(text: str, names: list[str]) -> bool:
    """True if any (non-empty) name appears in the text, ignoring case and spacing."""
    t = _norm_name(text)
    return any(n and n in t for n in (_norm_name(x) for x in names))


def npmi_coherence(topic_words: list[list[str]], docs: list[list[str]]) -> float:
    """Average normalised pointwise mutual information of word pairs within topics (document co-occurrence)."""
    n = len(docs)
    sets = [set(d) for d in docs]
    df: Counter[str] = Counter(w for s in sets for w in s)
    scores = []
    for words in topic_words:
        for a, b in itertools.combinations(words, 2):
            pab = sum(1 for s in sets if a in s and b in s) / n
            if pab == 0:
                scores.append(-1.0)
                continue
            pa, pb = df[a] / n, df[b] / n
            pmi = math.log(pab / (pa * pb))
            scores.append(pmi / -math.log(pab) if pab < 1 else 1.0)
    return sum(scores) / len(scores) if scores else 0.0


def diversity(topic_words: list[list[str]]) -> float:
    """Share of distinct words among all topics' top words (1 = no word shared between topics)."""
    allw = [w for ws in topic_words for w in ws]
    return len(set(allw)) / len(allw) if allw else 0.0
