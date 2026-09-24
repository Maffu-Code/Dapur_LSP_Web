"""
Formulir aplikasi Dapur Ina Aina
================================

Seluruh formulir diletakkan di satu berkas ini agar mudah ditunjukkan
kepada asesor: satu tempat untuk semua validasi masukan. Validasi di
sini bersifat wajib (server side) dan selalu dijalankan walau tampilan
sudah memakai atribut HTML seperti required.

Pesan kesalahan memakai bahasa Indonesia dan menyebutkan penyebabnya
secara spesifik, sesuai panduan tampilan aplikasi.
"""

from decimal import Decimal

from django import forms

from core.models import (
    KategoriEnum,
    KategoriProduk,
    MetodePembayaran,
    Pengguna,
    PeriodeLaporan,
    Produk,
    Role,
    StatusPesanan,
    StatusStok,
)


# ======================================================================
# Formulir masuk (Kasir dan Administrator)
# ======================================================================

class FormMasuk(forms.Form):
    """Formulir login. Dipakai Kasir dan Administrator.

    Pelanggan tidak memakai formulir ini karena tidak memiliki akun.
    """

    username = forms.CharField(
        label="Username",
        max_length=50,
        error_messages={"required": "Username wajib diisi."},
        widget=forms.TextInput(
            attrs={"class": "form-control", "autofocus": True, "autocomplete": "username"}
        ),
    )
    password = forms.CharField(
        label="Password",
        error_messages={"required": "Password wajib diisi."},
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "autocomplete": "current-password"}
        ),
    )


# ======================================================================
# Formulir Pelanggan
# ======================================================================

class FormPesanan(forms.Form):
    """Formulir pemesanan oleh Pelanggan.

    Field jumlah per produk dibuat dinamis mengikuti daftar produk yang
    sedang aktif, sehingga halaman menu dan formulir pesanan memakai
    data yang sama. Jumlah dikosongkan (atau 0) berarti produk tidak
    dipesan.
    """

    nama = forms.CharField(
        label="Nama Pemesan",
        max_length=100,
        error_messages={"required": "Nama pemesan wajib diisi."},
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Contoh: Budi"}
        ),
    )
    nomor_meja = forms.CharField(
        label="Nomor Meja",
        max_length=10,
        error_messages={"required": "Nomor meja wajib diisi."},
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Contoh: 5"}
        ),
    )
    metode_pembayaran = forms.ChoiceField(
        label="Metode Pembayaran",
        choices=MetodePembayaran.choices,
        initial=MetodePembayaran.TUNAI,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        error_messages={"required": "Metode pembayaran wajib dipilih."},
        help_text=(
            "Pilih Tunai untuk membayar di kasir, atau QRIS untuk "
            "membayar dengan memindai kode QR."
        ),
    )

    def __init__(self, *args, produk_list=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.produk_list = list(produk_list or [])
        # Satu field jumlah untuk setiap produk, diberi nama jumlah_<id>.
        for produk in self.produk_list:
            self.fields[f"jumlah_{produk.pk}"] = forms.IntegerField(
                label=produk.nama,
                required=False,
                min_value=0,
                max_value=999,
                widget=forms.NumberInput(
                    attrs={
                        "class": "form-control",
                        "min": "0",
                        "max": "999",
                        "step": "1",
                    }
                ),
                error_messages={
                    "min_value": "Jumlah tidak boleh negatif.",
                    "max_value": "Jumlah paling banyak 999.",
                    "invalid": "Jumlah harus berupa angka.",
                },
            )

    def item_dipilih(self):
        """Mengembalikan daftar (produk, jumlah) yang diisi lebih dari 0.

        Dipakai oleh view dan service untuk menyusun rincian pesanan.
        """
        hasil = []
        for produk in self.produk_list:
            jumlah = self.cleaned_data.get(f"jumlah_{produk.pk}") or 0
            if jumlah > 0:
                hasil.append((produk, jumlah))
        return hasil

    def baris(self):
        """Mengembalikan daftar pasangan (produk, field jumlah) untuk template.

        Template perlu memasangkan setiap produk dengan kolom jumlahnya.
        Karena nama field dibentuk dari id produk, pemasangan dilakukan
        di sini agar template tidak perlu mencari nama field secara
        manual.
        """
        return [
            (produk, self[f"jumlah_{produk.pk}"])
            for produk in self.produk_list
        ]

    def clean(self):
        data = super().clean()
        # Pesanan tanpa item tidak ada gunanya, jadi ditolak lebih awal
        # dengan pesan yang menjelaskan cara memperbaikinya.
        if self.is_valid() and not self.item_dipilih():
            raise forms.ValidationError(
                "Pesanan masih kosong. Isi jumlah minimal satu produk."
            )
        return data


class FormCekStatus(forms.Form):
    """Formulir pencarian pesanan berdasarkan nomor pesanan (AD03)."""

    nomor_pesanan = forms.CharField(
        label="Nomor Pesanan",
        max_length=20,
        error_messages={"required": "Nomor pesanan wajib diisi."},
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Contoh: PSN-20260923-0001",
                "autocomplete": "off",
            }
        ),
    )


