"""Loading, validating and enriching the RideOps ticket export."""
from __future__ import annotations

import pandas as pd

from .config import (
    DATETIME_COLS, DICT_FILE, OUTCOME_FIXED, REQUIRED_COLUMNS, STATUS_ENG,
    STATUS_L1,
)


class DataError(Exception):
    """Raised for problems the user can act on (missing file, wrong schema...)."""


def read_tickets(source) -> tuple[pd.DataFrame, list[str]]:
    """Read + validate a tickets CSV. `source` is a path or file-like object.

    Returns (dataframe with exactly REQUIRED_COLUMNS, list of warnings).
    """
    warnings: list[str] = []
    try:
        raw = pd.read_csv(source)
    except FileNotFoundError as exc:
        raise DataError(f"Tickets file not found: {source}") from exc
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise DataError(f"Could not parse the tickets CSV: {exc}") from exc

    raw.columns = [str(c).strip() for c in raw.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise DataError("Tickets CSV is missing required columns: " + ", ".join(missing))
    extra = [c for c in raw.columns if c not in REQUIRED_COLUMNS]
    if extra:
        warnings.append("Ignoring extra columns: " + ", ".join(extra))

    df = raw[REQUIRED_COLUMNS].copy()
    for col in DATETIME_COLS:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ["ticket_id", "channel", "client_id", "client_name", "client_tier",
                "category", "priority", "description", "assigned_agent",
                "escalated_to_eng", "eng_ticket_id", "eng_outcome", "status"]:
        df[col] = df[col].astype("object").where(df[col].isna(), df[col].astype(str).str.strip())
    for col in ["eng_handoffs", "reopen_count"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["csat_score"] = pd.to_numeric(df["csat_score"], errors="coerce")

    bad_created = int(df["created_at"].isna().sum())
    if bad_created:
        warnings.append(f"Dropped {bad_created} row(s) with an unparseable created_at.")
        df = df[df["created_at"].notna()]
    dupes = int(df["ticket_id"].duplicated().sum())
    if dupes:
        warnings.append(f"Dropped {dupes} duplicate ticket_id row(s).")
        df = df.drop_duplicates("ticket_id", keep="first")
    if df.empty:
        raise DataError("The tickets file contains no usable rows.")
    df["status"] = df["status"].fillna("Closed")
    df["escalated_to_eng"] = df["escalated_to_eng"].fillna("No")
    return df.reset_index(drop=True), warnings


def read_dictionary() -> pd.DataFrame:
    """Data dictionary for display. Returns an empty frame if unreadable."""
    try:
        return pd.read_csv(DICT_FILE)
    except Exception:  # noqa: BLE001 - dictionary is informational only
        return pd.DataFrame(columns=["column", "description"])


def normalise_text(text: str) -> str:
    """Lower-case and collapse digits so '12 employees' and '30 employees' match."""
    return pd.Series([str(text)]).str.lower().str.replace(r"\d+", "#", regex=True).iloc[0]


def enrich(df: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """Add derived columns. Everything is computed from the CSV columns only."""
    asof = pd.Timestamp(asof)
    d = df.copy()
    d["is_open"] = d["status"].str.startswith("Open")
    d["escalated"] = d["escalated_to_eng"].eq("Yes")
    d["tmpl"] = d["description"].str.lower().str.replace(r"\d+", "#", regex=True)
    end = d["final_closed_at"].where(~d["is_open"], asof)
    d["age_h"] = ((end - d["created_at"]).dt.total_seconds() / 3600).clip(lower=0)
    d["resolution_h"] = ((d["final_closed_at"] - d["created_at"]).dt.total_seconds() / 3600).where(~d["is_open"])
    d["first_resp_h"] = (d["first_response_at"] - d["created_at"]).dt.total_seconds() / 3600
    d["missing_first_response"] = d["is_open"] & d["first_response_at"].isna()
    d["eng_pending"] = d["status"].eq(STATUS_ENG)
    # Back with L1 after at least one engineering handoff (engineering answered, L1 owes next step)
    d["awaiting_l1"] = d["status"].eq(STATUS_L1) & d["eng_handoffs"].gt(0)
    d["avoidable"] = d["escalated"] & d["eng_outcome"].notna() & d["eng_outcome"].ne(OUTCOME_FIXED)
    return d
