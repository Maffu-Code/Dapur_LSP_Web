/* ==========================================================================
   Skrip tampilan aplikasi Dapur Ina Aina
   ==========================================================================
   Skrip ini hanya menangani keperluan tampilan. Seluruh aturan transaksi
   dan validasi tetap dikerjakan di sisi server supaya tetap berlaku walau
   JavaScript dimatikan.

   Isi:
   1. Mencegah klik tombol simpan dua kali pada formulir transaksi uang.
   2. Tombol konfirmasi sebelum aksi yang tidak dapat dibatalkan.
   3. Penyesuaian isian pembayaran mengikuti metode yang dipilih.
   ========================================================================== */

(function () {
  "use strict";

  /* ------------------------------------------------------------------
     1. Cegah klik ganda pada tombol kirim
     ------------------------------------------------------------------
     Pada transaksi uang, klik dua kali dapat membuat data tersimpan
     dua kali. Tombol dinonaktifkan sesaat setelah formulir dikirim dan
     teksnya diganti agar pengguna tahu prosesnya sedang berjalan.
  */
  function pasangPencegahKlikGanda() {
    var formulir = document.querySelectorAll("form[data-cegah-ganda]");
    Array.prototype.forEach.call(formulir, function (form) {
      form.addEventListener("submit", function () {
        var tombol = form.querySelector('button[type="submit"]');
        if (!tombol) {
          return;
        }
        // Tunda sedikit agar tombol sempat terkirim bersama formulir.
        window.setTimeout(function () {
          tombol.disabled = true;
          tombol.textContent = "Memproses...";
        }, 0);
      });
    });
  }

  /* ------------------------------------------------------------------
     2. Konfirmasi sebelum aksi yang tidak dapat dibatalkan
     ------------------------------------------------------------------
     Dipakai pada tombol hapus, batalkan pesanan, dan aksi lain yang
     mengubah data secara permanen.
  */
  function pasangKonfirmasi() {
    var tombol = document.querySelectorAll("[data-konfirmasi]");
    Array.prototype.forEach.call(tombol, function (el) {
      el.addEventListener("click", function (kejadian) {
        var pesan = el.getAttribute("data-konfirmasi");
        if (pesan && !window.confirm(pesan)) {
          kejadian.preventDefault();
        }
      });
    });
  }

  /* ------------------------------------------------------------------
     3. Isian pembayaran mengikuti metode yang dipilih
     ------------------------------------------------------------------
     Tunai : tampilkan isian jumlah uang diterima.
     QRIS  : tampilkan keterangan bahwa pembayaran diproses melalui
             kode QR dan dikonfirmasi setelah gateway menyatakan
             pembayaran berhasil.

     Tanpa JavaScript, seluruh isian tetap tampil dan validasi tetap
     dikerjakan di server, sehingga aplikasi tidak bergantung pada
     skrip ini.
  */
  function pasangIsianPembayaran() {
    var wadah = document.querySelector("[data-pembayaran]");
    if (!wadah) {
      return;
    }

    var radio = wadah.querySelectorAll('input[name="metode"]');
    var blokTunai = wadah.querySelector("[data-blok-tunai]");
    var blokQris = wadah.querySelector("[data-blok-qris]");

    function sesuaikan() {
      var terpilih = wadah.querySelector('input[name="metode"]:checked');
      var nilai = terpilih ? terpilih.value : "";
      var tunai = nilai === "TUNAI";

      if (blokTunai) {
        blokTunai.hidden = !tunai;
      }
      if (blokQris) {
        blokQris.hidden = tunai;
      }
    }

    Array.prototype.forEach.call(radio, function (el) {
      el.addEventListener("change", sesuaikan);
    });

    sesuaikan();
  }

  document.addEventListener("DOMContentLoaded", function () {
    pasangPencegahKlikGanda();
    pasangKonfirmasi();
    pasangIsianPembayaran();
  });
})();
