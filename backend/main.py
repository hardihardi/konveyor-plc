"""
main.py — REST API HMI Konveyor (FastAPI + SQLite).
Auth: bearer token (secrets.token_hex) di memori, 8 jam. Role: supervisor/teknisi.
Endpoint /api/status, /api/parameter (GET), /api/laporan (GET), /api/alarm (GET) publik baca-saja untuk display pabrik.
"""
from __future__ import annotations
import pathlib
import secrets
import threading
import time

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

import db
from engine import PLCEngine, SCAN_MS

app = FastAPI(
    title="HMI Konveyor API",
    version="0.2.0",
    description="REST API Smart Conveyor Sorting & Daily Production Counter (PRD v0.1)",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db.inisialisasi()
engine = PLCEngine()

# Muat parameter kalibrasi tersimpan dari DB (persistensi konfigurasi antar restart)
_tersimpan = db.ambil_parameter()
if "debounce_ms" in _tersimpan:
    engine.param.debounce_time_ms = _tersimpan["debounce_ms"]
if "speed_hz" in _tersimpan:
    engine.param.motor_target_speed_hz = _tersimpan["speed_hz"]
if "brake_ms" in _tersimpan:
    engine.param.brake_delay_ms = _tersimpan["brake_ms"]
if "sort_dwell_ms" in _tersimpan:
    engine.param.sort_actuator_dwell_ms = _tersimpan["sort_dwell_ms"]


def scan_loop() -> None:
    next_scan = time.monotonic()
    while True:
        engine.step()
        next_scan += SCAN_MS / 1000
        sleep = next_scan - time.monotonic()
        if sleep > 0:
            time.sleep(sleep)
        else:
            next_scan = time.monotonic()


threading.Thread(target=scan_loop, daemon=True, name="plc-scan").start()


# ------------------------------------------------------------------ Auth
_sesi_aktif: dict[str, dict] = {}
TOKEN_USIA_S = 8 * 3600
bearer = HTTPBearer(auto_error=False)


def pengguna_saat_ini(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if creds is None or creds.credentials not in _sesi_aktif:
        raise HTTPException(status_code=401, detail="Tidak terautentikasi. Login dulu di /api/auth/login.")
    sesi = _sesi_aktif[creds.credentials]
    if time.time() > sesi["expires"]:
        del _sesi_aktif[creds.credentials]
        raise HTTPException(status_code=401, detail="Sesi kedaluwarsa. Login ulang.")
    return sesi


def wajib_role(*roles: str):
    def cek(sesi: dict = Depends(pengguna_saat_ini)) -> dict:
        if sesi["role"] not in roles:
            raise HTTPException(status_code=403, detail=f"Perlu peran: {' atau '.join(roles)}.")
        return sesi
    return cek


# ------------------------------------------------------------------ Models
class LoginBody(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=4, max_length=64)

class PerintahBody(BaseModel):
    perintah: str = Field(..., pattern="^(start|stop|estop|reset|reset_counter)$")

class ParamBody(BaseModel):
    debounce_ms: int | None = Field(None, ge=10, le=20)
    speed_hz: int | None = Field(None, ge=10, le=60)
    brake_ms: int | None = Field(None, ge=100, le=2000)
    sort_dwell_ms: int | None = Field(None, ge=100, le=3000)

class TutupShiftBody(BaseModel):
    username: str
    password: str

class IOTestBody(BaseModel):
    kanal: str = Field(..., pattern="^(sensor|aktuator|interlock|estop)$")
    nilai: bool

class GantiPasswordBody(BaseModel):
    password_lama: str
    password_baru: str = Field(..., min_length=8, max_length=64)

    @field_validator("password_baru")
    @classmethod
    def tidak_angka_saja(cls, v):
        if v.isdigit():
            raise ValueError("Password baru tidak boleh angka saja.")
        return v


# ------------------------------------------------------------------ Auth
@app.post("/api/auth/login", tags=["auth"], summary="Login → bearer token (usia 8 jam)")
def login(body: LoginBody):
    akun = db.autentikasi(body.username, body.password)
    if not akun:
        raise HTTPException(status_code=401, detail="Username atau password salah.")
    token = secrets.token_hex(32)
    _sesi_aktif[token] = {"username": akun["username"], "role": akun["role"], "expires": time.time() + TOKEN_USIA_S}
    return {"access_token": token, "token_type": "bearer", "expires_in": TOKEN_USIA_S, "role": akun["role"]}

@app.post("/api/auth/logout", tags=["auth"])
def logout(creds: HTTPAuthorizationCredentials = Depends(bearer), sesi: dict = Depends(pengguna_saat_ini)):
    _sesi_aktif.pop(creds.credentials, None)
    return {"ok": True, "detail": "Logout berhasil."}

@app.post("/api/auth/ganti-password", tags=["auth"])
def ganti_password(body: GantiPasswordBody, sesi: dict = Depends(pengguna_saat_ini)):
    if not db.autentikasi(sesi["username"], body.password_lama):
        raise HTTPException(status_code=401, detail="Password lama salah.")
    db.ganti_password(sesi["username"], body.password_baru)
    return {"ok": True, "detail": "Password diganti."}


# ------------------------------------------------------------------ Publik baca-saja
@app.get("/api/status", tags=["mesin"], summary="Status mesin real-time (publik)")
def status():
    return engine.snapshot()

@app.get("/api/parameter", tags=["mesin"], summary="Parameter kalibrasi aktif (publik baca)")
def get_parameter():
    return engine.snapshot()["parameter"]

@app.get("/api/laporan", tags=["laporan"], summary="RPT-4: laporan live + riwayat DB (publik baca)")
def laporan(tanggal: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")):
    c = engine.counter
    total = c.sorted + c.passed
    return {
        "live": {
            "report_date": tanggal or time.strftime("%Y-%m-%d"),
            "shift_number": db.hitung_shift_saat_ini(),
            "total_item_count": c.total,
            "passed_item_count": c.passed,
            "sorted_item_count": c.sorted,
            "uptime_minutes": c.uptime_minutes,
            "efficiency_percent": round((total / 500) * 100),
        },
        "riwayat": db.ambil_laporan(tanggal),
    }

@app.get("/api/alarm", tags=["alarm"], summary="Alarm aktif + riwayat permanen (publik baca)")
def alarm():
    aktif = []
    if engine._estop_latched:
        aktif.append({"alarm_code": "E-STOP", "description": "Emergency stop aktif — daya motor diputus (STO)."})
    if engine._fault_latched:
        aktif.append({"alarm_code": "ACT-STUCK", "description": "Aktuator sortir tidak kembali home dalam dwell."})
    return {"aktif": aktif, "riwayat": db.riwayat_alarm(50)}


# ------------------------------------------------------------------ Kontrol (auth)
@app.post("/api/kontrol", tags=["mesin"], summary="Start/Stop/E-Stop/Reset (supervisor atau teknisi)")
def kontrol(body: PerintahBody, sesi: dict = Depends(wajib_role("supervisor", "teknisi"))):
    hasil = engine.perintah(body.perintah)
    if not hasil.get("ok"):
        raise HTTPException(status_code=409, detail=hasil["detail"])
    if body.perintah == "estop":
        db.catat_alarm("E-STOP", f"E-Stop diaktifkan oleh {sesi['username']}.")
    if body.perintah == "reset":
        db.bersihkan_alarm("E-STOP")
        db.bersihkan_alarm("ACT-STUCK")
    return hasil

@app.put("/api/parameter", tags=["mesin"], summary="Kalibrasi (khusus teknisi; tersimpan DB)")
def set_parameter(body: ParamBody, sesi: dict = Depends(wajib_role("teknisi"))):
    perubahan = {}
    if body.debounce_ms is not None:
        engine.param.debounce_time_ms = body.debounce_ms
        perubahan["debounce_ms"] = body.debounce_ms
    if body.speed_hz is not None:
        engine.param.motor_target_speed_hz = body.speed_hz
        perubahan["speed_hz"] = body.speed_hz
    if body.brake_ms is not None:
        engine.param.brake_delay_ms = body.brake_ms
        perubahan["brake_ms"] = body.brake_ms
    if body.sort_dwell_ms is not None:
        engine.param.sort_actuator_dwell_ms = body.sort_dwell_ms
        perubahan["sort_dwell_ms"] = body.sort_dwell_ms
    if not perubahan:
        raise HTTPException(status_code=422, detail="Tidak ada parameter yang diisi.")
    db.simpan_parameter(perubahan, sesi["username"])
    return engine.snapshot()["parameter"]

@app.post("/api/laporan/tutup-shift", tags=["laporan"], summary="RPT-5: tutup shift (khusus supervisor; arsip DB)")
def tutup_shift(body: TutupShiftBody, sesi: dict = Depends(wajib_role("supervisor"))):
    akun = db.autentikasi(body.username, body.password)
    if not akun or akun["role"] != "supervisor":
        raise HTTPException(status_code=403, detail="Autentikasi supervisor gagal.")
    c = engine.counter
    total = c.sorted + c.passed
    shift = db.hitung_shift_saat_ini()
    row_id = db.simpan_shift(
        time.strftime("%Y-%m-%d"), shift,
        c.total, c.passed, c.sorted, c.uptime_minutes,
        round((total / 500) * 100), body.username,
    )
    engine.perintah("reset_counter")
    return {"ok": True, "id": row_id,
            "detail": f"Shift {shift} ditutup oleh {body.username}. Counter direset, data diarsipkan."}

@app.get("/api/laporan/ekspor", tags=["laporan"], summary="RPT-6: ekspor CSV dari DB")
def ekspor_csv(tanggal: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")):
    rows = db.ambil_laporan(tanggal)
    if not rows:
        c = engine.counter
        total = c.sorted + c.passed
        rows = [{"report_date": tanggal or time.strftime("%Y-%m-%d"),
                 "shift_number": db.hitung_shift_saat_ini(),
                 "total_item_count": c.total, "passed_item_count": c.passed,
                 "sorted_item_count": c.sorted, "uptime_minutes": c.uptime_minutes,
                 "efficiency_percent": round((total / 500) * 100), "closed_by": ""}]
    header = "report_date,shift_number,total_item_count,passed_item_count,sorted_item_count,uptime_minutes,efficiency_percent,closed_by\n"
    csv = header + "".join(
        f"{r['report_date']},{r['shift_number']},{r['total_item_count']},{r['passed_item_count']},"
        f"{r['sorted_item_count']},{r['uptime_minutes']},{r['efficiency_percent']},{r.get('closed_by','')}\n"
        for r in rows)
    nama = tanggal or time.strftime("%Y-%m-%d")
    return PlainTextResponse(csv, media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename=laporan-produksi-{nama}.csv"})


# ------------------------------------------------------------------ Diagnostik
@app.post("/api/diagnostik/io", tags=["diagnostik"], summary="I/O test manual (khusus teknisi)")
def io_test(body: IOTestBody, sesi: dict = Depends(wajib_role("teknisi"))):
    mapping = {"sensor": "in_objek", "aktuator": "in_aktuator_home",
               "interlock": "in_interlock", "estop": "in_estop"}
    setattr(engine, mapping[body.kanal], body.nilai)
    return {"ok": True, "kanal": body.kanal, "nilai": body.nilai, "oleh": sesi["username"]}

@app.get("/api/simulasi/objek", tags=["diagnostik"], summary="Kirim objek simulasi ke sensor")
def sim_objek():
    engine.stimulus_sensor(True)
    time.sleep(0.05)
    engine.stimulus_sensor(False)
    return {"ok": True, "detail": "Objek simulasi dikirim ke sensor."}


# ------------------------------------------------------------------ Static HMI
_FRONTEND = pathlib.Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(_FRONTEND), html=True), name="hmi")
