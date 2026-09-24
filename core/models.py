"""
Model Django - Sistem Informasi Restoran Dapur Ina Aina
======================================================

File ini adalah implementasi langsung dari Class Diagram
(Class_Diagram_Dapur_Ina_Aina.drawio). Setiap class pada diagram menjadi
satu model Django (satu tabel SQLite), setiap atribut menjadi field,
dan setiap relasi (asosiasi / komposisi) menjadi ForeignKey dengan
on_delete yang mencerminkan jenis relasinya:

  - Asosiasi terarah (-->)   -> ForeignKey(..., on_delete=PROTECT)
                                (induk tidak boleh dihapus jika masih dipakai)
  - Komposisi (part-of, ikut terhapus) -> ForeignKey(..., on_delete=CASCADE)
                                (anak ikut terhapus jika induk dihapus)

Konvensi penamaan kelas dan atribut memakai bahasa Indonesia,
konsisten dengan Use Case, Activity, dan Class Diagram sebelumnya.

Riwayat perbaikan
-----------------
1. Produk.perbarui_status_stok() sebelumnya menyimpan dengan
   update_fields=["status_stok"] saja. Akibatnya perubahan nilai stok
   pada Produk.tambah_stok() dan Produk.kurangi_stok() hanya berubah di
   memori dan tidak pernah tersimpan ke basis data, sehingga stok tidak
   berkurang saat pesanan dibuat dan tidak kembali saat pesanan
   dibatalkan. Perbaikan: nilai stok ikut disimpan.

2. Produk.kurangi_stok(), tambah_stok(), dan atur_stok() sebelumnya
   menghitung dari nilai yang tersimpan di memori objek (self.stok),
   lalu menyimpan hasilnya sebagai nilai akhir. Bila satu objek Produk
   dipakai untuk beberapa pesanan, nilai yang tertulis dapat menimpa
   perubahan yang sudah terjadi di basis data sehingga stok berkurang
   lebih banyak dari seharusnya. Perbaikan: perhitungan dikerjakan
   langsung oleh basis data memakai F(), dan nilai stok dibaca ulang
   setelah perubahan.

3. Pesanan.hitung_total() dan Billing.buat_dari_pesanan() membulatkan
   nilai pajak ke 2 angka desimal sebelum dijumlahkan, supaya nilai
   subtotal + pajak selalu sama dengan total yang tersimpan
   (menghindari selisih pembulatan pada perhitungan uang).
"""

from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F
from django.utils import timezone

# Pajak / service charge flat 10 persen (lihat PREPROD.md bagian 2).
# Ubah di satu tempat ini bila besarannya berbeda.
PAJAK_PERSEN = Decimal("10")

# Semua nilai uang dibulatkan ke 2 angka desimal dengan pembulatan
# setengah ke atas, mengikuti kebiasaan perhitungan uang.
DUA_DESIMAL = Decimal("0.01")


def bulatkan_rupiah(nilai):
    """Membulatkan nilai uang ke 2 angka desimal (ROUND_HALF_UP)."""
    return Decimal(nilai).quantize(DUA_DESIMAL, rounding=ROUND_HALF_UP)


# ======================================================================
# ENUM (diimplementasikan sebagai TextChoices, sesuai kolom «enum» di
# Class Diagram: Role, KategoriEnum, StatusPesanan, MetodePembayaran,
# PeriodeLaporan)
# ======================================================================

class Role(models.TextChoices):
    ADMINISTRATOR = "ADMINISTRATOR", "Administrator"
    KASIR = "KASIR", "Kasir"


class KategoriEnum(models.TextChoices):
    MAKANAN_UTAMA = "MAKANAN_UTAMA", "Makanan Utama"
    APPETIZER = "APPETIZER", "Appetizer"
    MINUMAN = "MINUMAN", "Minuman"


class StatusPesanan(models.TextChoices):
    """Status pesanan.

    Sejak alur pembayaran diubah menjadi bayar di awal (2026-09-23),
    urutan statusnya adalah:

        BARU  -> bayar di muka (Tunai atau QRIS)
        DIBAYAR -> dapur mulai mengerjakan
        DIPROSES -> pesanan diserahkan ke pelanggan
        SELESAI

    Pesanan berstatus BARU berarti belum dibayar. Karena itu BARU
    ditampilkan sebagai "Menunggu Pembayaran" pada antarmuka, supaya
    pelanggan dan kasir langsung memahami bahwa langkah berikutnya
    adalah membayar, bukan menunggu dapur.

    DIBAYAR berada di awal alur karena pembayaran dilakukan sebelum
    dapur mengerjakan pesanan, namun dapur tetap dilacak melalui
    DIPROSES dan SELESAI.
    """

    BARU = "BARU", "Menunggu Pembayaran"
    DIBAYAR = "DIBAYAR", "Dibayar"
    DIPROSES = "DIPROSES", "Diproses"
    SELESAI = "SELESAI", "Selesai"
    DIBATALKAN = "DIBATALKAN", "Dibatalkan"


