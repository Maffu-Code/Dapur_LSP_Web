"""
View aplikasi Dapur Ina Aina
============================

Seluruh tampilan memakai class based view (CBV) agar struktur kode
seragam dan mudah dibaca. Tugas setiap view dibatasi pada tiga hal:
menerima permintaan, memvalidasi formulir, dan memanggil layanan pada
core/services.py. Aturan transaksi tidak ditulis ulang di sini.

Pembagian kelas
---------------
Pelanggan (tanpa login)
    BerandaPelangganView, FormPesananView, KonfirmasiPesananView,
    CekStatusView

Masuk dan keluar
    MasukView, KeluarView

Kasir (perlu login)
    KasirBerandaView, DaftarPesananView, DetailPesananView,
    UbahStatusPesananView, BillingView, CetakBillingView,
    PembayaranView, BuktiPembayaranView

Administrator (perlu login, peran Administrator)
    KelolaProdukView, TambahProdukView, UbahProdukView, HapusProdukView,
    KelolaKategoriView, TambahKategoriView, UbahKategoriView,
    HapusKategoriView, KelolaStokView, AturStokView, LaporanView,
    KelolaPenggunaView, TambahPenggunaView, UbahPenggunaView,
    HapusPenggunaView

Penamaan kelas memakai bahasa Indonesia agar konsisten dengan penamaan
model, formulir, dan template.
"""

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from core import services
from core import gateway as gateway_pembayaran
from core import tagihan_pdf
from core.autentikasi import (
    WajibAdministratorMixin,
    WajibLoginMixin,
    catat_keluar,
    catat_masuk,
)
from core.forms import (
    FormCekStatus,
    FormKategori,
    FormLaporan,
    FormMasuk,
    FormPembayaran,
    FormPengguna,
    FormPesanan,
    FormProduk,
    FormStok,
    FormUbahStatus,
)
from core.models import (
    KategoriProduk,
    MetodePembayaran,
    Pembayaran,
    Pengguna,
    PeriodeLaporan,
    Pesanan,
    Produk,
    Role,
    StatusPesanan,
    StatusStok,
    TransaksiGateway,
)


# ======================================================================
# Halaman Pelanggan (tanpa login)
# ======================================================================

class BerandaPelangganView(View):
    """Halaman menu: daftar produk per kategori beserta penyaring (AD02).

    Menampilkan seluruh produk aktif, dapat disaring berdasarkan
    kategori dan pencarian nama produk.
    """

    template_name = "pelanggan/beranda.html"

    def get(self, request):
        kategori_id = request.GET.get("kategori") or ""
        cari = request.GET.get("cari") or ""

        produk_list = services.produk_menu(
            kategori_id=kategori_id or None, cari=cari or None
        )

        konteks = {
            "produk_list": produk_list,
            "kategori_list": services.kategori_urut(),
            "kategori_terpilih": kategori_id,
            "cari": cari,
            "judul_halaman": "Menu Dapur Ina Aina",
        }
        return render(request, self.template_name, konteks)


class FormPesananView(View):
    """Halaman pengisian pesanan (AD02).

    Menampilkan daftar produk beserta kolom jumlah, ditambah nama
    pemesan dan nomor meja. Bila ada kesalahan, formulir dikembalikan
    beserta pesan kesalahan tanpa menghapus isian pengguna.
    """

    template_name = "pelanggan/form_pesanan.html"

    def get(self, request):
        produk_list = services.produk_menu()
        form = FormPesanan(produk_list=produk_list)
        return render(request, self.template_name, self._konteks(form, produk_list))

    def post(self, request):
        produk_list = services.produk_menu()
        form = FormPesanan(request.POST, produk_list=produk_list)

        if not form.is_valid():
            # Kesalahan ditampilkan pada halaman yang sama supaya
            # pengguna dapat langsung memperbaiki isiannya.
            messages.error(
                request, "Pesanan belum dapat dikirim. Periksa isian berikut."
            )
            return render(
                request, self.template_name, self._konteks(form, produk_list)
            )

        try:
            pesanan = services.buat_pesanan(
                nama_pemesan=form.cleaned_data["nama"],
                nomor_meja=form.cleaned_data["nomor_meja"],
                item_list=form.item_dipilih(),
                metode_pembayaran=form.cleaned_data["metode_pembayaran"],
            )
        except services.KesalahanLayanan as galat:
            # Kesalahan aturan bisnis, misalnya stok tidak mencukupi.
            messages.error(request, str(galat))
            return render(
                request, self.template_name, self._konteks(form, produk_list)
            )

        # Pesanan wajib dibayar lebih dahulu, jadi pelanggan langsung
        # diarahkan ke halaman pembayaran, bukan ke halaman konfirmasi.
        # Halaman konfirmasi tetap ada dan dapat dibuka setelah pembayaran.
        return redirect("core:pembayaran_pelanggan", nomor=pesanan.nomor_pesanan)

    def _konteks(self, form, produk_list):
        return {
            "form": form,
            "produk_list": produk_list,
            "judul_halaman": "Pesan Menu",
        }


class KonfirmasiPesananView(View):
    """Halaman konfirmasi berisi nomor pesanan yang baru dibuat (AD02)."""

    template_name = "pelanggan/konfirmasi_pesanan.html"

    def get(self, request, nomor):
        pesanan = get_object_or_404(
            Pesanan.objects.select_related("pelanggan"), nomor_pesanan=nomor
        )
        konteks = {
            "pesanan": pesanan,
            "judul_halaman": "Pesanan Diterima",
        }
        return render(request, self.template_name, konteks)


# ======================================================================
# Pembayaran oleh Pelanggan (tanpa login)
# ======================================================================

