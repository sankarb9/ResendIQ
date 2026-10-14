# Test plan and results template

Run: `python -m pytest -v`

| Scenario | Expected behavior | Result |
|---|---|---|
| Empty payload | No packet attempts; integrity passes | Covered by code path; add/verify dedicated test |
| Zero loss | All protocols deliver and verify data | Passed in existing protocol tests |
| Data loss | Retry or report failure at retry limit | Passed in Stop-and-Wait and deterministic GBN/SR tests |
| ACK loss | Receiver avoids duplicate application delivery; integrity separate from sender completion | Passed in new deterministic tests |
| Fixed seed | Channel outcomes repeat | Covered by existing channel tests |
| Invalid probabilities/window size | Configuration rejected | Passed by channel validation tests |
| Export | JSON and CSV are parseable | Covered by existing export tests |

Record actual command output here after testing. Do not mark a scenario as passed without execution.


Latest local verification after the ARQ fixes: `python -m pytest -q` — 32 passed, 1 skipped. The skipped Streamlit smoke tests require the Streamlit testing package; full browser/UI launch should still be verified on the target Windows laptop.

## Live UDP terminal integration check

The live terminal path was manually integration-tested by launching a receiver process and a sender process on a free localhost UDP port for each of Stop-and-Wait, Go-Back-N and Selective Repeat. With simulated data loss (30%) and ACK loss (20%), all three completed a text transfer and the receiver verified the reconstructed message with SHA-256. This process-level test is separate from the default automated pytest suite.

Manual test commands:

```powershell
# Terminal 1
python live_terminal.py receiver --port 5005 --data-loss 0.30 --seed 7

# Terminal 2
python live_terminal.py sender --port 5005 --protocol "Selective-Repeat" --ack-loss 0.20 --timeout-ms 500 --window-size 4 --seed 3
```
