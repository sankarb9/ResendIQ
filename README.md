# ResendIQ

**Wi-Fi Measurement and Packet-Loss Recovery Using ARQ Protocols**

ResendIQ combines two tools in one Streamlit app:

1. **Wi-Fi Analyzer** — measures real RTT, packet loss, jitter, DNS and HTTP behaviour at each location, scores stability, flags potential dead zones, draws a floor-plan heatmap and monitors over time.
2. **ARQ Simulator** — simulates data/ACK loss and recovery with Stop-and-Wait, Go-Back-N and Selective Repeat.
3. **Measured → ARQ (the bridge)** — converts a measured location (or a live probe) into the simulator's channel model and compares the three protocols over many seeded trials. See `docs/integration.md`.

> Safety and scope: Wi-Fi measurements use ordinary ping/DNS/HTTP probes. ARQ losses are simulated in software; the project does not intercept or alter real network traffic.

## Objectives
- Explain how acknowledgements, timeouts, sequence numbers, and retransmissions support reliable delivery.
- Compare three ARQ approaches using calculated event logs and metrics.
- Verify reconstructed text with SHA-256.
- Export experiment results and event logs.

## Technologies
Python 3.11+, Streamlit, Plotly, Pandas, NumPy, Pillow, SQLite (built in), Pytest; no external service is required.

## Windows setup

Open Command Prompt or PowerShell in the directory where you want the project.

```powershell
cd path\to\ResendIQ
py -3 --version
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest -v
streamlit run app.py   # entry point; pages live in views/
```

If `py -3` is unavailable, use `python --version` and `python -m venv .venv`. In PowerShell, if activation is blocked, use Command Prompt activation or run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for the current terminal only.

## Pages
- **Overview**, **Wi-Fi Analyzer** (Run test, Compare locations, Floor plan, Report, Monitor & trends), **ARQ Simulator**, **Measured → ARQ**.
- Wi-Fi measurements are stored in `data/wifi_analyzer.db` (SQLite; a sample with two locations is included).

### ARQ Simulator views
1. **Simulator:** select a protocol, configure loss/delay/timeout/seed, run a text or generated sample, inspect metrics and the event timeline, export CSV/JSON.
2. **Protocol Comparison:** run all protocols with the same text and settings, compare metrics and inspect a selected event log.
3. **Experiment History:** view current-session runs and download summaries.
4. **About ResendIQ:** protocol concepts and glossary.

## Architecture
- `models.py`: packets, ACKs, events, config and results.
- `packet_generator.py`: split text into packets and generate reproducible sample payloads.
- `network_channel.py`: seeded simulated loss outcomes.
- `protocols/`: protocol simulation logic, independent of Streamlit.
- `metrics.py`, `integrity.py`, `exports.py`: calculations, SHA-256 verification and file export.
- `wifi/` (`core.py`, `db.py`, `floorplan.py`): measurement, scoring/classification, SQLite storage, heatmap. Independent of Streamlit.
- `bridge.py`: measurement → `SimulationConfig` mapping and multi-trial protocol comparison.
- `app.py`: entry point using `st.navigation`; `views/`: one script per page (`home`, `wifi_analyzer`, `arq_simulator`, `measured_to_arq`).

## Metrics
- **Transmission attempts:** count of `DATA_SENT` events.
- **Retransmissions:** count of `RETRANSMISSION` events.
- **Data/ACK loss events:** individual simulated loss events, not unique packets.
- **Delivery success:** delivered unique packets / original packets × 100. Empty input is defined as 100%.
- **Retransmission overhead:** retransmission events / original packets × 100. Empty input is defined as 0%.
- **Simulated time:** accumulated configured one-way delays and timeout intervals in this simplified model; it is not real latency.
- **Integrity:** SHA-256 comparison of the complete reconstructed payload against the original. Integrity is not tied to sender completion.
- **Receiver complete:** all original packet IDs arrived at the receiver.
- **Sender completed:** the sender received the required acknowledgements before retry limits were reached.
- **Completion status:** SUCCESS only if sender completion, receiver completion, and integrity all pass.
- **ACK attempts:** ACK outcomes recorded as `ACK_RECEIVED` or `ACK_LOST` events.

## Limitations and assumptions
- Sequence numbers do not wrap around.
- The channel uses a dedicated seeded random generator, but each protocol consumes random outcomes in its own event order; comparison is reproducible but not a perfect shared-channel trace.
- Go-Back-N sends the current window and uses cumulative ACK progress; Selective Repeat tracks pending ACKs per packet within each window. Both are teaching-oriented event models with simplified sequential event timing, not cycle-accurate network stacks.
- The bridge assumes symmetric, independent loss in both directions and symmetric one-way delay; ICMP/DNS/HTTP probes stand in for the data path (see `docs/integration.md`).
- Wi-Fi thresholds and score weights are project-specific, not Wi-Fi standards.
- No real sockets, TCP interception, cloud service, or external API is used for the ARQ part.
- Experiment history lasts for the current Streamlit session; downloads provide local copies.

## Testing
Run `python -m pytest -v`. The included tests exercise packet generation, seeded channel behavior, protocol delivery/recovery, metrics, integrity, and exports. Do not report tests as passing unless the command has actually completed successfully.

## Future enhancements
A stricter discrete-event engine with shared channel-event plans, a step-by-step playback control, byte-oriented file transfer, and separately organized Streamlit page files.

## Live Terminal Mode (real UDP sockets)

Live Terminal Mode sends a real message between two terminal processes on the same laptop using UDP on `127.0.0.1`. The program implements Stop-and-Wait, Go-Back-N and Selective Repeat at the application layer. Packet loss is intentionally simulated by the receiver and ACK loss by the sender, so no system traffic is intercepted or altered.

Open **Terminal 1** in the project directory and start the receiver:

```powershell
python live_terminal.py receiver --port 5005 --data-loss 0.15
```

Open **Terminal 2** in the same project directory and start the sender:

```powershell
python live_terminal.py sender --port 5005 --protocol "Selective-Repeat" --ack-loss 0.10 --timeout-ms 500 --window-size 4
```

The sender prompts for a message. The receiver prints accepted packets and reconstructs the message; both terminals display ARQ events and the receiver reports a SHA-256 integrity result. The receiver exits after one successful transfer. Start it again for another demo.

Available `--protocol` values are `Stop-and-Wait`, `Go-Back-N`, and `Selective-Repeat`. Use `--data-loss 0.30` on the receiver and `--ack-loss 0.20` on the sender to make recovery more visible. Use the same port in both commands. If port 5005 is occupied, select another port for both.

The Streamlit **Live Terminal Mode** page can also run the transfer for you: press **Start live transfer** and it launches the same receiver and sender as subprocesses (`src/resendiq/live_runner.py`), streaming a colour-coded log plus integrity, retransmission and loss counters. A second tab generates copy-paste commands for the two-terminal demo from the sidebar settings. The UDP/ARQ logic itself still lives only in `live_terminal.py`.

## Frontend
Shared styling lives in `views/_ui.py` and `.streamlit/config.toml` (dark theme, KPI cards, status pills, one Plotly template, per-event and per-protocol colours). See `docs/FRONTEND_CHANGES.md`.
