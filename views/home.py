import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _ui
import streamlit as st

_ui.apply()
_ui.hero("📡 ResendIQ", "Measure a real Wi-Fi link, then see how ARQ protocols recover packet loss over it.")

# ---- live status strip (safe if the DB / data is missing) ----
n_loc = n_runs = 0
worst = None
try:
    from resendiq.wifi import db
    db.init()
    sessions = db.load_sessions()
    if not sessions.empty:
        n_loc, n_runs = sessions["location"].nunique(), len(sessions)
        worst = sessions.groupby("location")["score"].mean().sort_values().head(1)
except Exception:  # the overview must never crash
    pass
k1, k2, k3, k4 = st.columns(4)
with k1: _ui.kpi("Locations measured", n_loc, "saved in SQLite")
with k2: _ui.kpi("Measurement runs", n_runs, "ping · DNS · HTTP")
with k3: _ui.kpi("Weakest spot", worst.index[0] if worst is not None else "—",
                 f"mean score {worst.iloc[0]:.0f}/100" if worst is not None else "run a test first",
                 "#f87171" if worst is not None and worst.iloc[0] < 60 else None)
with k4: _ui.kpi("ARQ protocols", 3, "Stop-and-Wait · GBN · SR")

st.markdown("&nbsp;")
st.subheader("How it fits together")
st.markdown("`Wi-Fi Analyzer` → `Measured → ARQ` → `ARQ engines`  ·  and, separately, `Live Terminal` runs the same ideas over real UDP sockets.")

c1, c2 = st.columns(2)
with c1:
    _ui.card("📶 Wi-Fi Analyzer", "Measures RTT, loss, jitter, DNS and HTTP at each location. Scores stability, flags dead zones, "
             "draws a floor-plan heatmap and monitors trends over time.")
with c2:
    _ui.card("🔁 ARQ Simulator", "Simulates data and ACK loss with Stop-and-Wait, Go-Back-N and Selective Repeat. "
             "SHA-256 integrity check, event timeline, CSV/JSON export.")
st.markdown("")
c3, c4 = st.columns(2)
with c3:
    _ui.card("🔗 Measured → ARQ", "Turns a measured location into a channel model and compares the three protocols "
             "over many seeded trials — which one copes best <i>there</i>?")
with c4:
    _ui.card("🖥️ Live Terminal Mode", "Real UDP sender/receiver on localhost. Launch a transfer from the browser and "
             "watch data loss, ACK loss and retransmissions stream live.")

st.markdown("")
st.subheader("Suggested 3-minute demo")
_ui.step(1, "<b>Wi-Fi Analyzer</b> — measure two spots (near the router, far room).")
_ui.step(2, "<b>Measured → ARQ</b> — tick both locations and run the comparison.")
_ui.step(3, "<b>ARQ Simulator</b> — replay one protocol and inspect the packet timeline.")
_ui.step(4, "<b>Live Terminal</b> — run a real UDP transfer with 30% loss and read the log.")

st.caption("Measurements are real (ICMP / DNS / HTTP). ARQ runs are simulated; live mode uses localhost UDP with "
           "deliberately simulated loss. No real traffic is intercepted or altered.")
