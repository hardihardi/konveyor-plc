"""
test_api.py — test integrasi REST API (pytest + httpx/TestClient, tanpa server hidup).
Jalankan: cd backend && python3 -m pytest test_api.py -v
"""
import os
import tempfile

os.environ["HMI_DB"] = tempfile.mktemp(suffix=".db")  # DB test terpisah, sebelum import main

import pytest
from fastapi.testclient import TestClient

import db
import main


@pytest.fixture(scope="session")
def client():
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    db._local.conn = None
    db.inisialisasi()
    return TestClient(main.app)


@pytest.fixture(scope="session")
def tok_sup(client):
    r = client.post("/api/auth/login", json={"username": "supervisor", "password": "2580"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def tok_tek(client):
    r = client.post("/api/auth/login", json={"username": "teknisi", "password": "teknisi2026"})
    return r.json()["access_token"]


def test_openapi_tersedia(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert len(r.json()["paths"]) >= 12


def test_status_publik(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    assert "state" in r.json() and "counters" in r.json()


def test_kontrol_butuh_auth(client):
    assert client.post("/api/kontrol", json={"perintah": "start"}).status_code == 401


def test_login_salah(client):
    # password < 4 char ditolak validasi (422); password panjang tapi salah → 401
    assert client.post("/api/auth/login", json={"username": "supervisor", "password": "xxxx"}).status_code == 401


def test_role_supervisor_tidak_bisa_kalibrasi(client, tok_sup):
    r = client.put("/api/parameter", json={"debounce_ms": 18},
                   headers={"Authorization": f"Bearer {tok_sup}"})
    assert r.status_code == 403


def test_teknisi_kalibrasi_tersimpan_db(client, tok_tek):
    r = client.put("/api/parameter", json={"debounce_ms": 20},
                   headers={"Authorization": f"Bearer {tok_tek}"})
    assert r.status_code == 200 and r.json()["debounce_ms"] == 20
    assert db.ambil_parameter()["debounce_ms"] == 20


def test_parameter_validasi_rentang(client, tok_tek):
    # SORT-1 rentang PRD 10–20 ms — 30 harus 422
    r = client.put("/api/parameter", json={"debounce_ms": 30},
                   headers={"Authorization": f"Bearer {tok_tek}"})
    assert r.status_code == 422


def test_siklus_kontrol_lengkap(client, tok_sup):
    h = {"Authorization": f"Bearer {tok_sup}"}
    assert client.post("/api/kontrol", json={"perintah": "start"}, headers=h).status_code == 200
    client.get("/api/simulasi/objek")
    import time; time.sleep(1.3)
    s = client.get("/api/status").json()
    assert s["counters"]["total"] >= 1
    assert client.post("/api/kontrol", json={"perintah": "estop"}, headers=h).status_code == 200
    assert client.get("/api/status").json()["state"] == "estop"
    assert client.post("/api/kontrol", json={"perintah": "reset"}, headers=h).status_code == 200


def test_alarm_riwayat(client, tok_sup):
    r = client.get("/api/alarm")
    assert r.status_code == 200
    assert "aktif" in r.json() and "riwayat" in r.json()


def test_tutup_shift_arsip_db(client, tok_sup):
    h = {"Authorization": f"Bearer {tok_sup}"}
    r = client.post("/api/laporan/tutup-shift",
                    json={"username": "supervisor", "password": "2580"}, headers=h)
    assert r.status_code == 200
    riwayat = client.get("/api/laporan").json()["riwayat"]
    assert len(riwayat) >= 1
    assert riwayat[0]["closed_by"] == "supervisor"


def test_tutup_shift_password_salah(client, tok_sup):
    h = {"Authorization": f"Bearer {tok_sup}"}
    r = client.post("/api/laporan/tutup-shift",
                    json={"username": "supervisor", "password": "bukan"}, headers=h)
    assert r.status_code == 403


def test_ekspor_csv(client):
    r = client.get("/api/laporan/ekspor")
    assert r.status_code == 200
    assert r.text.startswith("report_date,shift_number,")


def test_ganti_password_dan_login_ulang(client, tok_tek):
    h = {"Authorization": f"Bearer {tok_tek}"}
    r = client.post("/api/auth/ganti-password",
                    json={"password_lama": "teknisi2026", "password_baru": "TeknisiBaru2026!"},
                    headers=h)
    assert r.status_code == 200
    # login dengan password baru
    r2 = client.post("/api/auth/login", json={"username": "teknisi", "password": "TeknisiBaru2026!"})
    assert r2.status_code == 200
    # kembalikan agar test idempoten bila diulang
    client.post("/api/auth/ganti-password",
                json={"password_lama": "TeknisiBaru2026!", "password_baru": "teknisi2026"},
                headers={"Authorization": f"Bearer {r2.json()['access_token']}"})


def test_logout_menghapus_sesi(client):
    r = client.post("/api/auth/login", json={"username": "supervisor", "password": "2580"})
    tok = r.json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.post("/api/auth/logout", headers=h).status_code == 200
    assert client.get("/api/laporan") .status_code == 200  # publik tetap bisa
    assert client.post("/api/kontrol", json={"perintah": "start"}, headers=h).status_code == 401
