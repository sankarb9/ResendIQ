"""SQLite storage: sessions, raw samples, monitoring log, floor plan + location coordinates."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

# <project root>/data/wifi_analyzer.db  (src/resendiq/wifi/db.py -> parents[3] is the project root)
DB = str(Path(__file__).resolve().parents[3] / "data" / "wifi_analyzer.db")
NUM_COLS = ["avg_ms", "loss_pct", "jitter_ms", "max_ms", "score", "dns_ms", "http_ms"]


def _connect():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB)


def init():
    c = _connect()
    with c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, location TEXT, created_at TEXT, duration_s INTEGER,
            basis TEXT, avg_ms REAL, loss_pct REAL, jitter_ms REAL, max_ms REAL,
            reachability TEXT, score REAL, status TEXT, diagnosis TEXT, details TEXT,
            band TEXT, dns_ms REAL, http_ms REAL, usability TEXT);
        CREATE TABLE IF NOT EXISTS samples(session_id INTEGER, target TEXT, seq INTEGER, rtt_ms REAL);
        CREATE TABLE IF NOT EXISTS monitor(
            id INTEGER PRIMARY KEY AUTOINCREMENT, location TEXT, created_at TEXT, avg_ms REAL,
            loss_pct REAL, jitter_ms REAL, score REAL, status TEXT, alert INTEGER);
        CREATE TABLE IF NOT EXISTS floorplan(id INTEGER PRIMARY KEY CHECK(id = 1), name TEXT, image BLOB);
        CREATE TABLE IF NOT EXISTS coords(location TEXT PRIMARY KEY, x REAL, y REAL);
        """)
        # migrate databases created by the earlier version
        cols = {r[1] for r in c.execute("PRAGMA table_info(sessions)")}
        for name, typ in [("band", "TEXT"), ("dns_ms", "REAL"), ("http_ms", "REAL"), ("usability", "TEXT")]:
            if name not in cols:
                c.execute(f"ALTER TABLE sessions ADD COLUMN {name} {typ}")
    c.close()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def save_session(location, duration, result, samples, band=None):
    p, a = result["primary"], result.get("app") or {}
    c = _connect()
    try:
        with c:
            cur = c.execute(
                "INSERT INTO sessions(location,created_at,duration_s,basis,avg_ms,loss_pct,jitter_ms,max_ms,"
                "reachability,score,status,diagnosis,details,band,dns_ms,http_ms,usability) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (location, _now(), duration, result["basis"], p["avg"], p["loss"], p["jitter"], p["max"],
                 p["reachability"], p["score"], p["status"], result["diagnosis"],
                 json.dumps({"metrics": result["metrics"], "app": a}),
                 band, a.get("dns_ms"), a.get("http_ms"), a.get("usability")))
            sid = cur.lastrowid
            c.executemany("INSERT INTO samples VALUES (?,?,?,?)",
                          [(sid, t, i, r) for t, v in samples.items() for i, r in enumerate(v)])
        return sid
    finally:
        c.close()


def load_sessions():
    c = _connect()
    try:
        df = pd.read_sql("SELECT * FROM sessions ORDER BY created_at", c)
    finally:
        c.close()
    for col in NUM_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ---- continuous monitoring ----
def save_monitor(location, p, alert):
    c = _connect()
    with c:
        c.execute("INSERT INTO monitor(location,created_at,avg_ms,loss_pct,jitter_ms,score,status,alert) "
                  "VALUES (?,?,?,?,?,?,?,?)",
                  (location, _now(), p["avg"], p["loss"], p["jitter"], p["score"], p["status"], int(alert)))
    c.close()


def load_monitor(location=None):
    c = _connect()
    try:
        q, args = "SELECT * FROM monitor", ()
        if location:
            q, args = q + " WHERE location = ?", (location,)
        df = pd.read_sql(q + " ORDER BY created_at", c, params=args)
    finally:
        c.close()
    df["created_at"] = pd.to_datetime(df["created_at"])
    return df


def load_trend():
    """All measurements (manual sessions + monitoring cycles) for time-of-day analysis."""
    c = _connect()
    try:
        df = pd.read_sql(
            "SELECT created_at, location, score, avg_ms, loss_pct, status, 'test' AS source FROM sessions "
            "UNION ALL SELECT created_at, location, score, avg_ms, loss_pct, status, 'monitor' FROM monitor "
            "ORDER BY created_at", c)
    finally:
        c.close()
    df["created_at"] = pd.to_datetime(df["created_at"])
    return df


# ---- floor plan ----
def save_floorplan(name, image_bytes):
    c = _connect()
    with c:
        c.execute("INSERT OR REPLACE INTO floorplan VALUES (1,?,?)", (name, image_bytes))
        c.execute("DELETE FROM coords")  # old positions don't apply to a new plan
    c.close()


def load_floorplan():
    c = _connect()
    try:
        row = c.execute("SELECT image FROM floorplan WHERE id = 1").fetchone()
    finally:
        c.close()
    return row[0] if row else None


def save_coord(location, x, y):
    c = _connect()
    with c:
        c.execute("INSERT OR REPLACE INTO coords VALUES (?,?,?)", (location, x, y))
    c.close()


def load_coords():
    c = _connect()
    try:
        return {r[0]: (r[1], r[2]) for r in c.execute("SELECT location, x, y FROM coords")}
    finally:
        c.close()


def clear_all():
    """Delete measurements (floor plan and positions are kept)."""
    c = _connect()
    with c:
        c.executescript("DELETE FROM sessions; DELETE FROM samples; DELETE FROM monitor;")
    c.close()
