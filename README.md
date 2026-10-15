# Konveyor PLC — Smart Conveyor Sorting & Daily Production Counter System

Implementasi PRD v0.1 (draft) — **Keduanya: Software (simulasi full-stack + database + REST API) + Hardware (kode PLC IEC 61131-3)**.

## Struktur

```
konveyor-plc/
├── plc/                      # HARDWARE — kode PLC (Siemens S7-1200, IEC 61131-3 ST)
│   ├── FB_ConveyorControl.scl    # CTRL-1..5, SORT-1..4 (state machine, debounce, brake sync, interlock, E-Stop STO)
│   └── FB_ProductionCounter.scl  # CNT-1..2, RPT-3..6 (counter retentif, shift 3×8 jam, DB daily summary, CSV)
├── backend/                  # SOFTWARE — engine simulasi + REST API + database
│   ├── engine.py                 # Mirror 1:1 logika SCL ke Python, scan cycle 10 ms, counter persisten
│   ├── main.py                   # FastAPI: auth token, kontrol, parameter, laporan, tutup-shift, CSV, alarm, diagnostik
│   ├── db.py                     # SQLite WAL: 4 tabel sesuai model data PRD Bab 8
│   └── requirements.txt
├── frontend/                 # SOFTWARE — HMI web responsif (WCAG 2.2 AA, dark mode, Bahasa Indonesia)
│   ├── index.html                # Kendali: status, indikator I/O, Start/Stop/Reset/E-STOP
│   ├── penghitung.html           # Counter + parameter kalibrasi teknisi
│   ├── laporan.html              # RPT-4 ringkasan + RPT-6 ekspor CSV + RPT-5 tutup shift
│   ├── diagnostik.html           # I/O test manual + simulator objek
│   ├── docs.html                 # Dokumentasi API di dalam HMI
│   ├── tokens.css                # Satu file token (kontras diverifikasi WCAG AA)
│   ├── shell.css / shell.js      # Layout mobile-first, drawer <lg, tema gelap/terang persisten
│   ├── components.css / components.js  # Komponen tunggal: toast, modal, konfirmasi, loading/empty/error
│   ├── api-client.js             # Fetch wrapper terpusat + ApiError
│   ├── format.js                 # Utilitas format seragam (id-ID)
│   └── hmi-app.js                # Logika modul (poll 500 ms)
└── README.md
```

## Parameter disetujui (Bab 12 + asumsi Bab 5)

| Parameter | Nilai |
|---|---|
| Kecepatan belt | 0,5 m/s (25 Hz VFD) |
| Jarak sensor → titik rem | 200 mm → dwell rem **400 ms** |
| Shift | 3 × 8 jam (06–14, 14–22, 22–06) |
| Sensor | Induktif PNP NO, debounce **15 ms** (rentang PRD 10–20) |
| Aktuator | Pneumatik, dwell default 500 ms (kalibrasi teknisi) |

## Jalankan

```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn main:app --port 8600
# HMI      → http://localhost:8600
# API docs → http://localhost:8600/docs   (Swagger UI interaktif)
#          → http://localhost:8600/redoc  (ReDoc)
```

## Akun bawaan (WAJIB ganti setelah login pertama)

| Username | Password awal | Peran | Hak |
|---|---|---|---|
| `supervisor` | `2580` | supervisor | Kontrol mesin, tutup shift, ekspor CSV |
| `teknisi` | `teknisi2026` | teknisi | Kontrol mesin, **kalibrasi parameter**, I/O test |

Ganti password: `POST /api/auth/ganti-password` (min 8 karakter, tidak boleh angka saja).
Hash: **PBKDF2-HMAC-SHA256, 200.000 iterasi** (stdlib, tanpa dependensi).
Set salt produksi via env `HMI_PIN_SALT`.

## Database (SQLite, mode WAL — `backend/hmi.db`, ubah via env `HMI_DB`)