# ======================================================================
# Formulir Kasir
# ======================================================================

class FormUbahStatus(forms.Form):
    """Formulir perubahan status pesanan (AD04).

    Pilihan status dibatasi pada perpindahan yang diizinkan dari status
    pesanan saat ini, sehingga pilihan yang salah tidak dapat dipilih
    sejak awal. Validasi ulang tetap dilakukan di service.
    """

    status_baru = forms.ChoiceField(
        label="Status Baru",
        error_messages={
            "required": "Status baru wajib dipilih.",
            "invalid_choice": "Status yang dipilih tidak sesuai alur pesanan.",
        },
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, pesanan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pesanan = pesanan
        if pesanan is not None:
            self.fields["status_baru"].choices = [
                (status, StatusPesanan(status).label)
                for status in pesanan.ALUR_STATUS_VALID.get(pesanan.status, [])
            ]


class FormPembayaran(forms.Form):
    """Formulir pembayaran tunai dan QRIS.

    Tunai : kasir mengisi jumlah uang diterima, sistem menghitung
            kembalian.
    QRIS  : pembayaran non tunai melalui kode QR. Kasir tidak mengisi
            apa pun selain menekan tombol konfirmasi setelah melihat
            status gateway menyatakan pembayaran berhasil. Nomor
            referensi diambil dari kode bayar transaksi gateway, bukan
            diketik manual, supaya bukti pembayaran selalu asli.

    Formulir ini dipakai hanya pada halaman kasir. Pelanggan memilih
    metode pembayaran pada formulir pemesanan (FormPesanan), dan
    pembayaran QRIS oleh pelanggan diproses melalui halaman pembayaran
    pelanggan.
    """

    metode = forms.ChoiceField(
        label="Metode Pembayaran",
        choices=MetodePembayaran.choices,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        error_messages={"required": "Metode pembayaran wajib dipilih."},
    )
    jumlah_diterima = forms.DecimalField(
        label="Jumlah Uang Diterima",
        required=False,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0"),
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0",
                "placeholder": "Contoh: 100000",
            }
        ),
        error_messages={
            "min_value": "Jumlah uang diterima tidak boleh negatif.",
            "invalid": "Jumlah uang diterima harus berupa angka.",
        },
    )

    def __init__(self, *args, billing=None, metode_awal=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.billing = billing
        # Metode yang dipilih pelanggan saat memesan dipakai sebagai
        # pilihan awal, supaya kasir tidak perlu memilih ulang dan
        # salah pilih menjadi lebih kecil kemungkinannya.
        if metode_awal and not self.is_bound:
            self.fields["metode"].initial = metode_awal

    def clean(self):
        data = super().clean()
        metode = data.get("metode")

        if metode == MetodePembayaran.TUNAI:
            jumlah = data.get("jumlah_diterima")
            if jumlah is None:
                self.add_error(
                    "jumlah_diterima", "Jumlah uang diterima wajib diisi untuk tunai."
                )
            elif self.billing is not None and jumlah < self.billing.total:
                nominal = f"{self.billing.total:,.0f}".replace(",", ".")
                self.add_error(
                    "jumlah_diterima",
                    f"Jumlah uang diterima kurang dari total tagihan "
                    f"Rp{nominal}.",
                )

        return data


# ======================================================================
# Formulir Administrator: Kategori Produk
# ======================================================================

class FormKategori(forms.ModelForm):
    """Formulir tambah dan ubah kategori produk (AD10).

    Tipe kategori diisi bebas oleh Administrator, tidak dipilih dari
    daftar tetap. Alasannya: menambah kategori baru tidak boleh
    bergantung pada kategori yang sudah ada. Administrator cukup
    mengetik nama tipe yang diinginkan, misalnya "Dessert" atau
    "Paket Hemat", tanpa perlu membuat kategori lain lebih dahulu.

    Penulisan tipe dirapikan otomatis: spasi berlebih dibuang dan
    huruf awal setiap kata dijadikan huruf besar, supaya "dessert"
    dan "Dessert" tidak menjadi dua tipe yang berbeda.
    """

    tipe = forms.CharField(
        max_length=20,
        label="Tipe Kategori",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Contoh: Dessert",
                "list": "daftar-tipe-kategori",
                "autocomplete": "off",
            }
        ),
        error_messages={
            "required": "Tipe kategori wajib diisi.",
            "max_length": "Tipe kategori paling panjang 20 karakter.",
        },
    )

    class Meta:
        model = KategoriProduk
        fields = ["nama", "tipe"]
        labels = {"nama": "Nama Kategori", "tipe": "Tipe Kategori"}
        widgets = {
            "nama": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Contoh: Minuman"}
            ),
        }
        error_messages = {
            "nama": {
                "required": "Nama kategori wajib diisi.",
                "unique": "Nama kategori tersebut sudah dipakai.",
            },
        }

    def clean_tipe(self):
        """Merapikan tulisan tipe: buang spasi lebih dan samakan huruf."""
        tipe = " ".join(self.cleaned_data["tipe"].split())
        return tipe.title()