class PembayaranPelangganView(View):
    """Halaman pembayaran yang dibuka pelanggan tepat setelah memesan.

    Pesanan wajib dibayar sebelum diproses, jadi halaman ini adalah
    langkah pertama setelah pemesanan dan merupakan halaman yang
    menggantikan halaman konfirmasi sebagai tujuan setelah memesan.

    Dua alur pembayaran ditangani di sini:

    Tunai
        Pelanggan diarahkan membayar di kasir. Halaman menampilkan
        tagihan dan nomor meja, sedangkan pencatatan pembayaran
        dilakukan kasir melalui halaman pembayaran kasir.

    QRIS
        Halaman menampilkan kode QR untuk dipindai. Pelanggan memindai,
        membayar, lalu statusnya berubah menjadi berhasil. Kasir
        mengonfirmasi pembayaran setelah melihat status dari gateway.
    """

    template_name = "pelanggan/pembayaran.html"

    def get(self, request, nomor):
        pesanan = get_object_or_404(
            Pesanan.objects.select_related("pelanggan").prefetch_related(
                "detail_list__produk"
            ),
            nomor_pesanan=nomor,
        )

        # Pesanan yang sudah dibayar tidak lagi menampilkan pilihan
        # pembayaran, tetapi ringkasan dan tautan untuk mencetak tagihan.
        if pesanan.sudah_dibayar():
            return render(
                request,
                "pelanggan/pembayaran_selesai.html",
                {
                    "pesanan": pesanan,
                    "pembayaran": self._pembayaran(pesanan),
                    "judul_halaman": "Pembayaran Selesai",
                },
            )

        if pesanan.status == StatusPesanan.DIBATALKAN:
            messages.error(
                request,
                f"Pesanan {pesanan.nomor_pesanan} sudah dibatalkan "
                f"sehingga tidak dapat dibayar.",
            )
            return redirect("core:beranda")

        billing = services.buat_billing(pesanan)
        konteks = {
            "pesanan": pesanan,
            "billing": billing,
            "judul_halaman": f"Pembayaran {pesanan.nomor_pesanan}",
        }

        if pesanan.metode_dipilih == MetodePembayaran.QRIS:
            transaksi, _ = services.mulai_pembayaran_qris(pesanan)
            konteks.update(
                {
                    "transaksi": transaksi,
                    "qr_data_uri": services.gambar_qr_data_uri(transaksi),
                    "gateway_simulasi": gateway_pembayaran.get_gateway().simulasi,
                }
            )

        return render(request, self.template_name, konteks)

    @staticmethod
    def _pembayaran(pesanan):
        """Mengambil data pembayaran sebuah pesanan bila sudah ada."""
        return Pembayaran.objects.filter(billing__pesanan=pesanan).first()


class SimulasiBayarQrisView(View):
    """Menandai pembayaran QRIS berhasil pada gateway mockup.

    Halaman ini hanya ada karena gateway yang dipakai masih berupa
    mockup. Tombol ini menggantikan peran aplikasi bank atau dompet
    digital milik pelanggan: pada gateway sungguhan, pelanggan membayar
    melalui aplikasinya dan status berubah di sisi penyedia.

    Setelah status berubah, pelanggan diarahkan kembali ke halaman
    pembayaran. Kasir tetap harus melihat status tersebut dan
    mengonfirmasi pembayaran sebelum pesanan dianggap lunas dan masuk
    ke dapur.
    """

    def post(self, request, nomor):
        pesanan = get_object_or_404(Pesanan, nomor_pesanan=nomor)

        transaksi = services.transaksi_terakhir(pesanan)
        if transaksi is None:
            messages.error(
                request, "Transaksi QRIS belum dibuat. Muat ulang halaman."
            )
            return redirect("core:pembayaran_pelanggan", nomor=nomor)

        try:
            services.simulasi_bayar_qris(transaksi)
        except services.KesalahanLayanan as galat:
            messages.error(request, str(galat))
        else:
            messages.success(
                request,
                "Pembayaran QRIS berhasil disimulasikan. "
                "Tunjukkan halaman ini kepada kasir untuk dikonfirmasi.",
            )

        return redirect("core:pembayaran_pelanggan", nomor=nomor)


class StatusPembayaranPelangganView(View):
    """Menampilkan status pembayaran non tunai milik sebuah pesanan.

    Dipakai halaman pembayaran QRIS untuk memeriksa apakah status sudah
    berubah menjadi berhasil. Pemeriksaan dilakukan dengan memuat ulang
    halaman, sehingga tidak memerlukan jaringan permanen dari peramban
    ke server dan tetap dapat didemonstrasikan tanpa koneksi internet.
    """

    def get(self, request, nomor):
        pesanan = get_object_or_404(Pesanan, nomor_pesanan=nomor)
        transaksi = services.transaksi_terakhir(pesanan)

        return JsonResponse(
            {
                "nomor_pesanan": pesanan.nomor_pesanan,
                "status_pesanan": pesanan.status,
                "sudah_dibayar": pesanan.sudah_dibayar(),
                "kode_bayar": transaksi.kode_bayar if transaksi else "",
                "status_transaksi": transaksi.status if transaksi else "",
            }
        )


class CekStatusView(View):
    """Halaman pemeriksaan status pesanan berdasarkan nomor pesanan (AD03).

    Halaman ini menangani dua keadaan: sebelum pencarian (formulir
    kosong) dan sesudah pencarian (formulir terisi beserta hasilnya).
    """

    template_name = "pelanggan/cek_status.html"

    def get(self, request):
        form = FormCekStatus()
        return render(
            request,
            self.template_name,
            {"form": form, "judul_halaman": "Cek Status Pesanan"},
        )

    def post(self, request):
        form = FormCekStatus(request.POST)
        pesanan = None

        if not form.is_valid():
            messages.error(request, "Nomor pesanan belum diisi dengan benar.")
            return render(
                request,
                self.template_name,
                {"form": form, "judul_halaman": "Cek Status Pesanan"},
            )

        nomor = form.cleaned_data["nomor_pesanan"].strip()
        pesanan = (
            Pesanan.objects.select_related("pelanggan", "billing")
            .prefetch_related("detail_list__produk")
            .filter(nomor_pesanan__iexact=nomor)
            .first()
        )

        if pesanan is None:
            messages.error(
                request,
                f"Pesanan dengan nomor {nomor} tidak ditemukan. "
                f"Periksa kembali nomor pesanannya.",
            )

        konteks = {
            "form": form,
            "pesanan": pesanan,
            "judul_halaman": "Cek Status Pesanan",
        }
        return render(request, self.template_name, konteks)


# ======================================================================
# Masuk dan keluar (Kasir dan Administrator)
# ======================================================================

