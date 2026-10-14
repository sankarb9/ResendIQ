"""Bridge: turn Wi-Fi measurements (RTT, loss, jitter) into an ARQ SimulationConfig.

Mapping (all assumptions are stated so they can be justified in the report):
  * Ping loss is ROUND-TRIP loss L. If data and ACK directions lose packets independently
    with the same probability p, then L = 1 - (1 - p)^2, so p = 1 - sqrt(1 - L).
  * One-way delay = avg RTT / 2 (symmetric path).
  * Timeout follows the classic RTO idea: avg RTT + 4 x jitter, never below one RTT.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

import pandas as pd

from .models import SimulationConfig
from .packet_generator import split_text
from .protocols import go_back_n, selective_repeat, stop_and_wait

PROTOCOLS = {
    "Stop-and-Wait": stop_and_wait.simulate,
    "Go-Back-N": go_back_n.simulate,
    "Selective Repeat": selective_repeat.simulate,
}


@dataclass(frozen=True)
class LinkMeasurement:
    label: str
    avg_ms: float | None
    loss_pct: float
    jitter_ms: float


def per_direction_loss(round_trip_loss: float) -> float:
    """Round-trip loss fraction (0-1) -> per-direction loss fraction, assuming symmetric independent loss."""
    L = min(max(float(round_trip_loss), 0.0), 1.0)
    return 1.0 - math.sqrt(1.0 - L)


def config_from_measurement(m: LinkMeasurement, *, max_retries: int = 5, window_size: int = 4,
                            seed: int = 42) -> SimulationConfig:
    if m.avg_ms is None or m.avg_ms != m.avg_ms:
        raise ValueError(f"'{m.label}' has no RTT (no replies received), so a delay cannot be derived.")
    jitter = 0.0 if m.jitter_ms is None or m.jitter_ms != m.jitter_ms else float(m.jitter_ms)
    delay = max(1, round(m.avg_ms / 2))
    timeout = max(2 * delay + 1, math.ceil(m.avg_ms + 4 * jitter))
    p = per_direction_loss(m.loss_pct / 100.0)
    return SimulationConfig(packet_loss=p, ack_loss=p, delay_ms=int(delay), timeout_ms=int(timeout),
                            max_retries=int(max_retries), window_size=int(window_size), seed=int(seed))


def location_measurements(sessions: pd.DataFrame) -> list[LinkMeasurement]:
    """Mean RTT / loss / jitter per location from the Wi-Fi analyzer's saved sessions."""
    out = []
    for loc, g in sessions.groupby("location"):
        avg = g["avg_ms"].mean()
        out.append(LinkMeasurement(str(loc), None if pd.isna(avg) else float(avg),
                                   float(g["loss_pct"].mean()), float(g["jitter_ms"].fillna(0).mean())))
    return out


def compare_protocols(text: str, config: SimulationConfig, trials: int = 20) -> pd.DataFrame:
    """Run every protocol `trials` times (seeds config.seed .. config.seed+trials-1) and average."""
    packets = split_text(text, payload_size=8)
    rows = []
    for name, simulate in PROTOCOLS.items():
        results = [simulate(packets, text, replace(config, seed=config.seed + i)) for i in range(trials)]
        n = len(results)
        rows.append({
            "protocol": name,
            "trials": n,
            "success_rate_percent": round(100 * sum(r.success for r in results) / n, 1),
            "mean_retransmissions": round(sum(r.metrics["retransmissions"] for r in results) / n, 2),
            "mean_timeouts": round(sum(r.metrics["timeout_events"] for r in results) / n, 2),
            "mean_simulated_time_ms": round(sum(r.metrics["simulated_time_ms"] for r in results) / n, 1),
        })
    return pd.DataFrame(rows)