class MetodePembayaran(models.TextChoices):
    """Metode pembayaran yang tersedia bagi pelanggan.

    Tunai   : dibayar langsung di kasir. Kasir memasukkan uang yang
              diterima dan sistem menghitung kembalian.
    QRIS    : pembayaran non tunai melalui pemindaian kode QR.
              Pada versi ini QRIS masih berupa mockup (lihat
              core/gateway.py), tetapi alur verifikasi statusnya sama
              dengan gateway sungguhan.
    """

    TUNAI = "TUNAI", "Tunai"
    QRIS = "QRIS", "QRIS (Non Tunai)"


class StatusTransaksi(models.TextChoices):
    """Status transaksi di sisi payment gateway.

    Dipakai oleh model TransaksiGateway untuk mencatat perjalanan
    pembayaran non tunai:

        MENUNGGU    : kode QR sudah dibuat dan menunggu dipindai
        DIBAYAR     : gateway menyatakan pembayaran berhasil
        GAGAL       : pembayaran ditolak atau dibatalkan
        KEDALUWARSA : kode QR melewati masa berlaku

    Khusus pada mockup, MENUNGGU berubah menjadi DIBAYAR setelah
    pelanggan menekan tombol simulasi bayar (lihat core/services.py)
    atau setelah kasir memeriksa status ke gateway.
    """

    MENUNGGU = "MENUNGGU", "Menunggu Pembayaran"
    DIBAYAR = "DIBAYAR", "Dibayar"
    GAGAL = "GAGAL", "Gagal"
    KEDALUWARSA = "KEDALUWARSA", "Kedaluwarsa"


class PeriodeLaporan(models.TextChoices):
    MINGGUAN = "MINGGUAN", "Mingguan"
    BULANAN = "BULANAN", "Bulanan"


class StatusStok(models.TextChoices):
    TERSEDIA = "TERSEDIA", "Tersedia"
    HABIS = "HABIS", "Habis"


# ======================================================================
# Pengguna  (Kasir / Administrator)
# ======================================================================

class Pengguna(models.Model):
    """Kasir dan Administrator. Password disimpan ter-hash (never plaintext)."""

    username = models.CharField(max_length=50, unique=True)
    password_hash = models.CharField(max_length=255)
    nama = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=Role.choices)
    aktif = models.BooleanField(default=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pengguna"
        verbose_name = "Pengguna"
        verbose_name_plural = "Pengguna"

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    def set_password(self, raw_password):
        """Menyimpan password dalam bentuk hash (Django make_password).

        Password asli tidak pernah disimpan ke basis data.
        """
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password)

    def verifikasi_password(self, raw_password):
        """Mencocokkan password yang diisi dengan hash di basis data."""
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)

    @property
    def adalah_administrator(self):
        """True bila role pengguna adalah Administrator."""
        return self.role == Role.ADMINISTRATOR

    @property
    def adalah_kasir(self):
        """True bila role pengguna adalah Kasir."""
        return self.role == Role.KASIR


# ======================================================================
# KategoriProduk
# ======================================================================

class KategoriProduk(models.Model):
    """Kategori produk. Menentukan pengelompokan menu pada halaman
    pelanggan.

    Tipe kategori disimpan sebagai teks bebas, bukan pilihan tetap.
    Alasannya: menambah kategori baru tidak boleh bergantung pada
    kategori yang sudah ada. Administrator dapat mengetik tipe baru
    secara langsung, misalnya "Dessert" atau "Paket Hemat".

    Nilai awal yang disediakan perintah seed adalah Makanan Utama,
    Appetizer, dan Minuman (lihat KategoriEnum), tetapi daftar itu
    hanya nilai awal, bukan batas yang mengikat.
    """

    nama = models.CharField(max_length=50, unique=True)
    tipe = models.CharField(max_length=20)

    class Meta:
        db_table = "kategori_produk"
        verbose_name = "Kategori Produk"
        verbose_name_plural = "Kategori Produk"

    def __str__(self):
        return self.nama

    def boleh_dihapus(self):
        """Cek dependensi sebelum hapus (AD10).

        Kategori tidak boleh dihapus bila masih dipakai oleh produk,
        supaya data produk tidak kehilangan kategorinya.
        """
        return not self.produk_list.exists()


