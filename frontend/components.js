// components.js — komponen dasar bersama: toast, modal, state loading/empty/error, konfirmasi hapus.
// Semua modul wajib memakai ini; dilarang membuat versi sendiri.

import { formatWaktu } from "./format.js";

/* ---------- Toast ---------- */
export function toast(judul, isi, jenis = "info", durasiMs = 4000) {
  const region = document.getElementById("toast-region");
  const el = document.createElement("div");
  el.className = "toast";
  el.dataset.kind = jenis;
  el.setAttribute("role", jenis === "error" ? "alert" : "status");
  el.innerHTML = `
    <div>
      <p class="toast-title"></p>
      <p class="toast-body"></p>
    </div>`;
  el.querySelector(".toast-title").textContent = judul;
  el.querySelector(".toast-body").textContent = isi;
  region.appendChild(el);
  setTimeout(() => el.remove(), durasiMs);
}

/* ---------- Modal generik: kembalikan Promise<string|null> dari input opsional ---------- */
export function bukaModal({ judul, isiHTML = "", tombol = [{ label: "Tutup", jenis: "secondary", nilai: null }] }) {
  return new Promise((selesai) => {
    const root = document.getElementById("modal-root");
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <h2 class="modal-title" id="modal-title"></h2>
        <div class="modal-content">${isiHTML}</div>
        <div class="modal-actions"></div>
      </div>`;
    backdrop.querySelector(".modal-title").textContent = judul;
    const actions = backdrop.querySelector(".modal-actions");

    function tutup(nilai) {
      root.removeChild(backdrop);
      selesai(nilai);
    }

    for (const t of tombol) {
      const btn = document.createElement("button");
      btn.className = `btn btn-${t.jenis}`;
      btn.textContent = t.label;
      btn.addEventListener("click", () => tutup(t.nilai));
      actions.appendChild(btn);
    }

    backdrop.addEventListener("keydown", (e) => {
      if (e.key === "Escape") tutup(null);
    });
    root.appendChild(backdrop);
    const fokusPertama = actions.querySelector("button");
    fokusPertama?.focus();
  });
}

/* Konfirmasi hapus/tindakan berisiko — pola tunggal untuk semua modul */
export function konfirmasi(judul, pesan) {
  return bukaModal({
    judul,
    isiHTML: `<p>${pesan}</p>`,
    tombol: [
      { label: "Batal", jenis: "secondary", nilai: false },
      { label: "Ya, lanjutkan", jenis: "danger", nilai: true },
    ],
  });
}

/* ---------- State loading / empty / error ---------- */
export function renderLoading(container, teks = "Memuat data…") {
  container.innerHTML = `
    <div class="state-loading" role="status">
      <div class="spinner" aria-hidden="true"></div>
      <p>${teks}</p>
    </div>`;
  container.setAttribute("aria-busy", "true");
}

export function renderEmpty(container, teks, saran = "") {
  container.removeAttribute("aria-busy");
  container.innerHTML = `
    <div class="state-empty">
      <p>${teks}</p>
      ${saran ? `<p class="toast-body">${saran}</p>` : ""}
    </div>`;
}

export function renderError(container, err) {
  container.removeAttribute("aria-busy");
  const waktu = formatWaktu(new Date().toISOString());
  container.innerHTML = `
    <div class="state-error" role="alert">
      <p><strong>Gagal memuat data (${waktu}).</strong></p>
      <p>${err.message ?? err}</p>
      <button class="btn btn-secondary" id="retry-btn">Coba lagi</button>
    </div>`;
  container.querySelector("#retry-btn")?.addEventListener("click", () => location.reload());
}
