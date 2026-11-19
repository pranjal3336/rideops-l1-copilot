"""RideOps L1 Support Copilot - Streamlit MVP.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import io
from datetime import datetime, time

import pandas as pd
import streamlit as st

from copilot import config as C
from copilot import data, insights, state
from copilot.ctx import Ctx
from copilot.similarity import TicketIndex
from copilot.views import sandbox, triage, workbench

st.set_page_config(page_title="RideOps L1 Support Copilot", page_icon="🎧", layout="wide")


@st.cache_data(show_spinner="Loading tickets...")
def load_raw(file_bytes: bytes | None):
    source = io.BytesIO(file_bytes) if file_bytes else C.TICKETS_FILE
    return data.read_tickets(source)


@st.cache_resource(show_spinner="Building similarity index...")
def build_index(_base: pd.DataFrame, signature: str) -> TicketIndex:
    return TicketIndex(_base)


def sidebar_controls() -> tuple[bytes | None, datetime, float]:
    sb = st.sidebar
    sb.title("🎧 RideOps L1 Copilot")
    sb.caption("Case-study MVP for L1 support agents. All data comes from the supplied ticket export.")
    if "view" not in st.session_state:
        st.session_state["view"] = C.VIEWS[0]
    sb.radio("View", C.VIEWS, key="view")

    with sb.expander("Demo clock & thresholds", expanded=False):
        d = st.date_input("'Now' date (IST)", value=C.DATA_PULL_ASOF.date(), key="asof_date")
        t = st.time_input("'Now' time", value=time(C.DATA_PULL_ASOF.hour, C.DATA_PULL_ASOF.minute), key="asof_time")
        aging = st.number_input("Aging threshold (hours)", min_value=1, max_value=720, value=C.DEFAULT_AGING_HOURS,
                                step=6, key="aging_h",
                                help="Assumption: the export has no SLA field, so 'aging' is a configurable age cut-off.")
        st.caption("Default is the data pull time (30 Sep 2026). Ticket ages are measured against this clock.")
    asof = datetime.combine(d, t)

    uploaded = None
    with sb.expander("Data source", expanded=False):
        st.caption(f"Default: `{C.TICKETS_FILE.name}`")
        up = st.file_uploader("Load a different tickets CSV (same 20 columns)", type=["csv"], key="upload")
        if up is not None:
            uploaded = up.getvalue()
        dic = data.read_dictionary()
        if not dic.empty:
            st.dataframe(dic, hide_index=True, height=260)

    sb.divider()
    sb.button("Reset Demo Data", on_click=state.reset_demo, type="secondary", key="reset_demo",
              help="Clears simulated resolutions, escalations, new tickets, checklist ticks, filters and uploads.")
    counts = state.sim_counts()
    if any(counts.values()):
        sb.caption(f":orange-badge[SIMULATED] {counts['new']} new · {counts['escalated']} escalated · "
                   f"{counts['resolved']} resolved · {counts['first_response']} first responses")
    with sb.expander(f"Simulated actions log ({len(st.session_state['actions'])})"):
        if st.session_state["actions"]:
            log = pd.DataFrame(st.session_state["actions"])
            st.dataframe(log.iloc[::-1], hide_index=True)
            st.download_button("Download log (CSV)", log.to_csv(index=False).encode("utf-8"),
                               "simulated_actions.csv", "text/csv", key="dl_log")
        else:
            st.caption("No simulated actions yet.")
    return uploaded, asof, float(aging)


def main() -> None:
    state.init_state()
    uploaded, asof, aging_h = sidebar_controls()

    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash)

    # ------------------------------------------------------------ load data
    base_raw, warnings = None, []
    try:
        base_raw, warnings = load_raw(uploaded)
    except data.DataError as exc:
        if uploaded is not None:
            st.sidebar.error(f"Uploaded file rejected: {exc}. Falling back to the bundled export.")
            try:
                base_raw, warnings = load_raw(None)
            except data.DataError as exc2:
                st.error(f"Could not load the bundled tickets file either: {exc2}")
                st.stop()
        else:
            st.error(f"Could not load tickets: {exc}")
            st.info("Place `rideops_support_tickets.csv` in the `data/` folder or upload it from the sidebar (Data source).")
            st.stop()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Unexpected error while loading data: {exc}")
        st.stop()
    for w in warnings:
        st.sidebar.warning(w)

    try:
        asof_ts = pd.Timestamp(asof)
        base = data.enrich(base_raw, asof_ts)
        eff = data.enrich(state.build_effective(base_raw), asof_ts)
        sig = f"{len(base_raw)}|{base_raw['ticket_id'].iloc[0]}|{base_raw['ticket_id'].iloc[-1]}|{base_raw['created_at'].max()}"
        index = build_index(base, sig)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not prepare the data: {exc}")
        st.stop()

    hist = insights.closed_history(base)
    ctx = Ctx(
        base=base, hist=hist, eff=eff, asof=asof_ts, aging_h=aging_h, index=index,
        clients=base_raw.drop_duplicates("client_id")[["client_id", "client_name", "client_tier"]],
        baseline_avoidable=insights.baseline_avoidable_rate(hist),
    )

    st.title("RideOps L1 Support Copilot")
    st.caption(
        f"{len(base_raw):,} tickets · {base_raw['created_at'].min():%d %b} to {base_raw['created_at'].max():%d %b %Y} · "
        f"{base_raw['client_id'].nunique()} clients · {base_raw['assigned_agent'].nunique()} L1 agents · "
        "buttons labelled SIMULATED change only this session."
    )
    if asof_ts < base_raw["created_at"].max():
        st.warning("The demo clock is earlier than the newest ticket; those tickets are shown with age 0.")

    view = st.session_state["view"]
    try:
        if view == "Triage Queue":
            triage.render(ctx)
        elif view == "Ticket Workbench":
            workbench.render(ctx)
        else:
            sandbox.render(ctx)
    except Exception as exc:  # noqa: BLE001 - show a friendly error instead of a stack trace
        st.error(f"Something went wrong in this view: {exc}")
        st.caption("Use Reset Demo Data in the sidebar to restore a clean state.")
        with st.expander("Technical details"):
            st.exception(exc)

    with st.expander("Data, definitions and assumptions"):
        st.markdown(
            "- **Source**: `rideops_support_tickets.csv` (1,444 tickets, 2 Jul - 30 Sep 2026) and its data dictionary. "
            "No records, statistics or outcomes are invented.\n"
            "- **Open** = status starts with 'Open'. **Engineering follow-up** = 'Open - with Engineering'.\n"
            "- **Avoidable escalation** = a closed escalation whose `eng_outcome` is not 'Fixed' (assumption).\n"
            "- **Aging** uses an adjustable hour threshold because the export has no SLA field (assumption).\n"
            "- **Checklists** are an authored playbook, not mined from data (the export has no resolution notes).\n"
            "- **Simulated** actions live only in this browser session and never modify the CSV; historical statistics "
            "always use the original closed tickets.\n"
            "- Some open tickets carry an `eng_outcome` even though the status says 'with Engineering'; the app shows it as "
            "the latest verdict recorded."
        )


main()