# ======================================================================
# Produk
# ======================================================================

class Produk(models.Model):
    # Asosiasi terarah KategoriProduk 1 --> 0..* Produk
    kategori = models.ForeignKey(
        KategoriProduk, on_delete=models.PROTECT, related_name="produk_list"
    )
    nama = models.CharField(max_length=100)
    deskripsi = models.TextField(blank=True, default="")
    harga = models.DecimalField(max_digits=10, decimal_places=2)
    stok = models.PositiveIntegerField(default=0)
    status_stok = models.CharField(
        max_length=10, choices=StatusStok.choices, default=StatusStok.HABIS
    )
    aktif = models.BooleanField(default=True)

    class Meta:
        db_table = "produk"
        verbose_name = "Produk"
        verbose_name_plural = "Produk"

    def __str__(self):
        return self.nama

    def perbarui_status_stok(self):
        """Menyamakan status_stok dengan nilai stok terbaru di basis data.

        Sesuai Activity Diagram AD07 (Mengelola Stok Produk): status
        Tersedia atau Habis ditentukan otomatis dari nilai stok, bukan
        diisi manual.

        Nilai stok dibaca ulang dari basis data terlebih dahulu, lalu
        status disimpan langsung dengan .update() supaya yang tertulis
        adalah nilai yang benar-benar tersimpan, bukan nilai lama yang
        mungkin masih tersimpan di memori objek ini.

        Mengembalikan nilai status_stok yang baru.
        """
        self.refresh_from_db()
        self.status_stok = StatusStok.TERSEDIA if self.stok > 0 else StatusStok.HABIS
        Produk.objects.filter(pk=self.pk).update(status_stok=self.status_stok)
        return self.status_stok

    def kurangi_stok(self, jumlah):
        """Mengurangi stok saat pesanan dibuat.

        Mengembalikan True bila berhasil, False bila stok tidak mencukupi.
        Sesuai AD02 (Memesan Menu). Pemanggilan dari sisi transaksi
        dilakukan di core/services.py di dalam satu transaksi basis data.

        Perhitungan dikerjakan langsung oleh basis data memakai F()
        supaya selalu memakai nilai stok terbaru. Cara ini mencegah
        nilai stok tertimpa oleh angka lama yang masih tersimpan di
        memori objek ini (lihat catatan di bagian atas berkas).
        """
        if jumlah <= 0:
            raise ValidationError("Jumlah harus lebih dari 0.")

        diperbarui = Produk.objects.filter(
            pk=self.pk, stok__gte=jumlah
        ).update(stok=F("stok") - jumlah)

        if not diperbarui:
            # Stok tidak mencukupi. Nilai stok tidak berubah.
            self.refresh_from_db()
            return False

        self.perbarui_status_stok()
        return True

    def tambah_stok(self, jumlah):
        """Menambah stok (input stok oleh Administrator, atau pengembalian
        stok saat pesanan dibatalkan). Sesuai AD07.

        Seperti kurangi_stok(), perhitungan dikerjakan oleh basis data
        agar selalu memakai nilai stok terbaru.
        """
        if jumlah <= 0:
            raise ValidationError("Jumlah harus lebih dari 0.")

        Produk.objects.filter(pk=self.pk).update(stok=F("stok") + jumlah)
        self.perbarui_status_stok()

    def atur_stok(self, jumlah_baru):
        """Menetapkan nilai stok secara langsung (halaman kelola stok).

        Berbeda dengan tambah_stok() yang menambah dari nilai sekarang,
        method ini memakai nilai hasil input Administrator sebagai nilai
        akhir stok. Status stok ikut diperbarui.
        """
        if jumlah_baru < 0:
            raise ValidationError("Jumlah stok tidak boleh negatif.")

        Produk.objects.filter(pk=self.pk).update(stok=jumlah_baru)
        self.perbarui_status_stok()
        return self.stok

    def boleh_dihapus(self):
        """Cek dependensi sebelum hapus (AD09).

        Produk yang pernah dipesan tidak boleh dihapus agar riwayat
        pesanan dan laporan tetap utuh. Produk semacam ini sebaiknya
        dinonaktifkan (aktif = False) saja.
        """
        return not self.detail_pesanan_list.exists()


