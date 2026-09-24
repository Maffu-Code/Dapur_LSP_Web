"""
Layanan transaksi aplikasi Dapur Ina Aina
=========================================

Berkas ini memuat proses yang menyentuh lebih dari satu tabel basis data
dan harus berhasil seluruhnya atau gagal seluruhnya (transaksi).

Pembagian tanggung jawab
------------------------
- Model (core/models.py)
  Menjaga aturan pada satu baris data, misalnya Produk.kurangi_stok()
  dan Pesanan.ubah_status().

- Layanan (berkas ini)
  Menjalankan urutan beberapa model dalam satu transaksi basis data,
  misalnya membuat pesanan sekaligus memotong stok beberapa produk.

- View (core/views.py)
  Menerima permintaan, memvalidasi formulir, memanggil layanan, lalu
  menampilkan hasil atau pesan kesalahan.

Alasan pemisahan ini: pada Class Diagram sudah ada dua class bertanda
«service», yaitu StokService dan LaporanService. Berkas ini adalah
perwujudan keduanya, sehingga kode program sejalan dengan rancangan.

Penanganan kesalahan
--------------------
Layanan menghentikan proses dengan melempar KesalahanLayanan yang
berisi pesan berbahasa Indonesia. View menangkap kesalahan tersebut
dan menampilkannya kepada pengguna. Dengan cara ini, aturan bisnis
tetap sama walau dipanggil dari halaman yang berbeda, dan pesan
kesalahan dapat diuji secara terpisah.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core import gateway as gateway_pembayaran
from core.models import (
    Billing,
    DetailPesanan,
    KategoriProduk,
    LaporanPenjualan,
    MetodePembayaran,
    Pelanggan,
    Pembayaran,
    PeriodeLaporan,
    Pesanan,
    Produk,
    StatusPesanan,
    TransaksiGateway,
)


class KesalahanLayanan(Exception):
    """Kesalahan aturan bisnis yang pesannya langsung ditampilkan ke pengguna.

    Dipakai untuk kondisi yang bisa dipahami pengguna, misalnya stok
    tidak mencukupi atau status tidak sesuai alur.
    """


# ======================================================================
# Layanan Pelanggan: membuat pesanan (AD02)
# ======================================================================

@transaction.atomic
def buat_pesanan(nama_pemesan, nomor_meja, item_list, metode_pembayaran=None):
    """Membuat pesanan baru beserta rinciannya dan memotong stok produk.

    Parameter
    ---------
    nama_pemesan     : str  - nama pelanggan (tanpa akun, dicatat untuk struk)
    nomor_meja       : str  - nomor meja tempat pelanggan duduk
    item_list        : list - daftar pasangan (Produk, jumlah)
    metode_pembayaran: str  - MetodePembayaran.TUNAI atau QRIS, pilihan
                              pelanggan saat memesan

    Mengembalikan objek Pesanan yang baru dibuat.

    Melempar KesalahanLayanan bila daftar item kosong, jumlah tidak
    sah, produk tidak aktif, atau stok tidak mencukupi.

    Seluruh langkah dibungkus @transaction.atomic, sehingga bila ada
    satu produk yang stoknya tidak mencukupi, pesanan dan pemotongan
    stok produk sebelumnya dibatalkan seluruhnya. Basis data tidak
    akan menyisakan pesanan setengah jadi.
    """
    if not item_list:
        raise KesalahanLayanan(
            "Pesanan tidak dapat dibuat karena belum ada produk yang dipilih."
        )

    # Metode pembayaran wajib berupa salah satu pilihan yang dikenal.
    # Pemeriksaan ini penting karena nilainya menentukan halaman
    # pembayaran mana yang dipakai kasir.
    metode_pembayaran = metode_pembayaran or MetodePembayaran.TUNAI
    if metode_pembayaran not in MetodePembayaran.values:
        raise KesalahanLayanan(
            f"Metode pembayaran '{metode_pembayaran}' tidak dikenal."
        )

    # --- Pemeriksaan awal seluruh item, sebelum ada data yang disimpan.
    # Langkah ini membuat pesan kesalahan dapat menyebut produk yang
    # bermasalah secara tepat, bukan berhenti di tengah proses.
    for produk, jumlah in item_list:
        if jumlah is None or jumlah <= 0:
            raise KesalahanLayanan(
                f"Jumlah untuk {produk.nama} harus lebih dari 0."
            )
        if not produk.aktif:
            raise KesalahanLayanan(
                f"Produk {produk.nama} sedang tidak dijual."
            )
        if produk.stok < jumlah:
            raise KesalahanLayanan(
                f"Stok {produk.nama} tersisa {produk.stok}, "
                f"sedangkan jumlah yang dipesan {jumlah}. "
                f"Kurangi jumlahnya atau pilih produk lain."
            )

    # --- Pelanggan dicatat setiap pesanan. Pelanggan tidak memiliki
    # akun, jadi data ini hanya dipakai untuk menandai meja dan nama.
    pelanggan = Pelanggan.objects.create(
        nama=nama_pemesan.strip(), nomor_meja=nomor_meja.strip()
    )

    pesanan = Pesanan.objects.create(
        pelanggan=pelanggan, metode_dipilih=metode_pembayaran
    )

    for produk, jumlah in item_list:
        DetailPesanan.objects.create(
            pesanan=pesanan, produk=produk, jumlah=jumlah
        )

    # --- Pemotongan stok dilakukan setelah seluruh rincian tersimpan.
    # Stok dicek ulang oleh method kurangi_stok sehingga tetap aman
    # walau ada perubahan stok di antara pemeriksaan awal dan langkah ini.
    for produk, jumlah in item_list:
        berhasil = produk.kurangi_stok(jumlah)
        if not berhasil:
            # Melempar kesalahan di dalam blok atomic akan membatalkan
            # seluruh perubahan pada fungsi ini.
            raise KesalahanLayanan(
                f"Stok {produk.nama} tidak mencukupi saat pesanan disimpan. "
                f"Pesanan dibatalkan, silakan ulangi pemesanan."
            )

    return pesanan


# ======================================================================
# Layanan Kasir: mengubah status pesanan (AD04)
# ======================================================================

@transaction.atomic
def ubah_status_pesanan(pesanan, status_baru):
    """Mengubah status pesanan dengan memeriksa alur status.

    Alur bayar di awal: BARU -> DIBAYAR -> DIPROSES -> SELESAI.
    Perpindahan ke DIBAYAR tidak dapat dilakukan melalui fungsi ini
    karena status tersebut hanya boleh ditulis oleh proses pembayaran
    (lihat proses_pembayaran()).

    Bila status baru adalah DIBATALKAN, stok setiap item dikembalikan
    ke produk. Pada pesanan yang sudah dibayar, pembatalan juga berarti
    dana perlu dikembalikan kepada pelanggan; hal itu ditandai oleh
    Pesanan.perlu_pengembalian_dana() dan dikembalikan secara manual
    oleh kasir.

    Mengembalikan objek Pesanan yang sudah diperbarui.
    Melempar KesalahanLayanan bila perpindahan status tidak diizinkan.
    """
    status_lama = pesanan.get_status_display()

    if not pesanan.boleh_ubah_ke(status_baru):
        # Pesan khusus untuk percobaan menulis status DIBAYAR secara
        # langsung, supaya penyebabnya jelas dan bukan sekadar dinyatakan
        # tidak diizinkan.
        if status_baru == StatusPesanan.DIBAYAR:
            raise KesalahanLayanan(
                f"Pesanan {pesanan.nomor_pesanan} belum dibayar. Status "
                f"Dibayar hanya dapat diberikan melalui proses pembayaran, "
                f"bukan melalui perubahan status manual."
            )
        raise KesalahanLayanan(
            f"Pesanan {pesanan.nomor_pesanan} berstatus {status_lama} "
            f"tidak dapat diubah menjadi {StatusPesanan(status_baru).label}."
        )

    berhasil = pesanan.ubah_status(status_baru)
    if not berhasil:
        raise KesalahanLayanan(
            f"Status pesanan {pesanan.nomor_pesanan} gagal diperbarui."
        )

    return pesanan


# ======================================================================
# Layanan Kasir: billing (AD05)
# ======================================================================

@transaction.atomic
def buat_billing(pesanan):
    """Menghitung dan menyimpan billing dari rincian pesanan (AD05).

    Memakai Billing.buat_dari_pesanan() yang bersifat idempoten, jadi
    membuka halaman billing berulang kali tidak menghasilkan tagihan
    ganda.

    Melempar KesalahanLayanan bila pesanan tidak memiliki rincian item
    atau bila pesanan sudah dibatalkan.
    """
    if pesanan.status == StatusPesanan.DIBATALKAN:
        raise KesalahanLayanan(
            f"Pesanan {pesanan.nomor_pesanan} sudah dibatalkan sehingga "
            f"tidak dapat ditagih."
        )

    if not pesanan.detail_list.exists():
        raise KesalahanLayanan(
            f"Pesanan {pesanan.nomor_pesanan} tidak memiliki rincian item."
        )

    return Billing.buat_dari_pesanan(pesanan)


# ======================================================================
# Layanan Kasir: pembayaran (AD06)
# ======================================================================

@transaction.atomic
def proses_pembayaran(
    billing,
    kasir,
    metode,
    jumlah_diterima=None,
    nomor_referensi="",
    transaksi=None,
):
    """Menyimpan pembayaran dan memindahkan pesanan ke status DIBAYAR.

    Alur bayar di awal (berlaku sejak 2026-09-23): pesanan dibuat,
    pelanggan memilih metode pembayaran, membayar, lalu pesanan masuk
    ke dapur. Karena itu perubahan status ke DIBAYAR terjadi di sini,
    bukan melalui layanan ubah status pesanan.

    Parameter
    ---------
    billing          : objek Billing yang dibayar
    kasir            : objek Pengguna yang melayani pembayaran
    metode           : MetodePembayaran.TUNAI atau QRIS
    jumlah_diterima  : Decimal, diisi untuk pembayaran tunai
    nomor_referensi  : str, diisi untuk QRIS
    transaksi        : objek TransaksiGateway, wajib untuk QRIS

    Mengembalikan objek Pembayaran yang tersimpan.

    Melempar KesalahanLayanan bila pesanan tidak layak dibayar, data
    pembayaran tidak valid, atau pesanan sudah pernah dibayar.

    Pemeriksaan khusus QRIS
    -----------------------
    Pembayaran QRIS tidak dapat disimpan sebelum gateway menyatakan
    pembayaran berhasil. Kasir hanya mengonfirmasi setelah melihat
    status gateway, jadi status itu diperiksa ulang di sini. Dengan
    begitu, konfirmasi tidak dapat menggantikan status gateway dan
    pesanan tidak akan tercatat lunas padahal pembayarannya belum
    benar-benar masuk.
    """
    pesanan = billing.pesanan

    # --- Pemeriksaan kelayakan bayar.
    if pesanan.sudah_dibayar() or Pembayaran.objects.filter(billing=billing).exists():
        raise KesalahanLayanan(
            f"Pesanan {pesanan.nomor_pesanan} sudah dibayar sebelumnya."
        )
    if pesanan.status == StatusPesanan.DIBATALKAN:
        raise KesalahanLayanan(
            f"Pesanan {pesanan.nomor_pesanan} sudah dibatalkan sehingga "
            f"tidak dapat dibayar."
        )

    # --- Penyusunan data pembayaran sesuai metode.
    if metode == MetodePembayaran.TUNAI:
        if jumlah_diterima is None:
            raise KesalahanLayanan("Jumlah uang diterima wajib diisi untuk tunai.")
        jumlah_diterima = Decimal(jumlah_diterima)
        nomor_referensi = ""
        transaksi = None
    elif metode == MetodePembayaran.QRIS:
        if transaksi is None:
            raise KesalahanLayanan(
                "Transaksi QRIS belum dibuat. Buat kode QR terlebih dahulu."
            )
        if transaksi.pesanan_id != pesanan.pk:
            raise KesalahanLayanan(
                "Transaksi QRIS yang dipilih bukan milik pesanan ini."
            )

        # Status gateway diperiksa ulang agar pembayaran tidak dapat
        # dicatat lunas sebelum gateway menyatakannya berhasil.
        gateway = gateway_pembayaran.get_gateway()
        status_gateway = gateway.periksa_status(transaksi)
        if status_gateway != gateway_pembayaran.STATUS_DIBAYAR:
            raise KesalahanLayanan(
                f"Pembayaran QRIS belum dinyatakan berhasil oleh gateway "
                f"(status: {transaksi.get_status_display()}). "
                f"Periksa kembali status pembayaran pelanggan."
            )

        # Jumlah yang dibayar harus sama dengan tagihan. Nilai ini
        # diambil dari transaksi, bukan dari isian kasir, supaya nominal
        # pembayaran tidak dapat diubah dari sisi halaman.
        if transaksi.jumlah != billing.total:
            raise KesalahanLayanan(
                f"Nominal transaksi QRIS (Rp{transaksi.jumlah:,.0f}) "
                f"tidak sama dengan total tagihan "
                f"(Rp{billing.total:,.0f})."
            )

        jumlah_diterima = billing.total
        nomor_referensi = transaksi.kode_bayar
    else:
        raise KesalahanLayanan("Metode pembayaran tidak dikenal.")

    pembayaran = Pembayaran(
        billing=billing,
        kasir=kasir,
        dikonfirmasi_kasir=kasir,
        metode=metode,
        jumlah_diterima=jumlah_diterima,
        nomor_referensi=nomor_referensi,
    )

    # --- Validasi dijalankan oleh model agar aturannya hanya ditulis
    # satu kali.
    if not pembayaran.validasi():
        raise KesalahanLayanan(pembayaran.pesan_kesalahan())

    pembayaran.hitung_kembalian()
    pembayaran.save()

    # --- Status pesanan dipindahkan ke DIBAYAR setelah pembayaran
    # tersimpan. Keduanya berada dalam satu transaksi, jadi bila salah
    # satu gagal, keduanya dibatalkan dan tidak ada pembayaran tanpa
    # perubahan status.
    #
    # Perpindahan ini ditulis langsung, bukan melalui ubah_status(),
    # karena ALUR_STATUS_VALID sengaja tidak memuat pasangan
    # BARU -> DIBAYAR supaya status DIBAYAR tidak dapat ditulis tanpa
    # ada pembayaran yang menyertainya.
    pesanan.status = StatusPesanan.DIBAYAR
    pesanan.save(update_fields=["status", "diperbarui_pada"])

    return pembayaran


# ======================================================================
# Layanan pembayaran QRIS (mockup gateway)
# ======================================================================

def transaksi_terakhir(pesanan):
    """Mengambil transaksi gateway yang paling relevan untuk sebuah pesanan.

    Urutan prioritasnya:

    1. Transaksi yang sudah berhasil. Bila ada, inilah yang dipakai,
       karena pembayaran pesanan itu memang sudah terjadi.
    2. Bila belum ada yang berhasil, transaksi terbaru. Ini mencakup
       transaksi yang masih menunggu pembayaran atau sudah kedaluwarsa.

    Urutan ini penting supaya transaksi lama yang sudah berhasil tidak
    tertutup oleh kode QR baru yang dibuat setelahnya. Tanpa aturan ini,
    kasir dapat mengonfirmasi kode QR yang belum dibayar padahal
    pembayaran pesanan tersebut sudah berhasil lebih dahulu.
    """
    daftar = TransaksiGateway.objects.filter(pesanan=pesanan)

    berhasil = (
        daftar.filter(status=gateway_pembayaran.STATUS_DIBAYAR)
        .order_by("-dibayar_pada")
        .first()
    )
    if berhasil is not None:
        return berhasil

    return daftar.order_by("-dibuat_pada").first()


def mulai_pembayaran_qris(pesanan):
    """Membuat transaksi QRIS baru untuk sebuah pesanan.

    Dipanggil ketika pelanggan memilih metode non tunai. Transaksi
    dibuat di sisi gateway (mockup, lihat core/gateway.py) lalu
    disimpan sebagai TransaksiGateway, sehingga statusnya dapat
    diperiksa kemudian.

    Transaksi yang sudah ada dipakai kembali bila memenuhi salah satu
    keadaan berikut:

      - masih menunggu pembayaran dan belum kedaluwarsa, sehingga tidak
        ada dua kode QR berbeda untuk satu tagihan yang sama;
      - sudah berhasil, karena membuat kode QR baru untuk tagihan yang
        sudah lunas tidak ada gunanya dan justru dapat menyesatkan.

    Kode QR baru hanya dibuat bila transaksi sebelumnya sudah
    kedaluwarsa atau gagal.
    """
    if pesanan.status == StatusPesanan.DIBATALKAN:
        raise KesalahanLayanan(
            f"Pesanan {pesanan.nomor_pesanan} sudah dibatalkan sehingga "
            f"tidak dapat dibayar."
        )
    if pesanan.sudah_dibayar():
        raise KesalahanLayanan(
            f"Pesanan {pesanan.nomor_pesanan} sudah dibayar sebelumnya."
        )

    billing = buat_billing(pesanan)

    transaksi_lama = transaksi_terakhir(pesanan)
    if transaksi_lama is not None:
        # Sudah berhasil, atau masih menunggu dan belum kedaluwarsa.
        if transaksi_lama.sudah_dibayar:
            return transaksi_lama, billing
        if (
            transaksi_lama.status == gateway_pembayaran.STATUS_MENUNGGU
            and not transaksi_lama.sudah_kedaluwarsa()
        ):
            return transaksi_lama, billing
        # Menunggu tetapi sudah kedaluwarsa, atau gagal. Ditandai agar
        # riwayatnya tetap terbaca dan tidak lagi dianggap menunggu.
        if transaksi_lama.status == gateway_pembayaran.STATUS_MENUNGGU:
            transaksi_lama.status = gateway_pembayaran.STATUS_KEDALUWARSA
            transaksi_lama.save(update_fields=["status"])

    gateway = gateway_pembayaran.get_gateway()
    data = gateway.buat_transaksi(pesanan, billing)

    transaksi = TransaksiGateway.objects.create(
        pesanan=pesanan,
        penyedia="MOCK",
        kode_bayar=data["kode_bayar"],
        qr_string=data["qr_string"],
        jumlah=data["jumlah"],
        status=gateway_pembayaran.STATUS_MENUNGGU,
        kedaluwarsa_pada=data["kedaluwarsa_pada"],
    )
    return transaksi, billing


def gambar_qr_data_uri(transaksi):
    """Membuat kode QR berbentuk data URI agar dapat dipasang di halaman.

    Bentuk data URI dipilih supaya kode QR tidak perlu ditulis sebagai
    berkas di server dan tidak memerlukan pengaturan penyajian berkas
    tambahan. Gambar dibuat sebagai SVG sehingga tidak memerlukan
    pustaka pengolah gambar.
    """
    import base64
    from io import BytesIO

    import qrcode
    import qrcode.image.svg

    gambar = qrcode.make(
        transaksi.qr_string, image_factory=qrcode.image.svg.SvgPathImage
    )
    penampung = BytesIO()
    gambar.save(penampung)
    isi = base64.b64encode(penampung.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{isi}"


def terima_notifikasi_gateway(kode_bayar, status, jumlah, tanda_tangan):
    """Memproses notifikasi pembayaran dari gateway.

    Dipanggil oleh alamat /notifikasi/gateway/ (lihat core/views.py).
    Notifikasi hanya dipercaya bila tanda tangannya sah dan nominalnya
    sama dengan transaksi yang tersimpan. Nominal dibandingkan dengan
    data di basis data, bukan dengan angka pada notifikasi, supaya
    notifikasi palsu bernilai kecil tidak dapat melunasi tagihan besar.

    Mengembalikan TransaksiGateway yang diperbarui.

    Melempar KesalahanLayanan bila tanda tangan tidak sah, transaksi
    tidak ditemukan, atau nominalnya tidak cocok.
    """
    from decimal import InvalidOperation

    try:
        jumlah_desimal = Decimal(str(jumlah))
    except (InvalidOperation, TypeError, ValueError):
        raise KesalahanLayanan("Nominal pada notifikasi tidak sah.")

    transaksi = TransaksiGateway.objects.filter(kode_bayar=kode_bayar).first()
    if transaksi is None:
        raise KesalahanLayanan(
            f"Transaksi dengan kode {kode_bayar} tidak ditemukan."
        )

    gateway = gateway_pembayaran.get_gateway()

    # Tanda tangan diperiksa dengan nominal milik transaksi yang
    # tersimpan, sehingga notifikasi yang mengubah nominal akan gagal.
    if not gateway.verifikasi_notifikasi(
        kode_bayar, status, transaksi.jumlah, tanda_tangan
    ):
        raise KesalahanLayanan(
            "Tanda tangan notifikasi tidak sah. Notifikasi ditolak dan "
            "tidak ada data yang diubah."
        )

    # Nominal pada notifikasi juga dibandingkan dengan nominal transaksi.
    if jumlah_desimal != transaksi.jumlah:
        raise KesalahanLayanan(
            f"Nominal notifikasi (Rp{jumlah_desimal:,.0f}) tidak sama dengan "
            f"nominal transaksi (Rp{transaksi.jumlah:,.0f})."
        )

    if status == gateway_pembayaran.STATUS_DIBAYAR and not transaksi.sudah_dibayar:
        transaksi.tandai_dibayar()
    elif status in (
        gateway_pembayaran.STATUS_GAGAL,
        gateway_pembayaran.STATUS_KEDALUWARSA,
    ):
        transaksi.status = status
        transaksi.save(update_fields=["status"])

    return transaksi


@transaction.atomic
def simulasi_bayar_qris(transaksi):
    """Menandai transaksi QRIS sebagai berhasil pada mockup.

    Fungsi ini hanya ada pada mockup. Fungsinya adalah menggantikan
    peran pelanggan yang membayar melalui aplikasi bank atau dompet
    digital: pada gateway sungguhan, status berubah sendiri di sisi
    penyedia dan aplikasi hanya menerima notifikasi.

    Hasil akhirnya sengaja dibuat sama dengan notifikasi sungguhan,
    yaitu transaksi bertanda tangan yang dibuat gateway lalu diperiksa
    ulang lewat terima_notifikasi_gateway(). Dengan cara ini jalur kode
    yang dipakai mockup dan jalur kode yang kelak dipakai gateway
    sungguhan adalah jalur yang sama.
    """
    gateway = gateway_pembayaran.get_gateway()
    if not gateway.simulasi:
        raise KesalahanLayanan(
            "Aksi simulasi hanya tersedia pada gateway mockup."
        )

    if transaksi.sudah_dibayar:
        return transaksi

    if transaksi.sudah_kedaluwarsa():
        transaksi.status = gateway_pembayaran.STATUS_KEDALUWARSA
        transaksi.save(update_fields=["status"])
        raise KesalahanLayanan(
            "Masa berlaku kode QR sudah habis. Buat kode QR baru."
        )

    tanda_tangan = gateway.tanda_tangan(
        transaksi.kode_bayar, gateway_pembayaran.STATUS_DIBAYAR, transaksi.jumlah
    )
    return terima_notifikasi_gateway(
        kode_bayar=transaksi.kode_bayar,
        status=gateway_pembayaran.STATUS_DIBAYAR,
        jumlah=transaksi.jumlah,
        tanda_tangan=tanda_tangan,
    )


def periksa_status_qris(transaksi):
    """Memeriksa status transaksi langsung ke gateway.

    Dipakai kasir untuk memastikan status terbaru sebelum menekan
    tombol konfirmasi pembayaran. Pada mockup, status tidak berubah
    sendiri, sehingga fungsi ini juga mencatat kedaluwarsa agar tampilan
    status tidak menyesatkan.
    """
    gateway = gateway_pembayaran.get_gateway()
    status = gateway.periksa_status(transaksi)

    if (
        status == gateway_pembayaran.STATUS_MENUNGGU
        and transaksi.sudah_kedaluwarsa()
    ):
        transaksi.status = gateway_pembayaran.STATUS_KEDALUWARSA
        transaksi.save(update_fields=["status"])
        return transaksi

    return transaksi


# ======================================================================
# Layanan Administrator: stok produk (AD07)
# ======================================================================

@transaction.atomic
def atur_stok_produk(produk, jumlah_baru):
    """Menetapkan nilai stok produk dan memperbarui status ketersediaannya.

    Sesuai AD07: status Tersedia atau Habis ditentukan otomatis dari
    nilai stok, bukan diisi manual.

    Mengembalikan objek Produk yang sudah diperbarui.
    Melempar KesalahanLayanan bila jumlah tidak sah.
    """
    if jumlah_baru is None:
        raise KesalahanLayanan("Jumlah stok wajib diisi.")
    if jumlah_baru < 0:
        raise KesalahanLayanan("Jumlah stok tidak boleh negatif.")

    produk.atur_stok(jumlah_baru)
    return produk


def filter_stok(kategori=None, status=None, cari=None):
    """Mengambil daftar produk dengan penyaringan untuk halaman kelola stok.

    Sesuai AD07 yang menyediakan penyaringan berdasarkan kategori atau
    status ketersediaan. Parameter yang kosong berarti tidak disaring.

    Mengembalikan QuerySet Produk yang sudah diurutkan.
    """
    produk = Produk.objects.select_related("kategori").order_by(
        "kategori__nama", "nama"
    )
    if kategori:
        produk = produk.filter(kategori_id=kategori)
    if status:
        produk = produk.filter(status_stok=status)
    if cari:
        produk = produk.filter(nama__icontains=cari)
    return produk


# ======================================================================
# Layanan Administrator: laporan penjualan (AD08)
# ======================================================================

def hitung_periode_laporan(periode, tanggal_acuan):
    """Menghitung tanggal mulai dan tanggal selesai untuk suatu periode.

    Mingguan: Senin sampai Minggu pada pekan yang memuat tanggal acuan.
    Bulanan : tanggal 1 sampai hari terakhir pada bulan yang sama.

    Mengembalikan pasangan (tanggal_mulai, tanggal_selesai).
    """
    if periode == PeriodeLaporan.MINGGUAN:
        mulai = tanggal_acuan - timedelta(days=tanggal_acuan.weekday())
        selesai = mulai + timedelta(days=6)
        return mulai, selesai

    if periode == PeriodeLaporan.BULANAN:
        mulai = tanggal_acuan.replace(day=1)
        # Hari pertama bulan berikutnya dikurangi satu hari menghasilkan
        # hari terakhir bulan ini, tanpa perlu tabel jumlah hari.
        if mulai.month == 12:
            bulan_depan = mulai.replace(year=mulai.year + 1, month=1)
        else:
            bulan_depan = mulai.replace(month=mulai.month + 1)
        selesai = bulan_depan - timedelta(days=1)
        return mulai, selesai

    raise KesalahanLayanan("Jenis laporan tidak dikenali.")


def buat_laporan(periode, tanggal_mulai, tanggal_selesai, simpan=True):
    """Menghitung laporan penjualan pada rentang tanggal tertentu (AD08).

    Hanya pesanan berstatus DIBAYAR yang dihitung, sesuai ketentuan
    studi kasus.

    Bila simpan bernilai True, hasilnya juga dicatat pada tabel
    laporan_penjualan sebagai riwayat pembuatan laporan.

    Mengembalikan objek LaporanPenjualan. Bila tidak ada data penjualan,
    total_penjualan bernilai 0 dan pemanggil dapat menampilkan pesan
    "tidak ada data penjualan".
    """
    if tanggal_selesai < tanggal_mulai:
        raise KesalahanLayanan(
            "Tanggal selesai tidak boleh lebih awal dari tanggal mulai."
        )

    if simpan:
        return LaporanPenjualan.generate(periode, tanggal_mulai, tanggal_selesai)

    # Tanpa penyimpanan: hitung nilai saja untuk ditampilkan.
    return LaporanPenjualan(
        periode=periode,
        tanggal_mulai=tanggal_mulai,
        tanggal_selesai=tanggal_selesai,
        total_penjualan=LaporanPenjualan.hitung_total(
            tanggal_mulai, tanggal_selesai
        ),
    )


def rincian_laporan(tanggal_mulai, tanggal_selesai):
    """Mengambil daftar pesanan yang sudah dibayar pada rentang tanggal.

    Dipakai halaman laporan agar Administrator dapat melihat pesanan
    mana saja yang membentuk total penjualan. Pesanan yang dihitung
    adalah yang berstatus DIBAYAR, DIPROSES, atau SELESAI, sesuai
    LaporanPenjualan.STATUS_TERHITUNG.
    """
    return (
        Pesanan.objects.filter(
            status__in=LaporanPenjualan.STATUS_TERHITUNG,
            dibuat_pada__date__gte=tanggal_mulai,
            dibuat_pada__date__lte=tanggal_selesai,
        )
        .select_related("pelanggan", "billing")
        .order_by("dibuat_pada")
    )


# ======================================================================
# Layanan Administrator: produk, kategori, dan pengguna
# ======================================================================

def kategori_dipakai(kategori):
    """True bila kategori masih dipakai oleh produk (AD10).

    Kategori yang masih dipakai tidak boleh dihapus supaya produk tidak
    kehilangan kategorinya.
    """
    return kategori.produk_list.exists()


def produk_pernah_dipesan(produk):
    """True bila produk pernah masuk ke sebuah pesanan (AD09).

    Produk semacam ini tidak boleh dihapus agar riwayat pesanan dan
    laporan tetap utuh. Sarannya: nonaktifkan saja produk tersebut.
    """
    return produk.detail_pesanan_list.exists()


def pengguna_boleh_dihapus(pengguna, pengguna_saat_ini):
    """True bila data pengguna boleh dihapus (AD11).

    Pengguna tidak boleh dihapus pada dua kondisi:
    1. Akun tersebut sedang dipakai login (akun sendiri).
    2. Pengguna pernah menangani pembayaran, karena pembayaran
       menyimpan rujukan ke kasir dengan aturan PROTECT.
    """
    if pengguna_saat_ini is not None and pengguna.pk == pengguna_saat_ini.pk:
        return False
    return not pengguna.pembayaran_list.exists()


def alasan_pengguna_tidak_boleh_dihapus(pengguna, pengguna_saat_ini):
    """Pesan penjelasan mengapa pengguna tidak dapat dihapus (AD11)."""
    if pengguna_saat_ini is not None and pengguna.pk == pengguna_saat_ini.pk:
        return "Akun yang sedang Anda pakai tidak dapat dihapus."
    if pengguna.pembayaran_list.exists():
        return (
            f"Pengguna {pengguna.username} pernah menangani pembayaran "
            f"sehingga datanya tidak dapat dihapus. Nonaktifkan saja akunnya."
        )
    return "Pengguna tersebut tidak dapat dihapus."


# ======================================================================
# Layanan pendukung tampilan
# ======================================================================

def produk_menu(kategori_id=None, cari=None):
    """Daftar produk yang dijual pada halaman menu Pelanggan (AD02).

    Hanya produk aktif yang ditampilkan, dengan penyaringan kategori
    opsional sesuai Use Case "Memfilter Menu berdasarkan Kategori".
    """
    produk = (
        Produk.objects.filter(aktif=True)
        .select_related("kategori")
        .order_by("kategori__nama", "nama")
    )
    if kategori_id:
        produk = produk.filter(kategori_id=kategori_id)
    if cari:
        produk = produk.filter(nama__icontains=cari)
    return produk


def kategori_urut():
    """Daftar kategori untuk pilihan penyaringan, diurutkan menurut nama."""
    return KategoriProduk.objects.order_by("nama")


def tipe_kategori_terpakai():
    """Daftar tipe kategori yang sudah dipakai, untuk saran pengisian.

    Dipakai pada formulir tambah dan ubah kategori supaya penulisan
    tipe seragam. Sifatnya hanya saran: Administrator tetap dapat
    mengetik tipe yang sama sekali baru tanpa harus membuat kategori
    lain lebih dahulu.
    """
    return list(
        KategoriProduk.objects.order_by("tipe")
        .values_list("tipe", flat=True)
        .distinct()
    )


def statistik_ringkas():
    """Angka ringkas untuk halaman beranda Kasir dan Administrator.

    Mengembalikan kamus berisi jumlah pesanan per status dan total
    penjualan hari ini. Dipakai sebagai gambaran cepat saat demo.
    """
    hari_ini = timezone.localdate()
    pesanan_hari_ini = Pesanan.objects.filter(dibuat_pada__date=hari_ini)

    return {
        "jumlah_baru": pesanan_hari_ini.filter(status=StatusPesanan.BARU).count(),
        "jumlah_diproses": pesanan_hari_ini.filter(
            status=StatusPesanan.DIPROSES
        ).count(),
        "jumlah_selesai": pesanan_hari_ini.filter(
            status=StatusPesanan.SELESAI
        ).count(),
        "jumlah_dibayar": pesanan_hari_ini.filter(
            status=StatusPesanan.DIBAYAR
        ).count(),
        "jumlah_dibatalkan": pesanan_hari_ini.filter(
            status=StatusPesanan.DIBATALKAN
        ).count(),
        "penjualan_hari_ini": LaporanPenjualan.hitung_total(hari_ini, hari_ini),
    }
