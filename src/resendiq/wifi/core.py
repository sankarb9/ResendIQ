"""Measurement + analysis core for the Wi-Fi Stability & Dead-Zone Analyzer.

Run standalone for a quick CLI test:  python core.py --duration 15
"""
import argparse
import platform
import re
import socket
import statistics
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

OS = platform.system()  # "Windows", "Darwin" (macOS) or "Linux"

# Project-specific thresholds (NOT universal Wi-Fi standards) - tune and justify in your report.
T = dict(
    stable_lat=50, stable_loss=1, stable_jit=15,   # Stable:  avg RTT ms, loss %, jitter ms
    fair_lat=100, fair_loss=5, fair_jit=30,        # Fair
    dead_loss=10,                                  # >= this loss % (or no replies) = Potential Dead Zone
)


# ---------- Module 1: network discovery ----------
def get_default_gateway():
    """Return the default gateway IP as a string, or None if it can't be found."""
    try:
        if OS == "Windows":
            out = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=10).stdout
            m = re.search(r"Default Gateway[ .]*:\s*((?:\d{1,3}\.){3}\d{1,3})", out)
        elif OS == "Darwin":
            out = subprocess.run(["route", "-n", "get", "default"], capture_output=True, text=True, timeout=10).stdout
            m = re.search(r"gateway:\s*(\S+)", out)
        else:
            out = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=10).stdout
            m = re.search(r"default via (\S+)", out)
        return m.group(1) if m else None
    except Exception:
        return None


# ---------- Modules 2 & 3: connectivity + performance measurement ----------
def ping_once(host, timeout=1.0):
    """Send one ICMP echo. Returns RTT in ms, or None if lost/unreachable."""
    if OS == "Windows":
        cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), host]
    elif OS == "Darwin":
        cmd = ["ping", "-c", "1", "-W", str(int(timeout * 1000)), host]  # macOS: -W is in ms
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, int(timeout))), host]  # Linux: -W is in s
    start = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
    except Exception:
        return None
    # A real reply always carries a TTL; this filters Windows' "host unreachable" replies (exit code 0).
    if p.returncode != 0 or not re.search(r"ttl=", p.stdout, re.I):
        return None
    m = re.search(r"time[=<]\s*([\d.]+)", p.stdout, re.I)
    return float(m.group(1)) if m else (time.perf_counter() - start) * 1000


def run_session(targets, duration=30, interval=0.5, on_progress=None):
    """Ping every target once per `interval` seconds for `duration` seconds.

    targets: {"gateway": "192.168.1.1", "external": "8.8.8.8"}
    Returns {label: [rtt_ms or None, ...]}.
    """
    samples = {k: [] for k in targets}
    n = max(1, int(duration / interval))
    with ThreadPoolExecutor(max_workers=max(1, len(targets))) as ex:
        for i in range(n):
            tick = time.perf_counter()
            futs = {k: ex.submit(ping_once, h) for k, h in targets.items()}
            for k, f in futs.items():
                samples[k].append(f.result())
            if on_progress:
                on_progress((i + 1) / n)
            time.sleep(max(0.0, interval - (time.perf_counter() - tick)))
    return samples


# ---------- Modules 4 & 5: stability analysis + dead-zone detection ----------
def summarize(rtts):
    ok = sorted(r for r in rtts if r is not None)
    sent, recv = len(rtts), len(ok)
    m = dict(sent=sent, received=recv, loss=round(100 * (sent - recv) / sent, 1) if sent else 100.0)
    if ok:
        m.update(avg=round(statistics.fmean(ok), 1), min=round(ok[0], 1), max=round(ok[-1], 1),
                 jitter=round(statistics.pstdev(ok), 1), p95=round(ok[int(0.95 * (recv - 1))], 1))
    else:
        m.update(avg=None, min=None, max=None, jitter=None, p95=None)
    return m


def reachability(m):
    if m["received"] == 0:
        return "Unreachable"
    return "Intermittent" if m["loss"] > 5 else "Reachable"


def score(m):
    """0-100 stability score. Weights: 40 loss, 35 latency, 25 jitter (finalize/justify in report)."""
    if m["received"] == 0:
        return 0.0
    loss_p = min(m["loss"] / 10, 1) * 40
    lat_p = min(max(m["avg"] - 20, 0) / 180, 1) * 35
    jit_p = min(m["jitter"] / 50, 1) * 25
    return round(100 - loss_p - lat_p - jit_p, 1)


def classify(m):
    if m["received"] == 0 or m["loss"] >= T["dead_loss"]:
        return "Potential Dead Zone"
    if m["avg"] <= T["stable_lat"] and m["loss"] <= T["stable_loss"] and m["jitter"] <= T["stable_jit"]:
        return "Stable"
    if m["avg"] <= T["fair_lat"] and m["loss"] <= T["fair_loss"] and m["jitter"] <= T["fair_jit"]:
        return "Fair"
    return "Unstable"


