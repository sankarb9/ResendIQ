import math

import pandas as pd
import pytest

from resendiq import bridge
from resendiq.bridge import LinkMeasurement


def test_per_direction_loss_inverts_round_trip():
    for L in (0.0, 0.05, 0.3, 1.0):
        p = bridge.per_direction_loss(L)
        assert 1 - (1 - p) ** 2 == pytest.approx(L)


def test_config_mapping():
    cfg = bridge.config_from_measurement(LinkMeasurement("x", 80.0, 10.0, 5.0), max_retries=7, window_size=3, seed=9)
    assert cfg.delay_ms == 40
    assert cfg.timeout_ms == 100            # 80 + 4*5
    assert cfg.timeout_ms >= 2 * cfg.delay_ms + 1
    assert cfg.packet_loss == cfg.ack_loss == pytest.approx(1 - math.sqrt(0.9))
    assert (cfg.max_retries, cfg.window_size, cfg.seed) == (7, 3, 9)


def test_timeout_never_below_one_rtt_and_delay_at_least_1ms():
    cfg = bridge.config_from_measurement(LinkMeasurement("x", 0.4, 0.0, 0.0))
    assert cfg.delay_ms == 1 and cfg.timeout_ms >= 3


def test_unreachable_location_is_rejected():
    with pytest.raises(ValueError):
        bridge.config_from_measurement(LinkMeasurement("dead", None, 100.0, 0.0))


def test_location_measurements_means_per_location():
    df = pd.DataFrame({"location": ["A", "A", "B"], "avg_ms": [10.0, 30.0, None],
                       "loss_pct": [0.0, 10.0, 100.0], "jitter_ms": [2.0, 4.0, None]})
    got = {m.label: m for m in bridge.location_measurements(df)}
    assert got["A"].avg_ms == 20.0 and got["A"].loss_pct == 5.0 and got["A"].jitter_ms == 3.0
    assert got["B"].avg_ms is None


def test_compare_protocols_clean_link_vs_lossy_link():
    text = "Reliable data transmission over a measured link."
    clean = bridge.compare_protocols(text, bridge.config_from_measurement(LinkMeasurement("c", 20, 0, 1)), trials=10)
    lossy = bridge.compare_protocols(text, bridge.config_from_measurement(LinkMeasurement("l", 20, 40, 1)), trials=10)
    assert list(clean["protocol"]) == ["Stop-and-Wait", "Go-Back-N", "Selective Repeat"]
    assert (clean["mean_retransmissions"] == 0).all() and (clean["success_rate_percent"] == 100).all()
    assert (lossy["mean_retransmissions"] > 0).all()
