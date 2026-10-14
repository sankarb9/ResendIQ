# 3-minute demonstration script

1. Introduce ResendIQ as an educational simulator for reliable transmission using ARQ.
2. In the Simulator page, set packet loss to 0 and run a short text with Stop-and-Wait. Point out delivery, integrity, metrics, and event timeline.
3. Increase data loss or ACK loss and run again. Explain the timeout and retransmission events.
4. Change to Go-Back-N and Selective Repeat. Explain window-based sending and their different retry behavior.
5. Open Protocol Comparison, run the same payload and seed, and compare the computed metrics.
6. Open Experiment History and download a CSV or JSON result.
7. Conclude that all packet and ACK losses are simulated and no real network traffic is intercepted.

## Optional live terminal demo
1. Open two terminals in the project folder and activate the same virtual environment in each.
2. In Terminal 1 run: `python live_terminal.py receiver --port 5005 --data-loss 0.30`.
3. In Terminal 2 run: `python live_terminal.py sender --port 5005 --protocol "Selective-Repeat" --ack-loss 0.20 --timeout-ms 500 --window-size 4`.
4. Enter a short message. Point out data loss, ACK loss, individual ACKs, selective retransmissions, reconstruction and SHA-256 integrity.
5. Restart the receiver and repeat with `Stop-and-Wait` and `Go-Back-N` to compare behavior.
6. Explain that UDP carries the datagrams; ResendIQ's own application-layer ARQ code provides acknowledgements and recovery. Loss is deliberately simulated in this educational demo.
