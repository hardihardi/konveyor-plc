# Konveyor PLC — Smart Conveyor Sorting & Daily Production Counter System

Implementasi PRD v0.1 (draft) — **Keduanya: Software (simulasi full-stack) + Hardware (kode PLC IEC 61131-3)**.

## Struktur

```
konveyor-plc/
├── plc/                      # HARDWARE — kode PLC (Siemens S7-1200, IEC 61131-3 ST)
│   ├── FB_ConveyorControl.scl    # CTRL-1..5, SORT-1..4 (state machine, debounce, brake sync, interlock, E-Stop STO)
│   └── FB_ProductionCounter.scl  # CNT-1..2, RPT-3..6 (counter retentif, shift 3×8 jam, DB daily summary, CSV)
├── backend/                  # SOFTWARE — engine simulasi + API
│   ├── engine.py                 # Mirror 1:1 logika SCL ke Python, scan cycle 10 ms, counter persisten (retentif)
│   └── main.py                   # FastAPI: status, kontrol, parameter, laporan, tutup-shift (PIN), ekspor CSV, diagnostik I/O, simulator objek
├── frontend/                 # SOFTWARE — HMI web responsif (WCAG 2.2 AA, dark mode wajib, Bahasa Indonesia)
│   ├── index.html                # Kendali: status, indikator I/O, Start/Stop/Reset/E-STOP
│   ├── penghitung.html           # Counter + parameter kalibrasi teknisi
│   ├── laporan.html              # RPT-4 ringkasan + RPT-6 ekspor CSV + RPT-5 tutup shift (PIN supervisor)
│   ├── diagnostik.html           # I/O test manual + simulator objek
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

## Jalankan (software)

```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn main:app --port 8600
# Buka http://localhost:8600
```

PIN supervisor default: **2580** — WAJIB ganti lewat env `HMI_PIN_SALT` sebelum produksi.

## Deploy hardware (PLC)

Import `plc/*.scl` ke TIA Portal (S7-1200), mapping I/O:
- `xObjekTerdeteksi` → input sensor induktif (I0.0)
- `xAktuatorHome` → sensor reed aktuator (I0.1)
- `xEStop` → safety relay NC (I0.2) — cat-0 STO ke VFD
- `xMotorRun` → VFD Modbus RTU / terminal 24 V
- `xSortirAktif` → solenoid pneumatik (Q0.0)

## Ketertelusuran PRD

Semua modul berkomentar dengan ID PRD (CTRL-N, SORT-N, CNT-N, RPT-N). Kebutuhan Fase Lanjutan (barcode, erp_sync, machine vision, MQTT/OPC-UA) **tidak dibangun** sesuai Bab 4.2 + 11.
