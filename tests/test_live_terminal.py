from live_terminal import PROTOCOLS, wire_read


def test_live_terminal_protocol_choices_are_available():
    assert PROTOCOLS == ("Stop-and-Wait", "Go-Back-N", "Selective-Repeat")


def test_live_terminal_wire_reader_handles_unicode_json():
    message = '{"type":"DATA","seq":2,"payload":"Hello 🌐"}'
    parsed = wire_read(message.encode("utf-8"))
    assert parsed == {"type": "DATA", "seq": 2, "payload": "Hello 🌐"}


def test_live_terminal_wire_reader_rejects_malformed_payload():
    assert wire_read(b"not-json") is None


def test_say_survives_a_console_that_cannot_encode_symbols(monkeypatch):
    import io
    import live_terminal

    raw = io.BytesIO()
    monkeypatch.setattr("sys.stdout", io.TextIOWrapper(raw, encoding="cp1252", errors="strict"))
    live_terminal.say("SENDER", "\u2192 Sent packet #0 \u2713 \u2717 \u27f3 \u231b")
    import sys
    sys.stdout.flush()
    assert b"Sent packet #0" in raw.getvalue()
