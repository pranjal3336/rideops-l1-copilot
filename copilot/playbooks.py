"""Category-specific diagnostic checklists.

IMPORTANT: these are an *authored starting playbook* (generic support best practice),
NOT derived from the ticket data - the CSV contains no resolution notes. They are
labelled as such in the UI and should be validated with Engineering / the Support Lead.
The categories are the exact `category` values present in the CSV.
"""
from __future__ import annotations

import re

PLAYBOOKS: dict[str, dict] = {
    "Roster / booking not syncing": {
        "checks": [
            "Record the affected employees, shift and date, and compare the client-portal roster with the booking list.",
            "Check the client's booking cut-off setting against the time the booking/change was made.",
            "Confirm the booking/roster was saved and submitted (not draft) and that no validation error was shown.",
            "For Excel uploads: check template version, date/shift formats, employee IDs and duplicate rows in the file.",
            "Check that cancellations were applied to the correct date and shift.",
            "Ask the client to refresh/re-sync once and note whether the problem reproduces.",
        ],
        "verify": [
            "Affected employees/shift now appear correctly in tomorrow's roster.",
            "Client admin confirmed the roster matches their records.",
        ],
        "evidence": "Employee IDs or count, shift + date, booking IDs, uploaded file name, time of the action, screenshots.",
    },
    "Live tracking / GPS incorrect": {
        "checks": [
            "Identify trip ID, cab/driver, time window and which surface is affected (employee app, admin portal, tracking link).",
            "Check scope: one trip/driver or many trips at the same time?",
            "Check driver app: location permission set to always, battery saver off, mobile data available.",
            "Note driver and employee app versions.",
            "For tracking links: open the link in another browser/device and confirm it has not expired.",
            "Compare the shown route/ETA with the planned route; note if a pickup address looks mis-geocoded.",
        ],
        "verify": [
            "Live location updates on an active trip (or the tracking link opens for the client).",
            "Client confirmed the ETA / position is now correct.",
        ],
        "evidence": "Trip IDs, vehicle number, timestamps (IST), screenshots/screen recording, app versions.",
    },
    "Report export failing": {
        "checks": [
            "Record report name, filters and date range used.",
            "Retry in smaller date ranges and note the range at which it starts failing.",
            "Retry in another browser / clear cache / try another export format.",
            "For scheduled reports: check recipient list, junk/spam folder and the schedule configuration.",
            "For missing trips: compare the exported trip count with the on-screen trip list for the same filters and statuses.",
            "Check the open engineering tickets below for an already-known export issue.",
        ],
        "verify": [
            "Re-export succeeded and row/trip counts reconcile with the on-screen list.",
            "Client confirmed they received a usable file.",
        ],
        "evidence": "Report name, filters, date range, expected vs actual row count, failure time, screenshot of the error.",
    },
    "Cab delay / no-show complaint": {
        "checks": [
            "Pull the trip record: scheduled vs actual pickup time, driver, vehicle and route.",
            "Check the live-tracking history to confirm whether the cab was late or never arrived.",
            "Confirm the driver/vehicle assignment was published before the shift.",
            "Ask the vendor/driver desk for the reason and log it on the ticket.",
            "Check whether the same route has repeated delays this week.",
            "Share the reason and corrective action with the client admin.",
        ],
        "verify": [
            "Root cause and corrective action shared with the client.",
            "Client acknowledged the response.",
        ],
        "evidence": "Trip ID, route, shift, scheduled/actual times, driver and vehicle.",
    },
    "How-to / feature request": {
        "checks": [
            "Search the help content for an existing guide and share the steps.",
            "Confirm whether the capability exists for this client's setup.",
            "If it is a feature request, log it to the product backlog instead of escalating as a defect.",
            "Offer a short screen-share if the client still cannot complete the task.",
        ],
        "verify": [
            "Client completed the task, or the request was logged to the product backlog with the client informed.",
        ],
        "evidence": "What the client is trying to achieve and the exact screen they are on.",
    },
    "Login / access issue": {
        "checks": [
            "Confirm the user's email/ID and that the request comes from the client's transport admin.",
            "Check the account exists, is active and has the expected role/permissions.",
            "For password problems: confirm the reset link was sent, is unexpired and the account is not locked.",
            "For SSO: count the affected users and ask whether the client's IT changed IdP settings or certificates recently.",
            "Try an incognito window / another browser.",
        ],
        "verify": [
            "User can log in and reach the required module.",
            "Client admin confirmed access.",
        ],
        "evidence": "Affected user list, exact error message, time of failure, SSO/IdP details if relevant.",
    },
    "OTP / boarding issue": {
        "checks": [
            "Record trip ID and employee, and confirm the employee's phone number on file.",
            "Check OTP SMS delivery (DND, network, number format).",
            "Check the trip status and that the OTP is for the right trip and not expired.",
            "Check driver app version and that the correct OTP was entered.",
            "For 'not boarded' cases: compare boarding timestamp/location with the pickup point.",
        ],
        "verify": [
            "OTP delivered and trip started / boarding status corrected.",
            "Client or employee confirmed.",
        ],
        "evidence": "Trip ID, employee ID, timestamps, driver app version, screenshot of the error.",
    },
    "Billing / invoice discrepancy": {
        "checks": [
            "Identify the invoice number, billing period and the disputed line items.",
            "Reconcile the invoice trip count with the trip report for the same period and filters.",
            "Check which rate card version applies and its effective date (e.g. new vendor).",
            "Check cancelled-trip, dead-km and toll lines against the contract terms and for duplicates.",
            "Prepare a line-by-line comparison (expected vs billed).",
        ],
        "verify": [
            "Client received a reconciled explanation or corrected invoice.",
            "Client accepted the resolution.",
        ],
        "evidence": "Invoice number, disputed lines, trip IDs, expected vs billed amounts.",
    },
    "Employee address / geocode change": {
        "checks": [
            "Confirm employee ID, old address, new address and the effective date.",
            "Check the address is updated in the employee master and the pin is correct on the map.",
            "Check upcoming rosters were regenerated with the new pickup point.",
            "For bulk issues (whole society): collect the employee list and correct pin coordinates.",
        ],
        "verify": [
            "Pickup point is correct on the next scheduled trip.",
            "Client confirmed.",
        ],
        "evidence": "Employee IDs, old/new address, correct pin location, effective date.",
    },
    "Driver / vehicle compliance docs": {
        "checks": [
            "Confirm document type, vehicle/driver and expiry date.",
            "Check upload format/size and retry the upload.",
            "Check verification status with the vendor/compliance desk.",
            "If a document is expired: confirm the vehicle is de-assigned or replaced for upcoming rosters.",
        ],
        "verify": [
            "Document accepted / status updated, or vehicle replaced.",
            "Client or vendor confirmed.",
        ],
        "evidence": "Vehicle/driver ID, document type, expiry date, upload error.",
    },
}

