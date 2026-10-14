import random
from .models import SimulationConfig

class SimulatedChannel:
    """Deterministic channel outcomes from a dedicated RNG; no real network traffic."""
    def __init__(self, config: SimulationConfig):
        if not 0 <= config.packet_loss <= 1 or not 0 <= config.ack_loss <= 1:
            raise ValueError("Loss probabilities must be between 0 and 1.")
        if config.delay_ms < 0 or config.timeout_ms <= 0 or config.max_retries < 0:
            raise ValueError("Delay must be >= 0, timeout > 0, and retries >= 0.")
        if config.window_size < 1:
            raise ValueError("Window size must be at least 1.")
        self.config = config
        self.rng = random.Random(config.seed)

    def data_lost(self) -> bool:
        return self.rng.random() < self.config.packet_loss

    def ack_lost(self) -> bool:
        return self.rng.random() < self.config.ack_loss
