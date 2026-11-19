"""Transparent, additive urgency score for open tickets (0-100)."""
from __future__ import annotations

import pandas as pd

from . import config as C

COMPONENTS = [
    ("pts_priority", "Priority"),
    ("pts_age", "Age"),
    ("pts_no_resp", "No first response"),
    ("pts_handoffs", "Eng ping-pong"),
    ("pts_reopen", "Reopened"),
    ("pts_awaiting", "Back with L1"),
    ("pts_tier", "Client tier"),
]


def score(df: pd.DataFrame, aging_hours: float) -> pd.DataFrame:
    """Return a copy of `df` with pts_* columns, `urgency` (0-100) and `why`."""
    d = df.copy()
    if d.empty:
        for col, _ in COMPONENTS:
            d[col] = pd.Series(dtype=float)
        d["urgency"] = pd.Series(dtype=float)
        d["why"] = pd.Series(dtype=object)
        return d
    d["pts_priority"] = d["priority"].map(C.W_PRIORITY).fillna(0).astype(float)
    d["pts_age"] = (C.W_AGE_MAX * (d["age_h"] / (2 * max(aging_hours, 1))).clip(0, 1)).round(1)
    d["pts_no_resp"] = d["missing_first_response"].astype(float) * C.W_NO_FIRST_RESPONSE
    d["pts_handoffs"] = ((d["eng_handoffs"] - 1).clip(lower=0) * C.W_HANDOFF_EACH).clip(upper=C.W_HANDOFF_CAP).astype(float)
    d["pts_reopen"] = (d["reopen_count"] * C.W_REOPEN_EACH).clip(upper=C.W_REOPEN_CAP).astype(float)
    d["pts_awaiting"] = d["awaiting_l1"].astype(float) * C.W_AWAITING_L1
    d["pts_tier"] = d["client_tier"].map(C.W_TIER).fillna(0).astype(float)
    total = d[[c for c, _ in COMPONENTS]].sum(axis=1)
    d["urgency"] = total.clip(upper=100).round(1)

    def _why(row) -> str:
        parts = [f"{label} {row[col]:g}" for col, label in COMPONENTS if row[col] > 0]
        return " + ".join(parts)

    d["why"] = d.apply(_why, axis=1)
    return d


def rules_table(aging_hours: float) -> pd.DataFrame:
    """Human-readable rule list for the UI."""
    return pd.DataFrame(
        [
            ("Priority", "P1 40 / P2 28 / P3 16 / P4 6"),
            ("Age", f"0-{C.W_AGE_MAX} pts, linear until age = 2 x aging threshold ({2 * aging_hours:g} h)"),
            ("No first response", f"+{C.W_NO_FIRST_RESPONSE} if first_response_at is blank"),
            ("Eng ping-pong", f"+{C.W_HANDOFF_EACH} per eng_handoffs beyond the first (max {C.W_HANDOFF_CAP})"),
            ("Reopened", f"+{C.W_REOPEN_EACH} per reopen_count (max {C.W_REOPEN_CAP})"),
            ("Back with L1", f"+{C.W_AWAITING_L1} if status is '{C.STATUS_L1}' after >=1 engineering handoff"),
            ("Client tier", "Enterprise 5 / Mid-market 2 / SMB 0"),
            ("Total", "Sum of the above, capped at 100"),
        ],
        columns=["Component", "Rule"],
    )
