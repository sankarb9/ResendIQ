import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _ui
import pandas as pd
import plotly.express as px
import streamlit as st

from resendiq.exports import export_events_csv, export_json, safe_filename
from resendiq.models import SimulationConfig
from resendiq.packet_generator import generate_sample, split_text
from resendiq.protocols import go_back_n, selective_repeat, stop_and_wait

_ui.apply()
_ui.hero("🔁 ARQ Recovery Simulator",
         "Watch Stop-and-Wait, Go-Back-N and Selective Repeat recover from simulated data and ACK loss.")
PROTOS = ["Stop-and-Wait", "Go-Back-N", "Selective Repeat"]
ENGINES = {"Stop-and-Wait": stop_and_wait.simulate, "Go-Back-N": go_back_n.simulate,
           "Selective Repeat": selective_repeat.simulate}
st.session_state.setdefault("history", [])
st.session_state.setdefault("last_result", None)


def settings() -> SimulationConfig:
    with st.sidebar:
        st.subheader("Network settings")
        preset = st.selectbox("Quick preset", ["Custom", "Clean link", "Typical Wi-Fi", "Weak signal", "Near dead zone"])
        presets = {"Clean link": (0.0, 0.0, 10, 40), "Typical Wi-Fi": (0.05, 0.03, 20, 80),
                   "Weak signal": (0.25, 0.15, 40, 150), "Near dead zone": (0.5, 0.35, 80, 300)}
        pl0, al0, d0, t0 = presets.get(preset, (0.10, 0.05, 20, 80))
        key = preset.replace(" ", "_")  # new keys per preset so widgets adopt preset values
        packet_loss = st.slider("Data packet loss", 0.0, 1.0, pl0, 0.05, key=f"pl_{key}")
        ack_loss = st.slider("ACK loss", 0.0, 1.0, al0, 0.05, key=f"al_{key}")
        delay = st.number_input("One-way delay (ms)", 0, 10000, d0, key=f"d_{key}")
        timeout = st.number_input("Timeout (ms)", 1, 60000, t0, key=f"t_{key}")
        retries = st.number_input("Max retries per packet/window", 0, 30, 5)
        window = st.number_input("Window size (GBN/SR)", 1, 32, 4)
        seed = st.number_input("Random seed", 0, 9999999, 42)
    return SimulationConfig(packet_loss, ack_loss, int(delay), int(timeout), int(retries), int(window), int(seed))


def run(protocol, text, config):
    result = ENGINES[protocol](split_text(text, payload_size=8), text, config)
    st.session_state.last_result = result
    st.session_state.history.insert(0, result)
    return result


def events_frame(result) -> pd.DataFrame:
    return pd.DataFrame([{"time_ms": e.time_ms, "event": e.event_type, "packet": e.packet_id, "message": e.message}
                         for e in result.events])


def timeline_chart(df: pd.DataFrame):
    d = df.dropna(subset=["packet"]).copy()
    d["packet"] = d["packet"].astype(int)
    fig = px.scatter(d, x="time_ms", y="packet", color="event", color_discrete_map=_ui.EVENT_COLORS,
                     hover_data=["message"], title="Packet timeline — one row per packet")
    fig.update_traces(marker={"size": 11, "line": {"width": 1, "color": "#0b1220"}})
    fig.update_yaxes(dtick=1, title="packet #", autorange="reversed")
    fig.update_xaxes(title="simulated time (ms)")
    fig.update_layout(height=420, legend_title_text="")
    return fig


def result_view(result):
    m = result.metrics
    ok = m["completion_status"] == "SUCCESS"
    c = st.columns(5)
    with c[0]: _ui.kpi("Completion", m["completion_status"], f"{result.protocol}", "#34d399" if ok else "#f87171")
    with c[1]: _ui.kpi("Delivery", f"{m['delivery_success_percent']}%", f"{m['delivered_unique_packets']} of {m['original_packets']} packets")
    with c[2]: _ui.kpi("Retransmissions", m["retransmissions"], f"{m['retransmission_overhead_percent']}% overhead")
    with c[3]: _ui.kpi("Losses", m["data_loss_events"] + m["ack_loss_events"], f"{m['data_loss_events']} data · {m['ack_loss_events']} ACK")
    with c[4]: _ui.kpi("Simulated time", f"{m['simulated_time_ms']} ms", f"{m['timeout_events']} timeout(s)")
    st.markdown("")
    p = st.columns(3)
    for col, (label, val, good) in zip(p, [("Receiver complete", m["receiver_complete"], "YES"),
                                           ("Sender confirmed", m["sender_completed"], "YES"),
                                           ("SHA-256 integrity", "PASS" if result.integrity_ok else "FAIL", "PASS")]):
        col.markdown(f"**{label}** &nbsp; {_ui.pill(str(val), '#34d399' if str(val) == good else '#f87171')}",
                     unsafe_allow_html=True)
    st.caption("Receiver delivery, sender acknowledgement and payload integrity are reported separately. "
               "Simulated time is not real network latency.")
    df = events_frame(result)
    t1, t2, t3 = st.tabs(["Packet timeline", "Event log", "Reconstructed text"])
    with t1:
        if df.dropna(subset=["packet"]).empty:
            st.info("No packet events to plot.")
        else:
            st.plotly_chart(timeline_chart(df), width="stretch")
    with t2:
        kinds = sorted(df["event"].unique()) if not df.empty else []
        chosen = st.multiselect("Filter events", kinds, default=kinds)
        st.dataframe(df[df["event"].isin(chosen)] if not df.empty else df, width="stretch", hide_index=True)
    with t3:
        st.code(result.reconstructed_text or "(empty)", language=None)
    stem = safe_filename(result.protocol)
    d1, d2, _ = st.columns([1, 1, 3])
    d1.download_button("⬇ Event log (CSV)", export_events_csv(result), f"{stem}_events.csv", "text/csv")
    d2.download_button("⬇ Experiment (JSON)", export_json(result), f"{stem}_experiment.json", "application/json")


