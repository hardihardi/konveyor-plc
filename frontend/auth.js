// auth.js — penjaga sesi klien: token + role di sessionStorage (hilang saat tab ditutup).
// Fungsi wajibAuth() dipanggil modul terlindungi; header() untuk api-client.

const KUNCI_TOKEN = "hmi-token";
const KUNCI_ROLE = "hmi-role";
const KUNCI_KEDALUWARSA = "hmi-exp";

export function simpanSesi(token, role, usiaDetik) {
  sessionStorage.setItem(KUNCI_TOKEN, token);
  sessionStorage.setItem(KUNCI_ROLE, role);
  sessionStorage.setItem(KUNCI_KEDALUWARSA, String(Date.now() + usiaDetik * 1000));
}

export function bersihkanSesi() {
  sessionStorage.removeItem(KUNCI_TOKEN);
  sessionStorage.removeItem(KUNCI_ROLE);
  sessionStorage.removeItem(KUNCI_KEDALUWARSA);
}

export function tokenAktif() {
  const token = sessionStorage.getItem(KUNCI_TOKEN);
  const exp = Number(sessionStorage.getItem(KUNCI_KEDALUWARSA) ?? 0);
  if (!token || Date.now() > exp) {
    bersihkanSesi();
    return null;
  }
  return token;
}

export function roleSaatIni() {
  return tokenAktif() ? sessionStorage.getItem(KUNCI_ROLE) : null;
}

/**
 * WajibAuth: bila belum login → redirect ke /login.html dengan parameter asal.
 * return: role aktif. Modul memakai ini untuk menonaktifkan tombol di luar perannya.
 */
export function wajibAuth(...roles) {
  const token = tokenAktif();
  if (!token) {
    location.href = `/login.html?asal=${encodeURIComponent(location.pathname)}`;
    return null;
  }
  const role = sessionStorage.getItem(KUNCI_ROLE);
  if (roles.length > 0 && !roles.includes(role)) {
    return { role, terbatas: true };
  }
  return { role, terbatas: false };
}

export function headerAuth() {
  const token = tokenAktif();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Logout global — dipasang oleh shell bila tombol ada
document.getElementById("btn-logout")?.addEventListener("click", async () => {
  try {
    const { apiPost } = await import("./api-client.js");
    await apiPost("/api/auth/logout", undefined, headerAuth());
  } catch { /* sesi server mungkin sudah habis — tetap bersihkan lokal */ }
  bersihkanSesi();
  location.href = "/login.html";
});
