# Konveyor PLC

Sistem sortir konveyor otomatis dengan penghitung produksi harian — lengkap dari sisi **software** (simulator + HMI web + database + REST API) dan **hardware** (program PLC Siemens S7-1200).

> Implementasi dari PRD v0.1 (draft). Setiap modul diberi komentar ID PRD-nya (CTRL-N, SORT-N, CNT-N, RPT-N) supaya mudah dilacak balik ke dokumen kebutuhan.

---

## Apa yang dikerjakan sistem ini

Sebuah konveyor membawa barang melewati sensor. Saat barang terdeteksi, mesin mengerem sabuk tepat di titik sortir, menyalakan aktuator pneumatik untuk mendorong barang keluar, lalu melanjutkan lagi — semua otomatis. Setiap barang masuk, keluar lewat sortir, atau lolos tanpa tersortir tercatat, diarsipkan per shift, dan bisa diekspor ke CSV untuk laporan harian.

Fitur utama:

- **Kendali mesin** — Start, Stop, Reset, dan E-Stop yang ter-latch (harus di-reset setelah kondisi aman).
- **Penghitung retentif** — angka produksi tidak hilang saat listrik mati.
- **Laporan per shift** — 3 shift × 8 jam, ditutup oleh supervisor dengan autentikasi.
- **Grafik tren** — riwayat arsip digambar langsung di HMI, ikut tema gelap/terang.
- **Alarm log permanen** — setiap E-Stop dan gangguan aktuator tercatat di database.
- **Kalibrasi terlindungi** — hanya peran teknisi yang boleh mengubah parameter.

---

## Struktur proyek

```
konveyor-plc/
├── plc/                        Program PLC (Siemens S7-1200, IEC 61131-3 Structured Text)
│   ├── FB_ConveyorControl.scl      Mesin status: CTRL-1..5, SORT-1..4
│   └── FB_ProductionCounter.scl    Penghitung & laporan: CNT-1..2, RPT-3..6
│
├── backend/                    Simulator + REST API + database
│   ├── engine.py                   Mirror logika SCL ke Python, siklus scan 10 ms
│   ├── main.py                     Endpoint FastAPI + autentikasi bearer token
│   ├── db.py                       SQLite (mode WAL), 4 tabel
│   ├── test_engine.py              11 unit test engine
│   ├── test_api.py                 15 test integrasi API
│   └── requirements.txt
│
├── frontend/                   HMI web — Bahasa Indonesia, WCAG 2.2 AA, dark mode
│   ├── login.html                  Halaman masuk (sesi 8 jam)
│   ├── index.html                  Kendali mesin: status, indikator I/O, tombol operasi
│   ├── penghitung.html             Counter produksi + parameter kalibrasi
│   ├── laporan.html                Ringkasan harian + tutup shift + ekspor CSV
│   ├── tren.html                   Grafik tren produksi (canvas, tanpa dependensi)
│   ├── diagnostik.html             Pengetesan I/O manual + simulator objek
│   ├── docs.html                   Dokumentasi API di dalam HMI
│   ├── tokens.css                  Satu-satunya sumber nilai visual (kontras lolos WCAG AA)
│   ├── shell.css / shell.js        Layout mobile-first + drawer + tema
│   ├── components.css / js         Komponen bersama: toast, modal, konfirmasi
│   ├── api-client.js               Pembungkus fetch terpusat
│   ├── auth.js                     Penjaga sesi sisi klien
│   ├── chart.js                    Penggambar grafik tren
│   └── hmi-app.js                  Logika modul (pembaruan tiap 500 ms)
│
├── .github/workflows/ci.yml    CI: test → build → push image ke GHCR
├── Dockerfile                  Image produksi (non-root + healthcheck)
└── docker-compose.yml          Deploy satu perintah
```

---

## Menjalankan

### Cara tercepat — Docker

```bash
docker compose up -d
```

Buka **http://localhost:8600** — selesai. Data tersimpan di volume Docker sehingga tetap ada setelah container di-rebuild.

### Tanpa Docker (pengembangan)

```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn main:app --port 8600
```

| Alamat | Isi |
|---|---|
| `http://localhost:8600` | HMI (antarmuka operator) |
| `http://localhost:8600/docs` | Swagger UI — coba API langsung dari browser |
| `http://localhost:8600/redoc` | ReDoc — tampilan referensi API |

### Menjalankan test

```bash
cd backend
python3 -m pytest test_engine.py test_api.py -v
```

26 test: logika sortir lengkap, debounce, E-Stop latch, counter retentif, autentikasi, hak akses per peran, arsip shift, sampai ekspor CSV.

---

## Akun bawaan

⚠️ **Ganti password sebelum dipakai sungguhan** — lewat menu profil atau `POST /api/auth/ganti-password`.

| Username | Password awal | Boleh apa |
|---|---|---|
| `supervisor` | `2580` | Kendali mesin, tutup shift, ekspor laporan |
| `teknisi` | `teknisi2026` | Kendali mesin, kalibrasi parameter, tes I/O |

Password di-hash dengan PBKDF2-HMAC-SHA256 (200.000 iterasi). Ganti nilai `HMI_PIN_SALT` di environment sebelum produksi — ini salt untuk semua hash password.

---

## Parameter produksi

