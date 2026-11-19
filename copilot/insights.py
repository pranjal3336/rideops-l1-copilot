"""Statistics computed strictly from the ticket CSV (no invented numbers)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def closed_history(base: pd.DataFrame) -> pd.DataFrame:
    """Closed tickets of the original export (final outcomes only)."""
    return base[~base["is_open"]]


def baseline_avoidable_rate(hist: pd.DataFrame) -> float:
    esc = hist[hist["escalated"] & hist["eng_outcome"].notna()]
    return float(esc["avoidable"].mean()) if len(esc) else float("nan")


def scope_stats(hist: pd.DataFrame, category: str, tmpl: str | None = None, min_esc: int = 8) -> dict:
    """Stats for an issue type (if enough escalations exist) or else its category."""
    sub = hist[hist["category"] == category]
    scope, label = "category", category
    if tmpl:
        same = hist[hist["tmpl"] == tmpl]
        if int(same["escalated"].sum()) >= min_esc:
            sub, scope, label = same, "issue type", tmpl
    esc = sub[sub["escalated"] & sub["eng_outcome"].notna()]
    non_esc = sub[~sub["escalated"]]
    n, ne = len(sub), len(esc)
    outcomes = esc["eng_outcome"].value_counts()
    return {
        "scope": scope,
        "label": label,
        "n_tickets": n,
        "n_escalated": ne,
        "esc_rate": ne / n if n else float("nan"),
        "outcomes": outcomes,
        "fixed_rate": float(outcomes.get(C.OUTCOME_FIXED, 0) / ne) if ne else float("nan"),
        "avoidable_rate": float(esc["avoidable"].mean()) if ne else float("nan"),
        "mean_handoffs": float(esc["eng_handoffs"].mean()) if ne else float("nan"),
        "median_res_h_l1": float(non_esc["resolution_h"].median()) if len(non_esc) else float("nan"),
        "median_res_h_eng": float(esc["resolution_h"].median()) if ne else float("nan"),
        "reopen_rate": float((sub["reopen_count"] > 0).mean()) if n else float("nan"),
        "csat_mean": float(sub["csat_score"].mean()) if sub["csat_score"].notna().any() else float("nan"),
        "csat_n": int(sub["csat_score"].notna().sum()),
    }


def escalation_risk(stats: dict, baseline: float) -> dict:
    """Level + reasons for the 'avoidable escalation' warning."""
    ne, rate = stats["n_escalated"], stats["avoidable_rate"]
    outcomes = stats["outcomes"]
    non_fixed = outcomes.drop(labels=[C.OUTCOME_FIXED], errors="ignore")
    reasons = []
    for outcome, cnt in non_fixed.head(2).items():
        pct = cnt / ne if ne else 0
        reasons.append((outcome, int(cnt), pct, C.OUTCOME_GUIDANCE.get(outcome, "")))
    if ne < 5 or np.isnan(rate):
        level = "unknown"
    elif rate >= 0.65:
        level = "high"
    elif rate >= 0.50:
        level = "elevated"
    else:
        level = "lower"
    return {"level": level, "rate": rate, "baseline": baseline, "n_escalated": ne, "reasons": reasons}


def known_open_eng(eff: pd.DataFrame, category: str, tmpl: str | None, exclude_id: str | None = None) -> pd.DataFrame:
    """Open tickets currently with engineering in the same category (same issue type flagged)."""
    m = eff["status"].eq(C.STATUS_ENG) & eff["category"].eq(category)
    if exclude_id:
        m &= eff["ticket_id"].ne(exclude_id)
    out = eff.loc[m, ["ticket_id", "eng_ticket_id", "client_name", "description", "created_at", "eng_handoffs", "tmpl"]].copy()
    out["same_issue_type"] = out["tmpl"].eq(tmpl) if tmpl else False
    return out.sort_values(["same_issue_type", "created_at"], ascending=[False, True]).drop(columns="tmpl")


def client_stats(eff: pd.DataFrame, client_id: str, asof: pd.Timestamp) -> dict:
    c = eff[eff["client_id"] == client_id]
    asof = pd.Timestamp(asof)
    per_client_avg = len(eff) / max(eff["client_id"].nunique(), 1)
    recent = c[c["created_at"] >= asof - pd.Timedelta(days=30)]
    esc = c[c["escalated"]]
    closed = c[~c["is_open"]]
    return {
        "total": len(c),
        "open": int(c["is_open"].sum()),
        "avg_per_client": per_client_avg,
        "last_30d": len(recent),
        "p1_p2": int(c["priority"].isin(["P1", "P2"]).sum()),
        "esc_rate": len(esc) / len(c) if len(c) else float("nan"),
        "reopen_rate": float((closed["reopen_count"] > 0).mean()) if len(closed) else float("nan"),
        "csat_mean": float(c["csat_score"].mean()) if c["csat_score"].notna().any() else float("nan"),
        "csat_n": int(c["csat_score"].notna().sum()),
        "by_category": c["category"].value_counts(),
        "recent_by_category": recent["category"].value_counts(),
        "frame": c.sort_values("created_at", ascending=False),
    }


def agent_load(eff: pd.DataFrame) -> pd.Series:
    """Open ticket count per L1 agent (all agents present in the data, zeros included)."""
    agents = sorted(eff["assigned_agent"].dropna().unique())
    counts = eff[eff["is_open"]]["assigned_agent"].value_counts()
    return pd.Series({a: int(counts.get(a, 0)) for a in agents})


def fmt_hours(h: float) -> str:
    if h is None or (isinstance(h, float) and np.isnan(h)):
        return "—"
    return f"{h:.1f} h" if h < 48 else f"{h / 24:.1f} d"


def fmt_pct(x: float) -> str:
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:.0f}%"


def fmt_dt(x) -> str:
    return "—" if pd.isna(x) else pd.Timestamp(x).strftime("%d %b %Y %H:%M")
