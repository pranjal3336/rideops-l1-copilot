"""View 2: Ticket workbench."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import config as C
from .. import insights as I
from .. import playbooks, scoring, state
from ..ctx import Ctx
from ..ui import SIM_NOTICE, copy_button, priority_label


# --------------------------------------------------------------------- helpers
def _val(x) -> str:
    if x is None or (not isinstance(x, str) and pd.isna(x)):
        return "—"
    if isinstance(x, pd.Timestamp):
        return I.fmt_dt(x)
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def build_summary(t, ctx: Ctx, stats: dict, cs: dict, similar: pd.DataFrame, pb: dict, checks: list[bool],
                  scope: str, evidence: str, ask: str, gates_ok: bool, override: bool,
                  known: pd.DataFrame) -> str:
    csat_txt = "n/a" if pd.isna(cs["csat_mean"]) else "%.1f (n=%d)" % (cs["csat_mean"], cs["csat_n"])
    done = [c for c, ok in zip(pb["checks"], checks) if ok]
    todo = [c for c, ok in zip(pb["checks"], checks) if not ok]
    lines = [
        "ENGINEERING ESCALATION SUMMARY",
        "[SIMULATED DRAFT - generated in the RideOps L1 Support Copilot demo; not sent to anyone]",
        "",
        f"Ticket: {t['ticket_id']} | Priority: {t['priority']} | Channel: {t['channel']}",
        f"Category (L1 tag): {t['category']}",
        f"Raised (IST): {I.fmt_dt(t['created_at'])} | Age: {I.fmt_hours(t['age_h'])} | Assigned L1 agent: {t['assigned_agent']}",
        f"First response: {I.fmt_dt(t['first_response_at'])}",
        "",
        f"Client: {t['client_name']} ({t['client_id']}), {t['client_tier']}",
        f"Client history in this dataset: {cs['total']} tickets ({cs['last_30d']} in last 30 days, {cs['open']} open), "
        f"{cs['p1_p2']} P1/P2, escalation rate {I.fmt_pct(cs['esc_rate'])}, avg CSAT {csat_txt}",
        "",
        "ISSUE (client description)",
        f"  {t['description']}",
        "",
        "SCOPE & IMPACT (entered by L1)",
        f"  {scope.strip() or 'NOT PROVIDED'}",
        "",
        "REPRODUCTION STEPS / EVIDENCE (entered by L1)",
        f"  {evidence.strip() or 'NOT PROVIDED'}",
        "",
        "L1 CHECKS",
        *(f"  [x] {c}" for c in done),
        *(f"  [ ] {c}" for c in todo),
        "",
        "ENGINEERING HISTORY ON THIS TICKET",
        f"  Handoffs so far: {int(t['eng_handoffs'])} | Latest eng outcome: {_val(t['eng_outcome'])} | "
        f"Linked eng ticket: {_val(t['eng_ticket_id'])} | Client reopens: {int(t['reopen_count'])}",
        "",
        f"HISTORICAL CONTEXT ({stats['scope']}: {stats['label']})",
        f"  {stats['n_escalated']} past escalations; {I.fmt_pct(stats['fixed_rate'])} ended 'Fixed', "
        f"{I.fmt_pct(stats['avoidable_rate'])} came back without an engineering fix.",
    ]
    for outcome, cnt in stats["outcomes"].head(6).items():
        lines.append(f"    - {outcome}: {int(cnt)}")
    lines += ["", "SIMILAR PAST TICKETS"]
    if similar.empty:
        lines.append("  None found.")
    for _, r in similar.head(3).iterrows():
        lines.append(
            f"  - {r['ticket_id']} | status: {r['status']} | escalated: {r['escalated_to_eng']} | "
            f"eng outcome: {_val(r['eng_outcome'])} | time to close: {I.fmt_hours(r['resolution_h'])} | {r['description']}"
        )
    lines += ["", "OPEN ENGINEERING TICKETS IN SAME CATEGORY (possible duplicates)"]
    if known.empty:
        lines.append("  None.")
    for _, r in known.head(5).iterrows():
        tag = " [same issue type]" if r["same_issue_type"] else ""
        lines.append(f"  - {_val(r['eng_ticket_id'])} (from {r['ticket_id']}){tag}: {r['description']}")
    lines += [
        "",
        "REQUEST TO ENGINEERING",
        f"  {ask.strip() or 'Please investigate and advise on the root cause / fix.'}",
        "",
        "ESCALATION READINESS",
        "  All readiness gates passed." if gates_ok else
        ("  Gates NOT all passed; escalated by agent override." if override else "  Some readiness gates are still open."),
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------------ view
def render(ctx: Ctx) -> None:
    st.subheader("Ticket workbench")
    eff = ctx.eff

    include_closed = st.toggle("Include closed tickets (browse history)", key="wb_closed")
    open_sorted = scoring.score(eff[eff["is_open"]], ctx.aging_h).sort_values(["urgency", "age_h"], ascending=False)
    ids = list(open_sorted["ticket_id"])
    if include_closed:
        ids += list(eff[~eff["is_open"]].sort_values("created_at", ascending=False)["ticket_id"])
    sel = st.session_state.get("selected_ticket")
    if sel and sel not in ids and sel in set(eff["ticket_id"]):
        ids.insert(0, sel)
    if not ids:
        st.info("No tickets to show. Turn on 'Include closed tickets' or Reset Demo Data.")
        return
    idx = ids.index(sel) if sel in ids else 0
    labels = dict(zip(eff["ticket_id"], eff["ticket_id"] + " · " + eff["priority"] + " · " + eff["client_name"]
                      + " · " + eff["description"].str.slice(0, 60)))
    pick = st.selectbox("Ticket", ids, index=idx, format_func=lambda i: labels.get(i, i), key="wb_pick")
    st.session_state["selected_ticket"] = pick

    t = eff[eff["ticket_id"] == pick].iloc[0]
    pid = t["ticket_id"]
    is_open = bool(t["is_open"])
    asof = ctx.asof.to_pydatetime()

    # ---------------------------------------------------------------- header
    st.markdown(f"### {pid} · {t['description']}")
    st.markdown(
        f":blue-badge[{priority_label(t['priority'])}] :gray-badge[{t['status']}] "
        f":gray-badge[{t['client_tier']}] :gray-badge[{t['category']}]"
        + (f" :orange-badge[{t['sim_flag'].upper()}]" if t["sim_flag"] else "")
    )
    m = st.columns(5)
    if is_open:
        sc = scoring.score(eff[eff["ticket_id"] == pid], ctx.aging_h).iloc[0]
        m[0].metric("Urgency", f"{sc['urgency']:.0f}/100", border=True, help=sc["why"])
        m[1].metric("Age", I.fmt_hours(t["age_h"]), border=True)
    else:
        m[0].metric("Urgency", "closed", border=True)
        m[1].metric("Time to final close", I.fmt_hours(t["resolution_h"]), border=True)
    m[2].metric("First response after", I.fmt_hours(t["first_resp_h"]) if pd.notna(t["first_resp_h"]) else "missing", border=True)
    m[3].metric("Eng handoffs / reopens", f"{int(t['eng_handoffs'])} / {int(t['reopen_count'])}", border=True)
    m[4].metric("CSAT", "—" if pd.isna(t["csat_score"]) else f"{t['csat_score']:.0f}/5", border=True)
    if is_open:
        st.caption(f"Urgency breakdown: {sc['why']}")

    # ----------------------------------------------- engineering state banners
    if is_open and t["awaiting_l1"]:
        outcome = t["eng_outcome"]
        if outcome == C.OUTCOME_FIXED:
            st.success("Engineering marked this **Fixed** and it is back with L1: verify with the client, then close it.")
        elif isinstance(outcome, str):
            st.warning(f"Engineering returned this ticket: **{outcome}**. "
                       f"{C.OUTCOME_GUIDANCE.get(outcome, '')} L1 owns the next action.")
    if is_open and t["eng_pending"]:
        st.info(f"With engineering ({_val(t['eng_ticket_id'])}). L1 still owns client updates; "
                f"latest outcome recorded: {_val(t['eng_outcome'])}.")
    if is_open and t["missing_first_response"]:
        c1, c2 = st.columns([2, 5])
        c1.button("Log first response (simulated)", key=f"fr::{pid}", on_click=state.log_first_response, args=(pid, asof))
        c2.warning("No first response recorded yet.")

    # --------------------------------------------- avoidable escalation warning
    stats = I.scope_stats(ctx.hist, t["category"], t["tmpl"])
    risk = I.escalation_risk(stats, ctx.baseline_avoidable)
    if not (is_open and t["eng_pending"]):
        head = (f"Avoidable-escalation risk **{risk['level'].upper()}**: {I.fmt_pct(risk['rate'])} of "
                f"{risk['n_escalated']} past escalations for this {stats['scope']} ended without an engineering fix "
                f"(all closed escalations: {I.fmt_pct(risk['baseline'])}).")
        body = "".join(f"\n- **{o}**: {c} of {risk['n_escalated']} ({I.fmt_pct(p)}). {g}" for o, c, p, g in risk["reasons"])
        extra = (f"\n- Comparable tickets resolved by L1 without escalation: median {I.fmt_hours(stats['median_res_h_l1'])}; "
                 f"escalated ones: median {I.fmt_hours(stats['median_res_h_eng'])}; "
                 f"{I.fmt_pct(stats['esc_rate'])} of them were escalated.")
        if risk["level"] == "high":
            st.error(head + body + extra, icon="🚨")
        elif risk["level"] == "elevated":
            st.warning(head + body + extra, icon="⚠️")
        elif risk["level"] == "lower":
            st.success(head + body + extra, icon="✅")
        else:
            st.info(f"Not enough closed escalations for this {stats['scope']} to judge ({risk['n_escalated']}). " + extra.strip("\n- "))
    with st.expander("How this warning is calculated"):
        st.markdown(
            "- Scope = this ticket's *issue type* (description with numbers masked) if it has at least 8 closed escalations, "
            "otherwise its *category*.\n"
            "- **Avoidable** = closed escalation whose `eng_outcome` is anything other than `Fixed` (assumption).\n"
            "- Level: HIGH at 65% or more, ELEVATED at 50-64%, LOWER below 50%, no rating with fewer than 5 escalations.\n"
            "- Only the original export is used (closed tickets); simulated tickets never feed these numbers."
        )
        if not stats["outcomes"].empty:
            st.bar_chart(stats["outcomes"], horizontal=True)

    tabs = st.tabs(["Details", "Client context", "Similar tickets", "Diagnose & act"])

    # ---------------------------------------------------------------- details
    with tabs[0]:
        c = st.columns(4)
        c[0].markdown(f"**Created**  \n{I.fmt_dt(t['created_at'])}")
        c[1].markdown(f"**First response**  \n{I.fmt_dt(t['first_response_at'])}")
        c[2].markdown(f"**First closed**  \n{I.fmt_dt(t['first_closed_at'])}")
        c[3].markdown(f"**Final closed**  \n{I.fmt_dt(t['final_closed_at'])}")
        rec = pd.DataFrame({"Field (CSV column)": C.REQUIRED_COLUMNS,
                            "Value": [_val(t[col]) for col in C.REQUIRED_COLUMNS]})
        st.dataframe(rec, hide_index=True, height=38 + 35 * len(rec))
        st.caption("Exactly the 20 columns of the ticket export. Timestamps are IST. A blank eng_outcome on an open ticket means "
                   "engineering has not returned a verdict yet; on open tickets it is the latest verdict recorded.")

    # ---------------------------------------------------------- client context
    with tabs[1]:
        cs = I.client_stats(eff, t["client_id"], ctx.asof)
        st.markdown(f"**{t['client_name']}** ({t['client_id']}) · {t['client_tier']}")
        a = st.columns(4)
        a[0].metric("Tickets (all time in data)", cs["total"], help=f"Average per client: {cs['avg_per_client']:.1f}", border=True)
        a[1].metric("Open now", cs["open"], border=True)
        a[2].metric("Last 30 days", cs["last_30d"], border=True)
        a[3].metric("P1 / P2 tickets", cs["p1_p2"], border=True)
        b = st.columns(4)
        b[0].metric("Escalation rate", I.fmt_pct(cs["esc_rate"]), border=True)
        b[1].metric("Reopen rate (closed)", I.fmt_pct(cs["reopen_rate"]), border=True)
        b[2].metric("Avg CSAT", "—" if pd.isna(cs["csat_mean"]) else f"{cs['csat_mean']:.1f}", help=f"n = {cs['csat_n']} rated tickets", border=True)
        b[3].metric("Avg tickets per client", f"{cs['avg_per_client']:.1f}", border=True)
        rep = cs["recent_by_category"]
        rep = rep[rep >= 2]
        if not rep.empty:
            st.warning("Repeat issues in the last 30 days: " + "; ".join(f"{k} ({v})" for k, v in rep.items()))
        st.markdown("**Tickets by category**")
        st.bar_chart(cs["by_category"], horizontal=True)
        st.markdown("**Most recent tickets**")
        fr = cs["frame"].head(10)
        st.dataframe(pd.DataFrame({
            "Ticket": fr["ticket_id"], "Created": fr["created_at"].dt.strftime("%d %b %H:%M"), "Priority": fr["priority"],
            "Category": fr["category"], "Status": fr["status"], "Escalated": fr["escalated_to_eng"],
            "Reopens": fr["reopen_count"], "CSAT": fr["csat_score"], "Description": fr["description"],
        }), hide_index=True)

    # --------------------------------------------------------- similar tickets
    with tabs[2]:
        s1, s2 = st.columns([1, 1])
        k = s1.slider("How many similar tickets", 3, 15, 8, key=f"sim_k")
        closed_only = s2.toggle("Closed tickets only (known outcomes)", value=True, key="sim_closed")
        similar = ctx.index.similar(t["description"], category=t["category"], client_id=t["client_id"],
                                    exclude_id=pid, k=k, closed_only=closed_only)
        if similar.empty:
            st.info("No similar historical tickets found.")
        else:
            st.dataframe(pd.DataFrame({
                "Match": (similar["match"] * 100).round(0), "Ticket": similar["ticket_id"], "Client": similar["client_name"],
                "Created": similar["created_at"].dt.strftime("%d %b %Y"), "Status": similar["status"],
                "Escalated": similar["escalated_to_eng"], "Eng outcome": similar["eng_outcome"],
                "Handoffs": similar["eng_handoffs"], "Time to close": similar["resolution_h"].map(I.fmt_hours),
                "Reopens": similar["reopen_count"], "Description": similar["description"],
            }), hide_index=True, column_config={
                "Match": st.column_config.ProgressColumn("Match %", min_value=0, max_value=100, format="%.0f")})
            cl = similar[~similar["status"].str.startswith("Open")]
            if len(cl):
                st.caption(
                    f"Of these {len(cl)} closed tickets: {int(cl['escalated'].sum())} were escalated; "
                    f"median time to close {I.fmt_hours(cl['resolution_h'].median())}; "
                    f"{int((cl['reopen_count'] > 0).sum())} were reopened.")
        st.caption("Match % = TF-IDF text similarity of descriptions (numbers masked) + 10 pts same category + 3 pts same client, "
                   "ties broken by recency. The export has no resolution notes, so only outcomes (not fix steps) can be shown.")

    # ----------------------------------------------------------- diagnose & act
    with tabs[3]:
        pb = playbooks.playbook_for(t["category"], t["description"])
        locked = not is_open
        if locked:
            st.info("This ticket is closed. Checklists are shown for reference; actions are disabled.")

        st.markdown("#### 1 · Diagnostic checklist")
        st.caption(":gray-badge[Authored playbook] Generic support best practice for this category; it is not derived from ticket data "
                   "(the export has no resolution notes). Validate with Engineering / the Support Lead.")
        checks = [st.checkbox(txt, key=f"chk::{pid}::{i}", disabled=locked) for i, txt in enumerate(pb["checks"])]
        frac = sum(checks) / len(checks)
        st.progress(frac, text=f"{sum(checks)}/{len(checks)} checks done")

        known = I.known_open_eng(eff, t["category"], t["tmpl"], exclude_id=pid)
        st.markdown("**Open engineering tickets in this category** (link instead of re-raising if it is the same problem)")
        if known.empty:
            st.caption("None open right now.")
        else:
            st.dataframe(known.assign(created_at=known["created_at"].dt.strftime("%d %b %H:%M")).rename(columns={
                "ticket_id": "Ticket", "eng_ticket_id": "Eng ticket", "client_name": "Client", "description": "Description",
                "created_at": "Created", "eng_handoffs": "Handoffs", "same_issue_type": "Same issue type"}), hide_index=True)
        reviewed = st.checkbox("I reviewed similar tickets and open engineering tickets (no duplicate, or linked)",
                               key=f"dup::{pid}", disabled=locked)

        st.divider()
        st.markdown("#### 2 · Escalate to engineering")
        scope = st.text_area("Scope & impact (who / what / when; how many users or trips)", key=f"scope::{pid}", disabled=locked, height=80)
        evid = st.text_area("Reproduction steps / evidence", key=f"evid::{pid}", disabled=locked, height=80,
                            help=f"Engineering usually needs: {pb['evidence']}")
        st.caption(f"Engineering usually needs: {pb['evidence']}")
        ask = st.text_input("What you need from engineering", key=f"ask::{pid}", disabled=locked)

        gates = [
            (f"Diagnostic checklist at least {C.CHECKLIST_GATE:.0%} done ({sum(checks)}/{len(checks)})", frac >= C.CHECKLIST_GATE),
            ("Scope & impact entered", len(scope.strip()) >= 10),
            ("Reproduction steps / evidence entered", len(evid.strip()) >= 10),
            ("Similar and open engineering tickets reviewed", reviewed),
        ]
        gates_ok = all(ok for _, ok in gates)
        st.markdown("**Escalation readiness**  \n" + "  \n".join(f"{'✅' if ok else '⬜'} {txt}" for txt, ok in gates))
        similar_for_summary = ctx.index.similar(t["description"], category=t["category"], client_id=t["client_id"],
                                                exclude_id=pid, k=3, closed_only=True)
        cs_sum = I.client_stats(eff, t["client_id"], ctx.asof)
        override = st.checkbox("Escalate anyway (readiness gates incomplete; I accept the avoidable-escalation risk)",
                               key=f"ovr::{pid}", disabled=locked or gates_ok or bool(t["eng_pending"]))
        summary_now = build_summary(t, ctx, stats, cs_sum, similar_for_summary, pb, checks, scope, evid, ask, gates_ok, override, known)
        skey = f"summary::{pid}"

        def _store_summary(text=summary_now, key=skey):
            st.session_state[key] = text

        g1, g2 = st.columns(2)
        g1.button("Generate escalation summary", key=f"gen::{pid}", on_click=_store_summary, disabled=locked)
        can_escalate = (not locked) and (not t["eng_pending"]) and skey in st.session_state and (gates_ok or override)
        g2.button("Mark escalated to Engineering (simulated)", key=f"esc::{pid}", type="primary", disabled=not can_escalate,
                  on_click=state.escalate_ticket, args=(pid, summary_now, override and not gates_ok, asof),
                  help="Generate the summary first; needs all gates passed or the override ticked.")
        if skey in st.session_state:
            st.code(st.session_state[skey], language=None, wrap_lines=True, height=360)
            copy_button(st.session_state[skey])
            if st.session_state[skey] != summary_now:
                st.caption("Inputs changed since this summary was generated; click Generate again to refresh it.")
        if pid in st.session_state["sim_escalated"]:
            e = st.session_state["sim_escalated"][pid]
            st.success(f"Simulated escalation recorded as {e['eng_ref']}. {SIM_NOTICE}")

        st.divider()
        st.markdown("#### 3 · Resolve after verification")
        ver = [st.checkbox(txt, key=f"ver::{pid}::{i}", disabled=locked) for i, txt in enumerate(pb["verify"])]
        note = st.text_area("Resolution note (what was done / confirmed)", key=f"note::{pid}", disabled=locked, height=70)
        if is_open and t["eng_pending"]:
            st.caption("This ticket is with engineering; closing it here is only a simulation and normally follows engineering's outcome.")
        ready = all(ver) and len(note.strip()) >= 10
        st.button("Mark resolved (simulated)", key=f"res::{pid}", type="primary", disabled=locked or not ready,
                  on_click=state.resolve_ticket, args=(pid, note, [v for v, ok in zip(pb["verify"], ver) if ok], t["assigned_agent"], asof),
                  help="Enabled once every verification item is ticked and a resolution note is written.")
        if pid in st.session_state["sim_resolved"]:
            r = st.session_state["sim_resolved"][pid]
            st.success(f"Resolved in this demo session. Note: {r['note']}")
            st.button("Undo simulated resolution", key=f"undo::{pid}", on_click=state.undo_resolution, args=(pid, asof))
        st.caption(SIM_NOTICE)
