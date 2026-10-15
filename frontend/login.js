// login.js — halaman masuk + penjaga sesi (session storage, dipakai seluruh modul via auth.js).
import { apiPost } from "./api-client.js";
import { simpanSesi, bersihkanSesi } from "./auth.js";

const form = document.getElementById("form-login");
const errBox = document.getElementById("login-error");

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  errBox.hidden = true;
  const fd = new FormData(form);
  const tombol = form.querySelector("button[type=submit]");
  tombol.disabled = true;
  try {
    const r = await apiPost("/api/auth/login", {
      username: fd.get("username"),
      password: fd.get("password"),
    });
    simpanSesi(r.access_token, r.role, r.expires_in);
    location.href = "/index.html";
  } catch (e) {
    errBox.textContent = e.detail ?? "Login gagal. Periksa username dan password.";
    errBox.hidden = false;
    bersihkanSesi();
  } finally {
    tombol.disabled = false;
  }
});
