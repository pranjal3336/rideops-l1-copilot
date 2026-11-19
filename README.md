# RideOps L1 Support Copilot (case-study MVP)

Streamlit + pandas + scikit-learn tool for **L1 support agents**. Runs entirely on the supplied export
(`data/rideops_support_tickets.csv`, 1,444 tickets; `data/rideops_data_dictionary.csv`).

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
pytest -q          # optional: UI + logic tests
```

## Views
1. **Triage Queue** - 48 open tickets ranked by an additive, fully visible urgency score; filters for priority, tier, category, agent, status, plus aging / no-first-response / back-with-L1 toggles, search, sort, CSV download. KPI cards: open, aging, missing first response, engineering follow-ups.
2. **Ticket Workbench** - full record (all 20 CSV columns), client statistics, similar historical tickets (TF-IDF), category checklist, avoidable-escalation warning, readiness gates, structured Engineering escalation summary with copy button, resolve-after-verification.
3. **New Ticket Sandbox** - enter a ticket, get a suggested category (cross-validated), similar tickets, historical outcomes, checklist; optionally add it to the queue.

## Data integrity
- Only CSV columns are used; every statistic is computed live from them. Nothing is invented.
- **Simulated** actions (resolve, escalate, first response, new ticket) live only in the browser session and are labelled. **Reset Demo Data** clears them.
- Historical statistics use the original *closed* tickets only.

## Assumptions (also shown in-app)
- "Now" = data pull time, 30 Sep 2026 23:59 IST (adjustable in the sidebar).
- Aging = open longer than an adjustable threshold (default 72 h); the export has no SLA field.
- Avoidable escalation = closed escalation whose `eng_outcome` is not `Fixed`.
- Urgency weights and escalation-risk thresholds are judgement calls, documented in-app.
- Checklists are an authored playbook (the export has no resolution notes); validate with Support/Engineering.
- Category classifier accuracy is ~100% because descriptions are templated; real free-text accuracy will be lower (low-confidence cases are flagged).

## Layout
```
app.py                 entrypoint, sidebar, error handling
copilot/data.py        load / validate / enrich
copilot/scoring.py     urgency score
copilot/insights.py    scope stats, escalation risk, client stats
copilot/similarity.py  TF-IDF search + category classifier
copilot/playbooks.py   checklists
copilot/state.py       simulated actions + reset
copilot/views/         triage.py, workbench.py, sandbox.py
tests/test_app.py
```
