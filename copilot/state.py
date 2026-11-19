"""Session state for simulated actions. Nothing here writes to the CSV or any backend."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from . import config as C

# Keys that survive "Reset Demo Data" (navigation only).
KEEP_ON_RESET = {"view"}


def init_state() -> None:
    st.session_state.setdefault("sim_resolved", {})        # ticket_id -> dict
    st.session_state.setdefault("sim_escalated", {})       # ticket_id -> dict
    st.session_state.setdefault("sim_first_response", {})  # ticket_id -> datetime
    st.session_state.setdefault("sim_tickets", [])         # list of full ticket rows
    st.session_state.setdefault("actions", [])             # action log
    st.session_state.setdefault("sandbox", None)


def log_action(asof: datetime, ticket_id: str, action: str, detail: str = "") -> None:
    st.session_state["actions"].append(
        {"demo_time": pd.Timestamp(asof).strftime("%d %b %H:%M"), "ticket": ticket_id,
         "action": action, "detail": detail, "simulated": True}
    )


def sim_counts() -> dict:
    s = st.session_state
    return {
        "resolved": len(s.get("sim_resolved", {})),
        "escalated": len(s.get("sim_escalated", {})),
        "first_response": len(s.get("sim_first_response", {})),
        "new": len(s.get("sim_tickets", [])),
    }


def has_simulated_changes() -> bool:
    return any(sim_counts().values())


def build_effective(base_raw: pd.DataFrame) -> pd.DataFrame:
    """Original export + simulated tickets + simulated actions (unenriched)."""
    df = base_raw.copy()
    df["sim_flag"] = ""
    s = st.session_state
    if s["sim_tickets"]:
        new = pd.DataFrame(s["sim_tickets"])
        for col in C.DATETIME_COLS:
            new[col] = pd.to_datetime(new[col])
        new["sim_flag"] = "Simulated new ticket"
        df = pd.concat([df, new[df.columns]], ignore_index=True)
    for tid, at in s["sim_first_response"].items():
        m = df["ticket_id"].eq(tid) & df["first_response_at"].isna()
        df.loc[m, "first_response_at"] = pd.Timestamp(at)
        df.loc[m & df["sim_flag"].eq(""), "sim_flag"] = "Simulated first response"
    for tid, e in s["sim_escalated"].items():
        m = df["ticket_id"].eq(tid)
        df.loc[m, "status"] = C.STATUS_ENG
        df.loc[m, "escalated_to_eng"] = "Yes"
        df.loc[m, "eng_handoffs"] = df.loc[m, "eng_handoffs"] + 1
        df.loc[m, "eng_ticket_id"] = e["eng_ref"]
        df.loc[m, "eng_outcome"] = None
        df.loc[m, "sim_flag"] = "Simulated escalation"
    for tid, e in s["sim_resolved"].items():
        m = df["ticket_id"].eq(tid)
        at = pd.Timestamp(e["at"])
        df.loc[m, "status"] = C.STATUS_CLOSED
        df.loc[m, "first_closed_at"] = at
        df.loc[m, "final_closed_at"] = at
        df.loc[m & df["first_response_at"].isna(), "first_response_at"] = at
        df.loc[m, "sim_flag"] = "Simulated resolution"
    return df


# ---------------------------------------------------------------- callbacks
def resolve_ticket(tid: str, note: str, verified: list[str], agent: str, asof: datetime) -> None:
    st.session_state["sim_resolved"][tid] = {"at": asof, "note": note.strip(), "verified": verified, "agent": agent}
    log_action(asof, tid, "Marked resolved", f"{len(verified)} verification checks ticked; note: {note.strip()[:80]}")


def undo_resolution(tid: str, asof: datetime) -> None:
    if st.session_state["sim_resolved"].pop(tid, None) is not None:
        log_action(asof, tid, "Undid simulated resolution")


def escalate_ticket(tid: str, summary: str, override: bool, asof: datetime) -> None:
    n = len(st.session_state["sim_escalated"]) + 1
    st.session_state["sim_escalated"][tid] = {
        "at": asof, "summary": summary, "override": override, "eng_ref": f"ENG-SIM-{n:03d}",
    }
    log_action(asof, tid, "Escalated to engineering", "gates overridden by agent" if override else "all readiness gates passed")


def log_first_response(tid: str, asof: datetime) -> None:
    st.session_state["sim_first_response"][tid] = asof
    log_action(asof, tid, "Logged first response")


def add_sim_ticket(row: dict, asof: datetime) -> str:
    sid = f"SIM-{len(st.session_state['sim_tickets']) + 1:03d}"
    full = {
        "ticket_id": sid, "created_at": pd.Timestamp(asof), "channel": row["channel"],
        "client_id": row["client_id"], "client_name": row["client_name"], "client_tier": row["client_tier"],
        "category": row["category"], "priority": row["priority"], "description": row["description"].strip(),
        "assigned_agent": row["assigned_agent"], "first_response_at": pd.NaT, "escalated_to_eng": "No",
        "eng_ticket_id": None, "eng_handoffs": 0, "eng_outcome": None, "status": C.STATUS_L1,
        "first_closed_at": pd.NaT, "final_closed_at": pd.NaT, "reopen_count": 0, "csat_score": float("nan"),
    }
    st.session_state["sim_tickets"].append(full)
    log_action(asof, sid, "Added new ticket to queue", f"{row['category']} / {row['priority']}")
    st.session_state["selected_ticket"] = sid
    st.session_state.pop("wb_pick", None)
    return sid


def reset_demo() -> None:
    """Clear every simulated action, form entry, checklist tick and cached resource."""
    for key in list(st.session_state.keys()):
        if key not in KEEP_ON_RESET:
            del st.session_state[key]
    st.cache_data.clear()
    st.cache_resource.clear()
    init_state()
    st.session_state["flash"] = "Demo data reset: all simulated actions and inputs were cleared."