config = settings()
tab_sim, tab_cmp, tab_hist, tab_about = st.tabs(["Simulator", "Protocol Comparison", "Experiment History", "About"])

with tab_sim:
    left, right = st.columns([2, 3])
    with left:
        protocol = st.radio("ARQ protocol", PROTOS, horizontal=True)
        mode = st.radio("Payload", ["Enter text", "Generate sample"], horizontal=True)
        if mode == "Enter text":
            sample = st.text_area("Text to transmit", "Reliable data transmission with ResendIQ.", height=100)
        else:
            sample = generate_sample(st.slider("Number of packets", 1, 30, 6), 8)
            st.code(sample, language=None)
        packets_n = len(split_text(sample, payload_size=8)) if sample else 0
        st.caption(f"{len(sample)} characters → {packets_n} packet(s) of 8 characters")
        go = st.button("▶ Run simulation", type="primary", disabled=not sample)
    with right:
        st.markdown("**Current channel**")
        k = st.columns(4)
        with k[0]: _ui.kpi("Data loss", f"{config.packet_loss:.0%}")
        with k[1]: _ui.kpi("ACK loss", f"{config.ack_loss:.0%}")
        with k[2]: _ui.kpi("One-way delay", f"{config.delay_ms} ms")
        with k[3]: _ui.kpi("Timeout", f"{config.timeout_ms} ms")
    if go:
        try:
            r = run(protocol, sample, config)
            (st.success if r.success else st.warning)(
                "Sender confirmed complete delivery." if r.success else "Sender did not confirm completion within the retry limit.")
        except ValueError as exc:
            st.error(str(exc))
    if st.session_state.last_result:
        result_view(st.session_state.last_result)
    else:
        st.info("Pick a protocol and press **Run simulation**. Try the *Weak signal* preset in the sidebar.")

with tab_cmp:
    text = st.text_area("Shared payload", "Compare reliable transmission across ARQ protocols.", height=90, key="cmp_text")
    if st.button("▶ Run comparison", type="primary", disabled=not text):
        try:
            st.session_state.comparison = [run(n, text, config) for n in PROTOS]
        except ValueError as exc:
            st.error(str(exc))
    if st.session_state.get("comparison"):
        res = st.session_state.comparison
        frame = pd.DataFrame([{"Protocol": r.protocol, **r.metrics} for r in res])
        best = min(res, key=lambda r: (not r.success, r.metrics["retransmissions"], r.metrics["simulated_time_ms"]))
        st.success(f"Fewest retransmissions among completed runs: **{best.protocol}** "
                   f"({best.metrics['retransmissions']} retransmissions, {best.metrics['simulated_time_ms']} ms). "
                   "One seed = one random outcome; use *Measured → ARQ* for multi-trial averages.")
        cols = st.columns(3)
        for col, (metric, title) in zip(cols, [("retransmissions", "Retransmissions"),
                                               ("simulated_time_ms", "Simulated time (ms)"),
                                               ("delivery_success_percent", "Delivery (%)")]):
            fig = px.bar(frame, x="Protocol", y=metric, color="Protocol", color_discrete_map=_ui.PROTOCOL_COLORS, title=title)
            fig.update_layout(showlegend=False, height=300, xaxis_title=None, yaxis_title=None)
            col.plotly_chart(fig, width="stretch")
        with st.expander("All metrics"):
            st.dataframe(frame, width="stretch", hide_index=True)
        chosen = st.selectbox("Inspect event log", [r.protocol for r in res])
        sel = next(r for r in res if r.protocol == chosen)
        st.plotly_chart(timeline_chart(events_frame(sel)), width="stretch")

with tab_hist:
    history = st.session_state.history
    if not history:
        st.info("No experiments yet. Run a simulation first.")
    else:
        frame = pd.DataFrame([{"protocol": r.protocol, **r.metrics, "seed": r.config.seed,
                               "packet_loss": r.config.packet_loss, "ack_loss": r.config.ack_loss} for r in history])
        st.dataframe(frame, width="stretch", hide_index=True)
        a, b, c = st.columns([1, 1, 4])
        a.download_button("⬇ History (CSV)", frame.to_csv(index=False), "resendiq_history.csv", "text/csv")
        b.download_button("⬇ History (JSON)", json.dumps([{"protocol": r.protocol, "metrics": r.metrics, "seed": r.config.seed}
                                                       for r in history], indent=2), "resendiq_history.json", "application/json")
        if c.button("🗑 Clear history"):
            st.session_state.history, st.session_state.last_result = [], None
            st.session_state.pop("comparison", None)
            st.rerun()

with tab_about:
    cols = st.columns(3)
    with cols[0]:
        _ui.card("Stop-and-Wait", "Send one packet, wait for its ACK. Easy to reason about, but the link idles during every round trip.")
    with cols[1]:
        _ui.card("Go-Back-N", "Send a window. The receiver only accepts in order, so after a loss the sender resends from the missing packet onward.")
    with cols[2]:
        _ui.card("Selective Repeat", "Each packet is ACKed individually and only unacknowledged packets are resent.")
    st.markdown("")
    st.markdown("""
- **ARQ** — Automatic Repeat reQuest: ACKs from the receiver; retransmission by the sender when needed.
- **Sequence number** — identifies packets and detects duplicates. **Timeout** — wait limit before a retry.
- **Integrity** — SHA-256 of the reconstructed payload compared with the original.

This is a simplified educational event simulation, not TCP: non-wrapping sequence numbers and approximate window timing.
""")
