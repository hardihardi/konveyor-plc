// chart.js — grafik tren produksi (canvas 2D, tanpa dependensi).
// Mengikuti token: warna dibaca dari CSS custom properties. Responsif via ResizeObserver.
// Hormati prefers-reduced-motion (tanpa animasi bila aktif).

function css(nama) {
  return getComputedStyle(document.documentElement).getPropertyValue(nama).trim();
}

const GERAK_MINIM = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function gambarTren(canvas, data, { target = 500 } = {}) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (w === 0 || h === 0) return;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  const pad = { kiri: 44, kanan: 12, atas: 16, bawah: 28 };
  const iw = w - pad.kiri - pad.kanan;
  const ih = h - pad.atas - pad.bawah;

  const garis = css("--border-subtle") || "#444";
  const teks = css("--text-secondary") || "#999";
  const aksen = css("--accent") || "#f97316";
  const sukses = css("--success") || "#16a34a";

  // Skala Y: maksimum dari data atau target, bulat ke atas per 100
  const maks = Math.max(target, ...data.map(d => d.total_item_count), 100);
  const yMax = Math.ceil(maks / 100) * 100;

  // Grid + label Y (4 garis)
  ctx.strokeStyle = garis;
  ctx.fillStyle = teks;
  ctx.font = "11px " + (css("--font-ui") || "sans-serif");
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.atas + (ih * i) / 4;
    ctx.beginPath();
    ctx.moveTo(pad.kiri, y);
    ctx.lineTo(pad.kiri + iw, y);
    ctx.stroke();
    ctx.textAlign = "right";
    ctx.fillText(String(yMax - (yMax * i) / 4), pad.kiri - 6, y + 4);
  }

  // Garis target shift (putus-putus)
  const yTarget = pad.atas + ih - (ih * target) / yMax;
  ctx.setLineDash([5, 4]);
  ctx.strokeStyle = teks;
  ctx.beginPath();
  ctx.moveTo(pad.kiri, yTarget);
  ctx.lineTo(pad.kiri + iw, yTarget);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.textAlign = "left";
  ctx.fillText("Target", pad.kiri + 4, yTarget - 4);

  if (data.length === 0) {
    ctx.fillStyle = teks;
    ctx.textAlign = "center";
    ctx.fillText("Belum ada data shift. Tutup shift untuk mengarsipkan data.", w / 2, h / 2);
    return;
  }

  // Sumbu X: label shift (tgl/shift)
  const n = data.length;
  const xAt = (i) => pad.kiri + (n === 1 ? iw / 2 : (iw * i) / (n - 1));
  ctx.textAlign = "center";
  data.forEach((d, i) => {
    ctx.fillText(`${d.report_date.slice(8,10)}/${d.report_date.slice(5,7)} S${d.shift_number}`, xAt(i), h - 8);
  });

  // Garis tren total
  ctx.strokeStyle = aksen;
  ctx.lineWidth = 2;
  ctx.beginPath();
  data.forEach((d, i) => {
    const y = pad.atas + ih - (ih * d.total_item_count) / yMax;
    i === 0 ? ctx.moveTo(xAt(i), y) : ctx.lineTo(xAt(i), y);
  });
  ctx.stroke();

  // Titik lolos (hijau) dan tersortir
  data.forEach((d, i) => {
    const yLolos = pad.atas + ih - (ih * d.passed_item_count) / yMax;
    const ySortir = pad.atas + ih - (ih * d.sorted_item_count) / yMax;
    ctx.fillStyle = sukses;
    ctx.beginPath();
    ctx.arc(xAt(i), yLolos, 3.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = aksen;
    ctx.beginPath();
    ctx.arc(xAt(i), ySortir, 3.5, 0, Math.PI * 2);
    ctx.fill();
  });

  // Isi area di bawah garis total (transparan, bukan dekorasi — memperjelas volume)
  ctx.globalAlpha = 0.08;
  ctx.fillStyle = aksen;
  ctx.beginPath();
  ctx.moveTo(xAt(0), pad.atas + ih);
  data.forEach((d, i) => ctx.lineTo(xAt(i), pad.atas + ih - (ih * d.total_item_count) / yMax));
  ctx.lineTo(xAt(n - 1), pad.atas + ih);
  ctx.closePath();
  ctx.fill();
  ctx.globalAlpha = 1;
}
