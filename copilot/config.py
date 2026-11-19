"""Central constants. Everything tied to the dataset schema lives here."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TICKETS_FILE = DATA_DIR / "rideops_support_tickets.csv"
DICT_FILE = DATA_DIR / "rideops_data_dictionary.csv"

# The brief says the data was pulled on 30 Sep 2026; used as the default "now".
DATA_PULL_ASOF = datetime(2026, 9, 30, 23, 59)

# Exact columns of rideops_support_tickets.csv (verified against the file).
REQUIRED_COLUMNS = [
    "ticket_id", "created_at", "channel", "client_id", "client_name",
    "client_tier", "category", "priority", "description", "assigned_agent",
    "first_response_at", "escalated_to_eng", "eng_ticket_id", "eng_handoffs",
    "eng_outcome", "status", "first_closed_at", "final_closed_at",
    "reopen_count", "csat_score",
]
DATETIME_COLS = ["created_at", "first_response_at", "first_closed_at", "final_closed_at"]

STATUS_L1 = "Open - with L1"
STATUS_ENG = "Open - with Engineering"
STATUS_CLOSED = "Closed"

OUTCOME_FIXED = "Fixed"
# Assumption (stated in the UI): any engineering verdict other than "Fixed" means the
# escalation did not need an engineering code/data fix -> treated as "avoidable".
OUTCOME_GUIDANCE = {
    "Config issue - returned to L1":
        "Verify client-side configuration (cut-offs, shifts, roles, templates) before escalating.",
    "Insufficient info - returned to L1":
        "Attach scope, time window, example trip/employee IDs and reproduction steps up front.",
    "Duplicate of known issue":
        "Check open engineering tickets for the same issue and link to them instead of raising a new one.",
    "Not a bug - how-to":
        "Resolve with a how-to / KB answer; no engineering needed.",
    "Not reproducible":
        "Capture reproduction evidence (screenshots, trip IDs, timestamps) and confirm it still reproduces.",
}

PRIORITIES = ["P1", "P2", "P3", "P4"]
TIERS = ["Enterprise", "Mid-market", "SMB"]
CHANNELS = ["Email", "Client portal", "Phone", "WhatsApp"]

VIEWS = ["Triage Queue", "Ticket Workbench", "New Ticket Sandbox"]

# Urgency score weights (max 100, clipped). Shown to agents verbatim in the UI.
W_PRIORITY = {"P1": 40, "P2": 28, "P3": 16, "P4": 6}
W_TIER = {"Enterprise": 5, "Mid-market": 2, "SMB": 0}
W_AGE_MAX = 25            # linear up to 2x the aging threshold
W_NO_FIRST_RESPONSE = 15
W_HANDOFF_EACH = 5        # per engineering handoff beyond the first (cap below)
W_HANDOFF_CAP = 10
W_REOPEN_EACH = 5
W_REOPEN_CAP = 10
W_AWAITING_L1 = 8         # engineering returned the ticket; L1 owes the next action
DEFAULT_AGING_HOURS = 72

# Escalation-readiness gates
CHECKLIST_GATE = 0.6      # share of diagnostic checklist that must be ticked
