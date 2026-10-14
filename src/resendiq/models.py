from dataclasses import dataclass, field
from typing import Any

@dataclass
class Packet:
    packet_id: int
    sequence_number: int
    payload: str

@dataclass
class Ack:
    sequence_number: int
    cumulative: bool = False

@dataclass
class Event:
    time_ms: float
    event_type: str
    message: str
    packet_id: int | None = None
    sequence_number: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

@dataclass
class SimulationConfig:
    packet_loss: float = 0.1
    ack_loss: float = 0.05
    delay_ms: int = 20
    timeout_ms: int = 80
    max_retries: int = 5
    window_size: int = 4
    seed: int = 42

@dataclass
class SimulationResult:
    protocol: str
    success: bool
    packets: list[Packet]
    received: dict[int, str]
    events: list[Event]
    metrics: dict[str, float | int | str]
    original_text: str
    reconstructed_text: str
    integrity_ok: bool
    config: SimulationConfig
