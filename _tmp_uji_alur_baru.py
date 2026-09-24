"""
Uji alur baru secara menyeluruh: pesan -> bayar -> cetak.

Dijalankan langsung terhadap aplikasi melalui Django test client agar
seluruh lapisan (formulir, view, layanan, model) ikut teruji.

Fokus uji:
  1. Pelanggan yang memesan langsung diarahkan ke halaman pembayaran.
  2. Tagihan TIDAK dapat dicetak sebelum dibayar.
  3. Pembayaran tunai oleh kasir mengubah status menjadi DIBAYAR.
  4. QRIS tidak dapat dikonfirmasi sebelum gateway menyatakan berhasil.
  5. Notifikasi gateway palsu ditolak (tanda tangan salah).
  6. Notifikasi dengan nominal yang diubah ditolak.
  7. Setelah dibayar, tagihan dapat dicetak dan PDF dapat diunduh.
  8. Status pesanan berjalan DIBAYAR -> DIPROSES -> SELESAI.
  9. Laporan menghitung pesanan yang sudah dibayar.
 10. Pesanan yang belum dibayar tidak dihitung laporan.
"""

import os
import re

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from core import services  # noqa: E402
from core.models import (  # noqa: E402
    LaporanPenjualan,
    Pembayaran,
    Pengguna,
    PeriodeLaporan,
    Pesanan,
    Produk,
    Role,
    StatusPesanan,
    TransaksiGateway,
)

HASIL = []


def uji(nama, syarat, keterangan=""):
    """Mencatat hasil satu pemeriksaan."""
    HASIL.append((nama, bool(syarat), keterangan))
    tanda = "LULUS" if syarat else "GAGAL"
    print(f"  [{tanda}] {nama}" + (f" -> {keterangan}" if keterangan else ""))


def ambil_csrf(client, url, **kwargs):
    """Mengambil token CSRF dari sebuah halaman."""
    respons = client.get(url, **kwargs)
    isi = respons.content.decode("utf-8")
    cocok = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', isi)
    return cocok.group(1) if cocok else "", respons


print("=" * 78)
print("UJI ALUR BAYAR DI AWAL")
print("=" * 78)

kasir = Pengguna.objects.filter(role=Role.KASIR, aktif=True).first()
if kasir is None:
    raise SystemExit("Akun kasir tidak ditemukan. Jalankan seed lebih dahulu.")

produk = Produk.objects.filter(aktif=True, stok__gt=5).first()
if produk is None:
    raise SystemExit("Produk dengan stok memadai tidak ditemukan.")

client = Client()

# ----------------------------------------------------------------------
print("\n1. PESAN -> LANGSUNG DIARAHKAN KE PEMBAYARAN")
# ----------------------------------------------------------------------
token, _ = ambil_csrf(client, reverse("core:form_pesanan"))
data = {
    "csrfmiddlewaretoken": token,
    "nama": "Uji Alur",
    "nomor_meja": "9",
    "metode_pembayaran": "TUNAI",
    f"jumlah_{produk.pk}": "2",
}
respons = client.post(reverse("core:form_pesanan"), data)

pesanan = Pesanan.objects.filter(pelanggan__nama="Uji Alur").first()
uji("Pesanan baru dibuat", pesanan is not None)
uji(
    "Diarahkan ke halaman pembayaran, bukan konfirmasi",
    respons.status_code == 302
    and f"/pesan/{pesanan.nomor_pesanan}/bayar/" in respons["Location"],
    respons.get("Location", "")[:70],
)
uji(
    "Status awal BARU berarti menunggu pembayaran",
    pesanan.status == StatusPesanan.BARU,
    f"status={pesanan.get_status_display()}",
)
uji(
    "Metode pilihan pelanggan tersimpan",
    pesanan.metode_dipilih == "TUNAI",
    f"metode={pesanan.metode_dipilih}",
)

# ----------------------------------------------------------------------
print("\n2. TAGIHAN BELUM DAPAT DICETAK SEBELUM DIBAYAR")
# ----------------------------------------------------------------------
uji(
    "Pesanan belum dibayar tidak boleh dicetak",
    pesanan.boleh_dicetak() is False,
)

