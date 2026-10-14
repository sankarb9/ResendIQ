from ..models import Event, SimulationConfig, SimulationResult
from ..network_channel import SimulatedChannel
from ..metrics import calculate_metrics
from ..integrity import verify_text


def simulate(packets, original_text: str, config: SimulationConfig) -> SimulationResult:
    channel = SimulatedChannel(config)
    events: list[Event] = []
    received: dict[int, str] = {}
    now = 0.0
    sender_completed = True

    for packet in packets:
        acked = False
        retries = 0
        while not acked:
            if retries:
                events.append(Event(now, "RETRANSMISSION", f"Retransmitting packet {packet.packet_id} after missing ACK/timeout.", packet.packet_id, packet.sequence_number))
            events.append(Event(now, "DATA_SENT", f"Sent packet {packet.packet_id}.", packet.packet_id, packet.sequence_number))
            now += config.delay_ms
            if channel.data_lost():
                events.append(Event(now, "DATA_LOST", f"Packet {packet.packet_id} lost in simulated channel.", packet.packet_id, packet.sequence_number))
                now += config.timeout_ms
                events.append(Event(now, "TIMEOUT", f"Timeout waiting for ACK for packet {packet.packet_id}.", packet.packet_id, packet.sequence_number))
            else:
                if packet.packet_id not in received:
                    received[packet.packet_id] = packet.payload
                    events.append(Event(now, "DATA_RECEIVED", f"Receiver accepted packet {packet.packet_id}.", packet.packet_id, packet.sequence_number))
                else:
                    events.append(Event(now, "DUPLICATE_SUPPRESSED", f"Duplicate packet {packet.packet_id} ignored.", packet.packet_id, packet.sequence_number))
                now += config.delay_ms
                if channel.ack_lost():
                    events.append(Event(now, "ACK_LOST", f"ACK for packet {packet.packet_id} was lost.", packet.packet_id, packet.sequence_number))
                    now += config.timeout_ms
                    events.append(Event(now, "TIMEOUT", f"Timeout waiting for ACK for packet {packet.packet_id}.", packet.packet_id, packet.sequence_number))
                else:
                    events.append(Event(now, "ACK_RECEIVED", f"ACK received for packet {packet.packet_id}.", packet.packet_id, packet.sequence_number))
                    acked = True
            if not acked:
                retries += 1
                if retries > config.max_retries:
                    sender_completed = False
                    events.append(Event(now, "RETRY_LIMIT", f"Retry limit reached for packet {packet.packet_id}.", packet.packet_id, packet.sequence_number))
                    break
        if not sender_completed:
            break

    reconstructed = "".join(received[i] for i in sorted(received))
    receiver_complete = len(received) == len(packets) and all(i in received for i in range(len(packets)))
    integrity = receiver_complete and verify_text(original_text, reconstructed)
    overall_success = sender_completed and receiver_complete and integrity
    metrics = calculate_metrics(len(packets), events, len(received), now, integrity, overall_success,
                                 receiver_complete=receiver_complete, sender_completed=sender_completed)
    return SimulationResult("Stop-and-Wait", overall_success, packets, received, events, metrics,
                            original_text, reconstructed, integrity, config)
