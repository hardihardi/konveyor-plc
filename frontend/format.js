/* format.js — utilitas format seragam: tanggal, angka, durasi. Locale tunggal id-ID. */

const LOCALE = "id-ID";

export function formatAngka(n) {
  return new Intl.NumberFormat(LOCALE).format(n);
}

export function formatWaktu(iso) {
  const d = new Date(iso);
  return new Intl.DateTimeFormat(LOCALE, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "Asia/Jakarta",
  }).format(d);
}

export function formatTanggal(iso) {
  const d = new Date(iso);
  return new Intl.DateTimeFormat(LOCALE, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Asia/Jakarta",
  }).format(d);
}

/* Durasi dalam menit -> "7 j 30 m" */
export function formatDurasiMenit(totalMenit) {
  const jam = Math.floor(totalMenit / 60);
  const menit = totalMenit % 60;
  if (jam === 0) return `${menit} m`;
  return `${jam} j ${menit} m`;
}

/* Persentase efisiensi: sorted+passed relative ke target shift */
export function formatPersen(bagian, total) {
  if (total <= 0) return "0%";
  return `${Math.round((bagian / total) * 100)}%`;
}

export function pesanValidasi(field, aturan) {
  const pesan = {
    wajib: `${field} wajib diisi`,
    min: `${field} minimal ${aturan.nilai}`,
    max: `${field} maksimal ${aturan.nilai}`,
    angka: `${field} harus berupa angka`,
  };
  return pesan[aturan.jenis] ?? `${field} tidak valid`;
}
