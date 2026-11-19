"""View 3: New ticket sandbox."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import config as C
from .. import insights as I
from .. import playbooks, state
from ..ctx import Ctx
from ..ui import SIM_NOTICE, goto_ticket


def _analyse(ctx: Ctx, form: dict) -> None:
    text = form["description"].strip()
    st.session_state["sandbox"] = {
        "form": form,
        "suggest": ctx.index.suggest_category(text),
        "similar": ctx.index.similar(text, client_id=form["client_id"], k=8),
    }


def render(ctx: Ctx) -> None:
    st.subheader("New ticket sandbox")
    st.caption(
        "Enter a ticket as a client would raise it. The copilot matches it against the historical tickets in the export, "
        "suggests a category and shows the checklist. Nothing is saved anywhere except this demo session."
    )

    clients = ctx.clients.sort_values("client_name")
    client_labels = {r.client_id: f"{r.client_name} ({r.client_id}) · {r.client_tier}" for r in clients.itertuples()}
    load = I.agent_load(ctx.eff)
    lowest = load.idxmin()

    with st.form("new_ticket_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        client_id = c1.selectbox("Client", list(client_labels), format_func=client_labels.get, key="sb_client")
        channel = c2.selectbox("Channel", C.CHANNELS, key="sb_channel")
        c3, c4 = st.columns(2)
        priority = c3.selectbox("Priority", C.PRIORITIES, index=2, key="sb_priority")
        agents = list(load.index)
        agent = c4.selectbox("Assign to L1 agent", agents, index=agents.index(lowest), key="sb_agent",
                             format_func=lambda a: f"{a} ({int(load[a])} open)" + (" · lowest load" if a == lowest else ""))
        description = st.text_area(
            "Issue description", key="sb_desc", height=100,
            placeholder="e.g. Roster uploaded via Excel but 14 employees missing",
        )
        submitted = st.form_submit_button("Analyse ticket", type="primary")

    if submitted:
        if len(description.strip()) < 8:
            st.error("Please describe the issue in at least a few words (8+ characters).")
        else:
            try:
                _analyse(ctx, {"client_id": client_id, "channel": channel, "priority": priority,
                               "assigned_agent": agent, "description": description})
            except Exception as exc:  # noqa: BLE001 - keep the demo alive
                st.session_state["sandbox"] = None
                st.error(f"Could not analyse this ticket: {exc}")

    res = st.session_state.get("sandbox")
    ex1, ex2 = st.columns([3, 2])
    with ex1.expander("Classifier quality (cross-validated on the export)"):
        st.write(
            f"{ctx.index.cv_folds}-fold cross-validated accuracy of the category suggestion on the {len(ctx.index.base):,} historical tickets: "
            f"**{ctx.index.cv_accuracy:.1%}**."
        )
        st.caption("Descriptions in this export are highly templated, so real-world accuracy on free-text tickets will be lower; "
                   "low-confidence suggestions are flagged for manual confirmation.")
    if not res:
        st.info("Fill in the form and click **Analyse ticket**.")
        return

    form, sug = res["form"], res["suggest"]
    client = clients[clients["client_id"] == form["client_id"]].iloc[0]
    st.divider()
    st.markdown(f"#### Analysis for {client['client_name']} · {client['client_tier']} · {form['priority']}")
    st.markdown(f"> {form['description'].strip()}")

    # ---------------------------------------------------------- category
    top_cat, top_p = sug["ranked"][0]
    st.markdown("**Suggested category**")
    cols = st.columns(len(sug["ranked"]))
    for col, (cat, p) in zip(cols, sug["ranked"]):
        col.metric(cat, f"{p:.0%}", border=True)
    if sug["low_confidence"]:
        st.warning(f"Low confidence (top probability {top_p:.0%}, vocabulary coverage {sug['coverage']:.0%}). "
                   "Please confirm the category manually below.")
    cats = sorted(ctx.base["category"].unique())
    options = ["Use suggestion: " + top_cat] + [c for c in cats]
    choice = st.selectbox("Category to use", options, key="sb_cat_choice")
    category = top_cat if choice.startswith("Use suggestion") else choice

    # ------------------------------------------------------- similar issues
    st.markdown("**Similar historical tickets**")
    similar = ctx.index.similar(form["description"], category=category, client_id=form["client_id"], k=8)
    if similar.empty:
        st.info("No similar historical tickets found. Check the category and wording.")
    else:
        st.dataframe(pd.DataFrame({
            "Match": (similar["match"] * 100).round(0), "Ticket": similar["ticket_id"], "Client": similar["client_name"],
            "Category": similar["category"], "Status": similar["status"], "Escalated": similar["escalated_to_eng"],
            "Eng outcome": similar["eng_outcome"], "Time to close": similar["resolution_h"].map(I.fmt_hours),
            "Description": similar["description"],
        }), hide_index=True, column_config={
            "Match": st.column_config.ProgressColumn("Match %", min_value=0, max_value=100, format="%.0f")})
        cl = similar[~similar["status"].str.startswith("Open")]
        if len(cl):
            st.caption(f"Of the {len(cl)} closed matches: {int(cl['escalated'].sum())} were escalated; "
                       f"median time to close {I.fmt_hours(cl['resolution_h'].median())}.")

    # ----------------------------------- historical outcomes + escalation risk
    tmpl = pd.Series([form["description"]]).str.lower().str.replace(r"\d+", "#", regex=True).iloc[0]
    stats = I.scope_stats(ctx.hist, category, tmpl)
    risk = I.escalation_risk(stats, ctx.baseline_avoidable)
    st.markdown("**What happened to this kind of ticket before**")
    a = st.columns(4)
    a[0].metric(f"Tickets ({stats['scope']})", f"{stats['n_tickets']:,}", border=True)
    a[1].metric("Escalated to engineering", I.fmt_pct(stats["esc_rate"]), border=True)
    a[2].metric("Escalations ending 'Fixed'", I.fmt_pct(stats["fixed_rate"]), border=True)
    a[3].metric("Median close: L1 vs eng", f"{I.fmt_hours(stats['median_res_h_l1'])} vs {I.fmt_hours(stats['median_res_h_eng'])}", border=True)
    msg = (f"Avoidable-escalation risk **{risk['level'].upper()}**: {I.fmt_pct(risk['rate'])} of {risk['n_escalated']} "
           f"past escalations here ended without an engineering fix (all closed escalations: {I.fmt_pct(risk['baseline'])}).")
    for o, c, p, g in risk["reasons"]:
        msg += f"\n- **{o}**: {c} ({I.fmt_pct(p)}). {g}"
    {"high": st.error, "elevated": st.warning, "lower": st.success}.get(risk["level"], st.info)(msg)

    # --------------------------------------------------------- checklist
    pb = playbooks.playbook_for(category, form["description"])
    st.markdown("**Diagnostic checklist for the agent**")
    st.caption(":gray-badge[Authored playbook] Generic best practice, not derived from ticket data.")
    for i, txt in enumerate(pb["checks"]):
        st.checkbox(txt, key=f"sb_chk::{category}::{i}")
    st.caption(f"If you do escalate, include: {pb['evidence']}")

    # ----------------------------------------------------- add to the queue
    st.divider()
    st.markdown("**Add to the triage queue**")
    row = {**form, "category": category, "client_name": client["client_name"], "client_tier": client["client_tier"]}
    c1, c2 = st.columns([2, 3])
    added = st.session_state.get("sandbox_added")
    if c1.button("Add to triage queue (simulated)", type="primary", key="sb_add"):
        sid = state.add_sim_ticket(row, ctx.asof.to_pydatetime())
        st.session_state["sandbox_added"] = sid
        st.rerun()
    c2.caption(SIM_NOTICE)
    if added:
        st.success(f"Added as {added}. It now appears in the Triage Queue and can be opened in the Workbench.")
        st.button(f"Open {added} in Workbench", on_click=goto_ticket, args=(added,), key="sb_open")