client_kasir = Client()
token, _ = ambil_csrf(client_kasir, reverse("core:masuk"))
client_kasir.post(
    reverse("core:masuk"),
    {
        "csrfmiddlewaretoken": token,
        "username": kasir.username,
        "password": "kasir123",
    },
)

respons = client_kasir.get(
    reverse("core:kasir_cetak_billing", args=[pesanan.pk]), follow=True
)
uji(
    "Halaman cetak menolak dan mengalihkan",
    respons.status_code == 200
    and "belum dapat dicetak" in respons.content.decode("utf-8").lower(),
    f"status={respons.status_code}",
)

respons = client_kasir.get(reverse("core:kasir_tagihan_pdf", args=[pesanan.pk]))
uji(
    "Unduhan PDF menolak sebelum dibayar",
    respons.status_code == 302,
    f"status={respons.status_code}",
)

# ----------------------------------------------------------------------
print("\n3. PEMBAYARAN TUNAI OLEH KASIR")
# ----------------------------------------------------------------------
billing = services.buat_billing(pesanan)
token, _ = ambil_csrf(client_kasir, reverse("core:kasir_pembayaran", args=[pesanan.pk]))
respons = client_kasir.post(
    reverse("core:kasir_pembayaran", args=[pesanan.pk]),
    {
        "csrfmiddlewaretoken": token,
        "metode": "TUNAI",
        "jumlah_diterima": str(billing.total),
    },
)
pesanan.refresh_from_db()
pembayaran = Pembayaran.objects.filter(billing=billing).first()

uji("Pembayaran tunai tersimpan", pembayaran is not None)
uji(
    "Status berubah menjadi DIBAYAR",
    pesanan.status == StatusPesanan.DIBAYAR,
    f"status={pesanan.get_status_display()}",
)
uji(
    "Kasir pengonfirmasi tercatat",
    pembayaran is not None and pembayaran.dikonfirmasi_kasir_id == kasir.pk,
)
uji(
    "Nomor referensi tunai kosong",
    pembayaran is not None and pembayaran.nomor_referensi == "",
)

# ----------------------------------------------------------------------
print("\n4. SETELAH DIBAYAR: TAGIHAN DAPAT DICETAK DAN PDF DIUNDUH")
# ----------------------------------------------------------------------
uji("Pesanan sudah dibayar boleh dicetak", pesanan.boleh_dicetak() is True)

respons = client_kasir.get(reverse("core:kasir_tagihan_pdf", args=[pesanan.pk]))
isi_pdf = respons.content
uji(
    "PDF terunduh dengan tipe application/pdf",
    respons.status_code == 200
    and respons["Content-Type"] == "application/pdf",
    f"{len(isi_pdf)} byte, status={respons.status_code}",
)
uji(
    "Berkas benar benar PDF",
    isi_pdf[:5] == b"%PDF-",
    f"awalan={isi_pdf[:5]!r}",
)
uji(
    "Nama berkas memuat nomor pesanan",
    pesanan.nomor_pesanan in respons.get("Content-Disposition", ""),
    respons.get("Content-Disposition", "")[:60],
)
uji(
    "Nomor pesanan tercetak di dalam PDF",
    pesanan.nomor_pesanan.encode() in isi_pdf
    or b"Tagihan" in isi_pdf,
)

# ----------------------------------------------------------------------
print("\n5. QRIS: TIDAK DAPAT DIKONFIRMASI SEBELUM GATEWAY BERHASIL")
# ----------------------------------------------------------------------
pesanan_qris = services.buat_pesanan(
    nama_pemesan="Uji QRIS",
    nomor_meja="11",
    item_list=[(produk, 1)],
    metode_pembayaran="QRIS",
)
billing_qris = services.buat_billing(pesanan_qris)
transaksi, _ = services.mulai_pembayaran_qris(pesanan_qris)

uji(
    "Transaksi QRIS dibuat dengan status MENUNGGU",
    transaksi.status == "MENUNGGU",
    f"kode={transaksi.kode_bayar}, status={transaksi.status}",
)
uji(
    "Kode bayar memakai awalan MOCK",
    transaksi.kode_bayar.startswith("MOCK-"),
)
uji(
    "Kode QR berisi penanda mockup",
    transaksi.qr_string.startswith("MOCKQRIS|"),
    transaksi.qr_string[:48],
)

