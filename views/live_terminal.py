import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _ui
import streamlit as st

from resendiq import live_runner as lr

_ui.apply()
_ui.hero("🖥️ Live Terminal Mode",
         "Real UDP sockets on localhost with application-layer ARQ. Run it right here, or in two terminals.")

PROTOS = ["Stop-and-Wait", "Go-Back-N", "Selective-Repeat"]
with st.sidebar:
    st.subheader("Live transfer settings")
    protocol = st.selectbox("Protocol", PROTOS, index=2)
    data_loss = st.slider("Data loss (receiver)", 0.0, 0.9, 0.30, 0.05)
    ack_loss = st.slider("ACK loss (sender)", 0.0, 0.9, 0.20, 0.05)
    timeout_ms = st.number_input("Timeout (ms)", 50, 5000, 400, 50)
    window = st.number_input("Window size (GBN/SR)", 1, 16, 4)
    packet_size = st.number_input("Packet size (chars)", 1, 64, 8)
    retries = st.number_input("Max retries", 0, 30, 8)
    seed = st.number_input("Seed", 0, 9_999_999, 42)
    port = st.number_input("UDP port", 1024, 65535, 5005)

message = st.text_input("Message to transmit", "Reliable data transmission using ARQ")
settings = lr.LiveSettings(message=message, protocol=protocol, port=int(port), data_loss=float(data_loss),
                           ack_loss=float(ack_loss), timeout_ms=int(timeout_ms), window_size=int(window),
                           max_retries=int(retries), packet_size=int(packet_size), seed=int(seed))

tab_run, tab_cmd, tab_help = st.tabs(["▶ Run in browser", "⌨ Run in two terminals", "ℹ How it works"])

with tab_run:
    n_packets = -(-len(message) // max(1, int(packet_size)))
    st.caption(f"{len(message)} characters → {n_packets} packet(s). Starts a receiver and a sender subprocess on "
               f"`127.0.0.1:{int(port)}`; loss is deliberately simulated.")
    go = st.button("▶ Start live transfer", type="primary", disabled=not message.strip())
    term = st.empty()

    def render(lines, running=False):
        body = "".join(f'<div class="{lr.classify(l)}">{html.escape(l)}</div>' for l in lines)
        cursor = '<div class="dim">▌</div>' if running else ""
        term.markdown(f'<div class="riq-term"><div>{body}{cursor}</div></div>', unsafe_allow_html=True)

    if go:
        if not lr.port_is_free(int(port)):
            st.error(f"UDP port {int(port)} is busy. Pick another port in the sidebar (or stop the old receiver).")
        else:
            lines: list[str] = []
            render(["[SYSTEM] Starting receiver and sender…"], True)
            for line in lr.run_transfer(settings):
                lines.append(line)
                render(lines[-200:], True)
            render(lines[-200:])
            st.session_state["live_summary"] = lr.parse_summary(lines)
    elif "live_summary" in st.session_state:
        render(st.session_state["live_summary"].lines[-200:])
    else:
        render(["[SYSTEM] Idle. Press “Start live transfer”."])

    sm = st.session_state.get("live_summary")
    if sm:
        ok = sm.integrity == "PASS"
        c = st.columns(5)
        with c[0]: _ui.kpi("Integrity", sm.integrity, "SHA-256 at receiver", "#34d399" if ok else "#f87171")
        with c[1]: _ui.kpi("Packets", sm.packets, f"{sm.total_sends} total sends")
        with c[2]: _ui.kpi("Retransmissions", sm.retransmissions, f"{sm.timeouts} timeout(s)")
        with c[3]: _ui.kpi("Losses injected", sm.data_losses + sm.ack_losses, f"{sm.data_losses} data · {sm.ack_losses} ACK")
        with c[4]: _ui.kpi("Wall-clock", f"{sm.elapsed_s:.2f} s" if sm.elapsed_s is not None else "—", "includes socket waits")
        if sm.reconstructed:
            st.markdown("**Reconstructed at receiver**")
            st.code(sm.reconstructed, language=None)
            if sm.reconstructed != message:
                st.warning("Reconstructed text differs from the original message.")
        st.download_button("⬇ Download log (.txt)", "\n".join(sm.lines), "live_transfer_log.txt")

with tab_cmd:
    st.info("Start the **receiver first**, keep both terminals open, and use the same port in both commands.")
    recv, send = lr.display_commands(settings)
    _ui.step(1, "<b>Terminal 1 — receiver</b> (applies the data loss)")
    st.code(recv, language="powershell")
    _ui.step(2, "<b>Terminal 2 — sender</b> (applies the ACK loss; omit <code>--message</code> to be prompted)")
    st.code(send, language="powershell")
    st.caption("Commands update as you change the sidebar settings. Run from the project folder with your virtual environment active.")

with tab_help:
    cols = st.columns(3)
    with cols[0]:
        _ui.card("Stop-and-Wait", "One packet in flight. Wait for its ACK; on timeout, resend. Simple but slow on lossy links.")
    with cols[1]:
        _ui.card("Go-Back-N", "Sends a window, uses cumulative ACKs. After a timeout every outstanding packet is resent.")
    with cols[2]:
        _ui.card("Selective Repeat", "Per-packet ACKs. Only packets still unacknowledged are retransmitted.")
    st.markdown("")
    st.markdown("- `--data-loss` belongs on the **receiver**; `--ack-loss` belongs on the **sender**.\n"
                "- Default host is `127.0.0.1`, so both processes run on the same machine.\n"
                "- Loss is simulated inside the program; it does not touch other network traffic.\n"
                "- Live mode currently sends text, not files.\n"
                "- Try the same message and seed with each protocol and compare retransmissions.")
