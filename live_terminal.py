"""ResendIQ Live Terminal Mode: real UDP sockets + application-layer ARQ.

Run in two terminals:
  python live_terminal.py receiver --port 5005 --data-loss 0.15
  python live_terminal.py sender --port 5005 --protocol Selective-Repeat --ack-loss 0.10
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import socket
import sys
import time
from typing import Any

HOST = "127.0.0.1"
PROTOCOLS = ("Stop-and-Wait", "Go-Back-N", "Selective-Repeat")


def wire_send(sock: socket.socket, address: tuple[str, int], packet: dict[str, Any]) -> None:
    sock.sendto(json.dumps(packet, ensure_ascii=False).encode("utf-8"), address)


def wire_read(data: bytes) -> dict[str, Any] | None:
    try:
        value = json.loads(data.decode("utf-8"))
        return value if isinstance(value, dict) else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


_ASCII_FALLBACK = {"\u2192": "->", "\u2190": "<-", "\u2713": "[ok]", "\u2717": "[x]", "\u21a9": "<-",
                   "\u27f3": "[retry]", "\u231b": "[timeout]", "\u2013": "-", "\u2014": "-"}


def say(role: str, message: str) -> None:
    """Print a log line; never crash on consoles (e.g. Windows cp1252) that cannot show symbols."""
    line = f"[{role}] {message}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        for symbol, plain in _ASCII_FALLBACK.items():
            line = line.replace(symbol, plain)
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(line.encode(enc, errors="replace").decode(enc, errors="replace"), flush=True)


def run_receiver(host: str = HOST, port: int = 5005, data_loss: float = 0.0,
                 seed: int = 42, idle_timeout: float = 180.0) -> int:
    """Receive one message over UDP and acknowledge packets according to ARQ."""
    rng = random.Random(seed)
    received: dict[int, str] = {}
    expected = 0
    active_protocol = "Stop-and-Wait"
    last_activity = time.monotonic()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)
    try:
        sock.bind((host, port))
        say("RECEIVER", f"Listening on udp://{host}:{port}")
        say("RECEIVER", f"Simulated data-packet loss: {data_loss:.0%}. Press Ctrl+C to stop.")
        while True:
            if time.monotonic() - last_activity > idle_timeout:
                say("RECEIVER", "Idle timeout; shutting down.")
                return 1
            try:
                raw, peer = sock.recvfrom(65535)
            except socket.timeout:
                continue
            msg = wire_read(raw)
            if not msg:
                say("RECEIVER", "Ignored malformed UDP datagram.")
                continue
            kind = msg.get("type")
            if kind == "HELLO":
                active_protocol = str(msg.get("protocol", "Stop-and-Wait"))
                received.clear()
                expected = 0
                last_activity = time.monotonic()
                say("RECEIVER", f"Connection request from {peer[0]}:{peer[1]} using {active_protocol}.")
                wire_send(sock, peer, {"type": "READY", "protocol": active_protocol})
                say("RECEIVER", "Sent READY acknowledgement.")
                continue
            if kind == "DATA":
                last_activity = time.monotonic()
                seq = msg.get("seq")
                payload = msg.get("payload")
                if not isinstance(seq, int) or not isinstance(payload, str):
                    continue
                if rng.random() < data_loss:
                    say("RECEIVER", f"✗ Simulated DATA LOSS for packet #{seq}; no ACK sent.")
                    continue
                if active_protocol == "Go-Back-N":
                    if seq == expected:
                        received[seq] = payload
                        say("RECEIVER", f"✓ Accepted packet #{seq}: {payload!r}")
                        expected += 1
                    elif seq < expected:
                        say("RECEIVER", f"↩ Duplicate packet #{seq}; discarded, repeat cumulative ACK.")
                    else:
                        say("RECEIVER", f"↩ Out-of-order packet #{seq}; discarded (expected #{expected}).")
                    wire_send(sock, peer, {"type": "ACK", "seq": expected - 1, "cumulative": True})
                    say("RECEIVER", f"→ Sent cumulative ACK #{expected - 1}.")
                else:
                    if seq not in received:
                        received[seq] = payload
                        say("RECEIVER", f"✓ Accepted packet #{seq}: {payload!r}")
                    else:
                        say("RECEIVER", f"↩ Duplicate packet #{seq}; payload not stored twice.")
                    wire_send(sock, peer, {"type": "ACK", "seq": seq, "cumulative": False})
                    say("RECEIVER", f"→ Sent ACK #{seq}.")
                continue
            if kind == "FIN":
                last_activity = time.monotonic()
                total = msg.get("total")
                expected_hash = msg.get("sha256")
                if not isinstance(total, int) or total < 0:
                    continue
                if len(received) != total or any(i not in received for i in range(total)):
                    missing = [i for i in range(total) if i not in received]
                    wire_send(sock, peer, {"type": "FIN_WAIT", "missing": missing})
                    say("RECEIVER", f"Finish request arrived with missing packets: {missing}. Waiting for retransmission.")
                    continue
                reconstructed = "".join(received[i] for i in range(total))
                actual_hash = hashlib.sha256(reconstructed.encode("utf-8")).hexdigest()
                integrity_ok = actual_hash == expected_hash
                wire_send(sock, peer, {"type": "DONE", "integrity_ok": integrity_ok, "sha256": actual_hash})
                say("RECEIVER", "" )
                say("RECEIVER", "========== MESSAGE RECONSTRUCTED ==========")
                say("RECEIVER", reconstructed)
                say("RECEIVER", f"Packets received: {total}/{total}")
                say("RECEIVER", f"SHA-256 integrity: {'PASS' if integrity_ok else 'FAIL'}")
                say("RECEIVER", "Sent DONE acknowledgement. Receiver finished.")
                return 0 if integrity_ok else 2
    except KeyboardInterrupt:
        say("RECEIVER", "Stopped by user.")
        return 130
    except OSError as exc:
        say("RECEIVER", f"Socket error: {exc}")
        return 1
    finally:
        sock.close()


def _receive_ack(sock: socket.socket, peer: tuple[str, int], rng: random.Random,
                 ack_loss: float) -> dict[str, Any] | None:
    try:
        raw, address = sock.recvfrom(65535)
    except socket.timeout:
        return None
    if address != peer:
        return None
    msg = wire_read(raw)
    if not msg:
        return None
    if msg.get("type") == "ACK" and rng.random() < ack_loss:
        say("SENDER", f"✗ Simulated ACK LOSS for ACK #{msg.get('seq')}; sender ignores it.")
        return {"type": "ACK_DROPPED", "seq": msg.get("seq"), "cumulative": msg.get("cumulative", False)}
    return msg


def run_sender(message: str, host: str = HOST, port: int = 5005,
               protocol: str = "Stop-and-Wait", packet_size: int = 8,
               ack_loss: float = 0.0, timeout_ms: int = 500, max_retries: int = 8,
               window_size: int = 4, seed: int = 42) -> int:
    """Send a UTF-8 text message with Stop-and-Wait, GBN, or SR over UDP."""
    if protocol not in PROTOCOLS:
        raise ValueError(f"protocol must be one of: {', '.join(PROTOCOLS)}")
    if packet_size < 1 or timeout_ms < 1 or max_retries < 0 or window_size < 1:
        raise ValueError("packet size, timeout and window must be positive; retries may be zero")
    rng = random.Random(seed)
    # Split on characters, not encoded bytes, so Unicode messages reconstruct exactly.
    chunks = [message[i:i + packet_size] for i in range(0, len(message), packet_size)]
    payload_hash = hashlib.sha256(message.encode("utf-8")).hexdigest()
    peer = (host, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout_ms / 1000.0)
    sent_attempts = 0
    retransmissions = 0
    started = time.monotonic()
    try:
        # Handshake: repeat HELLO until the receiver responds.
        ready = False
        for attempt in range(max_retries + 1):
            wire_send(sock, peer, {"type": "HELLO", "protocol": protocol})
            say("SENDER", f"Sent HELLO ({attempt + 1}/{max_retries + 1}); waiting for receiver...")
            try:
                raw, address = sock.recvfrom(65535)
                response = wire_read(raw) if address == peer else None
            except socket.timeout:
                response = None
            if response and response.get("type") == "READY":
                ready = True
                break
            if attempt < max_retries:
                say("SENDER", "READY timeout; retrying handshake.")
        if not ready:
            say("SENDER", "Could not reach receiver. Start the receiver terminal first.")
            return 1

        say("SENDER", f"Receiver ready. Protocol={protocol}; {len(chunks)} data packet(s); payload={len(message)} chars.")

        def transmit(seq: int, retry: bool = False) -> None:
            nonlocal sent_attempts, retransmissions
            wire_send(sock, peer, {"type": "DATA", "seq": seq, "payload": chunks[seq]})
            sent_attempts += 1
            if retry:
                retransmissions += 1
                say("SENDER", f"⟳ Retransmitting packet #{seq} (attempt {retransmissions} retransmission(s) total).")
            else:
                say("SENDER", f"→ Sent packet #{seq}: {chunks[seq]!r}")

        if protocol == "Stop-and-Wait":
            for seq in range(len(chunks)):
                retries = 0
                acknowledged = False
                while not acknowledged:
                    transmit(seq, retry=retries > 0)
                    deadline = time.monotonic() + timeout_ms / 1000.0
                    while time.monotonic() < deadline:
                        response = _receive_ack(sock, peer, rng, ack_loss)
                        if response is None:
                            break
                        if response.get("type") == "ACK_DROPPED":
                            continue
                        if response.get("type") == "ACK" and response.get("seq") == seq:
                            acknowledged = True
                            say("SENDER", f"← ACK #{seq} received.")
                            break
                    if not acknowledged:
                        if retries >= max_retries:
                            say("SENDER", f"Retry limit reached for packet #{seq}; transfer failed.")
                            return 2
                        retries += 1
                        say("SENDER", f"⌛ Timeout waiting for ACK #{seq}.")

        elif protocol == "Go-Back-N":
            base = 0
            next_seq = 0
            retries = 0
            while base < len(chunks):
                while next_seq < len(chunks) and next_seq < base + window_size:
                    transmit(next_seq)
                    next_seq += 1
                response = _receive_ack(sock, peer, rng, ack_loss)
                if response and response.get("type") == "ACK_DROPPED":
                    continue
                if response and response.get("type") == "ACK" and response.get("cumulative"):
                    acked_through = int(response.get("seq", -1))
                    if acked_through >= base:
                        base = min(acked_through + 1, len(chunks))
                        retries = 0
                        say("SENDER", f"← Cumulative ACK #{acked_through}; next unacknowledged packet is #{base}.")
                        continue
                # Socket timeout or non-progress ACK: resend every outstanding packet.
                if base < len(chunks):
                    if retries >= max_retries:
                        say("SENDER", f"Retry limit reached at packet #{base}; transfer failed.")
                        return 2
                    retries += 1
                    say("SENDER", f"⌛ Timeout/no progress; Go-Back-N retransmits packets #{base}–#{next_seq - 1}.")
                    for seq in range(base, next_seq):
                        transmit(seq, retry=True)

        else:  # Selective Repeat: individual ACKs and only retry missing ACKs.
            base = 0
            while base < len(chunks):
                end = min(base + window_size, len(chunks))
                pending = set(range(base, end))
                retries_by_seq = {seq: 0 for seq in pending}
                for seq in sorted(pending):
                    transmit(seq)
                while pending:
                    response = _receive_ack(sock, peer, rng, ack_loss)
                    if response and response.get("type") == "ACK_DROPPED":
                        continue
                    if response and response.get("type") == "ACK" and not response.get("cumulative"):
                        seq = response.get("seq")
                        if seq in pending:
                            pending.remove(seq)
                            say("SENDER", f"← ACK #{seq} received; {len(pending)} packet(s) still unacknowledged in window.")
                    elif response is None:
                        exhausted = [seq for seq in pending if retries_by_seq[seq] >= max_retries]
                        if exhausted:
                            say("SENDER", f"Retry limit reached for packet(s) {exhausted}; transfer failed.")
                            return 2
                        retrying = sorted(pending)
                        say("SENDER", f"⌛ Timeout; Selective Repeat retransmits only unacknowledged packets {retrying}.")
                        for seq in retrying:
                            retries_by_seq[seq] += 1
                            transmit(seq, retry=True)
                base = end

        # Finish handshake. Receiver confirms reconstruction and SHA-256 integrity.
        finish_ok = False
        for attempt in range(max_retries + 1):
            wire_send(sock, peer, {"type": "FIN", "total": len(chunks), "sha256": payload_hash})
            try:
                raw, address = sock.recvfrom(65535)
                response = wire_read(raw) if address == peer else None
            except socket.timeout:
                response = None
            if response and response.get("type") == "DONE":
                finish_ok = bool(response.get("integrity_ok"))
                break
            if response and response.get("type") == "FIN_WAIT":
                missing = response.get("missing", [])
                say("SENDER", f"Receiver reports missing packets {missing}; resending them.")
                for seq in missing:
                    if isinstance(seq, int) and 0 <= seq < len(chunks):
                        transmit(seq, retry=True)
            if attempt < max_retries:
                say("SENDER", "Waiting for final receiver confirmation; retrying FIN if needed.")
        elapsed = time.monotonic() - started
        say("SENDER", "========== TRANSMISSION SUMMARY ==========")
        say("SENDER", f"Protocol: {protocol}")
        say("SENDER", f"Data packets: {len(chunks)}; total sends: {sent_attempts}; retransmissions: {retransmissions}")
        say("SENDER", f"Elapsed wall-clock time: {elapsed:.3f} s (includes real socket waits)")
        say("SENDER", f"Receiver integrity confirmation: {'PASS' if finish_ok else 'NOT CONFIRMED / FAIL'}")
        return 0 if finish_ok else 3
    except KeyboardInterrupt:
        say("SENDER", "Stopped by user.")
        return 130
    except OSError as exc:
        say("SENDER", f"Socket error: {exc}")
        return 1
    finally:
        sock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="ResendIQ real UDP terminal demo with application-layer ARQ")
    sub = parser.add_subparsers(dest="role", required=True)
    receiver = sub.add_parser("receiver", help="start the receiver terminal first")
    receiver.add_argument("--host", default=HOST)
    receiver.add_argument("--port", type=int, default=5005)
    receiver.add_argument("--data-loss", type=float, default=0.15, help="simulated incoming DATA loss, 0..1")
    receiver.add_argument("--seed", type=int, default=42)
    sender = sub.add_parser("sender", help="send a message to the receiver")
    sender.add_argument("--host", default=HOST)
    sender.add_argument("--port", type=int, default=5005)
    sender.add_argument("--protocol", choices=PROTOCOLS, default="Selective-Repeat")
    sender.add_argument("--message", default=None, help="message to send; omit to enter interactively")
    sender.add_argument("--packet-size", type=int, default=8)
    sender.add_argument("--ack-loss", type=float, default=0.10, help="simulated ACK loss at sender, 0..1")
    sender.add_argument("--timeout-ms", type=int, default=500)
    sender.add_argument("--max-retries", type=int, default=8)
    sender.add_argument("--window-size", type=int, default=4)
    sender.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    for name in ("data_loss", "ack_loss"):
        if hasattr(args, name) and not 0 <= getattr(args, name) <= 1:
            parser.error(f"--{name.replace('_', '-')} must be between 0 and 1")
    if args.role == "receiver":
        return run_receiver(args.host, args.port, args.data_loss, args.seed)
    message = args.message
    if message is None:
        try:
            message = input("Enter the message to transmit: ")
        except EOFError:
            print("No message entered.", file=sys.stderr)
            return 1
    return run_sender(message, args.host, args.port, args.protocol, args.packet_size,
                      args.ack_loss, args.timeout_ms, args.max_retries,
                      args.window_size, args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
