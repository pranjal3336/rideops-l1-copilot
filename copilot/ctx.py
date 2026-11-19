"""Per-run context shared by all views."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .similarity import TicketIndex


@dataclass
class Ctx:
    base: pd.DataFrame      # original export, enriched (as of `asof`)
    hist: pd.DataFrame      # closed tickets of the original export
    eff: pd.DataFrame       # original + simulated changes, enriched
    asof: pd.Timestamp
    aging_h: float
    index: TicketIndex
    clients: pd.DataFrame   # unique client_id / client_name / client_tier
    baseline_avoidable: float