Nilai-nilai ini disepakati saat analisis kebutuhan (Bab 12 + asumsi Bab 5 PRD):

| Parameter | Nilai | Catatan |
|---|---|---|
| Kecepatan sabuk | 0,5 m/s (25 Hz) | Via VFD |
| Jarak sensor → titik rem | 200 mm | Setara dwell rem **400 ms** |
| Shift kerja | 3 × 8 jam | 06–14, 14–22, 22–06 |
| Sensor | Induktif PNP NO | Debounce **15 ms** (rentang PRD 10–20 ms) |
| Aktuator | Pneumatik | Dwell 500 ms, bisa dikalibrasi teknisi |

---

## REST API

Daftar lengkap dengan contoh ada di `http://localhost:8600/docs` atau halaman **API Docs** di dalam HMI. Ringkasannya:

| Metode | Path | Hak akses | Fungsi |
|---|---|---|---|
| POST | `/api/auth/login` | terbuka | Dapat bearer token (berlaku 8 jam) |
| POST | `/api/auth/logout` | login | Akhiri sesi |
| POST | `/api/auth/ganti-password` | login | Ganti password sendiri |
| GET | `/api/status` | terbuka | Status mesin real-time |
| GET | `/api/parameter` | terbuka | Nilai kalibrasi aktif |
| PUT | `/api/parameter` | teknisi | Ubah kalibrasi (tersimpan di DB) |
| POST | `/api/kontrol` | sup/tek | `start` · `stop` · `estop` · `reset` · `reset_counter` |
| GET | `/api/laporan` | terbuka | Laporan live + riwayat (`?tanggal=YYYY-MM-DD`) |
| POST | `/api/laporan/tutup-shift` | supervisor | Arsipkan shift ke DB, reset counter |
| GET | `/api/laporan/ekspor` | terbuka | Unduh CSV |
| GET | `/api/alarm` | terbuka | Alarm aktif + riwayat 50 terakhir |
| POST | `/api/diagnostik/io` | teknisi | Paksa nilai I/O per kanal |
| GET | `/api/simulasi/objek` | terbuka | Kirim objek simulasi (demo tanpa hardware) |

Endpoint yang terbuka sengaja dibaca-saja — untuk dipasang di layar pabrik tanpa login. Segala yang mengubah kondisi mesin wajib token.

### Contoh satu siklus

```bash
TOK=$(curl -s -X POST http://localhost:8600/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"supervisor","password":"2580"}' | jq -r .access_token)

curl -X POST http://localhost:8600/api/kontrol \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"perintah":"start"}'

curl http://localhost:8600/api/simulasi/objek   # demo: satu barang lewat
curl http://localhost:8600/api/status | jq .counters
```

---

## Database

Satu file SQLite (`backend/hmi.db`, bisa dipindah lewat `HMI_DB`) dengan mode WAL. Empat tabel:

| Tabel | Isi |
|---|---|
| `daily_production_summary` | Arsip per shift — unik per (tanggal, shift); total, lolos, tersortir, uptime, efisiensi, penutup |
| `alarm_log` | Kode alarm, deskripsi, waktu naik dan waktu bersih |
| `system_parameter` | Kalibrasi; dimuat ulang otomatis saat aplikasi start |
| `user_account` | Akun + hash PBKDF2, peran supervisor/teknisi |

---

## Deploy ke PLC sungguhan

Import kedua file `plc/*.scl` ke TIA Portal (S7-1200), lalu petakan I/O:

| Variabel | Perangkat | Terminal |
|---|---|---|
| `xObjekTerdeteksi` | Sensor induktif | I0.0 |
| `xAktuatorHome` | Sensor reed posisi aktuator | I0.1 |
| `xEStop` | Safety relay (kontak NC) | I0.2 — STO cat-0 ke VFD |
| `xMotorRun` | Perintah run VFD | Modbus RTU / terminal 24 V |
| `xSortirAktif` | Solenoid pneumatik | Q0.0 |

---

## CI/CD

`.github/workflows/ci.yml` berjalan pada setiap push ke `main`: lint → unit test → test integrasi → build image → push ke `ghcr.io/hardihardi/konveyor-plc`.

> **Catatan jujur:** runner GitHub Actions akun ini sedang terkunci billing ("account is locked due to a billing issue"). Workflow sudah benar dan tertes secara lokal — 26/26 pytest lolos dan image Docker terverifikasi jalan sehat. Setelah billing aktif di Settings → Billing, pipeline jalan tanpa perubahan apa pun.

---

## Batasan yang disengaja

Sesuai PRD (Bab 4.2 dan 11), hal-hal berikut **sengaja tidak dibangun** dan menunggu permintaan:

- Barcode scanner (`item_barcode`) dan sinkronisasi ERP (`erp_sync_status`)
- Pemeriksaan visual (machine vision)
- Komunikasi MQTT / OPC-UA

## Standar yang dipegang

- Kontras warna diverifikasi WCAG 2.2 AA; fokus keyboard selalu terlihat; target sentuh minimal 44×44 px; animasi menghormati `prefers-reduced-motion`.
- Validasi input di dua sisi: atribut HTML di klien, Pydantic di server (balasan 422/401/403/409 yang jelas).
- Tanpa placeholder, tanpa TODO, tanpa dead code — semua nilai visual merujuk satu file token.
