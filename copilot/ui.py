"""Small shared UI helpers."""
from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

PRIORITY_ICON = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🟢"}

SIM_NOTICE = ":orange-badge[SIMULATED] This action only changes this demo session. Nothing is sent to engineering, clients or any backend."

_COPY_HTML = """
<div style="font-family:system-ui,sans-serif">
<button id="b" style="padding:8px 14px;border-radius:8px;border:1px solid #1f5eff;background:#1f5eff;color:#fff;font-size:14px;cursor:pointer">__LABEL__</button>
<span id="m" style="margin-left:10px;font-size:13px;color:#555"></span>
</div>
<script>
const t = __PAYLOAD__;
const b = document.getElementById('b'), m = document.getElementById('m');
function fallback() {
  const a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select();
  let ok = false; try { ok = document.execCommand('copy'); } catch (e) {}
  document.body.removeChild(a); return ok;
}
b.onclick = async () => {
  let ok = false;
  try { await navigator.clipboard.writeText(t); ok = true; } catch (e) { ok = fallback(); }
  m.textContent = ok ? 'Copied to clipboard' : 'Copy blocked by the browser - use the copy icon on the text box above';
};
</script>
"""


def copy_button(text: str, label: str = "Copy summary to clipboard") -> None:
    payload = json.dumps(text).replace("</", "<\\/")
    html = _COPY_HTML.replace("__PAYLOAD__", payload).replace("__LABEL__", label)
    try:
        st.iframe(html, height=56)
    except Exception:  # noqa: BLE001 - older Streamlit
        components.html(html, height=56)


def goto_ticket(ticket_id: str) -> None:
    """on_click callback: open a ticket in the workbench."""
    st.session_state["selected_ticket"] = ticket_id
    st.session_state.pop("wb_pick", None)
    st.session_state["view"] = "Ticket Workbench"


def priority_label(p: str) -> str:
    return f"{PRIORITY_ICON.get(p, '')} {p}"