# ======================================================================
# Pelanggan
# ======================================================================

class Pelanggan(models.Model):
    """Pelanggan tanpa akun/login (self-order berbasis nomor meja)."""

    nama = models.CharField(max_length=100)
    nomor_meja = models.CharField(max_length=10)

    class Meta:
        db_table = "pelanggan"
        verbose_name = "Pelanggan"
        verbose_name_plural = "Pelanggan"

    def __str__(self):
        return f"{self.nama} (Meja {self.nomor_meja})"


# ======================================================================
# Pesanan
# ======================================================================

class Pesanan(models.Model):
    # Kelanjutan status yang diizinkan, dipakai oleh ubah_status().
    #
    # Alur bayar di awal (berlaku sejak 2026-09-23):
    #
    #     BARU --(bayar)--> DIBAYAR --> DIPROSES --> SELESAI
    #       \                  \            \
    #        `------------------+------------+--> DIBATALKAN
    #
    # Pembayaran ditempatkan sebelum DIPROSES, jadi perpindahan dari
    # BARU ke DIBAYAR tidak dilakukan melalui ubah_status(), melainkan
    # oleh layanan pembayaran (core/services.py) setelah pembayaran
    # tersimpan. Perpindahan tersebut tidak dicantumkan di sini supaya
    # status DIBAYAR tidak dapat ditulis tanpa ada pembayaran.
    ALUR_STATUS_VALID = {
        StatusPesanan.BARU: [
            StatusPesanan.DIBATALKAN,
        ],
        StatusPesanan.DIBAYAR: [
            StatusPesanan.DIPROSES,
            StatusPesanan.DIBATALKAN,
        ],
        StatusPesanan.DIPROSES: [
            StatusPesanan.SELESAI,
            StatusPesanan.DIBATALKAN,
        ],
        StatusPesanan.SELESAI: [],
        StatusPesanan.DIBATALKAN: [],
    }

    nomor_pesanan = models.CharField(max_length=20, unique=True, editable=False)
    # Asosiasi terarah Pelanggan 1 --> 0..* Pesanan
    pelanggan = models.ForeignKey(
        Pelanggan, on_delete=models.PROTECT, related_name="pesanan_list"
    )
    status = models.CharField(
        max_length=20, choices=StatusPesanan.choices, default=StatusPesanan.BARU
    )
    # Metode pembayaran yang dipilih pelanggan saat memesan.
    #
    # Disimpan pada pesanan supaya kasir mengetahui cara pelanggan akan
    # membayar tanpa perlu bertanya lagi, dan supaya alur pembayaran
    # dapat dipisahkan sejak awal: tunai ditangani langsung oleh kasir,
    # sedangkan QRIS menunggu konfirmasi gateway.
    #
    # Kolom ini hanya mencatat pilihan pelanggan. Pembayaran yang benar
    # benar terjadi tetap dicatat pada model Pembayaran.
    metode_dipilih = models.CharField(
        max_length=20,
        choices=MetodePembayaran.choices,
        default=MetodePembayaran.TUNAI,
    )
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "pesanan"
        verbose_name = "Pesanan"
        verbose_name_plural = "Pesanan"
        ordering = ["-dibuat_pada"]

    def __str__(self):
        return self.nomor_pesanan

    def save(self, *args, **kwargs):
        if not self.nomor_pesanan:
            self.nomor_pesanan = self._generate_nomor_pesanan()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_nomor_pesanan():
        # Format: PSN-YYYYMMDD-XXXX (XXXX = urutan pada hari itu)
        today = timezone.now().strftime("%Y%m%d")
        prefix = f"PSN-{today}-"
        terakhir = (
            Pesanan.objects.filter(nomor_pesanan__startswith=prefix)
            .order_by("-nomor_pesanan")
            .first()
        )
        urutan = int(terakhir.nomor_pesanan[-4:]) + 1 if terakhir else 1
        return f"{prefix}{urutan:04d}"

    def hitung_subtotal(self):
        """Menjumlahkan subtotal seluruh DetailPesanan. Sesuai Class Diagram.

        Harga satuan diambil dari DetailPesanan (bukan dari Produk) supaya
        perubahan harga produk di kemudian hari tidak mengubah nilai
        pesanan yang sudah terjadi.
        """
        total = sum(d.hitung_subtotal_item() for d in self.detail_list.all())
        return bulatkan_rupiah(total)

    def hitung_pajak(self, pajak_persen=PAJAK_PERSEN):
        """Menghitung nilai pajak dari subtotal, dibulatkan ke 2 desimal."""
        subtotal = self.hitung_subtotal()
        return bulatkan_rupiah(subtotal * Decimal(pajak_persen) / Decimal("100"))

    def hitung_total(self, pajak_persen=PAJAK_PERSEN):
        """Total = subtotal + pajak. Dipakai saat membuat Billing.

        Pajak dibulatkan lebih dulu, baru dijumlahkan, agar nilai
        subtotal + pajak selalu sama persis dengan total yang tersimpan.
        """
        return bulatkan_rupiah(self.hitung_subtotal() + self.hitung_pajak(pajak_persen))

    def boleh_ubah_ke(self, status_baru):
        """True bila perpindahan dari status sekarang ke status_baru diizinkan."""
        return status_baru in self.ALUR_STATUS_VALID.get(self.status, [])

    def ubah_status(self, status_baru):
        """Mengubah status pesanan dengan validasi alur.

        Alur bayar di awal (berlaku sejak 2026-09-23):

            BARU -> DIBAYAR -> DIPROSES -> SELESAI

        Pasangan BARU -> DIBAYAR tidak ditangani di sini karena
        perpindahan itu hanya boleh terjadi setelah pembayaran
        tersimpan. Penulisannya dilakukan oleh core/services.py.

        Bila status baru adalah DIBATALKAN, stok setiap item dikembalikan
        ke produk. Pada pesanan yang sudah dibayar, pembatalan juga
        berarti uang perlu dikembalikan kepada pelanggan; pengembalian
        dana itu dilakukan secara manual di kasir dan ditandai oleh
        perlu_pengembalian_dana().

        Mengembalikan True bila berhasil, False bila perpindahan status
        tidak diizinkan.
        """
        if not self.boleh_ubah_ke(status_baru):
            return False
        if status_baru == StatusPesanan.DIBATALKAN:
            for detail in self.detail_list.all():
                detail.produk.tambah_stok(detail.jumlah)
        self.status = status_baru
        self.save(update_fields=["status", "diperbarui_pada"])
        return True

    def sudah_dibayar(self):
        """True bila pesanan sudah dibayar.

        Pesanan dianggap sudah dibayar bila statusnya sudah melewati
        tahap pembayaran, yaitu DIBAYAR, DIPROSES, atau SELESAI. Status
        BARU berarti belum dibayar, dan DIBATALKAN bukan pembayaran yang
        sah karena pesanannya batal.

        Pemeriksaan ini juga melihat data Pembayaran, supaya pesanan
        yang pembayarannya tersimpan tetapi statusnya belum berpindah
        tetap dianggap sudah dibayar.
        """
        if self.status in (
            StatusPesanan.DIBAYAR,
            StatusPesanan.DIPROSES,
            StatusPesanan.SELESAI,
        ):
            return True
        return Pembayaran.objects.filter(billing__pesanan=self).exists()

    def boleh_dibayar(self):
        """Cek kelayakan bayar.

        Pesanan dapat dibayar hanya bila belum dibayar dan belum
        dibatalkan. Pembayaran dilakukan di awal, jadi pesanan berstatus
        BARU justru memang menunggu pembayaran.
        """
        if self.status == StatusPesanan.DIBATALKAN:
            return False
        return not self.sudah_dibayar()

    def boleh_dicetak(self):
        """True bila tagihan boleh dicetak atau diunduh sebagai PDF.

        Tagihan hanya dicetak setelah pembayaran tuntas. Aturan ini yang
        menjamin urutan yang diminta, yaitu pelanggan membayar lebih
        dahulu dan baru kemudian tagihannya dicetak.
        """
        return self.sudah_dibayar()

    def perlu_pengembalian_dana(self):
        """True bila pesanan dibatalkan setelah dibayar.

        Kasus ini berarti uang pelanggan harus dikembalikan. Aplikasi
        tidak memproses pengembalian dana secara otomatis, hanya
        menandainya supaya kasir mengetahui ada dana yang perlu
        dikembalikan.
        """
        if self.status != StatusPesanan.DIBATALKAN:
            return False
        return Pembayaran.objects.filter(billing__pesanan=self).exists()


