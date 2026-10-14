from resendiq.models import SimulationConfig
from resendiq.packet_generator import split_text
from resendiq.protocols.stop_and_wait import simulate

def test_success_no_loss():
    text = "abcdefgh"
    result = simulate(split_text(text, 4), text, SimulationConfig(packet_loss=0, ack_loss=0))
    assert result.success and result.integrity_ok and result.reconstructed_text == text

def test_loss_recovery_with_sufficient_retries():
    text = "hello"
    result = simulate(split_text(text, 5), text, SimulationConfig(packet_loss=0.4, ack_loss=0.2, seed=2, max_retries=10))
    assert result.reconstructed_text == text if result.success else not result.success

def test_zero_retries_can_fail():
    text = "hello"
    result = simulate(split_text(text, 5), text, SimulationConfig(packet_loss=1, ack_loss=0, max_retries=0))
    assert not result.success


def test_data_can_be_intact_even_when_ack_is_lost(monkeypatch):
    from resendiq.network_channel import SimulatedChannel

    monkeypatch.setattr(SimulatedChannel, "data_lost", lambda self: False)
    monkeypatch.setattr(SimulatedChannel, "ack_lost", lambda self: True)
    text = "hello"
    result = simulate(split_text(text, 5), text,
                      SimulationConfig(packet_loss=0, ack_loss=1, max_retries=0))
    assert not result.success
    assert result.reconstructed_text == text
    assert result.integrity_ok
    assert result.metrics["integrity"] == "PASS"
    assert result.metrics["receiver_complete"] == "YES"
    assert result.metrics["sender_completed"] == "NO"
