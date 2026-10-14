from resendiq.models import SimulationConfig
from resendiq.packet_generator import split_text
from resendiq.protocols.go_back_n import simulate

def test_no_loss_delivers():
    text = "abcdefghijkl"
    r = simulate(split_text(text, 4), text, SimulationConfig(packet_loss=0, ack_loss=0, window_size=2))
    assert r.success and r.reconstructed_text == text


def test_window_continues_sending_after_a_packet_is_lost(monkeypatch):
    from resendiq.network_channel import SimulatedChannel

    data_outcomes = iter([False, True, False, False, False])
    monkeypatch.setattr(SimulatedChannel, "data_lost", lambda self: next(data_outcomes, False))
    monkeypatch.setattr(SimulatedChannel, "ack_lost", lambda self: False)
    text = "abcdefghijkl"
    r = simulate(split_text(text, 4), text,
                 SimulationConfig(packet_loss=0, ack_loss=0, window_size=3, max_retries=3))
    assert r.success
    assert r.reconstructed_text == text
    assert any(e.event_type == "OUT_OF_ORDER_DISCARDED" for e in r.events)
    assert r.metrics["retransmissions"] >= 2


def test_receiver_integrity_is_separate_from_sender_completion(monkeypatch):
    from resendiq.network_channel import SimulatedChannel

    monkeypatch.setattr(SimulatedChannel, "data_lost", lambda self: False)
    monkeypatch.setattr(SimulatedChannel, "ack_lost", lambda self: True)
    text = "data"
    r = simulate(split_text(text, 4), text,
                 SimulationConfig(packet_loss=0, ack_loss=1, window_size=1, max_retries=0))
    assert not r.success
    assert r.integrity_ok
    assert r.metrics["receiver_complete"] == "YES"
    assert r.metrics["sender_completed"] == "NO"