class MasukView(View):
    """Halaman login untuk Kasir dan Administrator (AD01).

    Alur: periksa kelengkapan input, cari pengguna, cocokkan password,
    lalu buat sesi. Pesan kesalahan tidak menyebutkan bagian mana yang
    salah (username atau password), sesuai praktik keamanan yang lazim.
    """

    template_name = "auth/masuk.html"

    def get(self, request):
        # Pengguna yang sudah login tidak perlu melihat halaman ini.
        if request.pengguna is not None:
            return redirect(self._tujuan_setelah_masuk(request.pengguna))
        return render(
            request,
            self.template_name,
            {"form": FormMasuk(), "judul_halaman": "Masuk"},
        )

    def post(self, request):
        form = FormMasuk(request.POST)

        if not form.is_valid():
            messages.error(request, "Username dan password wajib diisi.")
            return render(
                request,
                self.template_name,
                {"form": form, "judul_halaman": "Masuk"},
            )

        username = form.cleaned_data["username"].strip()
        password = form.cleaned_data["password"]

        pengguna = Pengguna.objects.filter(username__iexact=username).first()

        if pengguna is None or not pengguna.verifikasi_password(password):
            messages.error(request, "Username atau password salah.")
            return render(
                request,
                self.template_name,
                {"form": form, "judul_halaman": "Masuk"},
            )

        if not pengguna.aktif:
            messages.error(
                request, "Akun ini sedang tidak aktif. Hubungi Administrator."
            )
            return render(
                request,
                self.template_name,
                {"form": form, "judul_halaman": "Masuk"},
            )

        catat_masuk(request, pengguna)
        messages.success(request, f"Selamat datang, {pengguna.nama}.")
        return redirect(self._tujuan_setelah_masuk(pengguna))

    @staticmethod
    def _tujuan_setelah_masuk(pengguna):
        """Menentukan halaman awal sesuai peran pengguna (AD01)."""
        if pengguna.adalah_administrator:
            return reverse("core:kelola_produk")
        return reverse("core:kasir_pesanan")


class KeluarView(View):
    """Halaman keluar (logout) untuk Kasir dan Administrator."""

    def get(self, request):
        return self._keluar(request)

    def post(self, request):
        return self._keluar(request)

    def _keluar(self, request):
        if request.pengguna is not None:
            catat_keluar(request)
            messages.success(request, "Anda telah keluar dari aplikasi.")
        return redirect("core:beranda")


# ======================================================================
# Halaman Kasir (perlu login)
# ======================================================================

class KasirBerandaView(WajibLoginMixin, View):
    """Halaman awal Kasir berisi ringkasan pesanan hari ini."""

    template_name = "kasir/beranda.html"

    def get(self, request):
        konteks = {
            "statistik": services.statistik_ringkas(),
            "hari_ini": timezone.localdate(),
            "judul_halaman": "Beranda Kasir",
        }
        return render(request, self.template_name, konteks)


class DaftarPesananView(WajibLoginMixin, View):
    """Daftar pesanan beserta statusnya, dapat disaring (AD04).

    Penyaringan berguna saat demo: menampilkan hanya pesanan yang perlu
    ditindaklanjuti, misalnya yang berstatus BARU.
    """

    template_name = "kasir/daftar_pesanan.html"

    def get(self, request):
        status_pilih = request.GET.get("status") or ""
        cari = request.GET.get("cari") or ""

        pesanan_list = Pesanan.objects.select_related(
            "pelanggan", "billing"
        ).order_by("-dibuat_pada")
        if status_pilih:
            pesanan_list = pesanan_list.filter(status=status_pilih)
        if cari:
            pesanan_list = pesanan_list.filter(
                Q(nomor_pesanan__icontains=cari)
                | Q(pelanggan__nama__icontains=cari)
                | Q(pelanggan__nomor_meja__icontains=cari)
            )

        konteks = {
            "pesanan_list": pesanan_list,
            "status_list": StatusPesanan.choices,
            "status_terpilih": status_pilih,
            "cari": cari,
            "judul_halaman": "Daftar Pesanan",
        }
        return render(request, self.template_name, konteks)


class DetailPesananView(WajibLoginMixin, View):
    """Rincian satu pesanan beserta rincian itemnya (AD04 dan AD05)."""

    template_name = "kasir/detail_pesanan.html"

    def get(self, request, pk):
        pesanan = get_object_or_404(
            Pesanan.objects.select_related("pelanggan").prefetch_related(
                "detail_list__produk"
            ),
            pk=pk,
        )
        form_status = FormUbahStatus(pesanan=pesanan)
        konteks = {
            "pesanan": pesanan,
            "form_status": form_status,
            "judul_halaman": f"Pesanan {pesanan.nomor_pesanan}",
        }
        return render(request, self.template_name, konteks)


class UbahStatusPesananView(WajibLoginMixin, View):
    """Memproses perubahan status pesanan (AD04).

    Validasi alur status dilakukan di layanan, bukan di sini, supaya
    aturan yang sama berlaku walau dipanggil dari halaman lain.
    """

    def post(self, request, pk):
        pesanan = get_object_or_404(Pesanan, pk=pk)
        form = FormUbahStatus(request.POST, pesanan=pesanan)

        if not form.is_valid():
            messages.error(
                request,
                "Status baru belum dipilih dengan benar. "
                "Pilih salah satu status yang tersedia.",
            )
            return redirect("core:kasir_detail_pesanan", pk=pk)

        try:
            services.ubah_status_pesanan(pesanan, form.cleaned_data["status_baru"])
        except services.KesalahanLayanan as galat:
            messages.error(request, str(galat))
            return redirect("core:kasir_detail_pesanan", pk=pk)

        messages.success(
            request,
            f"Status pesanan {pesanan.nomor_pesanan} berhasil diperbarui "
            f"menjadi {pesanan.get_status_display()}.",
        )
        return redirect("core:kasir_detail_pesanan", pk=pk)


class BillingView(WajibLoginMixin, View):
    """Menampilkan billing pesanan dan menyediakan tombol cetak (AD05)."""

    template_name = "kasir/billing.html"

    def get(self, request, pk):
        pesanan = get_object_or_404(
            Pesanan.objects.select_related("pelanggan").prefetch_related(
                "detail_list__produk"
            ),
            pk=pk,
        )

        try:
            billing = services.buat_billing(pesanan)
        except services.KesalahanLayanan as galat:
            messages.error(request, str(galat))
            return redirect("core:kasir_pesanan")

        konteks = {
            "pesanan": pesanan,
            "billing": billing,
            "judul_halaman": f"Billing {pesanan.nomor_pesanan}",
        }
        return render(request, self.template_name, konteks)


