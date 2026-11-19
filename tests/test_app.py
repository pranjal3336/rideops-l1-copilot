"""UI + logic tests. Run: pytest -q"""
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def fresh() -> AppTest:
    return AppTest.from_file(APP, default_timeout=120).run()


def clean(at: AppTest):
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def go(at: AppTest, view: str) -> AppTest:
    return at.sidebar.radio[0].set_value(view).run()


def test_kpis_match_csv():
    df = pd.read_csv(Path(APP).parent / "data" / "rideops_support_tickets.csv")
    at = fresh(); clean(at)
    m = {x.label: x.value for x in at.metric}
    assert m["Open tickets"] == str(int(df.status.str.startswith("Open").sum()))
    assert m["Missing first response"] == str(int(df[df.status.str.startswith("Open")].first_response_at.isna().sum()))
    assert m["Engineering follow-ups"] == str(int((df.status == "Open - with Engineering").sum()))


def test_filters_work():
    at = fresh()
    at.multiselect(key="f_prio").set_value(["P1"]).run(); clean(at)
    assert at.markdown[[("Showing" in x.value) for x in at.markdown].index(True)].value.startswith("**Showing 3 of 48")
    at.multiselect(key="f_prio").set_value([]).run()
    at.toggle(key="f_noresp").set_value(True).run(); clean(at)
    assert any("Showing 5 of 48" in x.value for x in at.markdown)


def test_workbench_full_flow():
    at = fresh()
    go(at, "Ticket Workbench"); clean(at)
    df = pd.read_csv(Path(APP).parent / "data" / "rideops_support_tickets.csv")
    pid = df[(df.status == "Open - with L1") & (df.escalated_to_eng == "No")].ticket_id.iloc[0]
    at.selectbox(key="wb_pick").set_value(pid).run(); clean(at)
    for i in range(3):
        at.checkbox(key=f"chk::{pid}::{i}").set_value(True)
    at.run()
    at.text_area(key=f"scope::{pid}").set_value("12 employees on night shift affected").run()
    at.text_area(key=f"evid::{pid}").set_value("Reproduced on admin portal at 10 PM").run()
    at.checkbox(key=f"dup::{pid}").set_value(True).run(); clean(at)
    at.button(key=f"gen::{pid}").click().run(); clean(at)
    assert any("ENGINEERING ESCALATION SUMMARY" in c.value for c in at.code)
    at.button(key=f"esc::{pid}").click().run(); clean(at)
    assert at.session_state["sim_escalated"][pid]["eng_ref"].startswith("ENG-SIM")
    # resolve
    n = 0
    while f"ver::{pid}::{n}" in [c.key for c in at.checkbox]:
        at.checkbox(key=f"ver::{pid}::{n}").set_value(True); n += 1
    at.run()
    at.text_area(key=f"note::{pid}").set_value("Verified with client admin").run()
    at.button(key=f"res::{pid}").click().run(); clean(at)
    assert pid in at.session_state["sim_resolved"]
    go(at, "Triage Queue"); clean(at)
    assert {x.label: x.value for x in at.metric}["Open tickets"] == "47"
    at.button(key="reset_demo").click().run(); clean(at)
    assert {x.label: x.value for x in at.metric}["Open tickets"] == "48"


def test_sandbox_flow():
    at = fresh()
    go(at, "New Ticket Sandbox"); clean(at)
    at.text_area(key="sb_desc").set_value("Roster uploaded via Excel but 14 employees missing")
    at.button[0].click().run(); clean(at)
    assert at.session_state["sandbox"]["suggest"]["ranked"][0][0] == "Roster / booking not syncing"
    at.button(key="sb_add").click().run(); clean(at)
    assert at.session_state["sim_tickets"][0]["ticket_id"] == "SIM-001"
    go(at, "Triage Queue"); clean(at)
    assert {x.label: x.value for x in at.metric}["Open tickets"] == "49"


def test_sandbox_validation():
    at = fresh(); go(at, "New Ticket Sandbox")
    at.text_area(key="sb_desc").set_value("hi")
    at.button[0].click().run()
    assert at.error
