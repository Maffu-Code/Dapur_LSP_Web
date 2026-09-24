"""
Antarmuka payment gateway (mockup QRIS)
=======================================

Modul ini memisahkan aplikasi dari penyedia payment gateway. View dan
layanan tidak pernah memanggil penyedia secara langsung, melainkan
memanggil fungsi pada modul ini. Akibatnya, penggantian penyedia
(misalnya Midtrans) hanya memerlukan satu kelas baru dan satu baris
perubahan pada config/settings.py, tanpa mengubah view, layanan, model,
maupun template.

Saat ini dipakai GatewayMockup, yaitu tiruan gateway QRIS yang berjalan
di dalam aplikasi. Tujuannya supaya alur pembayaran non tunai dapat
didemonstrasikan tanpa akun gateway sungguhan, dengan tetap memakai
jalur verifikasi yang sama seperti gateway sungguhan:

    1. gateway membuat transaksi          -> buat_transaksi()
    2. pelanggan membayar (scan QR)
    3. notifikasi masuk ke /notifikasi/gateway/
    4. aplikasi memeriksa tanda tangan    -> verifikasi_notifikasi()
    5. status transaksi diperbarui        -> terima_notifikasi_gateway()

Perbedaan mockup dengan gateway sungguhan hanya pada bagian transport,
yaitu siapa yang mengirim permintaan HTTP ke alamat notifikasi. Bentuk
data dan cara verifikasinya sama, sehingga saat penyedia sungguhan
dipakai nanti, bagian yang berubah hanya kelas gateway pada modul ini.

Catatan keamanan
----------------
Notifikasi gateway berasal dari mesin dan tidak dapat mengirim token
CSRF, sehingga alamat notifikasi dibebaskan dari pemeriksaan CSRF
(lihat core/views.py). Sebagai gantinya, setiap notifikasi wajib
menyertakan tanda tangan yang dihitung dari kode bayar, status, jumlah,
dan kunci rahasia milik penyedia. Tanda tangan diperiksa dengan
hmac.compare_digest agar waktu pemeriksaannya tidak dapat dipakai untuk
menebak tanda tangan yang benar.
"""

import hashlib
import hmac
import secrets
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

# Masa berlaku transaksi QRIS dalam satuan menit.
MASA_BERLAKU_MENIT = 15

# Status transaksi yang dipakai aplikasi dan gateway. Nilai ini sengaja
# disamakan dengan StatusTransaksi pada core/models.py supaya notifikasi
# dapat disimpan apa adanya.
STATUS_MENUNGGU = "MENUNGGU"
STATUS_DIBAYAR = "DIBAYAR"
STATUS_GAGAL = "GAGAL"
STATUS_KEDALUWARSA = "KEDALUWARSA"


def format_jumlah(nilai):
    """Menyusun nilai uang menjadi teks dua desimal, misalnya 50000.00.

    Bentuk yang sama dipakai saat menghitung dan saat memeriksa tanda
    tangan, sehingga hasil perhitungannya selalu cocok.
    """
    return f"{Decimal(nilai).quantize(Decimal('0.01')):.2f}"