class CetakBillingView(WajibLoginMixin, View):
    """Mencetak billing dan menampilkan versi cetaknya.

    Sejak alur bayar di awal, tagihan hanya boleh dicetak setelah
    pembayaran tuntas. Pesanan yang belum dibayar diarahkan kembali
    dengan pesan kesalahan, bukan ditampilkan halamannya.

    Halaman ini tetap dipertahankan untuk pencetakan melalui peramban.
    Untuk berkas yang dapat disimpan atau dikirim, tersedia
    UnduhTagihanPdfView yang menghasilkan berkas PDF.
    """

    template_name = "kasir/cetak_billing.html"

    def get(self, request, pk):
        pesanan = get_object_or_404(
            Pesanan.objects.select_related("pelanggan").prefetch_related(
                "detail_list__produk"
            ),
            pk=pk,
        )

        if not pesanan.boleh_dicetak():
            messages.error(
                request,
                f"Tagihan {pesanan.nomor_pesanan} belum dapat dicetak. "
                f"Tagihan hanya dapat dicetak setelah pembayaran selesai.",
            )
            return redirect("core:kasir_pesanan")

        try:
            billing = services.buat_billing(pesanan)
        except services.KesalahanLayanan as galat:
            messages.error(request, str(galat))
            return redirect("core:kasir_pesanan")

        billing.cetak()

        konteks = {
            "pesanan": pesanan,
            "billing": billing,
            "pembayaran": Pembayaran.objects.filter(
                billing__pesanan=pesanan
            ).first(),
            "judul_halaman": f"Cetak Billing {pesanan.nomor_pesanan}",
        }
        return render(request, self.template_name, konteks)


class UnduhTagihanPdfView(WajibLoginMixin, View):
    """Mengunduh tagihan pesanan sebagai berkas PDF.

    Berkas dibuat di sisi server (lihat core/tagihan_pdf.py), sehingga
    hasilnya berupa PDF sungguhan dan tidak bergantung pada peramban
    yang dipakai. Tagihan hanya dapat diunduh setelah dibayar, dan
    aturan itu diperiksa ulang di sini supaya tetap berlaku walau
    alamat unduhan dibuka langsung.
    """

    def get(self, request, pk):
        pesanan = get_object_or_404(
            Pesanan.objects.select_related("pelanggan").prefetch_related(
                "detail_list__produk"
            ),
            pk=pk,
        )

        try:
            billing = services.buat_billing(pesanan)
            pembayaran = Pembayaran.objects.filter(
                billing__pesanan=pesanan
            ).first()
            isi_pdf = tagihan_pdf.buat_pdf_tagihan(
                pesanan, billing, pembayaran
            )
        except services.KesalahanLayanan as galat:
            messages.error(request, str(galat))
            return redirect("core:kasir_pesanan")

        # Billing ditandai sudah dicetak karena berkasnya benar benar
        # dihasilkan, sehingga waktu cetak pada riwayat menjadi akurat.
        billing.cetak()

        tanggapan = HttpResponse(isi_pdf, content_type="application/pdf")
        tanggapan["Content-Disposition"] = (
            f'attachment; filename="{tagihan_pdf.nama_berkas(pesanan)}"'
        )
        return tanggapan


class NotifikasiGatewayView(View):
    """Menerima notifikasi pembayaran dari payment gateway.

    Alamat ini dipanggil oleh gateway, bukan oleh peramban, sehingga
    tidak dapat menyertakan token CSRF. Karena itu pemeriksaan CSRF
    dilewati untuk view ini, dan sebagai gantinya setiap notifikasi
    wajib menyertakan tanda tangan yang sah (diperiksa oleh
    services.terima_notifikasi_gateway).

    Notifikasi yang tidak sah tidak mengubah data apa pun dan dijawab
    dengan kode 403. Notifikasi yang sah dijawab dengan kode 200 supaya
    gateway tidak mengirim ulang.

    Bentuk data yang diterima mengikuti kebiasaan penyedia gateway:
    kode_bayar, status, jumlah, dan tanda_tangan. Pada penyedia
    sungguhan, pemetaan nama kolomnya cukup disesuaikan di view ini
    tanpa mengubah layanan.
    """

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        kode_bayar = request.POST.get("kode_bayar", "")
        status = request.POST.get("status", "")
        jumlah = request.POST.get("jumlah", "")
        tanda_tangan = request.POST.get("tanda_tangan", "")

        if not kode_bayar or not status or not jumlah or not tanda_tangan:
            return JsonResponse(
                {
                    "diterima": False,
                    "pesan": "Notifikasi tidak lengkap. "
                    "kode_bayar, status, jumlah, dan tanda_tangan wajib diisi.",
                },
                status=400,
            )

        try:
            transaksi = services.terima_notifikasi_gateway(
                kode_bayar=kode_bayar,
                status=status,
                jumlah=jumlah,
                tanda_tangan=tanda_tangan,
            )
        except services.KesalahanLayanan as galat:
            # Notifikasi tidak sah: data tidak diubah dan permintaan
            # ditolak, sehingga tidak ada pesanan yang tercatat lunas
            # karena notifikasi palsu.
            return JsonResponse(
                {"diterima": False, "pesan": str(galat)}, status=403
            )

        return JsonResponse(
            {
                "diterima": True,
                "kode_bayar": transaksi.kode_bayar,
                "status": transaksi.status,
            }
        )


class PeriksaStatusQrisView(WajibLoginMixin, View):
    """Memeriksa status pembayaran QRIS langsung ke gateway.

    Dipakai kasir dari halaman pembayaran untuk memastikan status
    terbaru sebelum menekan tombol konfirmasi. Pada mockup, tombol ini
    juga yang memperbarui status kedaluwarsa.
    """

    def post(self, request, pk):
        transaksi = get_object_or_404(TransaksiGateway, pk=pk)
        transaksi = services.periksa_status_qris(transaksi)

        messages.info(
            request,
            f"Status pembayaran {transaksi.kode_bayar}: "
            f"{transaksi.get_status_display()}.",
        )
        return redirect("core:kasir_pembayaran", pk=transaksi.pesanan.pk)


