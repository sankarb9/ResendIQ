"""Measured -> ARQ: drive the ARQ simulator with real Wi-Fi measurements."""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
import _ui
from resendiq import bridge
from resendiq.bridge import LinkMeasurement
from resendiq.wifi import core, db

_ui.apply()
_ui.hero("🔗 Measured → ARQ", "Use a measured link (latency, loss, jitter) as the channel, then compare how the three protocols recover over it.")
db.init()
sessions = db.load_sessions()

with st.sidebar:
    st.subheader("Simulation settings")
    text = st.text_area("Payload", "Reliable data transmission over a measured Wi-Fi link.", height=90)
    retries = st.number_input("Max retries per packet/window", 0, 30, 5)
    window = st.number_input("Window size (GBN/SR)", 1, 32, 4)
    trials = st.slider("Trials per protocol (different seeds)", 1, 100, 20)
    seed = st.number_input("Base seed", 0, 9_999_999, 42)

source = st.radio("Measurement source", ["Saved Wi-Fi locations", "Quick live probe", "Manual entry"], horizontal=True)
measurements: list[LinkMeasurement] = []

if source == "Saved Wi-Fi locations":
    if sessions.empty:
        st.info("No saved measurements yet. Run tests on the **Wi-Fi Analyzer** page first.")
    else:
        all_m = {m.label: m for m in bridge.location_measurements(sessions)}
        picked = st.multiselect("Locations", sorted(all_m), default=sorted(all_m))
        measurements = [all_m[p] for p in picked]
elif source == "Quick live probe":
    c1, c2, c3 = st.columns(3)
    secs = c1.slider("Probe length (s)", 5, 60, 10)
    gw = c2.text_input("Gateway", core.get_default_gateway() or "")
    ext = c3.text_input("External target", "8.8.8.8")
    if st.button("▶ Probe now", type="primary"):
        targets = ({"gateway": gw.strip()} if gw.strip() else {}) | ({"external": ext.strip()} if ext.strip() else {})
        if not targets:
            st.error("Enter a gateway or an external target.")
        else:
            bar = st.progress(0.0, text="Probing…")
            res = core.evaluate(core.run_session(targets, secs, 0.5, lambda p: bar.progress(p)))
            bar.empty()
            p = res["primary"]
            st.session_state["probe"] = LinkMeasurement(f"Live probe ({res['basis']})", p["avg"], p["loss"], p["jitter"] or 0.0)
    if "probe" in st.session_state:
        measurements = [st.session_state["probe"]]
else:
    a, b, c = st.columns(3)
    measurements = [LinkMeasurement("Manual", a.number_input("Avg RTT (ms)", 1.0, 5000.0, 40.0),
                                    b.number_input("Round-trip loss (%)", 0.0, 100.0, 5.0),
                                    c.number_input("Jitter (ms)", 0.0, 1000.0, 10.0))]

if measurements:
    rows, configs = [], {}
    for m in measurements:
        try:
            cfg = bridge.config_from_measurement(m, max_retries=int(retries), window_size=int(window), seed=int(seed))
        except ValueError as exc:
            st.warning(str(exc))
            continue
        configs[m.label] = cfg
        rows.append({"location": m.label, "avg RTT (ms)": round(m.avg_ms, 1), "RT loss (%)": round(m.loss_pct, 1),
                     "jitter (ms)": round(m.jitter_ms, 1), "→ data loss": round(cfg.packet_loss, 3),
                     "→ ACK loss": round(cfg.ack_loss, 3), "→ one-way delay (ms)": cfg.delay_ms,
                     "→ timeout (ms)": cfg.timeout_ms})
    if rows:
        st.subheader("Derived channel model")
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption("Ping loss is round-trip, so per-direction loss p = 1 − √(1 − L). One-way delay = RTT/2. "
                   "Timeout = RTT + 4 × jitter (never below one RTT).")
        if st.button("▶ Run ARQ comparison", type="primary"):
            frames = []
            for label, cfg in configs.items():
                f = bridge.compare_protocols(text, cfg, trials)
                f.insert(0, "location", label)
                frames.append(f)
            st.session_state["bridge_result"] = pd.concat(frames, ignore_index=True)
        res = st.session_state.get("bridge_result")
        if res is not None and not res.empty:
            st.subheader(f"Protocol comparison (mean over {int(res['trials'].iloc[0])} trials)")
            st.dataframe(res, width="stretch", hide_index=True)
            for metric, title in [("mean_simulated_time_ms", "Mean simulated completion time (ms)"),
                                  ("mean_retransmissions", "Mean retransmissions"),
                                  ("success_rate_percent", "Success rate (%)")]:
                st.plotly_chart(px.bar(res, x="location", y=metric, color="protocol", barmode="group", title=title,
                                       color_discrete_map=_ui.PROTOCOL_COLORS),
                                width="stretch")
            st.download_button("⬇ Results (.csv)", res.to_csv(index=False), "measured_to_arq.csv", "text/csv")
        st.caption("Limits: symmetric, independent loss assumed; ICMP/DNS/HTTP probes stand in for the data path; "
                   "the ARQ run is a simplified event simulation, not TCP and not real traffic.")
