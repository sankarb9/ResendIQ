from resendiq.metrics import calculate_metrics

def test_zero_packet_metrics_safe():
    m = calculate_metrics(0, [], 0, 0, True, True)
    assert m["delivery_success_percent"] == 100.0
    assert m["retransmission_overhead_percent"] == 0.0