class KonfirmasiPembayaranQrisView(WajibLoginMixin, View):
    """Konfirmasi kasir atas pembayaran QRIS yang sudah berhasil.

    Kasir menekan tombol ini setelah melihat status gateway menyatakan
    pembayaran berhasil. Status itu diperiksa ulang oleh
    services.proses_pembayaran, sehingga tombol ini tidak dapat dipakai
    untuk melunasi pesanan yang pembayarannya belum masuk.
    """

    def post(self, request, pk):
        pesanan = get_object_or_404(Pesanan, pk=pk)

        transaksi = services.transaksi_terakhir(pesanan)
        if transaksi is None:
            messages.error(
                request,
                "Transaksi QRIS belum dibuat untuk pesanan ini. "
                "Buat kode QR terlebih dahulu.",
            )
            return redirect("core:kasir_pembayaran", pk=pk)

        try:
            billing = services.buat_billing(pesanan)
            pembayaran = services.proses_pembayaran(
                billing=billing,
                kasir=request.pengguna,
                metode=MetodePembayaran.QRIS,
                transaksi=transaksi,
            )
        except services.KesalahanLayanan as galat:
            messages.error(request, str(galat))
            return redirect("core:kasir_pembayaran", pk=pk)

        messages.success(
            request,
            f"Pembayaran QRIS pesanan {pesanan.nomor_pesanan} dikonfirmasi. "
            f"Pesanan diteruskan ke dapur.",
        )
        return redirect("core:kasir_bukti_pembayaran", pk=pembayaran.pk)


class PembayaranView(WajibLoginMixin, View):
    """Halaman pembayaran tunai dan non tunai (AD06).

    Halaman ini memeriksa kelayakan bayar lebih dahulu. Bila pesanan
    tidak layak dibayar, kasir diarahkan kembali ke daftar pesanan
    dengan pesan kesalahan yang menjelaskan sebabnya.
    """

    template_name = "kasir/pembayaran.html"

    def get(self, request, pk):
        pesanan = get_object_or_404(
            Pesanan.objects.select_related("pelanggan").prefetch_related(
                "detail_list__produk"
            ),
            pk=pk,
        )

        # Pesanan yang sudah dibayar langsung diarahkan ke bukti bayar.
        pembayaran_lama = Pembayaran.objects.filter(billing__pesanan=pesanan).first()
        if pembayaran_lama is not None:
            return redirect("core:kasir_bukti_pembayaran", pk=pembayaran_lama.pk)

        if not pesanan.boleh_dibayar():
            messages.error(
                request,
                f"Pesanan {pesanan.nomor_pesanan} tidak dapat dibayar. "
                f"Pesanan mungkin sudah dibatalkan.",
            )
            return redirect("core:kasir_pesanan")

        try:
            billing = services.buat_billing(pesanan)
        except services.KesalahanLayanan as galat:
            messages.error(request, str(galat))
            return redirect("core:kasir_pesanan")

        konteks = {
            "pesanan": pesanan,
            "billing": billing,
            "form": FormPembayaran(billing=billing, metode_awal=pesanan.metode_dipilih),
            "judul_halaman": f"Pembayaran {pesanan.nomor_pesanan}",
            "metode_dipilih": pesanan.metode_dipilih,
            "gateway_nama": gateway_pembayaran.get_gateway().nama,
            "gateway_simulasi": gateway_pembayaran.get_gateway().simulasi,
        }

        # Untuk pesanan QRIS, transaksi gateway ikut ditampilkan supaya
        # kasir dapat melihat status pembayarannya sebelum mengonfirmasi.
        if pesanan.metode_dipilih == MetodePembayaran.QRIS:
            try:
                transaksi, _ = services.mulai_pembayaran_qris(pesanan)
            except services.KesalahanLayanan as galat:
                messages.error(request, str(galat))
                return redirect("core:kasir_pesanan")
            konteks.update(
                {
                    "transaksi": transaksi,
                    "qr_data_uri": services.gambar_qr_data_uri(transaksi),
                }
            )

        return render(request, self.template_name, konteks)

    def post(self, request, pk):
        pesanan = get_object_or_404(Pesanan, pk=pk)

        try:
            billing = services.buat_billing(pesanan)
        except services.KesalahanLayanan as galat:
            messages.error(request, str(galat))
            return redirect("core:kasir_pesanan")

        form = FormPembayaran(request.POST, billing=billing)

        if not form.is_valid():
            # Kesalahan disampaikan pada halaman yang sama supaya kasir
            # dapat langsung memperbaiki data pembayarannya.
            messages.error(
                request, "Data pembayaran belum benar. Periksa isian berikut."
            )
            return render(
                request,
                self.template_name,
                self._konteks_gagal(request, pesanan, billing, form),
            )

        # Untuk QRIS, transaksi gateway disertakan supaya layanan dapat
        # memeriksa status pembayaran yang sebenarnya sebelum menyimpan.
        transaksi = None
        if form.cleaned_data["metode"] == MetodePembayaran.QRIS:
            transaksi = services.transaksi_terakhir(pesanan)

        try:
            pembayaran = services.proses_pembayaran(
                billing=billing,
                kasir=request.pengguna,
                metode=form.cleaned_data["metode"],
                jumlah_diterima=form.cleaned_data.get("jumlah_diterima"),
                nomor_referensi=form.cleaned_data.get("nomor_referensi", ""),
                transaksi=transaksi,
            )
        except services.KesalahanLayanan as galat:
            messages.error(request, str(galat))
            return render(
                request,
                self.template_name,
                self._konteks_gagal(request, pesanan, billing, form),
            )

        messages.success(
            request,
            f"Pembayaran pesanan {pesanan.nomor_pesanan} berhasil disimpan.",
        )
        return redirect("core:kasir_bukti_pembayaran", pk=pembayaran.pk)

    def _konteks_gagal(self, request, pesanan, billing, form):
        """Menyusun konteks halaman pembayaran saat penyimpanan gagal.

        Data transaksi QRIS disertakan kembali supaya kode QR dan status
        pembayarannya tetap terlihat oleh kasir, sehingga ia dapat
        memperbaiki isian sambil tetap melihat status yang sebenarnya.
        """
        konteks = {
            "pesanan": pesanan,
            "billing": billing,
            "form": form,
            "judul_halaman": f"Pembayaran {pesanan.nomor_pesanan}",
            "metode_dipilih": pesanan.metode_dipilih,
            "gateway_nama": gateway_pembayaran.get_gateway().nama,
            "gateway_simulasi": gateway_pembayaran.get_gateway().simulasi,
        }

        transaksi = services.transaksi_terakhir(pesanan)
        if transaksi is not None:
            konteks["transaksi"] = transaksi
            konteks["qr_data_uri"] = services.gambar_qr_data_uri(transaksi)
        return konteks


