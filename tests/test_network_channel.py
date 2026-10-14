import pytest
from resendiq.models import SimulationConfig
from resendiq.network_channel import SimulatedChannel

def test_seeded_channel_repeats():
    c1, c2 = SimulatedChannel(SimulationConfig(seed=7)), SimulatedChannel(SimulationConfig(seed=7))
    assert [c1.data_lost() for _ in range(10)] == [c2.data_lost() for _ in range(10)]

def test_invalid_probability():
    with pytest.raises(ValueError): SimulatedChannel(SimulationConfig(packet_loss=1.1))


def test_invalid_window_size_rejected():
    import pytest
    from resendiq.models import SimulationConfig
    from resendiq.network_channel import SimulatedChannel

    with pytest.raises(ValueError, match="Window size"):
        SimulatedChannel(SimulationConfig(window_size=0))
