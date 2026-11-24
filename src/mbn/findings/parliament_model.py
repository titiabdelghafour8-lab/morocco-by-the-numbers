"""Offline topic model for parliamentary questions (``mbn topics``; needs the ``topics`` extra).

Embeds every question subject with an Arabic encoder, clusters with BERTopic (UMAP + HDBSCAN
+ class-based TF-IDF) under fixed seeds, and writes:

- ``data/parliament/assignments.csv``: kind, number, date, topic for every unique question
  (no names, no groups, no text);
- ``data/parliament/topic_model.json``: each topic's size, top words and five representative
  subjects (screened against the members' names), the run's settings and evaluation scores.

Topic *names* are not made here: they live in the reviewed ``topic_labels.json``.
"""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mbn.analyses import arabic
from mbn.analyses import findings as an
from mbn.analyses import parliament_topics as pt
from mbn.config import DATA_DIR
from mbn.findings import build
from mbn.parsers import parliament
from mbn.publish import data_export
from mbn.sources.store import DatasetStore

OUT_DIR = DATA_DIR / "parliament"
ENCODER = "CAMeL-Lab/bert-base-arabic-camelbert-msa"
SEED = 42
N_TOPICS = 30
MIN_CLUSTER = 120


def member_names(st: DatasetStore) -> list[str]:
    """Names of members of parliament from the portal's member lists (used only to screen outputs)."""
    return parliament.member_names(st.files("parlement/liste-des-depute*/*.xls*"))


def _seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    import torch

    torch.manual_seed(seed)


def embed(docs: list[str], model: str = ENCODER, cache: Path | None = None) -> np.ndarray:
    """Mean-pooled sentence embeddings (cached on disk between runs; the cache is not published)."""
    if cache and cache.exists():
        arr: np.ndarray = np.load(cache)
        if len(arr) == len(docs):
            return arr
    from sentence_transformers import SentenceTransformer

    enc = SentenceTransformer(model, device="cpu")
    enc.max_seq_length = 64
    out: np.ndarray = enc.encode(docs, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache, out)
    return out


def tfidf_embed(docs: list[str], dims: int = 128, seed: int = SEED) -> np.ndarray:
    """Baseline encoder: TF-IDF on words, reduced with SVD (no download)."""
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    x = TfidfVectorizer(tokenizer=arabic.tokens, lowercase=False, min_df=3, token_pattern=None).fit_transform(docs)
    out: np.ndarray = normalize(TruncatedSVD(dims, random_state=seed).fit_transform(x))
    return out


def fit_topics(docs: list[str], emb: np.ndarray, seed: int = SEED, n_topics: int = N_TOPICS) -> tuple[Any, list[int]]:
    from bertopic import BERTopic
    from hdbscan import HDBSCAN
    from sklearn.feature_extraction.text import CountVectorizer
    from umap import UMAP  # type: ignore[attr-defined,unused-ignore]

    _seed(seed)
    # c-TF-IDF runs on one joined document per topic, so a word only needs to occur in one topic
    vec = CountVectorizer(tokenizer=arabic.tokens, lowercase=False, min_df=1, token_pattern=None)
    model = BERTopic(
        umap_model=UMAP(  # type: ignore[no-untyped-call,unused-ignore]
            n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=seed, n_jobs=1
        ),
        hdbscan_model=HDBSCAN(min_cluster_size=MIN_CLUSTER, min_samples=10, prediction_data=True),
        vectorizer_model=vec,
        language="multilingual",  # the default, "english", strips every non-ASCII character
        top_n_words=10,
        calculate_probabilities=False,
    )
    model.fit(docs, emb)
    model.reduce_topics(docs, nr_topics=n_topics + 1)  # + the outlier topic
    topics = model.reduce_outliers(docs, model.topics_, strategy="embeddings", embeddings=emb)
    model.update_topics(docs, topics=topics, vectorizer_model=vec)
    return model, list(model.topics_)


def representatives(subjects: list[str], emb: np.ndarray, topics: list[int], k: int, names: list[str]) -> dict[int, list[str]]:
    """The k distinct subjects nearest each topic's centre, skipping any that names a member."""
    t = np.asarray(topics)
    out: dict[int, list[str]] = {}
    for topic in sorted(set(topics)):
        idx = np.where(t == topic)[0]
        centre = emb[idx].mean(axis=0)
        order = idx[np.argsort(-(emb[idx] @ centre))]
        picked: list[str] = []
        for i in order:
            s = " ".join(subjects[i].split())
            if s and s not in picked and len(s) <= 120 and not pt.contains_any(s, names):
                picked.append(s)
            if len(picked) == k:
                break
        out[topic] = picked
    return out