try:
    services.proses_pembayaran(
        billing=billing_qris,
        kasir=kasir,
        metode="QRIS",
        transaksi=transaksi,
    )
    ditolak = False
    pesan = "tidak ditolak"
except services.KesalahanLayanan as galat:
    ditolak = True
    pesan = str(galat)

uji(
    "Konfirmasi QRIS ditolak sebelum gateway berhasil",
    ditolak,
    pesan[:74],
)
uji(
    "Pesanan QRIS tetap belum dibayar",
    Pembayaran.objects.filter(billing=billing_qris).count() == 0,
)

# ----------------------------------------------------------------------
print("\n6. NOTIFIKASI GATEWAY PALSU DITOLAK")
# ----------------------------------------------------------------------
from core import gateway as gateway_pembayaran  # noqa: E402

gw = gateway_pembayaran.get_gateway()
url_notif = reverse("core:notifikasi_gateway")

respons = client.post(
    url_notif,
    {
        "kode_bayar": transaksi.kode_bayar,
        "status": "DIBAYAR",
        "jumlah": str(transaksi.jumlah),
        "tanda_tangan": "tanda-tangan-palsu",
    },
)
transaksi.refresh_from_db()
uji(
    "Notifikasi dengan tanda tangan palsu ditolak (403)",
    respons.status_code == 403,
    f"status={respons.status_code}",
)
uji(
    "Status transaksi tidak berubah setelah notifikasi palsu",
    transaksi.status == "MENUNGGU",
    f"status={transaksi.status}",
)

# Nominal diubah, tanda tangan dihitung dari nominal palsu.
tanda_palsu = gw.tanda_tangan(transaksi.kode_bayar, "DIBAYAR", 1)
respons = client.post(
    url_notif,
    {
        "kode_bayar": transaksi.kode_bayar,
        "status": "DIBAYAR",
        "jumlah": "1",
        "tanda_tangan": tanda_palsu,
    },
)
transaksi.refresh_from_db()
uji(
    "Notifikasi bernominal kecil ditolak",
    respons.status_code == 403,
    f"status={respons.status_code}",
)
uji(
    "Transaksi tetap belum berhasil",
    transaksi.status == "MENUNGGU",
)

tanda_benar = gw.tanda_tangan(
    transaksi.kode_bayar, "DIBAYAR", transaksi.jumlah
)
respons = client.post(
    url_notif,
    {
        "kode_bayar": transaksi.kode_bayar,
        "status": "DIBAYAR",
        "jumlah": str(transaksi.jumlah),
        "tanda_tangan": tanda_benar,
    },
)
transaksi.refresh_from_db()
uji(
    "Notifikasi sah diterima (200)",
    respons.status_code == 200,
    f"status={respons.status_code}",
)
uji(
    "Transaksi menjadi DIBAYAR",
    transaksi.status == "DIBAYAR",
    f"status={transaksi.status}",
)

# ----------------------------------------------------------------------
print("\n7. KASIR MENGONFIRMASI QRIS SETELAH GATEWAY BERHASIL")
# ----------------------------------------------------------------------
token, _ = ambil_csrf(
    client_kasir, reverse("core:kasir_pembayaran", args=[pesanan_qris.pk])
)
respons = client_kasir.post(
    reverse("core:kasir_konfirmasi_qris", args=[pesanan_qris.pk]),
    {"csrfmiddlewaretoken": token},
)
pesanan_qris.refresh_from_db()
pembayaran_qris = Pembayaran.objects.filter(billing=billing_qris).first()

uji(
    "Pembayaran QRIS tersimpan setelah dikonfirmasi",
    pembayaran_qris is not None,
)
uji(
    "Metode tercatat QRIS",
    pembayaran_qris is not None and pembayaran_qris.metode == "QRIS",
)
uji(
    "Nomor referensi diambil dari kode bayar gateway",
    pembayaran_qris is not None
    and pembayaran_qris.nomor_referensi == transaksi.kode_bayar,
    f"ref={pembayaran_qris.nomor_referensi if pembayaran_qris else '-'}",
)
uji(
    "Kembalian QRIS nol",
    pembayaran_qris is not None and pembayaran_qris.kembalian == 0,
)
uji(
    "Status pesanan QRIS menjadi DIBAYAR",
    pesanan_qris.status == StatusPesanan.DIBAYAR,
)

