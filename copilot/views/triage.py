"""View 1: Triage queue."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import config as C
from .. import scoring, state
from ..ctx import Ctx
from ..ui import goto_ticket


def _filter(df: pd.DataFrame, col: str, selected: list[str]) -> pd.DataFrame:
    return df[df[col].isin(selected)] if selected else df


def render(ctx: Ctx) -> None:
    st.subheader("Triage queue")
    st.caption(
        f"Open tickets only, ranked by a transparent urgency score. Data as of "
        f"{ctx.asof:%d %b %Y %H:%M} IST (data pull date); aging threshold {ctx.aging_h:g} h."
    )

    open_df = ctx.eff[ctx.eff["is_open"]]
    orig_open = int(ctx.base["is_open"].sum())
    scored = scoring.score(open_df, ctx.aging_h)
    scored["aging"] = scored["age_h"] > ctx.aging_h

    # ------------------------------------------------------------------ KPIs
    k1, k2, k3, k4 = st.columns(4)
    delta = len(open_df) - orig_open
    k1.metric(
        "Open tickets", len(open_df),
        delta=f"{delta:+d} vs data pull (simulated)" if delta else None, delta_color="inverse", border=True,
        help="Tickets whose status starts with 'Open' (L1 + Engineering).",
    )
    k2.metric(
        f"Aging > {ctx.aging_h:g} h", int(scored["aging"].sum()), border=True,
        help="Open tickets older than the aging threshold set in the sidebar (assumption; the data has no SLA field).",
    )
    k3.metric(
        "Missing first response", int(scored["missing_first_response"].sum()), border=True,
        help="Open tickets where first_response_at is blank.",
    )
    k4.metric(
        "Engineering follow-ups", int(scored["eng_pending"].sum()), border=True,
        help="Open tickets with status 'Open - with Engineering'. L1 still owns client updates and chasing.",
    )
    awaiting = int(scored["awaiting_l1"].sum())
    st.caption(
        f"{awaiting} open ticket(s) are back with L1 after at least one engineering handoff and need an L1 action. "
        f"{len(scored) - int(scored['aging'].sum())} are within the aging threshold."
    )

    if scored.empty:
        st.success("No open tickets. Use Reset Demo Data in the sidebar to restore the original queue.")
        return

    # --------------------------------------------------------------- filters
    st.markdown("**Filters**")
    f1, f2, f3, f4, f5 = st.columns(5)
    prio = f1.multiselect("Priority", C.PRIORITIES, placeholder="All", key="f_prio")
    tier = f2.multiselect("Client tier", C.TIERS, placeholder="All", key="f_tier")
    cats = f3.multiselect("Category", sorted(scored["category"].unique()), placeholder="All", key="f_cat")
    agents = f4.multiselect("Assigned agent", sorted(scored["assigned_agent"].unique()), placeholder="All", key="f_agent")
    where = f5.multiselect("Status", [C.STATUS_L1, C.STATUS_ENG], placeholder="All", key="f_status")

    t1, t2, t3, t4, t5 = st.columns([1, 1.4, 1.4, 1.6, 2])
    only_aging = t1.toggle("Aging only", key="f_aging")
    only_noresp = t2.toggle("No first response", key="f_noresp")
    only_back = t3.toggle("Back with L1", key="f_back", help="Returned by engineering, waiting on L1.")
    search = t4.text_input("Search", placeholder="ticket, client, text", key="f_search", label_visibility="collapsed")
    sort_by = t5.selectbox(
        "Sort", ["Urgency score (high to low)", "Oldest first", "Priority then age"],
        key="f_sort", label_visibility="collapsed",
    )

    view = scored
    for col, sel in (("priority", prio), ("client_tier", tier), ("category", cats),
                     ("assigned_agent", agents), ("status", where)):
        view = _filter(view, col, sel)
    if only_aging:
        view = view[view["aging"]]
    if only_noresp:
        view = view[view["missing_first_response"]]
    if only_back:
        view = view[view["awaiting_l1"]]
    if search.strip():
        q = search.strip().lower()
        hay = (view["ticket_id"] + " " + view["client_name"] + " " + view["description"] + " " + view["category"]).str.lower()
        view = view[hay.str.contains(q, regex=False)]

    if sort_by == "Oldest first":
        view = view.sort_values("age_h", ascending=False)
    elif sort_by == "Priority then age":
        view = view.sort_values(["priority", "age_h"], ascending=[True, False])
    else:
        view = view.sort_values(["urgency", "age_h"], ascending=[False, False])
    view = view.reset_index(drop=True)

    st.markdown(f"**Showing {len(view)} of {len(scored)} open tickets**")
    if view.empty:
        st.info("No open tickets match these filters. Clear a filter to see more.")
        return

    show = pd.DataFrame({
        "#": range(1, len(view) + 1),
        "Ticket": view["ticket_id"],
        "Urgency": view["urgency"],
        "Priority": view["priority"],
        "Tier": view["client_tier"],
        "Client": view["client_name"],
        "Category": view["category"],
        "Agent": view["assigned_agent"],
        "Status": view["status"],
        "Age (h)": view["age_h"].round(1),
        "1st response": view["missing_first_response"].map({True: "Missing", False: "Done"}),
        "Eng handoffs": view["eng_handoffs"],
        "Reopens": view["reopen_count"],
        "Score breakdown": view["why"],
        "Simulated": view["sim_flag"],
    })
    event = st.dataframe(
        show, hide_index=True, on_select="rerun", selection_mode="single-row", key="queue_table",
        column_config={
            "Urgency": st.column_config.ProgressColumn("Urgency", min_value=0, max_value=100, format="%.0f"),
            "Age (h)": st.column_config.NumberColumn("Age (h)", format="%.1f"),
        },
        height=min(560, 38 + 35 * len(show)),
    )
    rows = event.selection.rows if event and event.selection else []
    chosen = view.loc[rows[0], "ticket_id"] if rows and rows[0] < len(view) else None

    b1, b2, b3 = st.columns([2, 2, 3])
    b1.button(
        f"Open {chosen} in Workbench" if chosen else "Select a row to open it",
        type="primary", disabled=chosen is None, on_click=goto_ticket, args=(chosen,), key="open_wb",
    )
    b2.download_button(
        "Download filtered queue (CSV)",
        data=show.drop(columns=["#"]).to_csv(index=False).encode("utf-8"),
        file_name="rideops_triage_queue.csv", mime="text/csv", key="dl_queue",
    )
    if state.has_simulated_changes():
        b3.caption(":orange-badge[SIMULATED] Queue includes simulated actions from this session.")

    with st.expander("How the urgency score works (every rule, no hidden weights)"):
        st.dataframe(scoring.rules_table(ctx.aging_h), hide_index=True)
        st.caption(
            "Score = sum of components, capped at 100. The 'Score breakdown' column shows each ticket's exact points. "
            "Aging threshold is adjustable in the sidebar; tier weights are a judgement call, not derived from data."
        )
