"""The "Parliament" page: what MPs ask the government about, by topic and year.

Reads the offline topic model's outputs (``data/parliament/``) and the reviewed labels. Results
are by topic and year only: no MP names, no per-MP or per-party analysis.
"""

from __future__ import annotations

import datetime
import os
from typing import Any, cast

import pandas as pd

from mbn.analyses import parliament_topics as pt
from mbn.config import DATA_DIR
from mbn.findings import build as findings_build
from mbn.model.claims import Claim
from mbn.parsers import parliament
from mbn.publish import data_export, site
from mbn.sources.store import DatasetStore

PARL_DIR = DATA_DIR / "parliament"
MODEL_FILE = PARL_DIR / "topic_model.json"
LABELS_FILE = PARL_DIR / "topic_labels.json"
ASSIGN_FILE = PARL_DIR / "assignments.csv"
DATA_FILE = DATA_DIR / "parliament.json"
CSV_FILE = DATA_DIR / "parliament_topics_by_year.csv"
DATASETS = ("liste-des-questions-*", "liste-des-depute*")
FULL_YEAR_SHARE = 0.25
"""A year is shown if it has at least a quarter of the busiest year's questions (drops thin edge years)."""


def analyse(
    questions: pd.DataFrame, assignments: pd.DataFrame, model: dict[str, Any], labels: dict[str, Any], member_names: list[str]
) -> dict[str, Any]:
    """Topic shares by year and topic cards (pure). Fails if the labels were not reviewed for this model."""
    pt.check_labels(model, labels)
    key = ["kind", "number", "date_key"]
    df = questions[[*key, "date"]].merge(assignments[[*key, "topic"]], on=key, how="inner")
    df["year"] = pd.to_datetime(df["date"], errors="coerce").dt.year
    df = df.dropna(subset=["year"]).astype({"year": int})
    per_year = df["year"].value_counts()
    years = sorted(int(str(y)) for y, n in per_year.items() if n >= FULL_YEAR_SHARE * per_year.max())
    sh = pt.shares_by_year(df[df["year"].isin(years)])
    if len(years) >= 6:
        change = pt.change_in_share(sh, (years[0], years[2]), (years[-3], years[-1]))
    else:
        change = pd.Series(0.0, index=sh.columns)
    topics = []
    for t in sorted(model["topics"], key=lambda t: -int(t["size"])):
        tid = int(t["id"])
        lab = labels["topics"][str(tid)]
        share = [round(float(cast(float, sh.loc[y, tid])) if tid in sh.columns else 0.0, 2) for y in years]
        topics.append(
            {
                "id": tid,
                "en": lab["en"],
                "fr": lab["fr"],
                "ar": lab["ar"],
                "note": lab.get("note", ""),
                "kind": lab.get("kind", "theme"),
                "size": int((df["topic"] == tid).sum()),
                "share": share,
                "change": round(float(change.get(tid, 0.0)), 2),
                "peak_year": years[max(range(len(share)), key=lambda i: share[i])] if share else None,
                "words": [w for w in t["words"] if w not in set(labels.get("hidden_words", []))],
                "examples": [e for e in t["examples"] if not pt.contains_any(e, member_names)],
            }
        )
    themes = [t for t in topics if t["kind"] == "theme"] or topics  # mixed and procedural groups are shown, not ranked
    rising = sorted(themes, key=lambda t: -t["change"])
    summary = {
        "questions": len(df),
        "topics": len(topics),
        "first_year": years[0] if years else None,
        "last_year": years[-1] if years else None,
        "years_n": len(years),
        "top_id": themes[0]["id"] if themes else None,
        "top_share": round(100 * themes[0]["size"] / len(df), 1) if themes else 0,
        "mixed_share": round(100 * sum(t["size"] for t in topics if t["kind"] != "theme") / len(df), 1) if len(df) else 0,
        "rise_id": rising[0]["id"] if rising else None,
        "rise": rising[0]["change"] if rising else 0,
        "fall_id": rising[-1]["id"] if rising else None,
        "fall": rising[-1]["change"] if rising else 0,
    }
    return {
        "years": years,
        "topics": topics,
        "summary": summary,
        "evaluation": model.get("evaluation", {}),
        "encoder": model.get("encoder"),
        "fingerprint": model.get("fingerprint"),
    }