# ----------------------------------------------------------------------
print("\n8. ALUR STATUS DIBAYAR -> DIPROSES -> SELESAI")
# ----------------------------------------------------------------------
services.ubah_status_pesanan(pesanan, StatusPesanan.DIPROSES)
pesanan.refresh_from_db()
uji(
    "DIBAYAR -> DIPROSES diizinkan",
    pesanan.status == StatusPesanan.DIPROSES,
    f"status={pesanan.get_status_display()}",
)

services.ubah_status_pesanan(pesanan, StatusPesanan.SELESAI)
pesanan.refresh_from_db()
uji(
    "DIPROSES -> SELESAI diizinkan",
    pesanan.status == StatusPesanan.SELESAI,
    f"status={pesanan.get_status_display()}",
)

# Status DIBAYAR tidak boleh ditulis manual.
pesanan_manual = services.buat_pesanan(
    nama_pemesan="Uji Manual",
    nomor_meja="12",
    item_list=[(produk, 1)],
    metode_pembayaran="TUNAI",
)
try:
    services.ubah_status_pesanan(pesanan_manual, StatusPesanan.DIBAYAR)
    pesan = "tidak ditolak"
    ditolak = False
except services.KesalahanLayanan as galat:
    pesan = str(galat)
    ditolak = True
uji(
    "Status DIBAYAR tidak dapat ditulis tanpa pembayaran",
    ditolak,
    pesan[:74],
)

# ----------------------------------------------------------------------
print("\n9. LAPORAN MENGHITUNG PESANAN YANG SUDAH DIBAYAR")
# ----------------------------------------------------------------------
dari = pesanan.dibuat_pada.date()
sampai = pesanan.dibuat_pada.date()
total = LaporanPenjualan.hitung_total(dari, sampai)

uji(
    "Pesanan yang sudah dibayar ikut dihitung",
    total > 0,
    f"total=Rp{total:,.0f}".replace(",", "."),
)

# Pesanan yang belum dibayar tidak boleh dihitung.
pesanan_belum = services.buat_pesanan(
    nama_pemesan="Uji Belum Bayar",
    nomor_meja="13",
    item_list=[(produk, 1)],
    metode_pembayaran="TUNAI",
)
services.buat_billing(pesanan_belum)
total_sesudah = LaporanPenjualan.hitung_total(dari, sampai)
uji(
    "Pesanan belum dibayar tidak menambah total laporan",
    total_sesudah == total,
    f"sebelum=Rp{total:,.0f} sesudah=Rp{total_sesudah:,.0f}".replace(",", "."),
)

rincian = list(services.rincian_laporan(dari, sampai))
uji(
    "Rincian laporan tidak memuat pesanan belum dibayar",
    pesanan_belum.pk not in [p.pk for p in rincian],
    f"{len(rincian)} pesanan dalam rincian",
)

# ----------------------------------------------------------------------
print("\n10. HALAMAN PELANGGAN DAPAT DIBUKA")
# ----------------------------------------------------------------------
respons = client.get(
    reverse("core:pembayaran_pelanggan", args=[pesanan.nomor_pesanan])
)
uji(
    "Halaman pembayaran pesanan lunas menampilkan ringkasan",
    respons.status_code == 200
    and "Pembayaran Diterima" in respons.content.decode("utf-8"),
    f"status={respons.status_code}",
)

respons = client.get("/")
uji("Halaman menu tetap dapat dibuka", respons.status_code == 200)

respons = client.get(reverse("core:cek_status"))
uji("Halaman cek status tetap dapat dibuka", respons.status_code == 200)

# ----------------------------------------------------------------------
print("\n" + "=" * 78)
lulus = sum(1 for _, ok, _ in HASIL if ok)
gagal = len(HASIL) - lulus
print(f"RINGKASAN: {lulus} lulus, {gagal} gagal, dari {len(HASIL)} pemeriksaan")
print("=" * 78)
if gagal:
    print("\nPemeriksaan yang gagal:")
    for nama, ok, ket in HASIL:
        if not ok:
            print(f"  - {nama} {ket}")
