// hmi-app.js — aplikasi HMI utama: modul Kendali, Penghitung, Laporan, Diagnostik.
// Semua akses API lewat api-client.js; semua format lewat format.js; UI lewat components.js.

import { apiGet, apiPost, apiPut, ApiError, ENDPOINT } from "./api-client.js";
import { formatAngka, formatWaktu } from "./format.js";
import { toast, konfirmasi } from "./components.js";

const POLL_MS = 500;
const halamanAktif = document.querySelector("[data-halaman-aktif]")?.dataset.halamanAktif ?? "kendali";

const LABEL_STATUS = {
  idle: { teks: "Siaga", kelas: "chip--netral" },
  running: { teks: "Berjalan", kelas: "chip--sukses" },
  stopping: { teks: "Menghentikan", kelas: "chip--peringatan" },
  sorting: { teks: "Menyortir", kelas: "chip--info" },
  fault: { teks: "Gangguan", kelas: "chip--gagal" },
  estop: { teks: "DARURAT", kelas: "chip--gagal" },
};

const LABEL_IO = {
  sensor: "Sensor kedekatan",
  aktuator: "Aktuator sortir",
  interlock: "Interlock pagar",
  estop: "Rangkaian E-Stop",
};

function statusChip(state) {
  const s = LABEL_STATUS[state] ?? { teks: state, kelas: "chip--netral" };
  return `<span class="chip ${s.kelas}" role="status">${s.teks}</span>`;
}

function angkaAtauGaris(v) {
  return (v === null || v === undefined) ? "—" : formatAngka(v);
}

/* ------------------------------------------------------------------ Modul Kendali */
async function muatKendali() {
  const root = document.getElementById("panel-kendali");
  try {
    const s = await apiGet(ENDPOINT.status);
    document.getElementById("status-mesin").innerHTML = statusChip(s.state);
    document.getElementById("status-motor").textContent = s.motor_run ? "ON" : "OFF";
    document.getElementById("status-brake").textContent = s.brake_sync ? "Aktif" : "Bebas";
    document.getElementById("status-sortir").textContent = s.sortir_aktif ? "Dorong" : "Home";
    document.getElementById("frekuensi-vfd").textContent = angkaAtauGaris(s.vfd_frequency_hz) + " Hz";

    document.getElementById("btn-start").disabled = s.state !== "idle";
    document.getElementById("btn-stop").disabled = !(s.state === "running" || s.state === "sorting");
    document.getElementById("btn-estop").disabled = false;
    const perluReset = s.state === "estop" || s.state === "fault";
    document.getElementById("btn-reset").disabled = !perluReset;

    document.getElementById("lampu-estop").classList.toggle("lampu--merah", s.estop_latched);
    document.getElementById("lampu-interlock").classList.toggle("lampu--hijau", s.interlock_ok);
    document.getElementById("lampu-sensor").classList.toggle("lampu--kuning", s.sensor_objek);

    const alarmBox = document.getElementById("daftar-alarm");
    if (s.estop_latched || s.state === "fault") {
      alarmBox.innerHTML = `<li>${s.estop_latched
        ? "E-Stop aktif — daya motor diputus (STO). Tekan Reset setelah kondisi aman."
        : "Aktuator tidak kembali home dalam dwell. Periksa udara pneumatik."}</li>`;
      alarmBox.hidden = false;
    } else {
      alarmBox.hidden = true;
    }
  } catch (e) {
    if (!(e instanceof ApiError)) console.warn("poll gagal:", e);
  }
}

function pasangKendali() {
  const aksi = async (perintah, konfirmasi) => {
    if (konfirmasi) {
      const lanjut = await konfirmasi("Konfirmasi E-Stop", "Daya motor akan diputus seketika (STO). Lanjutkan?");
      if (!lanjut) return;
    }
    try {
      const r = await apiPost(ENDPOINT.kontrol, { perintah });
      toast(r.state ? `Mesin: ${r.state}` : "Perintah terkirim", "sukses");
      muatKendali();
    } catch (e) {
      toast(e.detail ?? "Perintah gagal", "gagal");
    }
  };
  document.getElementById("btn-start").addEventListener("click", () => aksi("start"));
  document.getElementById("btn-stop").addEventListener("click", () => aksi("stop"));
  document.getElementById("btn-estop").addEventListener("click", () =>
    aksi("estop", "Aktifkan E-Stop? Daya motor akan diputus seketika (STO)."));
  document.getElementById("btn-reset").addEventListener("click", () => aksi("reset"));
}