class BuktiPembayaranView(WajibLoginMixin, View):
    """Bukti pembayaran yang dapat ditunjukkan ke pelanggan (AD06)."""

    template_name = "kasir/bukti_pembayaran.html"

    def get(self, request, pk):
        pembayaran = get_object_or_404(
            Pembayaran.objects.select_related(
                "billing__pesanan__pelanggan", "kasir"
            ).prefetch_related("billing__pesanan__detail_list__produk"),
            pk=pk,
        )
        konteks = {
            "pembayaran": pembayaran,
            "pesanan": pembayaran.billing.pesanan,
            "judul_halaman": "Bukti Pembayaran",
        }
        return render(request, self.template_name, konteks)


# ======================================================================
# Halaman Administrator: Produk (AD09)
# ======================================================================

class KelolaProdukView(WajibAdministratorMixin, View):
    """Daftar produk beserta penyaringan (AD09)."""

    template_name = "kelola/produk_daftar.html"

    def get(self, request):
        kategori_id = request.GET.get("kategori") or ""
        cari = request.GET.get("cari") or ""

        produk_list = Produk.objects.select_related("kategori").order_by(
            "kategori__nama", "nama"
        )
        if kategori_id:
            produk_list = produk_list.filter(kategori_id=kategori_id)
        if cari:
            produk_list = produk_list.filter(nama__icontains=cari)

        konteks = {
            "produk_list": produk_list,
            "kategori_list": services.kategori_urut(),
            "kategori_terpilih": kategori_id,
            "cari": cari,
            "judul_halaman": "Kelola Data Produk",
        }
        return render(request, self.template_name, konteks)


class TambahProdukView(WajibAdministratorMixin, View):
    """Menambah produk baru (AD09)."""

    template_name = "kelola/produk_form.html"

    def get(self, request):
        form = FormProduk(initial={"aktif": True})
        return render(request, self.template_name, self._konteks(form, "Tambah"))

    def post(self, request):
        form = FormProduk(request.POST)

        if not form.is_valid():
            messages.error(
                request, "Data produk belum valid. Periksa isian berikut."
            )
            return render(request, self.template_name, self._konteks(form, "Tambah"))

        produk = form.save(commit=False)
        produk.stok = form.cleaned_data.get("stok_awal") or 0
        produk.status_stok = (
            StatusStok.TERSEDIA if produk.stok > 0 else StatusStok.HABIS
        )
        produk.save()

        messages.success(request, f"Produk {produk.nama} berhasil disimpan.")
        return redirect("core:kelola_produk")

    def _konteks(self, form, aksi):
        return {
            "form": form,
            "aksi": aksi,
            "judul_halaman": f"{aksi} Produk",
        }


class UbahProdukView(WajibAdministratorMixin, View):
    """Mengubah data produk. Stok tidak diubah di sini (lihat Kelola Stok)."""

    template_name = "kelola/produk_form.html"

    def get(self, request, pk):
        produk = get_object_or_404(Produk, pk=pk)
        form = FormProduk(instance=produk)
        return render(request, self.template_name, self._konteks(form, "Ubah"))

    def post(self, request, pk):
        produk = get_object_or_404(Produk, pk=pk)
        form = FormProduk(request.POST, instance=produk)

        if not form.is_valid():
            messages.error(
                request, "Data produk belum valid. Periksa isian berikut."
            )
            return render(request, self.template_name, self._konteks(form, "Ubah"))

        produk = form.save()
        messages.success(request, f"Produk {produk.nama} berhasil diperbarui.")
        return redirect("core:kelola_produk")

    def _konteks(self, form, aksi):
        return {
            "form": form,
            "aksi": aksi,
            "judul_halaman": f"{aksi} Produk",
        }


class HapusProdukView(WajibAdministratorMixin, View):
    """Hapus produk dengan pemeriksaan dependensi (AD09).

    Produk yang pernah dipesan tidak boleh dihapus agar riwayat pesanan
    dan laporan tetap utuh. Produk semacam ini hanya dapat
    dinonaktifkan.
    """

    template_name = "kelola/konfirmasi_hapus.html"

    def get(self, request, pk):
        produk = get_object_or_404(Produk, pk=pk)
        konteks = {
            "objek": produk,
            "jenis": "produk",
            "boleh_hapus": not services.produk_pernah_dipesan(produk),
            "alasan_tolak": (
                f"Produk {produk.nama} pernah dipesan sehingga datanya "
                f"tidak dapat dihapus. Nonaktifkan saja produk ini."
            ),
            "url_batal": "core:kelola_produk",
            "judul_halaman": "Hapus Produk",
        }
        return render(request, self.template_name, konteks)

    def post(self, request, pk):
        produk = get_object_or_404(Produk, pk=pk)

        if services.produk_pernah_dipesan(produk):
            messages.error(
                request,
                f"Produk {produk.nama} pernah dipesan sehingga tidak dapat "
                f"dihapus. Nonaktifkan saja produk ini.",
            )
            return redirect("core:kelola_produk")

        nama = produk.nama
        produk.delete()
        messages.success(request, f"Produk {nama} berhasil dihapus.")
        return redirect("core:kelola_produk")


# ======================================================================
# Halaman Administrator: Kategori (AD10)
# ======================================================================

class KelolaKategoriView(WajibAdministratorMixin, View):
    """Daftar kategori produk (AD10)."""

    template_name = "kelola/kategori_daftar.html"

    def get(self, request):
        konteks = {
            "kategori_list": KategoriProduk.objects.order_by("nama"),
            "judul_halaman": "Kelola Kategori Produk",
        }
        return render(request, self.template_name, konteks)


class TambahKategoriView(WajibAdministratorMixin, View):
    """Menambah kategori produk (AD10)."""

    template_name = "kelola/kategori_form.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "form": FormKategori(),
                "aksi": "Tambah",
                "tipe_tersedia": services.tipe_kategori_terpakai(),
                "judul_halaman": "Tambah Kategori",
            },
        )

    def post(self, request):
        form = FormKategori(request.POST)

        if not form.is_valid():
            messages.error(
                request, "Data kategori belum valid. Periksa isian berikut."
            )
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "aksi": "Tambah",
                    "tipe_tersedia": services.tipe_kategori_terpakai(),
                    "judul_halaman": "Tambah Kategori",
                },
            )

        kategori = form.save()
        messages.success(request, f"Kategori {kategori.nama} berhasil disimpan.")
        return redirect("core:kelola_kategori")


