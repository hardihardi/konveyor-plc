"""
main.py — API server HMI (FastAPI). Jalur endpoint sesuai api-client.js.
PIN supervisor RPT-5: di-hash bcrypt-style (sha256+salt sederhana — produksi: argon2).
"""
from __future__ import annotations
import hashlib
import hmac
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from engine import PLCEngine, SCAN_MS

PIN_SALT = os.environ.get("HMI_PIN_SALT", "ganti-di-produksi")
PIN_HASH = hashlib.sha256(f"{PIN_SALT}:2580".encode()).hexdigest()  # PIN default 2580 — WAJIB diganti

app = FastAPI(title="HMI Konveyor API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

engine = PLCEngine()


def scan_loop() -> None:
    """Loop scan cycle 10 ms — thread terpisah, mirror real PLC."""
    next_scan = time.monotonic()
    while True:
        engine.step()
        next_scan += SCAN_MS / 1000
        sleep = next_scan - time.monotonic()
        if sleep > 0:
            time.sleep(sleep)
        else:
            next_scan = time.monotonic()  # scan overrun: reset, jangan akumulasi


threading.Thread(target=scan_loop, daemon=True, name="plc-scan").start()


@asynccontextmanager
async def lifespan(_app):
    yield


# ------------------------------------------------------------------ Models
class PerintahBody(BaseModel):
    perintah: str = Field(..., pattern="^(start|stop|estop|reset|reset_counter)$")

class ParamBody(BaseModel):
    debounce_ms: int | None = Field(None, ge=10, le=20)     # SORT-1 rentang PRD
    speed_hz: int | None = Field(None, ge=10, le=60)
    brake_ms: int | None = Field(None, ge=100, le=2000)
    sort_dwell_ms: int | None = Field(None, ge=100, le=3000)

class TutupShiftBody(BaseModel):
    pin: str = Field(..., min_length=4, max_length=8)

class IOTestBody(BaseModel):
    kanal: str = Field(..., pattern="^(sensor|aktuator|interlock|estop)$")
    nilai: bool


# ------------------------------------------------------------------ Endpoint
@app.get("/api/status")
def status():
    return engine.snapshot()

@app.post("/api/kontrol")
def kontrol(body: PerintahBody):
    hasil = engine.perintah(body.perintah)
    if not hasil.get("ok"):
        raise HTTPException(status_code=409, detail=hasil["detail"])
    return hasil

@app.get("/api/parameter")
def get_parameter():
    return engine.snapshot()["parameter"]

@app.put("/api/parameter")
def set_parameter(body: ParamBody):
    """Teknisi otomasi (RPT peran Bab 3): kalibrasi debounce, speed, brake, dwell."""
    if body.debounce_ms is not None:
        engine.param.debounce_time_ms = body.debounce_ms
    if body.speed_hz is not None:
        engine.param.motor_target_speed_hz = body.speed_hz
    if body.brake_ms is not None:
        engine.param.brake_delay_ms = body.brake_ms
    if body.sort_dwell_ms is not None:
        engine.param.sort_actuator_dwell_ms = body.sort_dwell_ms
    return engine.snapshot()["parameter"]

@app.get("/api/laporan")
def laporan(tanggal: str | None = None):
    """RPT-4: ringkasan harian dari counter retentif."""
    c = engine.counter
    target_shift = 500  # target per shift — supervisor bisa ubah (kalibrasi)
    total = c.sorted + c.passed
    efisiensi = round((total / target_shift) * 100) if target_shift > 0 else 0
    return {
        "report_date": tanggal or time.strftime("%Y-%m-%d"),
        "shift_number": ((int(time.strftime("%H")) - 6) % 24) // 8 + 1,
        "total_item_count": c.total,
        "passed_item_count": c.passed,
        "sorted_item_count": c.sorted,
        "uptime_minutes": c.uptime_minutes,
        "efficiency_percent": efisiensi,
    }

@app.post("/api/laporan/tutup-shift")
def tutup_shift(body: TutupShiftBody):
    """RPT-5: reset counter dengan otorisasi PIN supervisor (alur Bab 7.4)."""
    digest = hashlib.sha256(f"{PIN_SALT}:{body.pin}".encode()).hexdigest()
    if not hmac.compare_digest(digest, PIN_HASH):
        raise HTTPException(status_code=403, detail="PIN supervisor salah. Coba lagi atau hubungi teknisi.")
    engine.perintah("reset_counter")
    return {"ok": True, "detail": "Shift ditutup, penghitung direset dan diarsipkan."}

@app.get("/api/laporan/ekspor")
def ekspor_csv(tanggal: str | None = None):
    """RPT-6: ekspor CSV."""
    l = laporan(tanggal)
    csv = (
        "report_date,shift_number,total_item_count,passed_item_count,"
        "sorted_item_count,uptime_minutes,efficiency_percent\n"
        f"{l['report_date']},{l['shift_number']},{l['total_item_count']},"
        f"{l['passed_item_count']},{l['sorted_item_count']},"
        f"{l['uptime_minutes']},{l['efficiency_percent']}\n"
    )
    return PlainTextResponse(csv, media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename=laporan-produksi-{l['report_date']}.csv"
    })

@app.get("/api/alarm")
def alarm_log():
    """alarm_log entity (Bab 8) — MVP: dari state engine."""
    alarms = []
    if engine._estop_latched:
        alarms.append({"alarm_code": "E-STOP", "description": "Emergency stop aktif — daya motor diputus (STO).",
                       "timestamp": time.time()})
    if engine._fault_latched:
        alarms.append({"alarm_code": "ACT-STUCK", "description": "Aktuator sortir tidak kembali home dalam dwell.",
                       "timestamp": time.time()})
    return alarms

@app.post("/api/diagnostik/io")
def io_test(body: IOTestBody):
    """Teknisi: pengetesan I/O manual (Bab 3 peran)."""
    mapping = {
        "sensor": "in_objek", "aktuator": "in_aktuator_home",
        "interlock": "in_interlock", "estop": "in_estop",
    }
    setattr(engine, mapping[body.kanal], body.nilai)
    return {"ok": True, "kanal": body.kanal, "nilai": body.nilai}

@app.get("/api/simulasi/objek")
def sim_objek():
    """Simulator: dorong 1 objek lewat sensor (untuk demo tanpa hardware)."""
    engine.stimulus_sensor(True)
    time.sleep(0.05)
    engine.stimulus_sensor(False)
    return {"ok": True, "detail": "Objek simulasi dikirim ke sensor."}


# ------------------------------------------------------------------ Static HMI
import pathlib
_FRONTEND = pathlib.Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(_FRONTEND), html=True), name="hmi")