| Tabel | Isi |
|---|---|
| `daily_production_summary` | Arsip per shift, UNIQUE(tanggal, shift) — total/lolos/tersortir/uptime/efisiensi + penutup shift |
| `alarm_log` | Semua alarm: kode, deskripsi, `raised_at`, `cleared_at` |
| `system_parameter` | Kalibrasi tersimpan — dimuat ulang otomatis saat restart |
| `user_account` | Akun + hash PBKDF2; role CHECK ('supervisor','teknisi') |

Counter mesin juga retentif: bertahan mati listrik (persisten, mirror `VAR_RETAIN` PLC).

## REST API ringkas (detail lengkap: `/docs` atau halaman API Docs di HMI)

| Metode | Path | Auth | Fungsi |
|---|---|---|---|
| POST | `/api/auth/login` | — | Bearer token (8 jam) |
| POST | `/api/auth/logout` | ✓ | Hapus sesi |
| POST | `/api/auth/ganti-password` | ✓ | Ganti password sendiri |
| GET | `/api/status` | — | State, I/O, counter, VFD real-time |
| GET | `/api/parameter` | — | Kalibrasi aktif |
| PUT | `/api/parameter` | teknisi | Ubah kalibrasi (validasi rentang PRD) → DB |
| POST | `/api/kontrol` | sup/tek | `start`\|`stop`\|`estop`\|`reset`\|`reset_counter` |
| GET | `/api/laporan` | — | Live + riwayat (`?tanggal=YYYY-MM-DD`) |
| POST | `/api/laporan/tutup-shift` | supervisor | Arsip DB + reset counter |
| GET | `/api/laporan/ekspor` | — | Unduh CSV dari DB |
| GET | `/api/alarm` | — | Aktif + riwayat 50 |
| POST | `/api/diagnostik/io` | teknisi | Paksa I/O per kanal |
| GET | `/api/simulasi/objek` | — | Objek demo (siklus SORT-1..4) |

Endpoint publik baca-saja disengaja untuk display pabrik/wallboard. Semua perubahan state butuh token.

## CI/CD

`.github/workflows/ci.yml` siap: push/PR ke `main` → lint (compileall) → unit test engine → integrasi test API → build & push image ke `ghcr.io/hardihardi/konveyor-plc` (cache GHA).

> **Status (jujur):** job GitHub Actions gagal start dengan *"account is locked due to a billing issue"* — akun free perlu membuka **Settings → Billing** (atau spending limit $0 untuk free tier) agar runner bisa dipakai. Semua 26 test **sudah diverifikasi lolos secara lokal** (`pytest test_engine.py test_api.py`), dan image Docker **sudah terverifikasi build + jalan sehat** di mesin lokal.

Jalankan lokal (tanpa GitHub Actions):

```bash
cd backend
python3 -m pytest test_engine.py test_api.py -v   # 26 test

# Docker
docker build -t konveyor-plc .
docker run -p 8600:8600 -e HMI_PIN_SALT="salt-rahasia-anda" konveyor-plc
# atau: docker compose up -d
```

## Deploy hardware (PLC)

Import `plc/*.scl` ke TIA Portal (S7-1200), mapping I/O:
- `xObjekTerdeteksi` → sensor induktif (I0.0)
- `xAktuatorHome` → sensor reed aktuator (I0.1)
- `xEStop` → safety relay NC (I0.2) — cat-0 STO ke VFD
- `xMotorRun` → VFD Modbus RTU / terminal 24 V
- `xSortirAktif` → solenoid pneumatik (Q0.0)

## Ketertelusuran PRD & standar

- Semua modul berkomentar dengan ID PRD (CTRL-N, SORT-N, CNT-N, RPT-N).
- Kebutuhan Fase Lanjutan (barcode `item_barcode`, `erp_sync_status`, machine vision, MQTT/OPC-UA) **tidak dibangun** sesuai Bab 4.2 + 11.
- Kontras token diverifikasi WCAG 2.2 AA; fokus keyboard selalu terlihat; target sentuh ≥44 px; `prefers-reduced-motion` dihormati.
- Tanpa placeholder/TODO/dead code; validasi input di klien (HTML) dan server (Pydantic: HTTP 422/401/403/409).