/* ------------------------------------------------------------------ Modul Penghitung */
async function muatPenghitung() {
  try {
    const s = await apiGet(ENDPOINT.status);
    document.getElementById("cnt-total").textContent = angkaAtauGaris(s.counters.total);
    document.getElementById("cnt-tersortir").textContent = angkaAtauGaris(s.counters.sorted);
    document.getElementById("cnt-lolos").textContent = angkaAtauGaris(s.counters.passed);
    document.getElementById("cnt-uptime").textContent = `${s.counters.uptime_minutes} menit`;
    document.getElementById("v-debounce").textContent = `${s.parameter.debounce_ms} ms`;
    document.getElementById("v-speed").textContent = `${s.parameter.speed_hz} Hz`;
    document.getElementById("v-brake").textContent = `${s.parameter.brake_ms} ms`;
    document.getElementById("v-dwell").textContent = `${s.parameter.sort_dwell_ms} ms`;
  } catch (e) {
    if (!(e instanceof ApiError)) console.warn("poll gagal:", e);
  }
}

function pasangParameter() {
  const form = document.getElementById("form-parameter");
  form?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const fd = new FormData(form);
    const baca = (k) => (fd.get(k) === "" || fd.get(k) === null ? null : Number(fd.get(k)));
    const body = {
      debounce_ms: baca("debounce_ms"),
      speed_hz: baca("speed_hz"),
      brake_ms: baca("brake_ms"),
      sort_dwell_ms: baca("sort_dwell_ms"),
    };
    try {
      await apiPut(ENDPOINT.parameter, body);
      toast("Parameter kalibrasi tersimpan", "sukses");
      muatPenghitung();
    } catch (e) {
      toast(e.detail ?? "Gagal menyimpan parameter", "gagal");
    }
  });
}


/* ------------------------------------------------------------------ Modul Laporan */
async function muatLaporan() {
  const root = document.getElementById("panel-laporan");
  if (!root) return;
  try {
    const l = await apiGet(ENDPOINT.laporan);
    document.getElementById("rpt-tanggal").textContent = l.report_date;
    document.getElementById("rpt-shift").textContent = `Shift ${l.shift_number}`;
    document.getElementById("rpt-total").textContent = angkaAtauGaris(l.total_item_count);
    document.getElementById("rpt-lolos").textContent = angkaAtauGaris(l.passed_item_count);
    document.getElementById("rpt-tersortir").textContent = angkaAtauGaris(l.sorted_item_count);
    document.getElementById("rpt-uptime").textContent = `${l.uptime_minutes} menit`;
    document.getElementById("rpt-efisiensi").textContent = `${l.efficiency_percent}%`;

    const tombol = document.getElementById("btn-ekspor");
    tombol.onclick = () => { window.location.href = ENDPOINT.eksporCsv; };

    const tutup = document.getElementById("form-tutup-shift");
    tutup.onsubmit = async (ev) => {
      ev.preventDefault();
      const pin = new FormData(tutup).get("pin") ?? "";
      const lanjut = await konfirmasi("Konfirmasi Tutup Shift", "Semua penghitung harian direset dan diarsipkan. Lanjutkan?");
      if (!lanjut) return;
      try {
        const r = await apiPost(ENDPOINT.tutupShift, { pin });
        toast(r.detail, "sukses");
        tutup.reset();
        muatLaporan();
      } catch (e) {
        toast(e.detail ?? "PIN salah", "gagal");
      }
    };
  } catch (e) {
    if (!(e instanceof ApiError)) console.warn("poll gagal:", e);
  }
}

/* ------------------------------------------------------------------ Modul Diagnostik */
function pasangDiagnostik() {
  const form = document.getElementById("form-io");
  form?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const fd = new FormData(form);
    try {
      await apiPost(ENDPOINT.ioTest, { kanal: fd.get("kanal"), nilai: fd.get("nilai") === "true" });
      toast(`I/O ${LABEL_IO[fd.get("kanal")]} disetel`, "sukses");
    } catch (e) {
      toast(e.detail ?? "Pengetesan gagal", "gagal");
    }
  });

  document.getElementById("btn-objek-sim")?.addEventListener("click", async () => {
    try {
      await apiGet(ENDPOINT.simObjek);
      toast("Objek simulasi dikirim ke sensor", "info");
    } catch (e) {
      toast(e.detail ?? "Gagal", "gagal");
    }
  });
}

/* ------------------------------------------------------------------ Init */
function init() {
  if (halamanAktif === "kendali") {
    pasangKendali();
    muatKendali();
    setInterval(muatKendali, POLL_MS);
  } else if (halamanAktif === "penghitung") {
    pasangParameter();
    muatPenghitung();
    setInterval(muatPenghitung, POLL_MS);
  } else if (halamanAktif === "laporan") {
    muatLaporan();
    setInterval(muatLaporan, 2000);
  } else if (halamanAktif === "diagnostik") {
    pasangDiagnostik();
  }
}

document.readyState === "loading"
  ? document.addEventListener("DOMContentLoaded", init)
  : init();