class GatewayPembayaran:
    """Antarmuka dasar payment gateway.

    Kelas ini tidak dipakai langsung. Kelas turunannya yang dipakai
    aplikasi, dipilih melalui settings.GATEWAY_PEMBAYARAN.
    """

    # Nama penyedia, dipakai pada halaman pembayaran agar pengguna
    # mengetahui transaksi ini sedang ditangani oleh gateway mana.
    nama = "Gateway"

    # Penanda apakah transaksi masih tiruan atau sungguhan. Dipakai
    # halaman pembayaran untuk menampilkan keterangan mockup.
    simulasi = True

    def buat_transaksi(self, pesanan, billing):
        """Membuat transaksi pembayaran di sisi gateway.

        Mengembalikan kamus berisi kode_bayar (nomor transaksi di sisi
        gateway), qr_string (isi QR yang dipindai pelanggan), dan
        kedaluwarsa_pada.
        """
        raise NotImplementedError

    def tanda_tangan(self, kode_bayar, status, jumlah):
        """Menghitung tanda tangan notifikasi.

        Dipakai mockup untuk meniru tanda tangan yang dikirim gateway
        sungguhan, dan dipakai aplikasi saat memeriksa keaslian.
        """
        raise NotImplementedError

    def verifikasi_notifikasi(self, kode_bayar, status, jumlah, tanda_tangan):
        """Memeriksa keaslian notifikasi yang diterima.

        Mengembalikan True bila tanda tangan cocok. Bila False,
        notifikasi harus ditolak dan tidak boleh mengubah data apa pun.
        """
        raise NotImplementedError

    def periksa_status(self, transaksi):
        """Membaca status transaksi langsung ke gateway.

        Dipakai kasir untuk memastikan status terbaru sebelum menekan
        tombol konfirmasi, bukan hanya mengandalkan notifikasi.
        """
        raise NotImplementedError


class GatewayMockup(GatewayPembayaran):
    """Tiruan gateway QRIS untuk keperluan demonstrasi.

    Kode bayar dibuat dengan awalan MOCK sehingga tidak mungkin tertukar
    dengan transaksi sungguhan. Tanda tangan dihitung dengan rumus yang
    meniru Midtrans, yaitu SHA512 dari kode bayar, status, jumlah, dan
    kunci rahasia.
    """

    nama = "QRIS (mockup)"
    simulasi = True
    PREFIX = "MOCK"

    @property
    def kunci_rahasia(self):
        """Kunci rahasia gateway.

        Pada mockup nilainya diambil dari config/settings.py. Pada
        penyedia sungguhan, nilai ini wajib berasal dari variabel
        lingkungan dan tidak boleh ikut tersimpan di dalam repositori.
        """
        return getattr(settings, "GATEWAY_MOCK_KEY", "mockup-kunci-uji")

    def buat_transaksi(self, pesanan, billing):
        kode_bayar = (
            f"{self.PREFIX}-{pesanan.nomor_pesanan}-{secrets.token_hex(3).upper()}"
        )
        jumlah = billing.total if billing is not None else pesanan.hitung_total()
        # Isi QR pada mockup sengaja diberi penanda jelas supaya tidak
        # disangka QRIS sungguhan saat demonstrasi.
        qr_string = f"MOCKQRIS|{kode_bayar}|{format_jumlah(jumlah)}"
        return {
            "kode_bayar": kode_bayar,
            "qr_string": qr_string,
            "jumlah": jumlah,
            "kedaluwarsa_pada": timezone.now()
            + timezone.timedelta(minutes=MASA_BERLAKU_MENIT),
        }

    def tanda_tangan(self, kode_bayar, status, jumlah):
        bahan = f"{kode_bayar}{status}{format_jumlah(jumlah)}{self.kunci_rahasia}"
        return hashlib.sha512(bahan.encode("utf-8")).hexdigest()

    def verifikasi_notifikasi(self, kode_bayar, status, jumlah, tanda_tangan):
        if not tanda_tangan:
            return False
        diharapkan = self.tanda_tangan(kode_bayar, status, jumlah)
        return hmac.compare_digest(diharapkan, str(tanda_tangan))

    def periksa_status(self, transaksi):
        """Status pada mockup tidak berubah sendiri.

        Berbeda dengan gateway sungguhan yang menyimpan status di sisi
        penyedia, mockup menyimpan statusnya di basis data aplikasi.
        Karena itu fungsi ini hanya mengembalikan status yang tercatat.
        """
        return transaksi.status


def get_gateway():
    """Mengambil gateway yang dipakai aplikasi.

    Dipilih melalui settings.GATEWAY_PEMBAYARAN supaya penggantian
    penyedia cukup dilakukan pada satu tempat.
    """
    from django.utils.module_loading import import_string

    jalur = getattr(
        settings, "GATEWAY_PEMBAYARAN", "core.gateway.GatewayMockup"
    )
    return import_string(jalur)()
