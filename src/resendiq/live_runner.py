"""Launch ``live_terminal.py`` receiver + sender as subprocesses and stream their output.

Independent of Streamlit so it can be unit-tested. The UDP/ARQ logic itself stays in live_terminal.py.
"""
from __future__ import annotations

import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

SCRIPT = Path(__file__).resolve().parents[2] / "live_terminal.py"


@dataclass
class LiveSettings:
    message: str = "Reliable data transmission using ARQ"
    protocol: str = "Selective-Repeat"
    port: int = 5005
    data_loss: float = 0.15
    ack_loss: float = 0.10
    timeout_ms: int = 500
    window_size: int = 4
    max_retries: int = 8
    packet_size: int = 8
    seed: int = 42


@dataclass
class LiveSummary:
    packets: int = 0
    total_sends: int = 0
    retransmissions: int = 0
    data_losses: int = 0
    ack_losses: int = 0
    timeouts: int = 0
    elapsed_s: float | None = None
    integrity: str = "UNKNOWN"
    reconstructed: str = ""
    sender_exit: int | None = None
    lines: list = field(default_factory=list)


def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def receiver_cmd(s: LiveSettings) -> list[str]:
    return [sys.executable, "-u", str(SCRIPT), "receiver", "--port", str(s.port),
            "--data-loss", str(s.data_loss), "--seed", str(s.seed)]


def sender_cmd(s: LiveSettings) -> list[str]:
    return [sys.executable, "-u", str(SCRIPT), "sender", "--port", str(s.port), "--protocol", s.protocol,
            "--message", s.message, "--packet-size", str(s.packet_size), "--ack-loss", str(s.ack_loss),
            "--timeout-ms", str(s.timeout_ms), "--max-retries", str(s.max_retries),
            "--window-size", str(s.window_size), "--seed", str(s.seed)]


def display_commands(s: LiveSettings) -> tuple[str, str]:
    """Copy-paste commands for people who prefer two real terminals."""
    recv = f"python live_terminal.py receiver --port {s.port} --data-loss {s.data_loss} --seed {s.seed}"
    msg = s.message.replace('"', "'")
    send = (f'python live_terminal.py sender --port {s.port} --protocol "{s.protocol}" --message "{msg}" '
            f"--packet-size {s.packet_size} --ack-loss {s.ack_loss} --timeout-ms {s.timeout_ms} "
            f"--window-size {s.window_size} --max-retries {s.max_retries} --seed {s.seed}")
    return recv, send


def _pump(proc: subprocess.Popen, q: "queue.Queue", done: threading.Event) -> None:
    for line in proc.stdout:  # type: ignore[union-attr]
        q.put(line.rstrip("\r\n"))
    done.set()


def run_transfer(s: LiveSettings, overall_timeout: float = 120.0) -> Iterator[str]:
    """Run a transfer and yield output lines (they already carry [SENDER]/[RECEIVER] prefixes)."""
    q: queue.Queue = queue.Queue()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}  # symbols survive the pipe on Windows
    popen_kw = dict(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                    errors="replace", env=env)
    receiver = sender = None
    try:
        receiver = subprocess.Popen(receiver_cmd(s), **popen_kw)
        r_done = threading.Event()
        threading.Thread(target=_pump, args=(receiver, q, r_done), daemon=True).start()
        time.sleep(0.6)  # let the receiver bind its socket
        sender = subprocess.Popen(sender_cmd(s), **popen_kw)
        s_done = threading.Event()
        threading.Thread(target=_pump, args=(sender, q, s_done), daemon=True).start()
        deadline = time.monotonic() + overall_timeout
        grace_end = None
        while time.monotonic() < deadline:
            try:
                yield q.get(timeout=0.1)
                continue
            except queue.Empty:
                pass
            if sender.poll() is not None and grace_end is None:
                grace_end = time.monotonic() + 3.0  # let the receiver print its final summary
            if grace_end and (receiver.poll() is not None or time.monotonic() > grace_end) and q.empty():
                break
        else:
            yield "[SYSTEM] Overall timeout reached; stopping both processes."
        while not q.empty():
            yield q.get()
    finally:
        for p in (sender, receiver):
            if p is not None and p.poll() is None:
                p.kill()
        for p in (sender, receiver):
            if p is not None:
                p.wait(timeout=5)
        if sender is not None:
            run_transfer.last_exit = sender.returncode  # type: ignore[attr-defined]


def parse_summary(lines: list[str]) -> LiveSummary:
    out = LiveSummary(lines=list(lines))
    grab_next = False
    for ln in lines:
        if "MESSAGE RECONSTRUCTED" in ln:
            grab_next = True
            continue
        if grab_next:
            out.reconstructed = ln.split("] ", 1)[-1] if ln.startswith("[RECEIVER]") else ln
            grab_next = False
        if "Simulated DATA LOSS" in ln:
            out.data_losses += 1
        elif "Simulated ACK LOSS" in ln:
            out.ack_losses += 1
        elif "⌛" in ln:
            out.timeouts += 1
        if m := re.search(r"Data packets: (\d+); total sends: (\d+); retransmissions: (\d+)", ln):
            out.packets, out.total_sends, out.retransmissions = map(int, m.groups())
        if m := re.search(r"Elapsed wall-clock time: ([\d.]+) s", ln):
            out.elapsed_s = float(m.group(1))
        if "[RECEIVER] SHA-256 integrity:" in ln:
            out.integrity = ln.rsplit(":", 1)[-1].strip()
        elif "Receiver integrity confirmation:" in ln and out.integrity == "UNKNOWN":
            out.integrity = "PASS" if ln.rstrip().endswith("PASS") else "FAIL"
    out.sender_exit = getattr(run_transfer, "last_exit", None)
    return out


def classify(line: str) -> str:
    """CSS class used by the terminal view."""
    if "✗" in line or "failed" in line or "FAIL" in line or "Retry limit" in line:
        return "bad"
    if "⟳" in line or "⌛" in line or "↩" in line:
        return "warn"
    if "✓" in line or "PASS" in line or "← ACK" in line or "←" in line:
        return "ok"
    if line.startswith("[RECEIVER]"):
        return "rx"
    if line.startswith("[SENDER]"):
        return "tx"
    return "dim"
