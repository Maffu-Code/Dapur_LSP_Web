"""
Perintah data contoh untuk presentasi (seed_demo).
Jalankan dengan:  python manage.py seed_demo

Membuat pesanan contoh pada berbagai status supaya setiap halaman dapat
ditunjukkan tanpa harus membuat data secara manual lebih dahulu.
Mengikuti alur bayar di awal, contoh yang dibuat adalah:

  - Pesanan BARU (menunggu pembayaran)
  - Pesanan DIBAYAR tunai (sudah dibayar, menunggu dapur)
  - Pesanan DIBAYAR QRIS (pembayaran non tunai melalui kode QR)
  - Pesanan DIPROSES (sudah dibayar, sedang dikerjakan)
  - Pesanan SELESAI (sudah dibayar dan sudah diserahkan)
  - Pesanan DIBATALKAN (contoh pengembalian stok)

Perintah ini memerlukan data dari `python manage.py seed` lebih dahulu
(akun kasir dan daftar produk).

Peringatan: perintah ini menambahkan pesanan contoh ke basis data dan
memotong stok produk sesuai pesanan tersebut. Jalankan pada basis data
presentasi, bukan pada data yang sudah dipakai sungguhan.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from core.models import Pengguna, Produk, Role
from core import services


class Command(BaseCommand):
    help = "Membuat pesanan contoh pada berbagai status untuk keperluan presentasi."

    def handle(self, *args, **options):
        kasir = Pengguna.objects.filter(role=Role.KASIR, aktif=True).first()
        if kasir is None:
            self.stdout.write(self.style.ERROR(
                "Akun kasir belum ada. Jalankan 'python manage.py seed' lebih dahulu."
            ))
            return

        produk_tersedia = list(Produk.objects.filter(aktif=True, stok__gt=0))
        if not produk_tersedia:
            self.stdout.write(self.style.ERROR(
                "Belum ada produk dengan stok tersedia. Jalankan "
                "'python manage.py seed' lebih dahulu."
            ))
            return

        # Ambil produk berdasarkan nama agar isi contoh tetap sama
        # walau urutan data berubah.
        def cari(nama):
            for produk in produk_tersedia:
                if produk.nama == nama:
                    return produk
            return None

        nasi = cari("Nasi Goreng Spesial") or produk_tersedia[0]
        teh = cari("Es Teh Manis") or produk_tersedia[-1]
        tahu = cari("Tahu Crispy") or produk_tersedia[0]

        dibuat = []

        # --- Pesanan BARU: menunggu pembayaran, belum dibayar.
        pesanan_baru = services.buat_pesanan(
            nama_pemesan="Rina",
            nomor_meja="3",
            item_list=[(nasi, 2), (teh, 2)],
            metode_pembayaran="TUNAI",
        )
        dibuat.append(pesanan_baru)

        # --- Pesanan DIBAYAR tunai: sudah dibayar, menunggu dapur.
        pesanan_tunai = services.buat_pesanan(
            nama_pemesan="Andi",
            nomor_meja="2",
            item_list=[(nasi, 3), (teh, 3)],
            metode_pembayaran="TUNAI",
        )
        billing_tunai = services.buat_billing(pesanan_tunai)
        services.proses_pembayaran(
            billing=billing_tunai,
            kasir=kasir,
            metode="TUNAI",
            jumlah_diterima=Decimal("150000.00"),
        )
        dibuat.append(pesanan_tunai)

        # --- Pesanan DIBAYAR QRIS: pembayaran non tunai melalui kode QR.
        #     Transaksi gateway dibuat lebih dahulu, lalu ditandai
        #     berhasil, baru pembayarannya dikonfirmasi kasir. Urutan ini
        #     sama dengan alur yang dijalani pengguna.
        pesanan_qris = services.buat_pesanan(
            nama_pemesan="Dewi",
            nomor_meja="9",
            item_list=[(tahu, 2), (teh, 2)],
            metode_pembayaran="QRIS",
        )
        billing_qris = services.buat_billing(pesanan_qris)
        transaksi_qris, _ = services.mulai_pembayaran_qris(pesanan_qris)
        services.simulasi_bayar_qris(transaksi_qris)
        services.proses_pembayaran(
            billing=billing_qris,
            kasir=kasir,
            metode="QRIS",
            transaksi=transaksi_qris,
        )
        dibuat.append(pesanan_qris)

        # --- Pesanan DIPROSES: sudah dibayar dan sedang dikerjakan dapur.
        pesanan_proses = services.buat_pesanan(
            nama_pemesan="Budi",
            nomor_meja="5",
            item_list=[(tahu, 3)],
            metode_pembayaran="TUNAI",
        )
        billing_proses = services.buat_billing(pesanan_proses)
        services.proses_pembayaran(
            billing=billing_proses,
            kasir=kasir,
            metode="TUNAI",
            jumlah_diterima=Decimal("100000.00"),
        )
        pesanan_proses.ubah_status("DIPROSES")
        dibuat.append(pesanan_proses)

        # --- Pesanan SELESAI: sudah dibayar dan sudah diserahkan.
        pesanan_selesai = services.buat_pesanan(
            nama_pemesan="Sari",
            nomor_meja="7",
            item_list=[(nasi, 1), (tahu, 1)],
            metode_pembayaran="TUNAI",
        )
        billing_selesai = services.buat_billing(pesanan_selesai)
        services.proses_pembayaran(
            billing=billing_selesai,
            kasir=kasir,
            metode="TUNAI",
            jumlah_diterima=Decimal("100000.00"),
        )
        pesanan_selesai.ubah_status("DIPROSES")
        pesanan_selesai.ubah_status("SELESAI")
        dibuat.append(pesanan_selesai)

        # --- Pesanan DIBATALKAN: contoh pengembalian stok.
        pesanan_batal = services.buat_pesanan(
            nama_pemesan="Tono",
            nomor_meja="1",
            item_list=[(teh, 4)],
            metode_pembayaran="TUNAI",
        )
        pesanan_batal.ubah_status("DIBATALKAN")
        dibuat.append(pesanan_batal)

        self.stdout.write(self.style.SUCCESS(
            f"{len(dibuat)} pesanan contoh berhasil dibuat:"
        ))
        for pesanan in dibuat:
            self.stdout.write(
                f"  {pesanan.nomor_pesanan}  "
                f"{pesanan.pelanggan.nama:6}  meja {pesanan.pelanggan.nomor_meja:2}  "
                f"status {pesanan.get_status_display()}"
            )

        self.stdout.write("")
        self.stdout.write(
            "Buka halaman Laporan Penjualan dengan periode bulan berjalan "
            "untuk melihat pesanan yang sudah dibayar."
        )