# ======================================================================
# DetailPesanan
# ======================================================================

class DetailPesanan(models.Model):
    # Komposisi Pesanan 1 *-- 1..* DetailPesanan
    pesanan = models.ForeignKey(
        Pesanan, on_delete=models.CASCADE, related_name="detail_list"
    )
    # Asosiasi terarah Produk 1 --> 0..* DetailPesanan
    produk = models.ForeignKey(
        Produk, on_delete=models.PROTECT, related_name="detail_pesanan_list"
    )
    jumlah = models.PositiveIntegerField()
    harga_satuan = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "detail_pesanan"
        verbose_name = "Detail Pesanan"
        verbose_name_plural = "Detail Pesanan"

    def __str__(self):
        return f"{self.produk.nama} x{self.jumlah}"

    def save(self, *args, **kwargs):
        if not self.harga_satuan:
            # Harga disalin saat item dibuat supaya nilai transaksi
            # tidak berubah bila harga produk diubah kemudian.
            self.harga_satuan = self.produk.harga
        super().save(*args, **kwargs)

    def hitung_subtotal_item(self):
        """Subtotal satu baris = harga_satuan dikali jumlah."""
        return bulatkan_rupiah(self.harga_satuan * self.jumlah)


# ======================================================================
# Billing
# ======================================================================