class UbahKategoriView(WajibAdministratorMixin, View):
    """Mengubah kategori produk (AD10)."""

    template_name = "kelola/kategori_form.html"

    def get(self, request, pk):
        kategori = get_object_or_404(KategoriProduk, pk=pk)
        return render(
            request,
            self.template_name,
            {
                "form": FormKategori(instance=kategori),
                "aksi": "Ubah",
                "tipe_tersedia": services.tipe_kategori_terpakai(),
                "judul_halaman": "Ubah Kategori",
            },
        )

    def post(self, request, pk):
        kategori = get_object_or_404(KategoriProduk, pk=pk)
        form = FormKategori(request.POST, instance=kategori)

        if not form.is_valid():
            messages.error(
                request, "Data kategori belum valid. Periksa isian berikut."
            )
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "aksi": "Ubah",
                    "tipe_tersedia": services.tipe_kategori_terpakai(),
                    "judul_halaman": "Ubah Kategori",
                },
            )

        kategori = form.save()
        messages.success(request, f"Kategori {kategori.nama} berhasil diperbarui.")
        return redirect("core:kelola_kategori")


class HapusKategoriView(WajibAdministratorMixin, View):
    """Hapus kategori dengan pemeriksaan dependensi (AD10).

    Kategori yang masih dipakai produk tidak boleh dihapus supaya
    produk tidak kehilangan kategorinya.
    """

    template_name = "kelola/konfirmasi_hapus.html"

    def get(self, request, pk):
        kategori = get_object_or_404(KategoriProduk, pk=pk)
        konteks = {
            "objek": kategori,
            "jenis": "kategori",
            "boleh_hapus": not services.kategori_dipakai(kategori),
            "alasan_tolak": (
                f"Kategori {kategori.nama} masih dipakai oleh "
                f"{kategori.produk_list.count()} produk sehingga tidak "
                f"dapat dihapus. Pindahkan atau hapus produknya terlebih dahulu."
            ),
            "url_batal": "core:kelola_kategori",
            "judul_halaman": "Hapus Kategori",
        }
        return render(request, self.template_name, konteks)

    def post(self, request, pk):
        kategori = get_object_or_404(KategoriProduk, pk=pk)

        if services.kategori_dipakai(kategori):
            messages.error(
                request,
                f"Kategori {kategori.nama} masih dipakai oleh "
                f"{kategori.produk_list.count()} produk sehingga tidak "
                f"dapat dihapus.",
            )
            return redirect("core:kelola_kategori")

        nama = kategori.nama
        kategori.delete()
        messages.success(request, f"Kategori {nama} berhasil dihapus.")
        return redirect("core:kelola_kategori")


# ======================================================================
# Halaman Administrator: Kelola Stok (AD07)
# ======================================================================

class KelolaStokView(WajibAdministratorMixin, View):
    """Daftar stok produk dengan penyaringan kategori dan status (AD07)."""

    template_name = "kelola/stok_daftar.html"

    def get(self, request):
        kategori_id = request.GET.get("kategori") or ""
        status_pilih = request.GET.get("status") or ""
        cari = request.GET.get("cari") or ""

        produk_list = services.filter_stok(
            kategori=kategori_id or None,
            status=status_pilih or None,
            cari=cari or None,
        )

        konteks = {
            "produk_list": produk_list,
            "kategori_list": services.kategori_urut(),
            "status_list": StatusStok.choices,
            "kategori_terpilih": kategori_id,
            "status_terpilih": status_pilih,
            "cari": cari,
            "judul_halaman": "Kelola Stok Produk",
        }
        return render(request, self.template_name, konteks)


class AturStokView(WajibAdministratorMixin, View):
    """Formulir input dan pembaruan stok satu produk (AD07).

    Nilai yang diisi adalah nilai akhir stok. Status Tersedia atau
    Habis ditentukan otomatis dari nilai tersebut.
    """

    template_name = "kelola/stok_form.html"

    def get(self, request, pk):
        produk = get_object_or_404(
            Produk.objects.select_related("kategori"), pk=pk
        )
        form = FormStok(initial={"jumlah_stok": produk.stok})
        return render(request, self.template_name, self._konteks(produk, form))

    def post(self, request, pk):
        produk = get_object_or_404(
            Produk.objects.select_related("kategori"), pk=pk
        )
        form = FormStok(request.POST)

        if not form.is_valid():
            messages.error(
                request, "Jumlah stok belum valid. Periksa isian berikut."
            )
            return render(request, self.template_name, self._konteks(produk, form))

        try:
            services.atur_stok_produk(produk, form.cleaned_data["jumlah_stok"])
        except services.KesalahanLayanan as galat:
            messages.error(request, str(galat))
            return render(request, self.template_name, self._konteks(produk, form))

        messages.success(
            request,
            f"Stok {produk.nama} berhasil disimpan menjadi {produk.stok} "
            f"({produk.get_status_stok_display()}).",
        )
        return redirect("core:kelola_stok")

    def _konteks(self, produk, form):
        return {
            "produk": produk,
            "form": form,
            "judul_halaman": f"Atur Stok: {produk.nama}",
        }


# ======================================================================
# Halaman Administrator: Laporan Penjualan (AD08)
# ======================================================================

