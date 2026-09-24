"""
Konfigurasi URL aplikasi core
=============================

Seluruh alamat halaman aplikasi Dapur Ina Aina didaftarkan di sini.
Penamaan URL memakai bahasa Indonesia agar konsisten dengan penamaan
model dan mudah ditelusuri saat presentasi.

Pembagian alamat
----------------
Pelanggan (tanpa login)
    ""                            halaman menu
    "pesan/"                      formulir pemesanan
    "pesan/diterima/<nomor>/"     konfirmasi nomor pesanan
    "status/"                     cek status pesanan

Masuk dan keluar
    "masuk/"                      halaman login Kasir/Administrator
    "keluar/"                     keluar dari aplikasi

Kasir (perlu login)
    "kasir/"                      beranda kasir
    "kasir/pesanan/"              daftar pesanan
    "kasir/pesanan/<pk>/"         rincian pesanan
    "kasir/pesanan/<pk>/status/"  ubah status pesanan
    "kasir/pesanan/<pk>/billing/" tampilkan billing
    "kasir/pesanan/<pk>/cetak/"   cetak billing
    "kasir/pesanan/<pk>/bayar/"   proses pembayaran
    "kasir/pembayaran/<pk>/"      bukti pembayaran

Administrator (perlu login, peran Administrator)
    "kelola/produk/..."           CRUD produk
    "kelola/kategori/..."         CRUD kategori
    "kelola/stok/..."             kelola stok
    "kelola/laporan/"             laporan penjualan
    "kelola/pengguna/..."         CRUD pengguna
"""