class Billing(models.Model):
    # Komposisi Pesanan 1 *-- 0..1 Billing
    pesanan = models.OneToOneField(
        Pesanan, on_delete=models.CASCADE, related_name="billing"
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    pajak = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    dicetak_pada = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "billing"
        verbose_name = "Billing"
        verbose_name_plural = "Billing"

    def __str__(self):
        return f"Billing #{self.pk} - {self.pesanan.nomor_pesanan}"

    @classmethod
    def buat_dari_pesanan(cls, pesanan, pajak_persen=PAJAK_PERSEN):
        """Membuat (atau memperbarui) billing dari rincian pesanan (AD05).

        Memakai update_or_create supaya pemanggilan berulang tidak
        menghasilkan billing ganda untuk satu pesanan.
        """
        subtotal = pesanan.hitung_subtotal()
        pajak = pesanan.hitung_pajak(pajak_persen)
        billing, _ = cls.objects.update_or_create(
            pesanan=pesanan,
            defaults={
                "subtotal": subtotal,
                "pajak": pajak,
                "total": bulatkan_rupiah(subtotal + pajak),
            },
        )
        return billing

    def cetak(self):
        """Mencatat waktu billing ditampilkan untuk dicetak (AD05)."""
        self.dicetak_pada = timezone.now()
        self.save(update_fields=["dicetak_pada"])

    def hitung_total_item(self):
        """Jumlah seluruh porsi/item pada pesanan ini.

        Dihitung dari DetailPesanan, bukan disimpan sebagai kolom,
        supaya nilainya selalu ikut rincian pesanan terbaru. Dipakai
        pada ringkasan billing dan bukti pembayaran agar kasir tahu
        berapa banyak item yang dibayar, bukan hanya nominalnya.
        """
        return sum(d.jumlah for d in self.pesanan.detail_list.all())

    @property
    def rincian_jumlah(self):
        """Jumlah baris menu pada pesanan ini (misalnya 3 jenis menu)."""
        return self.pesanan.detail_list.count()


# ======================================================================
# Pembayaran
# ======================================================================

class Pembayaran(models.Model):
    # Komposisi Billing 1 *-- 0..1 Pembayaran
    billing = models.OneToOneField(
        Billing, on_delete=models.CASCADE, related_name="pembayaran"
    )
    # Asosiasi terarah Pengguna(Kasir) 1 --> 0..* Pembayaran
    kasir = models.ForeignKey(
        Pengguna, on_delete=models.PROTECT, related_name="pembayaran_list"
    )
    metode = models.CharField(max_length=20, choices=MetodePembayaran.choices)
    jumlah_diterima = models.DecimalField(max_digits=10, decimal_places=2)
    kembalian = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    nomor_referensi = models.CharField(max_length=50, blank=True, default="")
    dibayar_pada = models.DateTimeField(auto_now_add=True)
    # Kasir yang mengonfirmasi pembayaran non tunai setelah memeriksa
    # status di gateway. Untuk pembayaran tunai, kolom ini sama dengan
    # kasir karena uang diterima langsung oleh kasir yang sama.
    # Kolom terpisah dipakai supaya riwayat pemeriksaan tetap terekam
    # bila yang menangani berbeda orang.
    dikonfirmasi_kasir = models.ForeignKey(
        Pengguna,
        on_delete=models.PROTECT,
        related_name="pembayaran_dikonfirmasi_list",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "pembayaran"
        verbose_name = "Pembayaran"
        verbose_name_plural = "Pembayaran"

    def __str__(self):
        return f"Pembayaran #{self.pk} - {self.billing.pesanan.nomor_pesanan}"

    def hitung_kembalian(self):
        """Menghitung kembalian.

        Khusus tunai: jumlah diterima dikurangi total tagihan. Bila
        jumlah diterima kurang dari total, nilai kembalian 0 karena
        pembayaran semacam itu ditolak oleh validasi().
        Pembayaran QRIS tidak menghasilkan kembalian karena nilainya
        tepat sebesar total tagihan.
        """
        if self.metode == MetodePembayaran.TUNAI:
            selisih = self.jumlah_diterima - self.billing.total
            self.kembalian = bulatkan_rupiah(max(selisih, Decimal("0")))
        else:
            self.kembalian = Decimal("0")
        return self.kembalian

    def validasi(self):
        """Memvalidasi data pembayaran sebelum disimpan.

        Tunai : jumlah uang diterima harus menutupi total tagihan.
        QRIS  : nomor referensi wajib diisi. Nomor ini berasal dari
                transaksi gateway yang sudah dinyatakan berhasil
                (lihat TransaksiGateway), jadi pembayaran QRIS tidak
                pernah tersimpan tanpa bukti dari gateway.
        """
        if self.metode == MetodePembayaran.TUNAI:
            return self.jumlah_diterima >= self.billing.total
        return bool(self.nomor_referensi)

    def pesan_kesalahan(self):
        """Pesan error berbahasa Indonesia sesuai penyebab tidak validnya."""
        if self.metode == MetodePembayaran.TUNAI:
            return (
                "Jumlah uang diterima kurang dari total tagihan. "
                f"Total tagihan Rp{self.billing.total:,.0f}."
            )
        return "Nomor referensi pembayaran QRIS wajib diisi."

    def adalah_non_tunai(self):
        """True bila pembayaran ini melalui gateway (QRIS)."""
        return self.metode == MetodePembayaran.QRIS


# ======================================================================
# TransaksiGateway
# ======================================================================

class TransaksiGateway(models.Model):
    """Transaksi pembayaran non tunai (QRIS) di sisi payment gateway.

    Model ini memisahkan dua hal yang sengaja tidak digabung:

      - Billing  : berapa yang harus dibayar (dihitung dari pesanan)
      - Transaksi: bagaimana pembayaran diproses oleh gateway

    Pemisahan ini yang membuat pembayaran non tunai dapat diperiksa
    statusnya. Kasir dapat melihat apakah gateway sudah menyatakan
    pembayaran berhasil atau belum, sebelum menekan tombol konfirmasi.

    Sejak versi ini gateway masih berupa mockup (lihat core/gateway.py),
    tetapi bentuk datanya sudah sama dengan gateway sungguhan sehingga
    penggantian penyedia tidak mengubah model ini.
    """

    # Komposisi Pesanan 1 *-- 0..* TransaksiGateway
    # Satu pesanan dapat memiliki beberapa percobaan transaksi, misalnya
    # ketika kode QR pertama kedaluwarsa lalu dibuat kode baru.
    pesanan = models.ForeignKey(
        Pesanan, on_delete=models.CASCADE, related_name="transaksi_list"
    )
    # Penyedia yang menangani transaksi, berguna bila kelak berganti
    # penyedia dan transaksi lama tetap perlu dibaca.
    penyedia = models.CharField(max_length=30, default="MOCK")
    # Nomor transaksi di sisi gateway (pada mockup berawalan MOCK-).
    kode_bayar = models.CharField(max_length=60, unique=True)
    # Isi QR yang dipindai pelanggan. Disimpan agar kode QR lama masih
    # dapat ditampilkan ulang tanpa memanggil gateway.
    qr_string = models.TextField(blank=True, default="")
    jumlah = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=StatusTransaksi.choices,
        default=StatusTransaksi.MENUNGGU,
    )
    kedaluwarsa_pada = models.DateTimeField(null=True, blank=True)
    dibayar_pada = models.DateTimeField(null=True, blank=True)
    # Waktu notifikasi gateway diterima. Dipakai untuk memastikan
    # pemeriksaan tanda tangan hanya terjadi pada notifikasi yang sah.
    notifikasi_pada = models.DateTimeField(null=True, blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "transaksi_gateway"
        verbose_name = "Transaksi Gateway"
        verbose_name_plural = "Transaksi Gateway"
        ordering = ["-dibuat_pada"]
        # Satu pesanan hanya boleh punya satu transaksi aktif yang belum
        # selesai. Batasan ini mencegah kasir membuat dua kode QR untuk
        # tagihan yang sama secara tidak sengaja, yang dapat berujung
        # pada pembayaran ganda.
        constraints = [
            models.UniqueConstraint(
                fields=["pesanan"],
                condition=models.Q(status=StatusTransaksi.MENUNGGU),
                name="satu_transaksi_menunggu_per_pesanan",
            )
        ]

    def __str__(self):
        return f"{self.kode_bayar} ({self.get_status_display()})"

    @property
    def sudah_dibayar(self):
        """True bila gateway sudah menyatakan pembayaran berhasil."""
        return self.status == StatusTransaksi.DIBAYAR

    def sudah_kedaluwarsa(self):
        """True bila kode QR sudah melewati masa berlakunya.

        Perbandingan memakai waktu sekarang, jadi status ini dapat
        berubah tanpa perlu ada proses latar belakang yang mengubahnya.
        """
        if self.kedaluwarsa_pada is None:
            return False
        return timezone.now() > self.kedaluwarsa_pada

    def tandai_dibayar(self):
        """Menandai transaksi berhasil dan menyimpan waktunya."""
        self.status = StatusTransaksi.DIBAYAR
        self.dibayar_pada = timezone.now()
        self.notifikasi_pada = self.notifikasi_pada or timezone.now()
        self.save(
            update_fields=["status", "dibayar_pada", "notifikasi_pada"]
        )
        return self


# ======================================================================
# LaporanPenjualan
# ======================================================================

class LaporanPenjualan(models.Model):
    periode = models.CharField(max_length=20, choices=PeriodeLaporan.choices)
    tanggal_mulai = models.DateField()
    tanggal_selesai = models.DateField()
    total_penjualan = models.DecimalField(max_digits=12, decimal_places=2)
    dibuat_pada = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "laporan_penjualan"
        verbose_name = "Laporan Penjualan"
        verbose_name_plural = "Laporan Penjualan"
        ordering = ["-dibuat_pada"]

    def __str__(self):
        return (
            f"Laporan {self.get_periode_display()} "
            f"{self.tanggal_mulai} s/d {self.tanggal_selesai}"
        )

    # Status pesanan yang dihitung sebagai penjualan.
    #
    # Sejak alur bayar di awal, status DIBAYAR bukan lagi status akhir.
    # Pesanan yang sudah dibayar bergerak ke DIPROSES lalu SELESAI,
    # sehingga ketiganya harus ikut dihitung. Bila hanya DIBAYAR yang
    # dihitung, laporan akan kehilangan hampir seluruh transaksi karena
    # pesanan yang sudah selesai dikerjakan tidak lagi berstatus DIBAYAR.
    STATUS_TERHITUNG = (
        StatusPesanan.DIBAYAR,
        StatusPesanan.DIPROSES,
        StatusPesanan.SELESAI,
    )

    @classmethod
    def hitung_total(cls, tanggal_mulai, tanggal_selesai):
        """Menghitung total penjualan pada rentang tanggal.

        Yang dihitung adalah pesanan yang sudah dibayar, yaitu berstatus
        DIBAYAR, DIPROSES, atau SELESAI. Pesanan tanpa data billing
        dilewati agar tidak menimbulkan error.
        """
        pesanan_dibayar = Pesanan.objects.filter(
            status__in=cls.STATUS_TERHITUNG,
            dibuat_pada__date__gte=tanggal_mulai,
            dibuat_pada__date__lte=tanggal_selesai,
        )
        total = sum(
            p.billing.total for p in pesanan_dibayar if hasattr(p, "billing")
        )
        return bulatkan_rupiah(total)

    @classmethod
    def generate(cls, periode, tanggal_mulai, tanggal_selesai):
        """Membuat data laporan penjualan untuk periode yang dipilih (AD08)."""
        total = cls.hitung_total(tanggal_mulai, tanggal_selesai)
        return cls.objects.create(
            periode=periode,
            tanggal_mulai=tanggal_mulai,
            tanggal_selesai=tanggal_selesai,
            total_penjualan=total,
        )
