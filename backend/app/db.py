import json
import sqlite3
import time
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS drivers (
    id TEXT PRIMARY KEY,
    name TEXT,
    phone TEXT
);
CREATE TABLE IF NOT EXISTS trips (
    id TEXT PRIMARY KEY,
    driver_id TEXT,
    container TEXT,
    port_name TEXT,
    port_lat REAL,
    port_lon REAL,
    status TEXT,            -- en_ruta | en_puerto | esperando_puerto | habilitado | cargando | cerrado
    created_at REAL
);
CREATE TABLE IF NOT EXISTS pings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id TEXT, lat REAL, lon REAL, speed REAL, ts REAL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id TEXT, type TEXT, payload TEXT, ts REAL
);
CREATE TABLE IF NOT EXISTS calls (
    id TEXT PRIMARY KEY,
    trip_id TEXT,
    reason TEXT,            -- arrival_check | load_authorized | emergency
    status TEXT,            -- ringing | done | failed
    transcript TEXT,
    outcome TEXT,           -- json: {available, eta_min, notes}
    voice TEXT,             -- json: metricas de voz
    duration_s REAL,
    cost_usd REAL,
    audio_path TEXT,        -- wav de la llamada, servido por /ops/calls/{id}/audio
    ts REAL
);
CREATE TABLE IF NOT EXISTS thresholds (
    key TEXT PRIMARY KEY, value REAL, updated_at REAL, reason TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id TEXT, severity TEXT, title TEXT, body TEXT, channels TEXT, ts REAL
);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript(SCHEMA)
        columns = {row[1] for row in c.execute("PRAGMA table_info(calls)")}
        if "twilio_sid" not in columns:
            c.execute("ALTER TABLE calls ADD COLUMN twilio_sid TEXT")
        if "audio_path" not in columns:
            c.execute("ALTER TABLE calls ADD COLUMN audio_path TEXT")


def q(sql, args=()):
    with conn() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def one(sql, args=()):
    r = q(sql, args)
    return r[0] if r else None


def x(sql, args=()):
    with conn() as c:
        c.execute(sql, args)


def log_event(trip_id, type_, payload):
    x("INSERT INTO events (trip_id,type,payload,ts) VALUES (?,?,?,?)",
      (trip_id, type_, json.dumps(payload), time.time()))
