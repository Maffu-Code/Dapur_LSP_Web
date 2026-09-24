"""
Pendaftaran model ke Django Admin
=================================

Django Admin dipakai sebagai alat bantu selama pengembangan dan
pemeriksaan data oleh asesor, bukan sebagai antarmuka utama aplikasi.
Antarmuka utama (Pelanggan, Kasir, Administrator) dibangun pada
halaman aplikasi sendiri di app core.

Setiap kelas di bawah ini hanya mengatur tampilan daftar (list_display),
filter, dan pencarian pada Django Admin agar data mudah diperiksa.
"""

from django.contrib import admin

from .models import (
    Billing,
    DetailPesanan,
    KategoriProduk,
    LaporanPenjualan,
    Pelanggan,
    Pembayaran,
    Pengguna,
    Pesanan,
    Produk,
)


@admin.register(Pengguna)
class PenggunaAdmin(admin.ModelAdmin):
    """Admin untuk Pengguna (Kasir dan Administrator)."""

    list_display = ("username", "nama", "role", "aktif", "dibuat_pada")
    list_filter = ("role", "aktif")
    search_fields = ("username", "nama")


@admin.register(KategoriProduk)
class KategoriProdukAdmin(admin.ModelAdmin):
    """Admin untuk KategoriProduk (3 kategori tetap sesuai studi kasus)."""

    list_display = ("nama", "tipe")
    list_filter = ("tipe",)


@admin.register(Produk)
class ProdukAdmin(admin.ModelAdmin):
    """Admin untuk Produk beserta stok dan status ketersediaannya."""

    list_display = ("nama", "kategori", "harga", "stok", "status_stok", "aktif")
    list_filter = ("kategori", "status_stok", "aktif")
    search_fields = ("nama",)


@admin.register(Pelanggan)
class PelangganAdmin(admin.ModelAdmin):
    """Admin untuk Pelanggan (tanpa akun, dikenali dari nomor meja)."""

    list_display = ("nama", "nomor_meja")
    search_fields = ("nama", "nomor_meja")


class DetailPesananInline(admin.TabularInline):
    """Menampilkan rincian item langsung pada halaman Pesanan."""

    model = DetailPesanan
    extra = 1


@admin.register(Pesanan)
class PesananAdmin(admin.ModelAdmin):
    """Admin untuk Pesanan beserta rincian itemnya."""

    list_display = ("nomor_pesanan", "pelanggan", "status", "dibuat_pada")
    list_filter = ("status",)
    search_fields = ("nomor_pesanan",)
    inlines = [DetailPesananInline]


@admin.register(Billing)
class BillingAdmin(admin.ModelAdmin):
    """Admin untuk Billing (subtotal, pajak, total tagihan)."""

    list_display = ("pesanan", "subtotal", "pajak", "total", "dicetak_pada")


@admin.register(Pembayaran)
class PembayaranAdmin(admin.ModelAdmin):
    """Admin untuk Pembayaran (tunai maupun non tunai)."""

    list_display = (
        "billing",
        "kasir",
        "metode",
        "jumlah_diterima",
        "kembalian",
        "dibayar_pada",
    )
    list_filter = ("metode",)


@admin.register(LaporanPenjualan)
class LaporanPenjualanAdmin(admin.ModelAdmin):
    """Admin untuk LaporanPenjualan (mingguan dan bulanan)."""

    list_display = (
        "periode",
        "tanggal_mulai",
        "tanggal_selesai",
        "total_penjualan",
        "dibuat_pada",
    )
    list_filter = ("periode",)
