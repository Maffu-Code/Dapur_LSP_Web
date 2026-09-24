"""
Konfigurasi Django - Sistem Informasi Restoran Dapur Ina Aina
=============================================================

Proyek ini dijalankan secara lokal (tanpa deployment) untuk keperluan
ujikom Associate Programmer LSP UG. Seluruh aset tampilan disimpan
secara lokal pada folder static/, sehingga aplikasi tetap tampil dengan
benar walau komputer lab tidak terhubung ke internet.

Catatan penamaan: folder proyek ini bernama config/ (bawaan perintah
django-admin startproject), sedangkan aplikasi utamanya bernama core/
dan berisi model sesuai Class Diagram.
"""

from pathlib import Path

# BASE_DIR menunjuk ke folder akar proyek, yaitu folder yang memuat
# manage.py. Semua path lain diturunkan dari sini agar proyek tetap
# jalan walau folder dipindah ke komputer lain.
BASE_DIR = Path(__file__).resolve().parent.parent


# ----------------------------------------------------------------------
# Keamanan dasar
# ----------------------------------------------------------------------
# SECRET_KEY hanya dipakai untuk menandatangani sesi dan token CSRF pada
# aplikasi lokal. Nilai ini berasal dari hasil django-admin startproject
# dan tidak perlu dirahasiakan karena aplikasi tidak pernah dipublikasi.
SECRET_KEY = "django-insecure-s!aspqp!7*16t%g)u(+e(4uf_9wdn%i(wr@oj80l52x2=s*a&-"

# DEBUG = True memudahkan proses belajar dan demonstrasi error saat ujikom,
# karena halaman error Django menampilkan traceback lengkap.
DEBUG = True

# Dijalankan hanya di komputer lokal, jadi cukup localhost.
# "testserver" ditambahkan agar pengujian otomatis (Tugas 4) dapat
# memakai test client bawaan Django tanpa mengubah pengaturan lagi.
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]


# ----------------------------------------------------------------------
# Aplikasi yang dipakai
# ----------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Aplikasi utama: memuat model sesuai Class Diagram Dapur Ina Aina.
    "core",
]

# Urutan middleware bawaan Django. CsrfViewMiddleware wajib aktif
# (lihat kebutuhan non-fungsional: CSRF aktif) dan MessagesMiddleware
# dipakai untuk menampilkan pesan sukses/gagal berbahasa Indonesia.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Menempelkan objek Pengguna yang sedang login ke setiap request
    # sebagai request.pengguna. Ditempatkan setelah SessionMiddleware
    # karena membaca data dari sesi.
    "core.middleware.PenggunaSesiMiddleware",
]

ROOT_URLCONF = "config.urls"

# Template disimpan pada folder templates/ di akar proyek supaya mudah
# ditunjukkan ke asesor: satu tempat untuk seluruh halaman aplikasi.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Menyediakan penanda menu aktif untuk sidebar pada
                # halaman Kasir dan Administrator.
                "core.context_processors.penanda_menu",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ----------------------------------------------------------------------
# Basis data: satu berkas SQLite (lihat kebutuhan non-fungsional)
# ----------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# ----------------------------------------------------------------------
# Validasi password bawaan Django
# ----------------------------------------------------------------------
# Dipakai oleh form pengguna agar password yang dibuat Administrator
# tidak terlalu lemah.
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# ----------------------------------------------------------------------
# Bahasa dan zona waktu
# ----------------------------------------------------------------------
LANGUAGE_CODE = "id"
TIME_ZONE = "Asia/Jakarta"
USE_I18N = True
USE_TZ = True

# Pemisah ribuan pada nilai uang. Dengan pengaturan ini, angka yang
# ditampilkan di seluruh halaman memakai tanda titik sebagai pemisah
# satuan, misalnya 55000 menjadi 55.000 dan 1234567 menjadi 1.234.567.
# Pemisah mengikuti bahasa pada LANGUAGE_CODE, jadi tanda titik memang
# sesuai untuk bahasa Indonesia.
#
# Nilai yang diisi pengguna pada formulir tidak terpengaruh, karena
# kolom masukan bertipe angka selalu dikirim dalam bentuk polos
# (25000), sehingga validasi formulir tetap berjalan seperti biasa.
USE_THOUSAND_SEPARATOR = True


# ----------------------------------------------------------------------
# Berkas statis (CSS/JS/gambar)
# ----------------------------------------------------------------------
# Seluruh CSS dan JS disimpan lokal di static/vendor/ (Bootstrap 5)
# dan static/css/ untuk gaya tambahan. Tidak memakai CDN agar aplikasi
# tetap berjalan tanpa internet.
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]


# ----------------------------------------------------------------------
# Payment gateway (pembayaran non tunai / QRIS)
# ----------------------------------------------------------------------
# Aplikasi tidak memanggil penyedia gateway secara langsung, melainkan
# melalui antarmuka pada core/gateway.py. Penggantian penyedia cukup
# dilakukan pada satu baris di bawah ini.
#
# Saat ini dipakai GatewayMockup, yaitu tiruan gateway QRIS yang
# berjalan di dalam aplikasi, karena akun penyedia sungguhan belum
# tersedia. Alur verifikasinya sengaja dibuat sama dengan gateway
# sungguhan (notifikasi bertanda tangan), sehingga penggantian penyedia
# tidak memerlukan perubahan pada view, layanan, maupun model.
GATEWAY_PEMBAYARAN = "core.gateway.GatewayMockup"

# Kunci rahasia untuk menandatangani notifikasi gateway pada mockup.
#
# Peringatan: nilai ini hanya untuk keperluan demonstrasi di komputer
# sendiri. Pada penyedia sungguhan, kunci ini wajib dibaca dari
# variabel lingkungan dan tidak boleh ditulis di dalam berkas ini,
# supaya tidak ikut tersebar bersama kode program.
GATEWAY_MOCK_KEY = "kunci-mockup-dapur-ina-aina"


# ----------------------------------------------------------------------
# Lain-lain
# ----------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Autentikasi memakai model Pengguna sendiri (lihat core/autentikasi.py),
# bukan django.contrib.auth.User. Nama URL ini mengikuti ruang nama app
# core (core/urls.py memakai app_name = "core"), jadi wajib berbentuk
# "core:masuk" dan bukan "masuk".
LOGIN_URL = "core:masuk"
