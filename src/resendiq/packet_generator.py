from .models import Packet

def split_text(text: str, payload_size: int = 8) -> list[Packet]:
    if payload_size < 1:
        raise ValueError("Payload size must be at least 1.")
    return [Packet(i, i, text[start:start + payload_size])
            for i, start in enumerate(range(0, len(text), payload_size))]

def generate_sample(packet_count: int, payload_size: int = 8) -> str:
    if packet_count < 0 or payload_size < 1:
        raise ValueError("Packet count must be non-negative and payload size positive.")
    return "".join(chr(65 + (i % 26)) * payload_size for i in range(packet_count))
