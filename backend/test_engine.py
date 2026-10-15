"""
test_engine.py — unit test engine PLC simulasi (pytest).
Jalankan: cd backend && python3 -m pytest test_engine.py -v
"""
import json
import os
import tempfile

import pytest

from engine import BRAKE_DWELL_MS, MesinState, PLCEngine, SCAN_MS, STATUS_LABEL


@pytest.fixture()
def engine(tmp_path):
    e = PLCEngine(persist_path=str(tmp_path / "counters.json"))
    e.param.sort_actuator_dwell_ms = 100  # percepat siklus untuk test
    return e


def jalankan(e, ms):
    for _ in range(ms // SCAN_MS):
        e.step()


def test_status_awal_idle(engine):
    assert engine.state == MesinState.IDLE
    assert not engine.out_motor


def test_start_dari_idle(engine):
    assert engine.perintah("start")["ok"]
    jalankan(engine, 20)
    assert engine.state == MesinState.RUNNING
    assert engine.out_motor


def test_start_dua_kali_ditolak(engine):
    engine.perintah("start")
    jalankan(engine, 20)
    assert not engine.perintah("start")["ok"]


def test_siklus_sortir_lengkap(engine):
    """SORT-1..4: objek → debounce → rem 400 ms → sortir → lanjut otomatis + CNT-1/2."""
    engine.perintah("start")
    jalankan(engine, 20)
    engine.stimulus_sensor(True)
    # debounce 15 ms: belum valid sebelum lewat
    jalankan(engine, 10)
    assert not engine.out_brake
    jalankan(engine, 20)                          # debounce 15 ms terlampaui → valid
    assert engine.state == MesinState.SORTING
    jalankan(engine, SCAN_MS)                     # siklus berikut: keluaran rem aktif
    assert engine.out_brake                       # SORT-2 rem sinkron
    jalankan(engine, BRAKE_DWELL_MS + 300)        # rem + dwell sortir (sortir terjadi)
    engine.stimulus_sensor(False)                 # objek lewat sensor — pulsa berakhir
    jalankan(engine, SCAN_MS * 2)
    assert engine.state == MesinState.RUNNING     # SORT-4 lanjut otomatis
    assert engine.counter.total == 1              # CNT-1
    assert engine.counter.sorted == 1             # CNT-2


def test_debounce_dedup(engine):
    """Pulsa singkat < debounce tidak dihitung (SORT-1)."""
    engine.perintah("start")
    jalankan(engine, 20)
    engine.stimulus_sensor(True)
    jalankan(engine, 10)                          # 10 ms < 15 ms debounce
    engine.stimulus_sensor(False)
    jalankan(engine, 200)
    assert engine.counter.total == 0


def test_estop_latched_sampai_reset(engine):
    """CTRL-3/5: E-Stop latch; reset hanya lepas bila rangkaian aman."""
    engine.perintah("start")
    jalankan(engine, 20)
    engine.perintah("estop")
    assert engine.state == MesinState.ESTOP
    assert not engine.out_motor
    # reset tanpa rangkaian E-Stop aman → tetap latch
    engine.in_estop = False
    engine.perintah("reset")
    jalankan(engine, 20)
    assert engine.state == MesinState.ESTOP
    # rangkaian aman → reset lulus
    engine.in_estop = True
    engine.perintah("reset")
    jalankan(engine, 20)
    assert engine.state == MesinState.IDLE


def test_stop_normal(engine):
    """CTRL-2: stop normal lewat STOPPING (deselerasi) → IDLE."""
    engine.perintah("start")
    jalankan(engine, 20)
    engine.perintah("stop")
    assert engine.state == MesinState.STOPPING
    jalankan(engine, 2200)
    assert engine.state == MesinState.IDLE
    assert not engine.out_brake


def test_fault_aktuator_tidak_home(engine):
    """Aktuator tidak kembali home dalam dwell → FAULT latched."""
    engine.perintah("start")
    jalankan(engine, 20)
    engine.in_aktuator_home = False
    engine.stimulus_sensor(True)
    jalankan(engine, 2000)
    assert engine.state == MesinState.FAULT
    engine.in_aktuator_home = True
    engine.perintah("reset")
    jalankan(engine, 20)
    assert engine.state == MesinState.IDLE


def test_counter_persisten(tmp_path):
    """RPT-3: counter bertahan antar instance (retentif)."""
    p = str(tmp_path / "c.json")
    e1 = PLCEngine(persist_path=p)
    e1.perintah("start")
    e1.counter.total = 7
    e1.counter.sorted = 5
    e1._simpan_persisten()
    e2 = PLCEngine(persist_path=p)
    assert e2.counter.total == 7
    assert e2.counter.sorted == 5


def test_reset_counter(engine):
    engine.perintah("start")
    jalankan(engine, 20)
    engine.stimulus_sensor(True)
    jalankan(engine, BRAKE_DWELL_MS + 300)
    engine.perintah("reset_counter")
    assert engine.counter.total == 0


def test_snapshot_bentuk(engine):
    s = engine.snapshot()
    for kunci in ("state", "state_label", "counters", "parameter"):
        assert kunci in s
    assert STATUS_LABEL[engine.state] == s["state_label"]


def test_file_persisten_json_valid(tmp_path):
    p = tmp_path / "c.json"
    e = PLCEngine(persist_path=str(p))
    e._simpan_persisten()
    data = json.loads(p.read_text())
    assert set(data) == {"total", "sorted", "passed", "uptime_minutes"}
