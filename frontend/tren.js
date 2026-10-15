// tren.js — halaman tren: muat riwayat, gambar chart, isi tabel, redraw saat resize/tema ganti.
import { apiGet } from "./api-client.js";
import { formatAngka } from "./format.js";
import { gambarTren } from "./chart.js";

const TARGET_SHIFT = 500;

function isiSemua(data) {
  const canvas = document.getElementById("chart-tren");
  gambarTren(canvas, data, { target: TARGET_SHIFT });

  const tbody = document.getElementById("tren-tbody");
  if (data.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="teks-bantu">Belum ada arsip. Data muncul setelah shift ditutup supervisor.</td></tr>';
  } else {
    tbody.innerHTML = data.map(d => `
      <tr>
        <td>${d.report_date}</td>
        <td>Shift ${d.shift_number}</td>
        <td>${formatAngka(d.total_item_count)}</td>
        <td>${formatAngka(d.passed_item_count)}</td>
        <td>${formatAngka(d.sorted_item_count)}</td>
        <td>${d.uptime_minutes} mnt</td>
        <td>${d.efficiency_percent}%</td>
        <td>${d.closed_by || "—"}</td>
      </tr>`).join("");
  }

  const total = data.reduce((a, d) => a + d.total_item_count, 0);
  const terbaik = data.reduce((a, d) => (d.total_item_count > (a?.total_item_count ?? -1) ? d : a), null);
  document.getElementById("tren-ringkas").textContent = data.length === 0
    ? "Belum ada data arsip."
    : `${data.length} shift terarsip · total ${formatAngka(total)} item · terbaik: ${terbaik.report_date} Shift ${terbaik.shift_number} (${formatAngka(terbaik.total_item_count)} item)`;
}

async function muat() {
  try {
    const l = await apiGet("/api/laporan");
    isiSemua(l.riwayat);
  } catch {
    document.getElementById("tren-ringkas").textContent = "Gagal memuat data. Periksa koneksi ke server.";
  }
}

function init() {
  const canvas = document.getElementById("chart-tren");
  new ResizeObserver(() => muat()).observe(canvas);
  // redraw saat tema berganti (warna token berubah)
  new MutationObserver(() => muat())
    .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  muat();
}

document.readyState === "loading"
  ? document.addEventListener("DOMContentLoaded", init)
  : init();
