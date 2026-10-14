# Architecture

The UI calls protocol functions and renders their `SimulationResult`. Protocol code depends on models, the simulated channel, metrics, and integrity helpers—not Streamlit.

```text
Streamlit UI
    |
    v
Protocol simulation ---> SimulatedChannel (seeded RNG)
    |                         |
    v                         v
Events + receiver data <--- simulated loss outcomes
    |
    +--> Metrics
    +--> SHA-256 integrity
    +--> CSV / JSON exports
```

Sequence numbers are non-wrapping integers equal to packet indexes. This avoids wraparound ambiguity in the prototype. The channel simulates data and ACK loss independently. Timing is approximate educational time, not measured network latency.

## Merged system
```text
Wi-Fi Analyzer page --> wifi/core.py (ping, DNS, HTTP, score) --> wifi/db.py (SQLite)
                                                                   |
Measured -> ARQ page --> bridge.py (measurement -> SimulationConfig)
                                   |
                                   v
                         protocols/* + SimulatedChannel --> metrics, integrity, exports
```
