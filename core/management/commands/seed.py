"""
Perintah setup data awal (seed).
Jalankan dengan:  python manage.py seed

Mengisi data yang wajib ada agar aplikasi dapat dipakai:
  - Akun Administrator default (admin)
  - Akun Kasir default (kasir)
  - 3 kategori produk wajib: Makanan Utama, Appetizer, Minuman
  - Contoh produk untuk setiap kategori, lengkap dengan stok awal

Perintah ini bersifat idempoten (aman dijalankan berulang). Data yang
sudah ada akan dilewati, tidak digandakan.

Untuk data contoh yang lebih banyak (termasuk pesanan yang sudah
dibayar) jalankan:  python manage.py seed_demo
"""

from decimal import Decimal

from django.core.management.base import BaseCommand

from core.models import (
    KategoriEnum,
    KategoriProduk,
    Pengguna,
    Produk,
    Role,
    StatusStok,
)


class Command(BaseCommand):
    help = (
        "Mengisi data awal: akun admin dan kasir, 3 kategori produk wajib, "
        "dan contoh produk beserta stok awalnya."
    )

    def handle(self, *args, **options):
        self._buat_pengguna()
        kategori = self._buat_kategori()
        self._buat_produk(kategori)
        self.stdout.write(self.style.SUCCESS("Seed selesai."))
        self.stdout.write("")
        self.stdout.write("Akun untuk masuk:")
        self.stdout.write("  Administrator  username: admin  password: admin123")
        self.stdout.write("  Kasir          username: kasir  password: kasir123")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "Ganti password tersebut sebelum presentasi."
        ))

    # ------------------------------------------------------------------
    # Akun pengguna
    # ------------------------------------------------------------------
    def _buat_pengguna(self):
        """Membuat akun Administrator dan Kasir bawaan."""
        daftar = [
            ("admin", "Administrator", Role.ADMINISTRATOR, "admin123"),
            ("kasir", "Kasir Restoran", Role.KASIR, "kasir123"),
        ]

        for username, nama, role, password in daftar:
            if Pengguna.objects.filter(username=username).exists():
                self.stdout.write(f"Akun {username} sudah ada, dilewati.")
                continue

            pengguna = Pengguna(username=username, nama=nama, role=role)
            pengguna.set_password(password)
            pengguna.save()
            self.stdout.write(
                self.style.SUCCESS(f"Akun {username} dibuat (peran {role}).")
            )

    # ------------------------------------------------------------------
    # Kategori produk
    # ------------------------------------------------------------------
    def _buat_kategori(self):
        """Membuat 3 kategori wajib dan mengembalikannya dalam kamus."""
        kategori_awal = [
            ("Makanan Utama", KategoriEnum.MAKANAN_UTAMA),
            ("Appetizer", KategoriEnum.APPETIZER),
            ("Minuman", KategoriEnum.MINUMAN),
        ]

        hasil = {}
        for nama, tipe in kategori_awal:
            objek, dibuat = KategoriProduk.objects.get_or_create(
                nama=nama, defaults={"tipe": tipe}
            )
            hasil[nama] = objek
            if dibuat:
                self.stdout.write(self.style.SUCCESS(f"Kategori dibuat: {nama}"))
            else:
                self.stdout.write(f"Kategori sudah ada: {nama}")

        return hasil

    # ------------------------------------------------------------------
    # Contoh produk
    # ------------------------------------------------------------------
    def _buat_produk(self, kategori):
        """Membuat contoh produk pada setiap kategori beserta stok awalnya."""
        contoh = [
            # (nama, kategori, harga, stok awal, deskripsi)
            (
                "Nasi Goreng Spesial",
                "Makanan Utama",
                "25000.00",
                20,
                "Nasi goreng dengan telur, ayam, dan kerupuk.",
            ),
            (
                "Ayam Bakar Kecap",
                "Makanan Utama",
                "32000.00",
                15,
                "Ayam bakar dengan sambal kecap dan lalapan.",
            ),
            (
                "Mie Goreng Jawa",
                "Makanan Utama",
                "22000.00",
                18,
                "Mie goreng bumbu Jawa dengan sayuran.",
            ),
            (
                "Tahu Crispy",
                "Appetizer",
                "12000.00",
                25,
                "Tahu goreng tepung renyah dengan saus kacang.",
            ),
            (
                "Pisang Goreng Keju",
                "Appetizer",
                "15000.00",
                20,
                "Pisang goreng dengan taburan keju dan susu.",
            ),
            (
                "Es Teh Manis",
                "Minuman",
                "6000.00",
                40,
                "Teh manis dingin dengan es batu.",
            ),
            (
                "Es Jeruk Segar",
                "Minuman",
                "9000.00",
                35,
                "Perasan jeruk dengan es batu dan gula.",
            ),
            (
                "Kopi Hitam",
                "Minuman",
                "10000.00",
                0,
                "Kopi tubruk tanpa gula. Sedang habis.",
            ),
        ]

        for nama, nama_kategori, harga, stok, deskripsi in contoh:
            if Produk.objects.filter(nama=nama).exists():
                self.stdout.write(f"Produk sudah ada: {nama}")
                continue

            Produk.objects.create(
                kategori=kategori[nama_kategori],
                nama=nama,
                deskripsi=deskripsi,
                harga=Decimal(harga),
                stok=stok,
                status_stok=(
                    StatusStok.TERSEDIA if stok > 0 else StatusStok.HABIS
                ),
                aktif=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Produk dibuat: {nama}"))