# ======================================================================
# Formulir Administrator: Produk
# ======================================================================

class FormProduk(forms.ModelForm):
    """Formulir tambah dan ubah produk (AD09).

    Field stok tidak ada di sini karena pengelolaan stok punya halaman
    tersendiri (kelola stok, AD07). Namun saat menambah produk baru,
    stok awal diisi lewat field tambahan di bawah.
    """

    stok_awal = forms.IntegerField(
        label="Stok Awal",
        required=False,
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
        error_messages={
            "min_value": "Stok awal tidak boleh negatif.",
            "invalid": "Stok awal harus berupa angka.",
        },
        help_text="Diisi saat menambah produk baru. Perubahan stok "
        "berikutnya dilakukan pada halaman Kelola Stok.",
    )

    class Meta:
        model = Produk
        fields = ["nama", "kategori", "deskripsi", "harga", "aktif"]
        labels = {
            "nama": "Nama Produk",
            "kategori": "Kategori",
            "deskripsi": "Deskripsi",
            "harga": "Harga",
            "aktif": "Produk Aktif",
        }
        widgets = {
            "nama": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Contoh: Nasi Goreng"}
            ),
            "kategori": forms.Select(attrs={"class": "form-select"}),
            "deskripsi": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Keterangan singkat produk (boleh dikosongkan)",
                }
            ),
            "harga": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "aktif": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        error_messages = {
            "nama": {"required": "Nama produk wajib diisi."},
            "kategori": {"required": "Kategori wajib dipilih."},
            "harga": {
                "required": "Harga wajib diisi.",
                "invalid": "Harga harus berupa angka.",
                "min_value": "Harga tidak boleh negatif.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Saat mengubah produk yang sudah ada, stok diatur di halaman
        # kelola stok, jadi field stok_awal tidak ditampilkan.
        if self.instance and self.instance.pk:
            self.fields.pop("stok_awal", None)

    def clean_harga(self):
        harga = self.cleaned_data["harga"]
        if harga is not None and harga <= 0:
            raise forms.ValidationError("Harga harus lebih dari 0.")
        return harga

    def clean(self):
        """Mewajibkan stok awal saat menambah produk baru."""
        data = super().clean()
        if not (self.instance and self.instance.pk) and data.get("stok_awal") is None:
            # Kosong dianggap 0 agar produk baru boleh langsung disimpan
            # walau stoknya belum tersedia.
            data["stok_awal"] = 0
        return data


# ======================================================================
# Formulir Administrator: Pengguna
# ======================================================================

class FormPengguna(forms.ModelForm):
    """Formulir tambah dan ubah pengguna (AD11).

    Saat menambah pengguna, password wajib diisi dan langsung disimpan
    dalam bentuk hash. Saat mengubah pengguna, password boleh
    dikosongkan yang berarti password lama tetap dipakai.
    """

    password = forms.CharField(
        label="Password",
        required=False,
        min_length=8,
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "autocomplete": "new-password"}
        ),
        error_messages={"min_length": "Password minimal 8 karakter."},
        help_text="Minimal 8 karakter. Saat mengubah data, kosongkan "
        "bila password tidak ingin diganti.",
    )

    class Meta:
        model = Pengguna
        fields = ["username", "nama", "role", "aktif"]
        labels = {
            "username": "Username",
            "nama": "Nama Lengkap",
            "role": "Peran",
            "aktif": "Akun Aktif",
        }
        widgets = {
            "username": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Contoh: kasir1"}
            ),
            "nama": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Contoh: Siti Aminah"}
            ),
            "role": forms.Select(attrs={"class": "form-select"}),
            "aktif": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        error_messages = {
            "username": {
                "required": "Username wajib diisi.",
                "unique": "Username tersebut sudah dipakai.",
            },
            "nama": {"required": "Nama lengkap wajib diisi."},
            "role": {"required": "Peran wajib dipilih."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Password wajib saat membuat pengguna baru.
        if not (self.instance and self.instance.pk):
            self.fields["password"].required = True
            self.fields["password"].error_messages["required"] = (
                "Password wajib diisi untuk pengguna baru."
            )

    def clean_aktif(self):
        """Mencegah Administrator menonaktifkan akunnya sendiri.

        Tanpa aturan ini, Administrator dapat mengunci dirinya sendiri
        keluar dari aplikasi.
        """
        aktif = self.cleaned_data["aktif"]
        pengguna_saat_ini = getattr(self, "pengguna_saat_ini", None)
        if (
            not aktif
            and pengguna_saat_ini is not None
            and self.instance.pk == pengguna_saat_ini.pk
        ):
            raise forms.ValidationError(
                "Akun yang sedang Anda pakai tidak dapat dinonaktifkan."
            )
        return aktif


# ======================================================================
# Formulir Administrator: Kelola Stok
# ======================================================================

class FormStok(forms.Form):
    """Formulir input dan pembaruan stok produk (AD07).

    Nilai yang diisi adalah nilai akhir stok, bukan penambahan, supaya
    maksudnya jelas bagi Administrator.
    """

    jumlah_stok = forms.IntegerField(
        label="Jumlah Stok",
        min_value=0,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": "0", "step": "1"}
        ),
        error_messages={
            "required": "Jumlah stok wajib diisi.",
            "min_value": "Jumlah stok tidak boleh negatif.",
            "invalid": "Jumlah stok harus berupa angka.",
        },
        help_text="Status Tersedia atau Habis akan disesuaikan "
        "otomatis dari nilai ini.",
    )


# ======================================================================
# Formulir Administrator: Laporan Penjualan
# ======================================================================

class FormLaporan(forms.Form):
    """Formulir pemilihan periode laporan penjualan (AD08)."""

    periode = forms.ChoiceField(
        label="Jenis Laporan",
        choices=PeriodeLaporan.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
        error_messages={"required": "Jenis laporan wajib dipilih."},
    )
    tanggal_mulai = forms.DateField(
        label="Tanggal Mulai",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        error_messages={
            "required": "Tanggal mulai wajib diisi.",
            "invalid": "Tanggal mulai tidak valid.",
        },
    )
    tanggal_selesai = forms.DateField(
        label="Tanggal Selesai",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        error_messages={
            "required": "Tanggal selesai wajib diisi.",
            "invalid": "Tanggal selesai tidak valid.",
        },
    )

    def clean(self):
        """Memastikan rentang tanggal masuk akal (AD08)."""
        data = super().clean()
        mulai = data.get("tanggal_mulai")
        selesai = data.get("tanggal_selesai")
        if mulai and selesai and selesai < mulai:
            raise forms.ValidationError(
                "Tanggal selesai tidak boleh lebih awal dari tanggal mulai."
            )
        return data