def diagnose(metrics):
    """Compare the Wi-Fi hop (gateway) with the wider path (external) to localize the fault."""
    gw, ext = metrics.get("gateway"), metrics.get("external")
    bad = ("Unstable", "Potential Dead Zone")
    if gw and gw["status"] in bad:
        return "Weak/unstable Wi-Fi link: even the router is affected at this location."
    if gw and ext and ext["status"] in bad:
        return "Wi-Fi link to the router looks fine; the problem is beyond the router (ISP/upstream)."
    p = gw or ext
    return {"Stable": "Healthy link at this location.",
            "Fair": "Usable but somewhat degraded link."}.get(p["status"], "Poor link at this location.")


def evaluate(samples):
    metrics = {k: summarize(v) for k, v in samples.items()}
    for m in metrics.values():
        m["reachability"], m["score"], m["status"] = reachability(m), score(m), classify(m)
    basis = "gateway" if "gateway" in metrics else "external"  # gateway = pure Wi-Fi hop
    return dict(basis=basis, metrics=metrics, primary=metrics[basis], diagnosis=diagnose(metrics))


# ---------- Application-layer checks (DNS + HTTP): "connected" vs "actually usable" ----------
DNS_HOSTS = ["google.com", "wikipedia.org", "cloudflare.com", "github.com"]
HTTP_URLS = ["http://connectivitycheck.gstatic.com/generate_204", "http://www.msftconnecttest.com/connecttest.txt"]
APP_T = dict(dns_slow=300, http_slow=1500)  # ms; project-specific "Degraded" limits


def dns_lookup_ms(host, timeout=3.0):
    """Time a DNS resolution (getaddrinfo has no timeout, so run it in a worker thread).
    Note: the OS may cache answers, so treat repeat-run DNS times as indicative."""
    start, ex = time.perf_counter(), ThreadPoolExecutor(max_workers=1)
    try:
        ex.submit(socket.getaddrinfo, host, 80).result(timeout=timeout)
        return (time.perf_counter() - start) * 1000
    except Exception:
        return None
    finally:
        ex.shutdown(wait=False)


def http_fetch_ms(url, timeout=5.0):
    """Time a small HTTP GET (DNS + TCP + request/response). None on failure."""
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            r.read(1024)
        return (time.perf_counter() - start) * 1000
    except Exception:
        return None


def app_checks(rounds=3):
    dns = [dns_lookup_ms(DNS_HOSTS[i % len(DNS_HOSTS)]) for i in range(rounds)]
    http = [http_fetch_ms(HTTP_URLS[i % len(HTTP_URLS)]) for i in range(rounds)]
    d, h = [x for x in dns if x is not None], [x for x in http if x is not None]
    dns_ms = round(statistics.fmean(d), 1) if d else None
    http_ms = round(statistics.fmean(h), 1) if h else None
    if not h:
        usability = "Unusable"
    elif len(h) < rounds or len(d) < rounds or http_ms > APP_T["http_slow"] or (dns_ms or 0) > APP_T["dns_slow"]:
        usability = "Degraded"
    else:
        usability = "Usable"
    return dict(dns_ms=dns_ms, dns_fail=rounds - len(d), http_ms=http_ms, http_fail=rounds - len(h),
                usability=usability)


# ---------- Statistics across repeated runs ----------
# Two-sided 95% Student-t critical values by degrees of freedom (next tabulated df >= actual = conservative)
_T95 = [(1, 12.706), (2, 4.303), (3, 3.182), (4, 2.776), (5, 2.571), (6, 2.447), (7, 2.365), (8, 2.306),
        (9, 2.262), (10, 2.228), (11, 2.201), (12, 2.179), (13, 2.160), (14, 2.145), (15, 2.131), (16, 2.120),
        (17, 2.110), (18, 2.101), (19, 2.093), (20, 2.086), (25, 2.060), (30, 2.042)]


def mean_ci(values):
    """(mean, std, 95% CI half-width) of repeated runs. std/CI are None when n < 2."""
    v = [x for x in values if x is not None and x == x]
    if not v:
        return None, None, None
    mean = statistics.fmean(v)
    if len(v) < 2:
        return round(mean, 1), None, None
    sd, df = statistics.stdev(v), len(v) - 1
    t = next((tv for d, tv in _T95 if d >= df), 1.96)
    return round(mean, 1), round(sd, 1), round(t * sd / len(v) ** 0.5, 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=15)
    ap.add_argument("--external", default="8.8.8.8")
    a = ap.parse_args()
    gw = get_default_gateway()
    print(f"OS: {OS} | gateway: {gw}")
    targets = ({"gateway": gw} if gw else {}) | {"external": a.external}
    res = evaluate(run_session(targets, a.duration, on_progress=lambda p: print(f"\r{p:4.0%}", end="")))
    print()
    for k, m in res["metrics"].items():
        print(k, m)
    print("Diagnosis:", res["diagnosis"])
    print("App layer:", app_checks())