from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    # --------------------------------------------------------------
    # Halaman Pelanggan (tanpa login)
    # --------------------------------------------------------------
    path("", views.BerandaPelangganView.as_view(), name="beranda"),
    path("pesan/", views.FormPesananView.as_view(), name="form_pesanan"),
    path(
        "pesan/diterima/<str:nomor>/",
        views.KonfirmasiPesananView.as_view(),
        name="konfirmasi_pesanan",
    ),
    path("status/", views.CekStatusView.as_view(), name="cek_status"),

    # --------------------------------------------------------------
    # Pembayaran oleh Pelanggan (tanpa login)
    #
    # Pelanggan diarahkan ke sini tepat setelah memesan, karena pesanan
    # wajib dibayar sebelum diproses.
    # --------------------------------------------------------------
    path(
        "pesan/<str:nomor>/bayar/",
        views.PembayaranPelangganView.as_view(),
        name="pembayaran_pelanggan",
    ),
    path(
        "pesan/<str:nomor>/bayar/simulasi/",
        views.SimulasiBayarQrisView.as_view(),
        name="simulasi_bayar_qris",
    ),
    path(
        "pesan/<str:nomor>/bayar/status/",
        views.StatusPembayaranPelangganView.as_view(),
        name="status_pembayaran_pelanggan",
    ),

    # --------------------------------------------------------------
    # Notifikasi gateway (dipanggil mesin gateway, bukan peramban)
    # --------------------------------------------------------------
    path(
        "notifikasi/gateway/",
        views.NotifikasiGatewayView.as_view(),
        name="notifikasi_gateway",
    ),

    # --------------------------------------------------------------
    # Masuk dan keluar
    # --------------------------------------------------------------
    path("masuk/", views.MasukView.as_view(), name="masuk"),
    path("keluar/", views.KeluarView.as_view(), name="keluar"),

    # --------------------------------------------------------------
    # Halaman Kasir (perlu login)
    # --------------------------------------------------------------
    path("kasir/", views.KasirBerandaView.as_view(), name="kasir_beranda"),
    path(
        "kasir/pesanan/",
        views.DaftarPesananView.as_view(),
        name="kasir_pesanan",
    ),
    path(
        "kasir/pesanan/<int:pk>/",
        views.DetailPesananView.as_view(),
        name="kasir_detail_pesanan",
    ),
    path(
        "kasir/pesanan/<int:pk>/status/",
        views.UbahStatusPesananView.as_view(),
        name="kasir_ubah_status",
    ),
    path(
        "kasir/pesanan/<int:pk>/billing/",
        views.BillingView.as_view(),
        name="kasir_billing",
    ),
    path(
        "kasir/pesanan/<int:pk>/cetak/",
        views.CetakBillingView.as_view(),
        name="kasir_cetak_billing",
    ),
    path(
        "kasir/pesanan/<int:pk>/bayar/",
        views.PembayaranView.as_view(),
        name="kasir_pembayaran",
    ),
    path(
        "kasir/pesanan/<int:pk>/bayar/qris/periksa/",
        views.PeriksaStatusQrisView.as_view(),
        name="kasir_periksa_qris",
    ),
    path(
        "kasir/pesanan/<int:pk>/bayar/qris/konfirmasi/",
        views.KonfirmasiPembayaranQrisView.as_view(),
        name="kasir_konfirmasi_qris",
    ),
    path(
        "kasir/pesanan/<int:pk>/tagihan.pdf",
        views.UnduhTagihanPdfView.as_view(),
        name="kasir_tagihan_pdf",
    ),
    path(
        "kasir/pembayaran/<int:pk>/",
        views.BuktiPembayaranView.as_view(),
        name="kasir_bukti_pembayaran",
    ),

    # --------------------------------------------------------------
    # Halaman Administrator: Produk (AD09)
    # --------------------------------------------------------------
    path(
        "kelola/produk/",
        views.KelolaProdukView.as_view(),
        name="kelola_produk",
    ),
    path(
        "kelola/produk/tambah/",
        views.TambahProdukView.as_view(),
        name="kelola_produk_tambah",
    ),
    path(
        "kelola/produk/<int:pk>/ubah/",
        views.UbahProdukView.as_view(),
        name="kelola_produk_ubah",
    ),
    path(
        "kelola/produk/<int:pk>/hapus/",
        views.HapusProdukView.as_view(),
        name="kelola_produk_hapus",
    ),

    # --------------------------------------------------------------
    # Halaman Administrator: Kategori (AD10)
    # --------------------------------------------------------------
    path(
        "kelola/kategori/",
        views.KelolaKategoriView.as_view(),
        name="kelola_kategori",
    ),
    path(
        "kelola/kategori/tambah/",
        views.TambahKategoriView.as_view(),
        name="kelola_kategori_tambah",
    ),
    path(
        "kelola/kategori/<int:pk>/ubah/",
        views.UbahKategoriView.as_view(),
        name="kelola_kategori_ubah",
    ),
    path(
        "kelola/kategori/<int:pk>/hapus/",
        views.HapusKategoriView.as_view(),
        name="kelola_kategori_hapus",
    ),

    # --------------------------------------------------------------
    # Halaman Administrator: Kelola Stok (AD07)
    # --------------------------------------------------------------
    path(
        "kelola/stok/",
        views.KelolaStokView.as_view(),
        name="kelola_stok",
    ),
    path(
        "kelola/stok/<int:pk>/",
        views.AturStokView.as_view(),
        name="kelola_stok_atur",
    ),

    # --------------------------------------------------------------
    # Halaman Administrator: Laporan Penjualan (AD08)
    # --------------------------------------------------------------
    path(
        "kelola/laporan/",
        views.LaporanView.as_view(),
        name="kelola_laporan",
    ),

    # --------------------------------------------------------------
    # Halaman Administrator: Pengguna (AD11)
    # --------------------------------------------------------------
    path(
        "kelola/pengguna/",
        views.KelolaPenggunaView.as_view(),
        name="kelola_pengguna",
    ),
    path(
        "kelola/pengguna/tambah/",
        views.TambahPenggunaView.as_view(),
        name="kelola_pengguna_tambah",
    ),
    path(
        "kelola/pengguna/<int:pk>/ubah/",
        views.UbahPenggunaView.as_view(),
        name="kelola_pengguna_ubah",
    ),
    path(
        "kelola/pengguna/<int:pk>/hapus/",
        views.HapusPenggunaView.as_view(),
        name="kelola_pengguna_hapus",
    ),
]
