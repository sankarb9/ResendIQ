# ResendIQ ARQ Fixes Applied

This update focuses on the ARQ simulator. Wi-Fi modules and features were not redesigned.

## Correctness fixes

1. **Separated payload integrity from sender completion.** A complete payload may be intact at the receiver even if ACK loss prevents the sender from confirming delivery. The SHA-256 integrity result is now calculated independently.
2. **Added separate outcome fields.** Metrics now report receiver completion, sender completion, integrity, and overall completion separately.
3. **Improved Go-Back-N window behavior.** The simulator sends the whole current window, discards out-of-order packets at the receiver, records cumulative ACK progress, and retransmits outstanding packets from the current base.
4. **Improved Selective Repeat tracking.** Packets in a window are attempted independently; ACK state and retries are tracked per packet, and only packets still awaiting ACK are retried.
5. **Added window-size validation.** A zero or negative window size is rejected instead of potentially causing a broken loop or invalid range step.
6. **Updated UI labels and docs.** The interface distinguishes sender completion, receiver completion, and payload integrity.
7. **Added deterministic regression tests** for ACK loss with intact receiver data, GBN handling after a loss inside a window, SR selective retransmission, and invalid window sizes.

## Verification performed

- Python compilation: `python -m compileall -q app.py src views tests` — passed.
- Automated tests: `python -m pytest -q` — 32 passed, 1 skipped.
- Manual protocol checks: zero loss, 100% data loss, and 100% ACK loss were exercised for all three ARQ protocols.

The skipped test is the Streamlit UI smoke test, which requires the Streamlit testing package in the environment. The full Streamlit launch should still be verified on the target Windows machine after installing `requirements.txt`.

## Remaining limitations

- This is an educational event simulation, not a real TCP stack or real packet transmission tool.
- Event timing for Go-Back-N and Selective Repeat is simplified and sequential; it is not cycle-accurate network timing.
- Protocols use non-wrapping sequence numbers.
- Protocol comparison is reproducible by seed but does not force every protocol to experience an identical channel-event trace.
