"""Windowed Go-Back-N ARQ teaching simulation (non-wrapping sequence numbers)."""
from ..models import Event, SimulationConfig, SimulationResult
from ..network_channel import SimulatedChannel
from ..metrics import calculate_metrics
from ..integrity import verify_text


def simulate(packets, original_text: str, config: SimulationConfig) -> SimulationResult:
    channel = SimulatedChannel(config)
    events: list[Event] = []
    received: dict[int, str] = {}
    attempts_by_packet = [0] * len(packets)
    now = 0.0
    base = 0
    expected_at_receiver = 0
    n = len(packets)
    retries_without_progress = 0
    sender_completed = True

    while base < n:
        end = min(base + config.window_size, n)
        highest_cumulative_ack = base - 1

        # Send every packet in the current window. The receiver accepts only
        # in-order packets and sends cumulative ACKs for the highest contiguous index.
        for i in range(base, end):
            p = packets[i]
            if attempts_by_packet[i] > 0:
                events.append(Event(now, "RETRANSMISSION", f"Go-Back-N retransmits packet {i}.", p.packet_id, p.sequence_number))
            attempts_by_packet[i] += 1
            events.append(Event(now, "DATA_SENT", f"Sent packet {i} in sender window [{base}, {end - 1}].", p.packet_id, p.sequence_number))
            now += config.delay_ms
            if channel.data_lost():
                events.append(Event(now, "DATA_LOST", f"Packet {i} lost.", p.packet_id, p.sequence_number))
                continue

            if i == expected_at_receiver:
                received[i] = p.payload
                expected_at_receiver += 1
                events.append(Event(now, "DATA_RECEIVED", f"Receiver accepted in-order packet {i}.", p.packet_id, p.sequence_number))
            elif i < expected_at_receiver:
                events.append(Event(now, "DUPLICATE_SUPPRESSED", f"Receiver ignored duplicate packet {i}.", p.packet_id, p.sequence_number))
            else:
                events.append(Event(now, "OUT_OF_ORDER_DISCARDED", f"Receiver discarded out-of-order packet {i}; expected {expected_at_receiver}.", p.packet_id, p.sequence_number))

            # GBN ACKs are cumulative. Out-of-order arrivals cause a duplicate ACK
            # for the last contiguous packet, if one exists.
            ack_index = expected_at_receiver - 1
            now += config.delay_ms
            if channel.ack_lost():
                events.append(Event(now, "ACK_LOST", f"Cumulative ACK through packet {ack_index} was lost.", p.packet_id, ack_index if ack_index >= 0 else None))
            elif ack_index >= 0:
                events.append(Event(now, "ACK_RECEIVED", f"Cumulative ACK through packet {ack_index}.", p.packet_id, ack_index))
                highest_cumulative_ack = max(highest_cumulative_ack, ack_index)

        new_base = max(base, highest_cumulative_ack + 1)
        if new_base >= end:
            base = end
            retries_without_progress = 0
            continue

        # Some packet(s) remain unacknowledged. The oldest outstanding packet's
        # timer expires, so GBN will retry from the current base on the next round.
        now += config.timeout_ms
        events.append(Event(now, "TIMEOUT", f"Window timeout; Go-Back-N retries outstanding packets from {new_base}.",
                            packets[new_base].packet_id, packets[new_base].sequence_number))
        if new_base > base:
            base = new_base
            retries_without_progress = 0
        else:
            retries_without_progress += 1
        if retries_without_progress > config.max_retries:
            sender_completed = False
            events.append(Event(now, "RETRY_LIMIT", "Go-Back-N retry limit reached.", packets[base].packet_id, packets[base].sequence_number))
            break

    reconstructed = "".join(received[i] for i in sorted(received))
    receiver_complete = len(received) == n and all(i in received for i in range(n))
    integrity = receiver_complete and verify_text(original_text, reconstructed)
    overall_success = sender_completed and receiver_complete and integrity
    metrics = calculate_metrics(n, events, len(received), now, integrity, overall_success,
                                 receiver_complete=receiver_complete, sender_completed=sender_completed)
    return SimulationResult("Go-Back-N", overall_success, packets, received, events, metrics,
                            original_text, reconstructed, integrity, config)