def _by_id(data: dict[str, Any], tid: int) -> dict[str, Any]:
    return next(t for t in data["topics"] if t["id"] == tid)


def text(data: dict[str, Any]) -> dict[str, str]:
    s = data["summary"]
    ev = data.get("evaluation", {})
    enc = ev.get("encoders", {})
    main = enc.get(data.get("encoder") or "", {})
    base: dict[str, Any] = next((v for k, v in enc.items() if k != data.get("encoder")), {})
    mc = ev.get("ministry_classifier", {})
    top, rise, fall = _by_id(data, s["top_id"]), _by_id(data, s["rise_id"]), _by_id(data, s["fall_id"])
    y0, y1 = s["first_year"], s["last_year"]
    return {
        "questions": f"{s['questions']:,}",
        "topics_n": str(s["topics"]),
        "first_year": str(y0),
        "last_year": str(y1),
        "early": f"{y0}–{y0 + 2}",
        "late": f"{y1 - 2}–{y1}",
        "top_en": top["en"],
        "top_share": f"{s['top_share']:.0f}%",
        "rise_en": rise["en"],
        "rise": f"{rise['change']:+.1f}".replace("-", "−"),
        "fall_en": fall["en"],
        "fall": f"{fall['change']:+.1f}".replace("-", "−"),
        "coh_main": f"{main.get('coherence_npmi', 0):.2f}",
        "div_main": f"{main.get('diversity', 0):.2f}",
        "coh_base": f"{base.get('coherence_npmi') or 0:.2f}",
        "div_base": f"{base.get('diversity') or 0:.2f}",
        "mixed_share": f"{s['mixed_share']:.0f}%",
        "clf_acc": f"{100 * mc.get('accuracy', 0):.0f}%",
        "clf_base": f"{100 * mc.get('majority_baseline', 0):.0f}%",
        "clf_areas": str(mc.get("areas", "")),
        "clf_test": str(mc.get("test_years", "")),
    }


def build(st: DatasetStore, updated: str | None = None) -> dict[str, Any]:
    questions = findings_build.parliament_questions(st)
    assignments = pd.read_csv(ASSIGN_FILE, dtype={"number": str, "date": str}).rename(columns={"date": "date_key"})
    names = parliament.member_names(st.files("parlement/liste-des-depute*/*.xls*"))
    out = analyse(questions, assignments, data_export.read_json(MODEL_FILE), data_export.read_json(LABELS_FILE), names)
    out["text"] = text(out)
    out["src"] = {
        "parliament": st.source("parlement/liste-des-questions-ecrites-de-la-session-d-avril").as_dict(),
        "oral": st.source("parlement/liste-des-questions-orales-de-la-session-d-octobre").as_dict(),
    }
    out["updated"] = updated or os.environ.get("DATA_DATE") or datetime.date.today().isoformat()
    rows = [
        {"topic_en": t["en"], "topic_fr": t["fr"], "topic_ar": t["ar"], "year": y, "share_pct": t["share"][j]}
        for t in out["topics"]
        for j, y in enumerate(out["years"])
    ]
    data_export.write_csv(CSV_FILE, rows, ["topic_en", "topic_fr", "topic_ar", "year", "share_pct"])
    return out


def render(data: dict[str, Any], nav: str = "") -> str:
    return site.render_page("parliament.html", data, nav)


def _s(key: str) -> Any:
    return lambda d: d["summary"][key]


CLAIMS: list[Claim] = [
    Claim("Questions with a topic (unique)", _s("questions"), 67111, 0),
    Claim("Topics", _s("topics"), 30, 0),
    Claim("Years shown", _s("years_n"), 7, 0),
    Claim("Largest theme share of all questions (%)", _s("top_share"), 10.1, 0.3),
    Claim("Mixed and procedural groups share (%)", _s("mixed_share"), 53.4, 0.5),
    Claim("Biggest rise in share, a theme (points)", _s("rise"), 0.86, 0.1),
    Claim("Biggest fall in share, a theme (points)", _s("fall"), -0.8, 0.1),
]
