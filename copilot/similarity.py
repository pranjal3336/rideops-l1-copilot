"""TF-IDF similarity search and category suggestion over historical descriptions."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline

CATEGORY_BOOST = 0.10
CLIENT_BOOST = 0.03
LOW_CONFIDENCE = 0.45
LOW_COVERAGE = 0.5


def _norm(text: str) -> str:
    return re.sub(r"\d+", "#", str(text).lower())


class TicketIndex:
    """Fits on the original export only; simulated tickets never enter the index."""

    def __init__(self, base: pd.DataFrame):
        self.base = base.reset_index(drop=True)
        texts = [_norm(t) for t in self.base["description"]]
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self.X = self.vec.fit_transform(texts)
        self.vocab = set(self.vec.vocabulary_)
        self.clf = LogisticRegression(C=20, max_iter=2000)
        self.clf.fit(self.X, self.base["category"])
        self.cv_accuracy, self.cv_folds = self._cross_validate(texts)

    def _cross_validate(self, texts) -> tuple[float, int]:
        y = self.base["category"]
        folds = int(min(5, y.value_counts().min()))
        if folds < 2:
            return float("nan"), 0
        pipe = make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
            LogisticRegression(C=20, max_iter=2000),
        )
        pred = cross_val_predict(pipe, texts, y, cv=StratifiedKFold(folds, shuffle=True, random_state=42))
        return float((pred == y.to_numpy()).mean()), folds

    # ------------------------------------------------------------------ classify
    def coverage(self, text: str) -> float:
        tokens = re.findall(r"[a-z0-9#]{2,}", _norm(text))
        tokens = [t for t in tokens if not t.isdigit()]
        if not tokens:
            return 0.0
        return sum(t in self.vocab for t in tokens) / len(tokens)

    def suggest_category(self, text: str, top: int = 3) -> dict:
        q = self.vec.transform([_norm(text)])
        proba = self.clf.predict_proba(q)[0]
        order = np.argsort(proba)[::-1][:top]
        ranked = [(self.clf.classes_[i], float(proba[i])) for i in order]
        cov = self.coverage(text)
        low = ranked[0][1] < LOW_CONFIDENCE or cov < LOW_COVERAGE
        return {"ranked": ranked, "coverage": cov, "low_confidence": low}

    # ------------------------------------------------------------------- similar
    def similar(self, text: str, category: str | None = None, client_id: str | None = None,
                exclude_id: str | None = None, k: int = 8, closed_only: bool = False) -> pd.DataFrame:
        q = self.vec.transform([_norm(text)])
        sim = (self.X @ q.T).toarray().ravel()
        score = sim.copy()
        b = self.base
        if category:
            score += CATEGORY_BOOST * (b["category"].to_numpy() == category)
        if client_id:
            score += CLIENT_BOOST * (b["client_id"].to_numpy() == client_id)
        mask = np.ones(len(b), dtype=bool)
        if exclude_id:
            mask &= b["ticket_id"].to_numpy() != exclude_id
        if closed_only:
            mask &= ~b["status"].str.startswith("Open").to_numpy()
        mask &= sim > 0
        out = b[mask].copy()
        out["text_sim"] = sim[mask]
        out["match"] = np.clip(score[mask], 0, 1)
        # Ties are common (templated descriptions): break by most recent first.
        out = out.sort_values(["match", "created_at"], ascending=[False, False]).head(k)
        return out
