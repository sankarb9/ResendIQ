from resendiq import live_runner as lr


def test_parse_summary_extracts_counts():
    lines = [
        "[RECEIVER] ✗ Simulated DATA LOSS for packet #1; no ACK sent.",
        "[SENDER] ✗ Simulated ACK LOSS for ACK #0; sender ignores it.",
        "[SENDER] ⌛ Timeout; Selective Repeat retransmits only unacknowledged packets [1].",
        "[RECEIVER] ========== MESSAGE RECONSTRUCTED ==========",
        "[RECEIVER] hello world",
        "[RECEIVER] SHA-256 integrity: PASS",
        "[SENDER] Data packets: 2; total sends: 4; retransmissions: 2",
        "[SENDER] Elapsed wall-clock time: 1.250 s (includes real socket waits)",
    ]
    s = lr.parse_summary(lines)
    assert (s.data_losses, s.ack_losses, s.timeouts) == (1, 1, 1)
    assert (s.packets, s.total_sends, s.retransmissions) == (2, 4, 2)
    assert s.reconstructed == "hello world" and s.integrity == "PASS" and s.elapsed_s == 1.25


def test_commands_use_the_chosen_settings():
    s = lr.LiveSettings(port=6001, protocol="Go-Back-N", data_loss=0.3)
    recv, send = lr.display_commands(s)
    assert "--port 6001" in recv and "--data-loss 0.3" in recv
    assert '"Go-Back-N"' in send


def test_end_to_end_lossless_transfer():
    port = 5977
    assert lr.port_is_free(port)
    s = lr.LiveSettings(message="hi there!", protocol="Stop-and-Wait", port=port, data_loss=0.0, ack_loss=0.0,
                        timeout_ms=300)
    summary = lr.parse_summary(list(lr.run_transfer(s, overall_timeout=30)))
    assert summary.integrity == "PASS" and summary.reconstructed == "hi there!"
