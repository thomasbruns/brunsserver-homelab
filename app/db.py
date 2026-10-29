"""SQLite com o histórico de temperatura/carga."""
from __future__ import annotations

import json
import sqlite3
import threading
import time

from . import config

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def init() -> None:
    global _conn
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    _conn.execute(
        """create table if not exists samples(
               ts integer primary key,
               cpu_temp real, load1 real, mem_percent real, disk_percent real,
               disk_temps text)"""
    )
    _conn.commit()


def close() -> None:
    # Com o lock: a amostra roda numa thread que o cancelamento da task não para,
    # e fechar a conexão no meio de um execute derruba o processo (segfault no sqlite).
    global _conn
    with _lock:
        if _conn:
            _conn.close()
            _conn = None


def insert_sample(snap: dict) -> None:
    root = next((m["percent"] for m in snap["mounts"] if m["mount"] == "/"), None)
    with _lock:
        if _conn is None:  # app desligando
            return
        _conn.execute(
            "insert or replace into samples values(?,?,?,?,?,?)",
            (int(time.time()), snap["cpu_temp"], snap["load"][0], snap["mem_percent"],
             root, json.dumps(snap["disk_temps"])),
        )
        _conn.execute("delete from samples where ts < ?", (time.time() - config.RETENTION_DAYS * 86400,))
        _conn.commit()


def query(hours: int) -> list[dict]:
    with _lock:
        if _conn is None:
            return []
        rows = _conn.execute(
            "select ts, cpu_temp, load1, mem_percent, disk_percent, disk_temps "
            "from samples where ts > ? order by ts",
            (time.time() - hours * 3600,),
        ).fetchall()
    return [
        {"ts": ts, "cpu_temp": cpu, "load1": load, "mem_percent": mem,
         "disk_percent": disk, "disk_temps": json.loads(dt or "{}")}
        for ts, cpu, load, mem, disk, dt in rows
    ]
