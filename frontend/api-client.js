// api-client.js — klien API terpusat: fetch wrapper + penanganan error sama untuk semua modul.
// Ekspor bernama apiGet/apiPost agar modul tidak menyentuh fetch langsung.

const BASE = import.meta?.env?.VITE_API ?? "";

export class ApiError extends Error {
  constructor(status, pesan) {
    super(pesan);
    this.status = status;
  }
}

async function request(path, opsi = {}) {
  let res;
  try {
    const { body, headers, ...sisanya } = opsi;
    res = await fetch(`${BASE}${path}`, {
      ...sisanya,
      headers: { "Content-Type": "application/json", ...headers },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Tidak dapat menyambung ke server PLC. Periksa koneksi jaringan.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `Permintaan gagal (HTTP ${res.status})`);
  }
  const tipe = res.headers.get("content-type") ?? "";
  return tipe.includes("application/json") ? res.json() : res.text();
}

export const apiGet = (path, headers = {}) => request(path, { headers });
export const apiPost = (path, body, headers = {}) => request(path, { method: "POST", body, headers });
export const apiPut = (path, body, headers = {}) => request(path, { method: "PUT", body, headers });

// Endpoint terpusat — dipakai modul via konstanta ini agar path tidak tersebar.
export const ENDPOINT = {
  status: "/api/status",
  kontrol: "/api/kontrol",
  parameter: "/api/parameter",
  laporan: "/api/laporan",
  tutupShift: "/api/laporan/tutup-shift",
  eksporCsv: "/api/laporan/ekspor",
  alarmLog: "/api/alarm",
  ioTest: "/api/diagnostik/io",
  simObjek: "/api/simulasi/objek",
};