def ministry_check(df: pd.DataFrame, test_from: int = 2022) -> dict[str, Any]:
    """Can the subject alone predict the policy area of the ministry? Trained on earlier years, tested on later ones."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    area = []
    for m in df["ministry"]:
        themes, _ = an.parliament_themes({m: 1})
        area.append(themes[0][0] if themes else None)
    d = df.assign(area=pd.Series(area, index=df.index, dtype=object)).dropna(subset=["area"])
    train, test = d[d["year"] < test_from], d[d["year"] >= test_from]
    vec = TfidfVectorizer(tokenizer=arabic.tokens, lowercase=False, min_df=3, token_pattern=None)
    clf = LogisticRegression(max_iter=2000).fit(vec.fit_transform(train["doc"]), train["area"])
    acc = float((clf.predict(vec.transform(test["doc"])) == test["area"]).mean())
    base = float((test["area"] == train["area"].mode()[0]).mean())
    return {
        "accuracy": round(acc, 3),
        "majority_baseline": round(base, 3),
        "train_years": f"to {test_from - 1}",
        "test_years": f"{test_from} on",
        "test_n": len(test),
        "areas": int(d["area"].nunique()),
    }


def run(st: DatasetStore, out_dir: Path = OUT_DIR, cache: Path | None = None) -> dict[str, Any]:
    q = build.parliament_questions(st)
    q = q[q["subject"].str.strip().astype(bool)].reset_index(drop=True)
    q["year"] = parliament.frame_dates(q).dt.year
    q["doc"] = [arabic.normalise(s) for s in q["subject"]]
    q = q[q["doc"].map(lambda s: len(arabic.tokens(s)) > 0)].reset_index(drop=True)
    docs = q["doc"].tolist()
    names = member_names(st)

    emb = embed(docs, cache=cache)
    model, topics = fit_topics(docs, emb)
    token_docs = [arabic.tokens(d) for d in docs]

    def words_of(m: Any) -> dict[int, list[str]]:
        return {int(k): [w for w, _ in v][:10] for k, v in m.get_topics().items() if int(k) != -1}

    words = words_of(model)
    reps = representatives(q["subject"].tolist(), emb, topics, 5, names)
    counts = pd.Series(topics).value_counts()
    topic_rows = [{"id": int(t), "size": int(counts[t]), "words": words[t], "examples": reps[t]} for t in sorted(words)]

    try:
        base_model, _ = fit_topics(docs, tfidf_embed(docs))
        base_words = list(words_of(base_model).values())
        base_eval: dict[str, Any] = {
            "coherence_npmi": round(pt.npmi_coherence(base_words, token_docs), 3),
            "diversity": round(pt.diversity(base_words), 3),
            "topics": len(base_words),
        }
    except ValueError as e:  # too few clusters to describe
        base_eval = {"coherence_npmi": None, "diversity": None, "topics": 0, "failed": str(e)}
    evaluation = {
        "encoders": {
            ENCODER: {
                "coherence_npmi": round(pt.npmi_coherence(list(words.values()), token_docs), 3),
                "diversity": round(pt.diversity(list(words.values())), 3),
                "topics": len(words),
            },
            "tf-idf + SVD (baseline)": base_eval,
        },
        "ministry_classifier": ministry_check(q),
        "not_benchmarked": "AraBERT and a multilingual sentence model were not downloaded (download budget: one model).",
    }
    result = {
        "encoder": ENCODER,
        "seed": SEED,
        "min_cluster_size": MIN_CLUSTER,
        "n_topics": len(topic_rows),
        "documents": len(docs),
        "fingerprint": pt.fingerprint(topic_rows),
        "topics": topic_rows,
        "evaluation": evaluation,
    }
    data_export.write_json(out_dir / "topic_model.json", result)
    data_export.write_csv(
        out_dir / "assignments.csv",
        [
            {"kind": k, "number": n, "date": d, "topic": int(t)}
            for k, n, d, t in zip(q["kind"], q["number"], q["date_key"], topics, strict=True)
        ],
        ["kind", "number", "date", "topic"],
    )
    return result
