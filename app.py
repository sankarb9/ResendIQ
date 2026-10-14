"""ResendIQ — measure a Wi-Fi link, then simulate how ARQ protocols recover over it.

Run:  streamlit run app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "views"))
import _ui

st.set_page_config(page_title="ResendIQ", page_icon="📡", layout="wide")

pages = [
    st.Page("views/home.py", title="Overview", icon="🏠", default=True),
    st.Page("views/wifi_analyzer.py", title="Wi-Fi Analyzer", icon="📶"),
    st.Page("views/arq_simulator.py", title="ARQ Simulator", icon="🔁"),
    st.Page("views/live_terminal.py", title="Live Terminal Mode", icon="🖥️"),
    st.Page("views/measured_to_arq.py", title="Measured → ARQ", icon="🔗"),
]
_ui.apply()
with st.sidebar:
    st.markdown("### 📡 ResendIQ")
    st.caption("Measure the link. Simulate the recovery.")
st.navigation(pages).run()