class LaporanView(WajibAdministratorMixin, View):
    """Laporan penjualan mingguan dan bulanan (AD08).

    Hanya pesanan berstatus DIBAYAR yang dihitung. Bila tidak ada data
    pada periode yang dipilih, halaman menampilkan pesan bahwa belum
    ada data penjualan, bukan angka nol tanpa keterangan.
    """

    template_name = "kelola/laporan.html"

    def get(self, request):
        """Menampilkan laporan periode berjalan tanpa perlu menekan apa pun.

        Halaman ini langsung menghitung dan menampilkan laporan periode
        pekan berjalan saat dibuka, sama seperti halaman katalog lain
        yang langsung menampilkan datanya. Administrator dapat mengubah
        periode lalu menekan Tampilkan untuk melihat periode lain.
        """
        hari_ini = timezone.localdate()
        periode = request.GET.get("periode") or PeriodeLaporan.MINGGUAN

        tanggal_mulai, tanggal_selesai = services.hitung_periode_laporan(
            periode, hari_ini
        )

        form = FormLaporan(
            initial={
                "periode": periode,
                "tanggal_mulai": tanggal_mulai,
                "tanggal_selesai": tanggal_selesai,
            }
        )

        # Hitung laporan periode berjalan, tanpa menyimpan ke riwayat.
        # Penyimpanan hanya terjadi saat Administrator menekan Tampilkan,
        # supaya membuka halaman tidak menumpuk riwayat laporan.
        try:
            laporan = services.buat_laporan(
                periode, tanggal_mulai, tanggal_selesai, simpan=False
            )
            rincian = services.rincian_laporan(tanggal_mulai, tanggal_selesai)
        except services.KesalahanLayanan:
            laporan = None
            rincian = []

        konteks = {
            "form": form,
            "laporan": laporan,
            "rincian": rincian,
            "judul_halaman": "Laporan Penjualan",
        }
        return render(request, self.template_name, konteks)

    def post(self, request):
        form = FormLaporan(request.POST)

        if not form.is_valid():
            messages.error(
                request, "Periode laporan belum valid. Periksa isian berikut."
            )
            return render(
                request,
                self.template_name,
                {"form": form, "judul_halaman": "Laporan Penjualan"},
            )

        periode = form.cleaned_data["periode"]
        tanggal_mulai = form.cleaned_data["tanggal_mulai"]
        tanggal_selesai = form.cleaned_data["tanggal_selesai"]

        try:
            laporan = services.buat_laporan(periode, tanggal_mulai, tanggal_selesai)
        except services.KesalahanLayanan as galat:
            messages.error(request, str(galat))
            return render(
                request,
                self.template_name,
                {"form": form, "judul_halaman": "Laporan Penjualan"},
            )

        rincian = services.rincian_laporan(tanggal_mulai, tanggal_selesai)

        if laporan.total_penjualan == 0 and not rincian.exists():
            messages.warning(
                request,
                "Tidak ada data penjualan pada periode yang dipilih.",
            )

        konteks = {
            "form": form,
            "laporan": laporan,
            "rincian": rincian,
            "judul_halaman": "Laporan Penjualan",
        }
        return render(request, self.template_name, konteks)


# ======================================================================
# Halaman Administrator: Pengguna (AD11)
# ======================================================================

class KelolaPenggunaView(WajibAdministratorMixin, View):
    """Daftar pengguna aplikasi (AD11)."""

    template_name = "kelola/pengguna_daftar.html"

    def get(self, request):
        konteks = {
            "pengguna_list": Pengguna.objects.order_by("role", "username"),
            "pengguna_saat_ini": request.pengguna,
            "judul_halaman": "Kelola Pengguna",
        }
        return render(request, self.template_name, konteks)


class TambahPenggunaView(WajibAdministratorMixin, View):
    """Menambah pengguna baru, password langsung disimpan ter-hash (AD11)."""

    template_name = "kelola/pengguna_form.html"

    def get(self, request):
        form = FormPengguna(initial={"aktif": True, "role": Role.KASIR})
        form.pengguna_saat_ini = request.pengguna
        return render(
            request,
            self.template_name,
            {"form": form, "aksi": "Tambah", "judul_halaman": "Tambah Pengguna"},
        )

    def post(self, request):
        form = FormPengguna(request.POST)
        form.pengguna_saat_ini = request.pengguna

        if not form.is_valid():
            messages.error(
                request, "Data pengguna belum valid. Periksa isian berikut."
            )
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "aksi": "Tambah",
                    "judul_halaman": "Tambah Pengguna",
                },
            )

        pengguna = form.save(commit=False)
        pengguna.set_password(form.cleaned_data["password"])
        pengguna.save()

        messages.success(request, f"Pengguna {pengguna.username} berhasil disimpan.")
        return redirect("core:kelola_pengguna")


class UbahPenggunaView(WajibAdministratorMixin, View):
    """Mengubah data pengguna. Password boleh dikosongkan (AD11)."""

    template_name = "kelola/pengguna_form.html"

    def get(self, request, pk):
        pengguna = get_object_or_404(Pengguna, pk=pk)
        form = FormPengguna(instance=pengguna)
        form.pengguna_saat_ini = request.pengguna
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "aksi": "Ubah",
                "pengguna": pengguna,
                "judul_halaman": "Ubah Pengguna",
            },
        )

    def post(self, request, pk):
        pengguna = get_object_or_404(Pengguna, pk=pk)
        form = FormPengguna(request.POST, instance=pengguna)
        form.pengguna_saat_ini = request.pengguna

        if not form.is_valid():
            messages.error(
                request, "Data pengguna belum valid. Periksa isian berikut."
            )
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "aksi": "Ubah",
                    "pengguna": pengguna,
                    "judul_halaman": "Ubah Pengguna",
                },
            )

        pengguna = form.save(commit=False)
        password_baru = form.cleaned_data.get("password")
        if password_baru:
            # Password di-hash ulang hanya bila diisi.
            pengguna.set_password(password_baru)
        pengguna.save()

        messages.success(request, f"Pengguna {pengguna.username} berhasil diperbarui.")
        return redirect("core:kelola_pengguna")


class HapusPenggunaView(WajibAdministratorMixin, View):
    """Hapus pengguna dengan pemeriksaan dependensi (AD11).

    Akun yang sedang dipakai login dan pengguna yang pernah menangani
    pembayaran tidak dapat dihapus.
    """

    template_name = "kelola/konfirmasi_hapus.html"

    def get(self, request, pk):
        pengguna = get_object_or_404(Pengguna, pk=pk)
        konteks = {
            "objek": pengguna,
            "jenis": "pengguna",
            "boleh_hapus": services.pengguna_boleh_dihapus(
                pengguna, request.pengguna
            ),
            "alasan_tolak": services.alasan_pengguna_tidak_boleh_dihapus(
                pengguna, request.pengguna
            ),
            "url_batal": "core:kelola_pengguna",
            "judul_halaman": "Hapus Pengguna",
        }
        return render(request, self.template_name, konteks)

    def post(self, request, pk):
        pengguna = get_object_or_404(Pengguna, pk=pk)

        if not services.pengguna_boleh_dihapus(pengguna, request.pengguna):
            messages.error(
                request,
                services.alasan_pengguna_tidak_boleh_dihapus(
                    pengguna, request.pengguna
                ),
            )
            return redirect("core:kelola_pengguna")

        username = pengguna.username
        pengguna.delete()
        messages.success(request, f"Pengguna {username} berhasil dihapus.")
        return redirect("core:kelola_pengguna")
