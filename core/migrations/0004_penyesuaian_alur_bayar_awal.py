"""
Penyesuaian data lama untuk alur bayar di awal
==============================================

Perubahan alur pembayaran mengubah arti beberapa status, sehingga data
yang sudah ada perlu disesuaikan supaya tidak salah dibaca.

Alur lama (bayar di akhir)
    BARU -> DIPROSES -> SELESAI -> DIBAYAR
    Status DIPROSES dan SELESAI berarti pesanan belum dibayar.

Alur baru (bayar di awal)
    BARU -> DIBAYAR -> DIPROSES -> SELESAI
    Status DIPROSES dan SELESAI berarti pesanan sudah dibayar.

Akibat perubahan itu, dua hal harus ditangani:

1. Pesanan lama berstatus DIPROSES atau SELESAI belum dibayar, sebab
   pembayaran pada alur lama justru terjadi di akhir. Bila statusnya
   dibiarkan, laporan penjualan akan menghitungnya sebagai penjualan
   padahal uangnya belum diterima. Pesanan seperti itu dikembalikan ke
   BARU, yang pada alur baru berarti menunggu pembayaran.

2. Pembayaran lama dengan metode DEBIT atau KARTU_KREDIT memakai
   metode yang sudah tidak dipakai lagi. Metode pembayaran non tunai
   sekarang bernama QRIS, jadi nilainya disesuaikan. Nomor referensi
   lamanya dibiarkan apa adanya karena masih berguna sebagai riwayat.

Pesanan yang sudah berstatus DIBAYAR tidak diubah, karena pada kedua
alur status tersebut sama-sama berarti sudah dibayar.
"""

from django.db import migrations


def maju(apps, skema_editor):
    """Menyesuaikan data lama agar sesuai alur bayar di awal."""
    Pesanan = apps.get_model("core", "Pesanan")
    Pembayaran = apps.get_model("core", "Pembayaran")

    # 1. Pesanan DIPROSES atau SELESAI yang belum punya pembayaran
    #    dikembalikan ke BARU (menunggu pembayaran).
    for pesanan in Pesanan.objects.filter(status__in=["DIPROSES", "SELESAI"]):
        sudah_dibayar = Pembayaran.objects.filter(
            billing__pesanan=pesanan
        ).exists()
        if not sudah_dibayar:
            pesanan.status = "BARU"
            pesanan.save(update_fields=["status"])

    # 2. Metode pembayaran non tunai lama disesuaikan menjadi QRIS.
    Pembayaran.objects.filter(metode__in=["DEBIT", "KARTU_KREDIT"]).update(
        metode="QRIS"
    )


def mundur(apps, skema_editor):
    """Mengembalikan data ke alur lama.

    Pemunduran hanya mengembalikan nama metode pembayaran. Status
    pesanan tidak dapat dikembalikan sepenuhnya, karena pesanan yang
    dikembalikan ke BARU pada langkah maju tidak lagi diketahui apakah
    sebelumnya berstatus DIPROSES atau SELESAI.
    """
    Pembayaran = apps.get_model("core", "Pembayaran")
    Pembayaran.objects.filter(metode="QRIS", nomor_referensi="").update(
        metode="DEBIT"
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "core",
            "0003_pembayaran_dikonfirmasi_kasir_pesanan_metode_dipilih_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(maju, mundur),
    ]
