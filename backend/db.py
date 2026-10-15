"""
db.py — lapisan database SQLite (WAL mode). Satu file, semua tabel sesuai model data PRD Bab 8.
Entitas dibangun: daily_production_summary, alarm_log, system_parameter, user_account (autentikasi teknisi/supervisor).
Fase Lanjutan (tidak dibangun sesuai Bab 4.2): item_event (barcode), erp_sync_status.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import date, datetime

DB_PATH = os.environ.get("HMI_DB", os.path.join(os.path.dirname(__file__), "hmi.db"))
PIN_SALT = os.environ.get("HMI_PIN_SALT", "ganti-di-produksi")

_local = threading.local()


def koneksi() -> sqlite3.Connection:
    """Koneksi per-thread (SQLite tidak thread-safe lintas koneksi yang sama)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        _local.conn = conn
    return conn


@contextmanager
def transaksi():
    conn = koneksi()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_production_summary (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date   TEXT NOT NULL,             -- YYYY-MM-DD
    shift_number  INTEGER NOT NULL CHECK (shift_number BETWEEN 1 AND 3),
    total_item_count   INTEGER NOT NULL DEFAULT 0,
    passed_item_count  INTEGER NOT NULL DEFAULT 0,
    sorted_item_count  INTEGER NOT NULL DEFAULT 0,
    uptime_minutes     INTEGER NOT NULL DEFAULT 0,
    efficiency_percent INTEGER NOT NULL DEFAULT 0,
    closed_at     TEXT NOT NULL,             -- RPT-5
    closed_by     TEXT NOT NULL,             -- username supervisor
    UNIQUE (report_date, shift_number)
);

CREATE TABLE IF NOT EXISTS alarm_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    alarm_code  TEXT NOT NULL,
    description TEXT NOT NULL,
    raised_at   TEXT NOT NULL,
    cleared_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_alarm_raised ON alarm_log (raised_at DESC);

CREATE TABLE IF NOT EXISTS system_parameter (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS user_account (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,             -- PBKDF2-HMAC-SHA256, 200.000 iterasi
    role         TEXT NOT NULL CHECK (role IN ('supervisor', 'teknisi')),
    created_at   TEXT NOT NULL,
    is_active    INTEGER NOT NULL DEFAULT 1
);
"""


def inisialisasi() -> None:
    with transaksi() as conn:
        conn.executescript(SCHEMA)
        # Seed akun default — password harus diganti saat login pertama (wajib di README).
        if conn.execute("SELECT COUNT(*) FROM user_account").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO user_account (username, password_hash, role, created_at) VALUES (?,?,?,?)",
                ("supervisor", hash_password("2580", PIN_SALT), "supervisor", sekarang()),
            )
            conn.execute(
                "INSERT INTO user_account (username, password_hash, role, created_at) VALUES (?,?,?,?)",
                ("teknisi", hash_password("teknisi2026", PIN_SALT), "teknisi", sekarang()),
            )


def sekarang() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ------------------------------------------------------------------ Password (PBKDF2 — standar stdlib, tanpa dependensi)
def hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return digest.hex()


def verifikasi_password(password: str, stored: str) -> bool:
    return hmac.compare_digest(hash_password(password, PIN_SALT), stored)


# ------------------------------------------------------------------ Laporan harian
def simpan_shift(
    report_date: str, shift_number: int, total: int, passed: int,
    sorted_count: int, uptime: int, efficiency: int, closed_by: str,
) -> int:
    with transaksi() as conn:
        cur = conn.execute(
            """INSERT INTO daily_production_summary
               (report_date, shift_number, total_item_count, passed_item_count,
                sorted_item_count, uptime_minutes, efficiency_percent, closed_at, closed_by)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT (report_date, shift_number) DO UPDATE SET
                 total_item_count=excluded.total_item_count,
                 passed_item_count=excluded.passed_item_count,
                 sorted_item_count=excluded.sorted_item_count,
                 uptime_minutes=excluded.uptime_minutes,
                 efficiency_percent=excluded.efficiency_percent,
                 closed_at=excluded.closed_at,
                 closed_by=excluded.closed_by""",
            (report_date, shift_number, total, passed, sorted_count, uptime, efficiency, sekarang(), closed_by),
        )
        return cur.lastrowid


def ambil_laporan(tanggal: str | None = None, limit: int = 90) -> list[dict]:
    conn = koneksi()
    if tanggal:
        rows = conn.execute(
            "SELECT * FROM daily_production_summary WHERE report_date=? ORDER BY shift_number", (tanggal,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM daily_production_summary ORDER BY report_date DESC, shift_number DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def hitung_shift_saat_ini() -> int:
    """Shift 1: 06–14, 2: 14–22, 3: 22–06 (disetujui)."""
    jam = datetime.now().hour
    if 6 <= jam < 14:
        return 1
    if 14 <= jam < 22:
        return 2
    return 3


# ------------------------------------------------------------------ Alarm
def catat_alarm(alarm_code: str, description: str) -> int:
    with transaksi() as conn:
        cur = conn.execute(
            "INSERT INTO alarm_log (alarm_code, description, raised_at) VALUES (?,?,?)",
            (alarm_code, description, sekarang()),
        )
        return cur.lastrowid


def aktif_alarm() -> list[dict]:
    return [dict(r) for r in koneksi().execute(
        "SELECT * FROM alarm_log WHERE cleared_at IS NULL ORDER BY raised_at DESC").fetchall()]


def bersihkan_alarm(alarm_code: str) -> None:
    with transaksi() as conn:
        conn.execute(
            "UPDATE alarm_log SET cleared_at=? WHERE alarm_code=? AND cleared_at IS NULL",
            (sekarang(), alarm_code),
        )


def riwayat_alarm(limit: int = 100) -> list[dict]:
    return [dict(r) for r in koneksi().execute(
        "SELECT * FROM alarm_log ORDER BY raised_at DESC LIMIT ?", (limit,)).fetchall()]


# ------------------------------------------------------------------ Parameter
def simpan_parameter(params: dict, updated_by: str = "teknisi") -> None:
    with transaksi() as conn:
        for k, v in params.items():
            conn.execute(
                "INSERT INTO system_parameter (key, value, updated_at, updated_by) VALUES (?,?,?,?) "
                "ON CONFLICT (key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at, updated_by=excluded.updated_by",
                (k, json.dumps(v), sekarang(), updated_by),
            )


def ambil_parameter() -> dict:
    rows = koneksi().execute("SELECT key, value FROM system_parameter").fetchall()
    return {r["key"]: json.loads(r["value"]) for r in rows}


# ------------------------------------------------------------------ Akun
def autentikasi(username: str, password: str) -> dict | None:
    row = koneksi().execute(
        "SELECT * FROM user_account WHERE username=? AND is_active=1", (username,)).fetchone()
    if row and verifikasi_password(password, row["password_hash"]):
        return {"username": row["username"], "role": row["role"]}
    return None


def ganti_password(username: str, password_baru: str) -> None:
    with transaksi() as conn:
        conn.execute(
            "UPDATE user_account SET password_hash=? WHERE username=?",
            (hash_password(password_baru, PIN_SALT), username),
        )
