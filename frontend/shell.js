// shell.js — perilaku layout: drawer navigasi, tema gelap/terang (tersimpan).
// ID elemen mengikuti HTML: btn-drawer, sidebar, drawer-veil, btn-tema.

const TEMA_KEY = "hmi-tema";

function terapkanTema(tema) {
  document.documentElement.dataset.theme = tema;
  try { localStorage.setItem(TEMA_KEY, tema); } catch { /* private mode: tema tidak persisten */ }
}

(function init() {
  let tema = "dark";
  try { tema = localStorage.getItem(TEMA_KEY) ?? "dark"; } catch { /* default */ }
  terapkanTema(tema);

  document.getElementById("btn-tema")?.addEventListener("click", () => {
    const sekarang = document.documentElement.dataset.theme;
    terapkanTema(sekarang === "dark" ? "light" : "dark");
  });

  const nav = document.getElementById("sidebar");
  const veil = document.getElementById("drawer-veil");
  const toggle = document.getElementById("btn-drawer");

  function setDrawer(terbuka) {
    nav.classList.toggle("sidebar--terbuka", terbuka);
    toggle.setAttribute("aria-expanded", String(terbuka));
    veil.hidden = !terbuka;
  }

  toggle?.addEventListener("click", () => setDrawer(!nav.classList.contains("sidebar--terbuka")));
  veil?.addEventListener("click", () => setDrawer(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && nav.classList.contains("sidebar--terbuka")) setDrawer(false);
  });
  // Tutup drawer setelah pilih menu (mobile)
  nav?.addEventListener("click", (e) => {
    if (e.target.closest("a") && window.innerWidth < 1024) setDrawer(false);
  });
})();