GENERIC = {
    "checks": [
        "Confirm the scope (who/what/when) and capture exact identifiers (trip, employee, invoice IDs).",
        "Try to reproduce the issue and note the exact error or behaviour.",
        "Check similar historical tickets and open engineering tickets for a known issue.",
    ],
    "verify": ["Issue no longer reproduces.", "Client confirmed the fix."],
    "evidence": "Identifiers, timestamps (IST), screenshots, steps to reproduce.",
}

# Extra, text-triggered checks (matched on the ticket description).
EXTRAS: list[tuple[str, str]] = [
    (r"date range", "Long date ranges: retry with a shorter range and report the longest range that works."),
    (r"\bsso\b", "SSO: ask client IT for IdP, recent certificate/metadata changes and the list of affected users."),
    (r"excel", "Excel involvement: ask for the exact file used and compare row counts with what was imported/exported."),
    (r"whatsapp alerts|show driver rating|bulk-cancel", "Looks like a feature request: log to the product backlog rather than escalating as a bug."),
    (r"insurance expired", "Check whether the vehicle is still assigned to upcoming shifts and arrange a replacement."),
    (r"duplicate entries", "Duplicates: export the roster and identify whether duplicates share booking IDs."),
    (r"route \d+", "Repeated delays: check the same route in other tickets this week before contacting the vendor."),
    (r"cut-?off", "Cut-off: compare the configured cut-off with the booking timestamp."),
]


def playbook_for(category: str, description: str = "") -> dict:
    base = PLAYBOOKS.get(category, GENERIC)
    checks = list(base["checks"])
    low = (description or "").lower()
    for pattern, text in EXTRAS:
        if re.search(pattern, low) and text not in checks:
            checks.append(text)
    return {"checks": checks, "verify": list(base["verify"]), "evidence": base["evidence"],
            "is_generic": category not in PLAYBOOKS}
