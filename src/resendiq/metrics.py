def calculate_metrics(
    packet_count: int,
    events: list,
    received_unique: int,
    simulated_time_ms: float,
    integrity_ok: bool,
    success: bool,
    *,
    receiver_complete: bool | None = None,
    sender_completed: bool | None = None,
) -> dict:
    """Calculate metrics from recorded events.

    ``success`` remains the overall successful-run flag for backwards
    compatibility. Receiver delivery, sender confirmation, and integrity are
    reported separately so an ACK loss cannot be mistaken for data corruption.
    """
    attempts = sum(e.event_type == "DATA_SENT" for e in events)
    retransmissions = sum(e.event_type == "RETRANSMISSION" for e in events)
    ack_attempts = sum(e.event_type in {"ACK_SENT", "ACK_LOST", "ACK_RECEIVED"} for e in events)
    data_losses = sum(e.event_type == "DATA_LOST" for e in events)
    ack_losses = sum(e.event_type == "ACK_LOST" for e in events)
    timeouts = sum(e.event_type == "TIMEOUT" for e in events)
    if receiver_complete is None:
        receiver_complete = received_unique == packet_count
    if sender_completed is None:
        sender_completed = success
    return {
        "original_packets": packet_count,
        "transmission_attempts": attempts,
        "ack_attempts": ack_attempts,
        "delivered_unique_packets": received_unique,
        "data_loss_events": data_losses,
        "ack_loss_events": ack_losses,
        "retransmissions": retransmissions,
        "timeout_events": timeouts,
        "delivery_success_percent": round(received_unique / packet_count * 100, 2) if packet_count else 100.0,
        "retransmission_overhead_percent": round(retransmissions / packet_count * 100, 2) if packet_count else 0.0,
        "simulated_time_ms": round(simulated_time_ms, 2),
        "receiver_complete": "YES" if receiver_complete else "NO",
        "sender_completed": "YES" if sender_completed else "NO",
        "integrity": "PASS" if integrity_ok else "FAIL",
        "completion_status": "SUCCESS" if success else "FAILED",
    }
