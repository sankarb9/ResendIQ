# Integration: Wi-Fi Analyzer -> ARQ Simulator

## Idea
The analyzer answers *"how bad is the link here?"*; the simulator answers *"how do ARQ protocols cope with a link like that?"*.
`resendiq/bridge.py` connects them so a measured location becomes the simulated channel.

## Mapping (measured -> simulated)
| Measured (per location, mean of saved runs) | Simulator field | Rule |
| --- | --- | --- |
| Round-trip loss L (ping) | `packet_loss`, `ack_loss` | p = 1 - sqrt(1 - L), same p each direction (since L = 1 - (1-p)^2) |
| Avg RTT | `delay_ms` | RTT / 2 (min 1 ms) |
| Avg RTT, jitter | `timeout_ms` | ceil(RTT + 4 x jitter), never below 2 x delay + 1 |
| (user choice) | `max_retries`, `window_size`, `seed` | set in the sidebar |

A location with no replies has no RTT, so no delay can be derived; the page reports it instead of guessing.

## Why many trials
One seed gives one random outcome. `compare_protocols` runs each protocol for `trials` consecutive seeds and reports means
(retransmissions, timeouts, simulated time) and success rate, so protocol differences are not seed luck.

## Assumptions to state in the report
- Loss is independent and symmetric between data and ACK directions.
- Delay is symmetric (RTT/2) and constant; jitter only widens the timeout.
- ICMP/DNS/HTTP measurements represent the path used by the simulated transfer.
- The ARQ models are simplified teaching simulations (non-wrapping sequence numbers, approximate window timing), not TCP.

## Quick demo
1. Wi-Fi Analyzer: measure two locations (e.g. near the router and in a far room).
2. Measured -> ARQ: tick both, run the comparison, show how simulated completion time and retransmissions grow at the weaker spot.
