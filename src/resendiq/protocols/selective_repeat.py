"""Selective Repeat ARQ teaching simulation with per-packet ACK/retry state."""
from ..models import Event, SimulationConfig, SimulationResult
from ..network_channel import SimulatedChannel
from ..metrics import calculate_metrics
from ..integrity import verify_text


def simulate(packets, original_text: str, config: SimulationConfig) -> SimulationResult:
    channel = SimulatedChannel(config)
    events: list[Event] = []
    received: dict[int, str] = {}
    now = 0.0
    n = len(packets)
    sender_completed = True
    window = config.window_size

    # Each window can have multiple packets received/buffered. ACK state is
    # maintained per packet, so a lost ACK only causes that packet to be retried.
    for start in range(0, n, window):
        end = min(start + window, n)
        pending = set(range(start, end))
        retries = {i: 0 for i in pending}
        while pending:
            exhausted = []
            for i in sorted(pending):
                p = packets[i]
                if retries[i] > 0:
                    events.append(Event(now, "RETRANSMISSION", f"Selective Repeat retransmits only unacknowledged packet {i}.", p.packet_id, p.sequence_number))
                events.append(Event(now, "DATA_SENT", f"Sent packet {i} in Selective Repeat window [{start}, {end - 1}].", p.packet_id, p.sequence_number))
                now += config.delay_ms
                if channel.data_lost():
                    events.append(Event(now, "DATA_LOST", f"Packet {i} lost.", p.packet_id, p.sequence_number))
                    now += config.timeout_ms
                    events.append(Event(now, "TIMEOUT", f"Timeout for packet {i}.", p.packet_id, p.sequence_number))
                else:
                    if i not in received:
                        received[i] = p.payload
                        events.append(Event(now, "DATA_RECEIVED", f"Receiver accepted/buffered packet {i}.", p.packet_id, p.sequence_number))
                    else:
                        events.append(Event(now, "DUPLICATE_SUPPRESSED", f"Receiver ignored duplicate packet {i}.", p.packet_id, p.sequence_number))
                    now += config.delay_ms
                    if channel.ack_lost():
                        events.append(Event(now, "ACK_LOST", f"Individual ACK for packet {i} was lost.", p.packet_id, p.sequence_number))
                        now += config.timeout_ms
                        events.append(Event(now, "TIMEOUT", f"Timeout waiting for ACK {i}.", p.packet_id, p.sequence_number))
                    else:
                        events.append(Event(now, "ACK_RECEIVED", f"Individual ACK received for packet {i}.", p.packet_id, p.sequence_number))
                        pending.discard(i)
                        continue

                retries[i] += 1
                if retries[i] > config.max_retries:
                    exhausted.append(i)
            if exhausted:
                sender_completed = False
                for i in exhausted:
                    p = packets[i]
                    events.append(Event(now, "RETRY_LIMIT", f"Retry limit reached for packet {i}.", p.packet_id, p.sequence_number))
                    pending.discard(i)
                break
        if not sender_completed:
            break

    reconstructed = "".join(received[i] for i in sorted(received))
    receiver_complete = len(received) == n and all(i in received for i in range(n))
    integrity = receiver_complete and verify_text(original_text, reconstructed)
    overall_success = sender_completed and receiver_complete and integrity
    metrics = calculate_metrics(n, events, len(received), now, integrity, overall_success,
                                 receiver_complete=receiver_complete, sender_completed=sender_completed)
    return SimulationResult("Selective Repeat", overall_success, packets, received, events, metrics,
                            original_text, reconstructed, integrity, config)
